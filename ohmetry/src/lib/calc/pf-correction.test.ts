import { describe, expect, it } from 'vitest';
import { pfCorrection } from './pf-correction';

describe('pfCorrection', () => {
  // 100 kW: tan(acos 0.8) = 0.75 ; tan(acos 0.95) = 0.32868 ; Qc = 100*0.42132 = 42.13 kvar
  it('100 kW from 0.80 to 0.95', () => {
    const r = pfCorrection(100, 0.8, 0.95);
    expect(r.kvarNeeded).toBeCloseTo(42.13, 2);
    expect(r.kvaBefore).toBeCloseTo(125, 6);
    expect(r.kvaAfter).toBeCloseTo(105.263, 3);
    expect(r.currentReductionPct).toBeCloseTo(15.79, 2);
  });
  // matches the three-phase page: 5.543 kW, 0.8 -> 0.95 needs 2.335 kvar
  it('5.543 kW from 0.80 to 0.95', () => expect(pfCorrection(5.543, 0.8, 0.95).kvarNeeded).toBeCloseTo(2.335, 3));
  it('correcting to unity cancels all kvar', () => expect(pfCorrection(100, 0.8, 1).kvarNeeded).toBeCloseTo(75, 6));
  it('rejects a lower target', () => expect(() => pfCorrection(100, 0.9, 0.8)).toThrow());
});
