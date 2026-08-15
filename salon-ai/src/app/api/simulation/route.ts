import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db/prisma";
import { startSimulation, stopSimulation, simulationStatus } from "@/lib/simulation/engine";
import { getSession } from "@/lib/auth/session";

export async function GET() {
  const settings = await prisma.businessSettings.findUnique({ where: { id: "default" } });
  return NextResponse.json({ enabled: settings?.demoMode ?? false, ...simulationStatus() });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const enabled = Boolean(body.enabled);

  await prisma.businessSettings.update({ where: { id: "default" }, data: { demoMode: enabled } });
  if (enabled) startSimulation();
  else stopSimulation();

  return NextResponse.json({ enabled, ...simulationStatus() });
}
