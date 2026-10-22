import { describe, expect, it } from 'vitest';
import { inverterSize } from './inverter';

describe('inverterSize', () => {
  // continuous 3000*1.25 = 3750 ; surge 3000-800+2400 = 4600 ; DC 3750/(48*0.9) = 86.81 A
  it('3 kW running, 800 W motor starting at 2400 W, 48 V', () => {
    const r = inverterSize(3000, 800, 2400, 48, 0.9);
    expect(r.continuousW).toBe(3750);
    expect(r.surgeW).toBe(4600);
    expect(r.dcAmps).toBeCloseTo(86.806, 3);
  });
  it('no motor means surge equals running load', () => expect(inverterSize(1000, 0, 0, 24, 0.9).surgeW).toBe(1000));
  it('rejects inconsistent motor data', () => {
    expect(() => inverterSize(1000, 1200, 2000, 24, 0.9)).toThrow();
    expect(() => inverterSize(1000, 500, 300, 24, 0.9)).toThrow();
  });
});
