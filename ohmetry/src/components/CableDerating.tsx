import { useState } from 'react';
import { requiredTabulated } from '../lib/calc/cable-derating';
import { minAreaMm2, nextIecSize, dropVolts, type Material } from '../lib/calc/conductor-drop';
import { Form, Num, Out, Sel, run } from './ui';

export default function CableDerating() {
  const [ib, setIb] = useState('55');
  const [inn, setIn] = useState('63');
  const [kt, setKt] = useState('0.87');
  const [kg, setKg] = useState('0.8');
  const [ko, setKo] = useState('1');
  const [len, setLen] = useState('50');
  const [volts, setVolts] = useState('400');
  const [drop, setDrop] = useState('3');
  const [circuit, setCircuit] = useState<'three' | 'two-wire'>('three');
  const [mat, setMat] = useState<Material>('copper');
  const { out, error } = run(() => {
    const d = requiredTabulated(Number(ib), inn.trim() === '' ? null : Number(inn), [Number(kt), Number(kg), Number(ko)]);
    const base = { amps: Number(ib), oneWayMetres: Number(len), material: mat, tempC: 70, circuit };
    const area = minAreaMm2({ ...base, volts: Number(volts), maxDropPercent: Number(drop) });
    const size = nextIecSize(area);
    return { d, area, size, pct: size ? (dropVolts(base, size) / Number(volts)) * 100 : null };
  });
  return (
    <Form label="IEC cable size calculator with derating factors">
      <div className="grid">
        <Num label="Design current Ib (A)" value={ib} set={setIb} />
        <Num label="Protective device In (A)" value={inn} set={setIn} hint="Leave empty to use Ib" />
        <Num label="Ambient temperature factor" value={kt} set={setKt} hint="From IEC 60364-5-52 for your ambient and insulation" />
        <Num label="Grouping factor" value={kg} set={setKg} hint="From the same standard for your installation method" />
        <Num label="Other factor" value={ko} set={setKo} hint="Soil thermal resistivity, depth, etc. Use 1 if none" />
        <Num label="One-way length (m)" value={len} set={setLen} />
        <Num label="System voltage (V)" value={volts} set={setVolts} />
        <Num label="Allowed voltage drop (%)" value={drop} set={setDrop} />
        <Sel label="Circuit" value={circuit} set={setCircuit} options={[['three', 'Three-phase'], ['two-wire', 'Single-phase / DC']]} />
        <Sel label="Conductor" value={mat} set={setMat} options={[['copper', 'Copper'], ['aluminium', 'Aluminium']]} />
      </div>
      <Out error={error} items={out && [
        ['Combined factor k', out.d.k.toFixed(3)],
        ['Tabulated rating needed', `${out.d.requiredTabulatedA.toFixed(1)} A or more`],
        ['Min area for voltage drop', `${out.area.toFixed(2)} mm² (at 70 °C)`],
        ['Voltage-drop size', out.size ? `${out.size} mm² (drop ${out.pct!.toFixed(2)} %)` : 'Over 300 mm²: use parallel runs'],
      ]} />
      <p className="hint">Find the smallest cable whose tabulated rating in your standard's table is at least the value above, and use the larger of that and the voltage-drop size. Voltage drop here is resistive only.</p>
    </Form>
  );
}
