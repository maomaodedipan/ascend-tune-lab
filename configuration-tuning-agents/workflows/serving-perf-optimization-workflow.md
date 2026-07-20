# vLLM-Ascend 服务化性能优化 · 工作流

本工作流由 `serving-perf-optimization` primary agent 在每次收到服务化性能优化请求时强制 Read，并严格按其推进。当前 **Step 1 通过 subagent 实现**；Step 2 及以后在 subagent 补齐前由 primary 调度 repo 内 skill 或引导用户操作。

> 安装：`configuration-tuning-agents/init.sh` 会将本目录 `workflows/` 挂载到项目 `.cursor/workflows`（或对应工具配置目录）及项目根 `workflows/`。模板见 [`templates/baseline-summary-template.md`](templates/baseline-summary-template.md)，示例见 [`templates/baseline-summary-example.md`](templates/baseline-summary-example.md)。
>
> Subagent 映射：Step 1 对应 `serving-baseline-reproduce-subagent`（定义见 `configuration-tuning-agents/agents/serving-baseline-reproduce-subagent.md`），派发模板见 `configuration-tuning-agents/workflows/references/subagent-prompt-templates.md`。

## 流程总览

```text
+--------------------------------------------------------------+
| 0. 确认场景与性能目标                                         |
|    模型/设备/量化/NPU/部署策略/IO 长度；可选吞吐或时延目标    |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| 1. 性能基线复现 【subagent】                                  |
|    拉 serving-baseline-reproduce-subagent                     |
|    产出 baseline-launch.sh + baseline-summary.md              |
+-----------------------------+--------------------------------+
```

## 执行规则

进入本工作流后，先建立 TaskList，再逐阶段推进。拉 subagent 前 Read `references/subagent-prompt-templates.md` 并替换占位符。

### 全局约束

- **Step 1 硬门禁**：无 `{case_dir}/baseline/baseline-launch.sh` 与 `baseline-summary.md` 不得进入 Step 2。
- **主 agent 只编排**：Step 1 的文档匹配与命令生成必须由 `serving-baseline-reproduce-subagent` 完成。
- **低时延 / 高吞吐选择**：subagent 产出双方案对比时，由 primary 询问用户或按 skill 推荐规则代用户确认后再写最终 `baseline-launch.sh`。
- **进度文件**：在 `{case_dir}/progress.md` 记录场景、Step 状态、baseline 路径；Step 1 完成后更新「基线已就绪」。

### TaskList 骨架

```text
T0. 确认场景参数与性能目标（可选）
T1. 准备或确认 MD 配置文件路径（可参考 config.example.md）
T2. 拉 serving-baseline-reproduce-subagent 完成基线复现
T3. 用户确认低时延/高吞吐（若 subagent 回报双匹配）
T4. 部署验证：执行 baseline-launch.sh，记录启动结果
T5. serving-cfg-extract 解析启动日志
T6. serving-perf-metrics 解析运行/压测日志
T7. 调优迭代：对照目标，规划下一轮（配置/参数变更）
```

T4–T7 可在 Step 1 subagent 稳定后再细化；当前版本以 **T0–T3 为必做**。

## Step 1 详细说明（基线复现）

### Primary 准备

1. 解析或创建 `{case_dir}/config.md`（格式同 `configuration-tuning-skills/ascend-baseline-generator/config.example.md`）。
2. 确认 `case_dir` 目录存在。
3. 按模板派发 subagent（见 `subagent-prompt-templates.md` § Step 1）；subagent 须按 [`templates/baseline-summary-template.md`](templates/baseline-summary-template.md) 落盘 `baseline-summary.md`。

### Subagent 完成后 Primary 检查

- Read `{case_dir}/baseline/baseline-summary.md`（结构以 `workflows/templates/baseline-summary-template.md` 为准）。
- 确认 handoff 完整：`match_status=matched`、`profile_confirmed=yes`、§3 参考容量、§4 部署引用、§5 服务 host/port 已填。
- 将 **§1–§5 路径与关键字段** 镜像至 `{case_dir}/progress.md` 的「Baseline handoff」节（不复制 §6 附录）。
- 按 §5 `suggested_next_actions` 派发下一环节 subagent 或引导用户执行 Step 2。

## Step 2–5（概要）

| Step | 动作 | 依赖 skill / 工具 |
| --- | --- | --- |
| 2 | 执行 `baseline-launch.sh`，保存启动与运行日志 | 用户环境 NPU + vLLM |
| 3 | `python3 configuration-tuning-skills/serving-cfg-extract/scripts/extract_log_params.py <启动日志>` | serving-cfg-extract |
| 4 | `python3 configuration-tuning-skills/serving-perf-metrics/scripts/parse_log.py <运行日志>` | serving-perf-metrics |
| 5 | 结合 vllm 配置 JSON 与模型特性 JSON 提出调优项 | vllm-ascend-config-extractor, model-feature-extractor |

后续可为 Step 3–5 增加独立 subagent；在此之前 primary 直接 Read 对应 SKILL.md 并执行脚本。
