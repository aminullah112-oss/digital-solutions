/** Line current from apparent power. Single: kVA*1000/V. Three-phase: kVA*1000/(sqrt3*V_LL). */
export type Phase = 'single' | 'three';

export function kvaToAmps(kva: number, volts: number, phase: Phase): number {
  if (!(kva > 0) || !(volts > 0)) throw new Error('kVA and volts must be positive');
  return (kva * 1000) / ((phase === 'three' ? Math.sqrt(3) : 1) * volts);
}
