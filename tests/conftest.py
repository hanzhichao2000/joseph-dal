from __future__ import annotations

import sys
from pathlib import Path

import pytest

API_SRC = Path("/home/hanzc/dev/joseph-api/src")
if API_SRC.exists():
    sys.path.insert(0, str(API_SRC))


class FakeProvider:
    provider_id = "fake"
    transports: tuple[str, ...] = ("file",)
    replay_policy = "idempotent_refetch"

    def __init__(self, transports: tuple[str, ...] = ("file",)) -> None:
        self.transports = transports

    @property
    def capabilities(self) -> tuple[object, ...]:
        return ()

    def export(self, capability: str, window: object, out_dir: Path) -> object:
        raise NotImplementedError

    def locate(self, record: object, root: Path) -> Path:
        return root


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def fake_entry_points(monkeypatch: pytest.MonkeyPatch):
    def _install(providers: dict[str, object]) -> None:
        class _EP:
            def __init__(self, name: str, obj: object) -> None:
                self.name, self._obj = name, obj

            def load(self) -> object:
                return self._obj

        from joseph_dal import host

        monkeypatch.setattr(
            host, "entry_points", lambda group: [_EP(n, o) for n, o in providers.items()]
        )

    return _install
