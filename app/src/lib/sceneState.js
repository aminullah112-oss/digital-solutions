// Shared mutable state read by the R3F render loop every frame.
// Deliberately not React state / not a store library: the values below are written
// by DOM event listeners and GSAP ScrollTrigger callbacks, and read inside useFrame —
// mutating a plain object avoids a React re-render (and a new dependency) for every
// mousemove/scroll tick, which is what actually matters for frame budget here.
export const sceneState = {
  mouse: { x: 0, y: 0 }, // normalized -1..1
  scrollProgress: 0, // 0..1 across the whole page
  activeSection: 'hero',
  sectionProgress: {}, // { [sectionId]: 0..1 local progress }
  reducedMotion: false,
};

export function setSectionProgress(id, value) {
  sceneState.sectionProgress[id] = value;
}
