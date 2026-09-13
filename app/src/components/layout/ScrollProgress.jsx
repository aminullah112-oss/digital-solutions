import { useEffect, useRef } from 'react';
import { ScrollTrigger } from '../../lib/gsapSetup';

export default function ScrollProgress() {
  const barRef = useRef(null);

  useEffect(() => {
    const trigger = ScrollTrigger.create({
      trigger: document.body,
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (self) => {
        if (barRef.current) barRef.current.style.transform = `scaleX(${self.progress})`;
      },
    });
    return () => trigger.kill();
  }, []);

  return (
    <div className="fixed top-0 inset-x-0 z-50 h-[2px] bg-transparent" aria-hidden="true">
      <div
        ref={barRef}
        className="h-full origin-left bg-gradient-to-r from-cyan to-amber"
        style={{ transform: 'scaleX(0)' }}
      />
    </div>
  );
}
