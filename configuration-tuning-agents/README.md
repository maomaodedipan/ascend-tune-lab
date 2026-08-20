# Configuration Tuning Agents

vLLM-Ascend 服务化性能优化编排，架构 **Plugin → Agent → Skill**，目录命名与 [`configuration-tuning-skills/`](../configuration-tuning-skills/) 对称。

- **Primary**：[`AGENTS.md`](AGENTS.md) — `serving-perf-optimization`（快路径或三路径路由）
- **Subagents**：[`agents/`](agents/) — 服务化 Phase 1 / Phase 2，独立 Profiling，以及 **路径 C · PD 配比** 四阶段
- **工作流**：[`workflows/`](workflows/) — 顶层 `primary-workflow.md` + 平级路径（服务化调优 / Profiling / PD 配比）
- **Skill 调用**：[`../configuration-tuning-skills/README.md`](../configuration-tuning-skills/README.md) — `standalone` / `dual` / `pipeline-only`；独立工具不走 A/B/C
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

安装后 primary 读取的工作流入口为：**`workflows/primary-workflow.md`**（先判定独立 skill 快路径，再进入平级路径详文）。Skill 分类见 [`../configuration-tuning-skills/README.md`](../configuration-tuning-skills/README.md)。

Profiling MCP 接入见 skill：`configuration-tuning-skills/msprof-mcp-setup/`（`pipeline-only`；bootstrap 脚本不绑在 init 默认路径）。

支持 `level`：`project`（默认）、`global`；支持 `tool`：`opencode`、`claude`、`trae`、`cursor`、`copilot`、`codearts`。详见 `./init.sh --help`。

## 手动使用（不运行 init）

1. 将 `AGENTS.md` 复制或链接到项目编排入口。
2. 将 `workflows/` 链接到项目根 `workflows/`，保证 AGENTS 内相对路径可解析。
3. **服务化**：准备 MD 配置（默认 `{workdir}/deploy-config.md`），走 Phase 0→1→2。  
   **Profiling（独立）**：明确要做分析 **且** 提供本地 `*_ascend_pt` / `PROF_*` 路径；**不会**在服务化调优路径内自动触发。  
   **PD 配比（路径 C）**：明确要算最佳 PD 配比；准备 `{workdir}/pd-deploy-config.md`；未指定容器时 Agent 按一机一容器拉起。  
   **独立 Skill**：只要白名单工具（如算 MFU、比对环境 dump）且未提 A/B/C 时，不进流水线；约定见 [`../configuration-tuning-skills/README.md`](../configuration-tuning-skills/README.md)。

## 目录结构

```
configuration-tuning-agents/
├── init.sh
├── AGENTS.md
├── README.md
├── agents/
│   ├── serving-baseline-reproduce-subagent.md
│   ├── serving-tuning-subagent.md
│   ├── serving-profiling-analysis-subagent.md
│   ├── serving-pd-config-check-subagent.md
│   ├── serving-pd-deploy-subagent.md
│   ├── serving-aisbench-install-subagent.md
│   └── serving-pd-ratio-benchmark-subagent.md
└── workflows/
    ├── primary-workflow.md
    ├── serving-tuning-workflow.md
    ├── profiling-analysis-workflow.md
    ├── pd-ratio-workflow.md
    ├── templates/
    └── references/
```

## 与 Skills 的对应关系

Skill 分为 `standalone` / `dual` / `pipeline-only`，完整表见 [`../configuration-tuning-skills/README.md`](../configuration-tuning-skills/README.md)。下表只列流水线编排。

| Phase / 场景 | Subagent | Skill | 当前 |
| --- | --- | --- | --- |
| 快路径（非流水线） | （不派发） | 白名单：`op-mfu-calculator`、`ascend-dump-analyzer`、`cluster-analysis`、`vllm-ascend-tuning` 等 | 已实现；无 A/B/C 意图时由 Primary 直接执行 |
| 服务化 · 1 基线 | `serving-baseline-reproduce-subagent` | `ascend-baseline-generator` | 已实现 |
| 服务化 · 2 调优 | `serving-tuning-subagent` | `serving-parallel-strategy-tuning`（入口） | 已实现（离线） |
| 服务化 · 2 子步骤 | （由入口编排） | `find-possible-parallel-strategy` 等 | 已实现 |
| **Profiling（独立）** | `serving-profiling-analysis-subagent` | Profiler 套件 + `msprof-mcp-setup` | 已实现；不在服务化路径内触发 |
| **PD 配比 · 1** | `serving-pd-config-check-subagent` | `pd-config-env-check` | 已实现 |
| **PD 配比 · 2** | `serving-aisbench-install-subagent` | `aisbench-install` | 已实现（部署前） |
| **PD 配比 · 3** | `serving-pd-deploy-subagent` | `pd-deploy` | 已实现 |
| **PD 配比 · 4** | `serving-pd-ratio-benchmark-subagent` | `pd-ratio-benchmark` | 已实现 |

Profiling skills（与 msagent `Profiler.yml` 一致，另加本仓接入 skill）：

- `msprof-mcp-setup`（pipeline-only；路径 B 内 `invoke=pipeline`）
- `ascend-profiler-data-validation` / `ascend-profiler-db-explorer`（pipeline-only）
- `ascend-computation-analysis` / `ascend-communication-analysis` / `ascend-schedule-analysis`（pipeline-only）
- `ascend-msprof-analyze-cli` / `compare-analyzer` / `ascend-cluster-fast-slow-rank-detector`（pipeline-only）
- `op-mfu-calculator`（dual；路径 B 内 `invoke=pipeline`）
- `github-raw-fetch`（pipeline-only；路径 B 内 `invoke=pipeline`）
