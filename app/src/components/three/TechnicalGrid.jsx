import { Grid } from '@react-three/drei';

// A faint blueprint-style floor grid — the "control room floor" cue. drei's Grid
// is a single optimized mesh (shader-based fade), not a mass of line geometry.
export default function TechnicalGrid() {
  return (
    <Grid
      position={[0, -3.4, 0]}
      args={[40, 40]}
      cellSize={0.5}
      cellThickness={0.5}
      cellColor="#1a2029"
      sectionSize={2.5}
      sectionThickness={1}
      sectionColor="#264049"
      fadeDistance={16}
      fadeStrength={1.4}
      infiniteGrid
      followCamera={false}
    />
  );
}
