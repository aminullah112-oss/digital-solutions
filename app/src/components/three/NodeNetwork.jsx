import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Line } from '@react-three/drei';
import * as THREE from 'three';
import { sceneState } from '../../lib/sceneState';

function sectionWeight(id) {
  const p = sceneState.sectionProgress[id];
  if (p === undefined) return 0;
  return Math.max(0, 1 - Math.abs(p - 0.5) * 2.2);
}

/**
 * Reusable orbit / constellation visual: a small hub with N nodes arranged on a
 * tilted ring, each connected to the hub by a line. Used for the Services orbit,
 * the case-studies category selector, and the Expertise constellation — same
 * component, different node counts/colors/active state.
 *
 * Fades in only while its own section is in view (via sceneState.sectionProgress),
 * so three instances can stay mounted for the whole page life without competing
 * for attention (or GPU — they're all just a handful of small meshes + lines).
 */
export default function NodeNetwork({
  sectionId,
  nodes,
  activeId = null,
  onNodeClick,
  onNodeHover,
  position = [0, 0, 0],
  radius = 2.15,
  tilt = 0.35,
  colorActive = '#4dd8e6',
  colorBase = '#3a4452',
}) {
  const group = useRef(null);
  const hub = useRef(null);

  const positions = useMemo(
    () =>
      nodes.map((_, i) => {
        const angle = (i / nodes.length) * Math.PI * 2;
        return new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius * 0.4, Math.sin(angle) * radius * 0.5);
      }),
    [nodes, radius]
  );

  const hubGeo = useMemo(() => new THREE.IcosahedronGeometry(0.22, 0), []);
  const nodeGeo = useMemo(() => new THREE.SphereGeometry(0.055, 10, 10), []);

  useFrame((state, delta) => {
    if (!group.current) return;
    const weight = sectionWeight(sectionId);
    group.current.visible = weight > 0.01;
    const opacityMul = weight;
    group.current.traverse((child) => {
      if (child.material && child.userData.baseOpacity !== undefined) {
        child.material.opacity = child.userData.baseOpacity * opacityMul;
      }
    });
    const scale = 0.82 + weight * 0.22;
    group.current.scale.setScalar(scale);
    group.current.rotation.y += delta * 0.05;
    if (hub.current) hub.current.rotation.y -= delta * 0.08;
  });

  return (
    <group ref={group} position={position} rotation={[tilt, 0, 0]}>
      <mesh ref={hub} geometry={hubGeo} userData={{ baseOpacity: 0.5 }}>
        <meshBasicMaterial color={colorActive} wireframe transparent opacity={0.5} />
      </mesh>

      {positions.map((pos, i) => {
        const node = nodes[i];
        const isActive = node.id === activeId;
        return (
          <group key={node.id}>
            <Line
              points={[[0, 0, 0], [pos.x, pos.y, pos.z]]}
              color={isActive ? colorActive : colorBase}
              transparent
              opacity={isActive ? 0.55 : 0.22}
              lineWidth={1}
            />
            <mesh
              position={pos}
              geometry={nodeGeo}
              userData={{ baseOpacity: isActive ? 1 : 0.55 }}
              onPointerOver={(e) => {
                e.stopPropagation();
                onNodeHover?.(node.id);
                document.body.style.cursor = 'pointer';
              }}
              onPointerOut={(e) => {
                e.stopPropagation();
                onNodeHover?.(null);
                document.body.style.cursor = '';
              }}
              onClick={(e) => {
                e.stopPropagation();
                onNodeClick?.(node.id);
              }}
              scale={isActive ? 1.7 : 1}
            >
              <meshBasicMaterial
                color={isActive ? colorActive : colorBase}
                transparent
                opacity={isActive ? 1 : 0.55}
              />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}
