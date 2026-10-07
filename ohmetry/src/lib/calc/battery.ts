/**
 * Battery bank sizing and runtime. Efficiency is the inverter (and battery round-trip) loss
 * between the bank and the AC load; apply it once.
 *   Capacity (Ah) = E_day * days / (DoD * V * eff)
 *   Runtime (h)   = Ah * V * DoD * eff / P_load
 */
function check(volts: number, dod: number, eff: number) {
  if (!(volts > 0)) throw new Error('Battery voltage must be positive');
  if (!(dod > 0 && dod <= 1)) throw new Error('Depth of discharge must be in (0, 1]');
  if (!(eff > 0 && eff <= 1)) throw new Error('Efficiency must be in (0, 1]');
}

export interface BatterySize { ah: number; kwhNominal: number; kwhUsable: number }

export function batterySize(dailyWh: number, days: number, dod: number, volts: number, eff: number): BatterySize {
  check(volts, dod, eff);
  if (!(dailyWh > 0) || !(days > 0)) throw new Error('Daily energy and days of autonomy must be positive');
  const ah = (dailyWh * days) / (dod * volts * eff);
  return { ah, kwhNominal: (ah * volts) / 1000, kwhUsable: (ah * volts * dod * eff) / 1000 };
}

export function batteryRuntimeHours(ah: number, volts: number, dod: number, eff: number, loadW: number): number {
  check(volts, dod, eff);
  if (!(ah > 0) || !(loadW > 0)) throw new Error('Capacity and load must be positive');
  return (ah * volts * dod * eff) / loadW;
}
