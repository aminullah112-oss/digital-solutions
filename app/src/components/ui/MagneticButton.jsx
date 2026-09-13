import { useEffect, useRef } from 'react';
import { gsap } from '../../lib/gsapSetup';
import { useIsTouch, useReducedMotion } from '../../lib/useMediaQuery';

const STRENGTH = 0.35;

export default function MagneticButton({ as: Tag = 'a', className = '', children, ...props }) {
  const ref = useRef(null);
  const isTouch = useIsTouch();
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || isTouch || reducedMotion) return undefined;

    const moveX = gsap.quickTo(el, 'x', { duration: 0.5, ease: 'power3.out' });
    const moveY = gsap.quickTo(el, 'y', { duration: 0.5, ease: 'power3.out' });

    const onMove = (e) => {
      const rect = el.getBoundingClientRect();
      const relX = e.clientX - (rect.left + rect.width / 2);
      const relY = e.clientY - (rect.top + rect.height / 2);
      moveX(relX * STRENGTH);
      moveY(relY * STRENGTH);
    };
    const onLeave = () => {
      moveX(0);
      moveY(0);
    };

    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
    return () => {
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [isTouch, reducedMotion]);

  return (
    <Tag ref={ref} className={className} data-cursor="expand" {...props}>
      {children}
    </Tag>
  );
}
