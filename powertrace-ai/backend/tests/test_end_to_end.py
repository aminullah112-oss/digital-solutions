"""End-to-end walk through the demo panel.

Seeds the demo project, reads live simulated data, injects a breaker
fail-to-close fault, traces the close circuit, opens a diagnostic session and
generates a report — the path a technician actually takes.
"""
from __future__ import annotations

import time


def test_health_reports_no_control_writes(client):
    body = client.get("/api/health").json()
    assert body["control_writes_enabled"] is False


def test_demo_seed_creates_a_marked_demo_project(client, auth, demo_project):
    project = client.get(f"/api/projects/{demo_project['project_id']}", headers=auth).json()
    assert project["is_demo"] is True
    assert "DEMO" in project["name"]


def test_simulated_controllers_poll_and_tag_their_values(client, auth, demo_project):
    controllers = client.get(
        f"/api/controllers?project_id={demo_project['project_id']}", headers=auth).json()
    assert len(controllers) == 2
    controller_id = controllers[0]["id"]

    for _ in range(60):
        live = client.get(f"/api/controllers/{controller_id}/live-data", headers=auth).json()
        if live["values"]:
            break
        time.sleep(0.1)

    assert live["values"], "poller produced no values"
    voltage = live["values"]["voltage_L1_L2"]
    assert voltage["source"] == "SIMULATED"
    assert voltage["quality"] == "SIMULATED"
    assert voltage["unit"] == "V"
    assert live["register_map"]["simulator_only"] is True
    assert live["register_map"]["verified"] is False


def test_circuit_graph_traces_the_close_circuit(client, auth, demo_project):
    pid = demo_project["project_id"]
    circuit = client.get(f"/api/circuits/{pid}", headers=auth).json()
    assert circuit["node_count"] >= 15

    trace = client.get(f"/api/circuits/{pid}/trace/EMCP_DO07?direction=down",
                       headers=auth).json()
    keys = [n["key"] for n in trace["nodes"]]
    assert keys[0] == "EMCP_DO07"
    for expected in ("W105", "TB23_14", "K12_COIL"):
        assert expected in keys, f"{expected} missing from downstream trace: {keys}"


def test_terminal_status_separates_controller_from_measurement(client, auth, demo_project):
    pid = demo_project["project_id"]
    node = client.get(f"/api/circuits/{pid}/node/EMCP_DO07", headers=auth).json()
    status = node["status"]
    assert status["expected"]["source"] == "EXPECTATION"
    assert status["measured"]["source"] in ("MEASURED", "SIMULATED")
    assert status["controller"]["signal"] == "DO_07"
    assert "not a measurement" in status["controller"]["note"]


def test_unmeasured_point_reads_not_measured(client, auth, demo_project):
    """CB1 has no measurement bound to it, so it must not claim a status."""
    pid = demo_project["project_id"]
    node = client.get(f"/api/circuits/{pid}/node/CB1", headers=auth).json()
    assert node["status"]["status"] in ("NOT MEASURED", "NO EXPECTATION")
    assert node["status"]["overlay_color"] == "GRAY"


def test_medium_voltage_nodes_carry_the_safety_notice(client, auth, demo_project):
    pid = demo_project["project_id"]
    node = client.get(f"/api/circuits/{pid}/node/GEN_BUS", headers=auth).json()
    assert node["medium_voltage"] is True
    assert "APPROPRIATELY RATED TEST EQUIPMENT" in node["safety_notice"]


def test_discontinuity_is_localized_between_two_measurements(client, auth, demo_project):
    pid = demo_project["project_id"]
    result = client.get(f"/api/diagnostics/evaluate/{pid}", headers=auth).json()
    segments = result["discontinuities"]
    assert segments, "expected a measured discontinuity in the demo panel"
    pairs = {tuple(s["between"]) for s in segments}
    assert ("CTRL_BUS", "K12_CONTACT") in pairs or ("K12_COIL", "K12_CONTACT") in pairs, pairs
    assert all(s["confidence"] == "CONFIRMED_BY_MEASUREMENT" for s in segments)


def test_rules_fire_on_the_demo_fault(client, auth, demo_project):
    pid = demo_project["project_id"]
    controllers = client.get(f"/api/controllers?project_id={pid}", headers=auth).json()
    cid = controllers[0]["id"]

    client.post(f"/api/demo/fault?controller_id={cid}&mode=BREAKER_FAIL_TO_CLOSE",
                headers=auth)
    for _ in range(60):
        live = client.get(f"/api/controllers/{cid}/live-data", headers=auth).json()
        if live["values"].get("breaker_close_command", {}).get("value") is True:
            break
        time.sleep(0.1)

    result = client.get(
        f"/api/diagnostics/evaluate/{pid}?fault_category=BREAKER_FAIL_TO_CLOSE",
        headers=auth).json()
    keys = {f["rule_key"] for f in result["findings"]}
    assert "coil_energized_contact_dead" in keys
    finding = next(f for f in result["findings"] if f["rule_key"] == "coil_energized_contact_dead")
    assert finding["confidence"] == "CONFIRMED_BY_MEASUREMENT"
    assert finding["evidence"]


def test_command_without_measurement_is_unverified(client, auth, demo_project):
    pid = demo_project["project_id"]
    result = client.get(
        f"/api/diagnostics/evaluate/{pid}?fault_category=BREAKER_FAIL_TO_CLOSE",
        headers=auth).json()
    finding = next((f for f in result["findings"]
                    if f["rule_key"] == "command_present_feedback_absent"), None)
    if finding:
        assert finding["confidence"] == "UNVERIFIED"


def test_fault_tree_marks_branches_from_evidence(client, auth, demo_project):
    pid = demo_project["project_id"]
    tree = client.get(
        f"/api/diagnostics/fault-tree/{pid}?fault_category=BREAKER_FAIL_TO_CLOSE",
        headers=auth).json()
    labels = {c["id"]: c for c in tree["children"]}
    assert labels["wiring_discontinuity"]["status"] == "SUSPECT"
    assert tree["status"] == "SUSPECT"


def test_diagnostic_session_generates_a_circuit_specific_procedure(client, auth, demo_project):
    pid = demo_project["project_id"]
    session = client.post("/api/diagnostics", headers=auth, json={
        "project_id": pid, "title": "Generator breaker failed to close",
        "fault_category": "BREAKER_FAIL_TO_CLOSE",
        "symptom": "Close command issued, breaker does not close.",
        "technician": "test", "start_node_key": "EMCP_DO07",
    }).json()

    assert session["steps"], "no procedure generated"
    titles = [s["title"] for s in session["steps"]]
    assert any("K12" in t for t in titles), titles
    measuring = [s for s in session["steps"] if s["requires_measurement"]]
    assert measuring
    assert all("APPROPRIATELY RATED TEST EQUIPMENT" in s["safety_notice"] for s in measuring)

    failing = [s for s in session["steps"] if s["status"] == "FAIL"]
    assert failing, "expected the dead contact to fail a step"


def test_report_exports_carry_provenance_and_disclaimer(client, auth, demo_project):
    pid = demo_project["project_id"]
    session = client.post("/api/diagnostics", headers=auth, json={
        "project_id": pid, "title": "Report test", "fault_category": "BREAKER_FAIL_TO_CLOSE",
    }).json()
    created = client.post("/api/reports", headers=auth, json={
        "project_id": pid, "diagnostic_session_id": session["id"], "technician": "test",
    }).json()

    body = client.get(f"/api/reports/{created['id']}?format=json", headers=auth).json()
    assert "not a safety-rated protection system" in body["disclaimer"]
    assert body["project"]["is_demo"] is True
    measured = [m for m in body["measurements"] if m.get("measured")]
    assert measured and all(m["measured"]["source"] in ("MEASURED", "SIMULATED")
                            for m in measured)

    csv_body = client.get(f"/api/reports/{created['id']}?format=csv", headers=auth).text
    assert "measurement," in csv_body
    html_body = client.get(f"/api/reports/{created['id']}?format=html", headers=auth).text
    assert "DEMO MODE" in html_body


def test_communication_loss_is_visible_not_silent(client, auth, demo_project):
    pid = demo_project["project_id"]
    controllers = client.get(f"/api/controllers?project_id={pid}", headers=auth).json()
    cid = controllers[1]["id"]
    client.post(f"/api/demo/fault?controller_id={cid}&mode=COMMUNICATION_LOSS", headers=auth)

    for _ in range(80):
        controller = client.get(f"/api/controllers/{cid}", headers=auth).json()
        if controller["connection_state"] == "ERROR":
            break
        time.sleep(0.1)
    assert controller["connection_state"] == "ERROR"
    assert controller["last_error"]

    live = client.get(f"/api/controllers/{cid}/live-data", headers=auth).json()
    assert live["values"] == {}, "stale values must not be shown as live after comms loss"


def test_register_map_cannot_be_verified_without_a_source_document(client, auth):
    created = client.post("/api/register-maps", headers=auth, json={
        "name": "Test map", "controller_type": "TEST", "registers": [],
    }).json()
    response = client.post(
        f"/api/register-maps/{created['id']}/verify?verified_by=test", headers=auth)
    assert response.status_code == 422
    assert "source_document" in response.text


def test_register_import_rejects_write_function_codes(client, auth):
    created = client.post("/api/register-maps", headers=auth, json={
        "name": "Write map", "controller_type": "TEST",
    }).json()
    csv_body = ("parameter_name,address,function_code,data_type\n"
                "some_value,40001,6,UINT16\n")
    response = client.post(
        f"/api/register-maps/{created['id']}/import",
        headers=auth,
        files={"file": ("map.csv", csv_body, "text/csv")},
    )
    assert response.status_code == 422
    assert "read function codes" in response.text


def test_measurement_channel_config_is_refused_for_direct_mv(client, auth, demo_project):
    devices = client.get(
        f"/api/measurements/devices?project_id={demo_project['project_id']}",
        headers=auth).json()
    response = client.post("/api/measurements/channels", headers=auth, json={
        "device_id": devices[0]["id"], "channel_tag": "AI-99",
        "input_type": "VOLTAGE_AC", "signal_conditioning": "DIRECT",
        "nominal_circuit_voltage_v": 4160.0, "max_rated_input": 600.0,
        "isolation_rating_v": 600.0,
    })
    assert response.status_code == 422
    assert "DIRECT_CONNECTION_REFUSED" in response.text


def test_search_finds_circuit_objects(client, auth, demo_project):
    results = client.get("/api/search?q=K12", headers=auth).json()
    titles = {r["title"] for r in results["results"]}
    assert "K12" in titles or "K12_COIL" in titles


def test_ai_layer_is_honest_when_unconfigured(client, auth, demo_project):
    pid = demo_project["project_id"]
    session = client.post("/api/diagnostics", headers=auth, json={
        "project_id": pid, "title": "AI test", "fault_category": "BREAKER_FAIL_TO_CLOSE",
    }).json()
    analysis = client.post(f"/api/diagnostics/{session['id']}/ai", headers=auth).json()
    assert analysis["status"] == "UNAVAILABLE"
    assert "deterministic" in analysis["reason"]


def test_viewer_role_cannot_configure_controllers(client, auth, demo_project):
    client.post("/api/auth/users", headers=auth, json={
        "email": "viewer@test.local", "password": "viewerpassword", "role": "VIEWER",
    })
    token = client.post("/api/auth/token", json={
        "email": "viewer@test.local", "password": "viewerpassword"}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/dashboard", headers=viewer).status_code == 200
    response = client.post("/api/controllers", headers=viewer, json={
        "project_id": demo_project["project_id"], "name": "Nope",
        "protocol": {"protocol": "MODBUS_TCP", "host": "192.0.2.5"},
    })
    assert response.status_code == 403
