import { useState } from 'react';
import { threePhasePower, type ThreePhasePower as R } from '../lib/calc/three-phase-power';

export default function ThreePhasePower() {
  const [v, setV] = useState('400');
  const [a, setA] = useState('10');
  const [pf, setPf] = useState('0.8');
  let r: R | null = null;
  let error = '';
  try { r = threePhasePower(Number(v), Number(a), Number(pf)); } catch (e) { error = (e as Error).message; }
  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label="Three-phase power calculator">
      <div className="grid">
        <label>Line-to-line voltage (V)<input inputMode="decimal" value={v} onChange={(e) => setV(e.target.value)} /></label>
        <label>Line current (A)<input inputMode="decimal" value={a} onChange={(e) => setA(e.target.value)} /></label>
        <label>Power factor<input inputMode="decimal" value={pf} onChange={(e) => setPf(e.target.value)} /></label>
      </div>
      {r
        ? <div className="result" role="status">
            <div><span>Apparent (S)</span><strong>{r.kVA.toFixed(3)} kVA</strong></div>
            <div><span>Real (P)</span><strong>{r.kW.toFixed(3)} kW</strong></div>
            <div><span>Reactive (Q)</span><strong>{r.kvar.toFixed(3)} kvar</strong></div>
          </div>
        : <p className="hint" role="status">{error}</p>}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}
