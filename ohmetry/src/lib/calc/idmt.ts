/**
 * IEC 60255-151 inverse-time overcurrent characteristic:
 *   t = TMS * k / ((I/Is)^alpha - 1)
 * Constants for the standard curves. Defined for I/Is > 1; real relays also have
 * a start (pickup) ratio, commonly 1.05 to 1.3 of Is, that a manufacturer sets.
 */
export type Curve = 'SI' | 'VI' | 'EI' | 'LTI';

export const CURVES: Record<Curve, { name: string; k: number; alpha: number }> = {
  SI: { name: 'Standard inverse', k: 0.14, alpha: 0.02 },
  VI: { name: 'Very inverse', k: 13.5, alpha: 1 },
  EI: { name: 'Extremely inverse', k: 80, alpha: 2 },
  LTI: { name: 'Long-time inverse', k: 120, alpha: 1 },
};

export function idmtTime(curve: Curve, tms: number, faultA: number, pickupA: number): number {
  if (!(tms > 0)) throw new Error('Time multiplier must be positive');
  if (!(pickupA > 0) || !(faultA > 0)) throw new Error('Currents must be positive');
  const m = faultA / pickupA;
  if (!(m > 1)) throw new Error('Fault current must exceed the pickup setting; the relay does not operate below it');
  const { k, alpha } = CURVES[curve];
  return (tms * k) / (Math.pow(m, alpha) - 1);
}
