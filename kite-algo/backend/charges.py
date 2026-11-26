"""Zerodha equity DELIVERY (CNC) charges, used by the backtest.

These rates are my best knowledge and they change over time. Before you rely
on a backtest, compare one trade with Zerodha's brokerage calculator
(zerodha.com/brokerage-calculator) and edit the numbers below if they differ.

All percentages are percent of the trade value (shares x price).
"""

RATES = {
    "brokerage_pct": 0.0,  # delivery brokerage is free on Zerodha
    "stt_buy_pct": 0.1,  # securities transaction tax, charged on buy and sell
    "stt_sell_pct": 0.1,
    "stamp_buy_pct": 0.015,  # stamp duty, buy side only
    "exchange_txn_pct": 0.00297,  # NSE transaction charge
    "sebi_per_crore": 10.0,  # rupees per crore of turnover
    "gst_pct": 18.0,  # on brokerage + exchange + SEBI charges
    "dp_charge_sell": 15.93,  # depository charge per stock sold (13.5 + 18% GST)
}


def _exchange_and_gst(turnover: float) -> float:
    brokerage = turnover * RATES["brokerage_pct"] / 100
    txn = turnover * RATES["exchange_txn_pct"] / 100
    sebi = turnover * RATES["sebi_per_crore"] / 1e7
    gst = (brokerage + txn + sebi) * RATES["gst_pct"] / 100
    return brokerage + txn + sebi + gst


def buy_charges(turnover: float) -> float:
    """Total charges in rupees for buying shares worth `turnover` rupees."""
    stt = turnover * RATES["stt_buy_pct"] / 100
    stamp = turnover * RATES["stamp_buy_pct"] / 100
    return round(stt + stamp + _exchange_and_gst(turnover), 2)


def sell_charges(turnover: float) -> float:
    """Total charges in rupees for selling shares worth `turnover` rupees."""
    stt = turnover * RATES["stt_sell_pct"] / 100
    return round(stt + _exchange_and_gst(turnover) + RATES["dp_charge_sell"], 2)
