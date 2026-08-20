---
name: pd-config-env-check
description: >-
  Validate PD-disaggregation Prefill/Decode launch commands and environment for
  Path C. Rewrite only network fields plus computed kv_port/engine_id/dp_size;
  never rename kv_connector. Renders mooncake_master + dual proxy (fetched from
  vllm-ascend). Use for PD ratio / PD deploy check.
---

# pd-config-env-check

路径 C · Phase 1。校验用户 PD 分离拉起命令与执行环境，按公式补齐 PD 参数，产出可执行 `rendered/`（含 **Mooncake master**）。

详文：[`references/kv-connector-and-params.md`](references/kv-connector-and-params.md)  
官方拉起回退：[`references/official-model-launch.md`](references/official-model-launch.md)（索引：[模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/)）

## 输入

| 项 | 说明 |
| --- | --- |
| `workdir` | 默认 `./workspace` |
| `config_md_path` | 默认 `{workdir}/pd-deploy-config.md` |
| 输出根 | `{workdir}/pd-ratio/check/` |

## 部署顺序（硬约束，写入产物）

```text
0. mooncake_master   （默认必须；skip_mooncake_master=true 可跳过）
1. Prefill
2. Decode
3. Proxy
```

## KV / 改写边界（摘要）

- **保留** `kv_connector` 原值；禁止改名。
- **仅可自动替换**：`kv_port` / `engine_id` / `*.dp_size` + 网络字段——且 **优先采用用户拉起命令中已写明的值**；公式仅作缺省回退。
- **只校验不改**：`kv_role`、`tp_size`、`kv_buffer_device`、`kv_parallel_size`、`kv_rank`、模型路径等。
- **用户已验证 / 官方回填的拉起命令**：除上述允许字段外，**禁止**擅自改 `LD_LIBRARY_PATH`、MTP/`--speculative-config`、`VLLM_WORKER_MULTIPROC_METHOD`、模型路径、端口、量化、`ASCEND_RT_VISIBLE_DEVICES` 等；跑不起来须**停下来列出选项并等用户确认**，禁止自行改参试错。
- **拉起命令缺失**：不得编造；按 [`official-model-launch.md`](references/official-model-launch.md) 从官方模型教程回填（优先 PD 分离章 + 匹配 A2/A3）。

## 拉起命令来源（用户优先，官方回退）

| 来源 | 条件 |
| --- | --- |
| **user** | Prefill（及 Decode）段已有可执行 bash |
| **official_docs** | 上述段为空/仅占位 → 打开 [模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/)，按 **模型名称** 定位页面，取与 **设备类型** 匹配的 A2/A3 命令；**kv_role / kv_connector 优先 PD 分离** 小节；**TP/DP 与可见卡取单实例命令**（见 `official-model-launch.md`），禁止把整机 DP 当最小实例 |
| **failed** | 教程无该模型或无可用 PD/在线命令 → 停止并请用户补命令 |

回填后在报告写明 `launch_cmd_source` / `official_docs_url`；权重路径若仍为文档占位须标 `weight_path_needs_user_confirm`。

## 同机共置 1P1D（实测硬规则）

### 最小 P/D 实例 size = 拉起命令 DP × TP

```text
min_P_instance_npus = DP_P × TP_P   # 来自 Prefill 拉起命令
min_D_instance_npus = DP_D × TP_D   # 来自 Decode 拉起命令
```

- TP：`--tensor-parallel-size` / `"tp_size"`
- DP：`--data-parallel-size` / 单实例本地 `"dp_size"`
- 该角色 `npu_count`（可见卡）须与 `DP×TP` 对齐；**不是**用整机 8/16 卡当「最小实例 size」
- **配比 QPS 基线（硬）**：只拉 **1 个最小 P + 1 个最小 D**，测试**不必使用全部卡**。`npu_ids` 为空时按 `compute_pd_params.py` 输出的 `suggested_p_npu_ids` / `suggested_d_npu_ids` 填写；`leftover_npu_ids` **不写入** P/D 行、不出现在 `ASCEND_RT_VISIBLE_DEVICES`。禁止半机硬拆（如 A2 8 卡写成 4P+4D）或加大 DP 占满整机。
- 例：官方 `--tensor-parallel-size 2 --data-parallel-size 1` → 最小实例 2 卡；同机 1P1D 则 P=`0,1`、D=`2,3`，卡 4–7 空闲。

同一 `host_ip` 上 P/D 拆卡共置时：

1. **禁止**用 `dp_size_local = npu_per_node / tp`（会把 A2+TP4 错算成 2，也会把整机卡算进实例）。改用拉起命令 `--data-parallel-size`，或该角色 `npu_count`（须已是 `DP×TP`）÷ `tp_size`。无 DP 时回退 `dp_local=1`，**禁止**用整机公式填满。
2. **禁止**把用户已验证的 `LOCAL_IP=127.0.0.1` / `NIC_NAME=lo` / `HCCL_IF_IP` 改写成机器外网 IP。
3. **禁止**改写用户已写明的 `--port`、`kv_port`、`engine_id` 去「对齐」默认公式（如 7100 / 36000）。
4. Proxy 展开：`dp_size_local=1` 时每个角色各 1 个 host:port；端口取用户 Prefill/Decode `--port`。
5. **一机一容器**：同 host 上 mooncake_master / P / D / proxy **共用同一 `container_name`**；多 vLLM 靠端口与 `ASCEND_RT_VISIBLE_DEVICES` 区分，禁止再为 P/D 各建一个容器。

## 容器保障（未指定则 Agent 拉起）

详见 [`scripts/env_check_helpers.md`](scripts/env_check_helpers.md) 与 [`scripts/ensure_host_container.sh`](scripts/ensure_host_container.sh)。  
官方 A2/A3 分 tab 参考：[GLM-5 Docker 安装](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/GLM5.html#__tabbed_1_2)。

### 宿主机白名单（硬约束）

SSH 宿主机后 **只允许 docker 相关指令**（`docker ps|inspect|run|start|exec|cp|logs|pull` 及用于 `docker run` 的 ensure 脚本）。  
**禁止**在宿主机执行 `npu-smi`、装包、改系统/网卡、业务拉起、压测等；NPU / Mooncake / vLLM / AISBench **一律 `docker exec` 进容器**。

| 情况 | 行为 |
| --- | --- |
| 已填 `container_name` 且 running | 复用 |
| 未填 / 容器不存在 / 已退出 | **Agent 按设备类型 docker run 或 start**（每 `host_ip` 仅一个容器） |

默认镜像选择（可用基本参数 `docker_image` **显式覆盖**；未指定时 **高版本优先**）：

| 设备类型 | 候选 tag（高→低） | NPU devices |
| --- | --- | --- |
| A2 | `v0.23.0rc1` → `v0.22.1rc1` | `davinci0`–`davinci7` |
| A3 | `v0.23.0rc1-a3` → `v0.22.1rc1-a3` | `davinci0`–`davinci15` |

解析顺序（仅 docker*）：对每个候选 `docker image inspect` 本地命中即用 → 否则 `docker pull` → 失败则试下一个更低版本；全部失败则 `failed`。仓库前缀：`quay.io/ascend/vllm-ascend:`。有新版本时把更高 tag **插到候选列表最前**。

### 多机镜像一致（硬约束）

配置中出现 **≥2 个不同 `host_ip`** 时：

1. **必须**全集群使用 **同一** `IMAGE` 引用（含 tag）；禁止各机各自高→低回退导致版本不一致。
2. 流程：先在**一台**宿主机上完成镜像解析（用户 `docker_image` 或高版本优先回退）→ 得到 `IMAGE_SELECTED` → **所有** host 的 `ensure_host_container.sh` / `docker run` **一律**带同一 `--image "$IMAGE_SELECTED"`（只 pull/用该 tag，不再本机单独降级）。
3. 若某机已有 running 容器但 `Config.Image` 与 `IMAGE_SELECTED` 不一致 → **不得**静默混用；`pd-check-status=failed`（或停容器后按统一镜像重建，须在报告写明并征得用户确认若会中断已有服务）。
4. 单机部署不受影响（仍可本机高版本优先回退）。

其余与官方一致：`--privileged`、`--security-opt label=disable`（openEuler/SELinux 上与同机可跑 NPU 的容器一致；缺省时 CANN 对 OPP proto 做 `realpath` 会 EPERM，表现为 `SpaceRegistry is nullptr` / `ZerosLike` errno 361001）、`--net=host`、`--shm-size=1g`、Ascend 控制设备与 driver volumes。Agent 常驻用 `-d` + `sleep infinity`（官方文档为 `-it ... bash` / `--rm`，需改 `NAME`/`IMAGE`）。**不要**在宿主机 root 盘已满时绑定 `-v /root/.cache:/root/.cache`；权重在 `/home` 时加 `-v /home:/home`。

未指定名字时生成合法名（如 `vllm-ascend` 或由模型名 slug）；**须**把最终 `container_name` 写回报告（同 host 各 role 行一致）。

拉起后在**容器内**做 NPU / Mooncake 校验；Mooncake 须镜像预装或用户已装——Agent **不安装** Mooncake。

## Mooncake 预装硬门禁（Phase 1 必做）

容器内 **必须已具备** Mooncake（镜像预装或用户已装）；Agent **不得**现场安装、不得擅自改用户拉起命令里的库路径「试错」。

### 交互式环境对齐（高频坑，必须遵守）

用户通常在 `docker exec -it` **交互壳**里验证配置；交互壳会 source `~/.bashrc`，其中常追加如 `/usr/local/lib`（`libtransfer_engine.so` 所在目录）。

| 方式 | 是否带上 `.bashrc` 中的库路径 | 结果 |
| --- | --- | --- |
| 用户 `docker exec -it` 后再跑配置 | 是 | 用户侧可拉起 |
| Agent `docker exec -d bash -lc ...`（非交互 login） | **否**（只读 `/etc/profile` 等） | 易报 `libtransfer_engine.so: cannot open shared object file` |

**硬规则**：

1. Phase 1 Mooncake **import 校验**与 Phase 3 **启动**，必须使用**交互等价环境**：`bash -ic`，或先 `source ~/.bashrc`（及容器内同等 profile）再执行用户命令。
2. **禁止**因非交互缺库就改写用户 `LD_LIBRARY_PATH`（例如擅自插入 `/usr/local/lib`）；缺的是启动方式，不是用户已验证配置。
3. 校验/启动日志须注明：`shell=interactive_equiv`（`bash -ic` 或 `source ~/.bashrc`）。

### 校验步骤

1. 从 Prefill/Decode 拉起命令解析用户声明的 Mooncake 相关路径（至少 `LD_LIBRARY_PATH` 中含 `mooncake` 的目录；若有 `MOONCAKE_CONFIG_PATH` 一并记录）。
2. 在每个 P/D（及将跑 `mooncake_master` 的）容器内按 [`scripts/env_check_helpers.md`](scripts/env_check_helpers.md) **Mooncake 节**执行校验（**必须**交互等价壳）：
   - 用户 `LD_LIBRARY_PATH` 中的 mooncake 目录存在且可读；
   - 在「交互等价 env + 用户命令中的 `export LD_LIBRARY_PATH=...`」下，`libtransfer_engine.so` 可解析；
   - 同上环境下 `python -c "from mooncake.engine import TransferEngine"` 成功；
   - 若 `require_mooncake_master=true`：`command -v mooncake_master` 成功。
3. **仅当**交互等价环境下仍失败 → `pd-check-status=failed`，写明缺失项，**停止**进入 Phase 2；与用户核对预装/配置。若仅非交互失败而交互成功 → 记为 Agent 启动方式问题，纠正为交互等价启动，**不得**改用户配置。
4. **禁止**：把 `/usr/local/lib` 等路径偷偷塞进用户命令；禁止 `pip install mooncake`；禁止用猜测路径继续渲染/部署。

## Agent 步骤

1. Read 本 SKILL、`references/kv-connector-and-params.md`、`references/official-model-launch.md`、`pd-check-report-template.md`。
2. 解析 `pd-deploy-config.md`。
3. **解析拉起命令来源**：若 Prefill/Decode 缺失 → 按模型名从官方教程回填（见上节）；找到则写入命令源并记录 URL；找不到 → `failed` 停止。
4. **按 host 保障容器**（见「容器保障」）：
   - 统计 distinct `host_ip`；
   - **多机（≥2）**：先解析一次 `IMAGE_SELECTED`，再对每台 `ensure_host_container.sh --image "$IMAGE_SELECTED" ...`；校验各机最终 `Config.Image` 一致；
   - **单机**：可本机高版本优先回退；
   - 同 host 统一 `container_name`。
5. 计算参数：

```bash
python configuration-tuning-skills/pd-config-env-check/scripts/compute_pd_params.py \
  --config {config_md_path} \
  --json {workdir}/pd-ratio/check/pd-params.json
```

若机器表 `npu_ids`/`npu_count` 为空：把 `suggested_p_npu_ids` / `suggested_d_npu_ids` 写回配置与 `ASCEND_RT_VISIBLE_DEVICES`（仅最小实例）；`leftover_npu_ids` 保持空闲。禁止按半机/整机填卡。

6. 一致性校验：

```bash
python configuration-tuning-skills/pd-config-env-check/scripts/validate_pd_config.py \
  --config {config_md_path} \
  --params-json {workdir}/pd-ratio/check/pd-params.json \
  --json {workdir}/pd-ratio/check/validate.json
```

`ok=false` → `pd-check-status=failed`，列出 errors 给用户改配置。

7. 渲染（含 mooncake + 拉取真实 proxy）：

```bash
python configuration-tuning-skills/pd-config-env-check/scripts/render_pd_launch.py \
  --config {config_md_path} \
  --out-dir {workdir}/pd-ratio/check/rendered \
  --params-json {workdir}/pd-ratio/check/pd-params.json \
  --proxy-local-dir {optional: repos/vllm-ascend/examples/disaggregated_prefill_v1} \
  --json {workdir}/pd-ratio/check/network-rewrite.json
```

若 `proxy_fetch.ok=false`：报告警告；部署（Phase 3）前必须补齐真实 proxy（本地仓或网络重试），否则部署失败回退。

8. 环境检查（`scripts/env_check_helpers.md`）：含容器状态（已 ensure）、mooncake master 目标机 ping，以及 **Mooncake 预装硬门禁**。Mooncake 校验失败则直接 `failed` 并停止。
9. 写 `pd-check-report.md` + `pd-check-status.md`（须含 `launch_cmd_source`、容器创建/复用、Mooncake 校验）。

## 产物

```text
{workdir}/pd-ratio/check/
  pd-check-report.md
  pd-check-status.md
  pd-params.json
  validate.json
  network-rewrite.json
  rendered/
    mooncake/
      start_mooncake_master.sh
      mooncake.json
      README.md
    prefill/
    decode/
    proxy/
      start_proxy.sh
      load_balance_proxy_*.py   # 真实脚本（fetch）
```

## 边界

- **允许**拉起命令为空时从 [官方模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/) 回填；教程无匹配则停止，禁止编造。
- **允许**在 `npu_ids` 为空时按最小实例（`DP×TP`）切卡并写回；禁止为 QPS 基线占满整机或加大 DP。
- **允许**在未指定/缺失时按设备类型（A2/A3 分模板）「一机一容器」创建容器；禁止同机为 P/D 各建容器；禁止改非允许字段；禁止擅自改写用户已验证的拉起命令。
- **多机必须同一镜像 tag**；禁止各机各自回退成不同版本。
- **宿主机只允许 docker 相关指令**；禁止宿主机执行非容器指令。
- Mooncake **须容器内可用**（镜像预装或用户已装）；路径以用户配置为准提前校验；缺失则停止并说明，禁止安装或猜测路径。
- Mooncake master 默认必启；集群已有 master 时由用户设 `skip_mooncake_master: true`。
