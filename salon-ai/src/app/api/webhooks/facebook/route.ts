import { NextRequest, NextResponse } from "next/server";
import { verifyMetaSignature, rateLimit } from "@/lib/channels/verify";
import { FacebookAdapter } from "@/lib/channels/adapters";
import { ingestChannelMessage } from "@/lib/ai/ingest";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const mode = searchParams.get("hub.mode");
  const token = searchParams.get("hub.verify_token");
  const challenge = searchParams.get("hub.challenge");

  if (mode === "subscribe" && token === process.env.FACEBOOK_VERIFY_TOKEN) {
    return new NextResponse(challenge ?? "", { status: 200 });
  }
  return NextResponse.json({ error: "Verification failed" }, { status: 403 });
}

export async function POST(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for") ?? "unknown";
  if (!rateLimit(`facebook:${ip}`)) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429 });
  }

  const rawBody = await req.text();
  const signature = req.headers.get("x-hub-signature-256");

  if (process.env.DEMO_MODE !== "true") {
    const valid = verifyMetaSignature(rawBody, signature, process.env.META_APP_SECRET);
    if (!valid) return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const messages = FacebookAdapter.parse(payload);
  for (const msg of messages) {
    await ingestChannelMessage(msg);
  }

  return NextResponse.json({ received: messages.length });
}
