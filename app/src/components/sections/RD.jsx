import { useRef } from 'react';
import { rd } from '../../data/content';
import { useReveal } from '../../lib/useReveal';

export default function RD() {
  const ref = useRef(null);
  useReveal(ref);

  return (
    <section ref={ref} className="relative py-16 md:py-20">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <div data-reveal className="rounded-2xl border border-dashed border-graphite-border p-8 md:p-10">
          <h3 className="font-mono-label text-[0.65rem] text-ink-2 mb-6">&#128300; {rd.title}</h3>
          <div className="grid md:grid-cols-3 gap-6">
            {rd.items.map((item) => (
              <div key={item.title}>
                <p className="text-sm font-semibold text-ink-0 mb-1.5">{item.title}</p>
                <p className="text-sm text-ink-3 leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
          <p className="font-mono-label text-[0.6rem] text-ink-3 mt-7 pt-6 border-t border-graphite-border">
            {rd.note}
          </p>
        </div>
      </div>
    </section>
  );
}
