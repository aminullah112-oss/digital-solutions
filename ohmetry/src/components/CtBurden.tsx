import { useState } from 'react';
import { ctBurden } from '../lib/calc/ct-burden';
import { Form, Num, Out, run } from './ui';

export default function CtBurden() {
  const [s, setS] = useState({ secondaryA: '5', leadOneWayM: '20', leadAreaMm2: '4', tempC: '20', relayVA: '1', ratedVA: '15', alf: '20', rctOhm: '0.2' });
  const f = (k: keyof typeof s, label: string, hint?: string) => <Num label={label} value={s[k]} set={(v) => setS({ ...s, [k]: v })} hint={hint} />;
  const { out, error } = run(() => ctBurden(Object.fromEntries(Object.entries(s).map(([k, v]) => [k, Number(v)])) as never));
  return (
    <Form label="CT burden calculator">
      <div className="grid">
        {f('secondaryA', 'CT secondary rating (A)', '1 or 5')}
        {f('leadOneWayM', 'One-way lead length (m)', 'CT to relay; the loop is twice this')}
        {f('leadAreaMm2', 'Lead cross-section (mm²)')}
        {f('tempC', 'Lead temperature (°C)')}
        {f('relayVA', 'Relay burden at rated current (VA)', 'From the relay datasheet')}
        {f('ratedVA', 'CT rated burden (VA)')}
        {f('alf', 'Rated accuracy limit factor', 'The 20 in 15 VA 5P20')}
        {f('rctOhm', 'CT secondary resistance (Ω)', 'From the CT test report')}
      </div>
      <Out error={error} items={out && [
        ['Lead loop resistance', `${out.leadOhm.toFixed(3)} Ω`],
        ['Lead burden', `${out.leadVA.toFixed(2)} VA`],
        ['Total connected burden', `${out.totalVA.toFixed(2)} VA`],
        ['Share of rated burden', `${(out.utilisation * 100).toFixed(0)} %`],
        ['Effective ALF', out.effectiveAlf.toFixed(1)],
        ['Within rated burden', out.ok ? 'Yes' : 'No'],
      ]} />
    </Form>
  );
}
