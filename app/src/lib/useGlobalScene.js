import { useEffect } from 'react';
import { ScrollTrigger } from './gsapSetup';
import { sceneState } from './sceneState';

// Wires the two inputs the whole 3D layer reads every frame: normalized pointer
// position and whole-page scroll progress. Mounted once near the app root.
export function useGlobalScene({ enabled }) {
  useEffect(() => {
    if (!enabled) return undefined;

    const onMove = (e) => {
      sceneState.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      sceneState.mouse.y = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener('pointermove', onMove, { passive: true });

    const trigger = ScrollTrigger.create({
      trigger: document.body,
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (self) => {
        sceneState.scrollProgress = self.progress;
      },
    });

    return () => {
      window.removeEventListener('pointermove', onMove);
      trigger.kill();
    };
  }, [enabled]);
}
