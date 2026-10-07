import { describe, expect, it } from 'vitest';
import { breakerSize } from './breaker-size';

describe('breakerSize', () => {
  // 1.25 * 32 = 40 exactly -> 40 A (typical 32 A EV charger)
  it('32 A continuous -> 40 A', () => expect(breakerSize(32)).toEqual({ minAmps: 40, breaker: 40 }));
  // 1.25 * 40 = 50 -> 50 A (40 A EVSE)
  it('40 A continuous -> 50 A', () => expect(breakerSize(40).breaker).toBe(50));
  // 1.25 * 24 = 30 -> 30 A
  it('24 A continuous -> 30 A', () => expect(breakerSize(24).breaker).toBe(30));
  // 1.25 * 25 = 31.25 -> next size up is 35 A
  it('25 A continuous -> 35 A', () => expect(breakerSize(25).breaker).toBe(35));
  // 1.25 * 16 + 10 = 30 -> 30 A
  it('mixed load 16 A + 10 A -> 30 A', () => expect(breakerSize(16, 10).breaker).toBe(30));
  it('noncontinuous only is not derated', () => expect(breakerSize(0, 20).breaker).toBe(20));
  // 1.25 * 160 = 200 -> 200 A
  it('160 A continuous -> 200 A', () => expect(breakerSize(160).breaker).toBe(200));
  it('rejects zero and oversize', () => {
    expect(() => breakerSize(0, 0)).toThrow();
    expect(() => breakerSize(5000)).toThrow();
  });
});
