"""DEMO MODE.

Builds a complete, self-consistent demo project so every screen can be
exercised without hardware: two simulated controllers, a control circuit
graph for a generator breaker close circuit, a simulated measurement gateway,
and a measurement set that reproduces the classic symptom — the controller
commands a close, the coil is at rated voltage, and nothing reaches the
breaker.

Everything created here is marked demo/simulated at the row level. The tags
travel with the data: a value that originated in the simulator is SIMULATED
on every screen and in every export.

The component tags (K12, F7, TB23-14, W-105, DO-07) are illustrative for this
fictional panel. They are not taken from any manufacturer's drawing.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import DataSource, EdgeType, NodeType, Protocol, Quality, Severity, utcnow
from ..models import (
    CircuitEdge, CircuitNode, Component, Connection, Controller, Measurement, MeasurementChannel,
    MeasurementDevice, Project, ProtocolConfiguration, RegisterDefinition, RegisterMap, Terminal,
    TroubleshootingRule, Wire,
)
from .builtin_rules import BUILTIN_RULES

DEMO_PROJECT_NAME = "PPU34 (DEMO)"

# key, label, type, controller_signal, nominal V, expected V at this point
NODES: list[tuple[str, str, NodeType, str, float | None, float | None]] = [
    ("DC24_SOURCE", "24 VDC control supply", NodeType.SOURCE, "", 24.0, 24.0),
    ("F7", "F7 control fuse 3 A", NodeType.FUSE, "", 24.0, 24.0),
    ("CTRL_BUS", "Control bus +24 V", NodeType.BUS, "", 24.0, 24.0),
    ("EMCP_DO07", "Controller output DO-07 (close command)", NodeType.CONTROLLER_OUTPUT,
     "DO_07", 24.0, 24.0),
    ("W105", "Wire W-105", NodeType.WIRE, "", 24.0, 24.0),
    ("TB23_14", "TB23-14", NodeType.TERMINAL, "", 24.0, 24.0),
    ("K12_COIL", "K12 close relay coil", NodeType.RELAY_COIL, "", 24.0, 24.0),
    ("K12_CONTACT", "K12 contact 13-14", NodeType.RELAY_CONTACT, "", 24.0, 24.0),
    ("TB23_16", "TB23-16", NodeType.TERMINAL, "", 24.0, 24.0),
    ("CB1_CLOSE_COIL", "CB1 breaker close coil", NodeType.LOAD, "", 24.0, 24.0),
    ("DC0V_RETURN", "0 V control return", NodeType.GROUND, "", 0.0, 0.0),
    ("CB1", "CB1 generator breaker", NodeType.BREAKER, "breaker_status", 4160.0, None),
    ("CB1_AUX", "CB1 auxiliary contact 52a", NodeType.RELAY_CONTACT, "", 24.0, 24.0),
    ("EMCP_DI11", "Controller input DI-11 (breaker closed)", NodeType.CONTROLLER_INPUT,
     "DI_11", 24.0, 24.0),
    ("GEN_BUS", "Generator bus 4160 V", NodeType.BUS, "", 4160.0, None),
    ("PT1", "PT1 4160/120 V", NodeType.PT, "", 4160.0, None),
    ("CT1", "CT1 600/5 A", NodeType.CT, "", 4160.0, None),
]

EDGES: list[tuple[str, str, EdgeType, str]] = [
    ("DC24_SOURCE", "F7", EdgeType.FEEDS, "W-101"),
    ("F7", "CTRL_BUS", EdgeType.FEEDS, "W-102"),
    ("CTRL_BUS", "EMCP_DO07", EdgeType.FEEDS, "W-103"),
    ("EMCP_DO07", "W105", EdgeType.SIGNAL_TO, "W-105"),
    ("W105", "TB23_14", EdgeType.CONNECTED_TO, "W-105"),
    ("TB23_14", "K12_COIL", EdgeType.FEEDS, "W-106"),
    ("K12_COIL", "DC0V_RETURN", EdgeType.RETURNS_TO, "W-107"),
    ("K12_CONTACT", "K12_COIL", EdgeType.CONTROLLED_BY, ""),
    ("CTRL_BUS", "K12_CONTACT", EdgeType.FEEDS, "W-110"),
    ("K12_CONTACT", "TB23_16", EdgeType.FEEDS, "W-111"),
    ("TB23_16", "CB1_CLOSE_COIL", EdgeType.FEEDS, "W-112"),
    ("CB1_CLOSE_COIL", "DC0V_RETURN", EdgeType.RETURNS_TO, "W-113"),
    ("CB1", "CB1_CLOSE_COIL", EdgeType.CONTROLLED_BY, ""),
    ("CB1", "CB1_AUX", EdgeType.SIGNAL_TO, ""),
    ("CB1_AUX", "EMCP_DI11", EdgeType.SIGNAL_TO, "W-120"),
    ("GEN_BUS", "CB1", EdgeType.FEEDS, ""),
    ("GEN_BUS", "PT1", EdgeType.CONNECTED_TO, ""),
    ("GEN_BUS", "CT1", EdgeType.CONNECTED_TO, ""),
    ("F7", "CTRL_BUS", EdgeType.PROTECTED_BY, ""),
]

COMPONENTS = [
    ("K12", NodeType.RELAY, "Close relay, 24 VDC coil, DPDT", "24 VDC / 10 A"),
    ("F7", NodeType.FUSE, "Control circuit fuse", "3 A"),
    ("CB1", NodeType.BREAKER, "Generator circuit breaker", "4160 V / 1200 A"),
    ("PT1", NodeType.PT, "Potential transformer", "4160:120 V"),
    ("CT1", NodeType.CT, "Current transformer", "600:5 A"),
]

TERMINALS = [
    ("TB23-14", "TB23", "14", "Close command from controller DO-07", 24.0, "0V_RETURN"),
    ("TB23-16", "TB23", "16", "Close coil feed from K12 contact", 24.0, "0V_RETURN"),
]

# Measured values for the demo fault. Voltage is present up to the relay
# contact and absent after it, which is what actually localizes the problem.
DEMO_MEASUREMENTS: list[tuple[str, float, str]] = [
    ("DC24_SOURCE", 24.3, "V"),
    ("F7", 24.2, "V"),
    ("CTRL_BUS", 24.2, "V"),
    ("EMCP_DO07", 23.9, "V"),
    ("TB23_14", 23.9, "V"),
    ("K12_COIL", 24.1, "V"),
    ("K12_CONTACT", 0.2, "V"),
    ("TB23_16", 0.1, "V"),
    ("CB1_CLOSE_COIL", 0.0, "V"),
]


def seed(db: Session, *, reset: bool = False) -> Project:
    existing = db.scalars(select(Project).where(Project.name == DEMO_PROJECT_NAME)).first()
    if existing and not reset:
        return existing
    if existing:
        db.delete(existing)
        db.commit()

    project = Project(
        name=DEMO_PROJECT_NAME, site="Demo Site", panel="PPU34",
        description=(
            "Demonstration project. Every value in it is simulated. It exists so the "
            "application can be exercised without hardware and must not be used as a "
            "reference for any real panel."
        ),
        is_demo=True, nominal_voltage_v=4160.0, nominal_frequency_hz=60.0,
        control_voltage_v=24.0,
    )
    db.add(project)
    db.flush()

    register_map = _seed_register_map(db)
    controllers = _seed_controllers(db, project, register_map)
    nodes = _seed_circuit(db, project, controllers[0])
    _seed_gateway(db, project, nodes)
    _seed_rules(db)
    db.commit()
    return project


def _seed_register_map(db: Session) -> RegisterMap:
    existing = db.scalars(select(RegisterMap).where(RegisterMap.name == "SIMULATOR DEMO MAP")
                          ).first()
    if existing:
        return existing
    rmap = RegisterMap(
        name="SIMULATOR DEMO MAP",
        controller_type="SIMULATOR", manufacturer="(none)", model="(simulated)",
        source_document="Generated for DEMO MODE. Contains no real device addresses.",
        verified=False, is_simulator_only=True,
        notes=(
            "Addresses in this map are placeholders consumed by the built-in simulator. "
            "They are meaningless on real hardware. Import a verified map from your "
            "controller's published register list before connecting to equipment."
        ),
    )
    db.add(rmap)
    db.flush()
    from .normalization import CATALOGUE

    for i, key in enumerate([*CATALOGUE, "DO_07", "DO_08", "DI_11", "DI_12"]):
        db.add(RegisterDefinition(
            register_map_id=rmap.id, controller_type="SIMULATOR", parameter_name=key,
            address=i, function_code=3, unit="", normalized_key=key,
            description=f"Simulated parameter {key}", source="SIMULATOR",
        ))
    return rmap


def _seed_controllers(db: Session, project: Project, rmap: RegisterMap) -> list[Controller]:
    controllers = []
    for index, name in enumerate(("EMCP DEMO 01", "EMCP DEMO 02"), start=1):
        controller = Controller(
            project_id=project.id, name=name,
            manufacturer="PowerTrace", model="Simulated genset controller",
            controller_type="SIMULATOR",
            description="Simulated controller — DEMO MODE. No physical device.",
            enabled=True, is_simulated=True, register_map_id=rmap.id,
        )
        db.add(controller)
        db.flush()
        db.add(ProtocolConfiguration(
            controller_id=controller.id, protocol=Protocol.SIMULATOR,
            host=None, port=None, unit_id=index, poll_interval_ms=1000,
            options={"nominal_voltage_v": 4160.0, "rated_kw": 2000.0},
        ))
        controllers.append(controller)
    return controllers


def _seed_circuit(db: Session, project: Project, controller: Controller) -> dict[str, CircuitNode]:
    components: dict[str, Component] = {}
    for ref, ctype, description, rating in COMPONENTS:
        component = Component(
            project_id=project.id, reference_designator=ref, component_type=ctype,
            description=description, rating=rating, location="PPU34 panel",
            confidence=1.0, verified=True,
        )
        db.add(component)
        db.flush()
        components[ref] = component

    terminals: dict[str, Terminal] = {}
    for tag, block, number, description, expected, reference in TERMINALS:
        terminal = Terminal(
            project_id=project.id, tag=tag, block=block, number=number,
            description=description, expected_voltage_v=expected,
            expected_reference=reference, expected_tolerance_pct=10.0,
            expected_signal_type="DC", confidence=1.0, verified=True,
        )
        db.add(terminal)
        db.flush()
        terminals[tag] = terminal

    wires: dict[str, Wire] = {}
    for _, _, _, wire_number in EDGES:
        if wire_number and wire_number not in wires:
            wire = Wire(project_id=project.id, wire_number=wire_number, color="", gauge="16 AWG",
                        confidence=1.0, verified=True)
            db.add(wire)
            db.flush()
            wires[wire_number] = wire

    nodes: dict[str, CircuitNode] = {}
    # Layout coordinates: left-to-right by electrical position so the graph
    # reads like a ladder rather than a hairball.
    # Columns 280 px apart, rows 170 px apart. Node cards render around
    # 230 x 110 px once a long label is in them, so anything tighter overlaps.
    layout = {
        # Control supply rail
        "DC24_SOURCE": (0, 0), "F7": (280, 0), "CTRL_BUS": (560, 0),
        # Close command path, above the rail
        "EMCP_DO07": (840, -190), "W105": (1120, -190), "TB23_14": (1400, -190),
        "K12_COIL": (1680, -190),
        # Close coil path, below the rail
        "K12_CONTACT": (840, 190), "TB23_16": (1120, 190), "CB1_CLOSE_COIL": (1400, 190),
        "DC0V_RETURN": (2000, 0),
        # Breaker and its feedback
        "CB1": (1680, 400), "CB1_AUX": (1400, 570), "EMCP_DI11": (1120, 570),
        # Medium-voltage side
        "GEN_BUS": (1680, 740), "CT1": (1400, 910), "PT1": (1960, 910),
    }
    for key, label, node_type, signal, nominal, expected in NODES:
        terminal = terminals.get(label if label in terminals else key.replace("_", "-"))
        if key == "TB23_14":
            terminal = terminals.get("TB23-14")
        elif key == "TB23_16":
            terminal = terminals.get("TB23-16")
        component = components.get(key) or components.get(key.split("_")[0])
        wire = wires.get("W-105") if key == "W105" else None
        x, y = layout.get(key, (0, 0))
        node = CircuitNode(
            project_id=project.id, key=key, label=label, node_type=node_type,
            component_id=component.id if component else None,
            terminal_id=terminal.id if terminal else None,
            wire_id=wire.id if wire else None,
            controller_id=controller.id if signal else None,
            controller_signal=signal, nominal_voltage_v=nominal,
            x=float(x), y=float(y), confidence=1.0, verified=True,
            attributes={"expected_voltage_v": expected} if expected is not None else {},
        )
        db.add(node)
        db.flush()
        nodes[key] = node

        # Nodes that are not terminals still need an expectation for the
        # comparison engine; terminals carry theirs on the Terminal row.
        if terminal is None and expected is not None:
            synthetic = Terminal(
                project_id=project.id, tag=f"{key}_PT", block=key, number="",
                description=f"Measurement point at {label}",
                expected_voltage_v=expected, expected_reference="0V_RETURN",
                expected_tolerance_pct=10.0, expected_signal_type="DC",
                confidence=1.0, verified=True,
            )
            db.add(synthetic)
            db.flush()
            node.terminal_id = synthetic.id

    for from_key, to_key, edge_type, wire_number in EDGES:
        db.add(CircuitEdge(
            project_id=project.id,
            from_node_id=nodes[from_key].id, to_node_id=nodes[to_key].id,
            edge_type=edge_type, wire_id=wires[wire_number].id if wire_number in wires else None,
            label=wire_number, confidence=1.0, verified=True,
        ))

    db.add(Connection(
        project_id=project.id, wire_id=wires["W-105"].id,
        from_terminal_id=terminals["TB23-14"].id, to_terminal_id=terminals["TB23-16"].id,
        confidence=1.0, verified=True,
        notes="Demo connection record; the traversable model is the circuit graph.",
    ))
    return nodes


def _seed_gateway(db: Session, project: Project, nodes: dict[str, CircuitNode]) -> None:
    device = MeasurementDevice(
        project_id=project.id, name="DAQ-01", manufacturer="(simulated)", model="(simulated)",
        transport="MODBUS_TCP", host=None, port=None, unit_id=1, enabled=True,
        is_simulated=True, connection_state="ONLINE",
        options={"note": "Simulated measurement gateway — DEMO MODE."},
    )
    db.add(device)
    db.flush()

    now = utcnow()
    for index, (node_key, value, unit) in enumerate(DEMO_MEASUREMENTS, start=1):
        node = nodes[node_key]
        channel = MeasurementChannel(
            device_id=device.id, channel_tag=f"AI-{index:02d}",
            description=f"{node.label} with respect to 0 V control return",
            input_type="VOLTAGE_DC", max_rated_input=60.0, max_rated_input_unit="V",
            isolation_rating_v=300.0, isolated=True, signal_conditioning="DIRECT",
            conditioning_ratio=1.0, scale=1.0, offset=0.0, unit=unit,
            calibrated_at=now - timedelta(days=90),
            calibration_due_at=now + timedelta(days=275),
            calibration_reference="SIMULATED calibration record",
            circuit_node_id=node.id, terminal_id=node.terminal_id,
            nominal_circuit_voltage_v=24.0,
        )
        db.add(channel)
        db.flush()
        db.add(Measurement(
            project_id=project.id, channel_id=channel.id, circuit_node_id=node.id,
            terminal_id=node.terminal_id, value=value, unit=unit,
            quality=Quality.SIMULATED.value, source=DataSource.SIMULATED.value,
            method="SIM", instrument="DAQ-01 (simulated)", technician="DEMO",
            notes="Simulated measurement — DEMO MODE.",
            timestamp=now - timedelta(seconds=len(DEMO_MEASUREMENTS) - index),
        ))

    # A medium-voltage channel, to exercise the safety validation path.
    db.add(MeasurementChannel(
        device_id=device.id, channel_tag="AI-20",
        description="Generator bus voltage via PT1 secondary",
        input_type="VOLTAGE_AC", max_rated_input=150.0, max_rated_input_unit="V",
        isolation_rating_v=600.0, isolated=True, signal_conditioning="PT",
        conditioning_ratio=34.67, scale=1.0, offset=0.0, unit="V",
        calibrated_at=now - timedelta(days=30), calibration_due_at=now + timedelta(days=335),
        calibration_reference="SIMULATED calibration record",
        circuit_node_id=nodes["GEN_BUS"].id, nominal_circuit_voltage_v=4160.0,
    ))


def _seed_rules(db: Session) -> None:
    for rule in BUILTIN_RULES:
        exists = db.scalars(
            select(TroubleshootingRule).where(TroubleshootingRule.key == rule["key"],
                                              TroubleshootingRule.project_id.is_(None))
        ).first()
        if exists:
            continue
        db.add(TroubleshootingRule(
            project_id=None, key=rule["key"], name=rule["name"],
            fault_category=rule["fault_category"], priority=rule["priority"],
            conditions=rule["conditions"], conclusion=rule["conclusion"],
            enabled=True, source="built-in",
        ))


def status(db: Session) -> dict[str, Any]:
    from ..config import settings
    from ..protocols.simulator import FAULT_MODES, SimulatorAdapter

    project = db.scalars(select(Project).where(Project.name == DEMO_PROJECT_NAME)).first()
    controllers = []
    if project:
        for c in db.scalars(select(Controller).where(Controller.project_id == project.id)):
            state = SimulatorAdapter.state_for(f"controller-{c.id}")
            controllers.append({
                "id": c.id, "name": c.name,
                "fault_mode": state.fault_mode if state else "NONE",
                "connection_state": str(c.connection_state),
            })
    return {
        "demo_mode": settings.demo_mode,
        "project_id": project.id if project else None,
        "project_name": project.name if project else None,
        "controllers": controllers,
        "available_faults": FAULT_MODES,
        "banner": "DEMO MODE — ALL VALUES SIMULATED",
    }
