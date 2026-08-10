# Primary 工作流 · 路径选择

`serving-perf-optimization` primary **每次请求必须先 Read 本文**，选定 **一条** 平级路径后再进入对应详文。  
本文只做路由与公共约定；各路径细节不在此展开。

## 平级路径一览

```text
                    +---------------------------+
                    |  primary-workflow.md      |
                    |  （路径选择 · 互斥）         |
                    +-------------+-------------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
+---------------------------+           +-----------------------------+
| 路径 A · 服务化调优         |           | 路径 B · Profiling 分析      |
| serving-tuning-workflow.md|           | profiling-analysis-workflow.md |
| Phase 0 → 1 → 2           |           | 独立分析流水线                 |
+---------------------------+           +-----------------------------+
```

| 路径 | 详文（选定后 Read） | 触发条件（摘要） | 状态 |
| --- | --- | --- | --- |
| **A · 服务化调优** | [`serving-tuning-workflow.md`](serving-tuning-workflow.md) | 基线复现 / 并行策略 / deploy-config / 服务化调优（且非 Profiling 意图） | 已实现 |
| **B · Profiling 分析** | [`profiling-analysis-workflow.md`](profiling-analysis-workflow.md) | **同时**：① 明确要做 profiling 分析；② 已给本地 `*_ascend_pt` / `*_ascend_ms` / `PROF_*` 路径 | 已实现 |

> 后续若新增路径（如压测复现等），在上表与示意图中平级追加一行/一支即可，**不要**把新能力塞进服务化 Phase 内部。

## 路由规则（硬要求）

1. **先判定路径，再 Read 详文**；未选定前禁止进入任一路径的 Phase / 分析步骤。
2. **路径互斥**：同一请求只走一条；禁止混跑、禁止在路径 A 中途插入路径 B（反之亦然）。
3. **意图不清** → 先问用户选 A 还是 B，默认不派发 subagent。
4. **路径 B 缺 `profiler_path`** → 只索取路径并停止；**不得**因此进入路径 A。
5. 派发模板统一见 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)。

## 公共约定 · `workdir`

两条路径共用：

| 优先级 | 来源 | 路径 |
| --- | --- | --- |
| 1 | 用户指定 | 消息中的 `workdir` / 工作目录 |
| 2 | **默认** | **`{cwd}/workspace`**（不存在则 `mkdir -p`） |

- 未指定时创建并告知：`workdir = <cwd>/workspace`。
- **全部报告 / 中间产物只写在 `workdir` 内**。

各路径落盘目录见对应详文（服务化：`{case_dir}/baseline|tuning/`；Profiling：`{workdir}/profiling/`）。

## 进入路径后

| 选定 | Primary 行为 |
| --- | --- |
| **A** | Read `serving-tuning-workflow.md`，严格按 Phase 0 → 1 → 2 推进；**禁止**派发 profiling subagent |
| **B** | Read `profiling-analysis-workflow.md`，派发 profiling subagent；**禁止**执行服务化 Phase 0–2 / deploy-config 门禁 |
