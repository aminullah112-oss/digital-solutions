import { useState } from 'react';
import { kvaToAmps, type Phase } from '../lib/calc/kva-to-amps';

export default function KvaToAmps() {
  const [kva, setKva] = useState('100');
  const [volts, setVolts] = useState('400');
  const [phase, setPhase] = useState<Phase>('three');
  let amps: number | null = null;
  let error = '';
  try { amps = kvaToAmps(Number(kva), Number(volts), phase); } catch (e) { error = (e as Error).message; }
  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label="kVA to amps calculator">
      <div className="grid">
        <label>Apparent power (kVA)<input inputMode="decimal" value={kva} onChange={(e) => setKva(e.target.value)} /></label>
        <label>Voltage (V, line-to-line for 3-phase)<input inputMode="decimal" value={volts} onChange={(e) => setVolts(e.target.value)} /></label>
        <label>Phase
          <select value={phase} onChange={(e) => setPhase(e.target.value as Phase)}>
            <option value="single">Single-phase</option><option value="three">Three-phase</option>
          </select>
        </label>
      </div>
      {amps !== null
        ? <div className="result" role="status"><div><span>Full-load current</span><strong>{amps.toFixed(2)} A</strong></div></div>
        : <p className="hint" role="status">{error}</p>}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}
