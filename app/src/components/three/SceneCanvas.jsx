import { useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import Scene from './Scene';
import SceneFallback from './SceneFallback';
import { hasWebGL } from '../../lib/webgl';
import { useReducedMotion, useIsMobile, useIsTablet } from '../../lib/useMediaQuery';
import { sceneState } from '../../lib/sceneState';

/**
 * The single persistent 3D canvas for the whole page. Decides up front whether to
 * render WebGL at all (capability + reduced-motion check), defers mounting until
 * after first paint so it never blocks initial content, and pauses its render loop
 * when the tab isn't visible.
 */
export default function SceneCanvas() {
  const reducedMotion = useReducedMotion();
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const [ready, setReady] = useState(false);
  const [tabVisible, setTabVisible] = useState(true);
  const [webglOk] = useState(() => hasWebGL());

  useEffect(() => {
    sceneState.reducedMotion = reducedMotion;
  }, [reducedMotion]);

  useEffect(() => {
    const idle = window.requestIdleCallback || ((cb) => setTimeout(cb, 150));
    const cancel = window.cancelIdleCallback || clearTimeout;
    const id = idle(() => setReady(true));
    return () => cancel(id);
  }, []);

  useEffect(() => {
    const onVis = () => setTabVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

  if (!webglOk || reducedMotion) {
    return <SceneFallback />;
  }

  if (!ready) {
    return <SceneFallback />;
  }

  const quality = isMobile ? 'low' : isTablet ? 'mid' : 'high';
  const particleCount = isMobile ? 60 : isTablet ? 130 : 220;
  const dprCap = isMobile ? 1.5 : 2;

  return (
    <div className="scene-host">
      <Canvas
        camera={{ position: [0, 0, 9], fov: 45, near: 0.1, far: 60 }}
        dpr={[1, dprCap]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        frameloop={tabVisible ? 'always' : 'never'}
        onCreated={({ gl }) => gl.setClearColor(0x000000, 0)}
      >
        <Scene quality={quality} particleCount={particleCount} />
      </Canvas>
    </div>
  );
}
