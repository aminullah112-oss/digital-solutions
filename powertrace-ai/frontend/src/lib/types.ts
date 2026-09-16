// Types mirroring the backend's provenance model. The unions are deliberately
// exhaustive: a new source or quality value should break the build rather
// than silently render as something else.

export type Quality = 'GOOD' | 'BAD' | 'STALE' | 'TIMEOUT' | 'UNKNOWN' | 'SIMULATED'

export type DataSource =
  | 'MEASURED' | 'CONTROLLER' | 'SCHEMATIC' | 'EXPECTATION'
  | 'INFERENCE' | 'SIMULATED' | 'UNKNOWN'

export type ComparisonResult =
  | 'NORMAL' | 'ABNORMAL' | 'MARGINAL' | 'NOT_MEASURED' | 'NO_EXPECTATION'

export type Confidence =
  | 'CONFIRMED_BY_MEASUREMENT' | 'LIKELY' | 'POSSIBLE' | 'UNVERIFIED'

export type ConnectionState =
  | 'OFFLINE' | 'CONNECTING' | 'ONLINE' | 'DEGRADED' | 'ERROR' | 'DISABLED'

export interface ValueEnvelope {
  key: string
  display_name: string
  group: string
  kind: 'analog' | 'discrete' | 'state' | 'counter'
  value: number | boolean | string | null
  unit: string
  timestamp: string
  quality: Quality
  source: DataSource
  source_detail?: string | null
  error?: string | null
  age_s?: number
}

export interface Controller {
  id: number
  project_id: number
  name: string
  manufacturer: string
  model: string
  controller_type: string
  description: string
  enabled: boolean
  is_simulated: boolean
  connection_state: ConnectionState
  last_ok_at: string | null
  last_error: string | null
  consecutive_failures: number
  register_map_id: number | null
  register_map_verified: boolean | null
  protocol?: {
    protocol: string
    host: string | null
    port: number | null
    unit_id: number
    poll_interval_ms: number
    timeout_s: number
    retries: number
  }
}

export interface Project {
  id: number
  name: string
  site: string
  panel: string
  description: string
  is_demo: boolean
  nominal_voltage_v: number | null
  nominal_frequency_hz: number | null
  control_voltage_v: number | null
}

export interface CircuitNode {
  id: number
  key: string
  label: string
  node_type: string
  controller_id: number | null
  controller_signal: string
  nominal_voltage_v: number | null
  x: number | null
  y: number | null
  confidence: number
  verified: boolean
  medium_voltage?: boolean
  safety_notice?: string
  depth?: number
  component?: { reference_designator: string; component_type: string; description: string
    rating: string; location: string; part_number: string }
  terminal?: { tag: string; block: string; number: string; description: string
    expected_voltage_v: number | null; expected_reference: string
    expected_tolerance_pct: number; expected_signal_type: string }
  wire?: { wire_number: string; color: string; gauge: string }
}

export interface CircuitEdge {
  id: number
  from: string
  to: string
  edge_type: string
  label: string
  wire_number: string
  confidence: number
  verified: boolean
}

export interface TerminalStatus {
  node_key: string
  terminal_tag: string | null
  expected: { value: number; unit: string; tolerance_pct: number; band: number
    min: number; max: number; signal_type: string; reference: string
    source: DataSource; basis: string } | null
  measured: { value: number; unit: string; quality: Quality; source: DataSource
    timestamp: string | null; method?: string; instrument?: string
    technician?: string } | null
  controller: { signal: string; value: number | boolean | string | null; unit?: string
    timestamp?: string; quality: Quality; source: DataSource; note: string } | null
  comparison: { result: ComparisonResult; reason: string; deviation: number | null
    deviation_pct: number | null }
  status: string
  overlay_color: 'GREEN' | 'RED' | 'YELLOW' | 'GRAY' | 'BLUE'
  reason: string
  medium_voltage?: boolean
  safety_notice?: string
}

export interface Finding {
  rule_key: string
  title: string
  statement: string
  confidence: Confidence
  suspect_nodes: string[]
  recommended_test: string
  evidence: Array<{ kind: string; label: string; value: unknown; source: string
    quality: string; detail: string; node_key: string | null }>
  missing_information: string[]
  severity: string
  source: string
}

export interface Discontinuity {
  between: [string, string]
  via: CircuitEdge
  upstream_measured: TerminalStatus['measured']
  downstream_measured: TerminalStatus['measured']
  statement: string
  confidence: Confidence
  components_in_segment: Array<{ key: string; label: string; node_type: string }>
}

export interface Alarm {
  id: number
  project_id: number
  controller_id: number | null
  code: string
  description: string
  description_source: string
  severity: 'SHUTDOWN' | 'ALARM' | 'WARNING' | 'EVENT' | 'INFO'
  source: string
  is_active: boolean
  acknowledged: boolean
  acknowledged_by: string
  raised_at: string
  cleared_at: string | null
}

export interface DiagnosticStep {
  id: number
  sequence: number
  title: string
  instruction: string
  expected: Record<string, unknown> | null
  actual: Record<string, unknown> | null
  status: 'PENDING' | 'PASS' | 'FAIL' | 'MARGINAL' | 'INFO' | 'SKIPPED'
  evidence: unknown[]
  next_action: string
  circuit_node_key: string
  requires_measurement: boolean
  safety_notice: string
  notes: string
  completed_at: string | null
}

export interface DiagnosticSession {
  id: number
  project_id: number
  controller_id: number | null
  title: string
  fault_category: string
  symptom: string
  status: string
  technician: string
  opened_at: string
  closed_at: string | null
  resolution: string
  unresolved_items: string[]
  findings: Finding[]
  ai_analysis: Record<string, any> | null
  steps: DiagnosticStep[]
}

export interface FaultTreeNode {
  id: string
  label: string
  status: 'RULED_OUT' | 'SUSPECT' | 'UNVERIFIED' | 'NOT_MEASURED'
  detail?: string
  children: FaultTreeNode[]
}

export interface DashboardPayload {
  controllers: Array<Controller & { host: string | null; protocol: string | null
    values: Record<string, ValueEnvelope | undefined> }>
  summary: {
    controllers_online: number
    controllers_offline: number
    generators_running: number
    generators_stopped: number
    active_faults: number
    warnings: number
    total_load_kw: number | null
    system_voltage_v: number | null
    frequency_hz: number | null
    contributing_controllers: number
    aggregate_note: string
  }
  alarms: Alarm[]
  demo_mode: boolean
}

export interface SystemStatus {
  app: string
  environment: string
  demo_mode: boolean
  control_writes_enabled: boolean
  server_time: string
  controllers: { total: number; online: number; offline: number; disabled: number
    simulated: number; polling: number[] }
  alarms: { active: number; shutdowns: number; warnings: number; unacknowledged: number }
  counts: { projects: number; schematics: number; open_sessions: number }
  last_synchronization: string | null
  safety: { control_commands: string; notice: string }
}
