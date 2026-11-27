"""Instrument classes and registry for the joseph-core quantitative trading platform.

Design:
- Instrument: Base class for all tradable instruments
- Future: Futures contract with multiplier, maturity date, etc.
- Option: Options contract with strike, expiry, option type, etc.
- InstrumentRegistry: Instance-based registry for instrument lookup

Key concepts:
- Internal symbol format: "EXCHANGE.SYMBOL" (e.g., "SHFE.ag2501", "CZCE.SR2505")
- Exchange symbol: Original exchange symbol format (e.g., "ag2501", "SR505")
- CZCE normalization: 3-digit year → 4-digit year (SR505 → SR2505)
- Case normalization: Each exchange has specific case requirements (hardcoded)

Note:
    InstrumentRegistry is NOT a singleton. Each instance maintains independent state,
    enabling test isolation, parallel backtests, and multi-strategy scenarios.
"""

import re
from collections.abc import Iterable
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .enums import EXCHANGE_DEFAULT_CURRENCY, AssetType, Currency, Exchange

__test_case_metadata__ = {"defaults": {"components": ("models",), "domains": ("futures",)}}

__all__ = [
    "Future",
    "Instrument",
    "InstrumentRegistry",
    "Option",
    "Stock",
    "extract_product",
    "get_multiplier",
    "get_multiplier_fallback",
    "get_multiplier_strict",
    "normalize_exchange_symbol",
    "normalize_symbol_case",
]


FutureCommissionPayload = dict[str, float]
DEFAULT_FUTURE_COMMISSIONS: FutureCommissionPayload = {
    "open": 0.0,
    "close": 0.0,
    "close_today": 0.0,
    "open_fixed": 0.0,
    "close_fixed": 0.0,
    "close_today_fixed": 0.0,
}


# Exchange-specific symbol specifications (hardcoded)
# Later this can be moved to a configuration file
_EXCHANGE_SPECS: dict[Exchange, dict[str, str | None]] = {
    Exchange.CFFEX: {
        "case": "upper",  # IF2506, IC2506, T2506, MO2503-C-6100
        "pattern": r"^[A-Z]{1,2}\d{4}(-[CP]-\d+)?$",
        "description": "uppercase + 4 digits, optionally -C/P-strike (e.g., MO2503-C-6100)",
    },
    Exchange.SHFE: {
        "case": "lower",  # ag2501, cu2501, rb2505
        "pattern": r"^[a-z]{1,2}\d{4}$",
        "description": "lowercase letters + 4 digits (e.g., ag2501)",
    },
    Exchange.DCE: {
        "case": "lower",  # i2405, m2405, a2501
        "pattern": r"^[a-z]{1,2}\d{4}$",
        "description": "lowercase letters + 4 digits (e.g., i2405)",
    },
    Exchange.CZCE: {
        "case": "upper",  # SR505, SR2505, AP105
        "pattern": r"^[A-Z]{2}\d{3,4}$",
        "description": "uppercase letters + 3-4 digits (e.g., SR505 or SR2505)",
    },
    Exchange.INE: {
        "case": "lower",  # sc2506, bc2506
        "pattern": r"^[a-z]{1,2}\d{4}$",
        "description": "lowercase letters + 4 digits (e.g., sc2506)",
    },
    Exchange.SSE: {
        "case": None,  # Numeric symbols, no case change
        "pattern": r"^\d{6}$",
        "description": "6-digit numeric code (e.g., 510050, 600000)",
    },
    Exchange.SZSE: {
        "case": None,
        "pattern": r"^\d{6}$",
        "description": "6-digit numeric code (e.g., 159919, 000001)",
    },
    # Other exchanges: no validation/normalization
}


def normalize_symbol_case(symbol: str, exchange: Exchange) -> str:
    """Normalize symbol case according to exchange specifications.

    Args:
        symbol: Original symbol string
        exchange: Exchange enum

    Returns:
        Normalized symbol with correct case

    Raises:
        ValueError: If symbol doesn't match exchange pattern (when pattern is defined)
    """
    spec = _EXCHANGE_SPECS.get(exchange)
    if not spec:
        # No specification for this exchange, return as-is
        return symbol

    # Normalize case
    case_style = spec["case"]
    if case_style == "upper":
        normalized = symbol.upper()
    elif case_style == "lower":
        normalized = symbol.lower()
    else:
        normalized = symbol

    # Validate pattern (optional)
    pattern = spec.get("pattern")
    if pattern and not re.match(pattern, normalized):
        description = spec.get("description", "unknown format")
        raise ValueError(
            f"Invalid {exchange.value} symbol '{symbol}'. Expected format: {description}"
        )

    return normalized


def normalize_exchange_symbol(exchange_symbol: str, exchange: Exchange, trading_date: date) -> str:
    """Normalize exchange symbol for case and CZCE 3-digit year codes.

    This function performs two types of normalization:
    1. Case normalization according to exchange specifications
    2. CZCE 3-digit year expansion (SR505 → SR2505)

    CZCE uses 3-digit year codes where:
    - The code is parsed as: last digit of year + 2-digit month
    - We use trading_date to determine the appropriate century

    Algorithm:
    1. First normalize case according to exchange specs
    2. For CZCE symbols with 3-digit code (e.g., "SR505"):
       - First digit: last digit of year (0-9)
       - Last two digits: month (01-12)
    3. Determine the century based on trading_date:
       - Find the nearest future contract date
       - If the same year-month already passed in trading_date, use next occurrence

    Example with trading_date=2024-01-15:
        "sr505" → "SR2505" (case normalized to upper, expanded to May 2025)
        "AG2501" → "ag2501" (SHFE uses lowercase)

    For non-CZCE exchanges, only case normalization is applied.
    """
    # First normalize case according to exchange specs
    normalized = normalize_symbol_case(exchange_symbol, exchange)

    # Only CZCE needs year expansion
    if exchange != Exchange.CZCE:
        return normalized

    # Check if symbol matches CZCE 3-digit pattern: letters + 3 digits
    match = re.match(r"([A-Z]+)(\d{3})$", normalized)
    if not match:
        # Either already 4-digit or not a standard contract symbol
        return normalized

    product_code = match.group(1)
    year_month_code = match.group(2)

    # Parse the code
    last_digit_of_year = int(year_month_code[0])  # 0-9
    month = int(year_month_code[1:3])  # 01-12

    # Get current year and century from trading_date
    current_year = trading_date.year
    current_century = current_year // 100  # e.g., 2024 -> 20
    current_decade = (current_year % 100) // 10  # tens digit of year

    # Start with the current decade
    candidate_year = current_century * 100 + current_decade * 10 + last_digit_of_year

    # Check if the candidate year-month has already passed
    candidate_date = date(candidate_year, month, 1)
    if candidate_date <= trading_date:
        # If passed or same month, use next occurrence (add 10 years)
        candidate_year += 10

    # Handle special case: if we're at the end of a century (e.g., 2099 → 2100)
    if candidate_year // 100 != current_century:
        # We've crossed a century boundary, adjust century
        # This is rare but could happen near century boundaries
        pass  # candidate_year already updated correctly

    # Format as 4-digit year + 2-digit month
    # Note: CZCE normalized format uses full 4-digit year
    normalized_year_month = f"{candidate_year % 100:02d}{month:02d}"

    return f"{product_code}{normalized_year_month}"


class Instrument(BaseModel):
    """Base class for all tradable instruments.

    Attributes:
        symbol: Internal symbol format "EXCHANGE.SYMBOL" (e.g., "SHFE.ag2501", "CFFEX.IF2506")
        exchange_symbol: Exchange-specific symbol format (e.g., "ag2501", "IF2506")
        product: Product code (e.g., "ag" for SHFE silver, "IF" for CFFEX stock index)
        exchange: Exchange code
        asset_type: Asset type (FUTURE, STOCK, OPTION, etc.)

    Notes:
        - exchange_symbol and product are automatically normalized according to exchange specs
        - SHFE/DCE/INE: lowercase (ag2501, i2405)
        - CFFEX/CZCE: uppercase (IF2506, SR2505)
    """

    symbol: str
    exchange_symbol: str
    product: str
    exchange: Exchange
    asset_type: AssetType  # 无默认值，由子类设置
    currency: Currency | None = None  # If None, inferred from exchange

    @model_validator(mode="after")
    def validate_and_normalize_symbol(self) -> "Instrument":
        """Validate symbol format and normalize exchange_symbol/product case.

        This validator:
        1. Validates internal symbol format (EXCHANGE.SYMBOL)
        2. Normalizes exchange_symbol case according to exchange specs
        3. Normalizes product case to match exchange_symbol
        4. Sets default currency based on exchange if not specified
        """
        # Validate internal symbol format
        if "." not in self.symbol:
            raise ValueError(f"Symbol must be in format 'EXCHANGE.SYMBOL', got: {self.symbol}")
        expected_prefix = f"{self.exchange.value}."
        if not self.symbol.startswith(expected_prefix):
            raise ValueError(
                f"Symbol {self.symbol} must start with exchange prefix {expected_prefix}"
            )

        # Normalize exchange_symbol case (but skip pattern validation here
        # because it's already called in Future.create() before construction)
        spec = _EXCHANGE_SPECS.get(self.exchange)
        if spec:
            case_style = spec["case"]
            if case_style == "upper":
                self.exchange_symbol = self.exchange_symbol.upper()
                self.product = self.product.upper()
            elif case_style == "lower":
                self.exchange_symbol = self.exchange_symbol.lower()
                self.product = self.product.lower()

        # Set default currency based on exchange if not specified
        if self.currency is None:
            self.currency = EXCHANGE_DEFAULT_CURRENCY.get(self.exchange, Currency.USD)

        return self


class Future(Instrument):
    """Futures contract specification.

    Attributes:
        multiplier: Contract multiplier (e.g., 10 for SHFE silver)
        maturity_date: Contract maturity/expiration date
        maturity_date_estimated: True if maturity_date is computed (e.g., from symbol regex),
            False if from authoritative source (e.g., exchange infotable via TSL)
        contract_metadata_provenance: Optional helper classification for how contract metadata
            was sourced or defaulted
        margin_rate: Initial margin rate (e.g., 0.10 for 10%)
        tick_size: Minimum price movement (e.g., 1.0)
        commissions: Commission structure with rate keys ("open", "close", "close_today")
            and additive fixed-fee keys ("open_fixed", "close_fixed", "close_today_fixed")
    """

    # 在 Future 子类中设置默认的 asset_type
    asset_type: AssetType = AssetType.FUTURE

    multiplier: float = Field(gt=0, description="Contract multiplier, must be > 0")
    maturity_date: date | None = None
    maturity_date_estimated: bool = Field(
        default=False,
        description="True if maturity_date is computed, False if from exchange",
    )
    contract_metadata_provenance: str | None = Field(
        default=None,
        description="Optional classification for helper/defaulted contract metadata provenance",
    )
    margin_rate: float = Field(ge=0, le=1, description="Margin rate between 0 and 1")
    tick_size: float = Field(gt=0, description="Tick size, must be > 0")
    commissions: FutureCommissionPayload = Field(
        default_factory=lambda: dict(DEFAULT_FUTURE_COMMISSIONS)
    )

    @classmethod
    def create(
        cls,
        exchange_symbol: str,
        exchange: Exchange,
        product: str,
        multiplier: float,
        margin_rate: float,
        tick_size: float,
        trading_date: date,  # 新增参数
        maturity_date: date | None = None,
        maturity_date_estimated: bool = False,
        contract_metadata_provenance: str | None = None,
        commissions: FutureCommissionPayload | None = None,
        currency: Currency | None = None,  # If None, inferred from exchange
    ) -> "Future":
        """Factory method to create a Future with automatic symbol normalization.

        Handles CZCE 3-digit year normalization using trading_date.

        Note:
            - symbol (internal): Uses 4-digit year for CZCE (e.g., "CZCE.SR2505")
            - exchange_symbol: Preserves original format for order placement (e.g., "SR505")
              Only case normalization is applied, not year expansion.
            - currency: If not specified, defaults based on exchange
              (CNY for China, USD for US, etc.)
            - maturity_date_estimated: True if maturity_date is computed (e.g., from
              symbol regex), False if from authoritative source (e.g., exchange infotable)
        """
        # For internal symbol: full normalization including CZCE 3→4 digit conversion
        normalized_for_internal = normalize_exchange_symbol(exchange_symbol, exchange, trading_date)
        internal_symbol = f"{exchange.value}.{normalized_for_internal}"

        # For exchange_symbol: only case normalization, preserve original format for trading
        normalized_exchange_symbol = normalize_symbol_case(exchange_symbol, exchange)

        # Prepare commissions dict
        comms = commissions or dict(DEFAULT_FUTURE_COMMISSIONS)

        return cls(
            symbol=internal_symbol,
            exchange_symbol=normalized_exchange_symbol,
            product=product,
            exchange=exchange,
            multiplier=multiplier,
            maturity_date=maturity_date,
            maturity_date_estimated=maturity_date_estimated,
            contract_metadata_provenance=contract_metadata_provenance,
            margin_rate=margin_rate,
            tick_size=tick_size,
            commissions=comms,
            currency=currency,
        )


class Option(Instrument):
    """Options contract specification for CFFEX stock index options (MO/IO).

    Attributes:
        strike: Strike price (e.g., 6100.0)
        expiry: Expiry date of the option contract
        option_type: Call or Put (from pricing.models.OptionType)
        underlying_symbol: Underlying futures symbol (e.g., "IM2503")
        multiplier: Contract multiplier (e.g., 100)
        tick_size: Minimum price movement (e.g., 0.2)
        margin_rate: Initial margin rate (e.g., 0.12 for 12%)
    """

    asset_type: AssetType = AssetType.OPTION

    strike: float = Field(gt=0, description="Strike price")
    expiry: date = Field(description="Expiry date")
    option_type: str = Field(description="Option type: 'call' or 'put'")
    exercise_style: Literal["european", "american"] = Field(
        default="european",
        description="Exercise style; CFFEX index options are European, most commodity options American",
    )
    commissions: dict[str, float] = Field(default_factory=dict)
    underlying_symbol: str = Field(description="Underlying symbol (e.g., IM2503)")
    multiplier: float = Field(gt=0, description="Contract multiplier")
    tick_size: float = Field(gt=0, description="Minimum price movement")
    margin_rate: float = Field(ge=0, le=1, description="Margin rate between 0 and 1")

    @classmethod
    def create(
        cls,
        exchange_symbol: str,
        exchange: Exchange,
        underlying_symbol: str,
        strike: float,
        expiry: date,
        option_type: str,
        multiplier: float,
        tick_size: float,
        margin_rate: float,
        trading_date: date,
    ) -> "Option":
        """Factory method to create an Option with automatic symbol normalization.

        Args:
            exchange_symbol: Exchange symbol (e.g., "MO2503-C-6100")
            exchange: Exchange enum (e.g., Exchange.CFFEX)
            underlying_symbol: Underlying futures symbol (e.g., "IM2503")
            strike: Strike price
            expiry: Expiry date
            option_type: "call" or "put"
            multiplier: Contract multiplier
            tick_size: Minimum price movement
            margin_rate: Margin rate (0-1)
            trading_date: Trading date for normalization
        """
        normalized = normalize_symbol_case(exchange_symbol, exchange)
        internal_symbol = f"{exchange.value}.{normalized}"

        # Extract product from exchange_symbol (letters before first digit)
        match = re.match(r"^([A-Za-z]+)", exchange_symbol)
        product = match.group(1).upper() if match else ""

        return cls(
            symbol=internal_symbol,
            exchange_symbol=normalized,
            product=product,
            exchange=exchange,
            strike=strike,
            expiry=expiry,
            option_type=option_type,
            underlying_symbol=underlying_symbol,
            multiplier=multiplier,
            tick_size=tick_size,
            margin_rate=margin_rate,
        )


class Stock(Instrument):
    """Stock or ETF instrument.

    Unlike futures/options, stocks have no multiplier, margin, or expiry.
    This is the simplest instrument type.

    Attributes:
        asset_type: AssetType.STOCK or AssetType.ETF
        lot_size: Trading lot size (default: 100 shares per lot)
        board_type: Board classification ("main", "gem", "star")
        price_limit_pct: Daily price limit as fraction (e.g., 0.10 = 10%)
    """

    # No default -- caller must specify STOCK or ETF
    asset_type: AssetType
    lot_size: int = 100
    board_type: str = "main"
    price_limit_pct: float = 0.10

    @classmethod
    def create(
        cls,
        exchange_symbol: str,
        exchange: Exchange,
        asset_type: AssetType = AssetType.ETF,
        *,
        lot_size: int = 100,
        board_type: str = "main",
        price_limit_pct: float = 0.10,
    ) -> "Stock":
        """Factory method with automatic symbol construction.

        Args:
            exchange_symbol: Exchange symbol (e.g., "510050", "600000")
            exchange: Exchange enum (SSE, SZSE)
            asset_type: STOCK or ETF (default: ETF)
            lot_size: Trading lot size (default: 100)
            board_type: Board classification ("main", "gem", "star")
            price_limit_pct: Daily price limit as fraction (e.g., 0.10 = 10%)
        """
        internal_symbol = f"{exchange.value}.{exchange_symbol}"
        return cls(
            symbol=internal_symbol,
            exchange_symbol=exchange_symbol,
            product=exchange_symbol,
            exchange=exchange,
            asset_type=asset_type,
            lot_size=lot_size,
            board_type=board_type,
            price_limit_pct=price_limit_pct,
        )


class InstrumentRegistry:
    """Registry for instrument lookup and cross-exchange disambiguation.

    Each InstrumentRegistry instance maintains its own independent registry,
    allowing for:
    - Test isolation (no shared state between tests)
    - Parallel backtests (each backtest has its own registry)
    - Multi-strategy isolation (different strategies can have separate registries)

    Provides:
    - register(): Register an instrument
    - get(): Get instrument by symbol with disambiguation
    - get_or_none(): Safe get returning None if not found
    - list_all(): List all registered instruments
    - list_by_exchange(): List instruments by exchange

    Handles cross-exchange symbol ambiguity (e.g., "AG" on SHFE vs DCE).

    Note:
        The singleton pattern was removed in favor of explicit instance management.
        Pass registry instances through the system rather than relying on global state.
    """

    _registry: dict[str, Instrument]

    def __init__(self) -> None:
        """Initialize a new empty InstrumentRegistry instance."""
        self._registry = {}

    def register(self, instrument: Instrument) -> None:
        """Register an instrument in the global registry."""
        self._registry[instrument.symbol] = instrument

    def register_many(self, instruments: Iterable[Instrument]) -> None:
        """Atomically register a validated batch without exposing partial state."""
        batch = tuple(instruments)
        symbols: set[str] = set()
        for instrument in batch:
            if not isinstance(instrument, Instrument):
                raise TypeError("register_many requires Instrument instances")
            if instrument.symbol in symbols:
                raise ValueError(f"duplicate instrument symbol in batch: {instrument.symbol}")
            symbols.add(instrument.symbol)
        replacement = self._registry.copy()
        for instrument in batch:
            replacement[instrument.symbol] = instrument
        self._registry = replacement

    def get(self, symbol: str) -> Instrument:
        """Get instrument by symbol.

        Args:
            symbol: Symbol in one of these formats:
                - Internal format: "SHFE.ag2501", "CFFEX.IF2506"
                - Exchange symbol: "ag2501", "IF2506"

        Returns:
            Instrument instance

        Raises:
            KeyError: If symbol not found
            ValueError: If ambiguous symbol (multiple exchanges have same exchange_symbol)

        Note:
            Product code queries (e.g., "IF", "ag") are NOT supported due to high
            ambiguity. Use full exchange_symbol or internal format instead.
        """
        # If symbol already in internal format, direct lookup
        if "." in symbol:
            return self._registry[symbol]

        # Try to find by exchange_symbol (exact match only)
        exchange_symbol_matches = []

        for instrument in self._registry.values():
            if instrument.exchange_symbol == symbol:
                exchange_symbol_matches.append(instrument)

        if not exchange_symbol_matches:
            raise KeyError(f"No instrument found for symbol: {symbol}")

        if len(exchange_symbol_matches) == 1:
            return exchange_symbol_matches[0]

        # Multiple exchanges have same exchange_symbol
        exchanges = sorted({inst.exchange.value for inst in exchange_symbol_matches})
        raise ValueError(
            f"Ambiguous exchange symbol '{symbol}' matches multiple exchanges: "
            f"{exchanges}. Please specify exchange using format 'EXCHANGE.{symbol}'"
        )

    def get_or_none(self, symbol: str) -> Instrument | None:
        """Safe version of get() that returns None if instrument not found."""
        try:
            return self.get(symbol)
        except (KeyError, ValueError):
            return None

    def list_all(self) -> list[Instrument]:
        """List all registered instruments."""
        return list(self._registry.values())

    def list_by_exchange(self, exchange: Exchange | str) -> list[Instrument]:
        """List all instruments for a specific exchange."""
        exchange_str = exchange.value if isinstance(exchange, Exchange) else exchange
        exchange_str = exchange_str.upper()

        return [inst for inst in self._registry.values() if inst.exchange.value == exchange_str]

    def clear(self) -> None:
        """Clear all registered instruments (mainly for testing)."""
        self._registry.clear()

    @classmethod
    def reset(cls) -> None:
        """No-op for backwards compatibility.

        Note:
            This method was used to reset the singleton instance in the old
            singleton pattern. Now that InstrumentRegistry is no longer a
            singleton, this method is a no-op.

            For test isolation, simply create a new InstrumentRegistry()
            instance for each test, or use the clear() method on existing
            instances.

        Example:
            @pytest.fixture
            def registry():
                return InstrumentRegistry()  # Fresh instance per test
        """
        # No-op: singleton pattern removed


def extract_product(symbol: str) -> str:
    """Extract product code from symbol.

    Handles: "CFFEX.IF2412" -> "IF", "IF2412" -> "IF", "ag2501" -> "AG"
    """
    if "." in symbol:
        symbol = symbol.split(".", 1)[1]
    product = "".join(c for c in symbol if c.isalpha())
    return product.upper()


# Fallback multipliers — used ONLY when InstrumentRegistry is unavailable.
_FALLBACK_MULTIPLIERS: dict[str, float] = {
    "IF": 300,
    "IH": 300,
    "IC": 200,
    "IM": 200,
    "RB": 10,
}


def get_multiplier(
    symbol: str,
    registry: InstrumentRegistry | None = None,
) -> float:
    """Get contract multiplier for a symbol.

    Tries InstrumentRegistry first (authoritative), falls back to
    hardcoded CFFEX defaults for backward compatibility.

    WARNING: This function has fallback behavior and should NOT be used in
    strict economic paths (backtest, live, verification). Use get_multiplier_strict()
    for strict paths, or get_multiplier_fallback() for explicit non-strict usage.

    Deprecation Notice:
        For new code, prefer:
        - get_multiplier_strict() for backtest/live/verification paths
        - get_multiplier_fallback() for dashboard/analytics read-only paths
    """
    if registry is not None:
        instrument = registry.get_or_none(symbol)
        if instrument is not None and isinstance(instrument, Future):
            return instrument.multiplier
    return _FALLBACK_MULTIPLIERS.get(extract_product(symbol), 1.0)


def get_multiplier_strict(
    symbol: str,
    registry: InstrumentRegistry | None,
) -> float:
    """Get contract multiplier with strict registry requirement.

    This is the authoritative path for strict economic flows:
    - backtest execution and settlement
    - strict trace verification
    - live execution / live risk / live settlement

    Args:
        symbol: Instrument symbol (e.g., "CFFEX.IF2412" or "IF2412")
        registry: InstrumentRegistry instance (required)

    Returns:
        Contract multiplier from authoritative registry data.

    Raises:
        ValueError: If registry is None or doesn't contain the symbol.

    Example:
        >>> registry = InstrumentRegistry()
        >>> future = Future.create(
        ...     exchange_symbol="IF2412",
        ...     exchange=Exchange.CFFEX,
        ...     product="IF",
        ...     multiplier=300.0,
        ...     margin_rate=0.12,
        ...     tick_size=0.2,
        ...     trading_date=date(2024, 12, 1),
        ... )
        >>> registry.register(future)
        >>> get_multiplier_strict("CFFEX.IF2412", registry)
        300.0
    """
    if registry is None:
        raise ValueError(
            f"Cannot get multiplier for '{symbol}': InstrumentRegistry is required "
            f"for strict multiplier lookup. "
            f"Use get_multiplier_fallback() for non-strict read-only paths."
        )

    instrument = registry.get_or_none(symbol)
    if instrument is None:
        raise ValueError(
            f"Cannot get multiplier for '{symbol}': instrument not found in registry. "
            f"Register the instrument before running strict economic flows."
        )
    if not isinstance(instrument, Future):
        raise TypeError(
            "Cannot get multiplier for "
            f"'{symbol}': expected Future, got {type(instrument).__name__}"
        )
    return instrument.multiplier


def get_multiplier_fallback(symbol: str) -> float:
    """Get contract multiplier using product-level fallback table.

    This is the NON-STRICT path for read-only tooling:
    - dashboard convenience views
    - exploratory analytics

    DO NOT use in strict economic paths (backtest, live, verification).
    Use get_multiplier_strict() for those cases.

    Args:
        symbol: Instrument symbol (e.g., "CFFEX.IF2412" or "IF2412")

    Returns:
        Product-level default multiplier from fallback table, or 1.0 if unknown.
    """
    return _FALLBACK_MULTIPLIERS.get(extract_product(symbol), 1.0)
