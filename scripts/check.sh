#!/usr/bin/env bash
# The pre-push gate: PII/secret scan, genre coverage, then the test suite.
# CI runs the same checks (genre coverage there only warns, so the monthly build never stalls).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY scripts/pii_check.py
$PY scripts/check_genres.py
$PY -m pytest -q
