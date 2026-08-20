# Skill 调用约定

本文是 skill **如何被调用** 的唯一说明：哪些走 A/B/C 流水线，哪些可由 Primary 直接执行，哪些两者都可以。

架构不变：**Plugin → Agent → Skill**。不新增路径，不给单步工具建 subagent。路由仍由 Primary 读 `workflows/primary-workflow.md` 后判定。

| 文档 | 职责 |
| --- | --- |
| [`../configuration-tuning-agents/workflows/primary-workflow.md`](../configuration-tuning-agents/workflows/primary-workflow.md) | 每次请求先 Read；按本文白名单做快路径 / A / B / C |
| 本文 | invoke 分类、dual 信封、落盘隔离、分类表 |
| 各 `SKILL.md` | 该工具的 SOP（算法、脚本、参数） |

---

## 三种 `invoke`

每个 skill 必须且只能属于一类。分类以 **本文表格** 为准；`SKILL.md` frontmatter **必须**写 `invoke:`，且与表一致。

| `invoke` | 含义 | Primary | Subagent |
| --- | --- | --- | --- |
| `standalone` | 只作独立工具 | 可快路径直接 Read `SKILL.md` | 默认不调用 |
| `dual` | 既是流水线步骤，又可独立调用 | 无 A/B/C 产品意图时可快路径 | 流水线内按 Phase/Step 调用 |
| `pipeline-only` | 只作流水线步骤 | **禁止**快路径 | 仅对应 subagent 调用 |

判定标准：

- 单步、输入当场能给齐、没有 Phase 门禁、失败不改流水线进度 → `standalone` 或 `dual`
- 有配置门禁、多阶段、要写 `*status.md` / `progress.md`、失败要回退 Phase → `pipeline-only`
- 同一套 SOP 两种用法 → `dual`，**不要**复制成两个 skill

路径（A/B/C）是用户可感知的产品；skill 是步骤。禁止把工具升格成 Path D/E/F。

---

## 架构

```text
用户请求
    │
    ▼
Primary  Read primary-workflow.md
    │
    ├── 快路径（standalone / dual，且无 A/B/C 产品意图）
    │       Read 对应 SKILL.md，invoke=standalone，当场执行
    │
    └── 慢路径（路径 A / B / C，互斥）
            Read 路径详文 → 派发 subagent
            subagent 按 Phase 调用 pipeline-only / dual（invoke=pipeline）
```

- 快路径 **不是** 第四条流水线，与 A/B/C 仍然互斥：一次请求只走一条。
- 简单 skill **不** 建 subagent。Subagent 只服务多步、有门禁、要落盘进度的工作。

---

## 路由顺序（硬要求）

Primary 在选 A/B/C **之前**按下列顺序判定。命中即停止往下。

1. **有 A/B/C 产品意图** → 整条走对应流水线。话里即使带了 dual skill 关键词，也只当内部步骤，**禁止**改走快路径。  
   例：「分析这份 profiling 并算 MFU」→ 路径 B，由 profiling subagent 调 `op-mfu-calculator`。
2. **只有白名单 skill 的工具意图，没有产品意图** → 快路径。Read 该 `SKILL.md`，`invoke=standalone`。  
   例：「910B3 上这个 GEMM 的 MFU 是多少」。
3. **用户明确说不要走流水线、只要某某 skill** → 仅当该 skill 在白名单内才走快路径；缺输入只问该 skill 的参数，不问 `deploy-config.md` / `pd-deploy-config.md`。`pipeline-only` 即使被点名也禁止快路径。
4. **既像独立工具又像流水线** → **流水线优先**，并告知用户本次按 A/B/C 跑。
5. **都对不上** → 问用户：独立工具 / 路径 A / B / C。默认不派发 subagent，也不执行快路径。

产品意图关键词（摘要，完整触发见各路径详文）：

| 产品 | 意图示例 |
| --- | --- |
| A · 服务化调优 | 服务化调优、基线复现、并行策略、`deploy-config` |
| B · Profiling 分析 | profiling / profiler / msprof **分析**（须同时有本地数据路径才进入） |
| C · 最佳 PD 配比 | 最佳 PD 配比、Prefill-Decode 配比、PD ratio |

「只想算 MFU / 只比对环境 dump」**不是** 产品意图。解析 compare xlsx 已改为 `pipeline-only`，须走路径 B，禁止快路径。

`msprof-mcp-setup` 已改为 `pipeline-only`：禁止「只装 MCP」快路径；只在进入路径 B 后作为 Step 0 / subagent 步骤执行。

---

## Dual：一份 SOP，两套信封

`dual` skill 算法不变，变的是调用信封。Read `SKILL.md` 之前由调用方标明模式：

| | `invoke=standalone` | `invoke=pipeline` |
| --- | --- | --- |
| 谁调用 | Primary（快路径） | 对应路径的 subagent |
| 输入 | 对话里当场给齐；禁止去读流水线配置来凑参 | 由上游产物注入，不得再问一套平行配置 |
| 输出 | `{workdir}/skills/<skill-name>/` | 该路径约定目录（见各 workflow） |
| 状态文件 | **禁止**写门禁 / 进度文件 | 由 subagent 按 Phase 规则写 |
| 对用户的说法 | 只报告本工具结果 | 不把单步说成「某 Phase 已完成」（除非该 Phase 定义上就是这一步） |

`SKILL.md` 建议用这两节承接信封（可按需精简）：

```markdown
## 独立调用
- 触发：用户只要本工具，且没有 A/B/C 产品意图
- 输入：……
- 输出：`{workdir}/skills/<skill-name>/`
- 禁止：写 baseline-summary、pd-check-status、profiling-report、progress.md
- 禁止：声称 Phase 已完成或进入下一 Phase

## 流水线内调用
- 触发：仅由对应 subagent 在 Phase/Step 内调用
- 输入：由上游注入
- 输出：写回该路径约定目录
```

---

## 落盘隔离（硬要求）

未指定 `workdir` 时仍为 `{cwd}/workspace`（与三条路径相同）。

| 模式 | 目录 | 禁止写入 |
| --- | --- | --- |
| standalone | `{workdir}/skills/<skill-name>/` | `*/baseline/`、`*/tuning/`、`{workdir}/profiling/`、`{workdir}/pd-ratio/`、任何 `*status.md` / `progress.md` |
| pipeline | 各路径详文约定的目录 | standalone 目录不是流水线门禁 |

独立调用可以写自己的小报告，但 **不能** 让下次跑 A/B/C 误以为某 Phase 已通过。

---

## 当前分类

### 快路径白名单（Primary 可直接调用）

仅当路由顺序第 2/3 步命中时使用。

| Skill | invoke | 独立触发（无 A/B/C 意图） | 流水线内 |
| --- | --- | --- | --- |
| `op-mfu-calculator` | dual | 算 MFU / 算子利用率 | 路径 B 算子 MFU |
| `ascend-dump-analyzer` | standalone | 采集 / 分析 / 比对 Ascend 环境 dump JSON | — |
| `cluster-analysis` | standalone | 对已有 `cluster_analysis_output` 做集群全景或双集群比对 | — |
| `vllm-ascend-tuning` | standalone | OS / CANN / Graph Mode / 量化等手册式调优 | — |

### pipeline-only（禁止快路径）

| Skill | 所属 |
| --- | --- |
| `ascend-baseline-generator` | 路径 A · Phase 1 |
| `serving-parallel-strategy-tuning` | 路径 A · Phase 2 入口 |
| `find-possible-parallel-strategy` | 路径 A · Phase 2 |
| `serving-kv-cache-capacity` | 路径 A · Phase 2 |
| `serving-slo-concurrency` | 路径 A · Phase 2 |
| `serving-cfg-extract` | 路径 A · 预留线上日志（当前 Phase 2 不执行） |
| `serving-perf-metrics` | 路径 A · 预留线上日志（当前 Phase 2 不执行） |
| `vllm-ascend-config-extractor` | 路径 A · 辅助 |
| `model-feature-extractor` | 路径 A · 辅助 |
| `ascend-profiler-data-validation` | 路径 B |
| `ascend-profiler-db-explorer` | 路径 B |
| `ascend-computation-analysis` | 路径 B |
| `ascend-communication-analysis` | 路径 B |
| `ascend-schedule-analysis` | 路径 B |
| `ascend-msprof-analyze-cli` | 路径 B |
| `compare-analyzer` | 路径 B · compare xlsx 解读 |
| `ascend-cluster-fast-slow-rank-detector` | 路径 B |
| `msprof-mcp-setup` | 路径 B · Step 0 硬门禁 |
| `github-raw-fetch` | 路径 B（各路径 subagent 拉远端文档时也可 `invoke=pipeline`） |
| `pd-config-env-check` | 路径 C · Phase 1 |
| `aisbench-install` | 路径 C · Phase 2 |
| `pd-deploy` | 路径 C · Phase 3 |
| `pd-ratio-benchmark` | 路径 C · Phase 4 |

分析套件（`ascend-*-analysis` 等）即使「只要其中一张表」，也保持 `pipeline-only`，避免绕过路径 B 的 MCP 门禁和完整报告。

`cluster-analysis` 吃的是 **已经导出的** `cluster_analysis_output`，不是原始 `PROF_*`。有原始采集目录且要做完整 Profiling → 仍走路径 B。`compare-analyzer` 已改为 `pipeline-only`，只在路径 B 内解读 compare xlsx。

`vllm-ascend-tuning` 是手册式建议，**不是**路径 A。用户要基线复现 / 并行策略流水线 → 仍走路径 A；要 PD 配比实测 → 仍走路径 C。

`pd-config-env-check` / `aisbench-install` / `pd-deploy` 即使技术上能单独跑，也保持 `pipeline-only`：单独检查/安装/部署会拆开路径 C，且容易误写门禁状态。

---

## Primary 的 `skills:` 列表

Cursor 按 **当前 agent 声明的 skills** 做匹配。Primary 的 `AGENTS.md` `skills:` **只挂白名单**（`standalone` + `dual`）。`pipeline-only` 只写在对应 subagent 的 `skills:` 上。

列表挂上 ≠ 允许跳过 Phase。有产品意图时仍走流水线；快路径只在路由顺序第 2/3 步生效。

---

## 新增 skill 清单

1. 在本文表格归类 `standalone` / `dual` / `pipeline-only`（先问：有没有 Phase 门禁、要不要写 `*status.md`）。
2. `SKILL.md` frontmatter 增加 `invoke:`，与表一致。`dual` 补上「独立调用 / 流水线内调用」两节。
3. `standalone` / `dual`：加入 Primary `AGENTS.md` 的 `skills:`，并写入 `primary-workflow.md` 快路径表。
4. `pipeline-only`：只加入对应 subagent 的 `skills:`，**不要**加入 Primary 列表。
5. `init.sh` 的 `INCLUDED_SKILLS` 按需追加（安装挂载，与能否快路径无关）。
6. 不要新开一条平级路径，除非这是新的用户可感知产品（与 A/B/C 同级的整段流水线）。

---

## 禁止

- 给计算器 / 日志抽取类 skill 建 subagent 或 Path D/E/F。
- 把同一个 SOP 拆成 `foo` 与 `foo-standalone` 两个 skill。
- 独立调用读写流水线门禁文件，或声称某 Phase 已完成。
- 独立调用为了凑参去读 / 生成 `deploy-config.md`、`pd-deploy-config.md`。
- 意图模糊时默认进路径 A。
- Primary 直接执行 `pipeline-only` skill。
- 流水线进行中再插入快路径或另一条路径。
