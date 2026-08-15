import { prisma } from "@/lib/db/prisma";

export async function getLeadSourceBreakdown() {
  const rows = await prisma.customer.groupBy({ by: ["source"], _count: { _all: true } });
  return rows.map((r) => ({ channel: r.source, count: r._count._all }));
}

export async function getConversionFunnel() {
  const [messages, leads, qualified, bookings] = await Promise.all([
    prisma.message.count({ where: { sender: "CUSTOMER" } }),
    prisma.lead.count(),
    prisma.lead.count({ where: { temperature: { in: ["QUALIFIED", "HOT", "VERY_HOT"] } } }),
    prisma.booking.count(),
  ]);
  return [
    { stage: "Messages", value: messages },
    { stage: "Leads", value: leads },
    { stage: "Qualified", value: qualified },
    { stage: "Bookings", value: bookings },
  ];
}

export async function getServiceDemand() {
  const rows = await prisma.lead.groupBy({ by: ["serviceId"], _count: { _all: true }, where: { serviceId: { not: null } } });
  const services = await prisma.service.findMany({ where: { id: { in: rows.map((r) => r.serviceId!) } } });
  return rows
    .map((r) => ({ name: services.find((s) => s.id === r.serviceId)?.name ?? "Unknown", enquiries: r._count._all }))
    .sort((a, b) => b.enquiries - a.enquiries)
    .slice(0, 8);
}

export async function getRevenueByChannel() {
  const rows = await prisma.booking.groupBy({
    by: ["source"],
    _sum: { price: true },
    where: { status: { in: ["CONFIRMED", "COMPLETED"] } },
  });
  return rows.map((r) => ({ channel: r.source, revenue: r._sum.price ?? 0 }));
}

export async function getRevenueByService() {
  const rows = await prisma.booking.groupBy({
    by: ["serviceId"],
    _sum: { price: true },
    where: { status: { in: ["CONFIRMED", "COMPLETED"] } },
  });
  const services = await prisma.service.findMany({ where: { id: { in: rows.map((r) => r.serviceId) } } });
  return rows
    .map((r) => ({ name: services.find((s) => s.id === r.serviceId)?.name ?? "Unknown", revenue: r._sum.price ?? 0 }))
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, 8);
}

export async function getRevenueByStaff() {
  const rows = await prisma.booking.groupBy({
    by: ["staffId"],
    _sum: { price: true },
    where: { status: { in: ["CONFIRMED", "COMPLETED"] }, staffId: { not: null } },
  });
  const staff = await prisma.staff.findMany({ where: { id: { in: rows.map((r) => r.staffId!) } } });
  return rows
    .map((r) => ({ name: staff.find((s) => s.id === r.staffId)?.name ?? "Unassigned", revenue: r._sum.price ?? 0 }))
    .sort((a, b) => b.revenue - a.revenue);
}

export async function getResponsePerformance() {
  const [aiCount, staffCount, totalConversations, handoffConversations] = await Promise.all([
    prisma.message.count({ where: { sender: "AI" } }),
    prisma.message.count({ where: { sender: "STAFF" } }),
    prisma.conversation.count(),
    prisma.humanHandoff.findMany({ distinct: ["conversationId"], select: { conversationId: true } }),
  ]);

  const total = aiCount + staffCount;
  const aiResponseRate = total > 0 ? Math.round((aiCount / total) * 100) : 0;
  const aiResolutionRate =
    totalConversations > 0 ? Math.round(((totalConversations - handoffConversations.length) / totalConversations) * 100) : 100;

  // Approximate avg response time: gap between each CUSTOMER message and the next AI/STAFF reply.
  const conversations = await prisma.conversation.findMany({
    include: { messages: { orderBy: { createdAt: "asc" } } },
    take: 200,
  });

  const aiGaps: number[] = [];
  const staffGaps: number[] = [];
  for (const c of conversations) {
    for (let i = 0; i < c.messages.length - 1; i++) {
      const cur = c.messages[i];
      const next = c.messages[i + 1];
      if (cur.sender === "CUSTOMER" && (next.sender === "AI" || next.sender === "STAFF")) {
        const gapSec = (next.createdAt.getTime() - cur.createdAt.getTime()) / 1000;
        if (gapSec >= 0 && gapSec < 3600 * 6) {
          (next.sender === "AI" ? aiGaps : staffGaps).push(gapSec);
        }
      }
    }
  }
  const avg = (arr: number[]) => (arr.length ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0);

  return {
    aiResponseRate,
    aiResolutionRate,
    avgAiResponseSeconds: avg(aiGaps),
    avgHumanResponseSeconds: avg(staffGaps),
  };
}
