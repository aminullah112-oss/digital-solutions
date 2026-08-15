import { NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";
import { sendChannelMessage } from "@/lib/channels/senders";

export async function POST(_req: Request, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const followUp = await prisma.followUp.findUnique({ where: { id }, include: { customer: true } });
  if (!followUp) return NextResponse.json({ error: "Not found" }, { status: 404 });

  if (followUp.conversationId) {
    const conversation = await prisma.conversation.findUnique({ where: { id: followUp.conversationId } });
    await prisma.message.create({
      data: { conversationId: followUp.conversationId, sender: "STAFF", text: followUp.suggestedMessage },
    });
    await prisma.conversation.update({
      where: { id: followUp.conversationId },
      data: { status: "WAITING_CUSTOMER", lastMessageAt: new Date() },
    });
    if (conversation) {
      const recipient = conversation.channel === "WHATSAPP" ? followUp.customer.phone : followUp.customer.externalId;
      await sendChannelMessage(conversation.channel, recipient, followUp.suggestedMessage);
    }
  }

  await prisma.followUp.update({
    where: { id },
    data: { status: "SENT", completedAt: new Date(), approvedById: session.sub },
  });

  return NextResponse.json({ ok: true });
}
