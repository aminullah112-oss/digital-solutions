import { useState } from 'react';
import { earthRodOhms, rodLengthForTarget } from '../lib/calc/earth-rod';
import { Form, Num, Out, run } from './ui';

export default function EarthRod() {
  const [rho, setRho] = useState('100');
  const [len, setLen] = useState('3');
  const [dia, setDia] = useState('16');
  const [target, setTarget] = useState('10');
  const r = run(() => earthRodOhms(Number(rho), Number(len), Number(dia)));
  const need = run(() => rodLengthForTarget(Number(rho), Number(dia), Number(target)));
  return (
    <Form label="Earth rod resistance calculator">
      <div className="grid">
        <Num label="Soil resistivity (Ω·m)" value={rho} set={setRho} hint="Measure it (Wenner method). Wet clay ~20 to 100, dry sand over 1000" />
        <Num label="Driven rod length (m)" value={len} set={setLen} />
        <Num label="Rod diameter (mm)" value={dia} set={setDia} />
        <Num label="Target resistance (Ω)" value={target} set={setTarget} />
      </div>
      <Out error={r.error} items={r.out !== null ? [
        ['Single rod resistance', `${r.out.toFixed(1)} Ω`],
        ['Length for the target', need.out === null ? 'One rod cannot reach it (use more rods)' : `${need.out.toFixed(1)} m`],
      ] : null} />
    </Form>
  );
}
