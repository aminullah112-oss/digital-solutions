import { describe, expect, it } from 'vitest';
import { awgToDiameterMm, awgToMm2, mm2ToNearestAwg, awgLabel } from './awg-to-mm2';

// Reference values: widely published AWG tables (solid conductor), rounded.
describe('awgToMm2', () => {
  it('AWG 10 = 2.588 mm, 5.26 mm2', () => {
    expect(awgToDiameterMm(10)).toBeCloseTo(2.588, 3);
    expect(awgToMm2(10)).toBeCloseTo(5.26, 2);
  });
  it('AWG 14 = 2.08 mm2', () => expect(awgToMm2(14)).toBeCloseTo(2.08, 2));
  it('AWG 12 = 3.31 mm2', () => expect(awgToMm2(12)).toBeCloseTo(3.31, 2));
  it('AWG 4 = 21.15 mm2', () => expect(awgToMm2(4)).toBeCloseTo(21.15, 2));
  it('AWG 1/0 (0) = 53.5 mm2', () => expect(awgToMm2(0)).toBeCloseTo(53.5, 0));
  it('AWG 4/0 (-3) = 107.2 mm2, 11.68 mm', () => {
    expect(awgToMm2(-3)).toBeCloseTo(107.2, 1);
    expect(awgToDiameterMm(-3)).toBeCloseTo(11.684, 3);
  });
  it('round-trips every size', () => {
    for (let n = -3; n <= 30; n++) expect(mm2ToNearestAwg(awgToMm2(n))).toBe(n);
  });
  it('maps 6 mm2 to AWG 9 (6.63 mm2, closer than AWG 10 at 5.26)', () => expect(mm2ToNearestAwg(6)).toBe(9));
  it('labels', () => {
    expect(awgLabel(-3)).toBe('4/0');
    expect(awgLabel(0)).toBe('1/0');
    expect(awgLabel(12)).toBe('12');
  });
  it('rejects out-of-range', () => {
    expect(() => awgToMm2(-4)).toThrow();
    expect(() => awgToMm2(1.5)).toThrow();
  });
});
