// Static, CSS-only stand-in for the WebGL scene — shown when WebGL is unavailable
// or the visitor prefers reduced motion. No animation loop, no canvas, just enough
// visual texture that the page doesn't feel broken.
export default function SceneFallback() {
  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 z-0 pointer-events-none"
      style={{
        background:
          'radial-gradient(ellipse 70% 55% at 50% 18%, rgba(77,216,230,0.10), transparent 60%), radial-gradient(ellipse 60% 40% at 85% 70%, rgba(232,166,98,0.05), transparent 65%)',
      }}
    >
      <div
        className="absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(ellipse 70% 60% at 50% 25%, black, transparent 75%)',
        }}
      />
    </div>
  );
}
