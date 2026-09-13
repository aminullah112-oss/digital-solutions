import { useEffect } from 'react';
import { gsap, ScrollTrigger } from './gsapSetup';

// Batched scroll-reveal for any [data-reveal] descendants of the given ref.
// Respects prefers-reduced-motion by skipping straight to the visible end-state.
export function useReveal(ref, deps = []) {
  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;

    const targets = root.querySelectorAll('[data-reveal]');
    if (!targets.length) return undefined;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      gsap.set(targets, { opacity: 1, y: 0, filter: 'blur(0px)' });
      return undefined;
    }

    gsap.set(targets, { opacity: 0, y: 28, filter: 'blur(6px)' });

    const triggers = Array.from(targets).map((el, i) =>
      ScrollTrigger.create({
        trigger: el,
        start: 'top 88%',
        onEnter: () =>
          gsap.to(el, {
            opacity: 1,
            y: 0,
            filter: 'blur(0px)',
            duration: 0.9,
            delay: (i % 4) * 0.06,
            ease: 'power3.out',
          }),
        once: true,
      })
    );

    return () => triggers.forEach((t) => t.kill());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
