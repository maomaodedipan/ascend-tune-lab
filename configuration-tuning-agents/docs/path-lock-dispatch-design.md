# 路径锁定与子代理派发设计

| 项 | 值 |
| --- | --- |
| 状态 | 部分落地（2026-08-24）：短路由、一页门禁、短 Task 模板、subagent 拒收） |
| 适用范围 | `serving-perf-optimization` Primary + 全部 `serving-*` subagent |
| 非目标 | 不把编排真源改成 Cursor-only；不新增产品路径 |

本文回答三件事：

1. 多路径时如何 **锁路径**，避免串台。
2. 锁定之后如何 **正确派发** 子代理（查表，不靠 description 自选）。
3. 如何用子代理做 **上下文隔离**（长 SOP 不进 Primary）。

当前实现已具备互斥路由、Phase 门禁、`Task.subagent_type` 硬编码。目标态是把 Primary 从「读完全文再派发」收成「短路由 + 文件状态机」。

---

## 1. 目标与非目标

### 1.1 目标

- 一次请求只进入：快路径 **或** 路径 A **或** B **或** C。
- 路径锁定后，`subagent_type` 只来自该路径的派发表，禁止按子代理 `description` 自动挑选。
- 每个 subagent 使用独立会话；阶段之间只通过 `workdir` 下的 status/report 交接。
- 同一套真源可挂到 Cursor / Claude / OpenCode 等；入口是 `AGENTS.md` + `init.sh`，不是 IDE 专用 Command。

### 1.2 非目标

- 用 Skill / Rule 代替 subagent 做隔离（它们都在当前会话追加上下文）。
- 路径 C 四个 Phase 并行派发。
- Primary 执行 `pipeline-only` skill。

---

## 2. 分层

```text
┌─────────────────────────────────────────────────────────┐
│ 适配层（按 IDE 挂载，可薄）                                  │
│  Cursor: .cursor/{agents,skills,workflows} + AGENTS.md     │
│  Claude: CLAUDE.md、.claude/{agents,skills}                │
│  其它:   init.sh → AGENTS.md + agents/ + skills/          │
└───────────────────────────┬─────────────────────────────┘
                            │ 只做「选路径 / 挂文件」
                            ▼
┌─────────────────────────────────────────────────────────┐
│ 编排层 Primary（短，常驻主会话）                             │
│  AGENTS.md 角色 + 本文的路由/派发表                          │
│  Phase 0 配置门禁；写 progress.md；Task 一次一个             │
└───────────────────────────┬─────────────────────────────┘
                            │ Task(subagent_type=表内 name)
                            ▼
┌─────────────────────────────────────────────────────────┐
│ 隔离层 Subagent（独立会话）                                  │
│  agents/<name>.md = 角色 + 拒收错 scene                     │
│  自己 Read 对应 SKILL.md（invoke=pipeline）                 │
└───────────────────────────┬─────────────────────────────┘
                            │ 落盘
                            ▼
┌─────────────────────────────────────────────────────────┐
│ 交接层 文件总线                                              │
│  progress.md、*-status.md、report、rendered/               │
└─────────────────────────────────────────────────────────┘
```

**真源（禁止 Cursor 化）：**

| 资产 | 路径 | 谁读 |
| --- | --- | --- |
| Primary 角色 | `configuration-tuning-agents/AGENTS.md` | Primary |
| 路径 SOP（应变短） | `workflows/*-workflow.md` | 目标：仅 Primary 读「门禁+派发表」；Phase 细则下放到 subagent/skill |
| Subagent 角色 | `configuration-tuning-agents/agents/*.md` | 该 subagent |
| 工具 SOP | `configuration-tuning-skills/<name>/SKILL.md` | 快路径=Primary；流水线=对应 subagent |

Cursor 没有名为 `workflows/` 的一等目录。路径锁定靠自然语言 + Primary，不提供额外 Command 入口。

---

## 3. 上下文隔离规则

| 规则 | 说明 |
| --- | --- |
| I1 | 长 SOP（Phase 步骤、脚本、KV 公式）只允许出现在 **被派发的那个** subagent 会话，或它 Read 的 Skill。 |
| I2 | Primary **禁止**为了派发而去 Read 路径详文全文；最多读派发表 + 门禁表（一页）。 |
| I3 | Task `prompt` 禁止粘贴 workflow/SKILL 正文；只传 `scene/path/phase/workdir/路径`。 |
| I4 | 子代理禁止 `resume` 成另一条路径的 agent；路径 C 四阶段用四个 name，不共用一个超大 agent 硬跑 0→4（可选演进见 §10）。 |
| I5 | 快路径不派发；dual skill 在流水线内由 **该路径 subagent** 调，产物写该路径目录，不写 `workdir/skills/`。 |

反模式：Primary Read `pd-ratio-workflow.md`（含全部实测硬规则）再派发 → 主会话被 PD 细节占满，隔离失败。

---

## 4. 路径锁定

### 4.1 判定顺序（仅用于第一次锁定）

与现网 `primary-workflow.md` 一致，锁定前 **零次** Task：

1. 有 A/B/C 产品意图 → 锁对应 path（话里带 dual 关键词也不改快路径）。
2. 仅白名单工具意图、无产品意图 → 锁 `path=fast`。
3. 用户明确只要某白名单 skill → `path=fast`（`pipeline-only` 点名也不进快路径）。
4. 既像工具又像流水线 → 流水线优先。
5. 对不上 → 问：独立工具 / A / B / C；**默认不派发**。

### 4.2 锁定产物 `progress.md`

路径 C 写 `{workdir}/pd-ratio/progress.md`；路径 A 建议 `{workdir}/progress.md` 或 `{case_dir}/progress.md`（实现时统一一种）；路径 B 写 `{workdir}/profiling/progress.md`。

最小字段：

```yaml
schema: path-lock/v1
path: C                 # fast | A | B | C
phase: 0                # 快路径无 phase；B 用 0=mcp / 1=analyze
status: ready_for_1     # 见各路径枚举
workdir: /abs/or/repo-relative
config_md_path: ...     # A/C；B 可空
# B only:
profiler_path: ...
# 锁定来源
lock_source: user_utterance | slash_command | user_confirm
locked_at: 2026-08-24T06:00:00Z
```

`path` 一经写入，本轮流水线结束前不得悄悄改写。用户要换路径：必须确认放弃当前 `path`，再开新 `progress.md`（或新 workdir）。

### 4.3 锁定后的聊天策略

| 用户新消息 | 行为 |
| --- | --- |
| 继续 / 重跑本 Phase / 补配置 | 仍走当前 path 的状态机 |
| 明确要换 A/B/C/快路径 | 先确认是否放弃；未确认 **禁止** 派其它路径 subagent |
| 顺口提到另一路径关键词 | **忽略**；不解锁 |

---

## 5. 派发状态机（锁定之后）

Primary 循环：

```text
loop:
  1. Read progress.md → path 必须已锁
  2. 读该 path 的门禁列，自上而下命中第一行「未完成」
  3. Task(subagent_type = 该行 name)  // 一次一个
  4. Read 该行验收文件
  5. 合法终态 → 更新 progress.phase/status，continue
     失败终态 → 按该 path 失败策略停止或回退；禁止改派其它 path
```

禁止：

- `subagent_type` 留空或改成表外 name。
- 根据子代理 `description` 让模型另选。
- 一次并行多个有副作用的 Phase（C 的 check/install/deploy/benchmark）。

### 5.1 快路径 `path=fast`

不派发。Primary 只 Read 对应 `configuration-tuning-skills/<name>/SKILL.md`，`invoke=standalone`。产物仅 `{workdir}/skills/<name>/`。

### 5.2 路径 A · 服务化调优

`workdir` 默认 `{cwd}/workspace`。配置 `{workdir}/deploy-config.md`。

| 顺序 | 门禁（全部满足才派） | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- | --- |
| P0 | Primary 自己做 | — | — | 合法 `## 基本参数` + `{workdir}/model_config.json` |
| P1 | P0 通过，且尚无完整 `{case_dir}/baseline/baseline-summary.md` | `serving-baseline-reproduce-subagent` | `baseline-reproduce` | `baseline-summary.md` + `baseline-launch.sh` |
| P2 | P1 验收通过 | `serving-tuning-subagent` | `serving-parallel-strategy-tuning` | `{case_dir}/tuning/tuning-status.md` 为 `completed` |

P2 内部的 KV / 并行枚举 / SLO 三个 skill 由 **tuning subagent** 调用，Primary 不再派子代理。

失败：停在当前 Phase；不进入 B/C。

### 5.3 路径 B · Profiling

| 顺序 | 门禁 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- | --- |
| P0 | 用户已给 `profiler_path`；否则只索取并停止 | — | — | `progress.md` 含路径 |
| P1 | P0 通过 | `serving-profiling-analysis-subagent` | `profiling-analysis` | `{workdir}/profiling/profiling-report.md`（MCP 未就绪则只交 setup 说明并停） |

只派这一个 subagent。禁止派 baseline / PD。

### 5.4 最佳 PD 配比（已改为独立 skill）

**已废弃 path=C。** 不要按本表派发。请用仓库根 `PD-ratio-benchmark/SKILL.md`。

下表仅作历史记录，实现已删除对应 subagent。

| 顺序 | 门禁 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- | --- |
| C0 | Primary：配置齐全（拉起命令可空） | — | — | 写出 `pd-ratio/progress.md` |
| C1 | C0 过，且 `pd-ratio/check/pd-check-status.md` ≠ `passed` | `serving-pd-config-check-subagent` | `pd-config-env-check` | 该文件 = `passed` |
| C2 | C1 passed，且 aisbench status 不是 `passed` 或 `skipped` | `serving-aisbench-install-subagent` | `aisbench-install` | `pd-ratio/aisbench/aisbench-install-status.md` |
| C3 | C2 过，且 `pd-ratio/deploy/pd-deploy-status.md` ≠ `passed` | `serving-pd-deploy-subagent` | `pd-deploy` | 该文件 = `passed`；`failed` → 回 C1，禁止进 C4 |
| C4 | C3 passed | `serving-pd-ratio-benchmark-subagent` | `pd-ratio-benchmark` | `pd-ratio/benchmark/pd-ratio-status.md` = `completed` |

合法 `subagent_type` 全集（path=C 时）：上表四个 name。出现 `serving-baseline-reproduce-subagent` 等即为缺陷。

---

## 6. Task 契约

### 6.1 必填

| 字段 | 约束 |
| --- | --- |
| `subagent_type` | 等于 `agents/<name>.md` 的 `name`，且 ∈ 当前 path 派发表 |
| `description` | 短标题，供 UI；不参与选人 |
| `prompt` | 含下列键值，**不含** SOP 正文 |

### 6.2 Prompt 模板（路径 C Phase 1 示例）

```text
scene: pd-config-env-check
path: C
phase: 1
workdir: {workdir}
config_md_path: {workdir}/pd-deploy-config.md

执行本 scene。Read：
- configuration-tuning-agents/agents/serving-pd-config-check-subagent.md
- configuration-tuning-skills/pd-config-env-check/SKILL.md（invoke=pipeline）

禁止：路径 A/B；本路径其它 Phase；快路径 skill 落盘。
完成后必须写 pd-ratio/check/pd-check-status.md 与 report。
```

其它 Phase 只改 `scene` / `phase` / 角色文件 / skill 名 / 产物路径。占位符仍以 `workflows/references/subagent-prompt-templates.md` 为实现对照，目标态应把该文件里的长【强制】清单下放到 agent md 与 Skill。

### 6.3 子代理拒收

每个 `agents/*.md` 正文首节：

1. 声明合法 `scene` 列表（通常一个）。
2. prompt 中 `path`/`scene` 不匹配 → 写本 Phase `*-status.md` 为 `failed`（或退出并回报），**不执行业务**。
3. `description` 写「仅由 serving-perf-optimization 在路径 X Phase N 派发」+ **禁止**用于其它路径；避免 Cursor 按描述自动委托。

---

## 7. Primary 允许 / 禁止清单

**允许：**

- 判定并写入 `progress.md`。
- Phase 0：建 workdir、生成/校验配置、路径 A 下载 `model_config.json`、询问 SLO。
- Read 派发表、门禁、status、短报告摘要。
- `Task` 一次一个表内 subagent。
- 快路径 Read 白名单 `SKILL.md`。

**禁止：**

- Read 路径详文中的实测硬规则/脚本级步骤（应在 Skill）。
- 派发表外 `subagent_type`。
- 未锁定 path 时派发。
- 执行 `pipeline-only` skill。
- 用子代理口头「成功」代替 status 文件。

---

## 8. 多 IDE

| 工具 | 锁路径入口 | 派发 |
| --- | --- | --- |
| 任意 | 自然语言 → Primary 判定顺序 | 同一张派发表 + 同一批 `agents/*.md` |
| Cursor | 同上 | `Task` + `.cursor/agents` |
| Claude | 同上 | Claude 的 subagent/Task 等价物 |

入口是自然语言。  
`.cursor-plugin/plugin.json` 不是 `init.sh` 的安装产物；Cursor 与 CANNBot 一样通过项目 `.cursor/skills`、`.cursor/agents` 发现。`init.sh project claude` 同样不依赖它。

---

## 9. 文件与命名（实现对照）

| 角色 | 现网路径 |
| --- | --- |
| Primary | `configuration-tuning-agents/AGENTS.md` |
| 路由（应变短） | `workflows/primary-workflow.md` |
| 派发模板（应变短） | `workflows/references/subagent-prompt-templates.md` |
| A/B/C 详文 | `workflows/serving-tuning-workflow.md` 等 |
| Subagents | `configuration-tuning-agents/agents/serving-*.md` |
| Skills | `configuration-tuning-skills/<name>/SKILL.md` |

`Task.subagent_type` 必须与 frontmatter `name` 逐字一致。

---

## 10. 相对现网的迁移

分步，不一次改目录名（**1–5 已落地**；第 6 项仍不在范围内）：

1. **文档**：以本文为派发规范；`primary-workflow.md` 增加「锁定后只查表」和 `progress.md` 字段。
2. **收短 Primary**：路径 `*-workflow.md` 只留触发、互斥、派发表、门禁、Phase 0；实测硬规则已在对应 `SKILL.md` 的，从 Primary 必读中删除。
3. **收短 Task prompt**：长【强制】迁入 `agents/*.md`。
4. **description / 拒收**：补 path+phase+scene 边界。
5. **适配**：`init.sh` 按 CANNBot 把 skills / agents / workflows 挂到目标 IDE 目录。项目根挂载一律 gitignore。
6. **不在本设计内**：把 `configuration-tuning-*` 改名为 Cursor 默认 `agents/` `skills/`（纯整理）。

可选演进：路径 C 合成一个 `serving-pd-ratio-pipeline-subagent` 在内部串四阶段——主会话更短，但 C1–C4 不再互相隔离。默认保持四 subagent + 文件总线。

---

## 11. 验收标准

- 锁定 C 后，日志里不得出现 A/B 的 `subagent_type`。
- C3 `failed` 后不得出现 benchmark subagent。
- Primary 一次循环最多一个 `Task`。
- 子代理 prompt 不含 workflow 全文。
- 换路径必须有用户确认记录（对话或 `progress.md` 新文件）。

---

## 12. 一句话

**自然语言只锁一次 `path`；此后 `subagent_type` 是（path × status 文件）的查表结果；子代理用独立会话读 Skill，用 status 和 Primary 交接。**
