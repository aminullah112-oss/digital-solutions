import { describe, expect, it } from 'vitest';
import { ctBurden } from './ct-burden';

const base = { secondaryA: 5, leadOneWayM: 20, leadAreaMm2: 4, tempC: 20, relayVA: 1, ratedVA: 15, alf: 20, rctOhm: 0.2 };

describe('ctBurden', () => {
  // R = 2*20*0.017241/4 = 0.17241 ohm ; lead VA = 25*0.17241 = 4.310 ; total 5.310
  // Sct = 25*0.2 = 5 ; ALF' = 20*(15+5)/(5.310+5) = 38.80
  it('5 A CT, 20 m of 4 mm2, 1 VA relay', () => {
    const r = ctBurden(base);
    expect(r.leadOhm).toBeCloseTo(0.17241, 5);
    expect(r.leadVA).toBeCloseTo(4.3103, 3);
    expect(r.totalVA).toBeCloseTo(5.3103, 3);
    expect(r.utilisation).toBeCloseTo(0.354, 3);
    expect(r.effectiveAlf).toBeCloseTo(38.80, 1);
    expect(r.ok).toBe(true);
  });
  // The same leads on a 1 A CT carry 1/25 of the VA
  it('1 A secondary cuts lead burden 25 times', () => {
    expect(ctBurden({ ...base, secondaryA: 1 }).leadVA).toBeCloseTo(0.17241, 5);
  });
  it('flags an overloaded CT', () => {
    const r = ctBurden({ ...base, leadOneWayM: 200 });
    expect(r.ok).toBe(false);
    expect(r.effectiveAlf).toBeLessThan(base.alf);
  });
  it('rejects bad input', () => expect(() => ctBurden({ ...base, leadAreaMm2: 0 })).toThrow());
});
