"""Enumerations for the joseph-core trading platform."""

from enum import StrEnum


class Exchange(StrEnum):
    """Exchange enumeration.

    Values correspond to standard exchange codes used in China futures market.
    """

    UNKNOWN = "UNKNOWN"  # Unknown or unspecified exchange
    CFFEX = "CFFEX"  # China Financial Futures Exchange
    SHFE = "SHFE"  # Shanghai Futures Exchange
    DCE = "DCE"  # Dalian Commodity Exchange
    CZCE = "CZCE"  # Zhengzhou Commodity Exchange
    INE = "INE"  # Shanghai International Energy Exchange
    GFEX = "GFEX"  # Guangzhou Futures Exchange
    SSE = "SSE"  # Shanghai Stock Exchange
    SZSE = "SZSE"  # Shenzhen Stock Exchange
    HKEX = "HKEX"  # Hong Kong Exchanges and Clearing
    NYSE = "NYSE"  # New York Stock Exchange
    NASDAQ = "NASDAQ"  # NASDAQ Stock Market


class AssetType(StrEnum):
    """Asset type enumeration."""

    FUTURE = "FUTURE"
    STOCK = "STOCK"
    OPTION = "OPTION"
    CRYPTO = "CRYPTO"
    BOND = "BOND"
    ETF = "ETF"
    COMMODITY = "COMMODITY"


class Currency(StrEnum):
    """Currency enumeration for instrument denomination."""

    CNY = "CNY"  # Chinese Yuan
    USD = "USD"  # US Dollar
    HKD = "HKD"  # Hong Kong Dollar
    EUR = "EUR"  # Euro
    JPY = "JPY"  # Japanese Yen
    GBP = "GBP"  # British Pound


# Default currency mapping by exchange
EXCHANGE_DEFAULT_CURRENCY: dict["Exchange", Currency] = {
    Exchange.CFFEX: Currency.CNY,
    Exchange.SHFE: Currency.CNY,
    Exchange.DCE: Currency.CNY,
    Exchange.CZCE: Currency.CNY,
    Exchange.INE: Currency.CNY,
    Exchange.SSE: Currency.CNY,
    Exchange.SZSE: Currency.CNY,
    Exchange.HKEX: Currency.HKD,
    Exchange.NYSE: Currency.USD,
    Exchange.NASDAQ: Currency.USD,
}
