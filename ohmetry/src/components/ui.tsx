import type { ReactNode } from 'react';

export function Num({ label, value, set, hint }: { label: string; value: string; set: (v: string) => void; hint?: string }) {
  return (
    <label>{label}
      <input inputMode="decimal" value={value} onChange={(e) => set(e.target.value)} />
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function Sel<T extends string>({ label, value, set, options }: { label: string; value: T; set: (v: T) => void; options: [T, string][] }) {
  return (
    <label>{label}
      <select value={value} onChange={(e) => set(e.target.value as T)}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

export function Out({ items, error }: { items: [string, string][] | null; error: string }) {
  return items
    ? <div className="result" role="status">{items.map(([l, v]) => <div key={l}><span>{l}</span><strong>{v}</strong></div>)}</div>
    : <p className="hint" role="status">{error}</p>;
}

export function Form({ label, children }: { label: string; children: ReactNode }) {
  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label={label}>
      {children}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}

/** Run a calculation, returning either its output or the error message. */
export function run<T>(fn: () => T): { out: T | null; error: string } {
  try { return { out: fn(), error: '' }; } catch (e) { return { out: null, error: (e as Error).message }; }
}
