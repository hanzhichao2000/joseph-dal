"""Canonical JSON encoding and hashing for content-addressed contracts.

One pass through the standard library's C encoder: ``json.dumps`` with ``default=`` for the few
Python types JSON does not know (dataclasses, enums, dates, datetimes), ``allow_nan=False`` for the
finite-float rule and ``skipkeys=False`` for the string-key rule. No third-party package needed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any


def canonical_json_bytes(value: object) -> bytes:
    """Return the stable UTF-8 JSON encoding used by content-addressed contracts."""
    _assert_string_keys(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
        default=_canonical_default,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    """Return a tagged SHA-256 digest over :func:`canonical_json_bytes`."""
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_default(value: object) -> Any:
    """Encode what JSON cannot: dataclasses, enums, dates, timezone-aware datetimes."""
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: getattr(value, item.name) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical datetimes must be timezone-aware")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def _assert_string_keys(value: object) -> None:
    """json.dumps coerces int keys to strings; the contract requires string keys, so check containers."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical mappings require string keys")
            _assert_string_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_string_keys(item)
