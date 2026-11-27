from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from joseph_dal.protocols import CapabilityDeclaration


def test_capability_declaration_carries_coverage_start_and_derived_from() -> None:
    decl = CapabilityDeclaration(
        capability_id="option_greeks",
        schema_version="cne-contract-0.25.0",
        source="cnequity@0.25.0",
        history_mode="by_date",
        coverage_start=date(2023, 11, 26),
        derived_from=("option_bars", "option_contracts"),
    )
    assert decl.coverage_start == date(2023, 11, 26)
    assert decl.derived_from == ("option_bars", "option_contracts")
    assert decl.window_limits is None


def test_capability_declaration_defaults_the_new_fields() -> None:
    decl = CapabilityDeclaration(
        capability_id="option_contracts",
        schema_version="cne-contract-0.25.0",
        source="cnequity@0.25.0",
        history_mode="snapshot_only",
    )
    assert decl.coverage_start is None and decl.derived_from is None


def test_capability_declaration_still_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="floor"):
        CapabilityDeclaration(
            capability_id="option_bars",
            schema_version="cne-contract-0.25.0",
            source="cnequity@0.25.0",
            history_mode="by_date",
            floor=date(2023, 11, 26),
        )
