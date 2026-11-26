"""A read-only wrapper around the Kite client.

The Algo Signals and GTT Placement features only ever READ from Kite. To make
that a property of the code instead of a promise, every endpoint of those
features gets its Kite client through ReadOnlyKite: any method that is not on
the allow-list below raises ForbiddenBrokerCall, so for example
`kite.place_gtt(...)`, `kite.place_order(...)`, `kite.modify_order(...)`,
`kite.cancel_order(...)` or `kite.delete_gtt(...)` cannot run even by accident.
"""

READ_METHODS = frozenset(
    {
        "profile",  # who you are (User tab)
        "get_gtts",  # existing GTTs
        "orders",  # today's orders
        "positions",
        "holdings",
        "instruments",  # instrument master (tick sizes, tokens)
        "ohlc",  # price snapshot
        "historical_data",  # daily candles
    }
)


class ForbiddenBrokerCall(AttributeError):
    """Raised when code tries to use a Kite method that is not read-only."""


class ReadOnlyKite:
    def __init__(self, kite, allowed=READ_METHODS):
        object.__setattr__(self, "_kite", kite)
        object.__setattr__(self, "_allowed", frozenset(allowed))

    def __getattr__(self, name: str):
        if name not in self._allowed:
            raise ForbiddenBrokerCall(f"Kite method '{name}' is not allowed here: this app only reads from Kite.")
        return getattr(self._kite, name)

    def __setattr__(self, name, value):
        raise ForbiddenBrokerCall("The read-only Kite wrapper cannot be modified.")
