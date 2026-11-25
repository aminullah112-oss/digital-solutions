/** Real power from current. DC: P = V*I. AC single: V*I*PF. AC three-phase: sqrt3*V_LL*I*PF. */
export type Supply = 'dc' | 'single' | 'three';

export function ampsToWatts(amps: number, volts: number, powerFactor: number, supply: Supply): number {
  if (!(amps > 0) || !(volts > 0)) throw new Error('Amps and volts must be positive');
  if (supply === 'dc') return amps * volts;
  if (!(powerFactor > 0 && powerFactor <= 1)) throw new Error('Power factor must be in (0, 1]');
  return (supply === 'three' ? Math.sqrt(3) : 1) * volts * amps * powerFactor;
}
