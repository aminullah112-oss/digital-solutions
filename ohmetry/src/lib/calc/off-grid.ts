/**
 * Off-grid system estimate. Energy flows panel -> controller -> battery -> inverter -> load,
 * so the array must cover the daily load divided by the battery/inverter efficiency,
 * then divided again by PSH * PR for the panel side.
 */
import { solarArray } from './solar-array';
import { batterySize } from './battery';

export interface OffGridInput {
  dailyWh: number; peakLoadW: number; peakSunHours: number; performanceRatio: number;
  panelW: number; batteryV: number; days: number; dod: number; eff: number;
}
export interface OffGridResult {
  panels: number; installedW: number; batteryAh: number; batteryKwhNominal: number;
  inverterW: number; controllerAmps: number;
}

export function offGrid(i: OffGridInput): OffGridResult {
  if (!(i.peakLoadW > 0)) throw new Error('Peak load must be positive');
  if (!(i.eff > 0 && i.eff <= 1)) throw new Error('Efficiency must be in (0, 1]');
  const arr = solarArray((i.dailyWh / i.eff) / 1000, i.peakSunHours, i.performanceRatio, i.panelW);
  const bat = batterySize(i.dailyWh, i.days, i.dod, i.batteryV, i.eff);
  return {
    panels: arr.panels,
    installedW: arr.installedW,
    batteryAh: bat.ah,
    batteryKwhNominal: bat.kwhNominal,
    inverterW: i.peakLoadW * 1.25,
    // MPPT output current into the battery, with a 25 % margin
    controllerAmps: (arr.installedW / i.batteryV) * 1.25,
  };
}
