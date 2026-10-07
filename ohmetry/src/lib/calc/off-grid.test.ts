import { describe, expect, it } from 'vitest';
import { offGrid } from './off-grid';

const base = { dailyWh: 5000, peakLoadW: 2000, peakSunHours: 5, performanceRatio: 0.75, panelW: 400, batteryV: 48, days: 2, dod: 0.5, eff: 0.9 };

describe('offGrid', () => {
  // 5000/0.9 = 5555.6 Wh -> /(5*0.75) = 1481.5 W -> 3.70 -> 4 panels = 1600 W
  // controller 1600/48*1.25 = 41.67 A ; inverter 2000*1.25 = 2500 W ; battery 462.96 Ah
  it('reference system', () => {
    const r = offGrid(base);
    expect(r.panels).toBe(4);
    expect(r.installedW).toBe(1600);
    expect(r.controllerAmps).toBeCloseTo(41.667, 3);
    expect(r.inverterW).toBe(2500);
    expect(r.batteryAh).toBeCloseTo(462.963, 3);
    expect(r.batteryKwhNominal).toBeCloseTo(22.222, 3);
  });
  // 5555.6 / (3 * 0.75) = 2469 W -> 6.17 -> 7 panels
  it('lower sun hours need more panels', () => expect(offGrid({ ...base, peakSunHours: 3 }).panels).toBe(7));
  it('rejects bad input', () => {
    expect(() => offGrid({ ...base, peakLoadW: 0 })).toThrow();
    expect(() => offGrid({ ...base, eff: 0 })).toThrow();
  });
});
