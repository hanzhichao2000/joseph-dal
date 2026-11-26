"""cnequity provider: shells out to the lake CLI (never imports cnequity) and returns a revision."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from joseph_api import RevisionFile, RevisionRecord, RevisionWindow

from joseph_dal.protocols import CapabilityDeclaration, ReplayPolicy, Transport, Window

_DATASETS: dict[str, str] = {
    "instruments": "core",
    "index_constituents": "core",
    "index_bars": "core",
    "daily_bars": "core",
    "futures_bars": "optional",
    "futures_contracts": "optional",
    "option_contracts": "optional",
    "option_bars": "optional",
}
_SCHEMA_VERSION = "cne-contract-0.25.0"


class CnequityProvider:
    provider_id = "cnequity"
    transports: tuple[Transport, ...] = ("live", "file")
    replay_policy: ReplayPolicy = "idempotent_refetch"

    def __init__(self, cne_bin: str = "cne", source_version: str | None = None) -> None:
        self._cne_bin = cne_bin
        self._source_version = source_version

    def _version(self) -> str:
        if self._source_version is None:
            out = subprocess.run(
                [self._cne_bin, "--version"], capture_output=True, text=True, check=True
            )
            self._source_version = out.stdout.strip().split()[-1]
        return self._source_version

    @property
    def capabilities(self) -> tuple[CapabilityDeclaration, ...]:
        source = f"cnequity@{self._version()}"
        return tuple(
            CapabilityDeclaration(
                capability_id=ds,
                schema_version=_SCHEMA_VERSION,
                source=source,
                history_mode="by_date",
            )
            for ds in _DATASETS
        )

    def export(self, capability: str, window: Window, out_dir: Path) -> RevisionRecord:
        if capability not in _DATASETS:
            raise ValueError(f"unknown cnequity dataset {capability!r}")
        out_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                self._cne_bin,
                "storage",
                "export",
                "--out",
                str(out_dir),
                "--start",
                window.start.isoformat(),
                "--end",
                window.end.isoformat(),
                capability,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        dataset_dir = out_dir / capability
        files = tuple(
            RevisionFile(
                path=p.relative_to(out_dir).as_posix(),
                digest=hashlib.sha256(p.read_bytes()).hexdigest(),
                size=p.stat().st_size,
            )
            for p in sorted(dataset_dir.rglob("*"))
            if p.is_file()
        )
        if not files:
            raise RuntimeError(f"cne storage export wrote no files for {capability!r}")
        source = f"cnequity@{self._version()}"
        digest = RevisionRecord.compute_content_digest(capability, _SCHEMA_VERSION, source, files)
        record = RevisionRecord(
            capability_id=capability,
            schema_version=_SCHEMA_VERSION,
            source=source,
            revision_id=f"{capability}:{window.start}:{window.end}:{digest[:12]}",
            content_digest=digest,
            files=files,
            window=RevisionWindow(start=window.start, end=window.end),
        )
        (out_dir / f"{capability}.revision.json").write_text(record.to_json(), encoding="utf-8")
        return record

    def locate(self, record: RevisionRecord, root: Path) -> Path:
        return root / record.files[0].path


def load_receipt(path: Path) -> RevisionRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RevisionRecord.model_validate(data)


__all__ = ["CnequityProvider", "load_receipt"]
