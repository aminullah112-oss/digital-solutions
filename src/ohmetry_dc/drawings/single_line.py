"""OHM-DC-2000-SLD-001: preliminary single-line diagram, generated from the master configuration.

Every rating on the sheet is read from the configuration, so the drawing cannot drift from the calculations. It is a concept diagram: it shows the architecture
and the preliminary ratings, not a verified design. Fault levels and device ratings are NOT shown as values because they are not verified (the sheet says so).

Revision A6 adds the architecture items a reviewer asked for, as CONCEPT symbols only: generator breakers, an interlock between the utility and generator
incomers, a power management system (PMS) for synchronising, load sharing and load shedding, UPS static and maintenance bypass, a battery isolator, and the
ownership and scope boundaries. None is a designed scheme and none carries a rating or a setting. Independence of the two utility supplies is NOT claimed.
"""
from __future__ import annotations

import textwrap
from xml.sax.saxutils import escape

from ohmetry_dc.models import ProjectConfig

W = 1700
INK, MUTE, ACC = "#0e171e", "#5b6770", "#b04a00"
CX = {"A": 345, "B": 1195}
MID = 770


def _t(x, y, text, size=13, anchor="middle", weight="normal", fill=INK, style=""):
    return f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}" {style}>{escape(str(text))}</text>'


def _line(x1, y1, x2, y2, w=2.2, dash="", color=INK):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}" {f"stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>'


def _poly(points, w=1.6, dash="5 4", color=MUTE):
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{w}" stroke-dasharray="{dash}"/>'


def _bus(x, y, w, label, tag, sub=""):
    return [f'<rect x="{x - w // 2}" y="{y - 5}" width="{w}" height="10" fill="{INK}"/>', _t(x - w // 2, y - 12, f"{tag}", 13, "start", "bold"), *([_t(x - w // 2, y + 24, label, 12, "start", fill=MUTE)] if label else []),
            *([_t(x - w // 2, y + 40, sub, 11, "start", fill=ACC)] if sub else [])]


def _breaker(x, y, tag, label=""):
    return [f'<rect x="{x - 9}" y="{y - 9}" width="18" height="18" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', _t(x + 16, y + 4, tag, 12, "start", "bold"), *([_t(x + 16, y + 19, label, 11, "start", fill=MUTE)] if label else [])]


def _tx(x, y, tag, l1, l2=""):
    return [f'<circle cx="{x}" cy="{y - 11}" r="20" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', f'<circle cx="{x}" cy="{y + 11}" r="20" fill="#fff" stroke="{INK}" stroke-width="2.2"/>',
            _t(x + 34, y - 6, tag, 13, "start", "bold"), _t(x + 34, y + 10, l1, 12, "start", fill=MUTE), *([_t(x + 34, y + 25, l2, 11, "start", fill=ACC)] if l2 else [])]


def _gen(x, y, tag, l1):
    return [f'<circle cx="{x}" cy="{y}" r="22" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', _t(x, y + 5, "G", 16, "middle", "bold"), _t(x, y + 40, tag, 12, "middle", "bold"), _t(x, y + 54, l1, 11, "middle", fill=MUTE)]


def _box(x, y, w, h, tag, l1, l2="", dash=""):
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="{INK}" stroke-width="2.2" {f"stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>', _t(x + w / 2, y + 22, tag, 14, "middle", "bold"),
            *([_t(x + w / 2, y + 40, l1, 12, "middle", fill=MUTE)] if l1 else []), *([_t(x + w / 2, y + 56, l2, 11, "middle", fill=ACC)] if l2 else [])]


def _switch(x, y, tag, l1):
    """Static bypass switch (concept symbol): a small box with a diagonal."""
    return [f'<rect x="{x - 13}" y="{y - 13}" width="26" height="26" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', f'<line x1="{x - 8}" y1="{y + 8}" x2="{x + 8}" y2="{y - 8}" stroke="{INK}" stroke-width="2"/>',
            _t(x + 22, y - 1, tag, 12, "start", "bold"), _t(x + 22, y + 14, l1, 11, "start", fill=MUTE)]


def _path(cfg: ProjectConfig, p: str, cx: int) -> list[str]:
    v = cfg.value
    mv, lv = v("electrical_system.mv_supply_voltage"), v("electrical_system.lv_line_voltage")
    n_g = int(v("equipment.generator_quantity_per_path"))
    z = v("equipment.transformer_impedance")
    o: list[str] = []
    # utility, with the ownership boundary
    o += [f'<circle cx="{cx}" cy="86" r="16" fill="#fff" stroke="{INK}" stroke-width="2.2"/>', _t(cx + 28, 82, f"Utility supply, path {p}", 13, "start", "bold"),
          _t(cx + 28, 98, f"{mv} kV, {v('electrical_system.frequency')} Hz (utility data pending)", 11, "start", fill=ACC)]
    o += [_line(cx, 102, cx, 138), _poly([(cx - 70, 119), (cx + 70, 119)], 1.4, "6 4", ACC), _t(cx + 78, 123, "Point of connection and ownership boundary: to be agreed with the utility", 10, "start", fill=ACC)]
    o += _breaker(cx, 147, f"MV-CB-{p}", "MV incomer") + [_line(cx, 156, cx, 198)]
    o += _bus(cx, 203, 150, f"{mv} kV", f"MV-SWG-{p}")
    o += [_line(cx, 208, cx, 252), _t(cx + 8, 246, f"CAB-MV-{p}", 11, "start", fill=MUTE)]
    o += _tx(cx, 285, f"TX-{p}1", f"{v('equipment.transformer_rating'):,} kVA, {mv}/{lv/1000:g} kV, Z {z} %", "Preliminary rating and impedance")
    o += [_line(cx, 317, cx, 372), _t(cx + 8, 345, f"BD-TX-{p} busduct", 11, "start", fill=MUTE)]
    o += _breaker(cx, 381, f"ACB-TX-{p}", "LV incomer") + [_line(cx, 390, cx, 438)]
    o += _bus(cx, 443, 620, "", f"LV-MSB-{p}") + [_t(cx - 310 + 80, 431, f"LV main switchboard, {lv:g} V, 3-phase", 11, "start", fill=MUTE)]
    o += [_t(cx + 318, 436, "Fault level:", 10, "start", fill=ACC), _t(cx + 318, 448, "NOT CALCULATED", 10, "start", "bold", ACC), _t(cx + 318, 460, "(utility data pending)", 10, "start", fill=ACC)]
    # generator system (left of the LV bus): per-unit breakers, generator bus, bus breaker
    gx = max(cx - 190, int(85 * (n_g - 1) / 2) + 60)
    gw = 85 * (n_g - 1) + 90
    o += [_line(gx, 448, gx, 520)] + _breaker(gx, 530, f"ACB-GEN-{p}", "generator bus breaker") + [_line(gx, 539, gx, 575)]
    o += _bus(gx, 580, gw, "", f"GENBUS-{p}") + [_t(gx + 12, 568, f"Generator bus ({n_g} x parallel)", 11, "start", fill=MUTE)]
    xs = [gx + int((i - (n_g - 1) / 2) * 85) for i in range(n_g)]
    for i, x in enumerate(xs):
        o += [_line(x, 585, x, 603)] + _breaker(x, 612, f"GCB-{p}{i + 1}") + [_line(x, 621, x, 640)] + _gen(x, 662, f"GEN-{p}{i + 1}", f"{v('equipment.generator_rating'):,} kVA")
    o += [_t(gx - gw // 2, 738, "Rating assumed PRP, NOT confirmed. N+1 per path.", 11, "start", fill=ACC)]
    # interlock between the utility incomer and the generator bus breaker (concept)
    o += [_poly([(cx - 9, 381), (cx - 322, 381), (cx - 322, 530), (gx - 9, 530)]), _t(cx - 312, 375, "Interlock ACB-TX / ACB-GEN (concept)", 10, "start", fill=ACC)]
    # PMS: synchronising, load sharing, load shedding (concept); dashed lines are control, not power
    o += [_poly([(xs[0], 748), (xs[-1], 748)])] + [_poly([(x, 742), (x, 748)]) for x in xs] + [_poly([(gx, 748), (gx, 775)])]
    o += _box(gx - 115, 775, 230, 68, f"PMS-{p} (concept)", "synchronising, load sharing", "load shedding: scheme not designed", dash="7 4")
    # UPS system (right of centre) with the vendor-scope boundary, battery isolator, static and maintenance bypass
    ux = cx + 150
    byx = cx + 20
    o += [_line(ux, 448, ux, 500)] + _breaker(ux, 509, f"ACB-UPS-IN-{p}", "UPS input") + [_line(ux, 518, ux, 556)]
    o += [_poly([(ux - 105, 546), (ux + 75, 546), (ux + 75, 806), (ux - 105, 806), (ux - 105, 546)], 1.4, "6 4", ACC), _t(ux - 100, 784, "UPS system boundary:", 10, "start", fill=ACC), _t(ux - 100, 796, "vendor scope, to be defined", 10, "start", fill=ACC)]
    o += _box(ux - 62, 556, 124, 62, f"UPS-{p}1", f"{v('equipment.ups_rating'):,.0f} kW / {v('equipment.ups_rating_kva'):,.0f} kVA", f"{v('equipment.ups_efficiency')} % (preliminary)")
    o += [_line(ux - 30, 618, ux - 30, 636)] + _breaker(ux - 30, 645, f"BAT-ISO-{p}") + [_t(ux - 14, 662, "isolator and", 10, "start", fill=ACC), _t(ux - 14, 673, "DC protection", 10, "start", fill=ACC), _t(ux - 14, 684, "(concept)", 10, "start", fill=ACC)]
    o += [_line(ux - 30, 654, ux - 30, 690)] + _box(ux - 92, 690, 124, 46, f"BAT-{p}1", "Not sized", "no discharge data")
    o += [_line(ux + 55, 618, ux + 55, 930), _t(ux + 63, 830, f"CAB-UPS-OUT-{p}", 11, "start", fill=MUTE)]
    # bypass: tapped from the UPS input, rejoining at the IT distribution board (common feed assumed)
    o += [_line(ux, 537, byx, 537), _line(byx, 537, byx, 930)]
    o += _switch(byx, 838, f"STS-{p}", "static bypass") + _breaker(byx, 872, f"MBB-{p}", "maintenance bypass") + [_line(byx, 930, ux + 55 - 115, 930)]
    o += _bus(ux + 55, 930, 230, f"IT distribution {p}", f"IT-DIST-{p}")
    # mechanical feeder (far right)
    mx = cx + 295
    o += [_line(mx, 448, mx, 640)] + [_t(mx + 8, 560, f"CAB-MECH-{p}", 11, "start", fill=MUTE)] + _box(mx - 62, 640, 124, 66, f"MECH {p}", "Cooling plant", "load model")
    return o


def _wrap(text: str, width: int = 190) -> list[tuple[int, str]]:
    lines = textwrap.wrap(text, width)
    return [(40, lines[0])] + [(58, ln) for ln in lines[1:]]


def build_single_line_svg(cfg: ProjectConfig, generated: str, drawing_no: str = "OHM-DC-2000-SLD-001") -> str:
    notes = ["1. Generated from the master configuration. Every rating shown is a PRELIMINARY ASSUMPTION or UNVERIFIED PLACEHOLDER (see the registers).",
             "2. Fault levels, device ratings, cable sizes, settings and earthing are NOT shown: not calculated or not verified (data pending).",
             "3. Generator basis (ISO 8528 PRP) assumed, not confirmed. Battery not sized. Open transition is a design decision. Closed transition and paralleling with the utility are not shown.",
             "4. Utility A and utility B are drawn as two supplies. Their independence (separate feeders, substations, upstream network) is NOT claimed and is not established.",
             "5. Interlock (concept): ACB-TX and ACB-GEN are shown as interlocked so that the generator bus cannot back-feed the transformer. The interlocking scheme is not designed.",
             "6. Generator paralleling and PMS (concept): each generator has a breaker (GCB) for synchronising. Synchronising, load sharing, load shedding and start/stop logic are functions of a PMS whose scheme, controller and communications are not designed.",
             "7. UPS (concept): static bypass (STS) and maintenance bypass (MBB) are shown, tapped from the UPS input; whether the bypass has its own feed is a design decision. Battery isolator and DC protection are not designed.",
             "8. Protection and metering boundaries: relays, current and voltage transformers, metering, protection zones and settings are not designed and not shown. The utility point of connection and the UPS vendor scope are boundaries to be agreed.",
             "9. Dual-corded IT load: a single load fed from both IT distribution boards. The path A and path B systems are otherwise separate (no tie shown).",
             "10. Educational and reference use only. Independent review and manufacturer data are needed before any project use."]
    wrapped = [ln for n in notes for ln in _wrap(n)]
    y0 = 1076
    H = y0 + 80 + len(wrapped) * 19 + 20
    parts: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">', f'<rect width="{W}" height="{H}" fill="#fff"/>',
                        f'<rect x="12" y="12" width="{W - 24}" height="{H - 24}" fill="none" stroke="{INK}" stroke-width="2"/>']
    parts += [f'<rect x="12" y="12" width="{W - 24}" height="34" fill="{ACC}"/>',
              _t(W / 2, 36, "PRELIMINARY CONCEPT DIAGRAM: NOT FOR CONSTRUCTION. NOT VERIFIED. ALL RATINGS ARE PRELIMINARY ASSUMPTIONS.", 16, "middle", "bold", "#fff")]
    parts += [_line(MID, 70, MID, 960, 1.4, "6 6")]
    parts += _path(cfg, "A", CX["A"]) + _path(cfg, "B", CX["B"])
    parts += [_t(CX["A"] - 30, 92, "PATH A", 20, "end", "bold", MUTE), _t(CX["B"] - 30, 92, "PATH B", 20, "end", "bold", MUTE)]
    # the single dual-corded IT load, fed from both IT distribution boards
    ax, bx = CX["A"] + 205, CX["B"] + 205
    parts += [_line(ax + 110, 935, ax + 110, 1005), _line(ax + 110, 1005, MID - 70, 1005), _line(bx + 110, 935, bx + 110, 1005), _line(bx + 110, 1005, MID + 70, 1005)]
    parts += _box(MID - 70, 976, 140, 66, "IT LOAD", f"{cfg.value('general.it_critical_load'):,} kW total", "dual-corded, both paths")
    parts += [_t(MID, 1062, "Only the dual-corded IT load is common to both paths. No electrical tie between the paths elsewhere. Independence of the two utility supplies is NOT claimed.", 11, "middle", fill=MUTE)]
    # title block
    hb = H - y0 - 24
    parts += [f'<rect x="24" y="{y0}" width="{W - 48}" height="{hb}" fill="none" stroke="{INK}" stroke-width="1.5"/>', _line(24, y0 + 40, W - 24, y0 + 40, 1), _line(1360, y0, 1360, y0 + hb, 1)]
    parts += [_t(40, y0 + 27, "OHMETRY 2 MW DATA CENTRE: PRELIMINARY SINGLE-LINE DIAGRAM", 17, "start", "bold"), _t(1376, y0 + 27, f"Drawing {drawing_no}   Rev {cfg.project.revision}", 15, "start", "bold")]
    for i, (nx, n) in enumerate(wrapped):
        parts.append(_t(nx, y0 + 64 + i * 19, n, 12, "start"))
    meta = [("Project", cfg.project.code), ("Revision", cfg.project.revision), ("Release state", cfg.project.release_state.value), ("Generated", generated), ("Drawn / checked / approved", "not assigned / not assigned / not assigned")]
    for i, (a, b) in enumerate(meta):
        parts += [_t(1376, y0 + 66 + i * 30, f"{a}:", 12, "start", "bold"), _t(1376, y0 + 82 + i * 30, b, 12, "start")]
    parts.append("</svg>")
    return "\n".join(parts)
