import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const body = await req.json().catch(() => ({}));
  const scheduledFor = body.scheduledFor ? new Date(body.scheduledFor) : new Date(Date.now() + 24 * 3_600_000);

  await prisma.followUp.update({ where: { id }, data: { status: "SCHEDULED", scheduledFor } });
  return NextResponse.json({ ok: true });
}
