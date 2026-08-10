#!/usr/bin/env bash
# Bootstrap msprof-mcp the msagent way: uv tool install → expose binary → write tool MCP config.
#
# Mirrors mindstudio-agent scripts/install.sh (uv + tool install) and init.sh tool/path layout.
# NOT wired into init.sh — run manually when Profiling MCP is needed.
#
# Usage (aligned with init.sh):
#   ./bootstrap-msprof-mcp.sh [level] [tool] [install_path]
#   ./bootstrap-msprof-mcp.sh project cursor
#   ./bootstrap-msprof-mcp.sh project claude /path/to/project
#   ./bootstrap-msprof-mcp.sh project opencode
#   ./bootstrap-msprof-mcp.sh global claude
#
# Backward compatible:
#   ./bootstrap-msprof-mcp.sh /path/to/project          # → project cursor <path>
#   ./bootstrap-msprof-mcp.sh                          # → project cursor <repo root>
#
# Tools: cursor | claude | opencode | all
#   cursor   → {project}/.cursor/mcp.json  or  ~/.cursor/mcp.json
#   claude   → {project}/.mcp.json         or  ~/.claude.json
#   opencode → {project}/.opencode/opencode.json  or  ~/.config/opencode/opencode.json
#              (仅 mcp.<name> V1 字段；不写 mcp.servers / .opencode/mcp/ / 顶层 mcpServers)
#   all      → write cursor + claude + opencode targets for the same level/path
#
# Env:
#   MSPROF_MCP_PIN=msprof-mcp==0.1.8
#   MSPROF_MCP_PYTHON=                 # default: system python3≥3.11, else 3.11
#   MSPROF_MCP_CONSTRAINTS=mcp>=1.26.0,<2 pandas>=2,<3
#   USE_CN_MIRROR=1|0
#   UV_DEFAULT_INDEX= / UV_PYTHON_INSTALL_MIRROR=
#   UV_BIN=uv
#   SKIP_MCP_JSON=0|1
#   SKIP_UV_INSTALL=0|1                # 1=assume msprof-mcp already installed
#
# Skill home: configuration-tuning-skills/msprof-mcp-setup/

set -euo pipefail

if [ -t 1 ] || [ "${FORCE_COLOR:-}" = "1" ]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
  CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; DIM=''; NC=''
fi

log_info() { printf "${CYAN}▸${NC} %s\n" "$*"; }
log_ok() { printf "${GREEN}✔${NC} %s\n" "$*"; }
log_warn() { printf "${YELLOW}⚠${NC} %s\n" "$*" >&2; }
log_err() { printf "${RED}✖${NC} %s\n" "$*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# skill → configuration-tuning-skills → repo root
REPO_ROOT="$(cd "$SKILL_ROOT/../.." && pwd)"

show_help() {
  sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'
}

LEVEL="project"
TOOL="cursor"
INSTALL_PATH=""

for arg in "$@"; do
  case "$arg" in
    --help|-h) show_help; exit 0 ;;
    global|project) LEVEL="$arg" ;;
    cursor|claude|opencode|all) TOOL="$arg" ;;
    *)
      if [ -d "$arg" ]; then
        INSTALL_PATH="$arg"
      else
        log_err "Unknown argument: $arg (expected level/tool/path). Try --help"
        exit 1
      fi
      ;;
  esac
done

# Legacy: single directory arg with no explicit tool → project cursor <path>
if [ "$#" -eq 1 ] && [ -n "$INSTALL_PATH" ]; then
  LEVEL="project"
  TOOL="cursor"
fi

if [ "$LEVEL" = "global" ]; then
  case "$TOOL" in
    cursor)   CONFIG_ROOT_BASE="$HOME/.cursor"; CONFIG_ROOT="$HOME/.cursor" ;;
    claude)   CONFIG_ROOT_BASE="$HOME"; CONFIG_ROOT="$HOME/.claude" ;;
    opencode) CONFIG_ROOT_BASE="$HOME/.config/opencode"; CONFIG_ROOT="$HOME/.config/opencode" ;;
    all)      CONFIG_ROOT_BASE="$HOME"; CONFIG_ROOT="$HOME" ;;
  esac
  PROJECT_ROOT="$CONFIG_ROOT_BASE"
else
  if [ -n "$INSTALL_PATH" ]; then
    PROJECT_ROOT="$(cd "$INSTALL_PATH" && pwd)"
  else
    PROJECT_ROOT="$REPO_ROOT"
  fi
  CONFIG_ROOT_BASE="$PROJECT_ROOT"
  case "$TOOL" in
    cursor)   CONFIG_ROOT="$CONFIG_ROOT_BASE/.cursor" ;;
    claude)   CONFIG_ROOT="$CONFIG_ROOT_BASE/.claude" ;;
    opencode) CONFIG_ROOT="$CONFIG_ROOT_BASE/.opencode" ;;
    all)      CONFIG_ROOT="$CONFIG_ROOT_BASE" ;;
  esac
fi

MSPROF_MCP_PIN="${MSPROF_MCP_PIN:-msprof-mcp==0.1.8}"
# mcp 2.x removed FastMCP; pandas 3.x breaks on Windows (keep <3 on all platforms for consistency)
MSPROF_MCP_CONSTRAINTS="${MSPROF_MCP_CONSTRAINTS:-mcp>=1.26.0,<2 pandas>=2,<3}"
SKIP_MCP_JSON="${SKIP_MCP_JSON:-0}"
SKIP_UV_INSTALL="${SKIP_UV_INSTALL:-0}"
USE_CN_MIRROR="${USE_CN_MIRROR:-1}"
TOOL_BIN_DIR="${UV_TOOL_BIN_DIR:-${HOME}/.local/bin}"

if [ -z "${MSPROF_MCP_PYTHON:-}" ]; then
  if command -v python3 >/dev/null 2>&1 \
    && python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    MSPROF_MCP_PYTHON="$(command -v python3)"
  else
    MSPROF_MCP_PYTHON="3.11"
  fi
fi

if [ "${USE_CN_MIRROR}" = "1" ]; then
  export UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-https://mirrors.aliyun.com/pypi/simple/}"
  export UV_PYTHON_INSTALL_MIRROR="${UV_PYTHON_INSTALL_MIRROR:-https://mirror.nju.edu.cn/github-release/astral-sh/python-build-standalone/}"
fi

case "$(uname -s)" in
  Darwin|Linux) ;;
  MINGW*|MSYS*|CYGWIN*)
    log_err "This script targets Linux/macOS/WSL. On Windows use: pip install -U ${MSPROF_MCP_PIN}"
    exit 1
    ;;
  *)
    log_warn "Unknown OS $(uname -s); continuing anyway"
    ;;
esac

install_uv() {
  if command -v curl >/dev/null 2>&1; then
    log_info "Installing uv (astral.sh)..."
    curl -fsSL https://astral.sh/uv/install.sh | sh
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    log_info "Installing uv (astral.sh)..."
    wget -qO- https://astral.sh/uv/install.sh | sh
    return
  fi
  log_err "curl or wget is required to install uv."
  exit 1
}

resolve_uv() {
  if [ -n "${UV_BIN:-}" ] && { [ -x "${UV_BIN}" ] || command -v "${UV_BIN}" >/dev/null 2>&1; }; then
    return 0
  fi
  UV_BIN="uv"
  if ! command -v uv >/dev/null 2>&1; then
    if [ -f "${HOME}/.local/bin/env" ]; then
      # shellcheck source=/dev/null
      . "${HOME}/.local/bin/env"
    fi
  fi
  if ! command -v uv >/dev/null 2>&1; then
    UV_BIN="${HOME}/.local/bin/uv"
  fi
  if [ ! -x "${UV_BIN}" ] && ! command -v "${UV_BIN}" >/dev/null 2>&1; then
    log_err "uv is not available after installation."
    log_err "Restart the shell or add ~/.local/bin to PATH, then retry."
    exit 1
  fi
}

# Cursor / Claude Code / shared .mcp.json format: top-level mcpServers
write_mcp_servers_json() {
  local mcp_target="$1"
  local bin_path="$2"
  mkdir -p "$(dirname "$mcp_target")"
  python3 - "$mcp_target" "$bin_path" <<'PY'
import json, sys
from pathlib import Path

dst = Path(sys.argv[1])
bin_path = sys.argv[2]
server = {"type": "stdio", "command": bin_path, "args": []}
if dst.is_file():
    data = json.loads(dst.read_text(encoding="utf-8"))
else:
    data = {}
data.setdefault("mcpServers", {})["msprof-mcp"] = server
dst.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(dst)
PY
}

# OpenCode: merge into opencode.json — only mcp.<name> is recognized by opencode.
# See https://opencode.ai/docs/mcp-servers/ — fields: type:"local", command:[...], enabled.
write_opencode_json() {
  local mcp_target="$1"
  local bin_path="$2"
  mkdir -p "$(dirname "$mcp_target")"
  python3 - "$mcp_target" "$bin_path" <<'PY'
import json, sys
from pathlib import Path

dst = Path(sys.argv[1])
bin_path = sys.argv[2]
entry = {
    "type": "local",
    "command": [bin_path],
    "enabled": True,
}
if dst.is_file():
    data = json.loads(dst.read_text(encoding="utf-8"))
else:
    data = {"$schema": "https://opencode.ai/config.json"}
mcp = data.setdefault("mcp", {})
mcp["msprof-mcp"] = entry
dst.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(dst)
PY
}

write_mcp_for_tool() {
  local tool="$1"
  local bin_path="$2"
  local target=""

  case "$tool" in
    cursor)
      if [ "$LEVEL" = "global" ]; then
        target="${HOME}/.cursor/mcp.json"
      else
        target="${CONFIG_ROOT_BASE}/.cursor/mcp.json"
      fi
      write_mcp_servers_json "$target" "$bin_path"
      log_ok "Cursor MCP → $target"
      ;;
    claude)
      if [ "$LEVEL" = "global" ]; then
        # Claude Code user scope: ~/.claude.json (NOT ~/.claude/settings.json)
        target="${HOME}/.claude.json"
      else
        # Claude Code project scope: <project>/.mcp.json
        target="${CONFIG_ROOT_BASE}/.mcp.json"
      fi
      write_mcp_servers_json "$target" "$bin_path"
      log_ok "Claude Code MCP → $target"
      ;;
    opencode)
      if [ "$LEVEL" = "global" ]; then
        target="${HOME}/.config/opencode/opencode.json"
        write_opencode_json "$target" "$bin_path"
        log_ok "OpenCode MCP → $target"
      else
        target="${CONFIG_ROOT_BASE}/.opencode/opencode.json"
        write_opencode_json "$target" "$bin_path"
        log_ok "OpenCode MCP → $target"
      fi
      ;;
    *)
      log_err "Unsupported tool for MCP write: $tool"
      return 1
      ;;
  esac
}

echo ""
echo -e "${BOLD}ascend-tune-lab${NC}${DIM} · bootstrap msprof-mcp (msagent-style uv tool)${NC}"
echo -e "  Level:   ${DIM}${LEVEL}${NC}"
echo -e "  Tool:    ${DIM}${TOOL}${NC}"
echo -e "  Project: ${DIM}${PROJECT_ROOT}${NC}"
echo -e "  Config:  ${DIM}${CONFIG_ROOT}${NC}"
echo -e "  Pin:     ${DIM}${MSPROF_MCP_PIN}${NC}"
echo -e "  Python:  ${DIM}${MSPROF_MCP_PYTHON}${NC}"
if [ "${USE_CN_MIRROR}" = "1" ]; then
  echo -e "  PyPI:    ${DIM}${UV_DEFAULT_INDEX}${NC}"
  echo -e "  CPython: ${DIM}${UV_PYTHON_INSTALL_MIRROR}${NC}"
else
  echo -e "  Mirror:  ${DIM}disabled (USE_CN_MIRROR=0)${NC}"
fi
echo ""

if [ "${SKIP_UV_INSTALL}" != "1" ]; then
  if ! command -v uv >/dev/null 2>&1 && [ ! -x "${HOME}/.local/bin/uv" ]; then
    install_uv
  fi
  resolve_uv
  log_ok "uv → ${UV_BIN}"

  INSTALL_CMD=("${UV_BIN}" tool install -U --python "${MSPROF_MCP_PYTHON}")
  if [ -n "${UV_DEFAULT_INDEX:-}" ]; then
    INSTALL_CMD+=(--default-index "${UV_DEFAULT_INDEX}")
  fi
  if [ -n "${MSPROF_MCP_CONSTRAINTS:-}" ]; then
    _constraint_file="$(mktemp)"
    # shellcheck disable=SC2064
    trap 'rm -f "${_constraint_file:-}"' RETURN
    # shellcheck disable=SC2086
    printf '%s\n' ${MSPROF_MCP_CONSTRAINTS} > "${_constraint_file}"
    INSTALL_CMD+=(--constraints "${_constraint_file}")
  fi
  INSTALL_CMD+=("${MSPROF_MCP_PIN}")
  log_info "${INSTALL_CMD[*]}"
  log_info "constraints: ${MSPROF_MCP_CONSTRAINTS:-"(none)"}"
  "${INSTALL_CMD[@]}"
else
  if [ -f "${HOME}/.local/bin/env" ]; then
    # shellcheck source=/dev/null
    . "${HOME}/.local/bin/env" 2>/dev/null || true
  fi
  UV_BIN="${UV_BIN:-uv}"
  log_info "SKIP_UV_INSTALL=1 — reusing existing msprof-mcp"
fi

MSPROF_BIN=""
if [ -x "${TOOL_BIN_DIR}/msprof-mcp" ]; then
  MSPROF_BIN="${TOOL_BIN_DIR}/msprof-mcp"
elif command -v msprof-mcp >/dev/null 2>&1; then
  MSPROF_BIN="$(command -v msprof-mcp)"
fi

if [ -z "${MSPROF_BIN}" ]; then
  log_err "msprof-mcp not found under ${TOOL_BIN_DIR} or PATH."
  log_err "Try: source ~/.bashrc  (or ~/.zshrc) and re-run, or unset SKIP_UV_INSTALL."
  exit 1
fi

if command -v realpath >/dev/null 2>&1; then
  MSPROF_BIN="$(realpath "${MSPROF_BIN}")"
fi

log_ok "msprof-mcp binary → ${MSPROF_BIN}"

if command -v "${UV_BIN:-uv}" >/dev/null 2>&1 || [ -x "${UV_BIN:-}" ]; then
  if "${UV_BIN:-uv}" tool list 2>/dev/null | grep -qi 'msprof-mcp'; then
    log_ok "uv tool list contains msprof-mcp"
  else
    log_warn "uv tool list did not show msprof-mcp (binary still present)"
  fi
fi
if [ ! -x "${MSPROF_BIN}" ]; then
  log_err "msprof-mcp is not executable: ${MSPROF_BIN}"
  exit 1
fi
VER=""
if command -v "${UV_BIN:-uv}" >/dev/null 2>&1 || [ -x "${UV_BIN:-}" ]; then
  VER="$("${UV_BIN:-uv}" tool run --from msprof-mcp python -c 'from importlib.metadata import version; print(version("msprof-mcp"))' 2>/dev/null || true)"
fi
if [ -n "${VER}" ]; then
  log_ok "msprof-mcp import ok, version ${VER}"
else
  log_warn "import smoke skipped; binary exists at ${MSPROF_BIN}"
fi

if [ "${SKIP_MCP_JSON}" = "1" ]; then
  log_info "SKIP_MCP_JSON=1 — not writing MCP config"
else
  case "$TOOL" in
    all)
      for t in cursor claude opencode; do
        write_mcp_for_tool "$t" "$MSPROF_BIN"
      done
      ;;
    *)
      write_mcp_for_tool "$TOOL" "$MSPROF_BIN"
      ;;
  esac
fi

# Skill reference template (PATH-style), non-fatal
TEMPLATE="${SKILL_ROOT}/references/mcp.cursor.template.json"
if mkdir -p "$(dirname "$TEMPLATE")" 2>/dev/null; then
  cat > "${TEMPLATE}" <<EOF
{
  "mcpServers": {
    "msprof-mcp": {
      "type": "stdio",
      "command": "msprof-mcp",
      "args": []
    }
  }
}
EOF
  log_ok "Cursor template → ${TEMPLATE}"
fi

echo ""
log_ok "Bootstrap complete."
case "$TOOL" in
  cursor|all)
    echo -e "  ${CYAN}Cursor:${NC} Reload Window / Settings → MCP，确认 ${DIM}msprof-mcp${NC} 已连接"
    ;;
esac
case "$TOOL" in
  claude|all)
    echo -e "  ${CYAN}Claude Code:${NC} 重启 claude 或执行 ${DIM}claude mcp list${NC} 确认"
    ;;
esac
case "$TOOL" in
  opencode|all)
    echo -e "  ${CYAN}OpenCode:${NC} 重启 opencode，确认 MCP ${DIM}msprof-mcp${NC} 已加载"
    ;;
esac
echo -e "  ${DIM}command: ${MSPROF_BIN}${NC}"
echo ""
