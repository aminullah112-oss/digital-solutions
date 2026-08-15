import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession, roleAtLeast } from "@/lib/auth/session";
import { hashPassword } from "@/lib/auth/password";

export async function GET() {
  const users = await prisma.user.findMany({ orderBy: { createdAt: "asc" }, select: { id: true, name: true, email: true, role: true, active: true } });
  return NextResponse.json({ users });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session || !roleAtLeast(session.role, "ADMIN")) {
    return NextResponse.json({ error: "Only admins can create users" }, { status: 403 });
  }

  const body = await req.json().catch(() => ({}));
  const { name, email, password, role } = body;
  if (!name || !email || !password) {
    return NextResponse.json({ error: "Name, email, and password are required" }, { status: 400 });
  }

  const passwordHash = await hashPassword(password);
  const user = await prisma.user.create({
    data: { name, email: String(email).toLowerCase(), passwordHash, role: role === "MANAGER" || role === "ADMIN" ? role : "STAFF" },
  });

  return NextResponse.json({ user: { id: user.id, name: user.name, email: user.email, role: user.role } });
}
