"""Architecture functions shown as CONCEPT symbols on the single-line diagram (revision A6).

Each entry says what the drawing shows, that it is NOT designed, and what is needed before it can be. Nothing here is a design, a rating or a setting.
The diagram, the architecture workbook and the outstanding-items register all read this list, so they cannot disagree.
"""
from __future__ import annotations

from dataclasses import dataclass

NOT_DESIGNED = "CONCEPT SYMBOL ONLY: NOT DESIGNED"
NOT_CLAIMED = "NOT CLAIMED"


@dataclass(frozen=True)
class ArchitectureFunction:
    id: str
    function: str
    drawing_tags: str
    shown_as: str
    status: str
    needed: str


ARCHITECTURE_FUNCTIONS: tuple[ArchitectureFunction, ...] = (
    ArchitectureFunction("ARCH-01", "Independence of utility supply A and utility supply B", "Utility supply, path A and B", "Two supplies drawn side by side with no tie",
                         NOT_CLAIMED, "Utility confirmation of separate feeders, substations and upstream network; common-mode failure review. Until then no independence is claimed."),
    ArchitectureFunction("ARCH-02", "Utility to generator transfer and interlocking", "ACB-TX-A/B, ACB-GEN-A/B", "Dashed interlock between the two incomers",
                         NOT_DESIGNED, "Transfer philosophy (open or closed transition), interlock scheme (key, hardwired, PLC), transfer time and retransfer rules."),
    ArchitectureFunction("ARCH-03", "Generator paralleling and synchronising", "GCB-A1 to GCB-A3, GCB-B1 to GCB-B3, GENBUS-A/B", "A breaker per generator onto a generator bus",
                         NOT_DESIGNED, "Synchroniser and paralleling controls, dead-bus closing logic, reverse-power and protection requirements from the generator manufacturer."),
    ArchitectureFunction("ARCH-04", "Power management system: load sharing", "PMS-A, PMS-B", "Dashed control box (concept)",
                         NOT_DESIGNED, "Load-sharing method (isochronous or droop), controller and communications, and the failure behaviour of the PMS."),
    ArchitectureFunction("ARCH-05", "Load shedding", "PMS-A, PMS-B", "Named on the PMS box; no shed feeders selected",
                         NOT_DESIGNED, "Load priority list, shed stages and triggers, and the restart sequence. Small power (LS-2) is already excluded from the generator load in the load model."),
    ArchitectureFunction("ARCH-06", "UPS static bypass", "STS-A, STS-B", "Static switch tapped from the UPS input, rejoining at the IT distribution board",
                         NOT_DESIGNED, "UPS manufacturer's bypass design; whether the bypass has its own feed (a design decision); bypass protection and transfer behaviour."),
    ArchitectureFunction("ARCH-07", "UPS maintenance bypass", "MBB-A, MBB-B", "Breaker in the bypass line",
                         NOT_DESIGNED, "Maintenance bypass scheme (wrap-around or external), interlocking so the bypass and the UPS output cannot be paralleled unintentionally, and isolation points."),
    ArchitectureFunction("ARCH-08", "Battery isolation and protection", "BAT-ISO-A, BAT-ISO-B", "Isolator between the UPS and the battery",
                         NOT_DESIGNED, "Battery manufacturer's DC protection and isolation requirements; battery is not sized, so no rating exists."),
    ArchitectureFunction("ARCH-09", "Protection and measurement boundaries", "Whole diagram", "Not drawn. Relays, current and voltage transformers and metering are not shown",
                         NOT_DESIGNED, "Protection philosophy, protection zones, metering points and the coordination study. Arc-flash is outside the scope of this package."),
    ArchitectureFunction("ARCH-10", "Utility point of connection and ownership boundary", "Dashed line below each utility supply", "Boundary marker (concept)",
                         NOT_DESIGNED, "Utility's written statement of the point of connection, protection and metering responsibilities."),
    ArchitectureFunction("ARCH-11", "UPS system vendor-scope boundary", "UPS system boundary (dashed)", "Dashed rectangle around the UPS and battery",
                         NOT_DESIGNED, "UPS and battery manufacturer's scope of supply and interfaces."),
    ArchitectureFunction("ARCH-12", "Dual-corded IT load", "IT LOAD", "One load fed from both IT distribution boards",
                         "PRELIMINARY ASSUMPTION", "IT equipment confirmation that all loads are dual-corded; single-corded equipment would need static transfer switches, which are not modelled."),
)
