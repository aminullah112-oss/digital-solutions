import { useRef } from 'react';
import { cta } from '../../data/content';
import { CONTACT_EMAIL, GITHUB_URL } from '../../lib/leads';
import { useSectionProgress } from '../../lib/useSectionProgress';
import { useReveal } from '../../lib/useReveal';
import { scrollToSelector } from '../../lib/scroll';
import MagneticButton from '../ui/MagneticButton';

export default function CTA() {
  const ref = useSectionProgress('cta');
  useReveal(ref);

  return (
    <section id="cta-section" ref={ref} className="relative py-32 md:py-44">
      <div className="max-w-content mx-auto px-5 sm:px-8 text-center">
        <h2
          data-reveal
          className="max-w-3xl mx-auto text-3xl sm:text-5xl md:text-6xl font-semibold text-ink-0 leading-[1.08]"
        >
          {cta.headline}
        </h2>
        <p data-reveal className="mt-6 max-w-xl mx-auto text-ink-1 text-base md:text-lg leading-relaxed">
          {cta.body}
        </p>

        <div data-reveal className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <MagneticButton
            href="#contact"
            onClick={(e) => {
              e.preventDefault();
              scrollToSelector('#contact');
            }}
            className="font-mono-label text-xs text-graphite-950 bg-cyan px-8 py-4 rounded-full inline-block hover:brightness-110 transition-[filter] duration-300"
          >
            Start a Project
          </MagneticButton>
          <MagneticButton
            as="a"
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono-label text-xs text-ink-0 border border-graphite-border px-8 py-4 rounded-full inline-block hover:border-cyan/50 hover:text-cyan transition-colors duration-300"
          >
            View GitHub
          </MagneticButton>
        </div>

        <a
          data-reveal
          data-cursor="expand"
          href={`mailto:${CONTACT_EMAIL}?subject=Project%20Inquiry`}
          className="mt-8 inline-block font-mono-label text-sm text-ink-2 hover:text-cyan transition-colors duration-300"
        >
          {CONTACT_EMAIL}
        </a>
      </div>
    </section>
  );
}
