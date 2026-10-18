#!/usr/bin/env bash
set -euo pipefail

ruff check sgbridgebot tests
mypy
pytest -q
