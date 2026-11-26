import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "joseph_dal"
TERMS = ("cnequity", "akshare", "vnpy", "tsl")


def test_host_contains_no_provider_literal():
    hits = []
    for path in sorted(ROOT.glob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        hits += [f"{path.name}: {t}" for t in TERMS if t in text]
    assert not hits, hits
