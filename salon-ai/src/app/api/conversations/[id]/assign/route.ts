import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const body = await req.json().catch(() => ({}));
  const staffId = typeof body.staffId === "string" && body.staffId.length > 0 ? body.staffId : null;

  await prisma.conversation.update({ where: { id }, data: { assignedStaffId: staffId } });
  return NextResponse.json({ ok: true });
}
