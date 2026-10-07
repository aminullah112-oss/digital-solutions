import { describe, expect, it } from 'vitest';
import { transformerFlc, shortCircuit } from './transformer';

describe('transformerFlc', () => {
  // 1000 kVA: 1e6/(1.73205*11000) = 52.49 A ; 1e6/(1.73205*400) = 1443.4 A
  it('1000 kVA 11 kV / 400 V', () => {
    const r = transformerFlc(1000, 11000, 400);
    expect(r.primaryA).toBeCloseTo(52.486, 2);
    expect(r.secondaryA).toBeCloseTo(1443.38, 1);
    expect(r.ratio).toBeCloseTo(27.5, 9);
  });
  it('primary and secondary currents are inversely proportional to voltage', () => {
    const r = transformerFlc(500, 33000, 11000);
    expect(r.secondaryA / r.primaryA).toBeCloseTo(3, 9);
  });
});

describe('shortCircuit', () => {
  // infinite bus: 1443.38 / 0.05 = 28 867 A
  it('1000 kVA, 400 V, 5 %Z, infinite bus', () => {
    const r = shortCircuit(1000, 400, 5);
    expect(r.iscA).toBeCloseTo(28867.5, 0);
    expect(r.iscMvaTotal).toBeCloseTo(20, 6); // 1 MVA / 0.05
  });
  // Zsource = 1/500 = 0.002 pu -> total 0.052 -> 1443.38/0.052 = 27 757 A
  it('with a 500 MVA source', () => expect(shortCircuit(1000, 400, 5, 500).iscA).toBeCloseTo(27757.4, 0));
  // 100 kVA 4 %: 144.34 / 0.04 = 3608 A (the figure quoted on the kVA to amps page)
  it('100 kVA, 400 V, 4 %Z', () => expect(shortCircuit(100, 400, 4).iscA).toBeCloseTo(3608.4, 0));
  it('a stronger source gives a higher fault level', () => {
    expect(shortCircuit(1000, 400, 5, 1000).iscA).toBeGreaterThan(shortCircuit(1000, 400, 5, 100).iscA);
  });
  it('rejects bad input', () => {
    expect(() => shortCircuit(1000, 400, 0)).toThrow();
    expect(() => shortCircuit(1000, 400, 5, 0)).toThrow();
  });
});
