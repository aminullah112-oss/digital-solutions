import type { Channel } from "@prisma/client";

const GRAPH_VERSION = "v21.0";

export interface SendResult {
  sent: boolean;
  reason?: string;
}

/**
 * Outbound delivery back to the customer on their original channel. Every
 * function here is a no-op (returns `{ sent: false, reason: "not_configured" }`)
 * when the relevant access token isn't set, so the app works fully in Demo
 * Mode without ever attempting a real network call.
 */
export async function sendWhatsAppMessage(toPhone: string, text: string): Promise<SendResult> {
  const token = process.env.WHATSAPP_ACCESS_TOKEN;
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  if (!token || !phoneNumberId) return { sent: false, reason: "not_configured" };

  try {
    const res = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${phoneNumberId}/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        to: toPhone.replace(/^\+/, ""),
        type: "text",
        text: { body: text },
      }),
    });
    if (!res.ok) return { sent: false, reason: `whatsapp_api_error_${res.status}` };
    return { sent: true };
  } catch {
    return { sent: false, reason: "network_error" };
  }
}

export async function sendInstagramMessage(recipientId: string, text: string): Promise<SendResult> {
  const token = process.env.INSTAGRAM_ACCESS_TOKEN;
  if (!token) return { sent: false, reason: "not_configured" };

  try {
    const res = await fetch(`https://graph.instagram.com/${GRAPH_VERSION}/me/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ recipient: { id: recipientId }, message: { text } }),
    });
    if (!res.ok) return { sent: false, reason: `instagram_api_error_${res.status}` };
    return { sent: true };
  } catch {
    return { sent: false, reason: "network_error" };
  }
}

export async function sendFacebookMessage(recipientId: string, text: string): Promise<SendResult> {
  const token = process.env.FACEBOOK_PAGE_ACCESS_TOKEN;
  if (!token) return { sent: false, reason: "not_configured" };

  try {
    const res = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/me/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ recipient: { id: recipientId }, message: { text } }),
    });
    if (!res.ok) return { sent: false, reason: `facebook_api_error_${res.status}` };
    return { sent: true };
  } catch {
    return { sent: false, reason: "network_error" };
  }
}

/**
 * Routes an outbound reply to the right channel sender. `target` is the
 * customer's phone (WhatsApp) or channel-specific external id (Instagram/
 * Facebook PSID). Website conversations are delivered purely by the customer
 * polling the (not-yet-built) public chat widget, so there's nothing to push.
 */
export async function sendChannelMessage(channel: Channel, target: string | null, text: string): Promise<SendResult> {
  if (!target) return { sent: false, reason: "no_recipient_id" };
  switch (channel) {
    case "WHATSAPP":
      return sendWhatsAppMessage(target, text);
    case "INSTAGRAM":
      return sendInstagramMessage(target, text);
    case "FACEBOOK":
      return sendFacebookMessage(target, text);
    case "WEBSITE":
      return { sent: true, reason: "delivered_in_app" };
    default:
      return { sent: false, reason: "unknown_channel" };
  }
}
