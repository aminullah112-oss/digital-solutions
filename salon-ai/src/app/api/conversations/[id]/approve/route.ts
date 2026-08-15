import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";
import { sendChannelMessage } from "@/lib/channels/senders";
import type { Prisma } from "@prisma/client";

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const body = await req.json().catch(() => ({}));
  const messageId = typeof body.messageId === "string" ? body.messageId : null;
  if (!messageId) return NextResponse.json({ error: "messageId is required" }, { status: 400 });

  const message = await prisma.message.findUnique({ where: { id: messageId } });
  if (!message || message.conversationId !== id) {
    return NextResponse.json({ error: "Message not found" }, { status: 404 });
  }

  const conversation = await prisma.conversation.findUniqueOrThrow({ where: { id }, include: { customer: true } });

  const meta = (message.metadata as Prisma.JsonObject | null) ?? {};
  await prisma.message.update({
    where: { id: messageId },
    data: { metadata: { ...meta, pending: false, approvedBy: session.name } },
  });

  const recipient = conversation.channel === "WHATSAPP" ? conversation.customer.phone : conversation.customer.externalId;
  await sendChannelMessage(conversation.channel, recipient, message.text);

  await prisma.conversation.update({
    where: { id },
    data: { status: "AI_HANDLING", lastMessageAt: new Date(), unreadCount: 0 },
  });

  return NextResponse.json({ ok: true });
}
