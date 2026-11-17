import { useState } from 'react';
import { voltageDrop } from '../lib/calc/voltage-drop';
import type { Material } from '../lib/calc/conductor-drop';
import { Form, Num, Out, Sel, run } from './ui';

export default function VoltageDrop() {
  const [circuit, setCircuit] = useState<'two-wire' | 'three'>('two-wire');
  const [amps, setAmps] = useState('20');
  const [len, setLen] = useState('30');
  const [area, setArea] = useState('4');
  const [volts, setVolts] = useState('230');
  const [mat, setMat] = useState<Material>('copper');
  const [temp, setTemp] = useState('70');
  const [x, setX] = useState('');
  const [pf, setPf] = useState('0.9');
  const { out, error } = run(() => voltageDrop({
    amps: Number(amps), oneWayMetres: Number(len), areaMm2: Number(area), volts: Number(volts), material: mat, tempC: Number(temp), circuit,
    xOhmPerKm: x.trim() === '' ? undefined : Number(x), powerFactor: Number(pf),
  }));
  return (
    <Form label="Voltage drop calculator">
      <div className="grid">
        <Sel label="Circuit" value={circuit} set={setCircuit} options={[['two-wire', 'Single-phase or DC (two wires)'], ['three', 'Three-phase']]} />
        <Num label="Load current (A)" value={amps} set={setAmps} />
        <Num label="One-way cable length (m)" value={len} set={setLen} />
        <Num label="Conductor cross-section (mm²)" value={area} set={setArea} hint="Use the AWG to mm² converter for AWG sizes" />
        <Num label="Supply voltage (V)" value={volts} set={setVolts} hint="Line-to-line for three-phase" />
        <Sel label="Conductor" value={mat} set={setMat} options={[['copper', 'Copper'], ['aluminium', 'Aluminium']]} />
        <Num label="Conductor temperature (°C)" value={temp} set={setTemp} hint="70 for PVC at full load, 90 for XLPE" />
        <Num label="Cable reactance (Ω/km), optional" value={x} set={setX} hint="From the data sheet. Leave empty for resistance only" />
        {x.trim() !== '' && <Num label="Load power factor" value={pf} set={setPf} />}
      </div>
      <Out error={error} items={out && [
        ['Voltage drop', `${out.dropV.toFixed(2)} V`],
        ['Drop', `${out.dropPercent.toFixed(2)} %`],
        ['Voltage at the load', `${out.loadVolts.toFixed(1)} V`],
        ['Conductor resistance', `${out.rOhmPerKm.toFixed(3)} Ω/km`],
      ]} />
    </Form>
  );
}
