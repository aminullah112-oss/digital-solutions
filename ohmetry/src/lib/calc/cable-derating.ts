/**
 * Tabulated current required for a cable once derating factors are applied.
 * Condition (IEC 60364-4-43 / 5-52): Ib <= In <= Iz, with Iz = It * k1 * k2 * ...
 * so the cable's tabulated rating It must be >= In / (k1 * k2 * ...).
 * The k factors and the It table come from IEC 60364-5-52; this function takes them as inputs.
 */
export interface Derating { k: number; basisA: number; requiredTabulatedA: number }

export function requiredTabulated(designA: number, deviceA: number | null, factors: number[]): Derating {
  if (!(designA > 0)) throw new Error('Design current must be positive');
  if (deviceA !== null && !(deviceA >= designA)) throw new Error('Protective device rating must be at least the design current');
  if (factors.length === 0) throw new Error('Enter at least one derating factor (1 if none applies)');
  for (const f of factors) if (!(f > 0 && f <= 1.5)) throw new Error('Derating factors must be between 0 and 1.5');
  const k = factors.reduce((a, b) => a * b, 1);
  const basisA = deviceA ?? designA;
  return { k, basisA, requiredTabulatedA: basisA / k };
}
