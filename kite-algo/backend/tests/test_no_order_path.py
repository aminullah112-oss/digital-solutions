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
# The one exception: live_gtt.py may place a BUY GTT (see test below). Everything else is forbidden everywhere.
FORBIDDEN_EVERYWHERE = sorted(set(FORBIDDEN) - {"place_gtt"})


def source_files():
    return [p for p in BACKEND.glob("*.py")]


@pytest.mark.parametrize("name", FORBIDDEN_EVERYWHERE)
def test_no_backend_source_file_calls_or_references_a_mutating_broker_method(name):
    """Static check over every backend module: not even a mention as a call or an attribute."""
    pattern = re.compile(rf"\.{name}\b|\b{name}\s*\(")
    hits = [f"{p.name}: {line.strip()}" for p in source_files() for line in p.read_text().splitlines() if pattern.search(line) and not line.strip().startswith("#")]
    # the guard's docstring and the allow-list talk about these names; code must not use them
    hits = [h for h in hits if not h.startswith("broker_guard.py") and not h.startswith("gtt_sim.py: `kite.")]
    assert hits == [], hits


def code_lines(pattern):
    rx = re.compile(pattern)
    return [(p.name, line.strip()) for p in source_files() for line in p.read_text().splitlines() if rx.search(line) and not line.strip().startswith(("#", "`"))]


def test_place_gtt_is_called_in_exactly_one_place_and_nowhere_else():
    calls = code_lines(r"\.place_gtt\(")
    assert [name for name, _ in calls] == ["live_gtt.py"], calls
    assert "place_gtt(" in calls[0][1] and "self._kite" in calls[0][1]


def test_the_live_writer_is_created_only_by_the_live_branch_of_the_api():
    made = code_lines(r"GttWriter\(")
    assert [name for name, _ in made] == ["main.py"], made


def test_the_live_writer_can_only_ever_send_a_single_leg_cnc_limit_buy_of_one_share():
    src = (BACKEND / "live_gtt.py").read_text()
    body = src[src.index("def place_buy_gtt"):src.index("# ----", src.index("def place_buy_gtt"))]
    assert body.count('"transaction_type": "BUY"') == 1
    assert '"SELL"' not in src and "'SELL'" not in src  # there is no sell anywhere, not even as a string
    for needle in ('"order_type": "LIMIT"', '"product": "CNC"', 'exchange="NSE"', "GTT_TYPE_SINGLE", "gtt_sim.QUANTITY"):
        assert needle in body, needle
    assert body.count("orders=[{") == 1  # exactly one order in the GTT
    import gtt_sim

    assert gtt_sim.QUANTITY == 1


def test_no_module_can_modify_cancel_or_delete_a_gtt_or_an_order():
    for name in ("modify_gtt", "delete_gtt", "modify_order", "cancel_order", "exit_order", "place_order", "convert_position"):
        hits = code_lines(rf"\.{name}\b|\b{name}\s*\(")
        assert [h for h in hits if h[0] != "broker_guard.py"] == [], (name, hits)


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
        SpyKite().place_gtt("single", "X", "NSE", [1.0], 1.0, [])
    assert SpyKite.mutating_calls == ["place_gtt"]
    SpyKite.reset()
