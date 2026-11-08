"""OHM-DC-2000-SLD-001: preliminary single-line diagram, generated from the master configuration.

Every rating on the sheet is read from the configuration, so the drawing cannot drift from the calculations. It is a concept diagram: it shows the architecture
and the preliminary ratings, not a verified design. Fault levels and device ratings are NOT shown as values because they are not verified (the sheet says so).
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from ohmetry_dc.models import ProjectConfig

W, H = 1700, 1180
INK, MUTE, ACC = "#0e171e", "#5b6770", "#b04a00"


def _t(x, y, text, size=13, anchor="middle", weight="normal", fill=INK, style=""):
    return f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}" {style}>{escape(str(text))}</text>'


def _line(x1, y1, x2, y2, w=2.2, dash=""):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{INK}" stroke-width="{w}" {f"stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>'


def _bus(x, y, w, label, tag, sub=""):
    return [f'<rect x="{x - w // 2}" y="{y - 5}" width="{w}" height="10" fill="{INK}"/>', _t(x - w // 2, y - 12, f"{tag}", 13, "start", "bold"), _t(x - w // 2, y + 24, label, 12, "start", fill=MUTE),
            *( [_t(x - w // 2, y + 40, sub, 11, "start", fill=ACC)] if sub else [])]


def _breaker(x, y, tag, label=""):
    return [f'<rect x="{x - 9}" y="{y - 9}" width="18" height="18" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', _t(x + 16, y + 4, tag, 12, "start", "bold"), *( [_t(x + 16, y + 19, label, 11, "start", fill=MUTE)] if label else [])]


def _tx(x, y, tag, l1, l2=""):
    return [f'<circle cx="{x}" cy="{y - 11}" r="20" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', f'<circle cx="{x}" cy="{y + 11}" r="20" fill="#fff" stroke="{INK}" stroke-width="2.2"/>',
            _t(x + 34, y - 6, tag, 13, "start", "bold"), _t(x + 34, y + 10, l1, 12, "start", fill=MUTE), *( [_t(x + 34, y + 25, l2, 11, "start", fill=ACC)] if l2 else [])]


def _gen(x, y, tag, l1):
    return [f'<circle cx="{x}" cy="{y}" r="22" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', _t(x, y + 5, "G", 16, "middle", "bold"), _t(x, y + 40, tag, 12, "middle", "bold"), _t(x, y + 54, l1, 11, "middle", fill=MUTE)]


def _box(x, y, w, h, tag, l1, l2=""):
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', _t(x + w / 2, y + 22, tag, 14, "middle", "bold"), _t(x + w / 2, y + 40, l1, 12, "middle", fill=MUTE),
            *( [_t(x + w / 2, y + 56, l2, 11, "middle", fill=ACC)] if l2 else [])]


def _path(cfg: ProjectConfig, p: str, cx: int) -> list[str]:
    v = cfg.value
    mv, lv = v("electrical_system.mv_supply_voltage"), v("electrical_system.lv_line_voltage")
    n_g = int(v("equipment.generator_quantity_per_path"))
    z = v("equipment.transformer_impedance")
    o: list[str] = []
    o += [f'<circle cx="{cx}" cy="86" r="16" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', _t(cx + 28, 82, f"Utility supply, path {p}", 13, "start", "bold"),
          _t(cx + 28, 98, f"{mv} kV, {v('electrical_system.frequency')} Hz (utility data pending)", 11, "start", fill=ACC)]
    o += [_line(cx, 102, cx, 138)] + _breaker(cx, 147, f"MV-CB-{p}", "MV incomer") + [_line(cx, 156, cx, 198)]
    o += _bus(cx, 203, 150, f"{mv} kV", f"MV-SWG-{p}")
    o += [_line(cx, 208, cx, 252), _t(cx + 8, 246, f"CAB-MV-{p}", 11, "start", fill=MUTE)]
    o += _tx(cx, 285, f"TX-{p}1", f"{v('equipment.transformer_rating'):,} kVA, {mv}/{lv/1000:g} kV, Z {z} %", "Preliminary rating and impedance")
    o += [_line(cx, 317, cx, 372), _t(cx + 8, 345, f"BD-TX-{p} busduct", 11, "start", fill=MUTE)]
    o += _breaker(cx, 381, f"ACB-TX-{p}", "LV incomer") + [_line(cx, 390, cx, 438)]
    o += _bus(cx, 443, 520, f"LV main switchboard, {lv:g} V, 3-phase", f"LV-MSB-{p}", "Fault level: NOT CALCULATED (utility data pending)")
    # generators (left of the LV bus)
    gx = cx - 190
    o += [_line(gx, 448, gx, 520)] + _breaker(gx, 530, f"ACB-GEN-{p}", "generator breaker") + [_line(gx, 539, gx, 575)]
    o += _bus(gx, 580, 230, f"Generator bus ({n_g} x parallel)", f"GENBUS-{p}")
    for i in range(n_g):
        x = gx - 85 + i * 85
        o += [_line(x, 585, x, 640)] + _gen(x, 662, f"GEN-{p}{i + 1}", f"{v('equipment.generator_rating'):,} kVA")
    o += [_t(gx - 120, 745, f"Rating assumed PRP, NOT confirmed. N+1 per path.", 11, "start", fill=ACC)]
    # UPS (right of centre)
    ux = cx + 130
    o += [_line(ux, 448, ux, 500)] + _breaker(ux, 509, f"ACB-UPS-IN-{p}", "UPS input") + [_line(ux, 518, ux, 556)] + _box(ux - 62, 556, 124, 62, f"UPS-{p}1", f"{v('equipment.ups_rating'):,.0f} kW / {v('equipment.ups_rating_kva'):,.0f} kVA", f"{v('equipment.ups_efficiency')} % (preliminary)")
    o += [_line(ux - 30, 618, ux - 30, 668)] + _box(ux - 92, 668, 124, 46, f"BAT-{p}1", "Not sized", "no discharge data")
    o += [_line(ux + 40, 618, ux + 40, 760), _t(ux + 48, 742, f"CAB-UPS-OUT-{p}", 11, "start", fill=MUTE)]
    o += _bus(ux + 40, 765, 230, f"IT distribution {p}", f"IT-DIST-{p}")
    o += [_line(ux + 40, 770, ux + 40, 815)] + _box(ux - 22, 815, 124, 56, f"IT LOAD {p}", f"{v('general.it_critical_load'):,} kW total (2N, both paths)")
    # mechanical feeder (far right)
    mx = cx + 262
    o += [_line(mx, 448, mx, 640)] + [_t(mx + 8, 560, f"CAB-MECH-{p}", 11, "start", fill=MUTE)] + _box(mx - 62, 640, 124, 58, f"MECH {p}", "Cooling plant", "load model")
    return o


def build_single_line_svg(cfg: ProjectConfig, generated: str, drawing_no: str = "OHM-DC-2000-SLD-001") -> str:
    parts: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">', f'<rect width="{W}" height="{H}" fill="#fff"/>',
                        f'<rect x="12" y="12" width="{W - 24}" height="{H - 24}" fill="none" stroke="{INK}" stroke-width="2"/>']
    parts += [f'<rect x="12" y="12" width="{W - 24}" height="34" fill="{ACC}"/>',
              _t(W / 2, 36, "PRELIMINARY CONCEPT DIAGRAM: NOT FOR CONSTRUCTION. NOT VERIFIED. ALL RATINGS ARE PRELIMINARY ASSUMPTIONS.", 16, "middle", "bold", "#fff")]
    parts += _path(cfg, "A", 330) + _path(cfg, "B", 1180)
    parts += [_t(330, 68, "PATH A", 20, "middle", "bold", MUTE), _t(1180, 68, "PATH B", 20, "middle", "bold", MUTE)]
    parts += [_line(760, 70, 760, 880, 1.4, "6 6"), _t(760, 905, "No electrical tie between paths (2N). Path independence of the two utility supplies is a design decision, not shown.", 11, "middle", fill=MUTE)]
    parts += [_t(W / 2, 925, "Equipment in path B is identical to path A (assumed by symmetry). Dual-corded IT loads are fed from both IT distribution boards.", 11, "middle", fill=MUTE)]
    # title block
    y0 = 960
    parts += [f'<rect x="24" y="{y0}" width="{W - 48}" height="190" fill="none" stroke="{INK}" stroke-width="1.5"/>', _line(24, y0 + 40, W - 24, y0 + 40, 1), _line(1060, y0, 1060, y0 + 190, 1)]
    parts += [_t(40, y0 + 27, "OHMETRY 2 MW DATA CENTRE: PRELIMINARY SINGLE-LINE DIAGRAM", 17, "start", "bold"), _t(1076, y0 + 27, f"Drawing {drawing_no}   Rev {cfg.project.revision}", 15, "start", "bold")]
    notes = ["1. Generated from the master configuration. Every rating shown is a PRELIMINARY ASSUMPTION or UNVERIFIED PLACEHOLDER (see the registers).",
             "2. Fault levels, device ratings, cable sizes, settings and earthing are NOT shown: not calculated or not verified (data pending).",
             "3. Generator basis (ISO 8528 PRP) assumed, not confirmed. Battery not sized. Open transition is a design decision.",
             "4. Educational and reference use only. Independent review and manufacturer data are needed before any project use."]
    for i, n in enumerate(notes):
        parts.append(_t(40, y0 + 66 + i * 26, n, 12, "start"))
    meta = [("Project", cfg.project.code), ("Revision", cfg.project.revision), ("Release state", cfg.project.release_state.value), ("Generated", generated), ("Drawn / checked / approved", "not assigned / not assigned / not assigned")]
    for i, (a, b) in enumerate(meta):
        parts += [_t(1076, y0 + 66 + i * 26, f"{a}:", 12, "start", "bold"), _t(1290, y0 + 66 + i * 26, b, 12, "start")]
    parts.append("</svg>")
    return "\n".join(parts)
