import { useEffect, useState } from 'react';
import { nav } from '../../data/content';
import { scrollToSelector } from '../../lib/scroll';
import MagneticButton from '../ui/MagneticButton';
import MobileMenu from './MobileMenu';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuOpen]);

  const handleNav = (e, href) => {
    e.preventDefault();
    setMenuOpen(false);
    scrollToSelector(href);
  };

  return (
    <>
      <header
        className={`fixed top-0 inset-x-0 z-40 transition-colors duration-500 ${
          scrolled ? 'bg-graphite-950/80 backdrop-blur-md border-b border-graphite-border' : 'bg-transparent'
        }`}
      >
        <nav className="max-w-content mx-auto px-5 sm:px-8 h-[76px] flex items-center justify-between">
          <a
            href="#home"
            onClick={(e) => handleNav(e, '#home')}
            className="font-display leading-tight select-none"
            data-cursor="expand"
          >
            <span className="block text-sm sm:text-base font-semibold tracking-[0.08em] text-ink-0">AMINULLAH</span>
            <span className="block font-mono-label text-[0.6rem] text-cyan">Digital Solutions</span>
          </a>

          <ul className="hidden lg:flex items-center gap-1">
            {nav.map((item) => (
              <li key={item.href}>
                <a
                  href={item.href}
                  onClick={(e) => handleNav(e, item.href)}
                  className="group flex items-center gap-2 px-4 py-2 text-sm text-ink-1 hover:text-ink-0 transition-colors duration-300"
                  data-cursor="expand"
                >
                  <span className="font-mono-label text-[0.62rem] text-cyan/70 group-hover:text-cyan transition-colors">
                    {item.n}
                  </span>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>

          <div className="hidden lg:block">
            <MagneticButton
              href="#contact"
              onClick={(e) => handleNav(e, '#contact')}
              className="font-mono-label text-[0.68rem] text-graphite-950 bg-cyan px-5 py-3 rounded-full inline-block hover:brightness-110 transition-[filter] duration-300"
            >
              Start a Project
            </MagneticButton>
          </div>

          <button
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            className="lg:hidden relative w-10 h-10 flex flex-col items-center justify-center gap-[5px]"
          >
            <span
              className={`block h-px w-6 bg-ink-0 transition-transform duration-300 ${menuOpen ? 'translate-y-[3px] rotate-45' : ''}`}
            />
            <span
              className={`block h-px w-6 bg-ink-0 transition-transform duration-300 ${menuOpen ? '-translate-y-[3px] -rotate-45' : ''}`}
            />
          </button>
        </nav>
      </header>

      <MobileMenu open={menuOpen} onNavigate={handleNav} />
    </>
  );
}
