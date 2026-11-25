import { useState } from 'react';
import { batterySize, batteryRuntimeHours } from '../lib/calc/battery';
import { Form, Num, Out, Sel, run } from './ui';

export default function BatteryBank() {
  const [mode, setMode] = useState<'size' | 'runtime'>('size');
  const [wh, setWh] = useState('5000');
  const [days, setDays] = useState('2');
  const [dod, setDod] = useState('0.5');
  const [v, setV] = useState('48');
  const [eff, setEff] = useState('0.9');
  const [ah, setAh] = useState('200');
  const [load, setLoad] = useState('1000');
  const size = run(() => batterySize(Number(wh), Number(days), Number(dod), Number(v), Number(eff)));
  const rt = run(() => batteryRuntimeHours(Number(ah), Number(v), Number(dod), Number(eff), Number(load)));
  return (
    <Form label="Battery bank size and runtime calculator">
      <div className="grid">
        <Sel label="Calculate" value={mode} set={setMode} options={[['size', 'Battery size needed'], ['runtime', 'Runtime of a battery']]} />
        {mode === 'size'
          ? <><Num label="Daily load (Wh)" value={wh} set={setWh} /><Num label="Days of autonomy" value={days} set={setDays} /></>
          : <><Num label="Battery capacity (Ah)" value={ah} set={setAh} /><Num label="Load (W)" value={load} set={setLoad} /></>}
        <Num label="Battery voltage (V)" value={v} set={setV} hint="12, 24 or 48" />
        <Num label="Usable depth of discharge" value={dod} set={setDod} hint="Lead-acid ~0.5, LiFePO4 ~0.8 to 0.9. Check the datasheet." />
        <Num label="Inverter efficiency" value={eff} set={setEff} />
      </div>
      {mode === 'size'
        ? <Out error={size.error} items={size.out && [
            ['Capacity', `${size.out.ah.toFixed(0)} Ah at ${Number(v)} V`],
            ['Nominal energy', `${size.out.kwhNominal.toFixed(1)} kWh`],
            ['Usable energy', `${size.out.kwhUsable.toFixed(1)} kWh`],
          ]} />
        : <Out error={rt.error} items={rt.out !== null ? [['Runtime', `${rt.out.toFixed(1)} h`]] : null} />}
    </Form>
  );
}
