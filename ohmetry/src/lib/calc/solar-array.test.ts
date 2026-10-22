import { describe, expect, it } from 'vitest';
import { solarArray } from './solar-array';

describe('solarArray', () => {
  // 30 kWh / (5 * 0.75) = 8.0 kW -> 20 x 400 W
  it('30 kWh/day, 5 PSH, PR 0.75, 400 W panels', () => {
    const r = solarArray(30, 5, 0.75, 400);
    expect(r.arrayW).toBeCloseTo(8000, 6);
    expect(r.panels).toBe(20);
    expect(r.installedW).toBe(8000);
    expect(r.dailyKwh).toBeCloseTo(30, 6);
  });
  // 10 kWh / (4 * 0.8) = 3125 W -> 7.8 -> 8 panels of 400 W = 3200 W
  it('rounds panel count up', () => {
    const r = solarArray(10, 4, 0.8, 400);
    expect(r.arrayW).toBeCloseTo(3125, 6);
    expect(r.panels).toBe(8);
    expect(r.installedW).toBe(3200);
  });
  it('rejects bad input', () => {
    expect(() => solarArray(0, 5, 0.75, 400)).toThrow();
    expect(() => solarArray(10, 0, 0.75, 400)).toThrow();
    expect(() => solarArray(10, 5, 1.2, 400)).toThrow();
  });
});
