# 路径 B · Profiling 分析（门禁）

`path=B` 已由 [`primary-workflow.md`](primary-workflow.md) 锁定。与 A/C 互斥。不要求 `deploy-config.md`。

禁止改走快路径（分析套件保持 `pipeline-only`；`op-mfu-calculator` 在本路径 `invoke=pipeline`，产物写 `profiling/` 不写 `skills/`）。

## 触发复核

须同时：① 明确要做 profiling 分析；② 已给本地 `profiler_path`（`*_ascend_pt` / `*_ascend_ms` / `PROF_*` 或可唯一定位的父目录）。

缺路径 → **只索取并停止**，不派发。禁止 ls/glob 猜测。

## 落盘

| 项 | 说明 |
| --- | --- |
| `profiler_path` | 必填 |
| `workdir` | 默认 `./workspace` |
| `output_dir` | 默认 `{workdir}/profiling` |
| 进度 | `{workdir}/profiling/progress.md`（`path: B`） |
| 交付 | `{output_dir}/profiling-report.md`（仅 MCP ready 后） |

## 派发

| 门禁 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- |
| 无有效 `profiler_path` | — | — | 只索取 |
| 已有路径 | `serving-profiling-analysis-subagent` | `profiling-analysis` | `profiling-report.md`；MCP 未就绪则只交 setup 并停 |

MCP setup、`GetMcpTools`、分析顺序由 **该 subagent** 执行（见其 agent md + `msprof-mcp-setup`）。Primary **禁止**自己跑 `pipeline-only` skill，也禁止派 A/C subagent。

已导出的 `cluster_analysis_output` 用快路径 `cluster-analysis`（须另锁 `path=fast`，且用户确认放弃 B）。本路径内不要改走该 standalone skill。

工具一览（供 subagent）：[`references/msprof-mcp-tools.md`](references/msprof-mcp-tools.md)。
