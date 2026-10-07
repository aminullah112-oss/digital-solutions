import { describe, expect, it } from 'vitest';
import { batterySize, batteryRuntimeHours } from './battery';

describe('battery', () => {
  // 5000*2 / (0.5*48*0.9) = 10000/21.6 = 462.96 Ah ; nominal 22.22 kWh ; usable 10 kWh
  it('5 kWh/day, 2 days, 50 % DoD, 48 V, 0.9 eff', () => {
    const r = batterySize(5000, 2, 0.5, 48, 0.9);
    expect(r.ah).toBeCloseTo(462.963, 3);
    expect(r.kwhNominal).toBeCloseTo(22.222, 3);
    expect(r.kwhUsable).toBeCloseTo(10, 6);
  });
  // 200*48*0.8*0.9 = 6912 Wh / 1000 W = 6.912 h
  it('runtime of 200 Ah 48 V at 1 kW', () => expect(batteryRuntimeHours(200, 48, 0.8, 0.9, 1000)).toBeCloseTo(6.912, 6));
  it('size then runtime round-trips to the stated autonomy', () => {
    const r = batterySize(5000, 2, 0.8, 24, 0.85);
    expect(batteryRuntimeHours(r.ah, 24, 0.8, 0.85, 5000 / 24)).toBeCloseTo(48, 6);
  });
  it('rejects bad input', () => {
    expect(() => batterySize(5000, 2, 0, 48, 0.9)).toThrow();
    expect(() => batterySize(5000, 2, 0.5, 48, 1.5)).toThrow();
    expect(() => batteryRuntimeHours(100, 12, 0.5, 0.9, 0)).toThrow();
  });
});
