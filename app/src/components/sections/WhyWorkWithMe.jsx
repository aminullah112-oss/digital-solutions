import { useRef } from 'react';
import { process } from '../../data/content';
import { useReveal } from '../../lib/useReveal';

export default function WhyWorkWithMe() {
  const ref = useRef(null);
  useReveal(ref);

  return (
    <section ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          {process.kicker}
        </p>
        <h2 data-reveal className="max-w-2xl text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1]">
          {process.title}
        </h2>

        <div className="mt-16 relative">
          <div
            aria-hidden="true"
            className="hidden md:block absolute top-5 left-0 right-0 h-px bg-gradient-to-r from-graphite-border via-cyan/30 to-graphite-border"
          />
          <div className="grid md:grid-cols-4 gap-8 md:gap-6">
            {process.steps.map((step) => (
              <div key={step.n} data-reveal className="relative">
                <div className="hidden md:flex w-2.5 h-2.5 rounded-full bg-cyan mb-8 relative z-10 ring-4 ring-graphite-950" />
                <p className="font-mono-label text-cyan text-xs mb-3">{step.n}</p>
                <h3 className="text-lg font-semibold text-ink-0 mb-2">{step.title}</h3>
                <p className="text-sm text-ink-2 leading-relaxed">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
