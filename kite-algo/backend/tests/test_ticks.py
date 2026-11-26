"""Live ticks: the /ws/ticks websocket and the hub behind it, using a fake Kite ticker."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

import main  # noqa: E402
import ticks  # noqa: E402
import token_store  # noqa: E402


class FakeTicker:
    instances = []

    def __init__(self, api_key, access_token):
        self.credentials = (api_key, access_token)
        self.calls = []  # ("subscribe", [tokens]) ...
        self.connected_with_thread = None
        FakeTicker.instances.append(self)

    def connect(self, threaded=False):
        self.connected_with_thread = threaded

    def subscribe(self, tokens):
        self.calls.append(("subscribe", sorted(tokens)))

    def unsubscribe(self, tokens):
        self.calls.append(("unsubscribe", sorted(tokens)))

    def set_mode(self, mode, tokens):
        self.calls.append(("set_mode", mode, sorted(tokens)))

    def stop_retry(self):
        self.calls.append(("stop_retry",))

    def close(self, *a):
        self.calls.append(("close",))

    # what Kite would do
    def go_online(self):
        self.on_connect(self, {})

    def go_offline(self):
        self.on_close(self, 1006, "lost")

    def push(self, ticks_):
        self.on_ticks(self, ticks_)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("KITE_SESSION_FILE", str(tmp_path / "session.json"))
    FakeTicker.instances = []
    hub = ticks.set_ticker_factory(FakeTicker)
    token_store.save_session("key123", "secret-token", "AB1234")
    yield hub
    ticks.set_ticker_factory(None)


@pytest.fixture
def client():
    return TestClient(main.app)


def ticker():
    return FakeTicker.instances[-1]


def recv(ws):
    return json.loads(ws.receive_text())


def tick(token, price, **extra):
    return {"instrument_token": token, "last_price": price, **extra}


# ============================================================= parse_tokens ====
def test_parse_tokens():
    assert ticks.parse_tokens("738561,5633, 5633 ,408065") == [738561, 5633, 408065]


@pytest.mark.parametrize("bad", ["", " , ", "abc", "1,2,x", "-5", "1.5", "1;2"])
def test_parse_tokens_rejects_garbage(bad):
    with pytest.raises(ValueError):
        ticks.parse_tokens(bad)


def test_parse_tokens_limits_the_count():
    with pytest.raises(ValueError):
        ticks.parse_tokens(",".join(str(i) for i in range(ticks.MAX_TOKENS_PER_CLIENT + 1)))


# =========================================================== the websocket ====
def test_connect_sends_a_status_message_first(client):
    with client.websocket_connect("/ws/ticks?tokens=11,22&mode=full") as ws:
        assert recv(ws) == {"type": "status", "connected": False, "tokens": 2}
    assert ticker().credentials == ("key123", "secret-token") and ticker().connected_with_thread is True


def test_subscribes_to_exactly_the_requested_tokens_once_kite_is_connected(client):
    with client.websocket_connect("/ws/ticks?tokens=11,22&mode=full") as ws:
        recv(ws)
        assert ticker().calls == []  # not connected yet: nothing to subscribe on
        ticker().go_online()
        assert recv(ws) == {"type": "status", "connected": True, "tokens": 2}
        assert ticker().calls == [("subscribe", [11, 22]), ("set_mode", "full", [11, 22])]


def test_ticks_for_the_requested_tokens_arrive_and_others_do_not(client):
    with client.websocket_connect("/ws/ticks?tokens=11,22") as ws:
        recv(ws)
        ticker().go_online()
        recv(ws)
        ticker().push([tick(11, 100.5), tick(999, 1.0), tick(22, 200.0, volume=5)])
        msg = recv(ws)
        assert msg == {"type": "ticks", "ticks": [tick(11, 100.5), tick(22, 200.0, volume=5)]}


def test_datetimes_in_ticks_are_serialised(client):
    with client.websocket_connect("/ws/ticks?tokens=11") as ws:
        recv(ws)
        ticker().go_online()
        recv(ws)
        ticker().push([tick(11, 1.0, exchange_timestamp=datetime(2026, 11, 26, 11, 0, 0))])
        assert recv(ws)["ticks"][0]["exchange_timestamp"] == "2026-11-26 11:00:00"


def test_two_browsers_get_only_their_own_ticks_over_one_kite_connection(client):
    with client.websocket_connect("/ws/ticks?tokens=1,2") as a, client.websocket_connect("/ws/ticks?tokens=2,3") as b:
        recv(a)
        recv(b)
        assert len(FakeTicker.instances) == 1  # one shared Kite connection
        ticker().go_online()
        recv(a)
        recv(b)
        ticker().push([tick(1, 10.0), tick(2, 20.0), tick(3, 30.0)])
        assert [t["instrument_token"] for t in recv(a)["ticks"]] == [1, 2]
        assert [t["instrument_token"] for t in recv(b)["ticks"]] == [2, 3]


def test_tokens_nobody_wants_any_more_are_unsubscribed(client):
    with client.websocket_connect("/ws/ticks?tokens=1,2") as a:
        recv(a)
        ticker().go_online()
        recv(a)
        with client.websocket_connect("/ws/ticks?tokens=2,3") as b:
            recv(b)
            assert ("subscribe", [3]) in ticker().calls  # only the new token is added
        # b has left: token 3 is dropped, token 2 stays because a still wants it
        assert ticker().calls[-1] == ("unsubscribe", [3])
    assert ("unsubscribe", [1, 2]) in ticker().calls


def test_a_browser_that_connects_while_kite_is_already_online_is_subscribed_at_once(client):
    with client.websocket_connect("/ws/ticks?tokens=1") as a:
        recv(a)
        ticker().go_online()
        recv(a)
        with client.websocket_connect("/ws/ticks?tokens=7,8&mode=quote") as b:
            recv(b)
            assert ticker().calls[-2:] == [("subscribe", [7, 8]), ("set_mode", "quote", [7, 8])]


def test_the_fullest_mode_wins_when_browsers_share_a_token(client):
    with client.websocket_connect("/ws/ticks?tokens=5&mode=ltp") as a:
        recv(a)
        ticker().go_online()
        recv(a)
        assert ticker().calls[-1] == ("set_mode", "ltp", [5])
        with client.websocket_connect("/ws/ticks?tokens=5&mode=full") as b:
            recv(b)
            assert ticker().calls[-1] == ("set_mode", "full", [5])


def test_after_a_reconnect_the_subscriptions_are_restored(client):
    with client.websocket_connect("/ws/ticks?tokens=1,2") as ws:
        recv(ws)
        ticker().go_online()
        recv(ws)
        ticker().go_offline()
        assert recv(ws) == {"type": "status", "connected": False, "tokens": 2}
        ticker().calls.clear()
        ticker().go_online()
        assert recv(ws)["connected"] is True
        assert ticker().calls == [("subscribe", [1, 2]), ("set_mode", "full", [1, 2])]


def test_logging_in_again_replaces_the_kite_connection(client):
    with client.websocket_connect("/ws/ticks?tokens=1") as ws:
        recv(ws)
    first = ticker()
    token_store.save_session("key123", "a-new-token", "AB1234")
    with client.websocket_connect("/ws/ticks?tokens=1") as ws:
        recv(ws)
    assert ("close",) in first.calls and len(FakeTicker.instances) == 2
    assert ticker().credentials == ("key123", "a-new-token")


def test_a_browser_gets_no_ticks_after_it_disconnects(client, isolated):
    with client.websocket_connect("/ws/ticks?tokens=1") as ws:
        recv(ws)
    assert isolated._clients == set()
    isolated.dispatch([tick(1, 5.0)])  # must not raise


# ============================================================== rejections ====
def test_other_websites_are_refused(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/ticks?tokens=1", headers={"origin": "https://evil.example"}):
            pass
    assert FakeTicker.instances == []


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_the_app_itself_is_allowed(client, origin):
    with client.websocket_connect("/ws/ticks?tokens=1", headers={"origin": origin}) as ws:
        assert recv(ws)["type"] == "status"


def test_not_logged_in_is_refused(client):
    token_store.clear_session()
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/ticks?tokens=1"):
            pass
    assert exc.value.code == 4401 and FakeTicker.instances == []


@pytest.mark.parametrize("query", ["tokens=", "tokens=abc", "tokens=1,x", "", "tokens=1&mode=turbo"])
def test_bad_requests_get_an_error_message_and_are_closed(client, query):
    with client.websocket_connect(f"/ws/ticks?{query}") as ws:
        msg = recv(ws)
        assert msg["type"] == "error" and msg["message"]
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    assert FakeTicker.instances == []


def test_too_many_tokens_are_refused(client):
    tokens = ",".join(str(i) for i in range(ticks.MAX_TOKENS_PER_CLIENT + 1))
    with client.websocket_connect(f"/ws/ticks?tokens={tokens}") as ws:
        assert recv(ws)["type"] == "error"


def test_the_access_token_never_reaches_the_browser(client):
    with client.websocket_connect("/ws/ticks?tokens=1") as ws:
        seen = [ws.receive_text()]
        ticker().go_online()
        seen.append(ws.receive_text())
        ticker().push([tick(1, 1.0)])
        seen.append(ws.receive_text())
    assert "secret-token" not in "".join(seen)


# ================================================================= the queue ====
def test_a_slow_browser_loses_the_oldest_ticks_not_the_newest():
    async def run():
        c = ticks.Client(asyncio.get_running_loop(), {1}, "full")
        for i in range(ticks.QUEUE_SIZE + 5):
            c.offer(str(i))
        got = [c.queue.get_nowait() for _ in range(c.queue.qsize())]
        return got

    got = asyncio.run(run())
    assert len(got) == ticks.QUEUE_SIZE and got[-1] == str(ticks.QUEUE_SIZE + 4) and got[0] == "5"


def test_posting_to_a_closed_loop_does_not_raise():
    loop = asyncio.new_event_loop()
    c = ticks.Client.__new__(ticks.Client)
    c.loop = loop
    loop.close()
    c.post("x")  # the browser is gone; nothing to do
