import { NextResponse } from "next/server";
import { getConversationDetail } from "@/lib/data/inbox";

export async function GET(_req: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const conversation = await getConversationDetail(id);
  if (!conversation) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json({ conversation });
}
