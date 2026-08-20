# 路径 B · Profiling 分析工作流

由 primary 在选定 **路径 B（Profiling 分析）** 后强制 Read 并推进。  
顶层路由见 [`primary-workflow.md`](primary-workflow.md)。对齐 msagent Profiler。

**与路径 A 平级、互斥**：不进入服务化 Phase 0–2，不要求 `deploy-config.md`。进入本路径后禁止改走独立 skill 快路径（分析套件保持 `pipeline-only`；dual skill 一律 `invoke=pipeline`）。

## 触发（进入本路径前已由 primary 确认）

须 **同时** 满足：

1. 用户明确要做 profiling / profiler / msprof 数据分析；
2. 用户提供了本地 `profiler_path`（`*_ascend_pt` / `*_ascend_ms` / `PROF_*` 或其可唯一定位的父目录）。

缺路径 → 只索取并停止；缺分析意图 → 不进入本路径。

## 流程总览

```text
+--------------------------------------------------------------+
| Step 0 · msprof-mcp 就绪（首次安装硬门禁）                      |
|    GetMcpTools → 未 ready 则 msprof-mcp-setup → Reload       |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Step 1 · 派发 serving-profiling-analysis-subagent            |
|    数据校验 → 单卡/多卡分析 → 交叉验证                         |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Step 2 · 验收                                                |
|    {workdir}/profiling/profiling-report.md                   |
+--------------------------------------------------------------+
```

## Subagent 映射

| 步骤 | Subagent | 状态 |
| --- | --- | --- |
| 分析 | `serving-profiling-analysis-subagent` | **已实现** |

派发模板见 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)「Profiling 分析」。

## 首次安装硬门禁（必须）

**每次进入分析前**确认 msprof-mcp 已就绪：

1. `GetMcpTools` / Settings → MCP 检查 `msprof-mcp` 或 `user-msprof-mcp` 是否 ready  
2. **未就绪（含首次使用）** → **必须**执行 `configuration-tuning-skills/msprof-mcp-setup/SKILL.md`  
   - Linux/macOS/WSL：`scripts/bootstrap-msprof-mcp.sh project cursor`（或 claude/opencode）  
   - Windows 原生：按技能第 6 节 pip（含 `mcp<2`、`pandas<3`）  
3. 安装后用户 **Reload Window / 重启 IDE**，再次确认 ready  
4. **禁止**跳过 setup 直接分析；禁止未 setup 时静默用本地读文件冒充 MCP 分析

## 前置依赖

| 依赖 | 用途 | 安装 |
| --- | --- | --- |
| `msprof-mcp==0.1.8` | MCP 工具面 | **首次：`msprof-mcp-setup`** |
| `msprof-analyze==8.5.2`（可选） | 集群 / advisor CLI | `pip install msprof-analyze==8.5.2` |
| Python ≥ 3.11、glibc ≥ 2.34 | uv tool + Perfetto | 系统环境 |

工具一览：[`references/msprof-mcp-tools.md`](references/msprof-mcp-tools.md)。

## 输入 / 输出

| 项 | 说明 |
| --- | --- |
| `profiler_path` | **必填**，用户给出的本地路径；禁止 ls/glob 猜测 |
| `workdir` | 默认 `./workspace` |
| `output_dir` | 可选；默认 `{workdir}/profiling` |
| 交付物 | `{output_dir}/profiling-report.md`（仅 MCP ready 后） |

## 全局约束

- **路径互斥**：本路径内 **禁止**执行服务化 Phase 0–2 / deploy-config / baseline / tuning，也禁止把分析套件改走快路径。
- **Skill 调用**：分析套件与 `msprof-mcp-setup` / `github-raw-fetch` / `compare-analyzer` 均为 `pipeline-only`；`op-mfu-calculator` 为 `dual`，本路径内一律 `invoke=pipeline`，产物写 `{workdir}/profiling/`（或 `output_dir`），禁止写 `{workdir}/skills/`。约定见 `configuration-tuning-skills/README.md`。
- **报告落盘**：只写 `workdir`（默认 `{workdir}/profiling/`）。
- **无路径不派发**：`profiler_path` 无效或缺失 → 中断并请用户确认。

## TaskList 骨架

```text
P0. 确认 profiler_path + 分析意图（已由路由完成则可跳过复核）
P1. GetMcpTools；未 ready → msprof-mcp-setup → 停止等 Reload
P2. 派发 serving-profiling-analysis-subagent
P3. 验收 profiling-report.md，路径 B 结束
```

## 分析顺序（摘要，由 subagent 执行）

1. MCP ready（否则只 setup）  
2. 数据校验（`ascend-profiler-data-validation`）  
3. 单卡：Timeline → 算子 → 通信 → 配置；多卡：advisor → Rank 下钻  
4. 交叉验证（Timeline vs CSV/DB）  
5. 落盘报告（问题 / 证据 / 影响 / 建议 / 验证方法）

## Skill 套件

- `msprof-mcp-setup`（**pipeline-only** · 首次硬门禁 · 本路径 `invoke=pipeline`）
- `ascend-profiler-data-validation` / `ascend-profiler-db-explorer`（**pipeline-only**）
- `ascend-computation-analysis` / `ascend-communication-analysis` / `ascend-schedule-analysis`（**pipeline-only**）
- `ascend-msprof-analyze-cli` / `compare-analyzer` / `ascend-cluster-fast-slow-rank-detector`（**pipeline-only**）
- `op-mfu-calculator`（**dual** · 本路径 `invoke=pipeline`）
- `github-raw-fetch`（**pipeline-only** · 本路径 `invoke=pipeline`）

`compare-analyzer` 在 `ascend-msprof-analyze-cli` 产出 `performance_comparison_result_*.xlsx` 之后以 `invoke=pipeline` 调用，产物写 `{workdir}/profiling/`。已导出的 `cluster_analysis_output` 仍用快路径 `cluster-analysis`，**不要**在本路径内改走该 standalone skill。
