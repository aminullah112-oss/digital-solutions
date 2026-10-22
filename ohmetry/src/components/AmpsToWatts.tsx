import { useState } from 'react';
import { ampsToWatts, type Supply } from '../lib/calc/amps-to-watts';

export default function AmpsToWatts() {
  const [amps, setAmps] = useState('15');
  const [volts, setVolts] = useState('120');
  const [pf, setPf] = useState('0.9');
  const [supply, setSupply] = useState<Supply>('single');
  let watts: number | null = null;
  let error = '';
  try { watts = ampsToWatts(Number(amps), Number(volts), Number(pf), supply); }
  catch (e) { error = (e as Error).message; }
  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label="Amps to watts calculator">
      <div className="grid">
        <label>Current (A)<input inputMode="decimal" value={amps} onChange={(e) => setAmps(e.target.value)} /></label>
        <label>Voltage (V, line-to-line for 3-phase)<input inputMode="decimal" value={volts} onChange={(e) => setVolts(e.target.value)} /></label>
        <label>Supply
          <select value={supply} onChange={(e) => setSupply(e.target.value as Supply)}>
            <option value="dc">DC</option><option value="single">AC single-phase</option><option value="three">AC three-phase</option>
          </select>
        </label>
        {supply !== 'dc' && <label>Power factor<input inputMode="decimal" value={pf} onChange={(e) => setPf(e.target.value)} /></label>}
      </div>
      {watts !== null
        ? <div className="result" role="status"><div><span>Real power</span><strong>{watts.toFixed(1)} W</strong></div><div><span>In kilowatts</span><strong>{(watts / 1000).toFixed(3)} kW</strong></div></div>
        : <p className="hint" role="status">{error}</p>}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}
