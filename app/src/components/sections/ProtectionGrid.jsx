import { useEffect } from 'react';
import { protectionGrid } from '../../data/content';
import { useReveal } from '../../lib/useReveal';
import { useSectionProgress } from '../../lib/useSectionProgress';
import { useInteraction } from '../../lib/InteractionContext';
import StatusBadge from '../ui/StatusBadge';

export default function ProtectionGrid() {
  const ref = useSectionProgress('protectiongrid');
  useReveal(ref);
  const { protectionGridActive, setProtectionGridActive } = useInteraction();

  useEffect(() => () => setProtectionGridActive(null), [setProtectionGridActive]);

  return (
    <section id="protectiongrid" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          {protectionGrid.kicker}
        </p>
        <h2 data-reveal className="text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1]">
          {protectionGrid.title}
        </h2>
        <p data-reveal className="mt-4 max-w-xl text-amber text-base md:text-lg">{protectionGrid.subtitle}</p>
        <p data-reveal className="mt-4 max-w-2xl text-ink-1 leading-relaxed">{protectionGrid.body}</p>

        <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {protectionGrid.products.map((p) => (
            <button
              key={p.id}
              type="button"
              data-reveal
              data-cursor="expand"
              onMouseEnter={() => setProtectionGridActive(p.id)}
              onMouseLeave={() => setProtectionGridActive((cur) => (cur === p.id ? null : cur))}
              onFocus={() => setProtectionGridActive(p.id)}
              onBlur={() => setProtectionGridActive((cur) => (cur === p.id ? null : cur))}
              className={`text-left rounded-2xl border p-6 backdrop-blur-md transition-all duration-300 ${
                protectionGridActive === p.id
                  ? 'border-cyan/60 bg-graphite-900/90 shadow-[0_0_40px_-12px_rgba(77,216,230,0.45)]'
                  : 'border-graphite-border bg-graphite-900/85 hover:border-graphite-600'
              }`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <h3 className="text-base font-semibold text-ink-0 leading-snug">{p.name}</h3>
                <StatusBadge status={p.status} />
              </div>
              {p.meta && <p className="font-mono-label text-[0.6rem] text-ink-3 mb-2">{p.meta}</p>}
              <p className="text-sm text-ink-2 leading-relaxed">{p.body}</p>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
