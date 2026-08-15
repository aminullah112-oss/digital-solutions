import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function GET() {
  const staff = await prisma.staff.findMany({
    orderBy: { name: "asc" },
    include: { services: { include: { service: true } }, user: true },
  });
  return NextResponse.json({ staff });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const { name, role, workingHours, serviceIds } = body;
  if (!name || !role) return NextResponse.json({ error: "Name and role are required" }, { status: 400 });

  const staff = await prisma.staff.create({
    data: {
      name,
      role,
      workingHours: workingHours || null,
      services: Array.isArray(serviceIds) ? { create: serviceIds.map((id: string) => ({ serviceId: id })) } : undefined,
    },
  });
  return NextResponse.json({ staff });
}
