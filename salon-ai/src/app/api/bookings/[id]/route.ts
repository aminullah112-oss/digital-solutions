import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function PATCH(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const body = await req.json().catch(() => ({}));
  const status = body.status;
  const allowed = ["PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "NO_SHOW", "RESCHEDULED"];
  if (!allowed.includes(status)) return NextResponse.json({ error: "Invalid status" }, { status: 400 });

  const booking = await prisma.booking.update({ where: { id }, data: { status } });

  if (status === "COMPLETED") {
    await prisma.customer.update({
      where: { id: booking.customerId },
      data: { totalSpend: { increment: booking.price }, lastVisitAt: new Date(), status: "ACTIVE_CUSTOMER" },
    });
  }

  return NextResponse.json({ booking });
}
