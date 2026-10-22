/**
 * Resistance of one vertical rod (Dwight/Sunde): R = rho / (2*pi*L) * (ln(4L/a) - 1)
 * rho soil resistivity (ohm.m), L driven length (m), a rod radius (m).
 * Uniform soil only. A measured value (fall-of-potential, IEEE Std 81) overrides this.
 */
export function earthRodOhms(rho: number, lengthM: number, diameterMm: number): number {
  if (!(rho > 0) || !(lengthM > 0) || !(diameterMm > 0)) throw new Error('Resistivity, length and diameter must be positive');
  const a = diameterMm / 2000;
  if (lengthM <= 4 * a) throw new Error('Rod length must be much greater than its diameter');
  return (rho / (2 * Math.PI * lengthM)) * (Math.log((4 * lengthM) / a) - 1);
}

/** Length needed (m) to reach a target resistance, by bisection. */
export function rodLengthForTarget(rho: number, diameterMm: number, targetOhms: number): number | null {
  if (!(targetOhms > 0)) throw new Error('Target must be positive');
  let lo = 0.5, hi = 100;
  if (earthRodOhms(rho, hi, diameterMm) > targetOhms) return null;
  for (let k = 0; k < 80; k++) {
    const mid = (lo + hi) / 2;
    if (earthRodOhms(rho, mid, diameterMm) > targetOhms) lo = mid; else hi = mid;
  }
  return hi;
}
