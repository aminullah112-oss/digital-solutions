/**
 * EV charger circuit. Supply equipment is a continuous load: overcurrent device
 * >= 125 % of charger current (NEC 625.41, 210.20(A)). Conductor ampacity must also be
 * >= 125 % of the charger current (NEC 210.19(A)(1)) and is selected from the code tables,
 * which this calculator does not contain. It adds a voltage-drop minimum area.
 */
import { breakerSize } from './breaker-size';

export interface EvCircuit { chargerAmps: number; minAmpacity: number; breaker: number }

export function evCircuit(chargerAmps: number): EvCircuit {
  const { minAmps, breaker } = breakerSize(chargerAmps);
  return { chargerAmps, minAmpacity: minAmps, breaker };
}

export function kwToChargerAmps(kw: number, volts: number): number {
  if (!(kw > 0) || !(volts > 0)) throw new Error('kW and volts must be positive');
  return (kw * 1000) / volts;
}

/** Hours to add `kwh` at `kw`, with charging efficiency (default 0.9 for AC charging losses). */
export function chargeHours(kwh: number, kw: number, eff = 0.9): number {
  if (!(kwh > 0) || !(kw > 0) || !(eff > 0 && eff <= 1)) throw new Error('Energy, power and efficiency must be positive');
  return kwh / (kw * eff);
}
