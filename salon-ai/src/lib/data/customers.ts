import { prisma } from "@/lib/db/prisma";

export async function listCustomers() {
  const customers = await prisma.customer.findMany({
    orderBy: { lastContactAt: "desc" },
    take: 300,
  });
  return customers;
}

export async function getCustomerProfile(id: string) {
  const customer = await prisma.customer.findUnique({
    where: { id },
    include: {
      conversations: {
        orderBy: { lastMessageAt: "desc" },
        include: { lead: { include: { service: true } }, messages: { orderBy: { createdAt: "desc" }, take: 1 } },
      },
      bookings: { orderBy: { date: "desc" }, include: { service: true, staff: true } },
      leads: { orderBy: { createdAt: "desc" }, include: { service: true } },
    },
  });
  return customer;
}
