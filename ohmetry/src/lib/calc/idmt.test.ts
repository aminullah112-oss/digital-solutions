import { describe, expect, it } from 'vitest';
import { idmtTime } from './idmt';

// At TMS 1.0 and I/Is = 10 the IEC curves give the widely tabulated times:
// SI 2.97 s, VI 1.50 s, EI 0.808 s, LTI 13.33 s. Hand check SI: 0.14 / (10^0.02 - 1) = 0.14 / 0.047129.
describe('idmtTime', () => {
  it('SI at 10x, TMS 1', () => expect(idmtTime('SI', 1, 1000, 100)).toBeCloseTo(2.97, 2));
  it('VI at 10x, TMS 1', () => expect(idmtTime('VI', 1, 1000, 100)).toBeCloseTo(1.5, 6));
  it('EI at 10x, TMS 1', () => expect(idmtTime('EI', 1, 1000, 100)).toBeCloseTo(0.8081, 4));
  it('LTI at 10x, TMS 1', () => expect(idmtTime('LTI', 1, 1000, 100)).toBeCloseTo(13.3333, 4));
  it('time scales linearly with TMS', () => expect(idmtTime('VI', 0.3, 1000, 100)).toBeCloseTo(0.45, 9));
  it('VI at 2x, TMS 1: 13.5 / 1 = 13.5 s', () => expect(idmtTime('VI', 1, 200, 100)).toBeCloseTo(13.5, 9));
  it('operates faster at higher current', () => expect(idmtTime('SI', 0.5, 2000, 100)).toBeLessThan(idmtTime('SI', 0.5, 500, 100)));
  it('rejects at or below pickup', () => {
    expect(() => idmtTime('SI', 1, 100, 100)).toThrow();
    expect(() => idmtTime('SI', 1, 50, 100)).toThrow();
  });
  it('rejects bad input', () => expect(() => idmtTime('SI', 0, 500, 100)).toThrow());
});
