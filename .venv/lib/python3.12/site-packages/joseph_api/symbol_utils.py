"""Internal symbol format utilities.

Internal symbol format: "EXCHANGE.SYMBOL" (e.g., "CFFEX.IF2506", "SHFE.ag2501").

This module provides parsing and formatting functions used across all models
that store symbol in internal format.
"""

import re
from typing import Any, ClassVar

from pydantic import computed_field, field_validator

from joseph_api.enums import Exchange

__test_case_metadata__ = {
    "defaults": {"components": ("models",), "domains": ("asset-independent",)},
    "overrides": {"extract_variety_and_date": {"domains": ("futures",)}},
}


def extract_variety_and_date(exchange_symbol: str) -> tuple[str, str]:
    """Extract variety and contract month from an exchange symbol.

    Args:
        exchange_symbol: Exchange-specific symbol (e.g., "IF2506", "ag2501")

    Returns:
        Tuple of (variety, "YYYY-MM") e.g. ("IF", "2025-06")

    Raises:
        ValueError: If symbol does not match expected pattern

    Examples:
        >>> extract_variety_and_date("IF2506")
        ('IF', '2025-06')
        >>> extract_variety_and_date("ag2501")
        ('ag', '2025-01')
    """
    m = re.fullmatch(r"([A-Za-z]+)(\d{2})(\d{2})", exchange_symbol)
    if not m:
        raise ValueError(f"Cannot extract variety/date from symbol: '{exchange_symbol}'")
    variety, yy, mm = m.group(1), m.group(2), m.group(3)
    return variety, f"20{yy}-{mm}"


def parse_internal_symbol(symbol: str) -> tuple[Exchange, str]:
    """Parse internal symbol into (Exchange, exchange_symbol).

    Args:
        symbol: Internal symbol (e.g., "CFFEX.IF2506")

    Returns:
        Tuple of (Exchange enum, exchange_symbol string)

    Raises:
        ValueError: If symbol is not in "EXCHANGE.SYMBOL" format

    Examples:
        >>> parse_internal_symbol("CFFEX.IF2506")
        (<Exchange.CFFEX: 'CFFEX'>, 'IF2506')
        >>> parse_internal_symbol("SHFE.ag2501")
        (<Exchange.SHFE: 'SHFE'>, 'ag2501')
    """
    if not symbol or "." not in symbol:
        raise ValueError(f"Symbol must be in internal format 'EXCHANGE.SYMBOL', got: '{symbol}'")

    exchange_str, exchange_symbol = symbol.split(".", 1)

    try:
        exchange = Exchange(exchange_str)
    except ValueError:
        raise ValueError(
            f"Unknown exchange '{exchange_str}' in symbol '{symbol}'. "
            f"Valid exchanges: {[e.value for e in Exchange]}"
        )

    return exchange, exchange_symbol


def format_internal_symbol(exchange: Exchange, exchange_symbol: str) -> str:
    """Format exchange and symbol into internal symbol format.

    Args:
        exchange: Exchange enum value
        exchange_symbol: Exchange-specific symbol (e.g., "IF2506")

    Returns:
        Internal symbol string (e.g., "CFFEX.IF2506")

    Examples:
        >>> format_internal_symbol(Exchange.CFFEX, "IF2506")
        'CFFEX.IF2506'
    """
    return f"{exchange.value}.{exchange_symbol}"


_LAKE_EXCHANGE_CODES: dict[str, Exchange] = {"CFE": Exchange.CFFEX}


def exchange_from_code(code: str | Exchange) -> Exchange:
    """Shared exchange for a source exchange code (the lake's ``CFE`` is the shared ``CFFEX``).

    Raises:
        ValueError: If the code is not a known exchange.

    Examples:
        >>> exchange_from_code("CFE")
        <Exchange.CFFEX: 'CFFEX'>
    """
    if isinstance(code, Exchange):
        return code
    return _LAKE_EXCHANGE_CODES.get(code) or Exchange(code)


def option_internal_symbol(exchange_code: str, exchange: str | Exchange = "CFE") -> str:
    """Internal symbol of an option row: the shared exchange code plus the source's exchange code.

    Examples:
        >>> option_internal_symbol("HO2311-C-2125", "CFE")
        'CFFEX.HO2311-C-2125'
    """
    return format_internal_symbol(exchange_from_code(exchange), exchange_code)


def validate_symbol_contract(symbol: str) -> tuple[Exchange, str]:
    """Validate symbol is in canonical internal format and not malformed.

    Rejects:
    - Empty/blank symbols
    - Bare symbols without exchange prefix
    - Double-prefixed symbols (e.g., "CFFEX.CFFEX.IF2506")

    Returns:
        (Exchange, exchange_symbol) tuple if valid.

    Raises:
        ValueError: If symbol is malformed.

    Examples:
        >>> validate_symbol_contract("CFFEX.IF2506")
        (<Exchange.CFFEX: 'CFFEX'>, 'IF2506')
        >>> validate_symbol_contract("SHFE.ag2501")
        (<Exchange.SHFE: 'SHFE'>, 'ag2501')
    """
    if not symbol:
        raise ValueError("Symbol must not be empty")

    dot_count = symbol.count(".")
    if dot_count == 0:
        raise ValueError(f"Symbol must be in internal format 'EXCHANGE.SYMBOL', got: '{symbol}'")
    if dot_count > 1:
        raise ValueError(
            f"Malformed double-prefixed symbol detected: '{symbol}'. "
            f"Expected format: 'EXCHANGE.SYMBOL' (single dot separator)"
        )

    return parse_internal_symbol(symbol)


class InternalSymbolMixin:
    """Mixin for Pydantic models that store symbol in internal format.

    Provides:
    - Symbol format validation at creation time
    - exchange: Exchange enum (computed from symbol)
    - exchange_symbol: bare exchange symbol string (computed from symbol)
    - model_dump()/model_dump_json() exclude computed fields by default

    Usage:
        class Order(InternalSymbolMixin, ExecutionEvent):
            ...

    Note: Must be listed BEFORE the Pydantic BaseModel in MRO.
    """

    _COMPUTED_SYMBOL_FIELDS: ClassVar[set[str]] = {"exchange", "exchange_symbol"}

    @field_validator("symbol")
    @classmethod
    def _validate_symbol_format(cls, v: str) -> str:
        """Validate canonical symbol contract format, including malformed prefixes."""
        validate_symbol_contract(v)
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def exchange(self) -> Exchange:
        """Exchange enum parsed from internal symbol."""
        return parse_internal_symbol(self.symbol)[0]  # type: ignore[attr-defined]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def exchange_symbol(self) -> str:
        """Exchange-specific symbol (e.g., 'IF2506')."""
        return parse_internal_symbol(self.symbol)[1]  # type: ignore[attr-defined]

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override to exclude computed symbol fields by default."""
        exclude = kwargs.get("exclude") or set()
        if isinstance(exclude, set):
            exclude = exclude | self._COMPUTED_SYMBOL_FIELDS
        kwargs["exclude"] = exclude
        dumped: dict[str, Any] = super().model_dump(**kwargs)  # type: ignore[misc]
        return dumped

    def model_dump_json(self, **kwargs: Any) -> str:
        """Override to exclude computed symbol fields by default."""
        exclude = kwargs.get("exclude") or set()
        if isinstance(exclude, set):
            exclude = exclude | self._COMPUTED_SYMBOL_FIELDS
        kwargs["exclude"] = exclude
        dumped_json: str = super().model_dump_json(**kwargs)  # type: ignore[misc]
        return dumped_json
