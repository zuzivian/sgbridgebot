#!/usr/bin/env bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

python -m piptools compile --quiet --no-header --strip-extras --generate-hashes --output-file="$tmp_dir/requirements.txt" requirements.in
python -m piptools compile --quiet --no-header --strip-extras --generate-hashes --output-file="$tmp_dir/requirements-dev.txt" requirements-dev.in

if ! diff -u requirements.txt "$tmp_dir/requirements.txt"; then
  echo "requirements.txt is out of date. Regenerate with pip-compile." >&2
  exit 1
fi

if ! diff -u requirements-dev.txt "$tmp_dir/requirements-dev.txt"; then
  echo "requirements-dev.txt is out of date. Regenerate with pip-compile." >&2
  exit 1
fi
