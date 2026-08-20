# 路径 C · PD 配比用户配置格式

Primary / `pd-config-env-check` 读取 `{workdir}/pd-deploy-config.md`（或用户指定路径）。独立 skill 快路径 **不** 使用本格式。模板见 [`../templates/pd-deploy-config.template.md`](../templates/pd-deploy-config.template.md)。  

KV / 公式细则：`configuration-tuning-skills/pd-config-env-check/references/kv-connector-and-params.md`。  
官方拉起回退：`configuration-tuning-skills/pd-config-env-check/references/official-model-launch.md`（[模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/)）。

## 必填

| 段 | 要求 |
| --- | --- |
| `## 基本参数` | 模型名称、设备类型、输入/输出长度非空；`same_launch_cmd` 默认 `false` |
| Mooncake / 拓扑 | `require_mooncake_master`、`skip_mooncake_master`、`mooncake_master_*`、`prefill_instances` 等 |
| `## 机器与容器` | 至少 1 行 P、1 行 D；可选 `mooncake_master`、`proxy`、`instance_id`；`container_name` **可空**（Agent 一机一容器拉起） |
| `## Prefill 拉起命令` | **推荐**非空；为空则 Agent 按模型名从[官方模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/)回填（优先 PD 分离 + 匹配 A2/A3） |
| `## Decode 拉起命令` | 同上；`same_launch_cmd=true` 时可省略 |

## SLO：TTFT / TPOT（Phase 0 必须处理）

路径 C **一开始**就要确定时延约束，供 Phase 4 压测验收：

| 字段 | Phase 0 行为 |
| --- | --- |
| **TTFT** | **先向用户询问**；用户提供则写入配置；仍不提供 → 默认 **不设限制**（可写 `不限` / 留空并注明 default） |
| **TPOT** | **先向用户询问**；用户提供则写入配置；仍不提供 → 默认 **50ms** |

Phase 4：P 只校验 TTFT、D 只校验 TPOT；详见 `pd-ratio-benchmark` skill。

## 可选

| 段 / 字段 | 说明 |
| --- | --- |
| `proxy_type` / `proxy_port` / `vllm_start_port` | 代理与 vLLM 端口基址 |
| `docker_image` | 可选；指定则全员固定。空则高版本优先；**多机时解析一次后所有 host 共用同一 tag** |
| `## Proxy` | 缺省则按 dp_size_local 展开自动生成 |
| `## 网络参数` | 网卡名等 |

## 自动改写范围（Phase 1）

| 允许 | 禁止 |
| --- | --- |
| 网络 env / baseline IP（**不含**用户已写的 `127.0.0.1`/`lo`） | 改 `kv_connector` 名称 |
| `kv_port` / `engine_id` / `*.dp_size`（**优先保留**拉起命令已有值） | 改 `tp_size`、`kv_role`、模型路径、量化、`--port`、`ASCEND_RT_VISIBLE_DEVICES` |
| proxy hosts/ports 展开（同机共置用角色 `npu_count`/用户 DP，勿用整机 `npu/tp`） | 同机为 P/D **各建**一个容器；宿主机执行非 docker 指令 |
| **未指定/缺失容器时**按设备类型（A2/A3 官方分 tab）`docker run` | 安装 Mooncake；改用户已验证拉起命令中的库路径 |
| **拉起命令为空时**从官方模型教程回填 | 教程无匹配时编造命令 |

机器表建议填写 `npu_ids` / `npu_count`（同机拆卡时必填，避免 DP 误算）。同 `host_ip` 各 role 共用一个 `container_name`。  
**最小 P/D 实例卡数** = 拉起命令 `DP × TP`（`--data-parallel-size` × `--tensor-parallel-size`）；`npu_count` 须与之对齐。  
**配比 QPS 基线（硬）**：只拉 1 个最小 P + 1 个最小 D，**不要把整机卡都写进 P/D 行**。`npu_ids` 为空时：P 用连续 `DP_P×TP_P` 张卡，D 用紧接着的 `DP_D×TP_D` 张；剩余卡空闲（留给 Phase 4 按整机卡数拟合扩容）。禁止把半机/整机硬拆成「4P+4D」一类占满压测。  
容器模板参考：[GLM5 Docker A3/A2](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/GLM5.html#__tabbed_1_2)。宿主机 **只允许 docker***。

## Phase 0 行为

1. 文件不存在 → 生成模板并停止。
2. 模型/设备/序列长度等必填缺失 → 列出缺失项并停止（拉起命令可空，交 Phase 1 官方回退）。
3. **TTFT/TPOT**：向用户询问；未答复则写入默认（TTFT 不限、TPOT=50ms）并在 `progress.md` 注明。
4. 通过 → 派发 Phase 1。
