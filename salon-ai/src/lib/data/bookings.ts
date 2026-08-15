import { prisma } from "@/lib/db/prisma";

export async function listBookings() {
  return prisma.booking.findMany({
    orderBy: { date: "desc" },
    include: { customer: true, service: true, staff: true },
    take: 300,
  });
}

export async function listBookingFormOptions() {
  const [customers, services, staff] = await Promise.all([
    prisma.customer.findMany({ orderBy: { name: "asc" }, select: { id: true, name: true, phone: true } }),
    prisma.service.findMany({ where: { active: true }, orderBy: { name: "asc" } }),
    prisma.staff.findMany({ where: { active: true }, orderBy: { name: "asc" } }),
  ]);
  return { customers, services, staff };
}
