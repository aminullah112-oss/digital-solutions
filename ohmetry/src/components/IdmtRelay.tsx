import { useState } from 'react';
import { idmtTime, CURVES, type Curve } from '../lib/calc/idmt';
import { Form, Num, Out, Sel, run } from './ui';

export default function IdmtRelay() {
  const [curve, setCurve] = useState<Curve>('SI');
  const [tms, setTms] = useState('0.2');
  const [pickup, setPickup] = useState('100');
  const [fault, setFault] = useState('1000');
  const t = run(() => idmtTime(curve, Number(tms), Number(fault), Number(pickup)));
  const table = [2, 5, 10, 20].map((m) => `${m}×: ${run(() => idmtTime(curve, Number(tms), m * Number(pickup), Number(pickup))).out?.toFixed(3) ?? '–'} s`);
  return (
    <Form label="IDMT overcurrent relay time calculator">
      <div className="grid">
        <Sel label="Curve (IEC 60255-151)" value={curve} set={setCurve} options={(Object.keys(CURVES) as Curve[]).map((c) => [c, `${CURVES[c].name} (${c})`] as [Curve, string])} />
        <Num label="Time multiplier setting (TMS)" value={tms} set={setTms} />
        <Num label="Pickup current Is (A, primary)" value={pickup} set={setPickup} hint="Relay current setting × CT ratio" />
        <Num label="Fault current (A, primary)" value={fault} set={setFault} />
      </div>
      <Out error={t.error} items={t.out !== null ? [['Operating time', `${t.out.toFixed(3)} s`], ['Multiple of pickup', `${(Number(fault) / Number(pickup)).toFixed(2)} ×`]] : null} />
      <p className="hint">At this TMS: {table.join('  ·  ')}</p>
    </Form>
  );
}
