"""joseph-dal: contract-only DAL host. Imports no provider; discovers them by entry points."""

from joseph_dal.exceptions import (
    DalHostError,
    LiveTransportRefused,
    ProviderDiscoveryError,
    RevisionVerificationError,
)
from joseph_dal.host import admit, discover_providers, locate
from joseph_dal.protocols import (
    PROVIDER_ENTRY_POINT_GROUP,
    CapabilityDeclaration,
    DataProvider,
    Preflight,
    ReadPolicy,
    ReplayPolicy,
    RevisionLocator,
    Transport,
    Window,
)
from joseph_dal.verify import verify_revision

__all__ = [
    "PROVIDER_ENTRY_POINT_GROUP",
    "CapabilityDeclaration",
    "DalHostError",
    "DataProvider",
    "LiveTransportRefused",
    "Preflight",
    "ProviderDiscoveryError",
    "ReadPolicy",
    "ReplayPolicy",
    "RevisionLocator",
    "RevisionVerificationError",
    "Transport",
    "Window",
    "admit",
    "discover_providers",
    "locate",
    "verify_revision",
]
