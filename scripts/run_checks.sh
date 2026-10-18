#!/usr/bin/env bash
set -euo pipefail

ruff check sgbridgebot tools tests
mypy
pytest -q
