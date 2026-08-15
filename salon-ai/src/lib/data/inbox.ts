import { prisma } from "@/lib/db/prisma";

export async function listConversations() {
  const conversations = await prisma.conversation.findMany({
    orderBy: { lastMessageAt: "desc" },
    include: {
      customer: true,
      lead: { include: { service: true } },
      assignedStaff: true,
      messages: { orderBy: { createdAt: "desc" }, take: 1 },
      handoffs: { where: { resolved: false }, take: 1 },
      followUps: { where: { status: { in: ["PENDING", "SCHEDULED"] } }, take: 1 },
    },
    take: 200,
  });

  return conversations.map((c) => ({
    id: c.id,
    channel: c.channel,
    status: c.status,
    unreadCount: c.unreadCount,
    lastMessageAt: c.lastMessageAt,
    customer: { id: c.customer.id, name: c.customer.name, phone: c.customer.phone },
    lead: c.lead
      ? {
          score: c.lead.score,
          temperature: c.lead.temperature,
          intent: c.lead.intent,
          sentiment: c.lead.sentiment,
          serviceName: c.lead.service?.name ?? null,
        }
      : null,
    lastMessagePreview: c.messages[0]?.text?.slice(0, 90) ?? "",
    assignedStaff: c.assignedStaff ? { name: c.assignedStaff.name } : null,
    hasOpenHandoff: c.handoffs.length > 0,
    hasOpenFollowUp: c.followUps.length > 0,
  }));
}

export async function getConversationDetail(id: string) {
  const conversation = await prisma.conversation.findUnique({
    where: { id },
    include: {
      customer: true,
      assignedStaff: true,
      messages: { orderBy: { createdAt: "asc" } },
      lead: { include: { service: true, scoreEvents: { orderBy: { createdAt: "desc" } } } },
      handoffs: { orderBy: { createdAt: "desc" } },
      followUps: { orderBy: { createdAt: "desc" } },
    },
  });
  if (!conversation) return null;

  const previousConversations = await prisma.conversation.count({
    where: { customerId: conversation.customerId, id: { not: conversation.id } },
  });

  return { ...conversation, previousConversations };
}

export async function listStaff() {
  return prisma.staff.findMany({ where: { active: true }, orderBy: { name: "asc" } });
}
