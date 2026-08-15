import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function GET() {
  const faqs = await prisma.fAQ.findMany({ orderBy: { createdAt: "desc" } });
  return NextResponse.json({ faqs });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const { question, answer, category } = body;
  if (!question || !answer) return NextResponse.json({ error: "Question and answer are required" }, { status: 400 });

  const faq = await prisma.fAQ.create({ data: { question, answer, category: category || "general" } });
  return NextResponse.json({ faq });
}
