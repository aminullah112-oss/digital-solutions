import { nav } from '../../data/content';

export default function MobileMenu({ open, onNavigate }) {
  return (
    <div
      className={`fixed inset-0 z-30 bg-graphite-950/98 backdrop-blur-xl transition-all duration-500 ease-engineered lg:hidden ${
        open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
      }`}
      aria-hidden={!open}
    >
      <div className="h-full flex flex-col justify-center px-8">
        <ul className="space-y-1">
          {nav.map((item, i) => (
            <li
              key={item.href}
              className="transition-all duration-500 ease-engineered"
              style={{
                transitionDelay: open ? `${i * 60 + 80}ms` : '0ms',
                opacity: open ? 1 : 0,
                transform: open ? 'translateY(0)' : 'translateY(16px)',
              }}
            >
              <a
                href={item.href}
                onClick={(e) => onNavigate(e, item.href)}
                tabIndex={open ? 0 : -1}
                className="flex items-baseline gap-4 py-3 text-3xl font-display font-semibold text-ink-0"
              >
                <span className="font-mono-label text-sm text-cyan">{item.n}</span>
                {item.label}
              </a>
            </li>
          ))}
        </ul>
        <a
          href="#contact"
          onClick={(e) => onNavigate(e, '#contact')}
          tabIndex={open ? 0 : -1}
          className="font-mono-label text-xs text-graphite-950 bg-cyan px-6 py-4 rounded-full inline-block mt-8 w-fit"
        >
          Start a Project
        </a>
      </div>
    </div>
  );
}
