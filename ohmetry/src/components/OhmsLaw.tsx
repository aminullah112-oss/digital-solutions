import { useState } from 'react';
import { solveOhm, type OhmResult } from '../lib/calc/ohms-law';

const FIELDS = [
  { key: 'V', label: 'Voltage', unit: 'V' },
  { key: 'I', label: 'Current', unit: 'A' },
  { key: 'R', label: 'Resistance', unit: 'Ω' },
  { key: 'P', label: 'Power', unit: 'W' },
] as const;
type Key = (typeof FIELDS)[number]['key'];

export default function OhmsLaw() {
  const [vals, setVals] = useState<Record<Key, string>>({ V: '12', I: '', R: '6', P: '' });
  let result: OhmResult | null = null;
  let error = '';
  const filled = FIELDS.filter((f) => vals[f.key].trim() !== '');
  if (filled.length === 2) {
    try {
      const known: Partial<Record<Key, number>> = {};
      for (const f of filled) known[f.key] = Number(vals[f.key]);
      result = solveOhm(known);
    } catch (e) { error = (e as Error).message; }
  } else {
    error = 'Fill in exactly two fields.';
  }
  const fmt = (n: number) => Number(n.toPrecision(6)).toString();

  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label="Ohm's law calculator">
      <div className="grid">
        {FIELDS.map((f) => (
          <label key={f.key}>
            {f.label} ({f.unit})
            <input inputMode="decimal" value={vals[f.key]}
              onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} />
          </label>
        ))}
      </div>
      {result ? (
        <div className="result" role="status">
          {FIELDS.map((f) => <div key={f.key}><span>{f.label}</span><strong>{fmt(result![f.key])} {f.unit}</strong></div>)}
        </div>
      ) : <p className="hint" role="status">{error}</p>}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}
