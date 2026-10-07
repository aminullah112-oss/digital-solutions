import { useState } from 'react';
import { shortCircuit } from '../lib/calc/transformer';
import { Form, Num, Out, run } from './ui';

export default function ShortCircuit() {
  const [kva, setKva] = useState('1000');
  const [v, setV] = useState('400');
  const [z, setZ] = useState('5');
  const [src, setSrc] = useState('');
  const { out, error } = run(() => shortCircuit(Number(kva), Number(v), Number(z), src.trim() === '' ? undefined : Number(src)));
  return (
    <Form label="Transformer short-circuit current calculator">
      <div className="grid">
        <Num label="Rating (kVA)" value={kva} set={setKva} />
        <Num label="Secondary voltage (V, line-to-line)" value={v} set={setV} />
        <Num label="Transformer impedance (%Z)" value={z} set={setZ} hint="On the nameplate, typically 4 to 6 % for distribution units" />
        <Num label="Source fault level (MVA), optional" value={src} set={setSrc} hint="Leave empty for an infinite bus (worst case)" />
      </div>
      <Out error={error} items={out && [
        ['Full-load current', `${out.flcA.toFixed(1)} A`],
        ['Total impedance', `${(out.zPu * 100).toFixed(2)} %`],
        ['Symmetrical fault current', `${(out.iscA / 1000).toFixed(2)} kA`],
        ['Fault level', `${out.iscMvaTotal.toFixed(1)} MVA`],
      ]} />
    </Form>
  );
}
