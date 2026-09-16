"""Schematic reading tests.

The sample drawing is a vector ladder diagram of the same generator breaker
close circuit the demo project builds by hand, so "did the reader understand
the drawing" has a concrete answer: does it reproduce the connectivity we know
is there, and does it refuse to invent the connectivity we know is not.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import net_builder, pdf_geometry, schematic_import

FIXTURE = Path(__file__).parent / "fixtures" / "sample_schematic.pdf"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="sample schematic fixture not generated"
)


@pytest.fixture(scope="module")
def page() -> pdf_geometry.PageGeometry:
    pages = pdf_geometry.extract(str(FIXTURE))
    assert pages, "pypdf not available or the fixture is unreadable"
    return pages[0]


@pytest.fixture(scope="module")
def result() -> dict:
    return schematic_import.run(str(FIXTURE), "application/pdf").as_dict()


def nets_of(result: dict) -> list[dict]:
    return [p for p in result["proposals"] if p["kind"] == "net"]


def net_containing(result: dict, key: str) -> dict | None:
    for proposal in nets_of(result):
        if key in [a["key"] for a in proposal["payload"]["attachments"]]:
            return proposal
    return None


# --- geometry -------------------------------------------------------------

def test_vector_page_yields_text_and_geometry(page):
    assert page.is_vector
    assert page.has_text
    assert page.width > 700 and page.height > 500


def test_device_outlines_are_separated_from_conductors(page):
    """A closed symbol outline is a device, not a length of wire."""
    assert len(page.devices) == 5, [d.size for d in page.devices]
    assert len(page.conductors) < len(page.segments)
    # Terminal markers are closed too, but small, so they stay conductors.
    assert any(not s.is_device for s in page.shapes)


def test_junction_dot_is_detected(page):
    assert len(page.junction_dots) == 1
    dot = page.junction_dots[0]
    assert abs(dot.x - 440.0) < 2 and abs(dot.y - 470.0) < 2


# --- the rule that matters ------------------------------------------------

def test_crossing_without_a_junction_dot_is_not_a_connection(result):
    """A conductor crosses both rungs. Only one crossing carries a dot.

    If the reader joined both, it has shorted the close command onto the close
    coil — a fault that does not exist, on a drawing that does not say so.
    """
    close_command_net = net_containing(result, "TB23-14")
    close_coil_net = net_containing(result, "TB23-16")
    assert close_command_net is not None
    assert close_coil_net is not None
    assert close_command_net["key"] != close_coil_net["key"]

    coil_side = {a["key"] for a in close_coil_net["payload"]["attachments"]}
    assert "TB23-14" not in coil_side
    assert "DO-07" not in coil_side


def test_crossing_with_a_junction_dot_is_a_connection(result):
    """The dotted crossing joins the vertical conductor to the close command."""
    command_net = net_containing(result, "TB23-14")
    assert command_net is not None
    attached = {a["key"] for a in command_net["payload"]["attachments"]}
    assert "TB23-20" in attached, attached


def test_devices_break_the_conductor(result):
    """The fuse sits in the run, so the conductors either side are not one net.

    Tracing straight through a component would hide the very break a
    technician is looking for.
    """
    supply_net = net_containing(result, "F7")
    assert supply_net is not None
    command_net = net_containing(result, "TB23-14")
    assert command_net is not None
    assert supply_net["key"] != command_net["key"]


def test_controller_output_and_coil_are_on_one_conductor(result):
    """DO-07 -> TB23-14 -> K12 coil is what the drawing shows."""
    command_net = net_containing(result, "TB23-14")
    attached = {a["key"] for a in command_net["payload"]["attachments"]}
    assert {"DO-07", "K12", "TB23-14"} <= attached, attached


# --- labels and provenance ------------------------------------------------

def test_wire_labels_bind_to_the_conductor_they_name(result):
    """A label near a crossing conductor must not be claimed by it."""
    coil_net = net_containing(result, "TB23-16")
    candidates = set(coil_net["payload"].get("conflicting_wire_numbers") or []) \
        | {coil_net["payload"]["wire_number"]}
    # W-200 names the vertical conductor that crosses this rung without a dot.
    assert coil_net["payload"]["wire_number"] in ("W-111", "W-112")
    assert "W-200" not in candidates, candidates


def test_conflicting_wire_numbers_are_surfaced_not_resolved(result):
    """One conductor carrying two numbers is reported for a reviewer."""
    flagged = [n for n in nets_of(result)
               if n["payload"].get("conflicting_wire_numbers")]
    assert flagged
    for net in flagged:
        assert "more than one wire number" in net["basis"]


def test_every_proposal_carries_confidence_and_basis(result):
    for proposal in result["proposals"]:
        assert proposal["confidence_band"] in ("HIGH", "MEDIUM", "LOW")
        assert proposal["basis"], proposal
        assert proposal["verified"] is False


def test_nothing_is_auto_accepted(result):
    assert result["requires_review"] is True
    assert "Review and accept" in result["note"]


def test_terminals_and_components_are_read(result):
    keys = {(p["kind"], p["key"]) for p in result["proposals"]}
    for tag in ("TB23-14", "TB23-16", "TB23-20"):
        assert ("terminal", tag) in keys, keys
    for designator in ("F7", "K12", "CB1", "DO-07"):
        assert ("component", designator) in keys, keys


def test_raster_input_reports_that_connectivity_cannot_be_traced():
    """A scan has no geometry. Say so; do not guess connectivity from it."""
    result = schematic_import.run("/nonexistent.png", "image/png").as_dict()
    stages = {entry["stage"]: entry for entry in result["log"]}
    assert stages["line_tracing"]["status"] == "UNAVAILABLE"
    assert stages["net_tracing"]["status"] == "UNAVAILABLE"
    assert "no connectivity could be traced" in result["note"]


def test_capabilities_do_not_overclaim():
    caps = schematic_import.capabilities()
    assert "vector" in caps["line_tracing"].lower()
    assert caps["symbol_detection"].startswith("PARTIAL")
    assert "junction dot" in caps["net_tracing"]


# --- net builder units ----------------------------------------------------

def test_net_confidence_penalises_lone_unlabelled_fragments():
    segment = pdf_geometry.Segment(0, 0, 40, 0)
    lone = net_builder.Net(id=1, segments=[segment])
    assert net_builder.net_confidence(lone) < 0.3


# --- end to end through the API -------------------------------------------

def test_upload_review_accept_then_trace(client, auth, demo_project):
    """Upload a real drawing, accept the traced conductors, trace the result.

    This is the whole point of the feature: a drawing goes in and a
    technician can trace a circuit out of it.
    """
    pid = demo_project["project_id"]

    upload = client.post(
        "/api/schematics/upload",
        headers=auth,
        files={"file": ("E-4412.pdf", FIXTURE.read_bytes(), "application/pdf")},
        data={"project_id": str(pid), "name": "E-4412 close circuit",
              "drawing_number": "E-4412", "revision": "B"},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()

    assert body["pages"][0]["is_vector"] is True
    assert body["pages"][0]["conductors"] > 0
    assert body["counts"]["net"] >= 4
    assert body["requires_review"] is True

    accepted = [p for p in body["proposals"]
                if p["kind"] in ("net", "terminal", "component")]
    response = client.post(f"/api/schematics/{body['schematic_id']}/accept",
                           headers=auth, json=accepted)
    assert response.status_code == 200, response.text
    created = response.json()["created"]
    assert created["nets"] >= 4
    assert created["connections"] >= 8

    # The imported conductor must now be traceable, and the trace must stop
    # where the drawing says it stops.
    trace = client.get(f"/api/circuits/{pid}/trace/TB23_14?direction=both&max_depth=4",
                       headers=auth).json()
    keys = {n["key"] for n in trace["nodes"]}
    assert "DO_07" in keys, keys
    # TB23_16 sits on the other rung, reachable only through the K12 relay,
    # never through the undotted crossing.
    path_to_coil = client.get(
        f"/api/circuits/{pid}/path?from_key=TB23_14&to_key=TB23_16", headers=auth).json()
    if path_to_coil["found"]:
        hops = [n["key"] for n in path_to_coil["path"]]
        assert any(h.startswith("K12") for h in hops), hops


def test_accepted_schematic_objects_are_marked_verified(client, auth, demo_project):
    pid = demo_project["project_id"]
    circuit = client.get(f"/api/circuits/{pid}?include_status=false", headers=auth).json()
    imported = [n for n in circuit["nodes"] if n["key"].startswith("W_")]
    assert imported, "expected imported wire nodes"
    assert all(n["verified"] for n in imported)
