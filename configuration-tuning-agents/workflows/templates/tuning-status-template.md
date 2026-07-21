# tuning-status 模板（第二阶段占位）

`tuning-status.md` 是 **`serving-tuning-subagent` 的唯一交付物**。当前版本固定为占位状态，表示服务化调优能力尚未实现。

## 落盘路径

```text
{case_dir}/tuning/tuning-status.md
```

## 写者 / 读者

| 角色 | 关系 |
| --- | --- |
| **写者** | `serving-tuning-subagent`（Phase 2 占位） |
| **读者** | primary（确认 Phase 2 占位结束）；未来调优 subagent 可覆写本文件 |

---

## 按下面结构落盘

```markdown
# Serving Tuning Status

> producer: serving-tuning-subagent
> phase: 2
> status: placeholder

## 1. 占位说明

- message: 服务化调优能力尚未实现；流水线在基线复现（Phase 1）完成后结束。
- implemented: no
- blocked_actions: deploy, collect_logs, parse_metrics, config_tuning

## 2. baseline-summary 确认

- baseline_summary_path:
- baseline_summary_valid: yes | no
- received_at: YYYY-MM-DD HH:MM (TZ)

### 2.1 已读取字段（摘要）

| 字段 | 值 |
| --- | --- |
| case_id | |
| model_name | |
| selected_profile | |
| launch_script_path | |
| service_host | |
| service_port | |

## 3. 后续版本预留（勿填写）

<!-- 未来 Phase 2 实装时可在此追加：部署结果、启动日志路径、指标 CSV、调优 Plan 等 -->
```
