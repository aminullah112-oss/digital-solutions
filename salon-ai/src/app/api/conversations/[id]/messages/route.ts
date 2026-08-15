import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const body = await req.json().catch(() => ({}));
  const text = typeof body.text === "string" ? body.text.trim() : "";
  if (!text) return NextResponse.json({ error: "Message text is required" }, { status: 400 });

  const conversation = await prisma.conversation.findUnique({ where: { id } });
  if (!conversation) return NextResponse.json({ error: "Conversation not found" }, { status: 404 });

  const message = await prisma.message.create({
    data: { conversationId: id, sender: "STAFF", text },
  });

  await prisma.conversation.update({
    where: { id },
    data: { status: "WAITING_CUSTOMER", lastMessageAt: new Date(), unreadCount: 0 },
  });

  await prisma.humanHandoff.updateMany({
    where: { conversationId: id, resolved: false },
    data: { resolved: true, resolvedAt: new Date() },
  });

  return NextResponse.json({ message });
}
