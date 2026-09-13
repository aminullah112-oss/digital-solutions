import { getLenis } from './useLenis';

export function scrollToSelector(selector) {
  const el = document.querySelector(selector);
  if (!el) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const lenis = getLenis();
  if (lenis) {
    lenis.scrollTo(el, { offset: -84, duration: reduced ? 0 : 1.1 });
  } else {
    el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
  }
}
