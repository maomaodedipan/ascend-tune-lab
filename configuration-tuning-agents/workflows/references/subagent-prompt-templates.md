# Subagent 派发模板

Primary agent 使用 Task 工具派发时，将 `{占位符}` 替换为实际值。`subagent_type` 必须与 `agents/*.md` frontmatter 中的 `name` 一致。

顶层路由：`workflows/primary-workflow.md`（快路径 / 路径 A 服务化调优 / 路径 B Profiling / 路径 C 最佳 PD 配比，互斥）。Skill 分类见 `configuration-tuning-skills/README.md`。

**快路径**：不派发 subagent；本文件模板不适用。

**路径 A 前置**：Phase 0 已确定 `workdir` 并校验 `config_md_path`（见 `references/user-config-format.md`）。  
**路径 B**：不要求 deploy-config；见下方「Profiling 分析」。路径 A 模板中 **禁止**派发 profiling / PD 配比 subagent。  
**路径 C**：见下方「路径 C · 最佳 PD 配比」；使用 `pd-deploy-config.md`，**禁止**混跑 A/B。

各模板中 Read `SKILL.md` 时一律标 **`invoke=pipeline`**。`pipeline-only` 禁止当独立工具执行。`dual` skill（如 `op-mfu-calculator`）在流水线内产物写该路径约定目录，禁止写 `{workdir}/skills/`。

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
  1. Read configuration-tuning-skills/msprof-mcp-setup/SKILL.md（invoke=pipeline）
  2. 按技能安装（Linux/WSL：scripts/bootstrap-msprof-mcp.sh；Windows：pip）
  3. 提示用户 Reload Window / 重启 IDE
  4. **停止分析主流程**，回报 setup 状态；不得假装已完成 profiling
- 仅当 MCP ready 后继续下列步骤

【MCP ready 后】
- 按场景 Read skill：configuration-tuning-skills/<skill>/SKILL.md（invoke=pipeline）
  （data-validation / db-explorer / computation / communication / schedule /
   msprof-analyze-cli / compare-analyzer / cluster-fast-slow-rank 为 pipeline-only；
   msprof-mcp-setup / github-raw-fetch 为 pipeline-only；
   op-mfu 为 dual，此处仍 invoke=pipeline）
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
- Read skill：configuration-tuning-skills/ascend-baseline-generator/SKILL.md（invoke=pipeline）
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
- Read 入口 skill：configuration-tuning-skills/serving-parallel-strategy-tuning/SKILL.md（invoke=pipeline）
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

---

## 路径 C · 最佳 PD 配比

**仅当**用户明确要做最佳 PD 配比 / PD 配比 / Prefill-Decode 配比 / PD ratio。  
详文见 `workflows/pd-ratio-workflow.md`。Primary 逐步派发，**验收上一 Phase status 后再派下一 Phase**。

### Phase 0 — PD 配置（Primary，非 subagent）

1. 确定 `workdir`（默认 `./workspace`）。
2. `config_md_path` 默认 `{workdir}/pd-deploy-config.md`。
3. 不存在 → 写入 `workflows/templates/pd-deploy-config.template.md` 并停止。
4. 存在 → 按 `references/pd-user-config-format.md` 校验模型/设备/序列长度等；缺失则停止。
5. **询问用户 TTFT / TPOT 限制**；未提供则写入默认：TTFT=不限、TPOT=50ms（`progress.md` 注明）。
6. 通过 → 进入 Phase 1。

### Phase 1 — PD 配置/环境检查

```
Task 调用参数：
{
  "description": "PD配置环境检查",
  "subagent_type": "serving-pd-config-check-subagent",
  "prompt": "
scene: pd-config-env-check

执行路径 C · Phase 1 · PD 配置与环境检查。

【强制】
- Read 角色定义：agents/serving-pd-config-check-subagent.md
- Read skill：configuration-tuning-skills/pd-config-env-check/SKILL.md（invoke=pipeline）
- Read 模板：workflows/templates/pd-check-report-template.md
- Read 配置格式：workflows/references/pd-user-config-format.md
- **一机一容器**：container_name 未填或不存在 → Agent 按 A2/A3 官方分 tab 模板 docker run（见 GLM5 文档 / ensure_host_container.sh）；同 host 共用；禁止同机 P/D 各建一容器
- **宿主机只允许 docker***（inspect/run/start/exec/cp/logs/pull）；禁止宿主机 npu-smi/装包/改系统；业务一律 docker exec 进容器
- A2：优先 `v0.23.0rc1`→`v0.22.1rc1` + davinci0-7；A3：优先 `v0.23.0rc1-a3`→`v0.22.1rc1-a3` + davinci0-15；可用 docker_image 固定；**多机必须同一 IMAGE**（先解析一次再对各机 --image）；--name 必须按环境改
- docker run 必须 `--privileged --security-opt label=disable`（否则 CANN realpath EPERM → SpaceRegistry/ZerosLike 361001）
- 禁止改非网络/非允许 KV 字段；禁止进路径 A/B；禁止安装 Mooncake
- 流程：拉起命令缺失则查官方模型教程回填 → ensure 容器 → compute_pd_params → validate_pd_config → render_pd_launch
- Read references/official-model-launch.md；优先教程 PD 分离章 + 匹配 A2/A3；无匹配模型则 failed，禁止编造
- Mooncake 校验须交互等价壳（bash -ic / source ~/.bashrc）；禁止因非交互缺库改 LD_LIBRARY_PATH
- 同机共置 1P1D：勿用 npu_per_node/tp；保留用户 dp_size、端口、127.0.0.1/lo
- **最小 P/D 实例 size = 拉起命令 DP×TP**；角色 npu_count 须对齐
- **QPS 基线禁止占满整机**：只分配 1 个最小 P + 1 个最小 D；npu_ids 空则用 pd-params 的 suggested_*_npu_ids；剩余卡空闲。禁止把官方「整机 DP」或半机硬拆写进基线
- 官方回填：kv_role/connector 可取 PD 分离章；**TP/DP 与 VISIBLE_DEVICES 取单实例命令**（如 Qwen3.6 §5.1 TP=2 DP=1），禁止把 §5.2 满机 DP 缩放到本机当实例 size
- 用户已验证 / 官方回填命令跑不起来 → 停止并等用户确认；禁止擅自去掉 MTP、加 spawn、改 LD_LIBRARY_PATH 或其它业务参数试错

【输入】
- workdir: {workdir}
- config_md_path: {config_md_path}

【输出】
- {workdir}/pd-ratio/check/pd-check-report.md
- {workdir}/pd-ratio/check/pd-check-status.md
- {workdir}/pd-ratio/check/rendered/

【完成回报】
status、报告路径、阻塞项摘要、rendered 目录。
  "
}
```

### Phase 2 — AISBench 安装（部署前）

```
Task 调用参数：
{
  "description": "AISBench安装",
  "subagent_type": "serving-aisbench-install-subagent",
  "prompt": "
scene: aisbench-install

执行路径 C · Phase 2 · AISBench 探测/源码安装（须在部署之前完成）。

【强制】
- Read 角色定义：agents/serving-aisbench-install-subagent.md
- Read skill：configuration-tuning-skills/aisbench-install/SKILL.md（invoke=pipeline）
- Read 模板：workflows/templates/aisbench-install-report-template.md
- 验收 Phase 1 pd-check-status.md=passed
- 安装目标来自 pd-deploy-config / Phase 1（优先 Prefill 容器）；不依赖 deploy 报告
- 已安装则 skip；成功判据 ais_bench -h
- 国内网络默认阿里云/清华 PyPI；默认源卡住勿长时间干等
- 与 vLLM 同容器：安装/skip 后检查 numpy；2.5+ 须钉回 <2.5，写入报告（避免 Numba 导致 Phase 3 起不来）
- failed 则不得进入 Phase 3 部署

【输入】
- workdir: {workdir}
- 安装目标 host/container（来自配置表或用户指定）

【输出】
- {workdir}/pd-ratio/aisbench/aisbench-install-report.md
- {workdir}/pd-ratio/aisbench/aisbench-install-status.md

【完成回报】
status（passed|skipped|failed）、ais_bench 路径。
  "
}
```

### Phase 3 — PD 部署

```
Task 调用参数：
{
  "description": "PD分离部署",
  "subagent_type": "serving-pd-deploy-subagent",
  "prompt": "
scene: pd-deploy

执行路径 C · Phase 3 · PD 部署。

【强制】
- Read 角色定义：agents/serving-pd-deploy-subagent.md
- Read skill：configuration-tuning-skills/pd-deploy/SKILL.md（invoke=pipeline）
- Read 模板：workflows/templates/pd-deploy-report-template.md
- 验收 {workdir}/pd-ratio/check/pd-check-status.md 必须为 passed
- 验收 {workdir}/pd-ratio/aisbench/aisbench-install-status.md 必须为 passed|skipped
- 启动命令仅来自 {workdir}/pd-ratio/check/rendered/
- 启动顺序：mooncake_master（若 required）→ Prefill → Decode → Proxy
- **只拉最小实例**：P/D 可见卡 = DP×TP；禁止为「把卡用满」再起额外 rank 或改大 DP
- 容器内必须交互等价壳（bash -ic / source ~/.bashrc）；禁止裸 bash -lc
- Proxy 须为真实脚本；PROXY_TYPE 按配置，禁止凭 connector 猜
- 健康检查以 POST /v1/chat/completions 为准；GET /v1/models 404 可忽略
- 容器内勿依赖 ss；master 用 pgrep，P/D 用 /v1/models；加载等待须留足（可达十余分钟）
- 若日志 Numba/numpy 2.5：钉回 numpy<2.5 后重试，勿改用户 LD_LIBRARY_PATH
- 失败则 rollback_to_phase1=true，不得进入 Phase 4；停止并等用户确认。禁止自行去掉 MTP、加 spawn、改 LD_LIBRARY_PATH 或其它业务参数后重试

【输入】
- workdir: {workdir}

【输出】
- {workdir}/pd-ratio/deploy/pd-deploy-report.md
- {workdir}/pd-ratio/deploy/pd-deploy-status.md

【完成回报】
status、proxy_base_url（成功时）、失败诊断与是否回退 Phase 1。
  "
}
```

### Phase 4 — PD 配比实测

```
Task 调用参数：
{
  "description": "PD配比实测",
  "subagent_type": "serving-pd-ratio-benchmark-subagent",
  "prompt": "
scene: pd-ratio-benchmark

执行路径 C · Phase 4 · AISBench 实测与最佳 PD 配比计算。

【强制】
- Read 角色定义：agents/serving-pd-ratio-benchmark-subagent.md
- Read skill：configuration-tuning-skills/pd-ratio-benchmark/SKILL.md（invoke=pipeline）
- Read 模板：workflows/templates/pd-ratio-report-template.md
- 验收 Phase 2 aisbench passed|skipped；Phase 3 deploy passed
- AISBench 配置必须含 summarizer；定长用 Synthetic；VLLMCustomAPIChat + stream=True 打 proxy
- Proxy 冒烟用 /v1/chat/completions；忽略 /v1/models 404
- SLO：读配置 TTFT/TPOT；空则 TTFT 不限、TPOT=50ms
- **分侧约束**：P 只校验 TTFT；D 只校验 TPOT；禁止用 TPOT 判 P、用 TTFT 判 D
- **P/D concurrency 可不同**；禁止强制对齐；禁止因 D 改并发而重跑 P
- **饱和扫点（硬）**：推荐阶梯 2→4→8→16→32，必要时 64/128；禁止单点宣称最大吞吐；缺低并发前端必须补测
- **最大并发**：撞上本侧 `--max-num-seqs` 且未饱和、本侧 SLO 仍合规 → 上调该侧 `max-num-seqs` 后继续扫；禁止把截断点当 selected；仍禁止改 MTP/spawn/LD_LIBRARY_PATH
- **P 饱和**：out=1 无有效 TPOT；须见「低并发 TTFT/QPS 未峰 → 峰值 → QPS 平台且 TTFT 单涨」
- **D 饱和**：须见「TTFT/TPOT 都偏小 → 同升 → TPOT 平台且仅 TTFT 涨」；仅 TPOT 作门禁
- **D 测 prefix cache 100%**：`PrefixLen = RequestSize`；Prefill 临时 `--enable-prefix-caching`；P 测 `PrefixLen = 0`；验证 e2e 与 D 测同口径
- 本侧不满足 → 只在本侧重测/补点；禁止用超约束点算配比；concurrency=1 仍失败则 status=failed
- 每一轮立刻写入 attempts/；summary 含按 concurrency 排序的 P/D 曲线；报告含饱和判读
- ≥64k 或预计很长：先告知用户耗时（TTFT 主导）；长任务远端后台+轮询
- 先完成 P 扫点再 D；计算 ratio=QPS_P/QPS_D；配比与当前 in/out 绑定不可复用
- **资源可达（硬）**：`avail_npus` = 设备类型整机卡数 × host 数（`pd-params.host_avail_npus`），**不是**基线 P/D 行 npu_count 之和
  - 基线 QPS 在最小 1P1D 上测；拟合后再决定扩多少实例
  - feasible=true → 按建议配比部署并做验证 e2e
  - feasible=false → 按最大可达配比部署并验证；报告明示降级
  - 无法扩出基线 → 可只做基线 e2e 对照并写明原因
- **验证目标**：各拓扑在相同业务 in/out 下求 **TTFT+TPOT 合规的最大吞吐**（concurrency **可不同**），再比单卡 QPS；基线 `npus` = 实际占用的最小实例卡，不含空闲卡
- **终态推荐（硬）**：以单卡吞吐最佳为准。`per_npu_improved=true` → 推荐验证拓扑；否则推荐并切回 **1P1D**。写 `recommend.json`
- 指标：JSON 取 throughput；CSV 取 TTFT/TPOT（stable|total）

【输入】
- workdir: {workdir}
- config_md_path: {config_md_path}
- proxy_base_url: {proxy_base_url}

【输出】
- {workdir}/pd-ratio/benchmark/attempts/
- {workdir}/pd-ratio/benchmark/p-qps-result.json
- {workdir}/pd-ratio/benchmark/d-qps-result.json
- {workdir}/pd-ratio/benchmark/ratio-calc.json
- {workdir}/pd-ratio/benchmark/capacity-fit.json
- {workdir}/pd-ratio/benchmark/recommend.json
- {workdir}/pd-ratio/benchmark/verify/
- {workdir}/pd-ratio/benchmark/pd-ratio-report.md
- {workdir}/pd-ratio/benchmark/pd-ratio-status.md

【完成回报】
QPS_P、QPS_D、ratio、公式建议 N_P/N_D、验证候选、**终态推荐**、feasible、per_npu_improved、attempt 次数与路径、终态报告路径。
  "
}
```
