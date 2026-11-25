import { describe, expect, it } from 'vitest';
import { earthRodOhms, rodLengthForTarget } from './earth-rod';

describe('earthRodOhms', () => {
  // rho 100, L 3 m, d 16 mm: a = 0.008 ; ln(4*3/0.008) = ln 1500 = 7.3132 ; 100/(2*pi*3) = 5.3052 ; R = 5.3052*6.3132 = 33.49 ohm
  it('100 ohm.m, 3 m, 16 mm', () => expect(earthRodOhms(100, 3, 16)).toBeCloseTo(33.49, 1));
  it('resistance is proportional to resistivity', () => expect(earthRodOhms(200, 3, 16)).toBeCloseTo(2 * earthRodOhms(100, 3, 16), 9));
  it('a longer rod lowers resistance, but less than proportionally', () => {
    const r3 = earthRodOhms(100, 3, 16), r6 = earthRodOhms(100, 6, 16);
    expect(r6).toBeLessThan(r3);
    expect(r6).toBeGreaterThan(r3 / 2);
  });
  it('finds the length for a target', () => {
    const L = rodLengthForTarget(100, 16, 20)!;
    expect(earthRodOhms(100, L, 16)).toBeCloseTo(20, 4);
  });
  it('returns null when a single rod cannot reach the target', () => expect(rodLengthForTarget(1000, 16, 1)).toBeNull());
  it('rejects bad input', () => expect(() => earthRodOhms(0, 3, 16)).toThrow());
});
