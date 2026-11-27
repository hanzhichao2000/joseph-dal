from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fake_cne import COVERAGE_START, LakeConfigurer, default_lake, install_fake_cne


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


@pytest.fixture
def cne(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LakeConfigurer:
    """Install the fake `cne`; the returned function configures the lake it serves."""
    path = install_fake_cne(tmp_path)

    def _configure(lake: dict[str, Any]) -> str:
        monkeypatch.setenv("FAKE_CNE_LAKE", json.dumps(lake))
        return path

    return _configure


@pytest.fixture
def lake_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Every lake CLI call the provider makes."""
    calls: list[list[str]] = []
    real = subprocess.run

    def _run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:  # type: ignore[type-arg]
        calls.append(cmd)
        return real(cmd, **kwargs)

    monkeypatch.setattr("joseph_dal_cnequity.subprocess.run", _run)
    return calls


__all__ = ["COVERAGE_START", "LakeConfigurer", "default_lake", "fake_entry_points", "fake_provider"]
