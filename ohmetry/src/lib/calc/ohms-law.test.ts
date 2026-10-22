import { describe, expect, it } from 'vitest';
import { solveOhm } from './ohms-law';

// Golden case: 12 V across 6 ohm -> 2 A, 24 W (checked by hand).
const golden = { V: 12, I: 2, R: 6, P: 24 };

describe('solveOhm', () => {
  const pairs: Array<[string, Parameters<typeof solveOhm>[0]]> = [
    ['V,I', { V: 12, I: 2 }], ['V,R', { V: 12, R: 6 }], ['V,P', { V: 12, P: 24 }],
    ['I,R', { I: 2, R: 6 }], ['I,P', { I: 2, P: 24 }], ['R,P', { R: 6, P: 24 }],
  ];
  it.each(pairs)('reproduces the golden case from %s', (_n, input) => {
    const r = solveOhm(input);
    for (const key of ['V', 'I', 'R', 'P'] as const) expect(r[key]).toBeCloseTo(golden[key], 9);
  });
  it('rejects the wrong number of inputs', () => {
    expect(() => solveOhm({ V: 1 })).toThrow();
    expect(() => solveOhm({ V: 1, I: 1, R: 1 })).toThrow();
  });
  it('rejects zero, negative and NaN', () => {
    expect(() => solveOhm({ V: 0, I: 1 })).toThrow();
    expect(() => solveOhm({ V: -5, I: 1 })).toThrow();
    expect(() => solveOhm({ V: NaN, I: 1 })).toThrow();
  });
});
