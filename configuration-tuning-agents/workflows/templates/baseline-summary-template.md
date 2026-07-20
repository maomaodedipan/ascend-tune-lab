# baseline-summary 模板

`baseline-summary.md` 是 **`serving-baseline-reproduce-subagent` 的结构化输出**，不是整条服务化调优流水线的终态报告。

下一环节的 subagent（部署验证、启动配置提取、运行指标解析、调优候选等，由 primary 按 workflow 派发）应 **以本文件为输入契约** 读取上下文；primary 仅负责验收 handoff 是否完整，并把路径写入 `progress.md`，**不在本文件内维护全流程状态**。

## 落盘布局

```text
{case_dir}/baseline/
├── baseline-launch.sh       # 可执行启动脚本（与 summary 配套）
├── baseline-summary.md      # 本模板 — 基线复现 subagent → 下一环节 subagent
└── config.used.md           # 匹配用 MD 配置副本
```

## 写者 / 读者

| 角色 | 关系 |
| --- | --- |
| **写者** | `serving-baseline-reproduce-subagent`（Step 1 基线复现） |
| **读者** | 服务化调优 **下一环节 subagent**（Step 2+）；primary 做 handoff 验收 |
| **不读者** | 不应把本文件当作 Plan Dashboard、调优 round 记录或最终性能结论 |

**边界**：

- 常驻区 **§1–§5** 为下游必填输入；缺失则下一环节 subagent 应拒绝开工并向 primary 报错。
- **§6 附录** 仅为基线复现过程留痕（文档匹配、评分）；下游 **可跳过不读**。

填写示例见 [`baseline-summary-example.md`](baseline-summary-example.md)。

---

## 按下面结构落盘

复制以下骨架到 `{case_dir}/baseline/baseline-summary.md` 并填写。

```markdown
# Baseline Reproduce Handoff

> producer: serving-baseline-reproduce-subagent  
> consumer: 服务化调优下一环节 subagent（Step 2+）  
> 用途: 基线复现结果交接，非全流程输出

## 1. 场景标识

下游用本节锁定「为谁调优、在哪类硬件上跑」。

| 字段 | 值 |
| --- | --- |
| case_id | |
| model_name | |
| device_type | |
| quantization | |
| num_npus | |
| deploy_strategy | |
| input_seq_len | |
| output_seq_len | |

- matched_baseline_doc: （仓库相对路径）
- match_status: matched | unmatched

## 2. 已确认基线方案

- selected_profile: 低时延 | 高吞吐 | 低时延/高吞吐（合并节）
- profile_confirmed: yes | no
- selection_note: （用户确认或 primary 代确认的一句话；若 profile_confirmed=no，下游不得启动调优）

## 3. 负载与参考容量口径

来自 baseline 文档「典型测试用例」匹配行；**下一环节**据此设计压测/对比（非已测得的实测性能）。

| 字段 | 值 |
| --- | --- |
| context_len_max_model_len | |
| ref_avg_input | |
| ref_avg_output | |
| ref_parallelism | |
| ref_max_concurrency | |
| ref_request_rate | |
| ref_prefix_cache_hit_rate | （如有） |

## 4. 部署产物引用

不粘贴 `baseline-launch.sh` 全文，只给路径与关键字段摘要。

| 字段 | 值 |
| --- | --- |
| launch_script_path | baseline-launch.sh |
| config_used_path | config.used.md |
| model_weights_path | |
| served_model_name | （若 launch 脚本中可解析） |

### 4.1 关键 vLLM 参数摘要

| 参数 | 值 |
| --- | --- |
| max_model_len | |
| max_num_seqs | |
| max_num_batched_tokens | （如有） |
| tensor_parallel_size | |
| data_parallel_size | |
| quantization | |

## 5. 下一环节 subagent 输入（Handoff Checklist）

本节为 **下游开工最小集**；subagent 进场先 Read 本节并核对。

- [ ] `match_status` = matched 且 `profile_confirmed` = yes
- [ ] `launch_script_path` 存在且与 §4 摘要一致
- [ ] §3 参考容量字段已填（尤其 `context_len_max_model_len`、`ref_max_concurrency`）
- [ ] 服务访问：`service_host`、`service_port` 已填（或明确标注「部署后回填」）

| 字段 | 值 |
| --- | --- |
| service_host | |
| service_port | |
| perf_goal_optional | （可选：吞吐/时延目标，primary Step 0 传入则记录） |
| suggested_next_actions | deploy_and_serve | collect_startup_log | collect_serving_log | （供 primary 派发参考，可多选） |

## 6. 附录：基线复现过程（可选）

仅供基线复现 subagent 留痕；**下一环节 subagent 不必读取**。

### 6.1 五字段比对

| 字段 | 配置值 | 文档值 | 结果 |
| --- | --- | --- | --- |
| device_type | | | |
| model_name | | | |
| quantization | | | |
| num_npus | | | |
| deploy_strategy | | | |

### 6.2 双 Profile 对比（若曾存在双匹配）

| 维度 | 低时延 | 高吞吐 |
| --- | --- | --- |
| context_len | | |
| max_concurrency | | |
| match_score | | |

### 6.3 匹配扫描

- docs_scanned:
- docs_identity_matched:
- scoring_formula: (平均输入 - input)² + (平均输出 - output)² × 0.8
```
