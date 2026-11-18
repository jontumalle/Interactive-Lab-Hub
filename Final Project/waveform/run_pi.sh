#!/usr/bin/env bash
# Temporarily give the receiver ownership of the lab screen.
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Create .venv and install requirements-pi.txt first.' >&2
  exit 1
fi
restore_screen=0
cleanup() {
  if [[ "$restore_screen" == 1 ]]; then
    sudo systemctl start piscreen.service || echo 'Could not restore piscreen.service; run sudo systemctl start piscreen.service.' >&2
  fi
}
trap cleanup EXIT
if command -v systemctl >/dev/null && systemctl is-active --quiet piscreen.service; then
  sudo systemctl stop piscreen.service
  restore_screen=1
fi
.venv/bin/python play.py "$@"
