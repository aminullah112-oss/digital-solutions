import { useState } from 'react';
import { inverterSize } from '../lib/calc/inverter';
import { Form, Num, Out, run } from './ui';

export default function InverterSize() {
  const [run_, setRun] = useState('3000');
  const [mRun, setMRun] = useState('800');
  const [mStart, setMStart] = useState('2400');
  const [v, setV] = useState('48');
  const [eff, setEff] = useState('0.9');
  const { out, error } = run(() => inverterSize(Number(run_), Number(mRun), Number(mStart), Number(v), Number(eff)));
  return (
    <Form label="Inverter size calculator">
      <div className="grid">
        <Num label="Total running load (W)" value={run_} set={setRun} hint="Everything that can be on at once" />
        <Num label="Largest motor, running (W)" value={mRun} set={setMRun} hint="0 if none" />
        <Num label="Largest motor, starting (W)" value={mStart} set={setMStart} hint="Often 3 to 7 times running" />
        <Num label="Battery voltage (V)" value={v} set={setV} />
        <Num label="Inverter efficiency" value={eff} set={setEff} />
      </div>
      <Out error={error} items={out && [
        ['Continuous rating', `${out.continuousW.toFixed(0)} W`],
        ['Surge rating', `${out.surgeW.toFixed(0)} W`],
        ['Max DC current', `${out.dcAmps.toFixed(0)} A at ${Number(v)} V`],
      ]} />
    </Form>
  );
}
