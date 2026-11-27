"""Market and account DTOs. Missing numeric values are float('nan'), never pd.NA."""

from __future__ import annotations

import math
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from joseph_api.enums import Exchange
from joseph_api.symbol_utils import exchange_from_code


def _require_finite_or_nan(value: float | None) -> float:
    """A missing numeric (None, as Parquet yields it) or an existing NaN becomes float NaN."""
    if value is None:
        return math.nan
    if isinstance(value, float) and math.isnan(value):
        return value
    return float(value)


class _Dto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Bar(_Dto):
    symbol: str
    exchange: Exchange
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = math.nan
    open_interest: float = math.nan
    freq: str = "1d"

    @field_validator("volume", "open_interest", mode="before")
    @classmethod
    def _numeric(cls, v: object) -> float:
        return _require_finite_or_nan(v)  # type: ignore[arg-type]


class Tick(_Dto):
    symbol: str
    exchange: Exchange
    ts: datetime
    last: float = math.nan
    bid: float = math.nan
    ask: float = math.nan
    bid_volume: float = math.nan
    ask_volume: float = math.nan
    volume: float = math.nan
    open_interest: float = math.nan


class Settlement(_Dto):
    symbol: str
    trade_date: date
    settlement_price: float
    prev_settlement: float = math.nan


class Margin(_Dto):
    symbol: str
    trade_date: date
    margin_rate_long: float
    margin_rate_short: float
    margin_per_lot: float = math.nan
    provenance: str = "declared"


class Fee(_Dto):
    symbol: str
    trade_date: date
    fee_open: float
    fee_close: float
    fee_close_today: float
    fee_unit: str = "per_lot"
    provenance: str = "declared"


class OptionContract(_Dto):
    """One row of the lake's option contract table.

    Source strings are verbatim (`symbol` is the lake's compact symbol, `exchange_code` the
    joseph option-symbol form); dates are as the source holds them — null when it no longer
    dates a contract. Not a tradable instrument spec: no margin, no commissions.
    """

    symbol: str
    exchange_code: str
    exchange: Exchange
    product: str
    product_name: str
    underlying_kind: str
    underlying_symbol: str
    option_type: str
    exercise_style: str
    strike: float
    multiplier: float
    tick_size: float
    expiry_date: date | None
    expiry_month: date | None
    list_date: date | None
    first_seen_date: date | None
    last_seen_date: date | None
    dates_basis: str
    source: str
    data_version: str
    fetched_at: datetime

    @field_validator("exchange", mode="before")
    @classmethod
    def _map_exchange(cls, v: object) -> Exchange:
        return exchange_from_code(v)  # type: ignore[arg-type]

    @field_validator("strike", "multiplier", "tick_size", mode="before")
    @classmethod
    def _numbers(cls, v: object) -> float:
        return _require_finite_or_nan(v)  # type: ignore[arg-type]


class OptionBar(_Dto):
    """One daily bar of an option as the lake holds it; prices in index points, `settle` is the
    exchange settlement. Missing numerics (greeks columns the lake leaves null) are NaN."""

    symbol: str
    exchange_code: str
    exchange: Exchange
    product: str
    underlying_symbol: str
    option_type: str
    strike: float
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    settle: float
    pre_settle: float
    volume: float = math.nan
    open_interest: float = math.nan
    exercise_volume: float = math.nan
    oi_change: float = math.nan
    amount: float = math.nan
    implied_vol: float = math.nan
    series_implied_vol: float = math.nan
    delta: float = math.nan
    source: str
    data_version: str
    fetched_at: datetime

    @field_validator("exchange", mode="before")
    @classmethod
    def _map_exchange(cls, v: object) -> Exchange:
        return exchange_from_code(v)  # type: ignore[arg-type]

    @field_validator(
        "strike",
        "open",
        "high",
        "low",
        "close",
        "settle",
        "pre_settle",
        "volume",
        "open_interest",
        "exercise_volume",
        "oi_change",
        "amount",
        "implied_vol",
        "series_implied_vol",
        "delta",
        mode="before",
    )
    @classmethod
    def _numbers(cls, v: object) -> float:
        return _require_finite_or_nan(v)  # type: ignore[arg-type]


class OptionGreek(_Dto):
    """One row of the lake's derived greeks; the model, rate and forward sources and the
    computation status travel with the row so a consumer can filter. Missing values are NaN."""

    symbol: str
    underlying_symbol: str
    trade_date: date
    status: str
    model: str
    rate_source: str
    forward_source: str
    source: str
    data_version: str
    fetched_at: datetime
    rate: float = math.nan
    time_to_expiry: float = math.nan
    underlying_price: float = math.nan
    iv: float = math.nan
    delta: float = math.nan
    gamma: float = math.nan
    vega: float = math.nan
    theta: float = math.nan
    rho: float = math.nan

    @field_validator(
        "rate",
        "time_to_expiry",
        "underlying_price",
        "iv",
        "delta",
        "gamma",
        "vega",
        "theta",
        "rho",
        mode="before",
    )
    @classmethod
    def _numbers(cls, v: object) -> float:
        return _require_finite_or_nan(v)  # type: ignore[arg-type]
