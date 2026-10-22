/** Line current from real power. I = P / (V * PF) single-phase, P / (sqrt3 * V * PF) three-phase. */
export type Phase = 'single' | 'three';

export function kwToAmps(kw: number, volts: number, powerFactor: number, phase: Phase): number {
  if (!(kw > 0) || !(volts > 0)) throw new Error('kW and volts must be positive');
  if (!(powerFactor > 0 && powerFactor <= 1)) throw new Error('Power factor must be in (0, 1]');
  const k = phase === 'three' ? Math.sqrt(3) : 1;
  return (kw * 1000) / (k * volts * powerFactor);
}
