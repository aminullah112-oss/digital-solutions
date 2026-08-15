import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession, roleAtLeast } from "@/lib/auth/session";

export async function PATCH(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session || !roleAtLeast(session.role, "ADMIN")) {
    return NextResponse.json({ error: "Only admins can update users" }, { status: 403 });
  }

  const { id } = await context.params;
  const body = await req.json().catch(() => ({}));
  const data: Record<string, unknown> = {};
  if (typeof body.active === "boolean") data.active = body.active;
  if (["ADMIN", "MANAGER", "STAFF"].includes(body.role)) data.role = body.role;

  const user = await prisma.user.update({ where: { id }, data });
  return NextResponse.json({ user: { id: user.id, name: user.name, email: user.email, role: user.role, active: user.active } });
}
