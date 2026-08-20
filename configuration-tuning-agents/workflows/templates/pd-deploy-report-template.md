# pd-deploy-report 模板

`pd-deploy-report.md` 是 **`serving-pd-deploy-subagent`（路径 C · Phase 3）** 的结构化输出。

下一环节依赖本报告中的 proxy endpoint（AISBench 已在 Phase 2 就绪）。失败时 primary **回退 Phase 1**，不得进入配比压测。

## 落盘布局

```text
{workdir}/pd-ratio/deploy/
├── pd-deploy-report.md
└── pd-deploy-status.md
```

## 写者 / 读者

| 角色 | 关系 |
| --- | --- |
| **写者** | `serving-pd-deploy-subagent` |
| **读者** | `serving-pd-ratio-benchmark-subagent`；primary |
| **禁止** | 使用非 `rendered/` 的启动命令；改写 Phase 1 产物内容（只读执行） |

---

## 按下面结构落盘

```markdown
# PD Deploy Report

> producer: serving-pd-deploy-subagent
> phase: 2
> workdir: {workdir}

## 1. 启动来源（硬约束）

| 项 | 路径 |
| --- | --- |
| check_status | `{workdir}/pd-ratio/check/pd-check-status.md` |
| rendered_dir | `{workdir}/pd-ratio/check/rendered` |

> 启动命令 **仅** 来自 rendered/；禁止另写配置。

## 2. 启动顺序与结果

| 顺序 | 角色 | 脚本/命令 | host | container | result | endpoint | 日志路径 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Mooncake master | rendered/mooncake/start_mooncake_master.sh | | | | | |
| 1 | Prefill | | | | | | |
| 2 | Decode | | | | | | |
| 3 | Proxy | | | | | | |

> 若 `skip_mooncake_master=true`：顺序 0 记为 skipped，并注明已有 master 地址。

## 3. 健康检查

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| mooncake_master 端口 | | |
| 端口监听 (P/D/proxy) | | |
| HTTP ready / models | | |
| 进程存活 | | |

## 4. 对外服务入口（供压测）

| 项 | 值 |
| --- | --- |
| mooncake_master_address | |
| proxy_host | |
| proxy_port | |
| PROXY_TYPE | basic \| layerwise |
| base_url | http://{proxy_host}:{proxy_port} |
| served_model_name | |

## 5. 失败诊断（仅 status=failed）

| 失败阶段 | 日志摘要 | 建议用户修改 | 是否回退 Phase 1 |
| --- | --- | --- | --- |
| | | | yes |

## 6. 结论

- overall: passed / failed
```

---

## 配套 `pd-deploy-status.md`

```markdown
# PD Deploy Status

- status: passed|failed
- report: {workdir}/pd-ratio/deploy/pd-deploy-report.md
- proxy_base_url:
- rollback_to_phase1: true|false
- timestamp:
- notes:
```
