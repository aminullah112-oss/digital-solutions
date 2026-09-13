import { useEffect } from 'react';
import Lenis from 'lenis';
import { gsap, ScrollTrigger } from './gsapSetup';

// Module-level so lib/scroll.js can drive the same instance for nav-link clicks
// without threading it through props/context.
let activeLenis = null;
export function getLenis() {
  return activeLenis;
}

// Smooth scroll is a desktop-only, motion-safe enhancement. Touch devices keep native
// momentum scroll (fighting it tends to feel worse, not better), and reduced-motion
// visitors get plain scroll behavior.
export function useLenis(enabled) {
  useEffect(() => {
    if (!enabled) return undefined;

    const lenis = new Lenis({
      duration: 1.05,
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 0,
      syncTouch: false,
    });
    activeLenis = lenis;

    lenis.on('scroll', ScrollTrigger.update);

    const raf = (time) => lenis.raf(time * 1000);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(raf);
      lenis.destroy();
      activeLenis = null;
    };
  }, [enabled]);
}
