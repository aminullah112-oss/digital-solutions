/** Capacitor size to raise power factor: Qc = P * (tan(acos(pf1)) - tan(acos(pf2))). */
export interface PfCorrection { kvarNeeded: number; kvaBefore: number; kvaAfter: number; currentReductionPct: number }

export function pfCorrection(kw: number, pfNow: number, pfTarget: number): PfCorrection {
  if (!(kw > 0)) throw new Error('Load must be positive');
  if (!(pfNow > 0 && pfNow <= 1) || !(pfTarget > 0 && pfTarget <= 1)) throw new Error('Power factors must be in (0, 1]');
  if (!(pfTarget > pfNow)) throw new Error('Target power factor must be higher than the present value');
  const tan = (pf: number) => Math.tan(Math.acos(pf));
  return {
    kvarNeeded: kw * (tan(pfNow) - tan(pfTarget)),
    kvaBefore: kw / pfNow,
    kvaAfter: kw / pfTarget,
    currentReductionPct: (1 - pfNow / pfTarget) * 100,
  };
}
