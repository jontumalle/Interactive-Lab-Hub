#!/usr/bin/env bash
# Run WordHound without competing with the Lab 2 PiTFT boot display.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(dirname "$APP_DIR")"
SCREEN_SERVICE="piscreen.service"
restore_screen=false

if sudo systemctl is-active --quiet "$SCREEN_SERVICE"; then
  sudo systemctl stop "$SCREEN_SERVICE"
  restore_screen=true
fi

restore() {
  if [ "$restore_screen" = true ]; then
    sudo systemctl start "$SCREEN_SERVICE" || true
  fi
}
trap restore EXIT HUP INT TERM

APP_COMMAND=("$LAB_DIR/.venv/bin/python" "$APP_DIR/app.py" "$@")
if id -nG | tr ' ' '\n' | grep -qx gpio; then
  "${APP_COMMAND[@]}"
else
  # The Pi image adds pi to the gpio group, but an existing SSH/VNC shell does
  # not inherit that membership until it is refreshed. sg starts only the app
  # with the group needed by Blinka/lgpio.
  printf -v QUOTED_COMMAND '%q ' "${APP_COMMAND[@]}"
  sg gpio -c "$QUOTED_COMMAND"
fi
