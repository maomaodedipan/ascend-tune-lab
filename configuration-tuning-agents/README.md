# Configuration Tuning Agents

vLLM-Ascend 服务化性能优化编排，架构 **Plugin → Agent → Skill**，目录命名与 [`configuration-tuning-skills/`](../configuration-tuning-skills/) 对称。

- **Primary**：[`AGENTS.md`](AGENTS.md) — `serving-perf-optimization`
- **Subagents**：[`agents/`](agents/) — Phase 1 / Phase 2 / 按需 Profiling（对齐 msagent Profiler）
- **工作流**：[`workflows/`](workflows/) — 编排步骤与派发模板
- **安装**：[`init.sh`](init.sh) — 挂载 skills / agents / **workflows** 到目标项目

## 安装（推荐）

在**目标服务项目**根目录执行（或指定 `install_path`）：

```bash
/path/to/ascend-tune-lab/configuration-tuning-agents/init.sh project cursor
# 或
/path/to/ascend-tune-lab/configuration-tuning-agents/init.sh project cursor /path/to/your/project
```

`init.sh` 会安装：

| 挂载项 | 目标位置（Cursor project 示例） |
| --- | --- |
| Primary | `./AGENTS.md`、`.cursor/AGENTS.md` |
| Subagents | `.cursor/agents/*.md` |
| Skills | `.cursor/ascend-tune-lab/skills/*` |
| **Workflows** | `.cursor/workflows/` **与** `./workflows/`（符号链接到本插件 `workflows/`） |
| 仓库路径 | `./configuration-tuning-skills/`、`./configuration-tuning-agents/` |

安装后 primary 读取的工作流入口为：**`workflows/serving-perf-optimization-workflow.md`**。

Profiling MCP 接入见 skill：`configuration-tuning-skills/msprof-mcp-setup/`（独立 bootstrap，不绑在 init 默认路径）。

支持 `level`：`project`（默认）、`global`；支持 `tool`：`opencode`、`claude`、`trae`、`cursor`、`copilot`、`codearts`。详见 `./init.sh --help`。

## 手动使用（不运行 init）

1. 将 `AGENTS.md` 复制或链接到项目编排入口。
2. 将 `workflows/` 链接到项目根 `workflows/`，保证 AGENTS 内相对路径可解析。
3. 服务化：准备 MD 配置（默认 `{workdir}/deploy-config.md`）。Profiling：直接提供 `*_ascend_pt` 路径。

## 目录结构

```
configuration-tuning-agents/
├── init.sh
├── AGENTS.md
├── README.md
├── agents/
│   ├── serving-baseline-reproduce-subagent.md
│   ├── serving-tuning-subagent.md
│   └── serving-profiling-analysis-subagent.md   # 按需 · msagent Profiler
└── workflows/
    ├── serving-perf-optimization-workflow.md
    ├── templates/
    └── references/
        ├── user-config-format.md
        ├── subagent-prompt-templates.md
        ├── profiling-analysis.md
        └── msprof-mcp-tools.md
```

## 与 Skills 的对应关系

| Phase / 场景 | Subagent | Skill | 当前 |
| --- | --- | --- | --- |
| 1 基线配置生成 | `serving-baseline-reproduce-subagent` | `ascend-baseline-generator` | 已实现 |
| 2 并行策略调优 | `serving-tuning-subagent` | `serving-parallel-strategy-tuning`（入口） | 已实现（离线） |
| 2 子步骤 | （由入口编排） | `find-possible-parallel-strategy` 等 | 已实现 |
| **按需 Profiling** | `serving-profiling-analysis-subagent` | Profiler 套件 + `msprof-mcp-setup` | 已实现 |

Profiling skills（与 msagent `Profiler.yml` 一致，另加本仓接入 skill）：

- `msprof-mcp-setup`
- `ascend-profiler-data-validation` / `ascend-profiler-db-explorer`
- `ascend-computation-analysis` / `ascend-communication-analysis` / `ascend-schedule-analysis`
- `ascend-msprof-analyze-cli` / `ascend-cluster-fast-slow-rank-detector`
- `op-mfu-calculator` / `github-raw-fetch`
