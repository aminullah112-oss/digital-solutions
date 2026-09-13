// Cheap, synchronous WebGL capability check — used to decide whether to even
// attempt mounting the R3F canvas, so a blocked/disabled WebGL context never
// throws mid-render.
export function hasWebGL() {
  if (typeof window === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl');
    return !!gl;
  } catch {
    return false;
  }
}
