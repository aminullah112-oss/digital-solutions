import { useRef, type CSSProperties } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import LiveProjectButton from './LiveProjectButton';

export interface Project {
  number: string;
  category: string;
  name: string;
  col1Image1: string;
  col1Image2: string;
  col2Image: string;
}

interface ProjectCardProps {
  project: Project;
  index: number;
  total: number;
}

const imageClass = 'w-full object-cover rounded-[40px] sm:rounded-[50px] md:rounded-[60px]';

export default function ProjectCard({ project, index, total }: ProjectCardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const targetScale = 1 - (total - 1 - index) * 0.03;

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start end', 'start start'],
  });
  const scale = useTransform(scrollYProgress, [0, 1], [1, targetScale]);

  return (
    <div
      ref={containerRef}
      className="h-[85vh] flex items-center sticky top-[calc(6rem+var(--stack-offset))] md:top-[calc(8rem+var(--stack-offset))]"
      style={{ '--stack-offset': `${index * 28}px` } as CSSProperties}
    >
      <motion.div
        style={{ scale }}
        className="w-full rounded-[40px] sm:rounded-[50px] md:rounded-[60px] border-2 border-[#D7E2EA] bg-[#0C0C0C] p-4 sm:p-6 md:p-8"
      >
        <div className="flex flex-wrap items-center justify-between gap-4 sm:gap-6 mb-4 sm:mb-6 md:mb-8">
          <div className="flex items-center gap-4 sm:gap-6">
            <span
              className="text-[#D7E2EA] font-black leading-none"
              style={{ fontSize: 'clamp(3rem, 10vw, 140px)' }}
            >
              {project.number}
            </span>
            <div className="flex flex-col gap-1">
              <span className="text-[#D7E2EA]/60 uppercase tracking-widest text-xs sm:text-sm font-medium">
                {project.category}
              </span>
              <span className="text-[#D7E2EA] uppercase font-medium text-lg sm:text-2xl md:text-3xl">
                {project.name}
              </span>
            </div>
          </div>

          <LiveProjectButton />
        </div>

        <div className="flex gap-3 sm:gap-4">
          <div className="flex flex-col gap-3 sm:gap-4 w-[40%]">
            <img
              src={project.col1Image1}
              alt={`${project.name} preview 1`}
              loading="lazy"
              className={imageClass}
              style={{ height: 'clamp(130px, 16vw, 230px)' }}
            />
            <img
              src={project.col1Image2}
              alt={`${project.name} preview 2`}
              loading="lazy"
              className={imageClass}
              style={{ height: 'clamp(160px, 22vw, 340px)' }}
            />
          </div>
          <div className="w-[60%]">
            <img
              src={project.col2Image}
              alt={`${project.name} preview 3`}
              loading="lazy"
              className={`${imageClass} h-full`}
            />
          </div>
        </div>
      </motion.div>
    </div>
  );
}
