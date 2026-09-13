import { createContext, useContext, useMemo, useState } from 'react';

// Shared interactive state between DOM sections (cards, lists — the accessible,
// keyboard/touch-reachable primary interface) and the persistent 3D layer (which
// reflects the same selection for visual delight, not as the only way to select it).
const InteractionContext = createContext(null);

export function InteractionProvider({ children }) {
  const [protectionGridActive, setProtectionGridActive] = useState(null);
  const [solutionsCategory, setSolutionsCategory] = useState('business');
  const [expertiseActive, setExpertiseActive] = useState(null);

  const value = useMemo(
    () => ({
      protectionGridActive,
      setProtectionGridActive,
      solutionsCategory,
      setSolutionsCategory,
      expertiseActive,
      setExpertiseActive,
    }),
    [protectionGridActive, solutionsCategory, expertiseActive]
  );

  return <InteractionContext.Provider value={value}>{children}</InteractionContext.Provider>;
}

export function useInteraction() {
  const ctx = useContext(InteractionContext);
  if (!ctx) throw new Error('useInteraction must be used within InteractionProvider');
  return ctx;
}
