import { useState } from 'react';
import { minAreaMm2, dropVolts, nextIecSize, nextAwg, type Material } from '../lib/calc/conductor-drop';
import { awgToMm2, awgLabel } from '../lib/calc/awg-to-mm2';
import { Form, Num, Out, Sel, run } from './ui';

export default function DcCable({ defaults }: { defaults?: { amps: string; len: string; volts: string; drop: string } }) {
  const d = defaults ?? { amps: '10', len: '10', volts: '48', drop: '2' };
  const [amps, setAmps] = useState(d.amps);
  const [len, setLen] = useState(d.len);
  const [volts, setVolts] = useState(d.volts);
  const [drop, setDrop] = useState(d.drop);
  const [mat, setMat] = useState<Material>('copper');
  const [temp, setTemp] = useState('30');
  const { out, error } = run(() => {
    const inp = { amps: Number(amps), oneWayMetres: Number(len), volts: Number(volts), maxDropPercent: Number(drop), material: mat, tempC: Number(temp) };
    const min = minAreaMm2(inp);
    const iec = nextIecSize(min);
    const awg = nextAwg(min);
    return { min, iec, awg, dropIec: iec ? dropVolts(inp, iec) : null, dropAwg: awg !== null ? dropVolts(inp, awgToMm2(awg)) : null, v: Number(volts) };
  });
  return (
    <Form label="Cable size by voltage drop calculator">
      <div className="grid">
        <Num label="Current (A)" value={amps} set={setAmps} />
        <Num label="One-way cable length (m)" value={len} set={setLen} hint="Length of the run, not out and back" />
        <Num label="System voltage (V)" value={volts} set={setVolts} />
        <Num label="Allowed voltage drop (%)" value={drop} set={setDrop} hint="2 to 3 % is a common design target" />
        <Sel label="Conductor" value={mat} set={setMat} options={[['copper', 'Copper'], ['aluminium', 'Aluminium']]} />
        <Num label="Conductor temperature (°C)" value={temp} set={setTemp} hint="Resistance rises with temperature" />
      </div>
      <Out error={error} items={out && [
        ['Minimum area', `${out.min.toFixed(2)} mm²`],
        ['Next IEC size', out.iec ? `${out.iec} mm² (drop ${(out.dropIec! / out.v * 100).toFixed(2)} %)` : 'Over 300 mm²: use parallel runs'],
        ['Next AWG size', out.awg !== null ? `${awgLabel(out.awg)} AWG (drop ${(out.dropAwg! / out.v * 100).toFixed(2)} %)` : 'Over 4/0: use parallel runs'],
      ]} />
      <p className="hint">Voltage drop only. Check the current rating of the chosen cable against the code tables before using it.</p>
    </Form>
  );
}
