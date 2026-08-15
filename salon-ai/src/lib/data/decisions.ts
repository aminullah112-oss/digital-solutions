import { prisma } from "@/lib/db/prisma";
import type { CustomerStatus } from "@prisma/client";

const NOT_YET_BOOKED: { notIn: CustomerStatus[] } = { notIn: ["BOOKED", "ACTIVE_CUSTOMER", "VIP"] };

export async function getActNowLeads() {
  const leads = await prisma.lead.findMany({
    where: {
      temperature: { in: ["HOT", "VERY_HOT"] },
      intent: { in: ["BOOKING", "AVAILABILITY"] },
      customer: { status: NOT_YET_BOOKED },
    },
    orderBy: { score: "desc" },
    include: { customer: true, service: true },
    take: 8,
  });
  return leads;
}

export async function getRevenueOpportunity() {
  const leads = await prisma.lead.findMany({
    where: {
      temperature: { in: ["QUALIFIED", "HOT", "VERY_HOT"] },
      customer: { status: NOT_YET_BOOKED },
    },
    orderBy: { estimatedValue: "desc" },
    include: { customer: true, service: true },
    take: 8,
  });
  const total = leads.reduce((sum, l) => sum + l.estimatedValue, 0);
  return { total, leads };
}

export async function getCustomerRisk() {
  const handoffs = await prisma.humanHandoff.findMany({
    where: { resolved: false, reason: { in: ["COMPLAINT", "REFUND_REQUEST", "MANAGER_REQUESTED"] } },
    orderBy: { createdAt: "desc" },
    include: { conversation: { include: { customer: true } } },
    take: 8,
  });
  return handoffs;
}

export async function getGrowthOpportunity() {
  const rows = await prisma.lead.groupBy({ by: ["serviceId"], _count: { _all: true }, where: { serviceId: { not: null } } });
  const services = await prisma.service.findMany({ where: { id: { in: rows.map((r) => r.serviceId!) } } });
  return rows
    .map((r) => ({ service: services.find((s) => s.id === r.serviceId)!, enquiries: r._count._all }))
    .filter((r) => r.service)
    .sort((a, b) => b.enquiries - a.enquiries)
    .slice(0, 5);
}

export async function getAutomationOpportunity() {
  const [aiCount, staffCount, conversations, handoffs] = await Promise.all([
    prisma.message.count({ where: { sender: "AI" } }),
    prisma.message.count({ where: { sender: "STAFF" } }),
    prisma.conversation.count(),
    prisma.humanHandoff.findMany({ distinct: ["conversationId"] }),
  ]);
  const total = aiCount + staffCount;
  return {
    aiShare: total > 0 ? Math.round((aiCount / total) * 100) : 0,
    aiResolutionRate: conversations > 0 ? Math.round(((conversations - handoffs.length) / conversations) * 100) : 100,
    staffCount,
    aiCount,
  };
}
