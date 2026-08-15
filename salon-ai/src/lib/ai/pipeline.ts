import { prisma } from "@/lib/db/prisma";
import { runNlp } from "./nlp";
import { getServiceLexicon, getBusinessSettings, getActivePromotionSnippet } from "./knowledge";
import { scoreConversationTurn, aggregateScore, classifyTemperature, estimateBookingProbability } from "./scoring";
import { evaluateHandoff } from "./handoff";
import { getAIProvider } from "./provider";
import { sendChannelMessage } from "@/lib/channels/senders";
import type { Channel, Language } from "@prisma/client";

export interface InboundMessageInput {
  conversationId: string;
  text: string;
  externalId?: string;
}

export interface PipelineResult {
  conversationId: string;
  leadId: string;
  score: number;
  temperature: string;
  intent: string;
  sentiment: string;
  handoffCreated: boolean;
  aiResponded: boolean;
  bookingCreated: boolean;
  events: { type: string; summary: string }[];
}

/**
 * Runs one inbound customer message through the full AI pipeline:
 * NLP → lead scoring → handoff evaluation → AI response decision → persistence.
 * This is the single entry point used by both webhook handlers and the demo simulator.
 */
export async function processInboundMessage(input: InboundMessageInput): Promise<PipelineResult> {
  const conversation = await prisma.conversation.findUniqueOrThrow({
    where: { id: input.conversationId },
    include: { customer: true, lead: true },
  });

  const [services, settings] = await Promise.all([getServiceLexicon(), getBusinessSettings()]);
  const nlp = runNlp(input.text, services);
  const events: { type: string; summary: string }[] = [];

  await prisma.message.create({
    data: {
      conversationId: conversation.id,
      sender: "CUSTOMER",
      text: input.text,
      language: nlp.language,
      externalId: input.externalId,
    },
  });

  await prisma.aiEvent.create({
    data: {
      type: "PROCESSING",
      channel: conversation.channel,
      customerName: conversation.customer.name,
      conversationId: conversation.id,
      summary: `Analyzing message from ${conversation.customer.name} on ${conversation.channel}`,
      detail: { intent: nlp.intent, sentiment: nlp.sentiment },
    },
  });

  const previousConversations = await prisma.conversation.count({
    where: { customerId: conversation.customerId, id: { not: conversation.id } },
  });
  const previousCustomer = previousConversations > 0 || conversation.customer.totalBookings > 0;
  const matchedService = nlp.matchedServiceId
    ? services.find((s) => s.id === nlp.matchedServiceId) ?? null
    : null;

  let lead = conversation.lead;
  if (!lead) {
    lead = await prisma.lead.create({
      data: {
        customerId: conversation.customerId,
        conversationId: conversation.id,
        intent: nlp.intent,
        sentiment: nlp.sentiment,
        urgency: nlp.urgency,
        serviceId: matchedService?.id,
      },
    });
  }

  const scoreEvents = scoreConversationTurn({
    nlp,
    previousCustomer,
    servicePrice: matchedService?.price ?? null,
    hasPreferredDate: !!nlp.extracted.preferredDate,
    hasPreferredTime: !!nlp.extracted.preferredTime,
  });

  if (scoreEvents.length > 0) {
    await prisma.leadScore.createMany({
      data: scoreEvents.map((e) => ({ leadId: lead!.id, reason: e.reason, points: e.points })),
    });
  }

  const allEvents = await prisma.leadScore.findMany({ where: { leadId: lead.id } });
  const score = aggregateScore(allEvents);
  const temperature = classifyTemperature(score);
  const bookingProbability = estimateBookingProbability(score, nlp.askedToBook);
  const estimatedValue = matchedService?.price ?? lead.estimatedValue ?? 0;

  lead = await prisma.lead.update({
    where: { id: lead.id },
    data: {
      intent: nlp.intent,
      sentiment: nlp.sentiment,
      urgency: nlp.urgency,
      serviceId: matchedService?.id ?? lead.serviceId,
      preferredDate: nlp.extracted.preferredDate ?? lead.preferredDate,
      preferredTime: nlp.extracted.preferredTime ?? lead.preferredTime,
      budget: nlp.extracted.budget ?? lead.budget,
      score,
      temperature,
      estimatedValue,
      bookingProbability,
    },
  });

  await prisma.aiEvent.create({
    data: {
      type: "LEAD_SCORED",
      channel: conversation.channel,
      customerName: conversation.customer.name,
      conversationId: conversation.id,
      summary: `Lead score ${score}/100 (${temperature}) for ${conversation.customer.name}`,
      detail: { score, temperature, breakdown: JSON.parse(JSON.stringify(scoreEvents)) },
    },
  });
  events.push({ type: "LEAD_SCORED", summary: `Lead score ${score} — ${temperature}` });

  const newStatus = deriveCustomerStatus(conversation.customer.status, temperature, nlp.askedToBook);
  await prisma.customer.update({
    where: { id: conversation.customerId },
    data: {
      leadScore: score,
      status: newStatus,
      lastContactAt: new Date(),
      language: nlp.language,
      phone: conversation.customer.phone ?? nlp.extracted.phone ?? undefined,
      email: conversation.customer.email ?? nlp.extracted.email ?? undefined,
    },
  });

  const handoff = evaluateHandoff({ nlp, consecutiveLowConfidenceTurns: 0, consecutiveAiRejections: 0 });

  let handoffCreated = false;
  let aiResponded = false;
  let bookingCreated = false;

  if (handoff.required) {
    await prisma.humanHandoff.create({
      data: {
        conversationId: conversation.id,
        reason: handoff.reason!,
        priority: handoff.priority,
        note: handoff.note,
      },
    });
    await prisma.conversation.update({
      where: { id: conversation.id },
      data: { status: "HUMAN_REQUIRED", lastMessageAt: new Date(), unreadCount: { increment: 1 } },
    });
    await prisma.aiEvent.create({
      data: {
        type: "HUMAN_HANDOFF",
        channel: conversation.channel,
        customerName: conversation.customer.name,
        conversationId: conversation.id,
        summary: `Escalated to human: ${handoff.note}`,
        detail: { reason: handoff.reason, priority: handoff.priority },
      },
    });
    handoffCreated = true;
    events.push({ type: "HUMAN_HANDOFF", summary: handoff.note });
  } else {
    const promoSnippet = await getActivePromotionSnippet(matchedService?.id ?? null);
    const provider = getAIProvider();
    let reply: { text: string; confidence: number };
    try {
      reply = await provider.generateReply({
        customerName: conversation.customer.name,
        language: nlp.language,
        intent: nlp.intent,
        serviceName: matchedService?.name ?? null,
        servicePrice: matchedService?.price ?? null,
        businessName: settings.salonName,
        knowledgeSnippet: promoSnippet,
      });
    } catch (err) {
      console.error("[pipeline] AI provider failed, routing to human", err);
      await prisma.humanHandoff.create({
        data: { conversationId: conversation.id, reason: "LOW_AI_CONFIDENCE", priority: "MEDIUM", note: "AI response generation failed — routed to staff." },
      });
      await prisma.conversation.update({
        where: { id: conversation.id },
        data: { status: "HUMAN_REQUIRED", lastMessageAt: new Date(), unreadCount: { increment: 1 } },
      });
      await prisma.aiEvent.create({
        data: {
          type: "HUMAN_HANDOFF",
          channel: conversation.channel,
          customerName: conversation.customer.name,
          conversationId: conversation.id,
          summary: `AI failed to generate a reply — escalated to human`,
        },
      });
      return {
        conversationId: conversation.id,
        leadId: lead.id,
        score,
        temperature,
        intent: nlp.intent,
        sentiment: nlp.sentiment,
        handoffCreated: true,
        aiResponded: false,
        bookingCreated: false,
        events: [...events, { type: "HUMAN_HANDOFF", summary: "AI failure fallback" }],
      };
    }

    const shouldQueue =
      settings.aiMode === "HUMAN_APPROVAL" || (settings.aiMode === "ASSISTED" && reply.confidence < 0.65);

    await prisma.message.create({
      data: {
        conversationId: conversation.id,
        sender: "AI",
        text: reply.text,
        language: nlp.language as Language,
        metadata: { confidence: reply.confidence, pending: shouldQueue },
      },
    });

    await prisma.conversation.update({
      where: { id: conversation.id },
      data: {
        status: shouldQueue ? "HUMAN_REQUIRED" : "AI_HANDLING",
        lastMessageAt: new Date(),
        unreadCount: shouldQueue ? { increment: 1 } : 0,
      },
    });

    await prisma.aiEvent.create({
      data: {
        type: "AI_RESPONDED",
        channel: conversation.channel,
        customerName: conversation.customer.name,
        conversationId: conversation.id,
        summary: shouldQueue
          ? `AI drafted a reply for ${conversation.customer.name} — awaiting staff approval`
          : `AI responded to ${conversation.customer.name} automatically`,
        detail: { text: reply.text, confidence: reply.confidence },
      },
    });
    aiResponded = !shouldQueue;
    events.push({ type: "AI_RESPONDED", summary: reply.text.slice(0, 80) });

    if (!shouldQueue) {
      const recipient = conversation.channel === "WHATSAPP" ? conversation.customer.phone : conversation.customer.externalId;
      await sendChannelMessage(conversation.channel, recipient, reply.text);
    }

    if (nlp.askedToBook && nlp.extracted.preferredDate && nlp.extracted.preferredTime && matchedService) {
      const booking = await prisma.booking.create({
        data: {
          customerId: conversation.customerId,
          conversationId: conversation.id,
          serviceId: matchedService.id,
          date: resolveNaturalDate(nlp.extracted.preferredDate, nlp.extracted.preferredTime),
          durationMin: 60,
          status: "PENDING",
          source: conversation.channel,
          price: matchedService.price,
          notes: `Requested via ${conversation.channel} chat — ${nlp.extracted.preferredDate} ${nlp.extracted.preferredTime}`,
        },
      });
      await prisma.customer.update({ where: { id: conversation.customerId }, data: { status: "BOOKED" } });
      await prisma.aiEvent.create({
        data: {
          type: "BOOKING_CREATED",
          channel: conversation.channel,
          customerName: conversation.customer.name,
          conversationId: conversation.id,
          summary: `Booking created for ${conversation.customer.name} — ${matchedService.name}`,
          detail: { bookingId: booking.id, date: booking.date },
        },
      });
      bookingCreated = true;
      events.push({ type: "BOOKING_CREATED", summary: `${matchedService.name} booked` });
    }
  }

  return {
    conversationId: conversation.id,
    leadId: lead.id,
    score,
    temperature,
    intent: nlp.intent,
    sentiment: nlp.sentiment,
    handoffCreated,
    aiResponded,
    bookingCreated,
    events,
  };
}

function deriveCustomerStatus(
  current: string,
  temperature: string,
  askedToBook: boolean
): "NEW" | "LEAD" | "QUALIFIED" | "BOOKED" | "ACTIVE_CUSTOMER" | "VIP" | "INACTIVE" | "LOST" {
  if (askedToBook) return "BOOKED";
  if (current === "ACTIVE_CUSTOMER" || current === "VIP" || current === "BOOKED") return current;
  if (temperature === "HOT" || temperature === "VERY_HOT" || temperature === "QUALIFIED") return "QUALIFIED";
  if (temperature === "WARM") return "LEAD";
  return current === "NEW" ? "NEW" : "LEAD";
}

function resolveNaturalDate(day: string, time: string): Date {
  const now = new Date();
  const date = new Date(now);
  const lower = day.toLowerCase();
  if (lower === "today") {
    // keep today
  } else if (lower === "tomorrow") {
    date.setDate(date.getDate() + 1);
  } else {
    const days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
    const idx = days.indexOf(lower);
    if (idx >= 0) {
      const diff = (idx - date.getDay() + 7) % 7 || 7;
      date.setDate(date.getDate() + diff);
    } else {
      date.setDate(date.getDate() + 1);
    }
  }
  const timeMatch = time.match(/(\d{1,2})(:(\d{2}))?\s?(am|pm)?/i);
  let hour = timeMatch ? Number(timeMatch[1]) : 18;
  const minute = timeMatch && timeMatch[3] ? Number(timeMatch[3]) : 0;
  const meridiem = timeMatch?.[4]?.toLowerCase();
  if (meridiem === "pm" && hour < 12) hour += 12;
  if (meridiem === "am" && hour === 12) hour = 0;
  if (!meridiem && hour < 10) hour += 12;
  date.setHours(hour, minute, 0, 0);
  return date;
}
