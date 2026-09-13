import { useEffect, useRef } from 'react';
import { ScrollTrigger } from './gsapSetup';
import { sceneState, setSectionProgress } from './sceneState';

// Attaches a ScrollTrigger to a section element that (a) records 0..1 local scroll
// progress into sceneState for the 3D layer to read, and (b) flags the section as
// "active" (drives which persistent 3D group is faded in) once it's substantially
// in view.
export function useSectionProgress(id) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;

    setSectionProgress(id, 0);

    const trigger = ScrollTrigger.create({
      trigger: el,
      start: 'top bottom',
      end: 'bottom top',
      onUpdate: (self) => setSectionProgress(id, self.progress),
      onToggle: (self) => {
        if (self.isActive) sceneState.activeSection = id;
      },
    });

    return () => {
      trigger.kill();
      delete sceneState.sectionProgress[id];
    };
  }, [id]);

  return ref;
}
