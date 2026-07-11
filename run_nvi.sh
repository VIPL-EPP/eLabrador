#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCH_FILE="${1:-blind_dreamer.launch}"
shift || true

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
else
  echo "Missing .env at $ROOT_DIR/.env" >&2
  exit 1
fi

source "$ROOT_DIR/edge/devel/setup.bash"

exec roslaunch nvi_bringup "$LAUNCH_FILE" "$@"