import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { solutionCategories, projects } from '../../data/content';
import { useReveal } from '../../lib/useReveal';
import { useSectionProgress } from '../../lib/useSectionProgress';
import { useInteraction } from '../../lib/InteractionContext';
import StatusBadge from '../ui/StatusBadge';

export default function DigitalSolutions() {
  const ref = useSectionProgress('solutions');
  useReveal(ref, []);
  const { solutionsCategory, setSolutionsCategory } = useInteraction();
  const reducedMotion = useReducedMotion();

  const visible = projects.filter((p) => p.category === solutionsCategory);

  return (
    <section id="solutions" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          Beyond Engineering
        </p>
        <h2 data-reveal className="text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1]">
          Beyond engineering.
        </h2>
        <p data-reveal className="mt-4 max-w-xl text-ink-1 text-base md:text-lg leading-relaxed">
          Digital systems for businesses outside engineering too.
        </p>

        <div data-reveal role="tablist" aria-label="Solution categories" className="mt-10 flex flex-wrap gap-3">
          {solutionCategories.map((cat) => (
            <motion.button
              key={cat.id}
              type="button"
              role="tab"
              aria-selected={solutionsCategory === cat.id}
              onClick={() => setSolutionsCategory(cat.id)}
              data-cursor="expand"
              whileHover={reducedMotion ? undefined : { scale: 1.04 }}
              whileTap={reducedMotion ? undefined : { scale: 0.97 }}
              className={`font-mono-label text-[0.68rem] px-4 py-2.5 rounded-full border transition-colors duration-300 ${
                solutionsCategory === cat.id
                  ? 'border-amber/60 bg-amber-dim text-amber'
                  : 'border-graphite-border text-ink-2 hover:text-ink-0 hover:border-graphite-600'
              }`}
            >
              {cat.label}
            </motion.button>
          ))}
        </div>

        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <AnimatePresence mode="popLayout" initial={false}>
            {visible.map((p, i) => (
              <motion.article
                key={p.id}
                layout={!reducedMotion}
                initial={reducedMotion ? false : { opacity: 0, y: 14, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={reducedMotion ? undefined : { opacity: 0, scale: 0.97 }}
                transition={{ duration: 0.35, delay: reducedMotion ? 0 : i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                whileHover={reducedMotion ? undefined : { y: -4, borderColor: 'rgba(77,216,230,0.4)' }}
                className="rounded-2xl border border-graphite-border bg-graphite-900/85 backdrop-blur-md p-6"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <h3 className="text-base font-semibold text-ink-0 leading-snug">{p.name}</h3>
                  <StatusBadge status={p.status} />
                </div>
                <p className="text-sm text-ink-2 leading-relaxed">{p.body}</p>
                <div className="flex flex-wrap gap-2 mt-4">
                  {p.stack.map((s) => (
                    <span key={s} className="font-mono-label text-[0.6rem] text-ink-2 bg-white/5 rounded px-2 py-1">
                      {s}
                    </span>
                  ))}
                </div>
              </motion.article>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
