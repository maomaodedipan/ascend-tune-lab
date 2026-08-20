# pd-check-report 模板

`pd-check-report.md` 是 **`serving-pd-config-check-subagent`（路径 C · Phase 1）** 的结构化输出。

下一环节先派发 **`serving-aisbench-install-subagent`（Phase 2）**；部署 subagent 必须以本报告 + `rendered/` 为唯一启动来源。primary 验收 `pd-check-status.md=passed` 后再进入 AISBench。

## 落盘布局

```text
{workdir}/pd-ratio/check/
├── pd-check-report.md      # 本模板
├── pd-check-status.md      # status=passed|failed
└── rendered/
    ├── prefill/
    ├── decode/
    └── proxy/
```

## 写者 / 读者

| 角色 | 关系 |
| --- | --- |
| **写者** | `serving-pd-config-check-subagent` |
| **读者** | `serving-aisbench-install-subagent`、`serving-pd-deploy-subagent`；primary 做 Phase 1 验收 |
| **禁止** | 改写非网络业务参数；同机为 P/D 各建容器 |

---

## 按下面结构落盘

复制以下骨架到 `{workdir}/pd-ratio/check/pd-check-report.md` 并填写。

```markdown
# PD Config & Env Check Report

> producer: serving-pd-config-check-subagent
> phase: 1
> workdir: {workdir}

## 1. 输入摘要

| 项 | 值 |
| --- | --- |
| config_md_path | |
| same_launch_cmd | true/false |
| 模型名称 | |
| launch_cmd_source | user / official_docs |
| official_docs_url | （official_docs 时必填） |
| 输入/输出长度 | |
| TTFT / TPOT | |
| 初始拓扑 | |
| require_mooncake_master / skip | |
| mooncake_master_address | |

## 2. 环境矩阵

| host_ip | role | container | container_state | ping | interconnect | npu_declared | npu_observed | ok |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | mooncake_master/P/D/proxy | | | | | | | |


### 2.1 容器保障（一机一容器）

| host_ip | container_name | action | image | device_type | ok |
| --- | --- | --- | --- | --- | --- |
| | | reused / created / started | | A2/A3 | |

- IMAGE_SELECTED（集群统一）:
- 多机镜像一致: yes/no

规则：未指定或不存在 → 按 A2/A3 分模板拉起；同 host 共用一名；宿主机只跑 docker*；**≥2 host 必须同一 image tag**。

### 2.2 Mooncake 预装与路径（硬门禁）

| host_ip | container | mooncake_dir | libtransfer_engine | TransferEngine import | mooncake_master | ok |
| --- | --- | --- | --- | --- | --- | --- |
| | | 用户 LD_LIBRARY_PATH 中路径 | found/missing | ok/fail | ok/missing/n/a | |

规则：容器内须可用（镜像预装或用户已装）；路径以用户配置为准。校验/结论必须以**交互等价壳**（`bash -ic` / `source ~/.bashrc`）为准。非交互失败而交互成功 → 不改用户配置，部署改用交互等价启动。交互下仍失败 → overall=failed，**停止**。

## 3. 命令校验

### 3.1 Prefill

- 命令来源：
- kv_connector（**原值保留**）：
- kv_role / 关键标志：
- 校验结果：pass/fail
- 问题：

### 3.2 Decode

- 命令来源：
- kv_connector（**原值保留**）：
- kv_role / 关键标志：
- 校验结果：pass/fail
- 问题：

### 3.3 Proxy

- 来源：user_provided / auto_generated
- proxy_type（basic|layerwise）：
- hosts/ports 是否按 dp_size_local 展开：pass/fail
- 与 P/D endpoints 一致性：pass/fail

## 3.4 PD 计算参数（pd-params.json）

| 项 | 值 |
| --- | --- |
| `npu_per_node` | |
| min_p_instance_npus / min_d_instance_npus | DP×TP |
| suggested_p_npu_ids / suggested_d_npu_ids | 基线切卡 |
| leftover_npu_ids | 空闲，QPS 不用 |
| host_avail_npus | 整机卡×host（拟合用） |
| prefill_dp_size_local / decode_dp_size_local | |
| prefill_dp_size / decode_dp_size | |
| 各实例 kv_port / engine_id | |
| kv_port 是否避开保留区 | |

## 4. 网络与允许字段改写清单

仅列出：网络字段，以及 `kv_port` / `engine_id` / `*.dp_size`（及存在的 dp_rank_start）。**不得**出现 `kv_connector` 改名。

| 文件/实例 | 字段 | 原值 | 新值 | 原因 |
| --- | --- | --- | --- | --- |
| | | | | |

## 5. 需用户手动修改项

（非允许字段问题：并行度/tp_size、模型路径、量化、kv_role、connector 选型、端口策略冲突、**Mooncake 未预装或与 LD_LIBRARY_PATH 不一致**等。Agent **不得**自行修改；须停止并与用户核对。）

| 优先级 | 位置 | 问题 | 建议修改 |
| --- | --- | --- | --- |
| | | | |

## 6. rendered 路径

| 角色 | 路径 |
| --- | --- |
| Mooncake master | `{workdir}/pd-ratio/check/rendered/mooncake/` |
| Prefill | `{workdir}/pd-ratio/check/rendered/prefill/` |
| Decode | `{workdir}/pd-ratio/check/rendered/decode/` |
| Proxy | `{workdir}/pd-ratio/check/rendered/proxy/`（真实脚本 + `PROXY_TYPE`） |

### 6.1 Proxy / 校验元数据

| 项 | 值 |
| --- | --- |
| proxy_fetch.ok | |
| validate.ok | |
| deploy_order | mooncake_master → prefill → decode → proxy |

## 7. 结论

- overall: passed / failed
- 阻塞项摘要：
```

---

## 配套 `pd-check-status.md`

写入 `{workdir}/pd-ratio/check/pd-check-status.md`：

```markdown
# PD Check Status

- status: passed|failed
- report: {workdir}/pd-ratio/check/pd-check-report.md
- rendered_dir: {workdir}/pd-ratio/check/rendered
- timestamp:
- notes:
```
