import { useRef } from 'react';
import { engineering } from '../../data/content';
import { useReveal } from '../../lib/useReveal';

const GROUP_LABELS = { domain: 'Domain', tool: 'Tools & Software', qms: 'Quality Systems' };

export default function Engineering() {
  const ref = useRef(null);
  useReveal(ref);

  const groups = ['domain', 'tool', 'qms'].map((g) => ({
    id: g,
    label: GROUP_LABELS[g],
    items: engineering.capabilities.filter((c) => c.group === g),
  }));

  return (
    <section id="engineering" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          {engineering.kicker}
        </p>
        <h2 data-reveal className="max-w-3xl text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1]">
          {engineering.title}
        </h2>
        <p data-reveal className="mt-5 max-w-xl text-ink-1 text-base md:text-lg leading-relaxed">
          {engineering.body}
        </p>

        <div className="mt-14 grid md:grid-cols-3 gap-6">
          {groups.map((group) => (
            <div
              key={group.id}
              data-reveal
              className="rounded-2xl border border-graphite-border bg-graphite-900/50 backdrop-blur-sm p-7"
            >
              <p className="font-mono-label text-[0.62rem] text-amber mb-5">{group.label}</p>
              <ul className="space-y-3">
                {group.items.map((item) => (
                  <li key={item.label} className="flex items-center gap-3 text-sm text-ink-1">
                    <span className="w-1 h-1 rounded-full bg-cyan shrink-0" />
                    {item.label}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
