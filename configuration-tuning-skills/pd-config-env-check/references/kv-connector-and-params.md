# KV Connector、kv_port 与 PD 参数公式

供 `pd-config-env-check` / `render_pd_launch.py` / `compute_pd_params.py` 使用。  
**硬规则：保留用户/模板中的 `kv_connector` 原值，禁止按模型猜名称替换。**

## 0. Mooncake master（先于 P/D）

当使用 Mooncake 系 connector / KV store 时，**必须先**在集群中拉起 `mooncake_master`，再启动 Prefill / Decode。

默认命令：

```bash
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
mooncake_master --port 50088 \
  --eviction_high_watermark_ratio 0.9 \
  --eviction_ratio 0.1 \
  --default_kv_lease_ttl 11000
```

配套 `mooncake.json`（各节点可读）：

```json
{
  "metadata_server": "P2PHANDSHAKE",
  "protocol": "ascend",
  "device_name": "",
  "master_server_address": "<master_ip>:50088",
  "global_segment_size": "1GB"
}
```

Path C 渲染产物：`rendered/mooncake/start_mooncake_master.sh` + `mooncake.json`。  
部署顺序：**master → Prefill → Decode → Proxy**。  
若集群已有 master：配置 `skip_mooncake_master: true`。

**预装硬门禁**：P/D/master 容器内须已预装 Mooncake；Phase 1 在**交互等价壳**（`bash -ic` / `source ~/.bashrc`）下按用户命令前置的 mooncake `LD_LIBRARY_PATH` 校验 `TransferEngine` import 与 `mooncake_master`。非交互 `bash -lc` 可能缺少 `.bashrc` 中的 `/usr/local/lib`，不得据此改用户配置。交互等价下仍失败则 `pd-check-status=failed` 并停止。详见 `scripts/env_check_helpers.md`。

参考：
- [vllm-ascend kv_pool / mooncake_master](https://docs.vllm.ai/projects/ascend/en/latest/user_guide/feature_guide/kv_pool.html)
- [mooncake_connector_deployment_guide.md](https://github.com/vllm-project/vllm-ascend/blob/main/examples/disaggregated_prefill_v1/mooncake_connector_deployment_guide.md)
- 注册表：`vllm_ascend/distributed/kv_transfer/__init__.py`（`MooncakeConnectorV1` / `Hybrid` / `Layerwise`）

## 1. KV Connector 类型

| connector | 当前出现于 | 状态 |
| --- | --- | --- |
| `MooncakeConnectorV1` | DeepSeek-V3.1、GLM5、GLM5.1 | 在用 |
| `MooncakeHybridConnector` | DeepSeek-V4-Pro、DeepSeek-V4-Flash | 在用 |
| `MooncakeConnector` | 早期版本 | 历史保留（已不在主流模板） |
| `MooncakeLayerwiseConnector` | 早期版本 | 历史保留（已不在主流模板） |

本 skill **一律保留**命令/模板里的 connector 字符串，不做名称替换。教程会随版本演化，硬编码替换只会脱节。

## 2. `kv_transfer_config` 通用结构

无论 connector 是哪一种，字段结构一致：

```json
{
  "kv_connector": "<模板原值>",
  "kv_role": "kv_producer | kv_consumer",
  "kv_port": "{kv_port}",
  "engine_id": "{engine_id}",
  "kv_connector_extra_config": {
    "prefill": {"dp_size": "X", "tp_size": "Y"},
    "decode": {"dp_size": "X", "tp_size": "Y"}
  }
}
```

**允许自动替换的字段（仅这些）**：

- `kv_port`
- `engine_id`
- `kv_connector_extra_config.prefill.dp_size`
- `kv_connector_extra_config.decode.dp_size`

**必须保留原值（只校验不改）**：`kv_connector`、`kv_role`、`tp_size`、以及其它非上列字段（含教程中可能出现的 `kv_buffer_device` / `kv_parallel_size` / `kv_rank` 等）。  
另：多机同角色可改写网络相关 env / 字面 IP（见主 SKILL）。

## 3. `kv_port` 端口范围

AscendDirectTransport 会占用 `[20000, 20000 + npu_per_node × 1000)` 区间，`kv_port` 不得落入该范围。

| 机型 | 卡数 | 保留端口范围 | 建议 kv_port |
| --- | --- | --- | --- |
| A2 | 8 | 20000 – 27999 | ≥ 28000 |
| A3 | 16 | 20000 – 35999 | ≥ 36000 |

公式以 **36000** 为基数（同时满足 A2 ≥28000 与 A3 ≥36000）。  
每个实例 `kv_port` **必须唯一**，按 **100** 递增：`36000, 36100, 36200, ...`。

## 4. 代理类型与 connector

| 代理脚本 | 默认搭配家族 | 路由方向 |
| --- | --- | --- |
| `load_balance_proxy_server_example.py` | MooncakeConnector 系（prefill→decode 推送为主） | P → D |
| `load_balance_proxy_layerwise_server_example.py` | MooncakeLayerwiseConnector 系（decode 拉取为主） | D → P |

`MooncakeConnectorV1` / `MooncakeHybridConnector` 在不同教程里都搭配过上述某一种 proxy——**以教程模板或用户输入为准，禁止凭名字猜**。  
渲染时把两份 proxy 脚本都放到 `rendered/proxy/`，`start_proxy.sh` 用 `PROXY_TYPE` 切换。

## 5. 代理启动参数

- `--prefiller-hosts`：空格分隔 IP；**每个节点 IP 重复 `dp_size_local` 次**
- `--prefiller-ports`：每节点 `vllm_start_port + i`（`i=0..dp_size_local-1`），对每个节点重复该序列
- `--decoder-hosts` / `--decoder-ports`：同理

默认 `vllm_start_port = 7100`（若用户命令已给 `--port` 基址则从其解析）。

### A3 示例（2P1D，TP=1，DP=16 → `dp_size_local=16`）

每个 Prefill 节点 IP 重复 16 次；ports `7100..7115` 对每个 Prefill 节点各列一遍。Decode 同理。

### A2 示例（4×1P 与 4×1D，TP=1，DP=8 → `dp_size_local=8`）

每个节点 IP ×8；ports `7100..7107` 每节点重复。

## 6. PD 参数计算公式

### 最小 P/D 实例 size（硬规则）

**一个 Prefill 或 Decode 实例占用的最小 NPU 数**，由该角色**拉起命令**中的并行度确定：

```text
min_instance_npu_size = DP × TP
```

| 符号 | 取值来源（优先顺序） |
| --- | --- |
| **TP** | `--tensor-parallel-size` → `kv_connector_extra_config.<role>.tp_size` → 配置字段 `prefill_tp_size` / `decode_tp_size` |
| **DP** | `--data-parallel-size`（本实例/本节点本地 DP）→ `kv_connector_extra_config.<role>.dp_size`（若表示单实例本地 DP） |

含义：

- **P 实例最小 size** = 该 Prefill 拉起命令的 `DP_P × TP_P`
- **D 实例最小 size** = 该 Decode 拉起命令的 `DP_D × TP_D`
- 路径 C **QPS 基线**：机器表该角色行的 `npu_count`（或 `ASCEND_RT_VISIBLE_DEVICES` 个数）**必须等于** `min_instance_npu_size`；剩余卡空闲。禁止为压测把半机/整机都分给 1P1D。
- **禁止**用整机 `npu_per_node`（A2=8 / A3=16）直接当作「最小实例 size」，也禁止用 `npu_per_node / tp` 加大 DP 去占满整机。整机卡数只用于 Phase 4 `avail_npus` 拟合扩容。

示例：

| 拉起命令 | 最小实例 size |
| --- | --- |
| `--data-parallel-size 1 --tensor-parallel-size 4` | **4** 卡 |
| `--data-parallel-size 2 --tensor-parallel-size 4` | **8** 卡 |
| TP=1、DP=16（A3 整机一类） | **16** 卡 |

校验：`validate_pd_config` 用 `tp_size × dp_size_local` 与可见卡数对照（见下）。

### 公共

```text
npu_per_node = 16 if machine_type in (A3, A3超节点) else 8
```

> **全卡独占节点**假设：仅当用户明确让 P 或 D **独占整机**时使用。路径 C 配比 QPS 基线 **不适用**（最小实例 + 剩余卡空闲）。  
> **同机共置（1 机拆分 P/D）**不适用该假设，见下节「同机共置覆盖」。  
> 无论哪种拓扑，**实例最小卡数定义始终是拉起命令的 DP×TP**。

### Prefill（全卡独占节点）

```text
prefill_tp_size = kv_connector_extra_config.prefill.tp_size   # 保留模板原值
prefill_dp_size_local = npu_per_node / prefill_tp_size
prefill_dp_size = prefill_instances × nodes_per_prefill_instance × prefill_dp_size_local
prefill_kv_port = 36000 + instance_index × 100
prefill_engine_id = instance_index + 1          # 1,2,3...
prefill_dp_rank_start = (node_index_in_instance - 1) × prefill_dp_size_local
```

`instance_index` 从 0 起；`node_index_in_instance` 从 1 起。  
**dp_rank_start 按实例内节点递增，各实例独立计数（禁止全局递增）。**

### Decode（全卡独占节点）

```text
decode_tp_size = kv_connector_extra_config.decode.tp_size
decode_dp_size_local = npu_per_node / decode_tp_size
decode_dp_size = decode_instances × nodes_per_decode_instance × decode_dp_size_local
decode_kv_port = 36000 + prefill_instances × 100 + instance_index × 100
decode_engine_id = prefill_instances + instance_index + 1
decode_dp_rank_start = (node_index_in_instance - 1) × decode_dp_size_local
```

### 同机共置覆盖（高频：单机 1P1D 拆卡）

当 **同一 `host_ip` 上同时有 P 与 D**（例如 A2 上 4 卡 P + 4 卡 D）：

| 错误做法 | 正确做法 |
| --- | --- |
| `dp_size_local = npu_per_node / tp`（A2+TP4 → 误得 2；也会占满整机） | 用拉起命令 `--data-parallel-size`；可见卡必须已是 `DP×TP` |
| 强行改写用户 `--data-parallel-size` / `"dp_size"` | **优先保留**拉起命令中已写明的 DP / `dp_size` / `kv_port` / `engine_id` / `--port` |
| 把 `LOCAL_IP=127.0.0.1` / `NIC_NAME=lo` 改成机器外网 IP | **保留 loopback**；禁止为「对齐 host_ip」破坏用户已验证的单机互联 |

同机示例（A2 8 卡，官方 TP=2 DP=1，路径 C QPS 基线 **不必占满整机**）：

```text
min instance = 2×1 = 2 卡
P: npu_ids=0,1  ASCEND_RT_VISIBLE_DEVICES=0,1
D: npu_ids=2,3  ASCEND_RT_VISIBLE_DEVICES=2,3
leftover: 4,5,6,7 空闲（拟合扩容才用）
prefill_dp_size_local = 1（不是 8/2=4）
decode_dp_size_local  = 1
proxy：各 1 个 prefiller / decoder
```

优先级（`compute_pd_params`）：

1. 拉起命令中的 `--data-parallel-size` / `"dp_size"` / `kv_port` / `engine_id` / `--port`
2. 机器表 `npu_count`（或可见卡）÷ `tp_size`（同机共置，且 `npu_count` 已是最小实例）
3. 回退 `dp_size_local=1`（**禁止**再用 `npu_per_node / tp_size` 填满整机）

### 示例（2P1D，A3，Prefill TP=8，Decode TP=4）

```text
npu_per_node=16
prefill_dp_size_local=2, decode_dp_size_local=4
prefill_dp_size=2×1×2=4
P1N1: kv_port=36000, engine_id=1, dp_rank_start=0
P2N1: kv_port=36100, engine_id=2, dp_rank_start=0
decode_dp_size=1×1×4=4
D1N1: kv_port=36200, engine_id=3, dp_rank_start=0
```

多实例 Decode（4D2N，`decode_dp_size_local=4`）：每实例 N1 `dp_rank_start=0`、N2 `=4`，实例间互不累加。

## 7. 实现入口

```bash
python scripts/compute_pd_params.py --config {pd-deploy-config.md} --json out.json
```

渲染阶段调用该脚本结果，写入各实例 `kv_transfer_config` 与 proxy hosts/ports。
