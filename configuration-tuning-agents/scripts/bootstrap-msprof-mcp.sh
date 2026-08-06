#!/usr/bin/env bash
# Compatibility shim — canonical script lives in the skill:
#   configuration-tuning-skills/msprof-mcp-setup/scripts/bootstrap-msprof-mcp.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$(cd "$SCRIPT_DIR/../../configuration-tuning-skills/msprof-mcp-setup/scripts" && pwd)/bootstrap-msprof-mcp.sh"
if [ ! -f "$TARGET" ]; then
  echo "error: canonical bootstrap not found: $TARGET" >&2
  exit 1
fi
exec bash "$TARGET" "$@"
