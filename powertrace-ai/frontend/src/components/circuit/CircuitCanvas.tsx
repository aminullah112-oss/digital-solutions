import { useEffect, useMemo } from 'react'
import {
  Background, BackgroundVariant, Controls, MarkerType, ReactFlow, useEdgesState,
  useNodesState, useReactFlow, type Edge, type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { CircuitEdge, CircuitNode, TerminalStatus } from '@/lib/types'
import { CircuitNodeCard, type CircuitNodeData } from './CircuitNode'

const nodeTypes = { circuit: CircuitNodeCard }

// Edge colour encodes relationship type, which is what makes a ladder
// readable at a glance: power flow vs. control signal vs. plain continuity.
const EDGE_STYLE: Record<string, { stroke: string; dash?: string }> = {
  FEEDS: { stroke: '#64748b' },
  POWERED_BY: { stroke: '#64748b' },
  RETURNS_TO: { stroke: '#475569', dash: '4 3' },
  SIGNAL_TO: { stroke: '#3b82f6', dash: '5 3' },
  CONTROLLED_BY: { stroke: '#8b5cf6', dash: '2 3' },
  CONNECTED_TO: { stroke: '#475569' },
  PROTECTED_BY: { stroke: '#f59e0b', dash: '1 4' },
}

export function CircuitCanvas({
  nodes, edges, status, selectedKey, highlightKeys, suspectKeys, onSelect, fitSignal,
}: {
  nodes: CircuitNode[]
  edges: CircuitEdge[]
  status: Record<string, TerminalStatus>
  selectedKey: string | null
  highlightKeys: string[] | null
  suspectKeys: string[]
  onSelect: (key: string) => void
  fitSignal: number
}) {
  const flowNodes = useMemo<Node<CircuitNodeData>[]>(() => {
    const highlight = highlightKeys ? new Set(highlightKeys) : null
    const suspects = new Set(suspectKeys)
    return nodes.map((node, index) => ({
      id: node.key,
      type: 'circuit',
      position: {
        x: node.x ?? (index % 6) * 220,
        y: node.y ?? Math.floor(index / 6) * 130,
      },
      selected: node.key === selectedKey,
      data: {
        label: node.label || node.key,
        nodeType: node.node_type,
        status: status[node.key],
        controllerSignal: node.controller_signal,
        mediumVoltage: node.medium_voltage,
        verified: node.verified,
        confidence: node.confidence,
        highlighted: highlight ? highlight.has(node.key) : undefined,
        suspect: suspects.has(node.key),
      },
    }))
  }, [nodes, status, selectedKey, highlightKeys, suspectKeys])

  const flowEdges = useMemo<Edge[]>(() => {
    const highlight = highlightKeys ? new Set(highlightKeys) : null
    return edges.map((edge) => {
      const style = EDGE_STYLE[edge.edge_type] ?? EDGE_STYLE.CONNECTED_TO
      const dim = highlight && !(highlight.has(edge.from) && highlight.has(edge.to))
      return {
        id: String(edge.id),
        source: edge.from,
        target: edge.to,
        label: edge.wire_number || undefined,
        labelStyle: { fill: '#64748b', fontSize: 9 },
        labelBgStyle: { fill: '#0b0f16' },
        style: {
          stroke: style.stroke,
          strokeDasharray: style.dash,
          opacity: dim ? 0.15 : 1,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: style.stroke, width: 14, height: 14 },
        animated: Boolean(highlight && !dim),
      }
    })
  }, [edges, highlightKeys])

  const [renderNodes, setNodes, onNodesChange] = useNodesState(flowNodes)
  const [renderEdges, setEdges, onEdgesChange] = useEdgesState(flowEdges)
  const flow = useReactFlow()

  useEffect(() => { setNodes(flowNodes) }, [flowNodes, setNodes])
  useEffect(() => { setEdges(flowEdges) }, [flowEdges, setEdges])
  useEffect(() => {
    if (fitSignal > 0) flow.fitView({ padding: 0.2, duration: 400 })
  }, [fitSignal, flow])

  return (
    <ReactFlow
      nodes={renderNodes}
      edges={renderEdges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => onSelect(node.id)}
      fitView
      minZoom={0.15}
      maxZoom={2.2}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1c2431" />
      <Controls className="!bg-panel-800 !border-edge" showInteractive={false} />
    </ReactFlow>
  )
}
