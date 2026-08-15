import { NextRequest, NextResponse } from "next/server";
import { verifyWebsiteToken, rateLimit } from "@/lib/channels/verify";
import { WebsiteChatAdapter } from "@/lib/channels/adapters";
import { ingestChannelMessage } from "@/lib/ai/ingest";

// First-party website chat widget posts here directly (no Meta signature scheme —
// it authenticates with a shared bearer token instead).
export async function POST(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for") ?? "unknown";
  if (!rateLimit(`website:${ip}`, 30, 60_000)) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429 });
  }

  if (process.env.DEMO_MODE !== "true") {
    const auth = req.headers.get("authorization");
    const token = auth?.startsWith("Bearer ") ? auth.slice(7) : null;
    if (!verifyWebsiteToken(token, process.env.WEBSITE_CHAT_TOKEN)) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const messages = WebsiteChatAdapter.parse(payload);
  const results = [];
  for (const msg of messages) {
    results.push(await ingestChannelMessage(msg));
  }

  return NextResponse.json({ received: messages.length, results });
}
