# PD 分离部署配置（路径 C · 最佳 PD 配比）

请填写下方必填段后保存，重新向 Agent 发起「计算最佳 PD 配比」请求。  
参考：`workflows/pd-ratio-workflow.md`、`configuration-tuning-skills/pd-config-env-check/references/kv-connector-and-params.md`。

**约束摘要**：

- 部署顺序：**Mooncake master → Prefill → Decode → Proxy**（除非 `skip_mooncake_master: true`）。
- Prefill / Decode 拉起命令：**推荐填写**；为空则 Phase 1 从 [官方模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/) 按模型名回填（优先 PD 分离 + A2/A3 匹配）。
- **保留** `kv_connector` 原值；Agent 只改网络字段与 `kv_port` / `engine_id` / `*.dp_size`。
- **容器**：未填 `container_name` 或不存在时，Agent **按一机一容器**自行 `docker run`；同机 P/D/proxy/mooncake 共用一容器，多 vLLM 用不同端口/卡。
- 可选 `docker_image`；默认 A2=`quay.io/ascend/vllm-ascend:v0.22.1rc1`，A3=`...:v0.22.1rc1-a3`。

## 基本参数

- 模型名称:
- 设备类型: A2
- 输入长度:
- 输出长度:
- TTFT: （请填写，如 10000ms；空=不设限制）
- TPOT: （请填写，如 50ms；空=默认 50ms）
- 初始拓扑: 1P1D
- same_launch_cmd: false
- prefill_instances: 1
- decode_instances: 1
- nodes_per_prefill_instance: 1
- nodes_per_decode_instance: 1
- prefill_tp_size: 1
- decode_tp_size: 1
- vllm_start_port: 7100
- proxy_type: basic
- proxy_port: 1999
- docker_image: （可选；指定则全员固定。空=高版本优先；多机解析一次后共用）
- require_mooncake_master: true
- skip_mooncake_master: false
- mooncake_master_host:
- mooncake_master_port: 50088
- mooncake_protocol: ascend
- mooncake_metadata_server: P2PHANDSHAKE
- mooncake_global_segment_size: 1GB

> `设备类型`：`A2` → 8 卡（容器挂 davinci0–7 + 非 a3 镜像）；`A3` → 16 卡（davinci0–15 + `*-a3` 镜像）。分模板见 [GLM5 Docker](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/GLM5.html#__tabbed_1_2)。  
> **宿主机**：只允许 docker 相关指令；其余一律进容器。  
> `proxy_type`：`basic` | `layerwise`（勿凭 connector 名猜）。  
> Mooncake：未填 `mooncake_master_host` 时优先用角色 `mooncake_master` 行，否则 proxy/P 首机。  
> **SLO**：Phase 0 须向用户确认 TTFT/TPOT；未提供则 **TTFT 不设限制**、**TPOT=50ms**。Phase 4：**P 只校验 TTFT，D 只校验 TPOT**；P/D 并发可不同。  
> **容器**：一机一容器；`--name` 与 `$IMAGE` 须按环境修改，禁止照抄示例。  
> **配比 QPS 基线**：每个 P/D 只占 **最小实例卡数 `DP×TP`**，不要占满整机。`npu_ids` 空则 P 从 0 起连续切 `DP_P×TP_P` 张、D 紧接着切 `DP_D×TP_D` 张，剩余卡空闲。例：官方 TP=2 DP=1 的 1P1D → P=`0,1` D=`2,3`，其余卡不写进表、不测 QPS。

## 机器与容器

| host_ip | container_name | role | instance_id | npu_ids | npu_count | ssh_user | ssh_port | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | mooncake_master | | | | | 22 | 与同机 P/D 共用 container；空=Agent 生成/拉起 |
| | | P | 0 | | | | 22 | 只填最小实例卡；空=Agent 按 DP×TP 切卡 |
| | | D | 0 | | | | 22 | 紧接 P 之后的最小实例卡；勿占满整机 |
| | | proxy | | | | | 22 | |

`role`：`P` / `D` / `proxy` / `mooncake_master`。同一 `host_ip` 的 `container_name` 应相同（空则 Agent 统一生成并拉起）。

## Prefill 拉起命令

```bash
# 可空：空则 Agent 从 https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/ 按模型名称回填
# Prefill: kv_role=kv_producer；kv_connector 保留教程/用户原值
```

## Decode 拉起命令

```bash
# 可空：同上；same_launch_cmd=true 时可省略
# Decode: kv_role=kv_consumer
```

## Proxy

（可选）

```bash
```

## 网络参数

- 网卡名:
- HCCL_IF_IP 映射: 使用各机 host_ip
- 其他网络环境变量:
