import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function POST(_req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  await prisma.conversation.update({ where: { id }, data: { status: "RESOLVED", unreadCount: 0 } });
  await prisma.humanHandoff.updateMany({
    where: { conversationId: id, resolved: false },
    data: { resolved: true, resolvedAt: new Date() },
  });

  return NextResponse.json({ ok: true });
}
