import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { nav } from '../../data/content';

const listVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.08 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] } },
};

export default function MobileMenu({ open, onNavigate }) {
  const reducedMotion = useReducedMotion();

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={reducedMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={reducedMotion ? undefined : { opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-30 bg-graphite-950/98 backdrop-blur-xl lg:hidden"
        >
          <motion.div
            variants={reducedMotion ? undefined : listVariants}
            initial="hidden"
            animate="visible"
            className="h-full flex flex-col justify-center px-8"
          >
            <ul className="space-y-1">
              {nav.map((item) => (
                <motion.li key={item.href} variants={reducedMotion ? undefined : itemVariants}>
                  <a
                    href={item.href}
                    onClick={(e) => onNavigate(e, item.href)}
                    className="flex items-baseline gap-4 py-3 text-3xl font-display font-semibold text-ink-0"
                  >
                    <span className="font-mono-label text-sm text-cyan">{item.n}</span>
                    {item.label}
                  </a>
                </motion.li>
              ))}
            </ul>
            <motion.a
              variants={reducedMotion ? undefined : itemVariants}
              href="#contact"
              onClick={(e) => onNavigate(e, '#contact')}
              whileTap={reducedMotion ? undefined : { scale: 0.96 }}
              className="font-mono-label text-xs text-graphite-950 bg-cyan px-6 py-4 rounded-full inline-block mt-8 w-fit"
            >
              Start a Project
            </motion.a>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
