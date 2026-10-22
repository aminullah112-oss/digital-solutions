/**
 * Conductor sizing by voltage drop only. Ampacity (heating) is NOT checked here:
 * it depends on insulation, installation method and the governing code tables.
 *
 * Resistivity at 20 C: copper 0.017241 ohm.mm2/m, aluminium 0.028264 ohm.mm2/m
 * (IEC 60028 annealed copper 1/58; aluminium per ASTM B230 class). Temperature
 * coefficients: copper 0.00393/C, aluminium 0.00403/C.
 */
import { awgToMm2 } from './awg-to-mm2';

export type Material = 'copper' | 'aluminium';
const RHO20: Record<Material, number> = { copper: 0.017241, aluminium: 0.028264 };
const ALPHA: Record<Material, number> = { copper: 0.00393, aluminium: 0.00403 };

export const IEC_SIZES = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300];
/** AWG sizes commonly stocked, smallest to largest (4/0 = -3). */
export const COMMON_AWG = [18, 16, 14, 12, 10, 8, 6, 4, 3, 2, 1, 0, -1, -2, -3];

export function resistivity(material: Material, tempC: number): number {
  return RHO20[material] * (1 + ALPHA[material] * (tempC - 20));
}

export interface DropInput {
  amps: number;
  oneWayMetres: number;
  volts: number;        // system voltage the drop is measured against
  maxDropPercent: number;
  material: Material;
  tempC: number;        // conductor operating temperature
  /** 'two-wire' (default): out and back, factor 2. 'three': balanced three-phase, line-to-line V, factor sqrt3. Resistance only, reactance ignored. */
  circuit?: 'two-wire' | 'three';
}

const loopFactor = (c?: 'two-wire' | 'three') => (c === 'three' ? Math.sqrt(3) : 2);

/** Minimum cross-section (mm2) for a two-conductor circuit: out and back. */
export function minAreaMm2(i: DropInput): number {
  if (!(i.amps > 0) || !(i.oneWayMetres > 0) || !(i.volts > 0)) throw new Error('Current, length and voltage must be positive');
  if (!(i.maxDropPercent > 0 && i.maxDropPercent < 100)) throw new Error('Allowed drop must be between 0 and 100 %');
  if (!(i.tempC >= -40 && i.tempC <= 150)) throw new Error('Temperature must be between -40 and 150 C');
  const rho = resistivity(i.material, i.tempC);
  return (loopFactor(i.circuit) * i.oneWayMetres * i.amps * rho) / (i.volts * (i.maxDropPercent / 100));
}

export function dropVolts(i: Omit<DropInput, 'maxDropPercent' | 'volts'>, areaMm2: number): number {
  return (loopFactor(i.circuit) * i.oneWayMetres * i.amps * resistivity(i.material, i.tempC)) / areaMm2;
}

export function nextIecSize(areaMm2: number): number | null {
  return IEC_SIZES.find((s) => s >= areaMm2 - 1e-9) ?? null;
}

export function nextAwg(areaMm2: number): number | null {
  return COMMON_AWG.find((n) => awgToMm2(n) >= areaMm2 - 1e-9) ?? null;
}
