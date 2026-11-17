import { useState } from 'react';
import { offGrid } from '../lib/calc/off-grid';
import { Form, Num, Out, run } from './ui';

export default function OffGrid() {
  const [s, setS] = useState({ dailyWh: '5000', peakLoadW: '2000', peakSunHours: '5', performanceRatio: '0.75', panelW: '400', batteryV: '48', days: '2', dod: '0.5', eff: '0.9' });
  const f = (k: keyof typeof s, label: string, hint?: string) => <Num label={label} value={s[k]} set={(v) => setS({ ...s, [k]: v })} hint={hint} />;
  const { out, error } = run(() => offGrid(Object.fromEntries(Object.entries(s).map(([k, v]) => [k, Number(v)])) as never));
  return (
    <Form label="Off-grid solar system calculator">
      <div className="grid">
        {f('dailyWh', 'Daily load (Wh)', 'Add up every appliance: W × hours')}
        {f('peakLoadW', 'Peak load at once (W)')}
        {f('peakSunHours', 'Peak sun hours', 'Use the worst month you must cover')}
        {f('performanceRatio', 'Performance ratio')}
        {f('panelW', 'Panel rating (W)')}
        {f('batteryV', 'Battery voltage (V)')}
        {f('days', 'Days of autonomy')}
        {f('dod', 'Usable depth of discharge')}
        {f('eff', 'Inverter efficiency')}
      </div>
      <Out error={error} items={out && [
        ['Panels', `${out.panels} × ${Number(s.panelW)} W (${(out.installedW / 1000).toFixed(2)} kW)`],
        ['Battery', `${out.batteryAh.toFixed(0)} Ah at ${Number(s.batteryV)} V (${out.batteryKwhNominal.toFixed(1)} kWh)`],
        ['Inverter', `${out.inverterW.toFixed(0)} W continuous`],
        ['Charge controller', `${out.controllerAmps.toFixed(0)} A minimum`],
      ]} />
    </Form>
  );
}
