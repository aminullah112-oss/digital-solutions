/**
 * Transformer currents and symmetrical short-circuit level (three-phase).
 *   FLC = kVA*1000 / (sqrt3 * V_LL)
 *   Isc = FLC / (Z_tr + Z_source) in per-unit on the transformer rating.
 * Z_source = S_tr / S_sc (source short-circuit MVA). Infinite bus when omitted.
 * Simplified: no voltage factor c (IEC 60909), no motor contribution, no cable impedance.
 */
import { kvaToAmps } from './kva-to-amps';

export interface Flc { primaryA: number; secondaryA: number; ratio: number }

export function transformerFlc(kva: number, primaryV: number, secondaryV: number): Flc {
  return { primaryA: kvaToAmps(kva, primaryV, 'three'), secondaryA: kvaToAmps(kva, secondaryV, 'three'), ratio: primaryV / secondaryV };
}

export interface ShortCircuit { flcA: number; zPu: number; iscA: number; iscMvaTotal: number }

export function shortCircuit(kva: number, volts: number, zPercent: number, sourceMva?: number): ShortCircuit {
  if (!(zPercent > 0 && zPercent < 100)) throw new Error('Impedance must be between 0 and 100 %');
  if (sourceMva !== undefined && !(sourceMva > 0)) throw new Error('Source MVA must be positive');
  const flcA = kvaToAmps(kva, volts, 'three');
  const zSource = sourceMva === undefined ? 0 : kva / 1000 / sourceMva;
  const zPu = zPercent / 100 + zSource;
  const iscA = flcA / zPu;
  return { flcA, zPu, iscA, iscMvaTotal: (Math.sqrt(3) * volts * iscA) / 1e6 };
}
