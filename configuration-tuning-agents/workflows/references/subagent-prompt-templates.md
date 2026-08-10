# Subagent 派发模板

Primary agent 使用 Task 工具派发时，将 `{占位符}` 替换为实际值。`subagent_type` 必须与 `agents/*.md` frontmatter 中的 `name` 一致。

顶层路由：`workflows/primary-workflow.md`（路径 A 服务化调优 / 路径 B Profiling，平级互斥）。

**路径 A 前置**：Phase 0 已确定 `workdir` 并校验 `config_md_path`（见 `references/user-config-format.md`）。  
**路径 B**：不要求 deploy-config；见下方「Profiling 分析」。路径 A 模板中 **禁止**派发 profiling subagent。

---

## Profiling 分析（路径 B）

**仅当同时满足**：① 用户明确要做 profiling 分析；② 已给出本地 `profiler_path`。  
**禁止**在路径 A（Phase 0/1/2）中途触发；详文见 `workflows/profiling-analysis-workflow.md`。

```
Task 调用参数：
{
  "description": "Profiling 性能分析",
  "subagent_type": "serving-profiling-analysis-subagent",
  "prompt": "
scene: profiling-analysis

执行 Ascend NPU Profiling 分析（路径 B；不进入服务化 Phase 0–2）。

【强制】
- Read 角色定义：agents/serving-profiling-analysis-subagent.md
- Read 工作流：workflows/profiling-analysis-workflow.md
- Read 工具表：workflows/references/msprof-mcp-tools.md
- 禁止执行服务化 Phase 0–2 / deploy-config / baseline / tuning

【步骤 0 · 首次安装硬门禁】
- GetMcpTools 检查 msprof-mcp / user-msprof-mcp 是否 ready
- 若未安装/未连接：
  1. Read configuration-tuning-skills/msprof-mcp-setup/SKILL.md
  2. 按技能安装（Linux/WSL：scripts/bootstrap-msprof-mcp.sh；Windows：pip）
  3. 提示用户 Reload Window / 重启 IDE
  4. **停止分析主流程**，回报 setup 状态；不得假装已完成 profiling
- 仅当 MCP ready 后继续下列步骤

【MCP ready 后】
- 按场景 Read skill：configuration-tuning-skills/<skill>/SKILL.md
  （data-validation / db-explorer / computation / communication / schedule /
   msprof-analyze-cli / cluster-fast-slow-rank / op-mfu / github-raw-fetch）
- 优先 CallMcpTool；server 名以 GetMcpTools 为准
- 单次工具失败才可局部退化为文件读取，并说明原因

【输入】
- profiler_path: {profiler_path}（用户明确本地路径；禁止自行递归搜索）
- workdir: {workdir}（默认 ./workspace）
- output_dir: {output_dir}（默认 {workdir}/profiling）
- focus: {focus}（可选：计算/通信/调度/集群/全面）

【交付物】
- MCP 未就绪时：setup 结果说明（binary/配置路径、待 Reload）
- MCP ready 后：{output_dir}/profiling-report.md

【完成回报】
向 primary 返回：setup 状态；若已分析则附结论摘要、profiling-report.md 路径、关键证据/MCP 工具说明。
  "
}
```

---

## Phase 0 — 工作目录 + 配置文件（Primary，非 subagent）

Primary 自行完成，不派发 subagent（**本段仅服务化**）：

1. 确定 `workdir`：用户指定 → 否则 `mkdir -p ./workspace` 并使用该目录；告知用户。
2. 确定 `config_md_path`：用户指定 → 否则 `{workdir}/deploy-config.md`。
3. Read `workflows/references/user-config-format.md`。
4. **文件不存在** → Read `workflows/templates/deploy-config.template.md`，写入 `{config_md_path}`，提醒用户填写后重新发起，**停止**。
5. **文件存在** → Read 配置文件，确认 `## 基本参数` 7 项齐全且非空；`## 服务化配置` / `## SLO约束` 可有可无。
6. 未填完 → 列出缺失项，提示参考 `configuration-tuning-skills/ascend-baseline-generator/config.example.md`，**停止**。
7. **下载模型 config（硬门禁）** → 运行  
   `download_modelscope_config.py --workdir {workdir} --config {config_md_path}`  
   → 产出 `{workdir}/model_config.json`。  
   **失败** → 展示 warning，要求用户手动放到该路径（可选补充 `ModelScope模型ID`），**停止**。
8. 校验通过且 config 就绪 → 记录 `workdir`、`config_md_path`、`model_config_path`，进入 Phase 1 派发。

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
- workdir: {workdir}（Phase 0 已确定；默认 ./workspace）
- config_md_path: {config_md_path}（Phase 0 已校验；必须含 ## 基本参数）
- model_config_path: {workdir}/model_config.json（Phase 0 已从 ModelScope 下载或用户手供）
- case_dir: {case_dir}（须在 workdir 内）
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

## Phase 2 — 并行策略调优

```
Task 调用参数：
{
  "description": "并行策略调优",
  "subagent_type": "serving-tuning-subagent",
  "prompt": "
scene: serving-parallel-strategy-tuning

执行 Phase 2 · 离线并行策略调优。

【强制】
- Read 角色定义：agents/serving-tuning-subagent.md
- Read 入口 skill：configuration-tuning-skills/serving-parallel-strategy-tuning/SKILL.md
- Read **唯一** Phase 2 模板：workflows/templates/tuning-process-template.md
  （同时定义中间产物 tuning-process.* 与汇总 tuning-status.md）

【输入】
- workdir: {workdir}
- case_dir: {case_dir}（须在 workdir 内）
- baseline_summary_path: {case_dir}/baseline/baseline-summary.md
- config_md_path: {config_md_path}

【步骤】
1. 校验 baseline-summary.md §5
2. 解析 ## SLO约束；缺失则询问用户；仍空则默认 TPOT=50ms、TTFT 不限
3. 运行 orchestrate_parallel_tuning.py --workdir {workdir}（clone 到 {workdir}/repos/）
   - clone 失败：把 warning / repos-clone.warning.md 原文回报用户，要求手动放置后重试，**停止**
   - 网络不可用且已有本地仓可用 --skip-clone；禁止静默跳过缺失仓库
4. 验收 tuning/tuning-process.md + tuning-process.json（须含并行策略 / KV / SLO 过程值）
5. 验收 tuning/tuning-status.md 与四个 JSON

【禁止操作】
- 不得执行 baseline-launch.sh 或任何部署/压测
- 不得修改 baseline-launch.sh / baseline-summary.md

【完成回报】
向 primary 返回：
- tuning-process.md 路径（中间过程产物）
- tuning-status.md 路径
- 推荐 DP/TP/EP、max_concurrency_slo、perf_db_source、used_real_csv
- 若 used_real_csv=false：必须附上 perf_db_fallback_reasons（为何未用真实 CSV）
- 摘要：并行组合数、各组合 max_concurrency_memory / max_concurrency_slo
  "
}
```
