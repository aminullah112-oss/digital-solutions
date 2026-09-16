"""Generate a vector control schematic for testing the import pipeline.

This produces the same close circuit the demo project seeds by hand, drawn as
a ladder diagram in a vector PDF — the format an AutoCAD Electrical, EPLAN or
SEE Electrical export actually has. Importing it should reconstruct the
connectivity that was built by hand, which is the only honest way to test a
schematic reader.

It deliberately includes the case that separates a working reader from a
dangerous one: a conductor crossing two rungs, joined to one by a junction dot
and merely crossing the other. A reader that joins both has invented a short.

    python tools/make_sample_schematic.py out.pdf
"""
from __future__ import annotations

import sys

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

WIDTH, HEIGHT = landscape(letter)

RAIL_LEFT_X = 70.0
RAIL_RIGHT_X = 720.0
RAIL_TOP = 520.0
RAIL_BOTTOM = 150.0

RUNG_A_Y = 470.0   # close command: controller output -> K12 coil
RUNG_B_Y = 330.0   # close coil: K12 contact -> CB1 close coil
CROSS_X = 440.0    # a conductor crossing both rungs


def device(c: pdfcanvas.Canvas, x0: float, y0: float, x1: float, y1: float,
           label: str, sub: str = "") -> None:
    """A device symbol: a closed outline, which breaks the conductor."""
    c.setLineWidth(1.0)
    c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x0 + 2, y1 + 3, label)
    if sub:
        c.setFont("Helvetica", 5.5)
        c.drawString(x0 + 2, y0 - 7, sub)


def terminal(c: pdfcanvas.Canvas, x: float, y: float, tag: str) -> None:
    """A terminal marker: a small closed outline that does not break the
    conductor, plus its tag."""
    c.setLineWidth(0.7)
    c.circle(x, y, 2.4, stroke=1, fill=0)
    c.setFont("Helvetica", 6.5)
    c.drawString(x - 16, y + 7, tag)


def wire(c: pdfcanvas.Canvas, x0: float, y0: float, x1: float, y1: float,
         number: str = "") -> None:
    c.setLineWidth(0.9)
    c.line(x0, y0, x1, y1)
    if number:
        c.setFont("Helvetica", 6)
        if abs(y1 - y0) < 0.5:
            c.drawString((x0 + x1) / 2 - 10, y0 + 4, number)
        else:
            c.drawString(x0 + 4, (y0 + y1) / 2, number)


def junction_dot(c: pdfcanvas.Canvas, x: float, y: float) -> None:
    """The drawing's explicit statement that conductors here are joined."""
    c.circle(x, y, 1.8, stroke=0, fill=1)


def build(path: str) -> None:
    c = pdfcanvas.Canvas(path, pagesize=(WIDTH, HEIGHT))
    c.setTitle("PPU34 generator breaker close circuit")

    # Title block
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, HEIGHT - 40, "PPU34 — GENERATOR BREAKER CLOSE CIRCUIT")
    c.setFont("Helvetica", 7)
    c.drawString(40, HEIGHT - 52, "DRAWING E-4412   REV B   SHEET 12 OF 40   24 VDC CONTROL")
    c.setFont("Helvetica", 6)
    c.drawString(40, 40, "SAMPLE DRAWING GENERATED FOR TESTING THE POWERTRACE AI IMPORT "
                         "PIPELINE. NOT A REAL INSTALLATION.")

    # Supply rails
    c.setLineWidth(1.3)
    c.line(RAIL_LEFT_X, RAIL_BOTTOM, RAIL_LEFT_X, RAIL_TOP)
    c.line(RAIL_RIGHT_X, RAIL_BOTTOM, RAIL_RIGHT_X, RAIL_TOP)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(RAIL_LEFT_X - 12, RAIL_TOP + 8, "+24 VDC")
    c.drawString(RAIL_RIGHT_X - 8, RAIL_TOP + 8, "0 V")

    # --- Rung A: close command ------------------------------------------
    wire(c, RAIL_LEFT_X, RUNG_A_Y, 150, RUNG_A_Y, "W-101")
    device(c, 150, RUNG_A_Y - 8, 190, RUNG_A_Y + 8, "F7", "3A")
    wire(c, 190, RUNG_A_Y, 300, RUNG_A_Y, "W-102")
    device(c, 300, RUNG_A_Y - 20, 380, RUNG_A_Y + 20, "DO-07", "EMCP OUTPUT")
    wire(c, 380, RUNG_A_Y, 470, RUNG_A_Y, "W-105")
    terminal(c, 470, RUNG_A_Y, "TB23-14")
    wire(c, 470, RUNG_A_Y, 560, RUNG_A_Y, "W-106")
    device(c, 560, RUNG_A_Y - 15, 620, RUNG_A_Y + 15, "K12", "CLOSE RELAY COIL")
    wire(c, 620, RUNG_A_Y, RAIL_RIGHT_X, RUNG_A_Y, "W-107")

    # --- Rung B: breaker close coil --------------------------------------
    wire(c, RAIL_LEFT_X, RUNG_B_Y, 200, RUNG_B_Y, "W-110")
    device(c, 200, RUNG_B_Y - 8, 250, RUNG_B_Y + 8, "K12", "CONTACT 13-14")
    wire(c, 250, RUNG_B_Y, 380, RUNG_B_Y, "W-111")
    terminal(c, 380, RUNG_B_Y, "TB23-16")
    wire(c, 380, RUNG_B_Y, 500, RUNG_B_Y, "W-112")
    device(c, 500, RUNG_B_Y - 15, 570, RUNG_B_Y + 15, "CB1", "BREAKER CLOSE COIL")
    wire(c, 570, RUNG_B_Y, RAIL_RIGHT_X, RUNG_B_Y, "W-113")

    # --- The discriminating case -----------------------------------------
    # One conductor crosses both rungs. A junction dot joins it to rung A.
    # There is no dot at rung B, so it only crosses there. A reader that joins
    # both has shorted the close command onto the close coil.
    wire(c, CROSS_X, 250, CROSS_X, 545, "W-200")
    junction_dot(c, CROSS_X, RUNG_A_Y)
    terminal(c, CROSS_X, 250, "TB23-20")

    c.showPage()
    c.save()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample_schematic.pdf"
    build(out)
    print(f"wrote {out}")
