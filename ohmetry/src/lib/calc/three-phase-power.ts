/** Balanced three-phase power from line voltage, line current and power factor. */
export interface ThreePhasePower { kVA: number; kW: number; kvar: number }

export function threePhasePower(lineVolts: number, amps: number, powerFactor: number): ThreePhasePower {
  if (!(lineVolts > 0) || !(amps > 0)) throw new Error('Voltage and current must be positive');
  if (!(powerFactor > 0 && powerFactor <= 1)) throw new Error('Power factor must be in (0, 1]');
  const kVA = (Math.sqrt(3) * lineVolts * amps) / 1000;
  const kW = kVA * powerFactor;
  const kvar = kVA * Math.sqrt(1 - powerFactor * powerFactor);
  return { kVA, kW, kvar };
}
