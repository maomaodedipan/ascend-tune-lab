# 路径 C · 最佳 PD 配比工作流

由 primary 在选定 **路径 C（最佳 PD 配比）** 后强制 Read 并严格推进。  
顶层路由见 [`primary-workflow.md`](primary-workflow.md)。

**范围**：Phase 0 配置门禁 → Phase 1 配置/环境检查 → Phase 2 AISBench 安装/探测 → Phase 3 部署 → Phase 4 实测配比。

> 用户输入：先定 `workdir`（未指定则 `./workspace`），再在其中放 `pd-deploy-config.md`。格式见 [`references/pd-user-config-format.md`](references/pd-user-config-format.md)。

**与路径 A/B 平级、互斥**：不进入服务化 Phase 0–2，不要求 profiling 路径。进入本路径后禁止改走独立 skill 快路径。

## 触发（进入本路径前已由 primary 确认）

用户明确要做：**最佳 PD 配比 / PD 配比 / Prefill-Decode 配比 / PD ratio** 等。

意图模糊 → primary 先问：独立工具 / A / B / C。

**Skill 调用**：本路径四个 skill 均为 `pipeline-only`。Read `SKILL.md` 时标 `invoke=pipeline`；产物只写 `{workdir}/pd-ratio/`。即使「只检查 / 只安装 / 只部署」也禁止快路径。约定见 `configuration-tuning-skills/README.md`。

## 报告落盘约定（硬要求）

| 类别 | 路径（相对 `workdir`） |
| --- | --- |
| 用户配置 | `pd-deploy-config.md` |
| 进度 | `pd-ratio/progress.md` |
| Phase 1 | `pd-ratio/check/`（report、status、`rendered/`） |
| Phase 2 | `pd-ratio/aisbench/` |
| Phase 3 | `pd-ratio/deploy/` |
| Phase 4 | `pd-ratio/benchmark/` |

## 流程总览

```text
+--------------------------------------------------------------+
| Phase 0 · workdir + pd-deploy-config.md（Primary）            |
|    不存在 → 生成模板并停止；未填完 → 停止                      |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Phase 1 · 配置/环境检查 【serving-pd-config-check-subagent】 |
|    网络改写 + ping/容器/卡 → pd-check-status=passed          |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Phase 2 · AISBench 安装 【serving-aisbench-install-subagent】|
|    探测已有则 skip；否则源码安装；passed|skipped 均可继续     |
|    （部署前完成，避免服务已起却缺压测工具）                     |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Phase 3 · 部署 【serving-pd-deploy-subagent】                 |
|    基线 1P1D = 最小 P 实例 + 最小 D 实例（DP×TP 卡）；剩余卡空闲 |
|    顺序：mooncake_master → P → D → proxy；失败 → 回退 Phase 1 |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Phase 4 · 配比实测 【serving-pd-ratio-benchmark-subagent】   |
|    在最小 1P1D 上测 QPS_P/QPS_D（不必占满整机）               |
|    ratio → 按整机卡数拟合扩容 → 验证部署/e2e → report        |
+--------------------------------------------------------------+
```

## Subagent 映射

| Phase | Subagent | Skill | 状态模板 |
| --- | --- | --- | --- |
| 1 | `serving-pd-config-check-subagent` | `pd-config-env-check`（含 `compute_pd_params` / KV 公式） | [`pd-check-report-template.md`](templates/pd-check-report-template.md) |
| 2 | `serving-aisbench-install-subagent` | `aisbench-install` | [`aisbench-install-report-template.md`](templates/aisbench-install-report-template.md) |
| 3 | `serving-pd-deploy-subagent` | `pd-deploy` | [`pd-deploy-report-template.md`](templates/pd-deploy-report-template.md) |
| 4 | `serving-pd-ratio-benchmark-subagent` | `pd-ratio-benchmark` | [`pd-ratio-report-template.md`](templates/pd-ratio-report-template.md) |

派发模板见 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)。

## 执行规则

### 全局约束

- **路径互斥**：本路径内禁止派发路径 A/B 的 subagent。
- **workdir 默认**：未指定则 `{cwd}/workspace`。
- **配置硬门禁**：无合法 `pd-deploy-config.md` 不得进 Phase 1。
- **产物硬门禁**：下一 Phase 必须验收上一 Phase status（见下表）。
- **AISBench 先于部署**：Phase 2 未 `passed|skipped` 不得进 Phase 3 部署。
- **部署失败回退**：Phase 3 `failed` → 提示用户改配置后 **重跑 Phase 1**（AISBench 已就绪通常不必重装），禁止直接进 Phase 4。
- **流水线终点**：`pd-ratio/benchmark/pd-ratio-report.md` + `pd-ratio-status.md`（`completed`）。

### 实测硬规则（跨 Phase，必须遵守）

| 规则 | 适用 | 说明 |
| --- | --- | --- |
| 交互等价壳 | Phase 1、3 | 容器内用 `bash -ic` / `source ~/.bashrc`；禁止裸 `bash -lc` 导致假阴性缺 `libtransfer_engine.so`；禁止因此改用户 `LD_LIBRARY_PATH` |
| Mooncake 预装 | Phase 1、3 | 只校验、不安装；路径以用户配置为准 |
| 同机共置 DP | Phase 1 | 同 host 拆卡 1P1D：**勿**用 `npu_per_node/tp`；保留用户 `dp_size`/端口/`127.0.0.1`+`lo` |
| **最小实例基线** | Phase 1、3、4 | QPS 实测只拉 **1 个最小 P + 1 个最小 D**（卡数=`DP×TP`）；**禁止**为压测占满整机。空 `npu_ids` 按建议连续切卡，剩余卡空闲。Phase 4 拟合用 **整机卡数**（设备类型×host）作 `avail_npus`，不是基线已分配卡数之和 |
| 一机一容器 | Phase 1 | 未指定/缺失则按 A2/A3 分模板 `docker run`；同机共用；**多机同一 IMAGE**；宿主机只允许 docker* |
| 用户已验证 / 官方回填 | Phase 1、3 | 除允许字段外不改命令；**失败必须停并等用户确认**后再改配置。禁止自行去掉 MTP、加 `spawn`、改 `LD_LIBRARY_PATH` 等试错 |
| AISBench 镜像 | Phase 2 | 国内优先阿里云/清华 PyPI；先探测再安装 |
| numpy 与 vLLM 同容器 | Phase 2→3 | 安装/skip 后须检查 numpy；`2.5+` 钉回 `<2.5`，否则 Prefill 报 Numba ImportError |
| Proxy 冒烟 | Phase 3/4 | 以 `/v1/chat/completions` 为准；`/v1/models` 404 可忽略；健康检查勿依赖容器内 `ss` |
| Phase 4 配置 | Phase 4 | 必须含 `summarizer`；Synthetic 定长；先 P（out=1）后 D（stable）；**P/D concurrency 可不同** |
| D 测 prefix cache | Phase 4 | **D 测与验证 e2e 必须 100% 共享前缀**：`PrefixLen = RequestSize`，Prefill 临时 `--enable-prefix-caching`；P 测 `PrefixLen = 0`。禁止用无 prefix cache 的 D 点算 `QPS_D` |
| 最大并发 | Phase 4 | 扫点撞上 `--max-num-seqs` 且本侧未饱和、SLO 仍合规 → **允许上调该侧最大并发**后继续扫；禁止把截断当峰值。仍禁止改 MTP / spawn / `LD_LIBRARY_PATH` |
| TTFT/TPOT | Phase 0→4 | **开场询问**；默认 TTFT 不限、TPOT=50ms；**P 只看 TTFT、D 只看 TPOT**；P/D 并发可不同；须按阶梯扫点证明饱和（P：QPS 平台+TTFT 单涨；D：TPOT 平台+TTFT 单涨）；缺前端须补测；必要时继续 64/128 并上调 `max-num-seqs` |
| 多次实测留痕 | Phase 4 | 每一轮 P/D（含失败）写入 `attempts/` 并在报告中完整同步；禁止只留最终一次 |
| 超长上下文耗时 | Phase 4 | 墙钟由 TTFT 主导（128k 可达分钟～数十分钟）；≥64k 先告知用户；长任务用 nohup+轮询 |
| 配比场景绑定 | Phase 4 | ratio 仅对当前 in/out 有效；换序列长度必须重测 |
| 资源可达+验证 | Phase 4 | 建议配比后 fit；可达则按建议**验证**。验证=各拓扑独立求双 SLO 最大吞吐（并发可不同），再比单卡。未提升则推荐并切回 1P1D |

### 验收门禁

| 进入 | 要求 |
| --- | --- |
| Phase 2 | `check/pd-check-status.md` = `passed` |
| Phase 3 | `aisbench/aisbench-install-status.md` = `passed` 或 `skipped` |
| Phase 4 | `deploy/pd-deploy-status.md` = `passed`（AISBench 已在 Phase 2 就绪） |

### TaskList 骨架

```text
C0. 确定 workdir；定位/生成/校验 pd-deploy-config.md；询问 TTFT/TPOT（缺省：TTFT 不限、TPOT=50ms）
C1. 派发 serving-pd-config-check-subagent；验收 pd-check-status=passed
C2. 派发 serving-aisbench-install-subagent；验收 passed|skipped
C3. 派发 serving-pd-deploy-subagent；失败则回退 C1
C4. 派发 serving-pd-ratio-benchmark-subagent；验收 pd-ratio-status=completed
    （SLO 已满足 + capacity-fit + 验证 e2e/单卡对比；终态推荐=单卡最佳，未提升则 1P1D）
C5. Primary 交付终态报告路径，路径 C 结束
```

## Phase 0 · 工作目录 + 配置文件（Primary）

1. 确定 `workdir`（用户指定 → 否则 `mkdir -p ./workspace`）。
2. `config_md_path` 默认 `{workdir}/pd-deploy-config.md`。
3. 不存在 → Read [`templates/pd-deploy-config.template.md`](templates/pd-deploy-config.template.md) 写入并停止。
4. 存在 → 按 [`references/pd-user-config-format.md`](references/pd-user-config-format.md) 校验模型/设备/序列长度等必填；拉起命令可空（Phase 1 从[官方模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/)回填）。
5. **TTFT / TPOT**：向用户询问限制；用户提供则写入配置；仍不提供 → 默认 **TTFT 不设限制**、**TPOT=50ms**，写入配置并在 `progress.md` 注明 `slo_source=default`。
6. 通过 → 创建 `pd-ratio/`，写 `progress.md`，进入 Phase 1。

## Skill 套件（全部 `pipeline-only`）

- `pd-config-env-check`
- `aisbench-install`
- `pd-deploy`
- `pd-ratio-benchmark`
