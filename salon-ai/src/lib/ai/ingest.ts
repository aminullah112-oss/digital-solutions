import { prisma } from "@/lib/db/prisma";
import { processInboundMessage, type PipelineResult } from "./pipeline";
import type { Channel } from "@prisma/client";

export interface NormalizedInboundMessage {
  channel: Channel;
  externalCustomerId: string;
  customerName: string;
  customerPhone?: string;
  text: string;
  externalMessageId?: string;
}

/**
 * Channel Identification → Customer Identification → Conversation History,
 * then hands off to the AI pipeline. Every channel adapter normalizes its
 * payload into `NormalizedInboundMessage` and calls this function.
 */
export async function ingestChannelMessage(input: NormalizedInboundMessage): Promise<PipelineResult> {
  // Prefer matching by phone (WhatsApp), then by the channel's own sender id
  // (Instagram/Facebook PSID, website session id) so repeat senders reuse
  // the same customer record instead of spawning a new one every message.
  let customer = input.customerPhone
    ? await prisma.customer.findUnique({ where: { phone: input.customerPhone } })
    : null;

  if (!customer) {
    customer = await prisma.customer.findUnique({ where: { externalId: input.externalCustomerId } });
  }

  if (!customer) {
    customer = await prisma.customer.create({
      data: {
        name: input.customerName,
        phone: input.customerPhone,
        externalId: input.customerPhone ? null : input.externalCustomerId,
        source: input.channel,
        status: "NEW",
      },
    });
  }

  let conversation = await prisma.conversation.findFirst({
    where: { customerId: customer.id, channel: input.channel, status: { notIn: ["RESOLVED"] } },
    orderBy: { lastMessageAt: "desc" },
  });

  if (!conversation) {
    conversation = await prisma.conversation.create({
      data: { customerId: customer.id, channel: input.channel, status: "OPEN" },
    });
    await prisma.customer.update({
      where: { id: customer.id },
      data: { totalConversations: { increment: 1 } },
    });
    await prisma.aiEvent.create({
      data: {
        type: "CUSTOMER_IDENTIFIED",
        channel: input.channel,
        customerName: customer.name,
        conversationId: conversation.id,
        summary: `New conversation started with ${customer.name} on ${input.channel}`,
      },
    });
  }

  return processInboundMessage({
    conversationId: conversation.id,
    text: input.text,
    externalId: input.externalMessageId,
  });
}
