/** Ohm's law and power. Any two of V, I, R, P determine the other two. */
export type Known = Partial<Record<'V' | 'I' | 'R' | 'P', number>>;
export interface OhmResult { V: number; I: number; R: number; P: number }

export function solveOhm(k: Known): OhmResult {
  const given = (['V', 'I', 'R', 'P'] as const).filter((x) => k[x] !== undefined);
  if (given.length !== 2) throw new Error('Provide exactly two of V, I, R, P');
  for (const g of given) {
    const v = k[g] as number;
    if (!Number.isFinite(v) || v <= 0) throw new Error(`${g} must be a positive number`);
  }
  const { V, I, R, P } = k;
  if (V !== undefined && I !== undefined) return { V, I, R: V / I, P: V * I };
  if (V !== undefined && R !== undefined) return { V, I: V / R, R, P: (V * V) / R };
  if (V !== undefined && P !== undefined) return { V, I: P / V, R: (V * V) / P, P };
  if (I !== undefined && R !== undefined) return { V: I * R, I, R, P: I * I * R };
  if (I !== undefined && P !== undefined) return { V: P / I, I, R: P / (I * I), P };
  // R and P
  const r = R as number, p = P as number;
  return { V: Math.sqrt(p * r), I: Math.sqrt(p / r), R: r, P: p };
}
