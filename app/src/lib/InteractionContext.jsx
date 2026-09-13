import { createContext, useContext, useMemo, useState } from 'react';

// Shared interactive state between DOM sections (cards, lists — the accessible,
// keyboard/touch-reachable primary interface) and the persistent 3D layer (which
// reflects the same selection for visual delight, not as the only way to select it).
const InteractionContext = createContext(null);

export function InteractionProvider({ children }) {
  const [solutionsCategory, setSolutionsCategory] = useState('business');
  const [expertiseActive, setExpertiseActive] = useState(null);
  const [servicesActive, setServicesActive] = useState(null);
  // Set when a visitor clicks a service's CTA, so the contact form can preselect the
  // matching "what do you need help with" option instead of making them pick it again.
  const [contactInterest, setContactInterest] = useState('');

  const value = useMemo(
    () => ({
      solutionsCategory,
      setSolutionsCategory,
      expertiseActive,
      setExpertiseActive,
      servicesActive,
      setServicesActive,
      contactInterest,
      setContactInterest,
    }),
    [solutionsCategory, expertiseActive, servicesActive, contactInterest]
  );

  return <InteractionContext.Provider value={value}>{children}</InteractionContext.Provider>;
}

export function useInteraction() {
  const ctx = useContext(InteractionContext);
  if (!ctx) throw new Error('useInteraction must be used within InteractionProvider');
  return ctx;
}
