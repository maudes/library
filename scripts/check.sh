#!/usr/bin/env bash
# The pre-push gate: PII/secret scan, then the test suite. Same checks CI runs.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY scripts/pii_check.py
$PY -m pytest -q
