"""Host exceptions. None of them names a provider unless the caller passed one in."""

from __future__ import annotations


class DalHostError(Exception):
    """Base class for joseph-dal host errors."""


class ProviderDiscoveryError(DalHostError):
    """The entry-point group could not be read or an entry point failed to load."""


class LiveTransportRefused(DalHostError):
    """A provider with a live transport was requested under strict-local mode."""

    def __init__(self, provider_id: str) -> None:
        super().__init__(
            f"provider {provider_id!r} declares a live transport; strict_local refuses it"
        )
        self.provider_id = provider_id


class RevisionVerificationError(DalHostError):
    """A revision does not match its receipt. `missing` names the file when one is absent."""

    def __init__(self, message: str, missing: str | None = None) -> None:
        super().__init__(message)
        self.missing = missing
