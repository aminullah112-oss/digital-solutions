import { NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function POST(_req: Request, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const handoff = await prisma.humanHandoff.update({
    where: { id },
    data: { resolved: true, resolvedAt: new Date() },
  });

  const remaining = await prisma.humanHandoff.count({ where: { conversationId: handoff.conversationId, resolved: false } });
  if (remaining === 0) {
    await prisma.conversation.update({ where: { id: handoff.conversationId }, data: { status: "WAITING_CUSTOMER" } });
  }

  return NextResponse.json({ ok: true });
}
