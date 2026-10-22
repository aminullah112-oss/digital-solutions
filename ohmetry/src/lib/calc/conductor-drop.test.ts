import { describe, expect, it } from 'vitest';
import { minAreaMm2, dropVolts, nextIecSize, nextAwg, resistivity } from './conductor-drop';

const base = { amps: 10, oneWayMetres: 10, volts: 48, maxDropPercent: 2, material: 'copper' as const, tempC: 20 };

describe('conductor-drop', () => {
  // 2*10*10*0.017241 / (48*0.02) = 3.4482/0.96 = 3.592 mm2
  it('10 A, 10 m, 48 V, 2 % copper at 20 C -> 3.59 mm2', () => expect(minAreaMm2(base)).toBeCloseTo(3.592, 3));
  // Hand check of the same case in volts: 2*10*10*0.017241/4 = 0.862 V (1.8 % of 48)
  it('drop in volts for 4 mm2', () => expect(dropVolts(base, 4)).toBeCloseTo(0.862, 3));
  it('rounds up to 4 mm2 and AWG 10', () => {
    expect(nextIecSize(3.592)).toBe(4);
    expect(nextAwg(3.592)).toBe(10);
  });
  it('exact size is not bumped up', () => expect(nextIecSize(4)).toBe(4));
  // copper at 70 C: 0.017241 * (1 + 0.00393*50) = 0.020629
  it('copper resistivity at 70 C', () => expect(resistivity('copper', 70)).toBeCloseTo(0.020629, 5));
  it('aluminium needs ~1.64x the copper area', () => {
    const r = minAreaMm2({ ...base, material: 'aluminium' }) / minAreaMm2(base);
    expect(r).toBeCloseTo(0.028264 / 0.017241, 6);
  });
  it('area scales linearly with current and length', () => {
    expect(minAreaMm2({ ...base, amps: 20 })).toBeCloseTo(2 * minAreaMm2(base), 9);
    expect(minAreaMm2({ ...base, oneWayMetres: 30 })).toBeCloseTo(3 * minAreaMm2(base), 9);
  });
  it('returns null beyond the largest size', () => expect(nextIecSize(500)).toBeNull());
  it('rejects bad input', () => {
    expect(() => minAreaMm2({ ...base, amps: 0 })).toThrow();
    expect(() => minAreaMm2({ ...base, maxDropPercent: 0 })).toThrow();
    expect(() => minAreaMm2({ ...base, tempC: 500 })).toThrow();
  });
});

describe('three-phase circuit', () => {
  // sqrt3*100*50*0.017241/(400*0.03) = 149.31/12 = 12.443 mm2 (20 C)
  const t = { amps: 100, oneWayMetres: 50, volts: 400, maxDropPercent: 3, material: 'copper' as const, tempC: 20, circuit: 'three' as const };
  it('100 A, 50 m, 400 V, 3 %', () => expect(minAreaMm2(t)).toBeCloseTo(12.4426, 3));
  it('is sqrt3/2 of the two-wire result', () => expect(minAreaMm2(t) / minAreaMm2({ ...t, circuit: 'two-wire' })).toBeCloseTo(Math.sqrt(3) / 2, 9));
});
