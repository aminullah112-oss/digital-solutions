import { useState } from 'react';
import { evCircuit, kwToChargerAmps, chargeHours } from '../lib/calc/ev-charger';
import { minAreaMm2, nextAwg, nextIecSize } from '../lib/calc/conductor-drop';
import { awgLabel } from '../lib/calc/awg-to-mm2';
import { Form, Num, Out, Sel, run } from './ui';

export default function EvCharger() {
  const [by, setBy] = useState<'amps' | 'kw'>('amps');
  const [val, setVal] = useState('32');
  const [v, setV] = useState('240');
  const [len, setLen] = useState('20');
  const [drop, setDrop] = useState('3');
  const [kwh, setKwh] = useState('60');
  const { out, error } = run(() => {
    const amps = by === 'amps' ? Number(val) : kwToChargerAmps(Number(val), Number(v));
    const c = evCircuit(amps);
    const min = minAreaMm2({ amps, oneWayMetres: Number(len), volts: Number(v), maxDropPercent: Number(drop), material: 'copper', tempC: 30 });
    const kw = (amps * Number(v)) / 1000;
    return { c, min, iec: nextIecSize(min), awg: nextAwg(min), hours: chargeHours(Number(kwh), kw) };
  });
  return (
    <Form label="EV charger breaker and wire size calculator">
      <div className="grid">
        <Sel label="Charger rated by" value={by} set={setBy} options={[['amps', 'Amps'], ['kw', 'kW']]} />
        <Num label={by === 'amps' ? 'Charger current (A)' : 'Charger power (kW)'} value={val} set={setVal} />
        <Num label="Supply voltage (V)" value={v} set={setV} />
        <Num label="One-way cable length (m)" value={len} set={setLen} />
        <Num label="Allowed voltage drop (%)" value={drop} set={setDrop} />
        <Num label="Battery to add (kWh)" value={kwh} set={setKwh} />
      </div>
      <Out error={error} items={out && [
        ['Charger current', `${out.c.chargerAmps.toFixed(1)} A`],
        ['Breaker', `${out.c.breaker} A`],
        ['Conductor ampacity needed', `${out.c.minAmpacity.toFixed(1)} A or more`],
        ['Min area for voltage drop', `${out.min.toFixed(2)} mm² (copper)`],
        ['Voltage-drop size', `${out.iec ?? '>300'} mm² or ${out.awg !== null ? awgLabel(out.awg) + ' AWG' : '>4/0 AWG'}`],
        ['Charge time', `${out.hours.toFixed(1)} h`],
      ]} />
      <p className="hint">Pick the cable that meets both the ampacity and the voltage-drop result, using the current NEC or IEC tables.</p>
    </Form>
  );
}
