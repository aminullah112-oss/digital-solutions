/**
 * Inverter sizing. Continuous rating covers the running load plus a margin.
 * Surge rating must cover the running load with the largest motor in its starting state.
 */
export interface InverterSize { continuousW: number; surgeW: number; dcAmps: number }

export function inverterSize(
  runningW: number, motorRunW: number, motorStartW: number, batteryV: number, eff: number, margin = 0.25,
): InverterSize {
  if (!(runningW > 0) || !(batteryV > 0)) throw new Error('Running load and battery voltage must be positive');
  if (!(motorRunW >= 0) || !(motorStartW >= 0)) throw new Error('Motor figures cannot be negative');
  if (motorRunW > runningW) throw new Error('Motor running watts cannot exceed the total running load');
  if (motorStartW > 0 && motorStartW < motorRunW) throw new Error('Starting watts must be at least the running watts');
  if (!(eff > 0 && eff <= 1)) throw new Error('Efficiency must be in (0, 1]');
  if (!(margin >= 0 && margin <= 1)) throw new Error('Margin must be between 0 and 1');
  const continuousW = runningW * (1 + margin);
  const surgeW = runningW - motorRunW + Math.max(motorStartW, motorRunW);
  return { continuousW, surgeW, dcAmps: continuousW / (batteryV * eff) };
}
