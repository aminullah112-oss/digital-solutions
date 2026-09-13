import { statusTone } from '../../data/content';

const TONE_CLASSES = {
  live: 'text-[#4ade80] border-[#4ade80]/35 bg-[#4ade80]/10',
  delivered: 'text-cyan border-cyan/35 bg-cyan-dim',
  prototype: 'text-ink-2 border-ink-2/30 bg-white/5',
};

export default function StatusBadge({ status }) {
  const tone = statusTone[status] || 'prototype';
  return (
    <span
      className={`font-mono-label inline-flex items-center rounded-full border px-2.5 py-1 text-[0.62rem] whitespace-nowrap ${TONE_CLASSES[tone]}`}
    >
      {status}
    </span>
  );
}
