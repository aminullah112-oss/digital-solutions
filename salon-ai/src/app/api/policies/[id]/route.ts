import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function PATCH(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await context.params;
  const body = await req.json().catch(() => ({}));
  const content = typeof body.content === "string" ? body.content : undefined;
  if (!content) return NextResponse.json({ error: "content is required" }, { status: 400 });

  const policy = await prisma.policy.update({ where: { id }, data: { content } });
  return NextResponse.json({ policy });
}
