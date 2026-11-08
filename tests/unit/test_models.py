import pytest
from pydantic import ValidationError

from ohmetry_dc.models import Parameter, Status

BASE = dict(name="X", unit="kW", description="d", source="s", revision="A0")


def test_accepts_a_complete_assumption():
    p = Parameter(id="a.b", value=2000, status="ASSUMPTION", **BASE)
    assert p.status is Status.ASSUMPTION and not p.missing


def test_user_input_may_be_missing_and_is_reported_missing():
    assert Parameter(id="a.b", value=None, status="USER_INPUT", **BASE).missing


def test_assumption_without_a_value_is_rejected():
    with pytest.raises(ValidationError):
        Parameter(id="a.b", value=None, status="ASSUMPTION", **BASE)


def test_unknown_status_is_rejected():
    with pytest.raises(ValidationError):
        Parameter(id="a.b", value=1, status="GUESS", **BASE)


@pytest.mark.parametrize("field", ["name", "unit", "description", "source", "revision"])
def test_required_provenance_fields_must_not_be_empty(field):
    kwargs = {**BASE, field: "  "}
    with pytest.raises(ValidationError):
        Parameter(id="a.b", value=1, status="ASSUMPTION", **kwargs)


def test_value_and_value_ref_together_are_rejected():
    with pytest.raises(ValidationError):
        Parameter(id="a.b", value=1, value_ref="c.d", status="ASSUMPTION", **BASE)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        Parameter(id="a.b", value=1, status="ASSUMPTION", colour="red", **BASE)
