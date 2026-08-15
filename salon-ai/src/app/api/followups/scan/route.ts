import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { scanForFollowUps } from "@/lib/ai/followup";

/** Manually trigger a follow-up sweep (staff-initiated, in addition to the automatic simulation sweep). */
export async function POST() {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const created = await scanForFollowUps({ staleAfterMs: 20 * 3_600_000, minScore: 20 });
  return NextResponse.json({ created: created.length });
}
