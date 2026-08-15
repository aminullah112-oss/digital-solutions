import { prisma } from "@/lib/db/prisma";

export interface Insight {
  id: string;
  title: string;
  whatHappened: string;
  whyItMatters: string;
  recommendation: string;
  expectedImpact: string;
  confidence: number; // 0-100
}

function confidenceFromSampleSize(n: number, cap = 90) {
  return Math.min(cap, Math.round(30 + n * 6));
}

async function channelComparisonInsight(): Promise<Insight | null> {
  const customers = await prisma.customer.groupBy({ by: ["source"], _count: { _all: true } });
  const bookings = await prisma.booking.groupBy({ by: ["source"], _count: { _all: true } });

  const total = customers.reduce((sum, c) => sum + c._count._all, 0);
  if (total === 0) return null;

  const rates = customers.map((c) => {
    const bookingCount = bookings.find((b) => b.source === c.source)?._count._all ?? 0;
    return { channel: c.source, leadShare: c._count._all / total, bookingsPerLead: c._count._all > 0 ? bookingCount / c._count._all : 0, leads: c._count._all };
  });

  const topShare = [...rates].sort((a, b) => b.leadShare - a.leadShare)[0];
  const topConverter = [...rates].sort((a, b) => b.bookingsPerLead - a.bookingsPerLead)[0];
  if (!topShare || !topConverter || topShare.channel === topConverter.channel) return null;

  const diffPct = Math.round((topConverter.bookingsPerLead - topShare.bookingsPerLead) * 100);
  if (diffPct <= 0) return null;

  return {
    id: "channel-comparison",
    title: `${titleCase(topShare.channel)} drives volume, ${titleCase(topConverter.channel)} converts better`,
    whatHappened: `${titleCase(topShare.channel)} generated ${Math.round(topShare.leadShare * 100)}% of new customers, but ${titleCase(topConverter.channel)} converts ${diffPct} percentage points more of its leads into bookings.`,
    whyItMatters: "High-volume channels that convert poorly are wasting the AI's fast-response advantage on leads that stall before booking.",
    recommendation: `Route qualified ${titleCase(topShare.channel)} leads into the same fast-follow-up flow that works on ${titleCase(topConverter.channel)}, or prioritize staff attention there.`,
    expectedImpact: `Potential to lift overall conversion by an estimated ${Math.max(3, Math.round(diffPct / 2))}%.`,
    confidence: confidenceFromSampleSize(topShare.leads),
  };
}

async function serviceDropOffInsight(): Promise<Insight | null> {
  const leads = await prisma.lead.findMany({ where: { serviceId: { not: null } }, include: { customer: true, service: true } });
  const byService = new Map<string, { name: string; total: number; converted: number }>();
  for (const l of leads) {
    if (!l.service) continue;
    const entry = byService.get(l.service.id) ?? { name: l.service.name, total: 0, converted: 0 };
    entry.total += 1;
    if (["BOOKED", "ACTIVE_CUSTOMER", "VIP"].includes(l.customer.status)) entry.converted += 1;
    byService.set(l.service.id, entry);
  }
  const candidates = [...byService.values()].filter((s) => s.total >= 2);
  candidates.sort((a, b) => b.total - a.total - (b.converted - a.converted));
  const top = candidates.find((s) => s.converted / s.total < 0.6);
  if (!top) return null;

  const notConverted = top.total - top.converted;
  return {
    id: "service-drop-off",
    title: `${top.name} enquiries aren't converting`,
    whatHappened: `${top.total} customers asked about ${top.name} this period. ${notConverted} did not proceed to a booking.`,
    whyItMatters: "Consistent interest without conversion usually means price hesitation or availability friction, not lack of demand.",
    recommendation: `Create a targeted ${top.name} promotion or bundle, and have the AI proactively offer it when this service is mentioned.`,
    expectedImpact: `Converting even a third of stalled leads could add ${notConverted > 0 ? Math.round(notConverted / 3) : 0}+ bookings.`,
    confidence: confidenceFromSampleSize(top.total, 85),
  };
}

async function reactivationInsight(): Promise<Insight | null> {
  const inactive = await prisma.customer.findMany({ where: { status: "INACTIVE" } });
  if (inactive.length === 0) return null;

  return {
    id: "reactivation",
    title: `${inactive.length} customers have gone quiet`,
    whatHappened: `${inactive.length} customers who previously engaged have not booked or messaged recently and are now marked inactive.`,
    whyItMatters: "Reactivating an existing customer is far cheaper than acquiring a new lead from scratch.",
    recommendation: "Launch a light-touch win-back message (e.g. a seasonal offer) to this segment, respecting messaging consent rules.",
    expectedImpact: `Even a 15-20% response rate could bring back ${Math.max(1, Math.round(inactive.length * 0.15))}+ customers.`,
    confidence: confidenceFromSampleSize(inactive.length, 75),
  };
}

async function complaintRiskInsight(): Promise<Insight | null> {
  const handoffs = await prisma.humanHandoff.findMany({ where: { reason: { in: ["COMPLAINT", "REFUND_REQUEST"] } } });
  if (handoffs.length === 0) return null;

  return {
    id: "complaint-risk",
    title: `${handoffs.length} unresolved complaint${handoffs.length === 1 ? "" : "s"} need attention`,
    whatHappened: `${handoffs.length} conversations were escalated for complaints or refund requests this period.`,
    whyItMatters: "Unaddressed complaints are the fastest way to lose a customer permanently and generate negative word-of-mouth.",
    recommendation: "Review the Attention Queue now and personally follow up on every open complaint within 24 hours.",
    expectedImpact: "Fast, personal resolution can often save the relationship and even increase loyalty.",
    confidence: 90,
  };
}

async function automationOpportunityInsight(): Promise<Insight | null> {
  const [aiCount, staffCount] = await Promise.all([
    prisma.message.count({ where: { sender: "AI" } }),
    prisma.message.count({ where: { sender: "STAFF" } }),
  ]);
  const total = aiCount + staffCount;
  if (total === 0) return null;
  const aiShare = Math.round((aiCount / total) * 100);

  return {
    id: "automation-opportunity",
    title: `AI is already handling ${aiShare}% of replies`,
    whatHappened: `Of ${total} outbound replies, ${aiCount} were sent automatically by the AI and ${staffCount} required staff typing.`,
    whyItMatters: "Every manually-typed routine reply (pricing, hours, availability) is staff time that could go to complex customers instead.",
    recommendation: staffCount > aiCount
      ? "Review recent staff replies for repeated patterns and add them to the knowledge base so the AI can answer them directly."
      : "Automation coverage looks strong — focus staff time on the Attention Queue and high-value bookings.",
    expectedImpact: staffCount > 0 ? `Automating the most common manual replies could free up ${Math.round(staffCount * 0.4)}+ staff replies per period.` : "Maintain current automation coverage.",
    confidence: confidenceFromSampleSize(total, 80),
  };
}

function titleCase(s: string) {
  return s.charAt(0) + s.slice(1).toLowerCase();
}

export async function generateInsights(): Promise<Insight[]> {
  const results = await Promise.all([
    channelComparisonInsight(),
    serviceDropOffInsight(),
    reactivationInsight(),
    complaintRiskInsight(),
    automationOpportunityInsight(),
  ]);
  return results.filter((r): r is Insight => r !== null);
}
