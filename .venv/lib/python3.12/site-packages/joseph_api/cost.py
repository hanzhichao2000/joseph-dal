"""Cost configuration models for trading costs.

CostConfig represents the commission and margin configuration for a specific contract,
loaded from DAL (active_contracts CSV files) rather than hardcoded in YAML.

This enables:
- Dynamic cost loading based on trading date (historical costs may differ)
- Consistency between DAL instrument data and cost model
- Override capability for testing/custom configurations
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

__test_case_metadata__ = {"defaults": {"components": ("models",), "domains": ("futures",)}}

AccountMarginBasis = Literal["gross", "cffex_index_larger_side"]


class CostConfig(BaseModel):
    """Cost configuration for a contract or product.

    Contains commission rates, margin requirements, and other cost-related parameters
    typically loaded from DAL active_contracts CSV files.

    Attributes:
        commission_open: Commission rate for opening positions (as proportion, e.g., 0.000023)
        commission_close: Commission rate for closing positions
        commission_close_today: Commission rate for same-day closing
        margin_rate: Initial margin requirement (e.g., 0.08 for 8%)
        multiplier: Contract multiplier (e.g., 300 for IF)
        tick_size: Minimum price movement
        effective_date: Date this configuration is effective from (for time-series queries)

    Example:
        >>> from datetime import date
        >>> config = CostConfig(
        ...     commission_open=0.000023,
        ...     commission_close=0.000023,
        ...     commission_close_today=0.0000345,
        ...     margin_rate=0.08,
        ...     multiplier=300.0,
        ...     tick_size=0.2,
        ...     effective_date=date(2024, 12, 20),
        ... )
        >>> config.get_close_today_penalty()
        1.5
    """

    commission_open: float = Field(default=0.0, ge=0, description="Opening commission rate")
    commission_close: float = Field(default=0.0, ge=0, description="Closing commission rate")
    commission_close_today: float = Field(
        default=0.0, ge=0, description="Same-day closing commission rate"
    )
    margin_rate: float = Field(default=0.08, ge=0, le=1, description="Margin rate (0-1)")
    multiplier: float = Field(default=1.0, gt=0, description="Contract multiplier")
    tick_size: float = Field(default=0.01, gt=0, description="Minimum price movement")
    effective_date: date | None = Field(
        default=None, description="Date this config is effective from"
    )

    def get_close_today_penalty(self) -> float:
        """Calculate close-today penalty multiplier.

        Returns:
            Ratio of close_today to close rate, or 1.0 if close rate is 0.

        Example:
            If commission_close = 0.000023 and commission_close_today = 0.0000345,
            penalty = 0.0000345 / 0.000023 = 1.5
        """
        if self.commission_close > 0:
            return self.commission_close_today / self.commission_close
        elif self.commission_open > 0:
            return self.commission_close_today / self.commission_open
        else:
            return 1.0

    def has_valid_rates(self) -> bool:
        """Check if this config has valid (non-zero) commission rates.

        Returns:
            True if at least one commission rate is non-zero.
        """
        return self.commission_open > 0 or self.commission_close > 0


class ProductCostConfig(BaseModel):
    """Cost configuration for a product (aggregated from contracts).

    When loading costs from DAL, we may have multiple contracts for the same product
    (e.g., IF2412, IF2501, IF2503). This class aggregates them to a product-level config.

    Attributes:
        product: Product code (e.g., "IF", "IC")
        configs: List of CostConfig for each contract in this product
        default_config: Default config to use when no specific contract config found
    """

    product: str = Field(description="Product code")
    configs: dict[str, CostConfig] = Field(
        default_factory=dict, description="Contract symbol -> CostConfig mapping"
    )

    def get_config(self, symbol: str | None = None) -> CostConfig | None:
        """Get cost config for a specific contract or product default.

        Args:
            symbol: Optional contract symbol (e.g., "IF2412")

        Returns:
            CostConfig if found, None otherwise
        """
        if symbol and symbol in self.configs:
            return self.configs[symbol]
        # Return first available config as default
        if self.configs:
            return next(iter(self.configs.values()))
        return None
