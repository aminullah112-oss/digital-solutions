import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { sceneState } from '../../lib/sceneState';

// Triangular falloff: 1 at the section's midpoint, 0 once you're a full section away.
function sectionWeight(id) {
  const p = sceneState.sectionProgress[id];
  if (p === undefined) return 0;
  return Math.max(0, 1 - Math.abs(p - 0.5) * 2.2);
}

// The hero's "digital engineering core" — nested wireframe icosahedra plus a couple
// of thin holographic rings. Persists for the whole page at low opacity, and comes
// forward again (fuller, slightly faster) for the closing CTA — the "more complete
// system" callback the brief asks for, achieved with intensity, not new geometry.
export default function EngineeringCore({ quality = 'high' }) {
  const group = useRef(null);
  const core = useRef(null);
  const shell = useRef(null);
  const ringA = useRef(null);
  const ringB = useRef(null);
  const mouseOffset = useRef({ x: 0, y: 0 });

  const detail = quality === 'low' ? 0 : 1;

  const coreGeo = useMemo(() => new THREE.IcosahedronGeometry(1.55, detail), [detail]);
  const shellGeo = useMemo(() => new THREE.IcosahedronGeometry(2.25, 0), []);
  const ringGeoA = useMemo(() => new THREE.TorusGeometry(3.1, 0.012, 8, 96), []);
  const ringGeoB = useMemo(() => new THREE.TorusGeometry(3.55, 0.008, 8, 96), []);

  useFrame((state, delta) => {
    if (!group.current) return;

    const strength = Math.max(0, sectionWeight('hero'), sectionWeight('cta') * 1.15);
    const cappedStrength = Math.min(1, strength);
    // Ambient floor is a small FRACTION of full intensity, not a flat additive amount —
    // otherwise the core stays almost as visible behind every section as it is in the
    // hero, competing with card content instead of receding into the background.
    const intensity = THREE.MathUtils.lerp(0.07, 1, cappedStrength);
    const t = state.clock.elapsedTime;

    group.current.rotation.y += delta * 0.09;
    group.current.rotation.x = Math.sin(t * 0.15) * 0.08;

    mouseOffset.current.x = THREE.MathUtils.lerp(mouseOffset.current.x, sceneState.mouse.x, 0.02);
    mouseOffset.current.y = THREE.MathUtils.lerp(mouseOffset.current.y, sceneState.mouse.y, 0.02);
    group.current.rotation.z = mouseOffset.current.x * 0.06;

    const qualityScale = quality === 'low' ? 0.72 : 1;
    const scale = (0.78 + cappedStrength * 0.36) * qualityScale;
    group.current.scale.setScalar(scale);

    if (core.current) {
      core.current.material.opacity = 0.6 * intensity;
      core.current.rotation.y -= delta * 0.05;
    }
    if (shell.current) {
      shell.current.material.opacity = 0.18 * intensity;
      shell.current.rotation.y += delta * 0.03;
      shell.current.rotation.x += delta * 0.015;
    }
    if (ringA.current) {
      ringA.current.material.opacity = 0.22 * intensity;
      ringA.current.rotation.z += delta * 0.06;
    }
    if (ringB.current) {
      ringB.current.material.opacity = 0.14 * intensity;
      ringB.current.rotation.x += delta * 0.045;
      ringB.current.rotation.z -= delta * 0.03;
    }
  });

  return (
    <group ref={group} position={[0, 0, 0]}>
      <mesh ref={core} geometry={coreGeo}>
        <meshBasicMaterial color="#4dd8e6" wireframe transparent opacity={0.6} />
      </mesh>
      <mesh ref={shell} geometry={shellGeo}>
        <meshBasicMaterial color="#8be9f2" wireframe transparent opacity={0.18} />
      </mesh>
      <mesh ref={ringA} geometry={ringGeoA} rotation={[Math.PI / 2.3, 0, 0]}>
        <meshBasicMaterial color="#4dd8e6" transparent opacity={0.22} />
      </mesh>
      <mesh ref={ringB} geometry={ringGeoB} rotation={[Math.PI / 1.7, 0.3, 0]}>
        <meshBasicMaterial color="#e8a662" transparent opacity={0.14} />
      </mesh>
    </group>
  );
}
