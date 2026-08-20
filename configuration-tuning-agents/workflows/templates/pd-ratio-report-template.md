# pd-ratio-report 模板

`pd-ratio-report.md` 是 **`serving-pd-ratio-benchmark-subagent`（路径 C · Phase 4）** 的终态报告。

## 落盘布局

```text
{workdir}/pd-ratio/benchmark/
├── attempts/                 # 每一次实测（含失败/扫点）
│   ├── attempt_NNN_p.json
│   ├── attempt_NNN_d.json
│   ├── attempts.jsonl
│   └── attempts-summary.md
├── p-qps-result.json         # 最终选用
├── d-qps-result.json
├── ratio-calc.json
├── capacity-fit.json         # 建议配比 vs 集群可达
├── verify/
│   ├── baseline-e2e.json
│   └── deploy-e2e.json
├── pd-ratio-report.md        # 本模板
└── pd-ratio-status.md
```

## 写者 / 读者

| 角色 | 关系 |
| --- | --- |
| **写者** | `serving-pd-ratio-benchmark-subagent` |
| **读者** | primary / 用户 |
| **输入依赖** | Phase 2 aisbench 可用；Phase 3 `proxy_base_url`；`pd-deploy-config.md` 中序列长度、SLO、机器表与拉起命令 DP×TP |

---

## 按下面结构落盘

```markdown
# Best PD Ratio Report

> producer: serving-pd-ratio-benchmark-subagent
> phase: 4
> workdir: {workdir}

## 1. 测试条件

| 项 | 值 |
| --- | --- |
| 输入长度 | |
| 输出长度（业务） | |
| TTFT 约束 | 用户值或「不限」（default）；**仅约束 P 测** |
| TPOT 约束 | 用户值或 50ms（default）；**仅约束 D 测** |
| SLO 来源 | user / default |
| proxy_base_url | |
| 数据集 / 请求数 | |
| D prefix cache | 必须 100%：`PrefixLen=RequestSize`；Prefill 是否临时 `--enable-prefix-caching`；hit rate（若日志有） |
| concurrency_P | P 最终选用（可与 D 不同） |
| concurrency_D | D 最终选用（可与 P 不同） |
| max-num-seqs | P/D 各自原值 → 扫点后值（若上调须写明） |
| request_rate | 可分侧记录 |
| 本侧约束是否满足 | P：TTFT 规则；D：TPOT；两侧均是才可 completed |
| 重测/扫点次数 | P 轮次数 / D 轮次数 / 总 attempt 数 |
| 预估/实际墙钟 | 注明 Prefill TTFT 主导 |
| 基线拓扑 | 如 1P1D · 卡数 |

## 2. 重测轨迹（全部 attempt，不得省略）

| attempt | side | concurrency | QPS | TTFT_ms | TPOT_ms | slo_met | selected | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 001 | p | 8 | | | — | true | | 无 TTFT：升并发扫吞吐 |
| 002 | p | 16 | | | — | true | ✓ | P 吞吐饱和点 |
| 003 | d | 8 | | | | true | ✓ | 仅 TPOT；并发可独立 |

详情目录：`{workdir}/pd-ratio/benchmark/attempts/`

### P 饱和判读（按 concurrency；out=1 无有效 TPOT）

| concurrency | QPS | TTFT_ms | 阶段 |
| --- | --- | --- | --- |
| 2 | | | 前端：TTFT 偏小，QPS 未峰 |
| 4 | | | 峰值 / selected |
| 8+ | | | 过饱和：QPS 平台，TTFT 单涨 |

### D 饱和判读（按 concurrency；须含 TTFT+TPOT 全流程）

| concurrency | QPS | TTFT_ms | TPOT_ms | 阶段 |
| --- | --- | --- | --- | --- |
| 低 | | | | 两者都偏小 |
| 中 | | | | 同升 |
| 高 | | | | TPOT 平台，仅 TTFT 涨 / selected |

## 3. 步骤 · P 节点 QPS（最终选用）

- 方法：`output_len=1`；**仅看 TTFT**；无 TTFT 则扫点至「QPS 平台 + TTFT 单涨」（须含低并发前端）
- 对应 attempt：
- 结果文件：`p-qps-result.json`

| 指标 | 值 |
| --- | --- |
| QPS_P | |
| TTFT | |
| concurrency_used | |
| request_rate_used | |
| constraint_checked | ttft（或 none） |
| slo_met | true |
| input_tokens_avg | |

## 4. 步骤 · D 节点 QPS（最终选用）

- 方法：**仅看 TPOT**；stable_stage；**Prefix cache = 100%**（`PrefixLen = RequestSize` + Prefill `--enable-prefix-caching`）；concurrency **不必**与 P 相同；曲线须含「两者偏小→同升→TPOT 平台」
- 对应 attempt：
- 结果文件：`d-qps-result.json`

| 指标 | 值 |
| --- | --- |
| QPS_D | |
| TPOT | |
| concurrency_used | |
| summarizer | stable_stage |
| constraint_checked | tpot |
| slo_met | true |

## 5. 最佳 PD 配比（建议）

公式：

- `ratio = QPS_P / QPS_D`
- 建议实例比：`N_D / N_P = QPS_P / QPS_D`

| 项 | 值 |
| --- | --- |
| QPS_P | |
| QPS_D | |
| ratio (QPS_P/QPS_D) | |
| 建议 N_P | |
| 建议 N_D | |
| 建议配比描述 | 例如 1P : kD |

## 6. 资源可达性（建议 vs 集群）

配比算出后**必须**用机器表总卡数 / 总机数判定能否拉起建议拓扑；结果见 `capacity-fit.json`。

| 项 | 值 |
| --- | --- |
| avail_npus | **整机**可用 NPU（设备类型默认卡数 × distinct host），不是基线 P/D 已分配卡之和 |
| avail_hosts | distinct host 数 |
| cost_p（单 P 实例卡数） | DP_P × TP_P |
| cost_d（单 D 实例卡数） | DP_D × TP_D |
| need_npus（建议拓扑） | suggested_n_p×cost_p + suggested_n_d×cost_d |
| feasible | true / false |
| 验证候选配比 | deploy_n_p : deploy_n_d（可行则=公式建议；否则=最大可达；只用于验证） |
| 终态推荐配比 | **单卡吞吐最佳**；未提升则为 1P1D（见 `recommend.json`） |
| 选用原因 | 建议可达并验证 / 建议不可达→最大可达验证 / 未提升单卡→回退 1P1D |

判定规则：

- **feasible=true** → 按**公式建议配比**部署并做验证压测（这是验证候选，不是终态）。
- **feasible=false** → 按脚本给出的**最大可达配比**部署并验证；须明示降级。
- 验证后：**单卡提升** → 终态推荐 = 验证拓扑；**未提升** → 终态推荐 **1P1D**，现网切回 1P1D。
- 最大可达仍等于当前基线且无法扩 → 可只做基线 e2e 对照，并写明「无法扩到建议配比」。

## 7. 验证实测（单卡吞吐对比）

在 §6 选定的 `deploy_n_p:deploy_n_d` 上，用**相同业务 in/out** 做端到端压测。每一拓扑**独立**扫并发，取 **TTFT 与 TPOT 均合规**的最大 QPS；**禁止**强制相同 concurrency。

| 项 | 基线拓扑 | 验证拓扑（deploy） |
| --- | --- | --- |
| 拓扑 | 如 1P1D | deploy_n_p P : deploy_n_d D |
| 使用 NPU 数 | | |
| 选用 concurrency | 可不同 | 可不同 |
| e2e QPS（双 SLO 最大） | | |
| TTFT / TPOT | 均须合规 | 均须合规 |
| **单卡 QPS**（e2e_qps / npus） | | |

| 判定 | 值 |
| --- | --- |
| per_npu_improved | true / false（`verify_qps_per_npu > baseline_qps_per_npu`） |
| 系统 QPS 变化 | |
| **终态推荐** | 单卡最佳拓扑；未提升必须为 **1P1D** |
| 说明 | 未提升时如实写原因并切回 1P1D；**禁止伪造提升** |

产物：`verify/baseline-e2e.json`、`verify/deploy-e2e.json`、`recommend.json`

## 8. 原始产物

| 文件 | 路径 |
| --- | --- |
| 全部 attempt | `{workdir}/pd-ratio/benchmark/attempts/` |
| attempts.jsonl | `{workdir}/pd-ratio/benchmark/attempts/attempts.jsonl` |
| P 最终 JSON | `{workdir}/pd-ratio/benchmark/p-qps-result.json` |
| D 最终 JSON | `{workdir}/pd-ratio/benchmark/d-qps-result.json` |
| ratio-calc | `{workdir}/pd-ratio/benchmark/ratio-calc.json` |
| capacity-fit | `{workdir}/pd-ratio/benchmark/capacity-fit.json` |
| 终态推荐 | `{workdir}/pd-ratio/benchmark/recommend.json` |
| 验证 e2e | `{workdir}/pd-ratio/benchmark/verify/` |
| AISBench 日志 | |

## 9. 结论与建议

- overall: completed / failed
- 公式建议 vs 验证候选 vs **终态推荐**（单卡最佳）：
- 资源判定摘要（feasible / 降级原因）：
- 单卡吞吐是否提升（per_npu_improved）：
- 现网拓扑（须等于终态推荐）：
- 解读：（配比仅对当前 in/out 有效；写明 P/D 各自 concurrency）
- 扫点说明：（P / D 饱和选点）
- 耗时归因：
- 下一步建议：
```

---

## 配套 `pd-ratio-status.md`

```markdown
# PD Ratio Status

- status: completed|failed
- report: {workdir}/pd-ratio/benchmark/pd-ratio-report.md
- attempts_dir: {workdir}/pd-ratio/benchmark/attempts/
- attempt_count:
- qps_p:
- qps_d:
- ratio:
- suggested_n_p:
- suggested_n_d:
- feasible:
- deploy_n_p:
- deploy_n_d:
- recommended_n_p:
- recommended_n_d:
- recommend: {workdir}/pd-ratio/benchmark/recommend.json
- capacity_fit: {workdir}/pd-ratio/benchmark/capacity-fit.json
- baseline_e2e_qps:
- verify_e2e_qps:
- baseline_qps_per_npu:
- verify_qps_per_npu:
- per_npu_improved: true|false|n/a
- ttft_limit_ms: null|number
- tpot_limit_ms: 50
- slo_source: user|default
- slo_met: true|false
- concurrency_p:
- concurrency_d:
- timestamp:
- notes:
```
