# Primary 工作流 · 路径锁定与查表派发

`serving-perf-optimization` 是 **一个** 插件的唯一入口。每次请求先 Read 本文：先 **锁 path**，再按表派发。设计见 [`../docs/path-lock-dispatch-design.md`](../docs/path-lock-dispatch-design.md)。

独立 skill 分类见 [`configuration-tuning-skills/README.md`](../../configuration-tuning-skills/README.md)。

**禁止**：未锁定 path 时派发；按子代理 `description` 自选 `subagent_type`；为派发而 Read 路径详文中的 Skill 级硬规则；一次并行多个有副作用的 Phase。

## 路由一览

```text
primary-workflow.md（锁 path）
        │
        ├── fast → 只 Read 白名单 SKILL.md，不派发
        ├── A    → Phase 0（本进程）→ 查表派 baseline → tuning
        ├── B    → 有 profiler_path → 派 profiling
        └── C    → Phase 0（本进程）→ 查表派 check → aisbench → deploy → benchmark
```

| 选定 | 锁 `path` | 触发（摘要） |
| --- | --- | --- |
| 快路径 | `fast` | 只要白名单工具，且无 A/B/C 产品意图 |
| A · 服务化调优 | `A` | 基线 / 并行策略 / `deploy-config`（非 Profiling、非 PD） |
| B · Profiling | `B` | 明确要分析 **且** 已给本地 `*_ascend_pt` / `*_ascend_ms` / `PROF_*` |
| C · 最佳 PD 配比 | `C` | PD 配比 / Prefill-Decode 配比 / PD ratio |

## 判定顺序（仅用于第一次锁定）

1. 有 A/B/C 产品意图 → 锁对应 path（话里带 dual 关键词也不改快路径）。
2. 只有白名单工具意图 → `path=fast`。
3. 用户明确只要某白名单 skill → `path=fast`（`pipeline-only` 点名也不进快路径）。
4. 既像工具又像流水线 → 流水线优先。
5. 对不上 → 问：独立工具 / A / B / C；**默认不派发**。

锁定后写入该路径的 `progress.md`（字段见下）。未确认放弃前禁止改 `path`。用户要换路径必须先确认。

## 快路径白名单

| Skill | invoke | 独立触发 |
| --- | --- | --- |
| `op-mfu-calculator` | dual | 算 MFU |
| `ascend-dump-analyzer` | standalone | 比对环境 dump |
| `cluster-analysis` | standalone | 已有集群分析目录 |
| `vllm-ascend-tuning` | standalone | 手册式调优（非路径 A） |

行为：只 Read 对应 `SKILL.md`（`invoke=standalone`）；产物 `{workdir}/skills/<name>/`；不派发；不写流水线 status。

## `progress.md`

C：`{workdir}/pd-ratio/progress.md`；A：`{case_dir}/progress.md`；B：`{workdir}/profiling/progress.md`。

```yaml
schema: path-lock/v1
path: C                 # fast | A | B | C
phase: 0
status: ready_for_1
workdir: ...
config_md_path: ...     # A/C
profiler_path: ...      # B
lock_source: user_utterance | slash_command | user_confirm
```

## 派发循环（path 已锁）

1. Read `progress.md`，确认 `path`。
2. 用下面对应表，自上而下命中第一行未完成门禁。
3. `Task`：`subagent_type` **抄表内 name**；prompt 只用 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md) 短模板。
4. 回来只认 status 文件，不认口头「成功」。
5. 一次一个 Task。表外 name 禁止出现。

### path=A

详文（Phase 0 + 门禁）：[`serving-tuning-workflow.md`](serving-tuning-workflow.md)。

| 门禁 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- |
| Phase 0：合法 `deploy-config.md` + `{workdir}/model_config.json` | — | — | 写入 progress |
| 尚无完整 `baseline-summary.md` | `serving-baseline-reproduce-subagent` | `baseline-reproduce` | `{case_dir}/baseline/baseline-summary.md` + `baseline-launch.sh` |
| 上一项通过 | `serving-tuning-subagent` | `serving-parallel-strategy-tuning` | `{case_dir}/tuning/tuning-status.md` = `completed` |

禁止派 profiling / 任何 PD subagent。

### path=B

详文：[`profiling-analysis-workflow.md`](profiling-analysis-workflow.md)。

| 门禁 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- |
| 无 `profiler_path` | — | — | 只索取并停止 |
| 已有路径 | `serving-profiling-analysis-subagent` | `profiling-analysis` | `{workdir}/profiling/profiling-report.md`（MCP 未就绪则只交 setup 并停） |

禁止派 A/C subagent。MCP setup 由 **该 subagent** 执行，Primary 不跑 `pipeline-only` skill。

### path=C

详文（Phase 0 + 门禁）：[`pd-ratio-workflow.md`](pd-ratio-workflow.md)。实测硬规则在对应 `SKILL.md`。

| 门禁 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- |
| Phase 0：合法 `pd-deploy-config.md` | — | — | `pd-ratio/progress.md` |
| `check/pd-check-status.md` ≠ `passed` | `serving-pd-config-check-subagent` | `pd-config-env-check` | 该文件 = `passed` |
| aisbench 不是 `passed` 或 `skipped` | `serving-aisbench-install-subagent` | `aisbench-install` | `aisbench/aisbench-install-status.md` |
| `deploy/pd-deploy-status.md` ≠ `passed` | `serving-pd-deploy-subagent` | `pd-deploy` | `passed`；`failed` → 回 Phase 1，禁止进 Phase 4 |
| deploy = `passed` | `serving-pd-ratio-benchmark-subagent` | `pd-ratio-benchmark` | `benchmark/pd-ratio-status.md` = `completed` |

禁止派 A/B subagent。

## 公共 `workdir`

| 优先级 | 路径 |
| --- | --- |
| 用户指定 | 消息中的 workdir |
| 默认 | `{cwd}/workspace`（不存在则创建） |

报告只写 workdir：fast → `skills/<name>/`；A → `{case_dir}/baseline|tuning/`；B → `profiling/`；C → `pd-ratio/`。
