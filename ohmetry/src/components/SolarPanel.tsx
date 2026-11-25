import { useState } from 'react';
import { solarArray } from '../lib/calc/solar-array';
import { Form, Num, Out, run } from './ui';

export default function SolarPanel() {
  const [kwh, setKwh] = useState('30');
  const [psh, setPsh] = useState('5');
  const [pr, setPr] = useState('0.75');
  const [w, setW] = useState('400');
  const { out, error } = run(() => solarArray(Number(kwh), Number(psh), Number(pr), Number(w)));
  return (
    <Form label="Solar panel system size calculator">
      <div className="grid">
        <Num label="Daily energy to produce (kWh)" value={kwh} set={setKwh} hint="From your bill: monthly kWh / 30" />
        <Num label="Peak sun hours per day" value={psh} set={setPsh} hint="Site and season specific, often 3 to 6" />
        <Num label="Performance ratio" value={pr} set={setPr} hint="0.75 is a common planning value" />
        <Num label="Panel rating (W)" value={w} set={setW} />
      </div>
      <Out error={error} items={out && [
        ['Array needed', `${(out.arrayW / 1000).toFixed(2)} kW`],
        ['Panels', `${out.panels} × ${Number(w)} W`],
        ['Installed', `${(out.installedW / 1000).toFixed(2)} kW`],
        ['Expected output', `${out.dailyKwh.toFixed(1)} kWh/day`],
      ]} />
    </Form>
  );
}
