import { useMemo, type CSSProperties, type ElementType, type ReactNode } from 'react';
import { motion } from 'framer-motion';

interface FadeInProps {
  children?: ReactNode;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
  delay?: number;
  duration?: number;
  x?: number;
  y?: number;
  // Passed straight through to the underlying element — e.g. src/alt when as="img".
  [rest: string]: unknown;
}

const EASE: [number, number, number, number] = [0.25, 0.1, 0.25, 1];

export default function FadeIn({
  children,
  as = 'div',
  className,
  style,
  delay = 0,
  duration = 0.7,
  x = 0,
  y = 30,
  ...rest
}: FadeInProps) {
  // motion.create() returns a new component identity — memoize on the tag so we don't
  // remount the element (and lose its animation state) on every parent re-render.
  const MotionTag = useMemo(() => motion.create(as), [as]);

  return (
    <MotionTag
      className={className}
      style={style}
      initial={{ opacity: 0, x, y }}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once: true, margin: '50px', amount: 0 }}
      transition={{ delay, duration, ease: EASE }}
      {...rest}
    >
      {children}
    </MotionTag>
  );
}
