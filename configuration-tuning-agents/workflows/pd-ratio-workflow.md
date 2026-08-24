# 路径 C · 最佳 PD 配比（门禁）

`path=C` 已由 [`primary-workflow.md`](primary-workflow.md) 锁定。本文件只给 Primary：**Phase 0**、门禁、派发表。实测硬规则（交互壳、最小实例、PrefixLen、饱和扫点、`avail_npus` 等）在对应 `SKILL.md`，Primary 不复述。

与 A/B 互斥。四个 skill 均为 `pipeline-only`。即使「只检查 / 只安装 / 只部署」也不走快路径。

## 落盘（相对 `workdir`）

| 类别 | 路径 |
| --- | --- |
| 配置 | `pd-deploy-config.md` |
| 进度 | `pd-ratio/progress.md`（`path: C`） |
| Phase 1 | `pd-ratio/check/`（report、status、`rendered/`） |
| Phase 2 | `pd-ratio/aisbench/` |
| Phase 3 | `pd-ratio/deploy/` |
| Phase 4 | `pd-ratio/benchmark/` |

## 派发

| 进入 | 要求 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- | --- |
| Phase 1 | Phase 0 通过 | `serving-pd-config-check-subagent` | `pd-config-env-check` | `check/pd-check-status.md` = `passed` |
| Phase 2 | 上一项 `passed` | `serving-aisbench-install-subagent` | `aisbench-install` | `aisbench/aisbench-install-status.md` = `passed` 或 `skipped` |
| Phase 3 | AISBench 已就绪 | `serving-pd-deploy-subagent` | `pd-deploy` | `deploy/pd-deploy-status.md` = `passed`；**`failed` → 回 Phase 1，禁止进 Phase 4** |
| Phase 4 | deploy = `passed` | `serving-pd-ratio-benchmark-subagent` | `pd-ratio-benchmark` | `benchmark/pd-ratio-status.md` = `completed` |

prompt：[`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)。一次一个 Task。禁止派 A/B subagent。

Skill：`pd-config-env-check` / `aisbench-install` / `pd-deploy` / `pd-ratio-benchmark`。报告模板在 `templates/`。

## Phase 0（Primary）

1. `workdir`：用户指定 → 否则 `mkdir` `{cwd}/workspace`。
2. `config_md_path` 默认 `{workdir}/pd-deploy-config.md`。
3. 不存在 → 写入 [`templates/pd-deploy-config.template.md`](templates/pd-deploy-config.template.md) 并 **停止**。
4. 存在 → 按 [`references/pd-user-config-format.md`](references/pd-user-config-format.md) 校验模型/设备/序列长度等；拉起命令可空（Phase 1 从[官方模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/)回填）。
5. **TTFT / TPOT**：询问；用户提供则写入配置；仍不提供 → 默认 **TTFT 不设限制**、**TPOT=50ms**，写入配置并在 `progress.md` 注明 `slo_source=default`。
6. 通过 → 创建 `pd-ratio/`，写 `progress.md`，进入 Phase 1。

终点：`pd-ratio/benchmark/pd-ratio-report.md` + `pd-ratio-status.md`。
