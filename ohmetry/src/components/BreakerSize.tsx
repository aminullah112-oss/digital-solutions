import { useState } from 'react';
import { breakerSize, type BreakerResult } from '../lib/calc/breaker-size';

export default function BreakerSize() {
  const [cont, setCont] = useState('32');
  const [non, setNon] = useState('0');
  let r: BreakerResult | null = null;
  let error = '';
  try { r = breakerSize(Number(cont), Number(non)); } catch (e) { error = (e as Error).message; }
  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label="Breaker size calculator">
      <div className="grid">
        <label>Continuous load (A)<input inputMode="decimal" value={cont} onChange={(e) => setCont(e.target.value)} /></label>
        <label>Noncontinuous load (A)<input inputMode="decimal" value={non} onChange={(e) => setNon(e.target.value)} /></label>
      </div>
      {r
        ? <div className="result" role="status">
            <div><span>Minimum rating (125% + 100%)</span><strong>{r.minAmps.toFixed(2)} A</strong></div>
            <div><span>Standard breaker</span><strong>{r.breaker} A</strong></div>
          </div>
        : <p className="hint" role="status">{error}</p>}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}
