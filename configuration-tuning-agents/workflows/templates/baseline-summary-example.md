# Baseline Reproduce Handoff

> producer: serving-baseline-reproduce-subagent  
> consumer: 服务化调优下一环节 subagent（Step 2+）  
> 示例 case：`qwen35-27b-a3-w8a8-mix-4096-1024`

## 1. 场景标识

| 字段 | 值 |
| --- | --- |
| case_id | qwen35-27b-a3-w8a8-mix-4096-1024 |
| model_name | Qwen3.5-27B |
| device_type | A3 |
| quantization | w8a8 |
| num_npus | 2 |
| deploy_strategy | 单机混部 |
| input_seq_len | 4096 |
| output_seq_len | 1024 |

- matched_baseline_doc: configuration-tuning-skills/ascend-baseline-generator/baseline-docs/Qwen/Qwen3.5-27B/基于vLLM-Ascend的Qwen3.5-27B模型Atlas 800I A3单机混部部署实践.md
- match_status: matched

## 2. 已确认基线方案

- selected_profile: 低时延
- profile_confirmed: yes
- selection_note: 用户确认低时延；高吞吐/低时延最大并发比为 2，未达 3 倍倾向规则

## 3. 负载与参考容量口径

| 字段 | 值 |
| --- | --- |
| context_len_max_model_len | 133000 |
| ref_avg_input | 4096 |
| ref_avg_output | 1024 |
| ref_parallelism | TP2 |
| ref_max_concurrency | 32 |
| ref_request_rate | 2 req/s |
| ref_prefix_cache_hit_rate | 0% |

## 4. 部署产物引用

| 字段 | 值 |
| --- | --- |
| launch_script_path | baseline-launch.sh |
| config_used_path | config.used.md |
| model_weights_path | /home/Qwen3.5-27B-w8a8-mtp |
| served_model_name | qwen3.5 |

### 4.1 关键 vLLM 参数摘要

| 参数 | 值 |
| --- | --- |
| max_model_len | 133000 |
| max_num_seqs | 32 |
| max_num_batched_tokens | 8096 |
| tensor_parallel_size | 2 |
| data_parallel_size | 1 |
| quantization | ascend |

## 5. 下一环节 subagent 输入（Handoff Checklist）

- [x] `match_status` = matched 且 `profile_confirmed` = yes
- [x] `launch_script_path` 存在且与 §4 摘要一致
- [x] §3 参考容量字段已填
- [x] 服务访问信息已填

| 字段 | 值 |
| --- | --- |
| service_host | 0.0.0.0 |
| service_port | 8000 |
| perf_goal_optional | 平均输出吞吐 ≥ 270 tokens/s（业务目标，待实测验证） |
| suggested_next_actions | deploy_and_serve, collect_startup_log, collect_serving_log |

## 6. 附录：基线复现过程（可选）

### 6.1 五字段比对

| 字段 | 配置值 | 文档值 | 结果 |
| --- | --- | --- | --- |
| device_type | A3 | Atlas 800I A3 | pass |
| model_name | Qwen3.5-27B | Qwen3.5-27B | pass |
| quantization | w8a8 | W8A8C16 | pass |
| num_npus | 2 | 2 | pass |
| deploy_strategy | 单机混部 | 单机混部部署 | pass |

### 6.2 双 Profile 对比

| 维度 | 低时延 | 高吞吐 |
| --- | --- | --- |
| context_len | 133000 | 65536 |
| max_concurrency | 32 | 64 |
| match_score | 0.0 | 512.0 |

### 6.3 匹配扫描

- docs_scanned: 9
- docs_identity_matched: 1
- scoring_formula: (平均输入 - input)² + (平均输出 - output)² × 0.8
