# Subagent 派发模板

Primary agent 使用 Task 工具派发时，将 `{占位符}` 替换为实际值。`subagent_type` 必须与 `configuration-tuning-agents/agents/*.md` frontmatter 中的 `name` 一致。

---

## Step 1 — 性能基线复现

```
Task 调用参数：
{
  "description": "性能基线复现",
  "subagent_type": "serving-baseline-reproduce-subagent",
  "prompt": "
scene: baseline-reproduce

执行 vLLM-Ascend 性能基线复现（Step 1）。

【强制】
- Read 并严格遵循 skill：configuration-tuning-skills/ascend-baseline-generator/SKILL.md
- Read 本角色定义：agents/serving-baseline-reproduce-subagent.md（或 configuration-tuning-agents/agents/...）

【输入】
- config_md_path: {config_md_path}
- case_dir: {case_dir}
- progress_md_path: {progress_md_path}

【输出目录】
- {case_dir}/baseline/

【交付物】
- baseline-launch.sh
- baseline-summary.md（Baseline Reproduce Handoff；按 workflows/templates/baseline-summary-template.md；可参考 baseline-summary-example.md）
- config.used.md

【低时延/高吞吐】
若两个 profile 均有有效匹配，在 baseline-summary.md §6.2 记录对比；向 primary 说明需确认 profile。profile_confirmed=yes 后再定稿 launch 脚本，并将 selected_profile 写入 §2。

【完成回报】
向 primary 返回：profile、handoff 路径、§5 suggested_next_actions；不要粘贴完整 shell 脚本到对话。
  "
}
```

填写结构与字段说明见 `workflows/templates/baseline-summary-template.md`。该文件是 **下一环节 subagent 的输入**，不是全流程输出。

---

## Step 2+（预留）

下一环节 subagent 进场须 Read `{case_dir}/baseline/baseline-summary.md`，至少消费 §1–§5。

```
Task 调用参数（示例骨架）：
{
  "description": "服务化调优下一环节",
  "subagent_type": "<待定>",
  "prompt": "
scene: serving-tuning-next

【输入 — 必读 handoff】
- baseline_summary_path: {case_dir}/baseline/baseline-summary.md
- launch_script_path: 从 summary §4 读取
- service_host / service_port: 从 summary §5 读取
- ref_max_concurrency / perf_goal_optional: 从 summary §3、§5 读取

【约束】
- 若 profile_confirmed != yes 或 match_status != matched，停止并向 primary 报错
  "
}
```
