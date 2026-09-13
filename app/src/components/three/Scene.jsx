import CameraRig from './CameraRig';
import DigitalCore from './DigitalCore';
import ParticleField from './ParticleField';
import TechnicalGrid from './TechnicalGrid';
import NodeNetwork from './NodeNetwork';
import { useInteraction } from '../../lib/InteractionContext';
import { solutionCategories, expertise } from '../../data/content';

const serviceNodes = solutionCategories.map((c) => ({ id: c.id }));
const expertiseNodes = expertise.groups.flatMap((g) => g.skills.map((s) => ({ id: `${g.id}:${s}` })));

export default function Scene({ quality = 'high', particleCount = 220 }) {
  const {
    servicesActive,
    setServicesActive,
    solutionsCategory,
    setSolutionsCategory,
    expertiseActive,
    setExpertiseActive,
  } = useInteraction();

  return (
    <>
      <CameraRig intensity={quality === 'low' ? 0.5 : 1} />
      <fog attach="fog" args={['#07090c', 8, 22]} />

      <DigitalCore quality={quality} />
      <ParticleField count={particleCount} />
      {quality !== 'low' && <TechnicalGrid />}

      {/* Services section — the primary offer, so it gets the strongest node network */}
      <NodeNetwork
        sectionId="products"
        nodes={serviceNodes}
        activeId={servicesActive}
        onNodeHover={setServicesActive}
        onNodeClick={setServicesActive}
        position={[0, 0, -1]}
        radius={2.3}
        colorActive="#4dd8e6"
      />

      <NodeNetwork
        sectionId="solutions"
        nodes={serviceNodes}
        activeId={solutionsCategory}
        onNodeHover={() => {}}
        onNodeClick={setSolutionsCategory}
        position={[0.4, 0.1, -0.6]}
        radius={1.9}
        colorActive="#a78bfa"
      />

      <NodeNetwork
        sectionId="expertise"
        nodes={expertiseNodes}
        activeId={expertiseActive}
        onNodeHover={setExpertiseActive}
        onNodeClick={setExpertiseActive}
        position={[0, -0.1, -2.2]}
        radius={2.3}
        colorActive="#8be9f2"
      />
    </>
  );
}
