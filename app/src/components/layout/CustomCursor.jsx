import { useEffect, useRef } from 'react';
import { gsap } from '../../lib/gsapSetup';
import { useIsTouch, useReducedMotion } from '../../lib/useMediaQuery';
import { useInteraction } from '../../lib/InteractionContext';

export default function CustomCursor() {
  const dotRef = useRef(null);
  const ringRef = useRef(null);
  const isTouch = useIsTouch();
  const reducedMotion = useReducedMotion();
  const { protectionGridActive, expertiseActive } = useInteraction();
  const active = isTouch || reducedMotion;

  useEffect(() => {
    // Don't hide the real system cursor until we've actually seen mouse movement —
    // a keyboard-only visitor (or one who simply hasn't touched the mouse yet) should
    // never lose their cursor to a decorative dot that's still sitting at (0,0).
    if (active) return undefined;
    const onFirstMove = () => document.documentElement.classList.add('has-custom-cursor');
    window.addEventListener('pointermove', onFirstMove, { once: true });
    return () => {
      window.removeEventListener('pointermove', onFirstMove);
      document.documentElement.classList.remove('has-custom-cursor');
    };
  }, [active]);

  useEffect(() => {
    if (active) return undefined;
    const dot = dotRef.current;
    const ring = ringRef.current;
    if (!dot || !ring) return undefined;

    const moveDot = gsap.quickTo(dot, 'x', { duration: 0.05 });
    const moveDotY = gsap.quickTo(dot, 'y', { duration: 0.05 });
    const moveRing = gsap.quickTo(ring, 'x', { duration: 0.35, ease: 'power3.out' });
    const moveRingY = gsap.quickTo(ring, 'y', { duration: 0.35, ease: 'power3.out' });

    const onMove = (e) => {
      moveDot(e.clientX);
      moveDotY(e.clientY);
      moveRing(e.clientX);
      moveRingY(e.clientY);
    };
    window.addEventListener('pointermove', onMove, { passive: true });

    const onOver = (e) => {
      const target = e.target.closest?.('[data-cursor]');
      ring.dataset.state = target ? target.dataset.cursor : '';
    };
    document.addEventListener('pointerover', onOver);

    return () => {
      window.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerover', onOver);
    };
  }, [active]);

  if (active) return null;

  const hovering3D = Boolean(protectionGridActive || expertiseActive);

  return (
    <>
      <div
        ref={dotRef}
        aria-hidden="true"
        className="fixed top-0 left-0 z-[70] w-1.5 h-1.5 rounded-full bg-cyan -translate-x-1/2 -translate-y-1/2 pointer-events-none"
      />
      <div
        ref={ringRef}
        aria-hidden="true"
        data-hover3d={hovering3D || undefined}
        className="cursor-ring fixed top-0 left-0 z-[70] w-8 h-8 rounded-full border border-cyan/70 -translate-x-1/2 -translate-y-1/2 pointer-events-none transition-[width,height,border-color,background-color] duration-200 ease-out data-[state=expand]:w-14 data-[state=expand]:h-14 data-[state=expand]:bg-cyan/10 data-[hover3d]:w-16 data-[hover3d]:h-16 data-[hover3d]:border-amber data-[hover3d]:bg-amber/10"
      />
    </>
  );
}
