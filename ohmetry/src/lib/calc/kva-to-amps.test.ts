import { describe, expect, it } from 'vitest';
import { kvaToAmps } from './kva-to-amps';

describe('kvaToAmps', () => {
  // 75000 / 240 = 312.5
  it('single-phase: 75 kVA at 240 V = 312.5 A', () => expect(kvaToAmps(75, 240, 'single')).toBeCloseTo(312.5, 6));
  // 100000 / (1.73205 * 400) = 144.34
  it('three-phase: 100 kVA at 400 V = 144.34 A', () => expect(kvaToAmps(100, 400, 'three')).toBeCloseTo(144.34, 2));
  // 500000 / (1.73205 * 480) = 601.4
  it('three-phase: 500 kVA at 480 V = 601.4 A', () => expect(kvaToAmps(500, 480, 'three')).toBeCloseTo(601.4, 1));
  it('rejects bad input', () => expect(() => kvaToAmps(-1, 400, 'three')).toThrow());
});
