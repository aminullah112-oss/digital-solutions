import { describe, expect, it } from 'vitest';
import { voltageDrop } from './voltage-drop';

const base = { amps: 20, oneWayMetres: 30, areaMm2: 4, volts: 230, material: 'copper' as const, tempC: 70, circuit: 'two-wire' as const };

describe('voltageDrop', () => {
  // rho70 = 0.017241*(1+0.00393*50) = 0.020629 ; 2*30*20*0.020629/4 = 6.189 V = 2.69 %
  it('single-phase 20 A, 30 m, 4 mm2, 230 V at 70 C', () => {
    const r = voltageDrop(base);
    expect(r.dropV).toBeCloseTo(6.189, 3);
    expect(r.dropPercent).toBeCloseTo(2.691, 3);
    expect(r.loadVolts).toBeCloseTo(223.811, 3);
  });
  // sqrt3*100*50*0.017241/25 = 5.972 V = 1.49 % of 400 V (20 C)
  it('three-phase 100 A, 50 m, 25 mm2, 400 V at 20 C', () => {
    const r = voltageDrop({ ...base, amps: 100, oneWayMetres: 50, areaMm2: 25, volts: 400, tempC: 20, circuit: 'three' });
    expect(r.rOhmPerKm).toBeCloseTo(0.68964, 5);
    expect(r.dropV).toBeCloseTo(5.9725, 3);
    expect(r.dropPercent).toBeCloseTo(1.4931, 3);
  });
  // with X = 0.08 ohm/km at PF 0.8: sqrt3*100*0.05*(0.68964*0.8 + 0.08*0.6) = 5.194 V
  it('adds reactance when supplied', () => {
    const r = voltageDrop({ ...base, amps: 100, oneWayMetres: 50, areaMm2: 25, volts: 400, tempC: 20, circuit: 'three', xOhmPerKm: 0.08, powerFactor: 0.8 });
    expect(r.dropV).toBeCloseTo(5.1937, 3);
  });
  it('ignores power factor without a reactance value', () => {
    expect(voltageDrop({ ...base, powerFactor: 0.5 }).dropV).toBeCloseTo(voltageDrop(base).dropV, 9);
  });
  // 12 V, 10 A, 10 m, 4 mm2 copper at 70 C: 2*10*10*0.020629/4 = 1.03 V = 8.6 %
  it('12 V DC shows why low voltage needs big cable', () => {
    expect(voltageDrop({ ...base, amps: 10, oneWayMetres: 10, volts: 12 }).dropPercent).toBeCloseTo(8.595, 2);
  });
  it('aluminium drops more than copper', () => {
    expect(voltageDrop({ ...base, material: 'aluminium' }).dropV).toBeGreaterThan(voltageDrop(base).dropV);
  });
  it('rejects bad input', () => {
    expect(() => voltageDrop({ ...base, areaMm2: 0 })).toThrow();
    expect(() => voltageDrop({ ...base, xOhmPerKm: 0.08, powerFactor: 1.5 })).toThrow();
  });
});
