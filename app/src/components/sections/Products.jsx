import { motion } from 'framer-motion';
import { solutionCategories } from '../../data/content';
import { useReveal } from '../../lib/useReveal';
import { useSectionProgress } from '../../lib/useSectionProgress';
import { useInteraction } from '../../lib/InteractionContext';
import { useReducedMotion } from '../../lib/useMediaQuery';
import { scrollToSelector } from '../../lib/scroll';
import MagneticButton from '../ui/MagneticButton';

export default function Products() {
  const ref = useSectionProgress('products');
  useReveal(ref);
  const { setContactInterest, servicesActive, setServicesActive } = useInteraction();
  const reducedMotion = useReducedMotion();

  const handleStart = (label) => {
    setContactInterest(label);
    scrollToSelector('#contact');
  };

  return (
    <section id="products" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          Services
        </p>
        <h2 data-reveal className="text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1] max-w-2xl">
          What I build for clients.
        </h2>
        <p data-reveal className="mt-5 max-w-xl text-ink-1 text-base md:text-lg leading-relaxed">
          Four kinds of work, all shipped the same way: fast, documented, and built around what's actually slowing your business down.
        </p>

        <div className="mt-14 grid md:grid-cols-2 gap-5">
          {solutionCategories.map((cat, i) => (
            <article
              key={cat.id}
              data-reveal
              onMouseEnter={() => setServicesActive(cat.id)}
              onMouseLeave={() => setServicesActive((cur) => (cur === cat.id ? null : cur))}
              onFocus={() => setServicesActive(cat.id)}
              onBlur={() => setServicesActive((cur) => (cur === cat.id ? null : cur))}
              className={`group rounded-2xl border backdrop-blur-sm p-7 md:p-8 transition-colors duration-500 ${
                servicesActive === cat.id
                  ? 'border-cyan/50 bg-graphite-900/80'
                  : 'border-graphite-border bg-graphite-900/60 hover:border-cyan/40'
              }`}
            >
              <span className="font-display text-3xl text-graphite-600 group-hover:text-cyan/40 transition-colors duration-500">
                {String(i + 1).padStart(2, '0')}
              </span>
              <h3 className="text-xl font-semibold text-ink-0 mt-4 mb-3">{cat.label}</h3>
              <p className="text-sm md:text-base text-ink-2 leading-relaxed mb-5">{cat.pitch}</p>
              <ul className="space-y-2 mb-7">
                {cat.deliverables.map((d) => (
                  <li key={d} className="flex gap-2.5 text-sm text-ink-1">
                    <span className="text-violet mt-1 shrink-0">&#9679;</span>
                    {d}
                  </li>
                ))}
              </ul>
              <motion.button
                type="button"
                data-cursor="expand"
                onClick={() => handleStart(cat.label)}
                whileTap={reducedMotion ? undefined : { scale: 0.97 }}
                className="font-mono-label text-[0.68rem] text-ink-0 border border-graphite-border rounded-full px-5 py-3 hover:border-cyan hover:text-cyan transition-colors duration-300"
              >
                Start a Project &rarr;
              </motion.button>
            </article>
          ))}
        </div>

        <div data-reveal className="mt-10 text-center">
          <MagneticButton
            href="#contact"
            onClick={(e) => {
              e.preventDefault();
              scrollToSelector('#contact');
            }}
            className="font-mono-label text-xs text-graphite-950 bg-cyan px-7 py-4 rounded-full inline-block hover:brightness-110 transition-[filter] duration-300"
          >
            Not Sure Which One? Tell Me What's Slow
          </MagneticButton>
        </div>
      </div>
    </section>
  );
}
