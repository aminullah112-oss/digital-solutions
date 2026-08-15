import { prisma } from "@/lib/db/prisma";

export async function listOpenHandoffs() {
  const handoffs = await prisma.humanHandoff.findMany({
    where: { resolved: false },
    orderBy: [{ priority: "desc" }, { createdAt: "asc" }],
    include: { conversation: { include: { customer: true } } },
  });
  // priority sort: HIGH > MEDIUM > LOW (Prisma orderBy desc on enum sorts alphabetically, so fix manually)
  const rank: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  return handoffs.sort((a, b) => rank[a.priority] - rank[b.priority]);
}

export async function listFollowUps() {
  return prisma.followUp.findMany({
    where: { status: { in: ["PENDING", "SCHEDULED"] } },
    orderBy: { createdAt: "asc" },
    include: {
      customer: true,
      lead: { include: { service: true } },
      conversation: true,
    },
  });
}
