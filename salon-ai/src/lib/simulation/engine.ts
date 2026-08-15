import { prisma } from "@/lib/db/prisma";
import { ingestChannelMessage } from "@/lib/ai/ingest";
import { scanForFollowUps } from "@/lib/ai/followup";
import { SIMULATED_MESSAGES, SIMULATED_CHANNELS, randomNewCustomerName } from "./scenarios";

interface SimulationState {
  running: boolean;
  timer: ReturnType<typeof setTimeout> | null;
  lastRunAt: Date | null;
  eventsGenerated: number;
}

const globalForSim = globalThis as unknown as { __salonSim?: SimulationState };
const state: SimulationState =
  globalForSim.__salonSim ?? (globalForSim.__salonSim = { running: false, timer: null, lastRunAt: null, eventsGenerated: 0 });

function randomInt(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

async function pickCustomerId(): Promise<{ id: string; phone: string | null; name: string } | null> {
  // 70% of the time, message an existing customer (continuing a relationship);
  // 30% of the time, simulate a brand-new lead arriving.
  if (Math.random() < 0.7) {
    const count = await prisma.customer.count();
    if (count > 0) {
      const skip = randomInt(0, count - 1);
      const [customer] = await prisma.customer.findMany({ take: 1, skip });
      if (customer) return customer;
    }
  }
  return null;
}

async function runOneTick() {
  const text = SIMULATED_MESSAGES[randomInt(0, SIMULATED_MESSAGES.length - 1)];
  const channel = SIMULATED_CHANNELS[randomInt(0, SIMULATED_CHANNELS.length - 1)];
  const existing = await pickCustomerId();

  if (existing) {
    await ingestChannelMessage({
      channel,
      externalCustomerId: existing.id,
      customerName: existing.name,
      customerPhone: existing.phone ?? undefined,
      text,
    });
  } else {
    const name = randomNewCustomerName();
    const phone = `+9665${randomInt(10000000, 99999999)}`;
    await ingestChannelMessage({
      channel,
      externalCustomerId: phone,
      customerName: name,
      customerPhone: phone,
      text,
    });
  }

  state.eventsGenerated += 1;
  state.lastRunAt = new Date();

  // Occasionally sweep for follow-ups too, so that panel stays alive during a demo.
  if (Math.random() < 0.2) {
    await scanForFollowUps({ staleAfterMs: 20 * 3_600_000, minScore: 20 }).catch(() => {});
  }
}

function scheduleNext() {
  if (!state.running) return;
  const minMs = Number(process.env.SIMULATION_MIN_INTERVAL_MS ?? 10_000);
  const maxMs = Number(process.env.SIMULATION_MAX_INTERVAL_MS ?? 20_000);
  const delay = randomInt(minMs, maxMs);
  state.timer = setTimeout(async () => {
    try {
      await runOneTick();
    } catch (err) {
      console.error("[simulation] tick failed", err);
    } finally {
      scheduleNext();
    }
  }, delay);
}

export function startSimulation() {
  if (state.running) return;
  state.running = true;
  scheduleNext();
}

export function stopSimulation() {
  state.running = false;
  if (state.timer) clearTimeout(state.timer);
  state.timer = null;
}

export function simulationStatus() {
  return { running: state.running, lastRunAt: state.lastRunAt, eventsGenerated: state.eventsGenerated };
}
