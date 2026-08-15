import { prisma } from "@/lib/db/prisma";

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export async function getDashboardSnapshot() {
  const since = startOfToday();

  const [
    messagesToday,
    newLeadsToday,
    hotLeads,
    qualifiedLeads,
    totalBookings,
    bookingsToday,
    revenueAgg,
    totalConversations,
    conversationsWithHandoff,
    totalLeadsAllTime,
    customersWithBooking,
  ] = await Promise.all([
    prisma.message.count({ where: { createdAt: { gte: since }, sender: "CUSTOMER" } }),
    prisma.lead.count({ where: { createdAt: { gte: since } } }),
    prisma.lead.count({ where: { temperature: { in: ["HOT", "VERY_HOT"] } } }),
    prisma.lead.count({ where: { temperature: "QUALIFIED" } }),
    prisma.booking.count(),
    prisma.booking.count({ where: { createdAt: { gte: since } } }),
    prisma.booking.aggregate({ _sum: { price: true }, where: { status: { in: ["CONFIRMED", "COMPLETED"] } } }),
    prisma.conversation.count(),
    prisma.humanHandoff.findMany({ distinct: ["conversationId"], select: { conversationId: true } }),
    prisma.lead.count(),
    prisma.customer.count({ where: { bookings: { some: {} } } }),
  ]);

  const conversionRate = totalLeadsAllTime > 0 ? Math.round((customersWithBooking / totalLeadsAllTime) * 100) : 0;
  const aiResolutionRate =
    totalConversations > 0
      ? Math.round(((totalConversations - conversationsWithHandoff.length) / totalConversations) * 100)
      : 100;

  return {
    messagesToday,
    newLeadsToday,
    hotLeads,
    qualifiedLeads,
    totalBookings,
    bookingsToday,
    revenue: revenueAgg._sum.price ?? 0,
    conversionRate,
    aiResolutionRate,
  };
}

export async function getRecentAiEvents(limit = 25) {
  return prisma.aiEvent.findMany({ orderBy: { createdAt: "desc" }, take: limit });
}

export async function getAttentionQueueCount() {
  return prisma.humanHandoff.count({ where: { resolved: false } });
}

export async function getFollowUpCount() {
  return prisma.followUp.count({ where: { status: { in: ["PENDING", "SCHEDULED"] } } });
}
