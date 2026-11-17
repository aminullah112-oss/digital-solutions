import { useState } from 'react';
import { awgToDiameterMm, awgToMm2, mm2ToNearestAwg, awgLabel } from '../lib/calc/awg-to-mm2';

const SIZES = Array.from({ length: 34 }, (_, i) => 30 - i); // 30 down to -3 (4/0)

export default function AwgToMm2() {
  const [mode, setMode] = useState<'awg' | 'mm2'>('awg');
  const [awg, setAwg] = useState(10);
  const [mm2, setMm2] = useState('6');
  let out = null as null | { label: string; d: number; area: number; note?: string };
  let error = '';
  try {
    if (mode === 'awg') out = { label: awgLabel(awg), d: awgToDiameterMm(awg), area: awgToMm2(awg) };
    else {
      const n = mm2ToNearestAwg(Number(mm2));
      out = { label: awgLabel(n), d: awgToDiameterMm(n), area: awgToMm2(n), note: `Nearest AWG size to ${Number(mm2)} mm²` };
    }
  } catch (e) { error = (e as Error).message; }
  return (
    <form className="calc" onSubmit={(e) => e.preventDefault()} aria-label="AWG to mm2 converter">
      <div className="grid">
        <label>Convert
          <select value={mode} onChange={(e) => setMode(e.target.value as 'awg' | 'mm2')}>
            <option value="awg">AWG to mm²</option><option value="mm2">mm² to nearest AWG</option>
          </select>
        </label>
        {mode === 'awg'
          ? <label>AWG size
              <select value={awg} onChange={(e) => setAwg(Number(e.target.value))}>
                {SIZES.map((n) => <option key={n} value={n}>{awgLabel(n)}</option>)}
              </select>
            </label>
          : <label>Area (mm²)<input inputMode="decimal" value={mm2} onChange={(e) => setMm2(e.target.value)} /></label>}
      </div>
      {out
        ? <><div className="result" role="status">
            <div><span>AWG</span><strong>{out.label}</strong></div>
            <div><span>Area</span><strong>{out.area.toFixed(2)} mm²</strong></div>
            <div><span>Diameter</span><strong>{out.d.toFixed(3)} mm</strong></div>
          </div>{out.note && <p className="hint">{out.note}. Round up if you need at least the given area.</p>}</>
        : <p className="hint" role="status">{error}</p>}
      <button type="button" className="print" onClick={() => window.print()}>Print result</button>
    </form>
  );
}
