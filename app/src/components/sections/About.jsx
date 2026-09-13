import { useRef } from 'react';
import { about } from '../../data/content';
import { useReveal } from '../../lib/useReveal';

export default function About() {
  const ref = useRef(null);
  useReveal(ref);

  return (
    <section id="about" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          {about.kicker}
        </p>
        <h2 data-reveal className="max-w-3xl text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1]">
          {about.title}
        </h2>

        <div className="mt-14 grid lg:grid-cols-[1fr_1.15fr] gap-12 lg:gap-16 items-start">
          <div data-reveal className="rounded-2xl border border-graphite-border bg-graphite-900/60 backdrop-blur-sm p-8">
            <div className="w-14 h-14 rounded-xl bg-cyan-dim border border-cyan/30 flex items-center justify-center font-display text-xl text-cyan mb-6">
              A.
            </div>
            <h3 className="text-lg font-semibold text-ink-0">Aminullah</h3>
            <p className="text-ink-2 text-sm mt-1 mb-6">Protection & Automation Engineer / Digital Solutions Builder</p>
            <ul className="space-y-3">
              {about.credentials.map((c) => (
                <li key={c} className="flex gap-3 text-sm text-ink-1 leading-relaxed">
                  <span className="text-cyan mt-1 shrink-0">&#9679;</span>
                  {c}
                </li>
              ))}
            </ul>
          </div>

          <div data-reveal>
            <p className="text-ink-1 text-base md:text-lg leading-relaxed mb-10">{about.body}</p>

            {/* Two disciplines presented as one connected system, not two disconnected cards */}
            <div className="relative rounded-2xl border border-graphite-border bg-graphite-900/40 backdrop-blur-sm p-6 sm:p-8">
              <div className="grid sm:grid-cols-2 gap-6 sm:gap-0 relative">
                {about.tracks.map((track, i) => (
                  <div key={track.id} className={`relative ${i === 0 ? 'sm:pr-8 sm:border-r sm:border-graphite-border' : 'sm:pl-8'}`}>
                    <p className="font-mono-label text-[0.62rem] text-amber mb-2">
                      {i === 0 ? 'Physical World' : 'Digital World'}
                    </p>
                    <h4 className="text-xl font-semibold text-ink-0 mb-3">{track.title}</h4>
                    <p className="text-sm text-ink-2 leading-relaxed">{track.body}</p>
                  </div>
                ))}
                <div
                  aria-hidden="true"
                  className="hidden sm:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-graphite-900 border border-cyan/40 items-center justify-center z-10"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
