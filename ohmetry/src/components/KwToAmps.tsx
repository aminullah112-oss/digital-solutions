import { useState } from 'react';
import { kwToAmps, type Phase } from '../lib/calc/kw-to-amps';

export default function KwToAmps() {
  const [kw, setKw] = useState('10');
  const [volts, setVolts] = useState('400');
  const [pf, setPf] = useState('0.8');
  const [phase, setPhase] = useState<Phase>('three');
  let amps: number | null = null;
  let error = '';
  try { amps = kwToAmps(Number(kw), Number(volts), Number(pf), phase); }
  catch (e) { error = (e as Error).message; }

  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label="kW to amps calculator">
      <div className="grid">
        <label>Power (kW)<input inputMode="decimal" value={kw} onChange={(e) => setKw(e.target.value)} /></label>
        <label>Voltage (V, line-to-line for 3-phase)<input inputMode="decimal" value={volts} onChange={(e) => setVolts(e.target.value)} /></label>
        <label>Power factor<input inputMode="decimal" value={pf} onChange={(e) => setPf(e.target.value)} /></label>
        <label>Phase
          <select value={phase} onChange={(e) => setPhase(e.target.value as Phase)}>
            <option value="single">Single-phase</option>
            <option value="three">Three-phase</option>
          </select>
        </label>
      </div>
      {amps !== null
        ? <div className="result" role="status"><div><span>Line current</span><strong>{amps.toFixed(2)} A</strong></div></div>
        : <p className="hint" role="status">{error}</p>}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}
