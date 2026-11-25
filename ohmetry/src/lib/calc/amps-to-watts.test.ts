import { describe, expect, it } from 'vitest';
import { ampsToWatts } from './amps-to-watts';

describe('ampsToWatts', () => {
  it('DC: 2 A at 12 V = 24 W', () => expect(ampsToWatts(2, 12, 1, 'dc')).toBe(24));
  it('DC ignores power factor', () => expect(ampsToWatts(2, 12, 0.5, 'dc')).toBe(24));
  // 15 * 120 * 0.9 = 1620
  it('single-phase: 15 A, 120 V, PF 0.9 = 1620 W', () => expect(ampsToWatts(15, 120, 0.9, 'single')).toBeCloseTo(1620, 6));
  // 1.73205 * 400 * 10 * 0.8 = 5542.56
  it('three-phase: 10 A, 400 V, PF 0.8 = 5542.6 W', () => expect(ampsToWatts(10, 400, 0.8, 'three')).toBeCloseTo(5542.56, 1));
  it('rejects bad input', () => {
    expect(() => ampsToWatts(0, 120, 1, 'single')).toThrow();
    expect(() => ampsToWatts(1, 120, 1.1, 'single')).toThrow();
  });
});
