import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { sceneState } from '../../lib/sceneState';

// Restrained camera drift: a small mouse-parallax offset, plus a gentle dolly/rotate
// tied to overall page scroll progress. Both are damped so the motion reads as
// "breathing", not tracking.
const KEYFRAMES = [
  { p: 0, pos: [0, 0, 9], look: [0, 0, 0] },
  { p: 0.35, pos: [1.4, -0.6, 7.5], look: [0.4, -0.2, 0] },
  { p: 0.65, pos: [-1.2, 0.4, 8], look: [-0.3, 0.1, 0] },
  { p: 1, pos: [0, -0.3, 9.5], look: [0, 0, 0] },
];

function lerpKeyframes(progress) {
  let a = KEYFRAMES[0];
  let b = KEYFRAMES[KEYFRAMES.length - 1];
  for (let i = 0; i < KEYFRAMES.length - 1; i++) {
    if (progress >= KEYFRAMES[i].p && progress <= KEYFRAMES[i + 1].p) {
      a = KEYFRAMES[i];
      b = KEYFRAMES[i + 1];
      break;
    }
  }
  const span = b.p - a.p || 1;
  const t = Math.min(1, Math.max(0, (progress - a.p) / span));
  return {
    pos: a.pos.map((v, i) => THREE.MathUtils.lerp(v, b.pos[i], t)),
    look: a.look.map((v, i) => THREE.MathUtils.lerp(v, b.look[i], t)),
  };
}

export default function CameraRig({ intensity = 1 }) {
  const { camera } = useThree();
  const target = new THREE.Vector3();

  useFrame((_, delta) => {
    const { pos, look } = lerpKeyframes(sceneState.scrollProgress);
    const mouseX = sceneState.mouse.x * 0.4 * intensity;
    const mouseY = sceneState.mouse.y * -0.25 * intensity;

    const damp = 1 - Math.pow(0.001, delta);
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, pos[0] + mouseX, damp);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, pos[1] + mouseY, damp);
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, pos[2], damp);

    target.set(look[0], look[1], look[2]);
    camera.lookAt(target);
  });

  return null;
}
