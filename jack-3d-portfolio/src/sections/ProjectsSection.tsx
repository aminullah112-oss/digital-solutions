import FadeIn from '../components/FadeIn';
import ProjectCard, { type Project } from '../components/ProjectCard';

const cdn = (path: string) =>
  `https://images.higgs.ai/?default=1&output=webp&url=${encodeURIComponent(
    `https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/${path}`
  )}&w=1280&q=85`;

const PROJECTS: Project[] = [
  {
    number: '01',
    category: 'Client',
    name: 'Nextlevel Studio',
    col1Image1: cdn('hf_20260412_055344_5eff02e0-87a5-41ce-b64f-eb08da8f33db.png'),
    col1Image2: cdn('hf_20260412_055431_11d841fd-8b41-46a5-82e4-b04f2407a7d8.png'),
    col2Image: cdn('hf_20260412_055451_e317bf2d-28d4-48cc-86b0-6f72f25b6327.png'),
  },
  {
    number: '02',
    category: 'Personal',
    name: 'Aura Brand Identity',
    col1Image1: cdn('hf_20260412_055654_911201c5-36d9-4bc6-bac7-331adfce159f.png'),
    col1Image2: cdn('hf_20260412_055723_5ceda0b8-d9c2-4665-b2e3-83ba19ba76d1.png'),
    col2Image: cdn('hf_20260412_055753_adc5dcbd-a8e6-49c0-b43a-9b030d835cea.png'),
  },
  {
    number: '03',
    category: 'Client',
    name: 'Solaris Digital',
    col1Image1: cdn('hf_20260412_055759_963cfb0b-4bd1-4b0f-9d0a-09bd6cf95b2f.png'),
    col1Image2: cdn('hf_20260412_060108_438f781a-9846-4dcc-89ab-c4e6cb830f5b.png'),
    col2Image: cdn('hf_20260412_055818_9d062121-ad7e-46b9-999a-1a6a692ef1ee.png'),
  },
];

export default function ProjectsSection() {
  return (
    <section
      id="projects"
      className="bg-[#0C0C0C] rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] -mt-10 sm:-mt-12 md:-mt-14 relative z-10 px-5 sm:px-8 md:px-10 pt-20 sm:pt-24 md:pt-32 pb-10"
    >
      <FadeIn
        as="h2"
        delay={0}
        className="hero-heading font-black uppercase leading-none tracking-tight text-center mb-16 sm:mb-20 md:mb-28"
        style={{ fontSize: 'clamp(3rem, 12vw, 160px)' }}
      >
        Project
      </FadeIn>

      <div className="max-w-6xl mx-auto">
        {PROJECTS.map((project, i) => (
          <ProjectCard key={project.number} project={project} index={i} total={PROJECTS.length} />
        ))}
      </div>
    </section>
  );
}
