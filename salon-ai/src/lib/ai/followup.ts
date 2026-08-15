import { prisma } from "@/lib/db/prisma";

export interface FollowUpScanOptions {
  /** Conversations idle longer than this are candidates for follow-up. */
  staleAfterMs?: number;
  /** Minimum lead score to bother following up on. */
  minScore?: number;
}

/**
 * Finds conversations that went quiet after an AI reply on a promising lead
 * and creates a FollowUp suggestion for staff to review. Safe to run repeatedly —
 * skips conversations that already have an open FollowUp.
 */
export async function scanForFollowUps(opts: FollowUpScanOptions = {}) {
  const staleAfterMs = opts.staleAfterMs ?? 1000 * 60 * 60 * 20; // 20h default
  const minScore = opts.minScore ?? 30;
  const cutoff = new Date(Date.now() - staleAfterMs);

  const candidates = await prisma.conversation.findMany({
    where: {
      lastMessageAt: { lte: cutoff },
      status: { in: ["AI_HANDLING", "WAITING_CUSTOMER", "OPEN"] },
      lead: { score: { gte: minScore } },
      followUps: { none: { status: { in: ["PENDING", "SCHEDULED"] } } },
    },
    include: { customer: true, lead: { include: { service: true } }, messages: { orderBy: { createdAt: "desc" }, take: 1 } },
  });

  const created = [];
  for (const convo of candidates) {
    if (!convo.lead) continue;
    const lastMessage = convo.messages[0];
    if (lastMessage?.sender === "CUSTOMER") continue; // waiting on staff, not a follow-up case

    const serviceName = convo.lead.service?.name ?? "their requested service";
    const suggestedMessage = `Hi ${convo.customer.name.split(" ")[0]}, just following up on ${serviceName} — we still have availability this week if you'd like to book. Let us know a day that works for you!`;

    const followUp = await prisma.followUp.create({
      data: {
        customerId: convo.customerId,
        conversationId: convo.id,
        leadId: convo.lead.id,
        reason: `No response for ${Math.round((Date.now() - convo.lastMessageAt.getTime()) / 3_600_000)}h after AI reply about ${serviceName}`,
        suggestedMessage,
      },
    });

    await prisma.aiEvent.create({
      data: {
        type: "FOLLOW_UP_CREATED",
        channel: convo.channel,
        customerName: convo.customer.name,
        conversationId: convo.id,
        summary: `Follow-up suggested for ${convo.customer.name} — ${serviceName}`,
        detail: { followUpId: followUp.id },
      },
    });

    created.push(followUp);
  }

  return created;
}
