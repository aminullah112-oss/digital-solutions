import { useRef, type CSSProperties } from 'react';
import { motion, useScroll, useTransform, type MotionValue } from 'framer-motion';

interface AnimatedTextProps {
  text: string;
  className?: string;
  style?: CSSProperties;
}

function AnimatedChar({
  char,
  range,
  progress,
}: {
  char: string;
  range: [number, number];
  progress: MotionValue<number>;
}) {
  const opacity = useTransform(progress, range, [0.2, 1]);
  const display = char === ' ' ? ' ' : char;

  return (
    <span style={{ position: 'relative', display: 'inline-block' }}>
      {/* Invisible placeholder reserves layout space so the absolutely positioned,
          animated character on top never shifts surrounding text. */}
      <span style={{ visibility: 'hidden' }}>{display}</span>
      <motion.span style={{ position: 'absolute', left: 0, top: 0, opacity }}>{display}</motion.span>
    </span>
  );
}

export default function AnimatedText({ text, className, style }: AnimatedTextProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.8', 'end 0.2'] });
  const chars = text.split('');
  const total = chars.length;

  return (
    <p ref={ref} className={className} style={style}>
      {chars.map((char, i) => (
        <AnimatedChar key={i} char={char} range={[i / total, (i + 1) / total]} progress={scrollYProgress} />
      ))}
    </p>
  );
}
