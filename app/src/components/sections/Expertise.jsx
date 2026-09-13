import { expertise } from '../../data/content';
import { useReveal } from '../../lib/useReveal';
import { useSectionProgress } from '../../lib/useSectionProgress';
import { useInteraction } from '../../lib/InteractionContext';

export default function Expertise() {
  const ref = useSectionProgress('expertise');
  useReveal(ref);
  const { expertiseActive, setExpertiseActive } = useInteraction();

  return (
    <section id="expertise" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-content mx-auto px-5 sm:px-8">
        <p data-reveal className="font-mono-label text-cyan text-xs mb-4">
          {expertise.kicker}
        </p>
        <h2 data-reveal className="text-3xl sm:text-4xl md:text-5xl font-semibold text-ink-0 leading-[1.1]">
          {expertise.title}
        </h2>

        <div className="mt-14 grid md:grid-cols-2 gap-10">
          {expertise.groups.map((group) => (
            <div key={group.id} data-reveal>
              <p className="font-mono-label text-[0.62rem] text-amber mb-5">{group.label}</p>
              <div className="flex flex-wrap gap-2.5">
                {group.skills.map((skill) => {
                  const nodeId = `${group.id}:${skill}`;
                  const isActive = expertiseActive === nodeId;
                  return (
                    <button
                      key={skill}
                      type="button"
                      data-cursor="expand"
                      onMouseEnter={() => setExpertiseActive(nodeId)}
                      onMouseLeave={() => setExpertiseActive((cur) => (cur === nodeId ? null : cur))}
                      onFocus={() => setExpertiseActive(nodeId)}
                      onBlur={() => setExpertiseActive((cur) => (cur === nodeId ? null : cur))}
                      className={`text-sm px-4 py-2.5 rounded-lg border backdrop-blur-md transition-all duration-300 ${
                        isActive
                          ? 'border-cyan/60 bg-graphite-900/95 text-cyan'
                          : 'border-graphite-border bg-graphite-900/85 text-ink-1 hover:border-graphite-600 hover:text-ink-0'
                      }`}
                    >
                      {skill}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
