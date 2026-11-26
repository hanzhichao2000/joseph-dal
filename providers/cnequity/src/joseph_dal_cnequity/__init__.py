"""cnequity provider: shells out to the lake CLI (never imports cnequity) and returns a revision."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from joseph_api import RevisionFile, RevisionRecord, RevisionWindow

from joseph_dal.protocols import CapabilityDeclaration, ReplayPolicy, Transport, Window

# dataset -> (layer, has_date_column). Datasets without a date column export without a window.
_DATASETS: dict[str, tuple[str, bool]] = {
    "instruments": ("core", False),
    "index_constituents": ("core", False),
    "index_bars": ("core", True),
    "daily_bars": ("core", True),
    "futures_bars": ("optional", True),
    "futures_contracts": ("optional", False),
    "option_contracts": ("optional", False),
    "option_bars": ("optional", True),
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

    def export(self, capability: str, window: Window | None, out_dir: Path) -> RevisionRecord:
        if capability not in _DATASETS:
            raise ValueError(f"unknown cnequity dataset {capability!r}")
        _, has_date = _DATASETS[capability]
        if has_date and window is None:
            raise ValueError(f"{capability!r} is dated; a window is required")
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [self._cne_bin, "storage", "export", "--out", str(out_dir)]
        if has_date and window is not None:
            cmd += ["--start", window.start.isoformat(), "--end", window.end.isoformat()]
        cmd.append(capability)
        # The lake writes no sidecar file: the receipt (rows, files, bytes, revision_id,
        # snapshot) is the JSON document printed on stdout.
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        report = json.loads(proc.stdout[proc.stdout.index("{") :])
        exported = next(e for e in report["exported"] if e["dataset"] == capability)
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
            revision_id=f"{capability}@lake:{exported['revision_id']}",
            content_digest=digest,
            files=files,
            window=RevisionWindow(start=window.start, end=window.end) if window else None,
        )
        (out_dir / f"{capability}.revision.json").write_text(record.to_json(), encoding="utf-8")
        return record

    def locate(self, record: RevisionRecord, root: Path) -> Path:
        return root / record.files[0].path


def load_receipt(path: Path) -> RevisionRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RevisionRecord.model_validate(data)


__all__ = ["CnequityProvider", "load_receipt"]
