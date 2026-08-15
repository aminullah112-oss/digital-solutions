import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function GET() {
  const bookings = await prisma.booking.findMany({
    orderBy: { date: "desc" },
    include: { customer: true, service: true, staff: true },
    take: 300,
  });
  return NextResponse.json({ bookings });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const { customerId, serviceId, staffId, date, notes } = body;
  if (!customerId || !serviceId || !date) {
    return NextResponse.json({ error: "customerId, serviceId, and date are required" }, { status: 400 });
  }

  const [customer, service] = await Promise.all([
    prisma.customer.findUnique({ where: { id: customerId } }),
    prisma.service.findUnique({ where: { id: serviceId } }),
  ]);
  if (!customer || !service) return NextResponse.json({ error: "Invalid customer or service" }, { status: 400 });

  const booking = await prisma.booking.create({
    data: {
      customerId,
      serviceId,
      staffId: staffId || null,
      date: new Date(date),
      durationMin: service.durationMin,
      price: service.price,
      status: "CONFIRMED",
      source: customer.source,
      notes: notes || null,
    },
  });

  await prisma.customer.update({ where: { id: customerId }, data: { status: "BOOKED" } });

  await prisma.aiEvent.create({
    data: {
      type: "BOOKING_CREATED",
      channel: customer.source,
      customerName: customer.name,
      summary: `Booking created for ${customer.name} — ${service.name}`,
      detail: { bookingId: booking.id, manual: true },
    },
  });

  return NextResponse.json({ booking });
}
