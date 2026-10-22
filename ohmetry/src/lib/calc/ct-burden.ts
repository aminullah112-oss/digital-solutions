/**
 * CT burden check (IEC 61869-2 style).
 *   Lead loop resistance R_l = 2 * rho * L / A
 *   Connected burden S = I_sn^2 * R_l + S_relay      (VA at rated secondary current)
 *   Effective accuracy limit factor ALF' = ALF * (S_n + S_ct) / (S + S_ct), S_ct = I_sn^2 * R_ct
 * A burden above the rated value S_n degrades accuracy and lowers the saturation limit.
 */
import { resistivity } from './conductor-drop';

export interface CtInput {
  secondaryA: number; leadOneWayM: number; leadAreaMm2: number; tempC: number;
  relayVA: number; ratedVA: number; alf: number; rctOhm: number;
}
export interface CtResult { leadOhm: number; leadVA: number; totalVA: number; utilisation: number; effectiveAlf: number; ok: boolean }

export function ctBurden(c: CtInput): CtResult {
  const pos: [number, string][] = [[c.secondaryA, 'Secondary current'], [c.leadOneWayM, 'Lead length'], [c.leadAreaMm2, 'Lead area'], [c.ratedVA, 'Rated burden'], [c.alf, 'Accuracy limit factor']];
  for (const [v, n] of pos) if (!(v > 0)) throw new Error(`${n} must be positive`);
  if (!(c.relayVA >= 0) || !(c.rctOhm >= 0)) throw new Error('Relay burden and CT resistance cannot be negative');
  const leadOhm = (2 * c.leadOneWayM * resistivity('copper', c.tempC)) / c.leadAreaMm2;
  const i2 = c.secondaryA * c.secondaryA;
  const leadVA = i2 * leadOhm;
  const totalVA = leadVA + c.relayVA;
  const sct = i2 * c.rctOhm;
  return {
    leadOhm, leadVA, totalVA,
    utilisation: totalVA / c.ratedVA,
    effectiveAlf: (c.alf * (c.ratedVA + sct)) / (totalVA + sct),
    ok: totalVA <= c.ratedVA,
  };
}
