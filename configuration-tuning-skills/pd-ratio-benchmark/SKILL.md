---
name: pd-ratio-benchmark
description: >-
  Run AISBench tests to measure Prefill-side and Decode-side QPS under SLO, then
  compute best PD instance ratio (Path C Phase 4). Use after aisbench-install.
---

# pd-ratio-benchmark

路径 C · Phase 4。用 AISBench 实测 QPS_P / QPS_D，计算最佳 PD 配比；按集群**整机**卡数/机数拟合可达拓扑并做验证 e2e（单卡吞吐对比），落盘终态报告。

**QPS 扫点在最小 1P1D 上完成**（每侧实例卡数 = `DP×TP`），测试阶段不要求、也不应使用全部 NPU。拟合扩容才使用整机 `avail_npus`。

## SLO 约束（硬门禁）

配比压测前必须已确定 TTFT / TPOT 限制（Phase 0 写入 `pd-deploy-config.md`）：

| 字段 | 用户已提供 | 未提供时的默认 |
| --- | --- | --- |
| **TTFT** | 按用户值（ms）校验 | **不设限制**（不校验 TTFT） |
| **TPOT** | 按用户值（ms）校验 | **50ms** |

### 分侧校验（禁止混用）

| 测项 | 只关心的约束 | 不关心 |
| --- | --- | --- |
| **P 测**（`output_len=1`） | **仅 TTFT**（若有限制） | **不校验 TPOT**（且 P 侧无有效 TPOT） |
| **D 测**（业务输出长度 + stable） | **仅 TPOT**（用户值或默认 50ms） | **不校验 TTFT** |

指标取实测 **Average**（报告中同时保留 P99 等供参考）。

## 并发与饱和扫点（硬要求）

**P 与 D 的 concurrency / request_rate 可以不同**；禁止强制对齐，禁止因 D 降并发而重跑 P。

### 推荐并发阶梯

默认按倍增扫点（可按机器能力微调，但须覆盖「低 → 峰 → 过饱和」）：

`2 → 4 → 8 → 16 → 32`（必要时继续 `64 → 128…`）

- **禁止**只测单个并发点就宣称最大吞吐。
- **禁止**把「客户端 concurrency 撞上服务端 `--max-num-seqs`」当成饱和或 selected。
- 报告中须按 concurrency **排序**给出本侧曲线（不必按 attempt 时间序解读饱和）。

### 必要时调整最大并发（`--max-num-seqs`）

扫点以**饱和曲线**为准，不以启动命令里的官方/回填 `max-num-seqs` 为上限。

**何时必须上调**（本侧独立判断，禁止为对齐另一侧而改）：

1. 当前客户端 concurrency **已达到**该实例 `--max-num-seqs`；且
2. 本侧约束仍满足（P：TTFT；D：TPOT）；且
3. QPS **仍在上升**（未出现本侧过饱和：P 为 QPS 平台+TTFT 单涨；D 为 TPOT 平台+QPS 增益可忽略，或 TPOT 已超限）。

则：**允许**提高该侧 `--max-num-seqs`（建议倍增，至少覆盖下一档 concurrency），重启**该侧**实例后继续扫点。这是 Phase 4 允许的字段，**不必**再问用户；仍禁止改 MTP / `spawn` / `LD_LIBRARY_PATH` / TP/DP / 端口 / 量化等其它启动参数。

操作约束：

- 同步写入 `pd-deploy-config.md` 与 `rendered/` 对应 P 或 D 脚本；验证扩实例时额外 D/P 用**同一**新值。
- 只停并重启被改的那一侧（`docker exec` + `bash -ic`）；对侧与 Mooncake 尽量保持。
- 历史 attempt **全部保留**；报告写明原值 → 新值及哪几次 attempt 之后生效。
- 上调后启动失败 / OOM：停止或退回上一档已成功的 `max-num-seqs`，写入报告；不得为此改 MTP 等其它参数试错。
- 已真正过饱和则**不要**再抬 `max-num-seqs`。

### P 测扫点

1. 若有 TTFT 限制：只保留 TTFT 合规点；在合规集合内取 **QPS 最大** 点为 `QPS_P`。超 TTFT → 降并发。
2. **若无 TTFT 限制**：从低并发扫到高并发，直到确认吞吐饱和，取 **QPS 最大** 点为 `QPS_P`。
3. concurrency=1 仍超 TTFT（仅当有限制时）→ 该侧 `slo_met=false`，整体可 `failed`。

**P 侧饱和判据（`output_len=1`，无有效 TPOT）：**

| 阶段 | 期望现象 |
| --- | --- |
| 低并发（须含，如 c=2） | TTFT 相对偏小；QPS **尚未**到峰（或明显低于峰值） |
| 峰值 | QPS 最大（选作 `QPS_P`） |
| 过饱和 | QPS **不再升高**（持平或略降），**TTFT 继续明显增大** |

> 不得用 TPOT 描述 P 饱和。P 的「最大吞吐已取得」= 曲线同时具备前端（低并发）与过饱和（QPS 平台 + TTFT 单涨）。缺前端须**补测**更低并发（如 c=2）。

### D 测扫点

1. **只按 TPOT** 约束选点；超 TPOT → 降 concurrency。
2. 在 TPOT 合规前提下扫到吞吐饱和，取 **QPS 最大** 合规点为 `QPS_D`。
3. concurrency=1 仍超 TPOT → `failed`。
4. **禁止**用 TTFT 判定 D 成败；**禁止**要求 `concurrency_P == concurrency_D`。
5. **Prefix cache = 100%（硬）**：D 测必须让请求共享**全部**输入前缀，使服务端 Prefix cache hit rate 趋近 100%。否则 Prefill 计算会污染 D 侧 QPS，测到的不是 Decode 吞吐。
   - AISBench Synthetic tokenid：`PrefixLen = RequestSize`（AISBench 允许闭区间 `[0, RequestSize]`；相等即 100% 共享前缀）。P 测保持 `PrefixLen = 0`。
   - D 扫点期间：Prefill 若为 `--no-enable-prefix-caching`，**临时**改为 `--enable-prefix-caching` 后重启 **Prefill**（必要时 Decode 同步开启，否则 cache 无法命中）。MTP / spawn / `LD_LIBRARY_PATH` / TP/DP / 端口 / 量化仍禁止改。
   - D 扫点与验证 e2e 使用同一套 100% prefix（`PrefixLen = RequestSize` + Prefill `--enable-prefix-caching`），以便单卡对比与 `QPS_D` 同口径。P 测保持 `PrefixLen = 0`。全部完成后可将 prefix-caching 恢复为官方原值。
   - 报告须写明 D 测 `PrefixLen/RequestSize`、Prefill 是否临时开启 prefix-caching，以及 vLLM 日志中的 Prefix cache hit rate（若有）。

**D 侧饱和判据（完整 TTFT + TPOT 叙事，须在报告中体现）：**

| 阶段 | 期望现象 |
| --- | --- |
| 低并发 | **TTFT 与 TPOT 都偏小**；QPS 未到峰 |
| 上升段 | TTFT、TPOT 随并发**一同增大**，QPS 上升 |
| 饱和段 | **TPOT 基本不变**（平台），**仅 TTFT 继续明显增大**，QPS 持平或增益可忽略 |

> 若只有高并发点、缺少「两者都偏小」的前端，须**补测**更低并发，直到能讲清上述全流程，再选定 `QPS_D`。

### 不满足则必须重测（禁止用超约束点算配比）

1. 各自在本侧约束下重测 / 补点，直到 `slo_met=true` 且饱和曲线可解释。
2. **禁止**在任一侧 `slo_met=false` 时计算 ratio / 写 `completed`。
3. 不得擅自放宽默认值（尤其默认 TPOT=50ms）。

### 多次测试结果必须全部同步落盘（硬要求）

每次 P/D 实测（含失败与成功、含吞吐扫点与补测）都要立刻落盘，**禁止只保留最终一次**：

1. **每次跑完立刻写** `attempts/attempt_NNN_{p|d}.json`（`NNN` 从 `001` 递增），字段至少含：attempt、side(`p`|`d`)、concurrency、request_rate、qps、ttft_ms、tpot_ms、slo_met、slo_fail_reason、raw_log_path、timestamp。
2. **追加** `attempts/attempts.jsonl`（一行一次尝试；`attempt` 为时间序，P/D 可交错）。
3. **更新** `attempts/attempts-summary.md`：除时间序表外，**必须**另附按 concurrency 排序的 **P 曲线表** 与 **D 曲线表**（标注饱和阶段与 `selected`）。
4. 最终采用的点另写（或覆盖）`p-qps-result.json` / `d-qps-result.json`，带 `attempt_id`；两侧 `max_concurrency` **可不同**。
5. 终态报告 **§ 重测轨迹** 含全部 attempt，并含 P/D **饱和判读**小节。
6. 向用户/primary 回报时同步给出 attempt 目录路径与次数。

## 方法

1. **确定序列长度与 SLO**：来自 `pd-deploy-config.md`（含上文默认规则）。
2. **P 节点 QPS**：输出长度 **1**；按上文 P 侧扫点与饱和判据得到 **QPS_P**。
3. **D 节点 QPS**：业务输出长度；稳态汇总；按上文 D 侧扫点与饱和判据（**仅 TPOT 门禁**）得到 **QPS_D**。并发**不必**与 P 相同。

```bash
ais_bench --models <model_task> --datasets <dataset_task> \
  --summarizer stable_stage --mode perf
```

或在配置文件内使用 `StablePerfMetricCalculator`（等价 steady-stage）。  
得到系统 QPS ≈ **QPS_D**。参考：[Steady-stage testing](https://ais-bench-benchmark.readthedocs.io/en/latest/advanced_tutorials/stable_stage.html)。

4. **配比**（仅当 P/D 均 `slo_met=true` 且饱和曲线可解释）：

- `ratio = QPS_P / QPS_D`
- `N_D / N_P = QPS_P / QPS_D`（建议 `N_D : N_P ≈ QPS_P : QPS_D`）

5. **资源可达性 → 验证部署与实测**（硬要求，见下节）：配比算出后必须检查集群能否拉起建议拓扑；能则按建议配比验证，不能则按**可达最大配比**验证，并写入报告。

压测入口默认 Phase 3 的 `proxy_base_url`。

> **配比场景绑定**：ratio 只对当前输入/输出长度有效（P/D 各自选用的并发点写入报告）。换序列长度必须重测，禁止复用旧 ratio。

## 配比落地与验证实测（硬要求）

在得到建议 `N_P : N_D` 之后，**不得**只写建议就结束；必须做资源判定 + 一组端到端验证压测。

### 资源盘点

从 `pd-deploy-config.md` / `pd-params.json` 汇总：

| 量 | 定义 |
| --- | --- |
| `avail_npus` | **整机**可用 NPU：设备类型默认卡数（A2=8 / A3=16）× distinct `host_ip`（即 `host_avail_npus`）。**不是**基线 P/D 行 `npu_count` 之和（基线只占最小实例） |
| `avail_hosts` | distinct `host_ip` 数 |
| `cost_p` | **一个 Prefill 实例**最小卡数 = 拉起命令 `DP_P × TP_P` |
| `cost_d` | **一个 Decode 实例**最小卡数 = 拉起命令 `DP_D × TP_D` |
| `need` | `suggested_n_p × cost_p + suggested_n_d × cost_d` |
| `baseline_npus_in_use` | 当前 QPS 基线实际占用卡 = `cost_p + cost_d`（1P1D）；空闲卡不计入单卡吞吐分母 |

同机共置时：同一 host 上可同时放 1 个 P 实例 + 1 个 D 实例，只要 `cost_p + cost_d ≤` 该机卡数；QPS 扫点阶段 **只拉这 1P1D**，不必把剩余卡用上。

### 可达判定

```bash
python configuration-tuning-skills/pd-ratio-benchmark/scripts/fit_pd_ratio_capacity.py \
  --suggested-n-p {n_p} --suggested-n-d {n_d} \
  --cost-p {DP_P*TP_P} --cost-d {DP_D*TP_D} \
  --avail-npus {avail_npus} [--avail-hosts {n}] \
  --out-json {workdir}/pd-ratio/benchmark/capacity-fit.json
```

| 结果 | 行为 |
| --- | --- |
| `feasible=true` | **按建议配比** `deploy_n_p:deploy_n_d` 重新渲染/部署（或扩实例），再跑验证压测 |
| `feasible=false` | **按脚本给出的最大可达配比** `deploy_n_p:deploy_n_d`（尽量贴近目标 ratio）部署并验证；报告写明「建议不可达 → 采用最大可达」 |

若最大可达仍为当前基线拓扑（如已是 1P1D 且无法扩）→ 验证压测可在现拓扑补测 e2e，并在报告说明「资源不足无法扩到建议配比，仅完成基线对照」。

### 验证压测（各拓扑独立求 SLO 最大吞吐）

业务场景：与配置相同的 **输入/输出长度**（本任务 3584 / 1536）。**TTFT 与 TPOT 同时作为门禁**（用户值或默认：TTFT 不限、TPOT=50ms）。

**禁止**强制 1P1D 与验证拓扑使用相同 concurrency。每一拓扑自己扫点，取该拓扑在双 SLO 下的 **最大 e2e QPS**，再比单卡。

1. **1P1D 基线**：在最小 1P1D 上，业务 in/out、经 proxy、`stable_stage`，按并发阶梯扫点（`2→4→8→16→32`，必要时 `64→128…`）。每点校验 **TTFT 且 TPOT**。在合规集合内取 QPS 最大者为 `baseline_e2e_qps`（记下 `baseline_concurrency`，可与 1P2D 不同）。`baseline_npus`=`baseline_npus_in_use`，`baseline_qps_per_npu = e2e_qps / npus`。可复用已有 1P1D 业务 e2e 点，但必须按 **双 SLO** 重新选点（D 测只看 TPOT 的点，若 TTFT 超限则不得用作 verify 基线）。
2. **部署候选拓扑**（如 1P2D）：扩实例后 **重新独立扫点**（并发不必等于基线）。同样双 SLO，取合规最大 QPS 为 `verify_e2e_qps`（记下 `verify_concurrency`）。撞上该拓扑 `--max-num-seqs` 且双 SLO 仍合规、QPS 仍升 → 上调后继续。
3. **单卡对比**：`verify_qps_per_npu = verify_e2e_qps / verify_npus`。报告必须写明两侧 **各自** concurrency。
4. **判定与终态推荐（硬，以单卡吞吐最佳为准）**：
   - `per_npu_improved = verify_qps_per_npu > baseline_qps_per_npu`。
   - **提升**：终态推荐 = 验证拓扑；现网保持该拓扑。
   - **未提升**（含持平）：终态推荐 = **基线 1P1D**；**必须**把现网切回 1P1D。公式 1P:kD 只是验证候选。
   - 禁止因「对齐并发」而让某一拓扑在未打满或已超 SLO 的点上对比。
5. 产物：`verify/baseline-e2e.json`、`verify/deploy-e2e.json`（均含 `concurrency`、`ttft_ms`、`tpot_ms`、`slo_met`）、`recommend.json`；attempt 用 `attempt_*_v.json`（或 `*_verify.json`）。

```bash
python configuration-tuning-skills/pd-ratio-benchmark/scripts/select_recommend_pd.py \
  --baseline-json {workdir}/pd-ratio/benchmark/verify/baseline-e2e.json \
  --deploy-json {workdir}/pd-ratio/benchmark/verify/deploy-e2e.json \
  --out-json {workdir}/pd-ratio/benchmark/recommend.json
```

### 报告必须包含

- 公式建议配比 vs **验证候选** vs **终态推荐**（单卡吞吐最佳）；`feasible`、卡数/机器数账本
- 基线 vs 验证的 e2e QPS 与 **单卡 QPS**
- 结论：是否提升；未提升则终态推荐 1P1D，现网须切回 1P1D

## AISBench 配置硬约束（实测必守）

| 规则 | 说明 |
| --- | --- |
| **必须带 `summarizer`** | P 用 `DefaultPerfMetricCalculator`，D 用 `StablePerfMetricCalculator`（或 CLI `--summarizer stable_stage`） |
| **固定长度用 Synthetic** | `RequestCount` 建议 ≥ 并发×4（如 concurrency=8 → 32） |
| **Chat + stream** | `VLLMCustomAPIChat`，`stream=True` |
| **入口是 proxy** | `host_ip`/`host_port` 指向 proxy；不要直连 P/D |
| **模型名** | 填 served-model-name（以 Phase 3 冒烟为准） |
| **P/D 可独立调参** | 输入长度一致；`output_len` / summarizer 不同；**concurrency / request_rate / RequestCount 可不同** |
| **`request_rate=0`** | 尽快打满 |
| **先 P 后 D** | 顺序：先完成 P 侧饱和扫点并选定 `QPS_P`，再做 D 侧扫点；两侧选点互不绑定 |
| **D 测 prefix cache 100%** | D 与验证 e2e：`PrefixLen = RequestSize` + Prefill `--enable-prefix-caching`；P：`PrefixLen = 0` + 保持官方 `--no-enable-prefix-caching`（若官方如此）。禁止用无共享前缀的 D 点算 `QPS_D` |
| **指标解析** | throughput 常在 JSON；TTFT/TPOT 常在同目录 CSV（`Stage=total|stable`）——两侧都要解析落盘 |

### Proxy 健康检查

冒烟以 **chat/completions** 为准；`/v1/models` 404 可忽略。

### 超长上下文耗时

墙钟几乎由 Prefill TTFT 主导；≥64k 先告知用户；长任务用 nohup+轮询。不得因耗时长而跳过扫点/补测或丢掉中间结果。

### 配置骨架

```bash
ais_bench /path/ais_p_qps.py --mode perf
ais_bench /path/ais_d_qps.py --mode perf
```

指标：Request Throughput；D 侧优先 **stable** 段 QPS。

## Agent 步骤

1. Read 本 SKILL、`pd-ratio-report-template.md`、Phase 2/3 status、`pd-deploy-config.md`。
2. 解析 SLO（空则 TTFT 不限、TPOT=50ms）；创建 `attempts/`。
3. 粗估墙钟；≥64k 先告知用户。
4. 冒烟 proxy。
5. **P 测扫点**（含低并发前端）：有 TTFT 则在合规下取最大 QPS；无 TTFT 则扫到「QPS 平台 + TTFT 单涨」。缺前端则补测。若撞上 Prefill `--max-num-seqs` 且尚未过饱和 → 上调后继续。每轮写 attempt → 更新 `p-qps-result.json`。
6. **D 测扫点（独立 concurrency）**：仅 TPOT 门禁；**必须** `PrefixLen = RequestSize`（100% 共享前缀）且 Prefill 已 `--enable-prefix-caching`。扫到「TPOT 平台 + TTFT 单涨」且含低并发前端。若撞上 Decode `--max-num-seqs` 且 TPOT 仍合规、QPS 仍升 → 上调后继续，**不要**把截断点当 `QPS_D`。每轮写 attempt → 更新 `d-qps-result.json`。**不要**为对齐 P 而改并发或重跑 P。验证 e2e 与 D 测同口径（100% prefix）。
7. 两侧均满足后计算配比：

```bash
python configuration-tuning-skills/pd-ratio-benchmark/scripts/compute_pd_ratio.py \
  --p-json {workdir}/pd-ratio/benchmark/p-qps-result.json \
  --d-json {workdir}/pd-ratio/benchmark/d-qps-result.json \
  --out-json {workdir}/pd-ratio/benchmark/ratio-calc.json
```

8. **资源拟合**：`--avail-npus` 用 `pd-params.json` 的 `host_avail_npus`（整机×host），`--cost-p/--cost-d` 用 `min_*_instance_npus` → `capacity-fit.json`；决定验证候选 `deploy_n_p:deploy_n_d`（建议可达则用建议，否则最大可达）。
9. **验证部署 + e2e 压测**：按拟合配比部署；**1P1D 与候选拓扑各自扫点**，取 TTFT+TPOT 合规的最大 e2e QPS（并发可不同）；比单卡；`select_recommend_pd.py`。未提升则推荐并切回 1P1D。
10. 写报告（扫点轨迹 + 饱和判读 + **资源可达性** + **验证实测与单卡对比** + **终态推荐=单卡最佳**）+ status。

## 产物

```text
{workdir}/pd-ratio/benchmark/
  ais_p_qps.py
  ais_d_qps.py
  attempts/
    attempt_NNN_p.json
    attempt_NNN_d.json
    ...
    attempts.jsonl
    attempts-summary.md   # 含按 concurrency 排序的 P/D 曲线
  p-qps-result.json          # 最终选用（slo_met=true）
  d-qps-result.json
  ratio-calc.json
  capacity-fit.json          # 建议 vs 可达（验证候选）
  recommend.json             # 终态推荐（单卡吞吐最佳；未提升则 1P1D）
  verify/
    baseline-e2e.json
    deploy-e2e.json
  pd-ratio-report.md
  pd-ratio-status.md
```

## JSON 最小字段

最终 `p-qps-result.json` / `d-qps-result.json`：

```json
{
  "qps": 0.0,
  "ttft_ms": null,
  "tpot_ms": null,
  "max_concurrency": null,
  "request_rate": null,
  "request_count": null,
  "output_len": 1,
  "input_tokens_avg": null,
  "summarizer": "default_perf|stable_stage",
  "slo_met": true,
  "ttft_limit_ms": null,
  "tpot_limit_ms": 50,
  "constraint_checked": "ttft|tpot|none",
  "attempt_id": "attempt_002_p",
  "raw_log_path": ""
}
```

单次 `attempts/attempt_NNN_{p|d}.json` 另含：`attempt`、`side`、`slo_fail_reason`、`selected`、`timestamp`。
