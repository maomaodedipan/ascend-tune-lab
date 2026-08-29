#!/usr/bin/env bash
# ascend-tune-lab plugin installer.
# Install flow follows cannbot-skills:
#   plugins-official/triton-op-generator/init.sh
#   plugins-official/model-infer-optimize/init.sh (agents / workflows)
# ----------------------------------------------------------------------------------------------------------

set -e

# --- Color & output helpers ---
if [ -t 1 ]; then
  GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'
  CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; RED=''; CYAN=''; BOLD=''; DIM=''; NC=''
fi

ok()   { echo -e "  ${DIM}${GREEN}✓${NC}${DIM} $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠${NC}${DIM} $*${NC}"; }
err()  { echo -e "  ${RED}✗${NC}${DIM} $*${NC}"; }
info() { echo -e "  ${DIM}${CYAN}→${NC}${DIM} $*${NC}"; }
step() { echo -e "${DIM}$*${NC}"; }

BRAND="ascend-tune-lab"
VERSION="0.1.0"
SOURCE_AGENT_FILE="AGENTS.md"

# Skill whitelist (space-separated) — all skills bundled with this plugin
INCLUDED_SKILLS="ascend-baseline-generator serving-cfg-extract serving-perf-metrics vllm-ascend-config-extractor model-feature-extractor serving-parallel-strategy-tuning find-possible-parallel-strategy serving-kv-cache-capacity serving-slo-concurrency msprof-mcp-setup ascend-profiler-db-explorer ascend-profiler-data-validation ascend-computation-analysis ascend-communication-analysis ascend-schedule-analysis ascend-msprof-analyze-cli ascend-cluster-fast-slow-rank-detector op-mfu-calculator github-raw-fetch pd-config-env-check pd-deploy aisbench-install pd-ratio-measure compare-analyzer ascend-dump-analyzer cluster-analysis vllm-ascend-tuning"
INCLUDED_AGENT_PATTERN="serving-*"

# Detect TRAE variant by scanning global config directories.
# Sets global: TRAE_VARIANT=(ide|plugin|cli|unknown)
detect_trae_variant() {
    if [ -d "$HOME/.trae" ]; then
        TRAE_VARIANT="ide"
    elif [ -d "$HOME/.marscode" ]; then
        TRAE_VARIANT="plugin"
    elif [ -d "$HOME/.traecli" ]; then
        TRAE_VARIANT="cli"
    else
        TRAE_VARIANT="unknown"
    fi
}

show_banner() {
  echo ""
  echo -e "${CYAN}${BOLD}ascend-tune-lab${NC}"
  echo -e "  ${BOLD}vLLM-Ascend 服务化性能优化${NC}"
  echo ""
}

show_help() {
    cat << EOF
ascend-tune-lab - Plugin Installer

Usage: init.sh [level] [tool] [install_path]

Arguments:
  level        - Installation level: "project" (default) or "global"
  tool         - Target tool: "opencode" (default), "claude", "trae", "cursor", "copilot", or "codearts"
  install_path - Project-level installation directory (default: current working directory)

Options:
  --help  - Show this help message

Examples:
  init.sh                              # Project-level, OpenCode
  init.sh project opencode             # Project-level, OpenCode
  init.sh global  opencode             # Global-level, OpenCode
  init.sh project claude               # Project-level, Claude Code
  init.sh global  claude               # Global-level, Claude Code
  init.sh project trae                 # Project-level, Trae
  init.sh project cursor               # Project-level, Cursor
  init.sh project copilot              # Project-level, Copilot
  init.sh global  copilot              # Global-level, Copilot
  init.sh project codearts             # Project-level, CodeArts
  init.sh project claude /path/to/proj # Project-level, Claude Code, custom path

Installation paths:
  OpenCode: .opencode/skills/ + AGENTS.md  (auto-discovered)
  Claude:   .claude/skills/ + CLAUDE.md    (per-item symlinks auto-created)
  Trae:     .trae/skills/ + AGENTS.md      (project-level only)
  Cursor:   .cursor/skills/ + AGENTS.md    (auto-discovered)
  Copilot:  .github/skills/ + AGENTS.md    (project-level)
            ~/.copilot/skills/ + AGENTS.md (global)
  CodeArts: .codeartsdoer/skills/ + AGENTS.md    (project-level)
            ~/.codeartsdoer/skills/ + AGENTS.md   (global)

After installation, launch directly:
  OpenCode: opencode
  Claude:   claude
  Trae:     通过 CLI 或 IDE 启动
  Cursor:   通过 Cursor IDE 启动
  Copilot:  通过 GitHub Copilot CLI / IDE 启动
  CodeArts: 通过 CodeArts CLI / IDE 启动
EOF
}

LEVEL="project"
TOOL="opencode"
INSTALL_PATH=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$SCRIPT_DIR"
LOCAL_AGENT_ROOT="$PLUGIN_ROOT/agents"

# Sibling skills directory (source tree).
if [ -d "$PLUGIN_ROOT/../configuration-tuning-skills" ]; then
    LOCAL_SKILL_ROOT="$(cd "$PLUGIN_ROOT/../configuration-tuning-skills" && pwd)"
else
    LOCAL_SKILL_ROOT=""
fi

if [ -z "$LOCAL_SKILL_ROOT" ] || [ ! -d "$LOCAL_SKILL_ROOT" ]; then
    err "Cannot find configuration-tuning-skills/. Please run init.sh from the source tree."
    exit 1
fi

for arg in "$@"; do
    case "$arg" in
        --help)                 show_help; exit 0 ;;
        global|project)         LEVEL="$arg" ;;
        opencode|claude|trae|cursor|copilot|codearts) TOOL="$arg" ;;
        *)
            if [ -n "$INSTALL_PATH" ]; then
                echo "Error: Unexpected argument '$arg'. Valid: global, project, opencode, claude, trae, cursor, copilot, codearts, [install_path], --help."
                exit 1
            fi
            INSTALL_PATH="$arg"
            ;;
    esac
done

# Resolve project-level install base (default: current dir; override via install_path arg).
# Global level installs under $HOME and ignores install_path.
if [ -n "$INSTALL_PATH" ]; then
    if [ ! -d "$INSTALL_PATH" ]; then
        echo "Error: install_path '$INSTALL_PATH' is not an existing directory."
        exit 1
    fi
    INSTALL_BASE="$(cd "$INSTALL_PATH" && pwd)"
else
    INSTALL_BASE="$PWD"
fi

# Determine config root directory and target md filename
if [ "$LEVEL" = "global" ]; then
    if [ "$TOOL" = "opencode" ]; then
        CONFIG_ROOT="$HOME/.config/opencode"
    elif [ "$TOOL" = "trae" ]; then
        echo "Error: Global installation is not supported for Trae. Use project-level instead."
        exit 1
    elif [ "$TOOL" = "copilot" ]; then
        CONFIG_ROOT="$HOME/.copilot"
    elif [ "$TOOL" = "cursor" ]; then
        CONFIG_ROOT="$HOME/.cursor"
    elif [ "$TOOL" = "codearts" ]; then
        CONFIG_ROOT="$HOME/.codeartsdoer"
    else
        CONFIG_ROOT="$HOME/.claude"
    fi
else
    if [ "$TOOL" = "opencode" ]; then
        CONFIG_ROOT="$INSTALL_BASE/.opencode"
    elif [ "$TOOL" = "trae" ]; then
        detect_trae_variant
        case "$TRAE_VARIANT" in
            plugin) CONFIG_ROOT="$INSTALL_BASE/.marscode" ;;
            cli)    CONFIG_ROOT="$INSTALL_BASE/.traecli" ;;
            *)      CONFIG_ROOT="$INSTALL_BASE/.trae" ;;
        esac
    elif [ "$TOOL" = "copilot" ]; then
        CONFIG_ROOT="$INSTALL_BASE/.github"
    elif [ "$TOOL" = "cursor" ]; then
        CONFIG_ROOT="$INSTALL_BASE/.cursor"
    elif [ "$TOOL" = "codearts" ]; then
        CONFIG_ROOT="$INSTALL_BASE/.codeartsdoer"
    else
        CONFIG_ROOT="$INSTALL_BASE/.claude"
    fi
fi

if [ "$TOOL" = "opencode" ] || [ "$TOOL" = "trae" ] || [ "$TOOL" = "cursor" ] || [ "$TOOL" = "copilot" ] || [ "$TOOL" = "codearts" ]; then
    TARGET_MD_NAME="AGENTS.md"
else
    TARGET_MD_NAME="CLAUDE.md"
fi

BRAND_DIR="$CONFIG_ROOT"

show_banner
echo "  Tool:      $TOOL"
echo "  Level:     $LEVEL"
echo "  Path:      $CONFIG_ROOT"
echo "  MD File:   $TARGET_MD_NAME"
echo ""

if [ "$TOOL" = "trae" ]; then
    case "$TRAE_VARIANT" in
        ide)
            info "Detected: TRAE IDE (.trae)"
            ;;
        plugin)
            info "Detected: TRAE Plugin (.marscode)"
            ;;
        cli)
            info "Detected: TRAE CLI (.traecli)"
            ;;
        unknown)
            warn "TRAE variant not detected; defaulting to IDE path"
            warn "If you use TRAE Plugin, ensure ~/.marscode exists before re-running"
            warn "If you use TRAE CLI, ensure ~/.traecli exists before re-running"
            ;;
    esac
    echo ""
fi

# --- Step 0: Confirmation before installation ---
step "[0/4] Checking items to be installed..."

SKILLS_TO_INSTALL=""
SKILL_COUNT=0
for skill_entry in "$LOCAL_SKILL_ROOT"/*; do
    [ -e "$skill_entry" ] || continue
    name=$(basename "$skill_entry")
    echo "$INCLUDED_SKILLS" | grep -qw "$name" || continue
    SKILLS_TO_INSTALL="$SKILLS_TO_INSTALL $name"
    SKILL_COUNT=$((SKILL_COUNT + 1))
done

SOURCE_AGENT_PATH="$PLUGIN_ROOT/$SOURCE_AGENT_FILE"
AGENT_FILE_EXISTS=false
if [ -f "$SOURCE_AGENT_PATH" ]; then
    AGENT_FILE_EXISTS=true
fi

echo ""
echo -e "${BOLD}以下内容将被安装/替换：${NC}"
echo ""

if [ "$SKILL_COUNT" -gt 0 ]; then
    echo -e "${CYAN}Skills (${SKILL_COUNT} 项)：${NC}"
    for name in $SKILLS_TO_INSTALL; do
        target="$BRAND_DIR/skills/$name"
        if [ -e "$target" ] || [ -L "$target" ]; then
            echo -e "  ${YELLOW}$name${NC}"
        else
            echo -e "  ${GREEN}$name${NC}"
        fi
    done
    echo ""
fi

if [ "$AGENT_FILE_EXISTS" = true ]; then
    echo -e "${CYAN}${TARGET_MD_NAME} (1 项)：${NC}"
    target="$BRAND_DIR/$TARGET_MD_NAME"
    if [ -e "$target" ] || [ -L "$target" ]; then
        echo -e "  ${YELLOW}${TARGET_MD_NAME}${NC}"
    else
        echo -e "  ${GREEN}${TARGET_MD_NAME}${NC}"
    fi
    echo ""
fi

echo -e "${BOLD}${YELLOW}注意：仅替换上述白名单内的内容，不影响其他已存在的 skills${NC}"
echo ""
ok "开始安装..."
echo ""

# --- Step 1: Create directory + per-item symlinks ---
step "[1/4] Setting up plugin directory..."
mkdir -p "$BRAND_DIR/skills"

for skill_entry in "$LOCAL_SKILL_ROOT"/*; do
    [ -e "$skill_entry" ] || continue
    name=$(basename "$skill_entry")
    echo "$INCLUDED_SKILLS" | grep -qw "$name" || continue
    target="$BRAND_DIR/skills/$name"
    if [ -e "$target" ] || [ -L "$target" ]; then
        rm -rf "$target"
    fi
done

skill_link_count=0
for skill_entry in "$LOCAL_SKILL_ROOT"/*; do
    [ -e "$skill_entry" ] || continue
    name=$(basename "$skill_entry")
    echo "$INCLUDED_SKILLS" | grep -qw "$name" || continue
    ln -sfn "$(realpath "$skill_entry")" "$BRAND_DIR/skills/$name"
    skill_link_count=$((skill_link_count + 1))
done
ok "Skills: $skill_link_count linked"

REPO_ROOT="$(cd "$PLUGIN_ROOT/.." && pwd)"
MAIN_PD="$REPO_ROOT/PD-ratio-benchmark"
if [ -f "$MAIN_PD/SKILL.md" ]; then
    rm -rf "$BRAND_DIR/skills/PD-ratio-benchmark"
    ln -sfn "$(realpath "$MAIN_PD")" "$BRAND_DIR/skills/PD-ratio-benchmark"
    ok "Main skill: PD-ratio-benchmark linked"
fi

for link in "$BRAND_DIR/skills"/*; do
    [ -L "$link" ] && [ ! -e "$link" ] && rm "$link"
done

# Agents (model-infer-optimize)
if [ -d "$LOCAL_AGENT_ROOT" ]; then
    mkdir -p "$BRAND_DIR/agents"
    agent_link_count=0
    for agent_entry in "$LOCAL_AGENT_ROOT"/*; do
        [ -e "$agent_entry" ] || continue
        name=$(basename "$agent_entry")
        base="${name%.md}"
        case "$base" in
            serving-pd-*|serving-aisbench-install-subagent) continue ;;
            $INCLUDED_AGENT_PATTERN) ;;
            *) continue ;;
        esac
        rm -f "$BRAND_DIR/agents/$name"
        ln -sfn "$(realpath "$agent_entry")" "$BRAND_DIR/agents/$name"
        agent_link_count=$((agent_link_count + 1))
    done
    ok "Agents: $agent_link_count linked"
fi

# Workflows (model-infer-optimize)
if [ -d "$PLUGIN_ROOT/workflows" ]; then
    mkdir -p "$BRAND_DIR"
    ln -sfn "$(realpath "$PLUGIN_ROOT/workflows")" "$BRAND_DIR/workflows"
    ok "workflows"
fi
echo ""

# --- Step 2: Install config file (AGENTS.md / CLAUDE.md) ---
step "[2/4] Installing configuration..."

if [ "$LEVEL" = "project" ]; then
    if [ "$TOOL" = "opencode" ] || [ "$TOOL" = "cursor" ] || [ "$TOOL" = "copilot" ] || [ "$TOOL" = "codearts" ]; then
        config_target="$INSTALL_BASE/AGENTS.md"
    else
        config_target="$INSTALL_BASE/CLAUDE.md"
    fi
else
    if [ "$TOOL" = "opencode" ] || [ "$TOOL" = "cursor" ] || [ "$TOOL" = "copilot" ] || [ "$TOOL" = "codearts" ]; then
        config_target="$CONFIG_ROOT/AGENTS.md"
    else
        config_target="$CONFIG_ROOT/CLAUDE.md"
    fi
fi

config_src="$PLUGIN_ROOT/AGENTS.md"

# Skip only when source file is already at target location
# (PLUGIN_ROOT = INSTALL_BASE, e.g. cd configuration-tuning-agents && bash init.sh project cursor)
if { [ "$TOOL" = "opencode" ] || [ "$TOOL" = "cursor" ] || [ "$TOOL" = "copilot" ] || [ "$TOOL" = "codearts" ]; } && [ "$LEVEL" = "project" ] && [ "$PLUGIN_ROOT" = "$INSTALL_BASE" ]; then
    ok "$(basename "$config_target") already in current directory"
else
    if [ "$LEVEL" = "global" ]; then
        [ -e "$config_target" ] || [ -L "$config_target" ] && rm -f "$config_target"
        PLUGIN_ROOT_ABS="$(realpath "$PLUGIN_ROOT")"
        ESCAPED_ROOT="$(echo "$PLUGIN_ROOT_ABS" | sed 's/#/\\#/g')"
        sed \
          -e "s#\`workflows/#\`${ESCAPED_ROOT}/workflows/#g" \
          "$config_src" > "$config_target"
        ok "$(basename "$config_target") (absolute paths for global mode)"
    else
        ln -sf "$config_src" "$config_target"
        ok "$(basename "$config_target")"
    fi
fi
echo ""

# --- Step 3: Health check + manifest ---
step "[3/4] Running health check..."
health_ok=true
health_errors=""

for sub in skills; do
  target="$BRAND_DIR/$sub"
  if [ -d "$target" ]; then
    count=$(ls -d "$target"/* 2>/dev/null | wc -l)
    [ "$count" -eq 0 ] && { health_errors="${health_errors}\n  ${YELLOW}⚠${NC} $sub/ is empty"; }
  else
    health_errors="${health_errors}\n  ${RED}✗${NC} $sub/ missing"
    health_ok=false
  fi
done

if [ "$LEVEL" = "project" ]; then
    if [ "$TOOL" = "opencode" ] || [ "$TOOL" = "cursor" ] || [ "$TOOL" = "copilot" ] || [ "$TOOL" = "codearts" ]; then
        [ -f "$INSTALL_BASE/AGENTS.md" ] || { health_errors="${health_errors}\n  ${RED}✗${NC} AGENTS.md missing in project directory"; health_ok=false; }
    else
        [ -f "$INSTALL_BASE/CLAUDE.md" ] || { health_errors="${health_errors}\n  ${RED}✗${NC} CLAUDE.md missing in project directory"; health_ok=false; }
    fi
else
    if [ "$TOOL" = "opencode" ] || [ "$TOOL" = "cursor" ] || [ "$TOOL" = "copilot" ] || [ "$TOOL" = "codearts" ]; then
        [ -f "$CONFIG_ROOT/AGENTS.md" ] || { health_errors="${health_errors}\n  ${RED}✗${NC} AGENTS.md missing"; health_ok=false; }
    else
        [ -f "$CONFIG_ROOT/CLAUDE.md" ] || { health_errors="${health_errors}\n  ${RED}✗${NC} CLAUDE.md missing"; health_ok=false; }
    fi
fi

MANIFEST="$CONFIG_ROOT/cannbot-manifest.json"

SKILLS_JSON="[]"
if [ -d "$BRAND_DIR/skills" ]; then
  SKILLS_JSON=$(ls -d "$BRAND_DIR/skills"/* 2>/dev/null | while read d; do
    echo "${d##*/}"
  done | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))" 2>/dev/null || echo "[]")
fi

AGENTS_JSON="[]"
if [ -d "$LOCAL_AGENT_ROOT" ]; then
  AGENTS_JSON=$(find "$LOCAL_AGENT_ROOT" -maxdepth 1 -name 'serving-*.md' -printf '%f\n' 2>/dev/null | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))" 2>/dev/null || echo "[]")
fi

cat > "$MANIFEST" << MANIFEST_EOF
{
  "brand": "$BRAND",
  "version": "$VERSION",
  "team": "$BRAND",
  "level": "$LEVEL",
  "tool": "$TOOL",
  "installed_skills": $SKILLS_JSON,
  "installed_agents": $AGENTS_JSON,
  "installed_md_file": "$TARGET_MD_NAME",
  "brand_dir": "$CONFIG_ROOT",
  "install_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
MANIFEST_EOF

[ -f "$MANIFEST" ] || { health_errors="${health_errors}\n  ${RED}✗${NC} Manifest generation failed"; health_ok=false; }

if [ "$health_ok" = true ] && [ -z "$health_errors" ]; then
  ok "All checks passed"
else
  echo -e "$health_errors"
  [ "$health_ok" = true ] && warn "Some warnings, see above" || err "Some checks failed, see above"
fi
echo ""

# --- Step 4: Summary & Quick Start ---
step "[4/4] Done."
echo ""
echo -e "  ${GREEN}${BOLD}✓ ascend-tune-lab installed successfully!${NC}"
echo ""
echo -e "  ${BOLD}Quick Start:${NC}"
if [ "$TOOL" = "opencode" ]; then
  echo -e "  ${CYAN}1.${NC} 启动 CLI: ${GREEN}opencode${NC}"
  echo -e "  ${CYAN}2.${NC} 直接输入需求: ${GREEN}${BOLD}帮我做服务化调优${NC}"
elif [ "$TOOL" = "trae" ]; then
  echo -e "  ${CYAN}1.${NC} 通过 CLI/IDE 启动${NC}"
  echo -e "  ${CYAN}2.${NC} 直接输入需求: ${GREEN}${BOLD}帮我做服务化调优${NC}"
elif [ "$TOOL" = "copilot" ]; then
  echo -e "  ${CYAN}1.${NC} 通过 GitHub Copilot CLI / IDE 启动${NC}"
  echo -e "  ${CYAN}2.${NC} 直接输入需求: ${GREEN}${BOLD}帮我做服务化调优${NC}"
elif [ "$TOOL" = "cursor" ]; then
  echo -e "  ${CYAN}1.${NC} 通过 Cursor IDE 启动${NC}"
  echo -e "  ${CYAN}2.${NC} 直接输入需求: ${GREEN}${BOLD}帮我做服务化调优${NC}"
elif [ "$TOOL" = "codearts" ]; then
  echo -e "  ${CYAN}1.${NC} 通过 CodeArts CLI / IDE 启动${NC}"
  echo -e "  ${CYAN}2.${NC} 直接输入需求: ${GREEN}${BOLD}帮我做服务化调优${NC}"
else
  echo -e "  ${CYAN}1.${NC} 启动 CLI: ${GREEN}claude${NC}"
  echo -e "  ${CYAN}2.${NC} 直接输入需求: ${GREEN}${BOLD}帮我做服务化调优${NC}"
fi
echo ""
echo -e "  ${DIM}Note: 所有执行阶段将在当前会话中实时显示${NC}"
echo ""
