import { hero } from '../../data/content';
import { useReveal } from '../../lib/useReveal';
import { useSectionProgress } from '../../lib/useSectionProgress';
import { scrollToSelector } from '../../lib/scroll';
import MagneticButton from '../ui/MagneticButton';
import CountUp from '../ui/CountUp';

export default function Hero() {
  const ref = useSectionProgress('hero');
  useReveal(ref);

  return (
    <section id="home" ref={ref} className="relative min-h-[100svh] flex items-center pt-24 pb-16">
      <div className="max-w-content w-full mx-auto px-5 sm:px-8">
        <div
          data-reveal
          className="font-mono-label inline-flex items-center gap-2 text-[0.65rem] text-cyan border border-cyan/25 bg-cyan-dim rounded-full px-3 py-1.5 mb-8"
        >
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan opacity-60" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan" />
          </span>
          System Status &mdash; Digital Solutions Online
        </div>

        <h1
          data-reveal
          className="max-w-4xl text-[2.4rem] leading-[1.08] sm:text-6xl md:text-[4.2rem] md:leading-[1.04] font-semibold text-ink-0"
        >
          I build digital products that solve real problems.
        </h1>

        <p data-reveal className="mt-7 max-w-xl text-ink-1 text-base md:text-lg leading-relaxed">
          {hero.sub}
        </p>

        <div data-reveal className="mt-9 flex flex-wrap items-center gap-4">
          <MagneticButton
            href="#solutions"
            onClick={(e) => {
              e.preventDefault();
              scrollToSelector('#solutions');
            }}
            className="font-mono-label text-xs text-graphite-950 bg-cyan px-7 py-4 rounded-full inline-block hover:brightness-110 transition-[filter] duration-300"
          >
            Explore My Work
          </MagneticButton>
          <MagneticButton
            href="#contact"
            onClick={(e) => {
              e.preventDefault();
              scrollToSelector('#contact');
            }}
            className="font-mono-label text-xs text-ink-0 border border-graphite-border px-7 py-4 rounded-full inline-block hover:border-cyan/50 hover:text-cyan transition-colors duration-300"
          >
            Start a Project
          </MagneticButton>
        </div>

        <dl data-reveal className="mt-16 flex flex-wrap gap-x-12 gap-y-6">
          {hero.stats.map((s) => (
            <div key={s.label}>
              <dt className="sr-only">{s.label}</dt>
              <dd className="font-display text-3xl sm:text-4xl font-semibold text-ink-0">
                <CountUp value={s.value} suffix={s.suffix} />
              </dd>
              <dd className="font-mono-label text-[0.62rem] text-ink-2 mt-1">{s.label}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div
        aria-hidden="true"
        className="hidden md:block absolute top-[26%] right-[6%] font-mono-label text-[0.6rem] text-ink-3 text-right leading-relaxed"
      >
        <p>ENGINEERING_CORE // ACTIVE</p>
        <p>LAT 13.08&deg;N &middot; LON 80.27&deg;E</p>
      </div>
    </section>
  );
}
