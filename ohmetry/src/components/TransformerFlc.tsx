import { useState } from 'react';
import { transformerFlc } from '../lib/calc/transformer';
import { Form, Num, Out, run } from './ui';

export default function TransformerFlc() {
  const [kva, setKva] = useState('1000');
  const [pv, setPv] = useState('11000');
  const [sv, setSv] = useState('400');
  const { out, error } = run(() => transformerFlc(Number(kva), Number(pv), Number(sv)));
  return (
    <Form label="Transformer full-load current calculator">
      <div className="grid">
        <Num label="Rating (kVA, three-phase)" value={kva} set={setKva} />
        <Num label="Primary voltage (V, line-to-line)" value={pv} set={setPv} />
        <Num label="Secondary voltage (V, line-to-line)" value={sv} set={setSv} />
      </div>
      <Out error={error} items={out && [
        ['Primary full-load current', `${out.primaryA.toFixed(2)} A`],
        ['Secondary full-load current', `${out.secondaryA.toFixed(1)} A`],
        ['Voltage ratio', `${out.ratio.toFixed(2)} : 1`],
      ]} />
    </Form>
  );
}
