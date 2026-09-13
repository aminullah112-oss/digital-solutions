import { useRef } from 'react';
import { protectionGrid } from '../../data/content';
import { useReveal } from '../../lib/useReveal';
import StatusBadge from '../ui/StatusBadge';

// The tangible, get-it-today items from the ProtectionGrid line — shown in the
// ecosystem view above, but framed here as concrete, purchasable/downloadable products.
const SHOWCASE_IDS = ['estimation-tool', 'atp-fat-pack', 'commissioning-toolkit'];

export default function Products() {
  const ref = useRef(null);
  useReveal(ref);
  const items = SHOWCASE_IDS.map((id) => protectionGrid.products.find((p) => p.id === id)).filter(Boolean);

  return (
    <section id="products" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          Product Showroom
        </p>
        <h2 data-reveal className="text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1] max-w-2xl">
          Tools you can put to work today.
        </h2>

        <div className="mt-14 space-y-5">
          {items.map((p, i) => (
            <article
              key={p.id}
              data-reveal
              className="group relative rounded-2xl border border-graphite-border bg-graphite-900/50 backdrop-blur-sm p-7 md:p-10 grid md:grid-cols-[auto_1fr_auto] items-center gap-6 transition-all duration-500 ease-engineered hover:border-cyan/40 hover:-translate-y-1"
            >
              <span className="font-display text-4xl md:text-5xl text-graphite-600 group-hover:text-cyan/40 transition-colors duration-500">
                {String(i + 1).padStart(2, '0')}
              </span>

              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-xl md:text-2xl font-semibold text-ink-0">{p.name}</h3>
                  <StatusBadge status={p.status} />
                </div>
                <p className="text-sm md:text-base text-ink-2 leading-relaxed max-w-xl">{p.body}</p>
              </div>

              <a
                href="#"
                data-cursor="expand"
                className="font-mono-label text-[0.68rem] text-ink-0 border border-graphite-border rounded-full px-5 py-3 whitespace-nowrap justify-self-start md:justify-self-end group-hover:border-cyan group-hover:text-cyan transition-colors duration-300"
              >
                View Details &rarr;
              </a>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
