import type { NormalizedInboundMessage } from "@/lib/ai/ingest";

/**
 * Every channel adapter turns a provider-specific webhook payload into the
 * common `NormalizedInboundMessage` shape consumed by ingestChannelMessage().
 * Add a new channel by writing one function here plus one webhook route —
 * nothing else in the pipeline needs to change.
 */
export interface ChannelAdapter {
  channel: NormalizedInboundMessage["channel"];
  parse(payload: unknown): NormalizedInboundMessage[];
}

function textOrNull(v: unknown): string | null {
  return typeof v === "string" && v.trim().length > 0 ? v : null;
}

export const WhatsAppAdapter: ChannelAdapter = {
  channel: "WHATSAPP",
  parse(payload) {
    const out: NormalizedInboundMessage[] = [];
    const entries = (payload as { entry?: unknown[] })?.entry ?? [];
    for (const entry of entries as Record<string, unknown>[]) {
      const changes = (entry.changes as Record<string, unknown>[]) ?? [];
      for (const change of changes) {
        const value = change.value as Record<string, unknown>;
        const messages = (value?.messages as Record<string, unknown>[]) ?? [];
        const contacts = (value?.contacts as Record<string, unknown>[]) ?? [];
        for (const msg of messages) {
          const from = String(msg.from ?? "");
          const contact = contacts[0] as Record<string, unknown> | undefined;
          const profile = contact?.profile as Record<string, unknown> | undefined;
          const text = textOrNull((msg.text as Record<string, unknown>)?.body);
          if (!text) continue;
          out.push({
            channel: "WHATSAPP",
            externalCustomerId: from,
            customerPhone: from.startsWith("+") ? from : `+${from}`,
            customerName: (profile?.name as string) ?? `WhatsApp ${from.slice(-4)}`,
            text,
            externalMessageId: String(msg.id ?? ""),
          });
        }
      }
    }
    return out;
  },
};

export const InstagramAdapter: ChannelAdapter = {
  channel: "INSTAGRAM",
  parse(payload) {
    const out: NormalizedInboundMessage[] = [];
    const entries = (payload as { entry?: unknown[] })?.entry ?? [];
    for (const entry of entries as Record<string, unknown>[]) {
      const messaging = (entry.messaging as Record<string, unknown>[]) ?? [];
      for (const evt of messaging) {
        const sender = evt.sender as Record<string, unknown>;
        const message = evt.message as Record<string, unknown> | undefined;
        const text = textOrNull(message?.text);
        if (!text) continue;
        const psid = String(sender?.id ?? "");
        out.push({
          channel: "INSTAGRAM",
          externalCustomerId: psid,
          customerName: `Instagram ${psid.slice(-4)}`,
          text,
          externalMessageId: String(message?.mid ?? ""),
        });
      }
    }
    return out;
  },
};

export const FacebookAdapter: ChannelAdapter = {
  channel: "FACEBOOK",
  parse(payload) {
    const out: NormalizedInboundMessage[] = [];
    const entries = (payload as { entry?: unknown[] })?.entry ?? [];
    for (const entry of entries as Record<string, unknown>[]) {
      const messaging = (entry.messaging as Record<string, unknown>[]) ?? [];
      for (const evt of messaging) {
        const sender = evt.sender as Record<string, unknown>;
        const message = evt.message as Record<string, unknown> | undefined;
        const text = textOrNull(message?.text);
        if (!text) continue;
        const psid = String(sender?.id ?? "");
        out.push({
          channel: "FACEBOOK",
          externalCustomerId: psid,
          customerName: `Facebook ${psid.slice(-4)}`,
          text,
          externalMessageId: String(message?.mid ?? ""),
        });
      }
    }
    return out;
  },
};

export const WebsiteChatAdapter: ChannelAdapter = {
  channel: "WEBSITE",
  parse(payload) {
    const p = payload as Record<string, unknown>;
    const text = textOrNull(p.text);
    if (!text) return [];
    return [
      {
        channel: "WEBSITE",
        externalCustomerId: String(p.sessionId ?? p.customerId ?? "web-anon"),
        customerName: (p.name as string) || "Website Visitor",
        customerPhone: p.phone as string | undefined,
        text,
        externalMessageId: p.messageId as string | undefined,
      },
    ];
  },
};
