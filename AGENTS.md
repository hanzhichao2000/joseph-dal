# joseph-dal contributor instructions

This repository owns the DAL host, provider protocols, and revision verification.
Discover providers by entry point. Keep provider-specific imports and behavior in plugins.
Replay reads pinned revisions. Strict-local admission refuses live transports.

## Local checks

Run from the repository root with Python 3.11 or newer. The development checks match
`.github/workflows/ci.yml`.

```sh
check_dir=$(mktemp -d)
python3 tools/check_keywords.py keywords/public-boundary.txt .
python3 -m venv "$check_dir/dev"
"$check_dir/dev/bin/python" -m pip install -e '.[dev]' -e providers/cnequity
"$check_dir/dev/bin/ruff" check src tests providers
"$check_dir/dev/bin/ruff" format --check src tests providers
"$check_dir/dev/bin/mypy"
"$check_dir/dev/bin/pytest" -q
```

The public keyword check runs offline with the checker and publishable wordlist
vendored from `joseph-docs-public`. Keep the two files in sync with their public source.

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
immutable Git commit SHA. Update both files together using the same SHA. The current pin is
`2dd66417f4f85325f41fbaef4389448c4810a3d0`.
When this repository needs new API behavior, such as the option-row DTOs from
[joseph-api PR #10](https://github.com/hanzhichao2000/joseph-api/pull/10),
update the pin after the API PR merges, using the full SHA of the merged commit.

## Public contributions

- Use `codex/<topic>-<issue number>` for the branch. Keep planning and coordination in the owning internal
  issue. Public PRs require approval from a private-project lead.
- In `joseph-docs-public` only, add new public-layer Markdown files to `public-layer.allow`
  in the same PR and keep each file at or below 200 lines.
- Scan public changes for vendor names, private paths and URLs, credentials, and proprietary
  strategy identifiers. Keep internal roadmap details and evidence out of public files and PR text.
- Record verification commands, results, exact repository SHAs, and CI run links in the owning
  internal issue. Include the pinned revision IDs when relevant. Keep raw logs, research evidence,
  and generated reports out of this repository. Follow the public
  [evidence and claims contract](https://github.com/hanzhichao2000/joseph-docs-public/blob/main/contracts/evidence-and-claims.md).
