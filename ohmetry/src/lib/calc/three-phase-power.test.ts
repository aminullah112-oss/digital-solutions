import { describe, expect, it } from 'vitest';
import { threePhasePower } from './three-phase-power';

describe('threePhasePower', () => {
  // S = 1.73205*400*10/1000 = 6.9282 kVA; P = 0.8*S = 5.5426; Q = 0.6*S = 4.1569
  it('400 V, 10 A, PF 0.8', () => {
    const r = threePhasePower(400, 10, 0.8);
    expect(r.kVA).toBeCloseTo(6.9282, 3);
    expect(r.kW).toBeCloseTo(5.5426, 3);
    expect(r.kvar).toBeCloseTo(4.1569, 3);
  });
  it('unity PF has zero kvar', () => expect(threePhasePower(480, 100, 1).kvar).toBeCloseTo(0, 9));
  it('P^2 + Q^2 = S^2', () => {
    const r = threePhasePower(415, 37, 0.85);
    expect(r.kW ** 2 + r.kvar ** 2).toBeCloseTo(r.kVA ** 2, 9);
  });
  it('rejects bad input', () => expect(() => threePhasePower(400, 10, 0)).toThrow());
});
