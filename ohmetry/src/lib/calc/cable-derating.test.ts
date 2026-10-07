import { describe, expect, it } from 'vitest';
import { requiredTabulated } from './cable-derating';

describe('requiredTabulated', () => {
  // k = 0.87 * 0.8 = 0.696 ; 63 / 0.696 = 90.52 A
  it('63 A device with two factors', () => {
    const r = requiredTabulated(55, 63, [0.87, 0.8]);
    expect(r.k).toBeCloseTo(0.696, 9);
    expect(r.requiredTabulatedA).toBeCloseTo(90.517, 3);
  });
  it('uses the design current when no device is given', () => expect(requiredTabulated(40, null, [1]).requiredTabulatedA).toBe(40));
  it('no derating leaves the current unchanged', () => expect(requiredTabulated(40, 40, [1, 1]).requiredTabulatedA).toBe(40));
  it('rejects a device below the design current', () => expect(() => requiredTabulated(50, 40, [1])).toThrow());
  it('rejects empty or absurd factors', () => {
    expect(() => requiredTabulated(40, 40, [])).toThrow();
    expect(() => requiredTabulated(40, 40, [0])).toThrow();
  });
});
