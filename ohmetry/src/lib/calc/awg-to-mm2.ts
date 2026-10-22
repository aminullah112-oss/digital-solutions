/**
 * AWG is defined by its diameters (ASTM B258): d(mm) = 0.127 * 92^((36 - n) / 39).
 * n = 0 for AWG 0 (1/0); 4/0 is n = -3, 3/0 is -2, 2/0 is -1.
 * Areas are for a solid round conductor. Stranded conductors differ slightly.
 */
export function awgToDiameterMm(n: number): number {
  if (!Number.isInteger(n) || n < -3 || n > 40) throw new Error('AWG must be a whole number from 4/0 (-3) to 40');
  return 0.127 * Math.pow(92, (36 - n) / 39);
}

export function awgToMm2(n: number): number {
  const d = awgToDiameterMm(n);
  return (Math.PI / 4) * d * d;
}

/** Nearest AWG size (by area) for a given area in mm2. */
export function mm2ToNearestAwg(area: number): number {
  if (!(area > 0)) throw new Error('Area must be positive');
  const d = Math.sqrt((4 * area) / Math.PI);
  const n = Math.round(36 - (39 * Math.log(d / 0.127)) / Math.log(92));
  return Math.min(40, Math.max(-3, n));
}

export function awgLabel(n: number): string {
  return n >= 1 ? String(n) : n === 0 ? '1/0' : `${1 - n}/0`;
}
