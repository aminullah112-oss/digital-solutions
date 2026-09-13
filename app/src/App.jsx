import { lazy, Suspense } from 'react';
import { InteractionProvider } from './lib/InteractionContext';
import { useLenis } from './lib/useLenis';
import { useGlobalScene } from './lib/useGlobalScene';
import { useIsTouch, useReducedMotion } from './lib/useMediaQuery';

import Navbar from './components/layout/Navbar';
import ScrollProgress from './components/layout/ScrollProgress';
import CustomCursor from './components/layout/CustomCursor';
import Footer from './components/layout/Footer';

import Hero from './components/sections/Hero';
import About from './components/sections/About';
import Products from './components/sections/Products';
import DigitalSolutions from './components/sections/DigitalSolutions';
import Expertise from './components/sections/Expertise';
import WhyWorkWithMe from './components/sections/WhyWorkWithMe';
import CTA from './components/sections/CTA';
import Contact from './components/sections/Contact';
import SceneFallback from './components/three/SceneFallback';

// The whole three.js/R3F/drei/gsap-for-3D stack lives behind this dynamic import so it
// never lands in the critical bundle that blocks first paint of the actual page content.
const SceneCanvas = lazy(() => import('./components/three/SceneCanvas'));

function AppShell() {
  const isTouch = useIsTouch();
  const reducedMotion = useReducedMotion();

  useLenis(!isTouch && !reducedMotion);
  useGlobalScene({ enabled: !reducedMotion });

  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Suspense fallback={<SceneFallback />}>
        <SceneCanvas />
      </Suspense>
      <div className="page-content">
        <ScrollProgress />
        <CustomCursor />
        <Navbar />
        <main id="main">
          <Hero />
          <About />
          <Products />
          <DigitalSolutions />
          <Expertise />
          <WhyWorkWithMe />
          <CTA />
          <Contact />
        </main>
        <Footer />
      </div>
    </>
  );
}

export default function App() {
  return (
    <InteractionProvider>
      <AppShell />
    </InteractionProvider>
  );
}
