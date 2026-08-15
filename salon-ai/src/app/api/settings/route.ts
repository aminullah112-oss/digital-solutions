import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { getSession } from "@/lib/auth/session";

export async function GET() {
  const settings = await prisma.businessSettings.findUnique({ where: { id: "default" } });
  return NextResponse.json({ settings });
}

export async function PATCH(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const data: Record<string, unknown> = {};
  for (const key of ["salonName", "address", "phone"]) {
    if (typeof body[key] === "string") data[key] = body[key];
  }
  if (body.openingHours) data.openingHours = body.openingHours;
  if (body.socials) data.socials = body.socials;
  if (body.channelsEnabled) data.channelsEnabled = body.channelsEnabled;
  if (typeof body.aiMode === "string") data.aiMode = body.aiMode;
  for (const key of ["notifyHotLead", "notifyComplaint", "notifyBooking", "notifyHandoff"]) {
    if (typeof body[key] === "boolean") data[key] = body[key];
  }

  const settings = await prisma.businessSettings.update({ where: { id: "default" }, data });
  return NextResponse.json({ settings });
}
