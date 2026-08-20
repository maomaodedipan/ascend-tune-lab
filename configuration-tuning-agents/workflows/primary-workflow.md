# Primary 工作流 · 路径选择

`serving-perf-optimization` primary **每次请求必须先 Read 本文**，再选定 **快路径** 或 **一条** 平级路径。

本文只做路由与公共约定；独立 skill 分类见 [`configuration-tuning-skills/README.md`](../../configuration-tuning-skills/README.md)；各路径细节不在此展开。

## 路由一览

```text
                    +---------------------------+
                    |  primary-workflow.md      |
                    |  （快路径 / A / B / C）     |
                    +-------------+-------------+
                                  |
          +-----------+-----------+-----------+-----------+
          |           |           |           |
          v           v           v           v
   +------------+ +--------+ +--------+ +--------+
   | 快路径      | | 路径 A | | 路径 B | | 路径 C |
   | standalone | | 服务化 | | Prof.  | | PD配比 |
   | / dual     | | 调优   | | 分析   | |        |
   | 直接执行   | | 0→1→2 | | 独立   | | 0→4    |
   | SKILL.md   | |        | | 流水线 | |        |
   +------------+ +--------+ +--------+ +--------+
```

快路径 **不是** 第四条产品路径，与 A/B/C **互斥**。完整 invoke 约定（信封、落盘、分类表）以 [`configuration-tuning-skills/README.md`](../../configuration-tuning-skills/README.md) 为准。

| 选定 | 详文（选定后 Read） | 触发条件（摘要） | 状态 |
| --- | --- | --- | --- |
| **快路径 · 独立 Skill** | 对应 `configuration-tuning-skills/<name>/SKILL.md` | 明确只要白名单工具，**且**无 A/B/C 产品意图 | 已实现 |
| **A · 服务化调优** | [`serving-tuning-workflow.md`](serving-tuning-workflow.md) | 基线复现 / 并行策略 / deploy-config / 服务化调优（且非 Profiling / PD 配比意图） | 已实现 |
| **B · Profiling 分析** | [`profiling-analysis-workflow.md`](profiling-analysis-workflow.md) | **同时**：① 明确要做 profiling 分析；② 已给本地 `*_ascend_pt` / `*_ascend_ms` / `PROF_*` 路径 | 已实现 |
| **C · 最佳 PD 配比** | [`pd-ratio-workflow.md`](pd-ratio-workflow.md) | 明确要做最佳 PD 配比 / PD 配比 / Prefill-Decode 配比 / PD ratio（实测 P/D 吞吐） | 已实现 |

> 后续若新增 **产品路径**，在上表与示意图中平级追加一行/一支即可，**不要**把新能力塞进服务化 Phase 内部。  
> 后续若新增 **可独立调用的 skill**，改 [`configuration-tuning-skills/README.md`](../../configuration-tuning-skills/README.md) 分类表与本文快路径表，**不要**新开一条路径。

## 判定顺序（硬要求）

1. **有 A/B/C 产品意图** → 走对应流水线。话里即使带了 dual skill 关键词，也只当内部步骤；**禁止**改走快路径。
2. **只有白名单 skill 的工具意图，没有产品意图** → 快路径：Read 该 `SKILL.md`，`invoke=standalone`，禁止进入任何路径详文 / Phase。
3. **用户明确只要某某 skill、不要走流水线** → 仅当该 skill 在白名单内才走快路径；缺输入只问该 skill 的参数。`pipeline-only` 即使被点名也禁止快路径。
4. **既像独立工具又像流水线** → **流水线优先**。
5. **都对不上** → 问用户：独立工具 / A / B / C。默认不派发、不执行快路径。

未选定前禁止进入任一路径的 Phase / 分析步骤。

## 快路径白名单

仅当判定顺序第 2/3 步命中。完整表与信封见 README。

| Skill | invoke | 独立触发（须明确、且无 A/B/C 意图） |
| --- | --- | --- |
| `op-mfu-calculator` | dual | 算 MFU / 算子利用率 |
| `ascend-dump-analyzer` | standalone | 采集 / 比对 Ascend 环境 dump |
| `cluster-analysis` | standalone | 已有集群分析目录的全景 / 比对报告 |
| `vllm-ascend-tuning` | standalone | OS / CANN / Graph Mode 等手册式调优（非路径 A） |

快路径行为：

- 只 Read 对应 `SKILL.md` 并执行；**禁止** Read 路径 A/B/C 详文、禁止派发 subagent。
- `dual` 标 `invoke=standalone`。产物只写 `{workdir}/skills/<skill-name>/`。
- **禁止**写 `baseline-summary.md`、`pd-check-status`、`profiling-report.md`、`progress.md` 等门禁/进度文件。
- **禁止**声称某 Phase 已完成。
- **禁止**为凑参去读或生成 `deploy-config.md` / `pd-deploy-config.md`。
- 未列入上表的 skill（`pipeline-only`）禁止快路径。`msprof-mcp-setup` 只在进入路径 B 后作为 Step 0 执行，禁止单独「只装 MCP」。`compare-analyzer` 只在路径 B 内由 profiling subagent 调用，禁止单独「只解析 compare xlsx」。

## 路由规则（硬要求）

1. **先按判定顺序选定，再 Read 详文或 SKILL.md**。
2. **互斥**：同一请求只走快路径或一条产品路径；禁止混跑；禁止在 A/B/C 中途插入快路径或另一条路径。
3. **路径 B 缺 `profiler_path`** → 只索取路径并停止；**不得**因此进入路径 A 或 C，也不得改成快路径分析。
4. **路径 C**：用户提到 PD 配比 / 最佳 P:D 等 → 进入 C；**不得**把配比实测塞进路径 A Phase 2 或快路径。
5. 派发模板统一见 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)。

## 公共约定 · `workdir`

快路径与三条路径共用：

| 优先级 | 来源 | 路径 |
| --- | --- | --- |
| 1 | 用户指定 | 消息中的 `workdir` / 工作目录 |
| 2 | **默认** | **`{cwd}/workspace`**（不存在则 `mkdir -p`） |

- 未指定时创建并告知：`workdir = <cwd>/workspace`。
- **全部报告 / 中间产物只写在 `workdir` 内**。

落盘目录：快路径 `{workdir}/skills/<skill-name>/`；服务化 `{case_dir}/baseline|tuning/`；Profiling `{workdir}/profiling/`；PD 配比 `{workdir}/pd-ratio/`。

## 进入后

| 选定 | Primary 行为 |
| --- | --- |
| **快路径** | Read 对应 `SKILL.md`（`invoke=standalone`）；禁止派发 subagent；禁止进入 A/B/C |
| **A** | Read `serving-tuning-workflow.md`，严格按 Phase 0 → 1 → 2 推进；**禁止**派发 profiling / PD 配比 subagent |
| **B** | Read `profiling-analysis-workflow.md`，派发 profiling subagent；**禁止**执行服务化 / PD 配比 Phase |
| **C** | Read `pd-ratio-workflow.md`，按 Phase 0 → 1 → 2 → 3 → 4 逐步派发四个 PD subagent；**禁止**混跑 A/B |
