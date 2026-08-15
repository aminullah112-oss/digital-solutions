import { NextResponse } from "next/server";
import { listConversations } from "@/lib/data/inbox";

export async function GET() {
  const conversations = await listConversations();
  return NextResponse.json({ conversations });
}
