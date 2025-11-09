from __future__ import annotations

from collections.abc import Iterator
from random import getrandbits

from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.market_data.tick.trade_tick_event import TradeTickEvent


def _quote_to_samples(e: QuoteTickEvent) -> Iterator[PriceSample]:
    q = e.quote_tick
    dt = e.dt_event
    inst = q.instrument
    yield PriceSample(inst, dt, PriceType.BID, q.bid_price)
    yield PriceSample(inst, dt, PriceType.ASK, q.ask_price)


def _trade_to_samples(e: TradeTickEvent) -> Iterator[PriceSample]:
    t = e.trade_tick
    yield PriceSample(t.instrument, e.dt_event, PriceType.LAST_TRADE, t.price)


def _bar_to_samples(e: BarEvent) -> Iterator[PriceSample]:
    # 1:1 copy of current BarEvent.iter_price_samples semantics (including RNG tie‑break)
    b = e.bar
    inst = b.instrument
    start = b.start_dt
    end = b.end_dt
    dt_range = end - start
    dt_open = start
    dt_33 = start + (dt_range / 3)
    dt_67 = start + (dt_range * 2 / 3)
    dt_close = end
    pt = b.price_type

    dist_high = abs(b.high - b.open)
    dist_low = abs(b.low - b.open)

    if dist_high < dist_low:
        first = "HIGH"
    elif dist_low < dist_high:
        first = "LOW"
    else:
        bit = getrandbits(1)
        first = "HIGH" if bit == 0 else "LOW"

    yield PriceSample(inst, dt_open, pt, b.open)
    if first == "HIGH":
        yield PriceSample(inst, dt_33, pt, b.high)
        yield PriceSample(inst, dt_67, pt, b.low)
    else:
        yield PriceSample(inst, dt_33, pt, b.low)
        yield PriceSample(inst, dt_67, pt, b.high)
    yield PriceSample(inst, dt_close, pt, b.close)
