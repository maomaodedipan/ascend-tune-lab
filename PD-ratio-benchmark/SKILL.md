---
name: pd-ratio-benchmark
description: >-
  Standalone vLLM-Ascend Prefill/Decode ratio skill: check launch env, install
  AISBench, deploy 1P1D, then measure QPS and recommend PD instance ratio. Use
  when the user asks for 最佳 PD 配比, PD ratio, Prefill-Decode 配比, or
  pd-ratio-benchmark.
---

# pd-ratio-benchmark

独立 skill。Read 本文件后，在当前会话按顺序 Read / 执行四个子 skill。不经过插件编排，不派发任何 agent。

## 子 skill

全部在 `configuration-tuning-skills/`。每一步先 Read 该目录的 `SKILL.md`，再执行；上一步 status 未通过则停止。

| 顺序 | Skill | 目录 | 通过条件 |
| --- | --- | --- | --- |
| 1 | `pd-config-env-check` | `configuration-tuning-skills/pd-config-env-check/` | `pd-ratio/check/pd-check-status.md` = `passed` |
| 2 | `aisbench-install` | `configuration-tuning-skills/aisbench-install/` | `pd-ratio/aisbench/aisbench-install-status.md` = `passed` 或 `skipped` |
| 3 | `pd-deploy` | `configuration-tuning-skills/pd-deploy/` | `pd-ratio/deploy/pd-deploy-status.md` = `passed`；`failed` → 回到步骤 1，禁止进步骤 4 |
| 4 | `pd-ratio-measure` | `configuration-tuning-skills/pd-ratio-measure/` | `pd-ratio/benchmark/pd-ratio-status.md` = `completed` |

报告模板：`configuration-tuning-agents/workflows/templates/pd-*-report-template.md`。

## 工作目录与配置

- `workdir`：用户指定优先，否则 `{cwd}/workspace`（不存在则创建）。
- 配置：`{workdir}/pd-deploy-config.md`。
- 格式：[references/pd-user-config-format.md](references/pd-user-config-format.md)。
- 空模板：[templates/pd-deploy-config.template.md](templates/pd-deploy-config.template.md)。

## 步骤

1. Read 本 SKILL 与 `references/pd-user-config-format.md`。
2. **配置门禁**：
   - 配置文件不存在 → 写入模板并 **停止**，请用户填写后重试。
   - 存在 → 校验模型名称、设备类型、输入/输出长度；拉起命令可空（步骤 1 从官方教程回填）。
   - **TTFT / TPOT**：先问用户；仍不提供 → **TTFT 不设限制**、**TPOT=50ms**，写入配置。
3. 创建 `{workdir}/pd-ratio/`。
4. 按上表 **顺序** 执行四个子 skill：每次 Read 对应 `SKILL.md`，按该文件 SOP 做完，验收 status 文件后再进入下一步。一次只跑一个子 skill。
5. 步骤 3 失败 → 诊断后回到步骤 1（重新检查/渲染）；**禁止**未部署成功就压测。
6. 步骤 4 完成后把终态报告路径交给用户：`pd-ratio/benchmark/pd-ratio-report.md`。

## 产物（相对 workdir）

```text
pd-deploy-config.md
pd-ratio/
  check/          # 子 skill 1
  aisbench/       # 子 skill 2
  deploy/         # 子 skill 3
  benchmark/      # 子 skill 4（含 pd-ratio-report.md）
```

## 约束

- 宿主机只允许 docker；业务一律 `docker exec`。
- 基线只拉最小 **1P1D**（每侧卡数 = 拉起命令 `DP×TP`）。
- 不编造配置值；不擅自改 MTP / spawn / `LD_LIBRARY_PATH` / 量化等启动参数。
- 硬规则（KV 改写边界、AISBench 扫点、P/D SLO 拆分）以各子 skill 为准，本文件不复述。
