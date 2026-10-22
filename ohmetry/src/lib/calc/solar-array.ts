/**
 * Array size from daily energy: P_array = E_day / (PSH * PR).
 * PSH = peak sun hours (kWh/m2/day on the array plane). PR = performance ratio,
 * the combined derate for temperature, soiling, wiring, mismatch and inverter loss.
 */
export interface SolarArray { arrayW: number; panels: number; installedW: number; dailyKwh: number }

export function solarArray(dailyKwh: number, peakSunHours: number, performanceRatio: number, panelW: number): SolarArray {
  if (!(dailyKwh > 0) || !(panelW > 0)) throw new Error('Daily energy and panel wattage must be positive');
  if (!(peakSunHours > 0 && peakSunHours <= 12)) throw new Error('Peak sun hours must be between 0 and 12');
  if (!(performanceRatio > 0 && performanceRatio <= 1)) throw new Error('Performance ratio must be in (0, 1]');
  const arrayW = (dailyKwh * 1000) / (peakSunHours * performanceRatio);
  const panels = Math.ceil(arrayW / panelW - 1e-9);
  const installedW = panels * panelW;
  return { arrayW, panels, installedW, dailyKwh: (installedW * peakSunHours * performanceRatio) / 1000 };
}
