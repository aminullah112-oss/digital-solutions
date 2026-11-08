"""Check statuses. A software check passing proves code behaviour, not engineering correctness."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    NOT_VERIFIED = "NOT VERIFIED"
    NOT_APPLICABLE = "NOT APPLICABLE"


@dataclass
class CheckResult:
    id: str
    title: str
    status: CheckStatus
    detail: str
    values: dict = field(default_factory=dict)  # inputs and outputs with units, for traceability
    next_action: str = ""
    # Four separate statuses. `status` above is the OVERALL DESIGN STATUS: it is PASS only when the calculation passes AND every input is verified.
    calculation_status: str = ""       # CALCULATED, PARTIAL or NOT CALCULATED: did the arithmetic run on complete inputs
    calculation_result: str = ""       # what the calculation found against the criterion (PASS, WARNING, FAIL), preliminary when the inputs are
    input_status: str = ""             # the worst data status among the inputs (see models/data_status.py), or N/A
    verification_status: str = ""      # VERIFIED, NOT VERIFIED or N/A (the check tests the arithmetic, not the design)
    inputs_used: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "status": self.status.value, "calculation_status": self.calculation_status, "calculation_result": self.calculation_result,
                "input_status": self.input_status, "verification_status": self.verification_status, "detail": self.detail, "values": self.values, "inputs_used": self.inputs_used,
                "next_action": self.next_action}
