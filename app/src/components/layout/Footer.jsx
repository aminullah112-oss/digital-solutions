export default function Footer() {
  return (
    <footer className="border-t border-graphite-border py-8 px-5 sm:px-8">
      <div className="max-w-content mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-ink-3 text-sm">
        <p>&copy; {new Date().getFullYear()} Aminullah. Built and deployed on GitHub Pages.</p>
        <p className="font-mono-label text-[0.65rem] text-ink-3">Engineering × Software × AI × Automation</p>
      </div>
    </footer>
  );
}
