# joseph-dal contributor instructions

This repository owns the DAL host, provider protocols, and revision verification.
Discover providers by entry point. Keep provider-specific imports and behavior in plugins.
Replay reads pinned revisions. Strict-local admission refuses live transports.

## Local checks

Run from the repository root with Python 3.11 or newer. The development checks match
`.github/workflows/ci.yml`.

```sh
check_dir=$(mktemp -d)
python3 -m venv "$check_dir/dev"
"$check_dir/dev/bin/python" -m pip install -e '.[dev]' -e providers/cnequity
"$check_dir/dev/bin/ruff" check src tests providers
"$check_dir/dev/bin/ruff" format --check src tests providers
"$check_dir/dev/bin/mypy"
"$check_dir/dev/bin/pytest" -q
```

Build the host and provider wheels, then install and check them in a separate, fresh
environment outside the source tree.

```sh
"$check_dir/dev/bin/python" -m pip wheel --no-deps --wheel-dir "$check_dir/wheels" . ./providers/cnequity
python3 -m venv "$check_dir/clean"
(
  set -e
  cd "$check_dir"
  ./clean/bin/python -m pip install wheels/joseph_dal-*.whl wheels/joseph_dal_cnequity-*.whl
  ./clean/bin/python - <<'PYTHON'
from importlib.metadata import entry_points

from joseph_dal import PROVIDER_ENTRY_POINT_GROUP

plugins = entry_points(group=PROVIDER_ENTRY_POINT_GROUP)
assert any(plugin.name == "cnequity" and callable(plugin.load()) for plugin in plugins)
PYTHON
)
```

Both `pyproject.toml` and `providers/cnequity/pyproject.toml` pin `joseph-api` to a full,
immutable Git commit SHA. Update both together when changing the pin. The current pin is
`2dd66417f4f85325f41fbaef4389448c4810a3d0`.

## Public contributions

- Use `codex/<topic>-<issue number>` for the branch. Keep planning and coordination in the owning internal
  issue. Public PRs require approval from a private-project lead.
- Scan public changes for vendor names, private paths and URLs, credentials, and proprietary
  strategy identifiers. Keep internal roadmap details and evidence out of public files and PR text.
- Record verification commands, results, exact repository SHAs, and CI run links in the owning
  internal issue. Include the pinned revision IDs when relevant. Keep raw logs, research evidence,
  and generated reports out of this repository. Follow the public
  [evidence and claims contract](https://github.com/hanzhichao2000/joseph-docs-public/blob/main/contracts/evidence-and-claims.md).
