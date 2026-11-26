from __future__ import annotations

import stat
from datetime import date
from pathlib import Path

from joseph_dal_cnequity import CnequityProvider, load_receipt

from joseph_dal import verify_revision
from joseph_dal.protocols import Window


def _fake_cne(tmp_path: Path) -> str:
    script = tmp_path / "cne"
    script.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "--version" ]; then echo "cne, version 0.25.0"; exit 0; fi\n'
        'out=""; start=""; end=""; ds=""; shift 2\n'  # skip "storage export"
        'while [ $# -gt 0 ]; do case "$1" in --out) out="$2"; shift 2;; --start) start="$2"; shift 2;;'
        ' --end) end="$2"; shift 2;; *) ds="$1"; shift;; esac; done\n'
        'mkdir -p "$out/$ds" && printf "PARquet-%s-%s-%s" "$ds" "$start" "$end" > "$out/$ds/part-0.parquet"\n'
        'printf "sidecar" > "$out/$ds/manifest.json"\n',
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


def test_export_produces_verifiable_revision(tmp_path: Path):
    cne = _fake_cne(tmp_path)
    provider = CnequityProvider(cne_bin=cne)
    out = tmp_path / "out"
    rec = provider.export("option_bars", Window(start=date(2024, 1, 1), end=date(2024, 3, 31)), out)
    assert rec.source == "cnequity@0.25.0"
    assert {f.path for f in rec.files} == {
        "option_bars/part-0.parquet",
        "option_bars/manifest.json",
    }
    assert all(not p.startswith("/") for p in (f.path for f in rec.files))
    verify_revision(out, rec)
    assert load_receipt(out / "option_bars.revision.json") == rec
    assert rec.revision_id.startswith("option_bars:2024-01-01:2024-03-31:")


def test_capabilities_declare_source_and_history_mode(tmp_path: Path):
    provider = CnequityProvider(cne_bin=_fake_cne(tmp_path))
    caps = {c.capability_id: c for c in provider.capabilities}
    assert caps["option_bars"].source == "cnequity@0.25.0"
    assert caps["option_bars"].history_mode == "by_date"
    assert provider.replay_policy == "idempotent_refetch"
