"""Canonical market data field names."""

from typing import ClassVar


class DataFieldAlias:
    """Standard field name constants for normalized data.

    All data from various sources (TSL, AKShare, CSV) should be normalized
    to these standard field names.
    """

    # Core fields
    TRADING_DATE = "trading_date"
    DATE = TRADING_DATE  # Alias for backward compatibility
    TIMESTAMP = "timestamp"
    EVENT_TS = "event_ts"
    RECV_TS = "recv_ts"
    SOURCE_ROW = "source_row"
    SOURCE_FORMAT = "source_format"
    CUMULATIVE_VOLUME = "cumulative_volume"
    CUMULATIVE_TURNOVER = "cumulative_turnover"
    LAST_PRICE = "last_price"
    LOWER_LIMIT = "lower_limit"
    UPPER_LIMIT = "upper_limit"
    ASK_PRICE_1 = "ask_price_1"
    ASK_PRICE_2 = "ask_price_2"
    ASK_PRICE_3 = "ask_price_3"
    ASK_PRICE_4 = "ask_price_4"
    ASK_PRICE_5 = "ask_price_5"
    ASK_VOLUME_1 = "ask_volume_1"
    ASK_VOLUME_2 = "ask_volume_2"
    ASK_VOLUME_3 = "ask_volume_3"
    ASK_VOLUME_4 = "ask_volume_4"
    ASK_VOLUME_5 = "ask_volume_5"
    BID_PRICE_1 = "bid_price_1"
    BID_PRICE_2 = "bid_price_2"
    BID_PRICE_3 = "bid_price_3"
    BID_PRICE_4 = "bid_price_4"
    BID_PRICE_5 = "bid_price_5"
    BID_VOLUME_1 = "bid_volume_1"
    BID_VOLUME_2 = "bid_volume_2"
    BID_VOLUME_3 = "bid_volume_3"
    BID_VOLUME_4 = "bid_volume_4"
    BID_VOLUME_5 = "bid_volume_5"
    SYMBOL = "symbol"
    EXCHANGE = "exchange"
    PRODUCT = "product"
    AVAILABLE_TIME = "available_time"
    MEMBER = "member"
    RANK_TYPE = "rank_type"
    RANK = "rank"
    VALUE_CHG = "value_chg"
    SOURCE = "source"
    INGEST_TS = "ingest_ts"
    RAW_RANK_TYPE = "raw_rank_type"
    RAW_MEMBER = "raw_member"
    RAW_PAYLOAD_HASH = "raw_payload_hash"

    # OHLC fields
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    SETTLE = "settle"
    PRE_SETTLE = "pre_settle"

    # Volume fields
    VOLUME = "volume"
    OPEN_INTEREST = "open_interest"
    OPEN_INTEREST_CHANGE = "open_interest_change"
    TURNOVER = "turnover"

    # Contract specification fields
    MULTIPLIER = "multiplier"
    TICK_SIZE = "tick_size"
    MATURITY_DATE = "maturity_date"
    # Note: maturity_date_estimated is now a field on the Future model, not a DataFrame column
    MARGIN_RATIO = "margin_ratio"

    # Commission fields
    COMMISSION_OPEN_RATE = "commission_open_rate"
    COMMISSION_CLOSE_RATE = "commission_close_rate"
    COMMISSION_CLOSE_TODAY_RATE = "commission_close_today_rate"

    # Limit fields
    LIMIT_UP = "limit_up"
    LIMIT_DOWN = "limit_down"

    # Stock-specific fields
    ADJ_FACTOR = "adj_factor"
    PREV_CLOSE = "prev_close"
    TOTAL_SHARES = "total_shares"
    FREE_FLOAT_SHARES = "free_float_shares"
    TOTAL_MV = "total_mv"
    FREE_FLOAT_MV = "free_float_mv"
    TRADING_STATUS = "trading_status"  # 1=normal, 0=halted

    # Option-specific fields
    STRIKE = "strike"
    OPTION_TYPE = "option_type"  # "call" or "put"
    EXPIRY_DATE = "expiry_date"
    IMPLIED_VOL = "implied_vol"
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    THETA = "theta"
    RHO = "rho"
    OPTION_SYMBOL = "option_symbol"
    UNDERLYING_SYMBOL = "underlying_symbol"

    # All fields list
    ALL_FIELDS: ClassVar[list[str]] = [
        TRADING_DATE,
        TIMESTAMP,
        EVENT_TS,
        RECV_TS,
        SOURCE_ROW,
        SOURCE_FORMAT,
        CUMULATIVE_VOLUME,
        CUMULATIVE_TURNOVER,
        LAST_PRICE,
        LOWER_LIMIT,
        UPPER_LIMIT,
        ASK_PRICE_1,
        ASK_PRICE_2,
        ASK_PRICE_3,
        ASK_PRICE_4,
        ASK_PRICE_5,
        ASK_VOLUME_1,
        ASK_VOLUME_2,
        ASK_VOLUME_3,
        ASK_VOLUME_4,
        ASK_VOLUME_5,
        BID_PRICE_1,
        BID_PRICE_2,
        BID_PRICE_3,
        BID_PRICE_4,
        BID_PRICE_5,
        BID_VOLUME_1,
        BID_VOLUME_2,
        BID_VOLUME_3,
        BID_VOLUME_4,
        BID_VOLUME_5,
        SYMBOL,
        EXCHANGE,
        PRODUCT,
        AVAILABLE_TIME,
        MEMBER,
        RANK_TYPE,
        RANK,
        VALUE_CHG,
        SOURCE,
        INGEST_TS,
        RAW_RANK_TYPE,
        RAW_MEMBER,
        RAW_PAYLOAD_HASH,
        OPEN,
        HIGH,
        LOW,
        CLOSE,
        SETTLE,
        PRE_SETTLE,
        VOLUME,
        OPEN_INTEREST,
        OPEN_INTEREST_CHANGE,
        TURNOVER,
        MULTIPLIER,
        TICK_SIZE,
        MATURITY_DATE,
        MARGIN_RATIO,
        COMMISSION_OPEN_RATE,
        COMMISSION_CLOSE_RATE,
        COMMISSION_CLOSE_TODAY_RATE,
        LIMIT_UP,
        LIMIT_DOWN,
        # Stock fields
        ADJ_FACTOR,
        PREV_CLOSE,
        TOTAL_SHARES,
        FREE_FLOAT_SHARES,
        TOTAL_MV,
        FREE_FLOAT_MV,
        TRADING_STATUS,
        # Option fields
        STRIKE,
        OPTION_TYPE,
        EXPIRY_DATE,
        IMPLIED_VOL,
        DELTA,
        GAMMA,
        VEGA,
        THETA,
        RHO,
        OPTION_SYMBOL,
        UNDERLYING_SYMBOL,
    ]


# =============================================================================
# Configuration Models for Field Normalizer
# =============================================================================


DataFieldAlias.__module__ = "joseph_core.dal.field_alias"
