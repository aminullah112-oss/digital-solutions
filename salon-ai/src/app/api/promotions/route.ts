import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function GET() {
  const promotions = await prisma.promotion.findMany({ orderBy: { startDate: "desc" }, include: { services: { include: { service: true } } } });
  return NextResponse.json({ promotions });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const { name, description, discountPct, startDate, endDate, serviceIds } = body;
  if (!name || !description || !startDate || !endDate) {
    return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
  }

  const promotion = await prisma.promotion.create({
    data: {
      name,
      description,
      discountPct: Number(discountPct) || 0,
      startDate: new Date(startDate),
      endDate: new Date(endDate),
      services: Array.isArray(serviceIds) ? { create: serviceIds.map((id: string) => ({ serviceId: id })) } : undefined,
    },
  });
  return NextResponse.json({ promotion });
}
