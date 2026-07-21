# Subagent 派发模板

Primary agent 使用 Task 工具派发时，将 `{占位符}` 替换为实际值。`subagent_type` 必须与 `agents/*.md` frontmatter 中的 `name` 一致。

**前置条件**：Phase 0 已校验用户 `config_md_path`（见 `references/user-config-format.md`）。

---

## Phase 0 — 工作目录配置文件（Primary，非 subagent）

Primary 自行完成，不派发 subagent：

1. 确定 `config_md_path`：用户指定 → 否则工作目录 `deploy-config.md`。
2. Read `workflows/references/user-config-format.md`。
3. **文件不存在** → Read `workflows/templates/deploy-config.template.md`，写入 `{config_md_path}`，提醒用户填写后重新发起，**停止**。
4. **文件存在** → Read 配置文件，确认 `## 基本参数` 7 项齐全且非空；`## 服务化配置` 可有可无。
5. 未填完 → 列出缺失项，提示参考 `configuration-tuning-skills/ascend-baseline-generator/config.example.md`，**停止**。
6. 校验通过 → 记录 `config_md_path`，进入 Phase 1 派发。

---

## Phase 1 — 基线配置生成

```
Task 调用参数：
{
  "description": "基线配置生成",
  "subagent_type": "serving-baseline-reproduce-subagent",
  "prompt": "
scene: baseline-reproduce

执行 Phase 1 · 基线配置生成。

【强制】
- Read skill：configuration-tuning-skills/ascend-baseline-generator/SKILL.md
- Read 角色定义：agents/serving-baseline-reproduce-subagent.md
- Read 配置格式：workflows/references/user-config-format.md

【输入】
- config_md_path: {config_md_path}（Phase 0 已校验；必须含 ## 基本参数）
- case_dir: {case_dir}
- progress_md_path: {progress_md_path}

【配置约束】
- 只从 config_md_path 读取场景参数，不得从对话补充 ## 基本参数 字段
- ## 服务化配置 可选；缺失则 launch 脚本使用 baseline 文档默认值

【输出目录】
- {case_dir}/baseline/

【交付物】
- baseline-launch.sh
- baseline-summary.md
- config.used.md（用户配置文件副本）

【低时延/高吞吐】
双 profile 匹配时，在 baseline-summary.md §6.2 记录对比并向 primary 请求确认。

【完成回报】
向 primary 返回：profile、`baseline-summary.md` 路径；不要粘贴完整 shell 脚本。
  "
}
```

---

## Phase 2 — 服务化调优（占位）

```
Task 调用参数：
{
  "description": "服务化调优占位",
  "subagent_type": "serving-tuning-subagent",
  "prompt": "
scene: serving-tuning-placeholder

执行 Phase 2 · 服务化调优（占位模块）。

【强制】
- Read 角色定义：agents/serving-tuning-subagent.md
- Read 模板：workflows/templates/tuning-status-template.md

【输入】
- case_dir: {case_dir}
- baseline_summary_path: {case_dir}/baseline/baseline-summary.md

【允许操作】
- Read baseline-summary.md §1–§5
- 校验 baseline-summary.md §5 输入清单
- 写入 {case_dir}/tuning/tuning-status.md（status=placeholder）

【禁止操作】
- 不得执行 baseline-launch.sh 或任何部署/压测
- 不得调用 serving-cfg-extract、serving-perf-metrics 等 skill 或运行脚本
- 不得修改 baseline 产物或 vLLM 参数

【完成回报】
向 primary 返回：tuning-status.md 路径、`baseline_summary_valid`、明确说明「Phase 2 占位完成，流水线结束」。
  "
}
```
