# 路径 A · 服务化调优（门禁）

`path=A` 已由 [`primary-workflow.md`](primary-workflow.md) 锁定。本文件只给 Primary：**Phase 0**、门禁、派发表。Skill 细则由对应 subagent 读取。

进入后禁止快路径、禁止派 Profiling / PD subagent。

## 落盘

| 类别 | 相对 `workdir` |
| --- | --- |
| 配置 | `deploy-config.md`（或用户指定 `config_md_path`） |
| 模型 | `model_config.json`（Phase 0 下载或手供） |
| Case | `{case_dir}/`（默认 `cases/<model>-<device>-<quant>/`） |
| Phase 1 | `{case_dir}/baseline/` |
| Phase 2 | `{case_dir}/tuning/` |
| 源码仓 | `repos/` |
| 进度 | `{case_dir}/progress.md`（`schema: path-lock/v1`，`path: A`） |

## 派发

| 门禁 | `subagent_type` | scene | 验收 |
| --- | --- | --- | --- |
| Phase 0 通过 | — | — | 合法配置 + `model_config.json` |
| 尚无完整 baseline | `serving-baseline-reproduce-subagent` | `baseline-reproduce` | `baseline-summary.md` + `baseline-launch.sh` |
| 上一项通过 | `serving-tuning-subagent` | `serving-parallel-strategy-tuning` | `tuning/tuning-status.md` = `completed` |

prompt：[`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)。一次一个 Task。

本路径 skill 均为 `pipeline-only`（`invoke=pipeline`）。Phase 2 不部署、不压测、不改 `baseline-launch.sh`。无 `baseline-summary.md` 不进 Phase 2。clone 失败须警告并手供，禁止静默跳过（测试 `--allow-without-repos` 除外）。

## Phase 0（Primary）

1. Read [`references/user-config-format.md`](references/user-config-format.md)。
2. `workdir`：用户指定 → 否则创建 `{cwd}/workspace`。
3. `config_md_path`：用户指定 → 否则 `{workdir}/deploy-config.md`。
4. 文件不存在 → 写入 [`templates/deploy-config.template.md`](templates/deploy-config.template.md) 并 **停止**。
5. 存在但 `## 基本参数` 未填完 → 列出缺失项并 **停止**。
6. 校验通过后下载模型 config：
   ```bash
   python configuration-tuning-skills/serving-parallel-strategy-tuning/scripts/download_modelscope_config.py \
     --workdir {workdir} --config {config_md_path} --json
   ```
   - 成功或已有合法 `model_config.json` → 继续。
   - **失败** → 展示 warning，要求手供 `{workdir}/model_config.json`，**停止**。
7. 写 `progress.md`，确定 `case_dir`，进入 Phase 1。

终点：`{case_dir}/baseline/baseline-launch.sh` + `{case_dir}/tuning/tuning-process.md` + `tuning-status.md`。
