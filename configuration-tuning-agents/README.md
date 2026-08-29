# Configuration Tuning Agents

vLLM-Ascend 服务化性能优化编排，架构 **Plugin → Agent → Skill**，目录命名与 [`configuration-tuning-skills/`](../configuration-tuning-skills/) 对称。

- **Primary**：[`AGENTS.md`](AGENTS.md) — `serving-perf-optimization`（快路径或路径 A/B）
- **Subagents**：[`agents/`](agents/) — 服务化 Phase 1 / Phase 2，独立 Profiling
- **工作流**：[`workflows/`](workflows/) — 短路由 `primary-workflow.md`（锁 path + 查表）
- **Skill 调用**：[`../configuration-tuning-skills/README.md`](../configuration-tuning-skills/README.md) — `standalone` / `dual` / `pipeline-only`；独立工具不走 A/B。最佳 PD 配比见 [`../PD-ratio-benchmark/SKILL.md`](../PD-ratio-benchmark/SKILL.md)
- **安装**：仓库根 [`quickstart.md`](../quickstart.md)；脚本 [`init.sh`](init.sh)（安装流程对齐 CANNBot `init.sh`）
- **派发设计**：[`docs/path-lock-dispatch-design.md`](docs/path-lock-dispatch-design.md) — 路径锁定、状态机派发、子代理上下文隔离

## 安装（推荐）

在**目标服务项目**根目录执行（或指定 `install_path`）：

```bash
cd /path/to/ascend-tune-lab/configuration-tuning-agents
bash init.sh project cursor
# 或安装到指定项目
bash init.sh project cursor /path/to/your/project
```

`init.sh` 会安装：

| 挂载项 | 目标位置（Cursor project 示例） |
| --- | --- |
| Primary | 安装目标 `AGENTS.md`（在插件目录执行时文件已在当前目录，跳过） |
| Subagents | `.cursor/agents/*.md` |
| Skills | `.cursor/skills/*` |
| Workflows | `.cursor/workflows/` |

安装后 primary 读取的工作流入口为：**`workflows/primary-workflow.md`**（先锁 path，再按表派发；路径详文只含门禁与 Phase 0）。Skill 分类见 [`../configuration-tuning-skills/README.md`](../configuration-tuning-skills/README.md)。

用户安装步骤见仓库根 [`quickstart.md`](../quickstart.md)。`init.sh` 对齐 CANNBot：skills 挂到 `.cursor/skills/`（不是 Marketplace，也不复制到 `~/.cursor/plugins/local`）。在插件目录执行 `bash init.sh project cursor` 时，`AGENTS.md` 已在当前目录则跳过。若 Cursor 打开的是仓库根，第三个参数传仓库路径。

Profiling MCP 接入见 skill：`configuration-tuning-skills/msprof-mcp-setup/`（`pipeline-only`；bootstrap 脚本不绑在 init 默认路径）。

支持 `level`：`project`（默认）、`global`；支持 `tool`：`opencode`、`claude`、`trae`、`cursor`、`copilot`、`codearts`。详见 `./init.sh --help`。

## 手动使用（不运行 init）

1. 将 `AGENTS.md` 复制或链接到项目编排入口。
2. 将 `workflows/` 链接到项目根 `workflows/`，保证 AGENTS 内相对路径可解析。
3. **服务化**：准备 MD 配置（默认 `{workdir}/deploy-config.md`），走 Phase 0→1→2。  
   **Profiling（独立）**：明确要做分析 **且** 提供本地 `*_ascend_pt` / `PROF_*` 路径；**不会**在服务化调优路径内自动触发。  
   **独立 Skill**：只要白名单工具（如算 MFU、比对环境 dump、最佳 PD 配比）且未提 A/B 时，不进流水线；PD 配比见 [`../PD-ratio-benchmark/SKILL.md`](../PD-ratio-benchmark/SKILL.md)。约定见 [`../configuration-tuning-skills/README.md`](../configuration-tuning-skills/README.md)。

## 目录结构

```
configuration-tuning-agents/
├── init.sh
├── AGENTS.md
├── README.md
├── agents/
│   └── serving-*.md
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
| 快路径（非流水线） | （不派发） | 白名单：`op-mfu-calculator`、`ascend-dump-analyzer`、`cluster-analysis`、`vllm-ascend-tuning` 等 | 已实现；无 A/B / PD 意图时由 Primary 直接执行 |
| 服务化 · 1 基线 | `serving-baseline-reproduce-subagent` | `ascend-baseline-generator` | 已实现 |
| 服务化 · 2 调优 | `serving-tuning-subagent` | `serving-parallel-strategy-tuning`（入口） | 已实现（离线） |
| 服务化 · 2 子步骤 | （由入口编排） | `find-possible-parallel-strategy` 等 | 已实现 |
| **Profiling（独立）** | `serving-profiling-analysis-subagent` | Profiler 套件 + `msprof-mcp-setup` | 已实现；不在服务化路径内触发 |
| **最佳 PD 配比** | （不派发） | 独立 skill `PD-ratio-benchmark` | 与快路径相同，不走 A/B |

Profiling skills（与 msagent `Profiler.yml` 一致，另加本仓接入 skill）：

- `msprof-mcp-setup`（pipeline-only；路径 B 内 `invoke=pipeline`）
- `ascend-profiler-data-validation` / `ascend-profiler-db-explorer`（pipeline-only）
- `ascend-computation-analysis` / `ascend-communication-analysis` / `ascend-schedule-analysis`（pipeline-only）
- `ascend-msprof-analyze-cli` / `compare-analyzer` / `ascend-cluster-fast-slow-rank-detector`（pipeline-only）
- `op-mfu-calculator`（dual；路径 B 内 `invoke=pipeline`）
- `github-raw-fetch`（pipeline-only；路径 B 内 `invoke=pipeline`）
