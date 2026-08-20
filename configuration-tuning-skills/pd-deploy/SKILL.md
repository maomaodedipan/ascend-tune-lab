---
name: pd-deploy
invoke: pipeline-only
description: >-
  Deploy Mooncake master then Prefill/Decode/Proxy from Path C rendered scripts.
  Use after pd-config-env-check and aisbench-install. On failure diagnose and
  rollback to Phase 1.
---

# pd-deploy

## 调用约定

`invoke: pipeline-only`。仅由路径 C Phase 3 的 `serving-pd-deploy-subagent` 以 `invoke=pipeline` 调用。产物写 `{workdir}/pd-ratio/deploy/`。禁止独立部署。约定见 `configuration-tuning-skills/README.md`。

路径 C · Phase 3。严格使用 `{workdir}/pd-ratio/check/rendered/` 启动服务。

## 前置硬门禁

1. `pd-check-status.md` = `passed`（其中须已通过 **Mooncake 预装/路径** 校验）。
2. `aisbench-install-status.md` = `passed` 或 `skipped`（**部署前**已完成 AISBench 探测/安装）。
3. `rendered/mooncake|prefill|decode|proxy` 齐全。
4. Proxy 脚本为**真实** Python（`proxy_fetch.ok=true` 或文件体积明显非占位）；否则先补齐再部署。
5. **禁止**用未渲染的 `pd-deploy-config.md` 原文启动。
6. **禁止擅自试错（须用户确认才能改配置再试）**：官方回填与用户命令同等。第一次拉起失败 → **停止、诊断、问用户**。禁止自行去掉 `--speculative-config`（MTP）、增删 `VLLM_WORKER_MULTIPROC_METHOD` 等命令中没有的环境变量、改写 `LD_LIBRARY_PATH`、模型路径、端口或其他业务字段后再重试。

## 启动顺序（硬约束）

| 顺序 | 组件 | 脚本 |
| --- | --- | --- |
| **0** | **Mooncake master** | `rendered/mooncake/start_mooncake_master.sh`（若 `mooncake_master.required=true`） |
| 1 | Prefill | `rendered/prefill/*.sh` |
| 2 | Decode | `rendered/decode/*.sh` |
| 3 | Proxy | `rendered/proxy/start_proxy.sh`（`PROXY_TYPE`） |

若 `skip_mooncake_master=true`：跳过步骤 0，但须在报告注明「用户确认集群已有 master」，并记录 `master_server_address`。

Mooncake master 参考命令（仅当 Phase 1 已确认容器预装且路径一致；**不要**在此追加用户未声明的库路径）：

```bash
mooncake_master --port 50088 \
  --eviction_high_watermark_ratio 0.9 \
  --eviction_ratio 0.1 \
  --default_kv_lease_ttl 11000
```

各节点使用 `rendered/mooncake/mooncake.json`（或用户配置的 `MOONCAKE_CONFIG_PATH`）。

## Agent 步骤

1. Read 本 SKILL 与 `pd-deploy-report-template.md`。
2. 再次确认 Phase 1 Mooncake 门禁已通过；未通过则拒绝部署。
3. 按上表顺序**在已 ensure 的容器内**启动；每步做端口/进程检查。同一 host 上多个 vLLM（P/D）共用一容器，靠端口与 `ASCEND_RT_VISIBLE_DEVICES` 区分。启动命令内容须与 Phase 1 `rendered/` 一致。
   **基线只拉最小 1P1D**：每个实例可见卡 = `DP×TP`；剩余卡保持空闲，禁止额外拉满机 DP/多实例来「把卡用完」。
4. **启动壳硬约束**：一律 `docker exec` + **交互等价环境**（`bash -ic` 或先 `source ~/.bashrc`）。宿主机 **禁止**非 docker 指令；**禁止**因此改写用户 `LD_LIBRARY_PATH`。
5. Proxy：`PROXY_TYPE=basic|layerwise bash start_proxy.sh`（禁止凭 connector 名猜）；同样在交互等价壳中启动。
6. **健康检查**（按优先级）：
   - Mooncake master：**进程存活**（`pgrep -af mooncake_master`）；容器内未必有 `ss`，勿把 `ss` 当唯一判据；
   - Prefill / Decode：`GET /v1/models` 返回 served-model（模型加载可达十余分钟，等待循环须足够长，例如 20–30min 量级）；
   - Proxy：**以 `POST /v1/chat/completions` 冒烟成功为准**。部分 example proxy 对 `GET /v1/models` 返回 **404** 仍属正常，**不得**仅因 models 404 判部署失败。P/D ready 后再起 proxy，并稍等再冒烟。
7. **AISBench 同容器安装后的启动失败**：若日志出现 `Numba needs NumPy 2.4 or less` / `Got NumPy 2.5`，属 Phase 2 依赖污染，**钉回 `numpy<2.5`** 后重试 Prefill/Decode（见 `aisbench-install`）；勿改用户 `LD_LIBRARY_PATH` 或业务启动参数。
8. 成功 → report + `status=passed`（含 `proxy_base_url`、served `model` 名若已知、`mooncake_master_address`；注明 `shell=interactive_equiv`）。
9. 失败 → **停止**，落盘诊断 + `rollback_to_phase1=true`，**向用户列出失败点与可选改法并等待确认**；禁止在未确认前改 MTP / spawn / `LD_LIBRARY_PATH` / 其它启动参数后重试。Primary 不得进 Phase 4。

## 产物

```text
{workdir}/pd-ratio/deploy/
  pd-deploy-report.md
  pd-deploy-status.md
```

## 边界

- 不修改 `rendered/`；需改配置则回退 Phase 1 并由用户确认。
- 不安装 Mooncake / AISBench、不压测（numpy 钉回属于修复 AISBench 安装副作用，允许）。
- 宿主机只允许 docker*；业务一律 `docker exec`。
- 拉不起来只诊断与核对；官方回填命令同样不得自作主张改参试错。
