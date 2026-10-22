import { useState } from 'react';
import { pfCorrection } from '../lib/calc/pf-correction';
import { Form, Num, Out, run } from './ui';

export default function PfCorrection() {
  const [kw, setKw] = useState('100');
  const [now, setNow] = useState('0.8');
  const [tgt, setTgt] = useState('0.95');
  const { out, error } = run(() => pfCorrection(Number(kw), Number(now), Number(tgt)));
  return (
    <Form label="Power factor correction calculator">
      <div className="grid">
        <Num label="Real power (kW)" value={kw} set={setKw} />
        <Num label="Present power factor" value={now} set={setNow} />
        <Num label="Target power factor" value={tgt} set={setTgt} />
      </div>
      <Out error={error} items={out && [
        ['Capacitor size needed', `${out.kvarNeeded.toFixed(1)} kvar`],
        ['Apparent power before', `${out.kvaBefore.toFixed(1)} kVA`],
        ['Apparent power after', `${out.kvaAfter.toFixed(1)} kVA`],
        ['Line current reduction', `${out.currentReductionPct.toFixed(1)} %`],
      ]} />
    </Form>
  );
}
