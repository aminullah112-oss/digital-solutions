/**
 * Voltage drop of a loaded cable.
 *   Resistive:  dV = k * I * L * R           (k = 2 for two-wire/DC, sqrt3 for balanced three-phase)
 *   With reactance: dV = k * I * L * (R*cos(phi) + X*sin(phi))
 * R comes from the conductor resistivity at the operating temperature. Reactance is only applied
 * when the caller supplies it (from the cable data sheet); otherwise the calculation is resistive.
 */
import { resistivity, type Material } from './conductor-drop';

export interface DropCalc {
  amps: number; oneWayMetres: number; areaMm2: number; volts: number;
  material: Material; tempC: number; circuit: 'two-wire' | 'three';
  /** Cable reactance in ohm/km (optional). */
  xOhmPerKm?: number;
  /** Load power factor, used only when xOhmPerKm is given. */
  powerFactor?: number;
}
export interface DropResult { rOhmPerKm: number; dropV: number; dropPercent: number; loadVolts: number }

export function voltageDrop(c: DropCalc): DropResult {
  for (const [v, n] of [[c.amps, 'Current'], [c.oneWayMetres, 'Length'], [c.areaMm2, 'Cross-section'], [c.volts, 'Voltage']] as [number, string][])
    if (!(v > 0)) throw new Error(`${n} must be positive`);
  if (!(c.tempC >= -40 && c.tempC <= 150)) throw new Error('Temperature must be between -40 and 150 C');
  const k = c.circuit === 'three' ? Math.sqrt(3) : 2;
  const rOhmPerKm = (resistivity(c.material, c.tempC) / c.areaMm2) * 1000;
  let term = rOhmPerKm;
  if (c.xOhmPerKm !== undefined) {
    const pf = c.powerFactor ?? 1;
    if (!(pf > 0 && pf <= 1)) throw new Error('Power factor must be in (0, 1]');
    if (!(c.xOhmPerKm >= 0)) throw new Error('Reactance cannot be negative');
    term = rOhmPerKm * pf + c.xOhmPerKm * Math.sqrt(1 - pf * pf);
  }
  const dropV = (k * c.amps * (c.oneWayMetres / 1000) * term);
  return { rOhmPerKm, dropV, dropPercent: (dropV / c.volts) * 100, loadVolts: c.volts - dropV };
}
