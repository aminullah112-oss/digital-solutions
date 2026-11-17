import { describe, expect, it } from 'vitest';
import { evCircuit, kwToChargerAmps, chargeHours } from './ev-charger';

describe('ev-charger', () => {
  it('32 A charger -> 40 A min ampacity, 40 A breaker', () => expect(evCircuit(32)).toEqual({ chargerAmps: 32, minAmpacity: 40, breaker: 40 }));
  it('40 A charger -> 50 A breaker', () => expect(evCircuit(40).breaker).toBe(50));
  // 7200/240 = 30 A ; 1.25*30 = 37.5 -> 40 A
  it('7.2 kW at 240 V -> 30 A -> 40 A breaker', () => {
    const a = kwToChargerAmps(7.2, 240);
    expect(a).toBeCloseTo(30, 9);
    expect(evCircuit(a).breaker).toBe(40);
  });
  // 11.5 kW / 240 = 47.92 A ; *1.25 = 59.9 -> 60 A
  it('11.5 kW at 240 V -> 60 A breaker', () => expect(evCircuit(kwToChargerAmps(11.5, 240)).breaker).toBe(60));
  // 60 kWh / (7.2 * 0.9) = 9.259 h
  it('charge time for 60 kWh at 7.2 kW', () => expect(chargeHours(60, 7.2)).toBeCloseTo(9.259, 3));
  it('rejects bad input', () => {
    expect(() => kwToChargerAmps(0, 240)).toThrow();
    expect(() => chargeHours(60, 7.2, 0)).toThrow();
  });
});
