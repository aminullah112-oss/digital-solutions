import { describe, expect, it } from 'vitest';
import { kwToAmps } from './kw-to-amps';

describe('kwToAmps', () => {
  // Hand check: 10000 / (240 * 1) = 41.667 A
  it('single-phase, unity PF', () => expect(kwToAmps(10, 240, 1, 'single')).toBeCloseTo(41.6667, 3));
  // Hand check: 10000 / (1.73205 * 400 * 0.8) = 18.042 A
  it('three-phase, 0.8 PF', () => expect(kwToAmps(10, 400, 0.8, 'three')).toBeCloseTo(18.0422, 3));
  // Hand check: 50000 / (1.73205 * 480 * 0.9) = 66.82 A
  it('three-phase, 480 V, 0.9 PF', () => expect(kwToAmps(50, 480, 0.9, 'three')).toBeCloseTo(66.82, 2));
  it('rejects bad input', () => {
    expect(() => kwToAmps(0, 240, 1, 'single')).toThrow();
    expect(() => kwToAmps(1, 240, 1.2, 'single')).toThrow();
    expect(() => kwToAmps(1, 240, 0, 'three')).toThrow();
  });
});
