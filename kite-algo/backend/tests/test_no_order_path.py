"""There must be no way for this app to place, change, cancel or delete a real order or GTT."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

import broker_guard  # noqa: E402
from fakes_algo import MUTATORS, SpyKite  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
FORBIDDEN = MUTATORS + ["place_gtt", "modify_gtt", "delete_gtt"]


def source_files():
    return [p for p in BACKEND.glob("*.py")]


@pytest.mark.parametrize("name", sorted(set(FORBIDDEN)))
def test_no_backend_source_file_calls_or_references_a_mutating_broker_method(name):
    """Static check over every backend module: not even a mention as a call or an attribute."""
    pattern = re.compile(rf"\.{name}\b|\b{name}\s*\(")
    hits = [f"{p.name}: {line.strip()}" for p in source_files() for line in p.read_text().splitlines() if pattern.search(line) and not line.strip().startswith("#")]
    # the guard's docstring and the allow-list talk about these names; code must not use them
    hits = [h for h in hits if not h.startswith("broker_guard.py") and not h.startswith("gtt_sim.py: `kite.")]
    assert hits == [], hits


def test_the_allow_list_contains_only_reads():
    assert broker_guard.READ_METHODS == {"profile", "get_gtts", "orders", "positions", "holdings", "instruments", "ohlc", "historical_data"}
    assert not (set(FORBIDDEN) & broker_guard.READ_METHODS)


@pytest.mark.parametrize("name", sorted(set(FORBIDDEN)))
def test_the_read_only_wrapper_refuses_every_mutating_method(name):
    SpyKite.reset()
    wrapped = broker_guard.ReadOnlyKite(SpyKite())
    with pytest.raises(broker_guard.ForbiddenBrokerCall):
        getattr(wrapped, name)  # refused before the method can even be fetched
    assert SpyKite.mutating_calls == []


def test_the_wrapper_allows_reads_and_cannot_be_modified():
    SpyKite.reset()
    wrapped = broker_guard.ReadOnlyKite(SpyKite())
    assert wrapped.get_gtts() == [] and wrapped.orders() == [] and wrapped.holdings() == []
    assert wrapped.positions() == {"net": [], "day": []}
    with pytest.raises(broker_guard.ForbiddenBrokerCall):
        wrapped.place_gtt = lambda *a: None
    with pytest.raises(broker_guard.ForbiddenBrokerCall):
        wrapped._allowed = frozenset({"place_gtt"})


def test_forbidden_call_is_an_attribute_error_so_it_can_never_be_swallowed_as_success():
    assert issubclass(broker_guard.ForbiddenBrokerCall, AttributeError)


def test_the_spy_itself_fails_loudly_so_the_other_tests_mean_something():
    SpyKite.reset()
    with pytest.raises(AssertionError):
        SpyKite().place_gtt(trigger_type="single")
    assert SpyKite.mutating_calls == ["place_gtt"]
    SpyKite.reset()
