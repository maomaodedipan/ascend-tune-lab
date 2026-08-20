# 环境检查与容器保障命令模板

参考：[GLM-5 安装 · Docker（A3/A2 分 tab）](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/GLM5.html#__tabbed_1_2)

## 宿主机指令白名单（硬约束）

SSH 到宿主机后，**只允许容器相关指令**，禁止执行其他宿主机命令（如宿主机 `npu-smi`、改驱动/系统包、改网卡、写业务脚本到宿主机任意路径等）。

| 允许（宿主机） | 禁止（宿主机） |
| --- | --- |
| `docker ps` / `docker inspect` / `docker start` / `docker run` / `docker exec` / `docker cp` / `docker logs` / `docker pull` | 宿主机直接跑 `npu-smi`、`apt`、`pip`、改 `/etc`、业务拉起、压测 |
| 将 `ensure_host_container.sh` 传到临时路径后 `bash` 执行（仅用于 `docker run`） | 在宿主机安装 Mooncake / AISBench / 改 LD_LIBRARY_PATH |

**NPU / Mooncake / vLLM / AISBench 一律 `docker exec` 进容器后再做。**

## 容器策略（一机一容器）

| 情况 | Agent 行为 |
| --- | --- |
| 用户已填 `container_name` 且 `running` | 复用；同 `host_ip` 上 P/D/proxy/mooncake **共用该容器** |
| 未填 `container_name` | 按设备类型生成名字并 **docker run** |
| 已填名字但容器不存在 / 已退出 | **创建或 `docker start`** |

同一 `host_ip` 只保留 **一个** 容器；多个 vLLM 在容器内用不同端口 / `ASCEND_RT_VISIBLE_DEVICES` 拉起。

### 默认镜像（未指定 `docker_image` 时：高版本优先）

| 设备类型 | 候选（高→低） |
| --- | --- |
| A2 | `quay.io/ascend/vllm-ascend:v0.23.0rc1` → `...:v0.22.1rc1` |
| A3 | `quay.io/ascend/vllm-ascend:v0.23.0rc1-a3` → `...:v0.22.1rc1-a3` |

解析：本地 `docker image inspect` 命中 → 用；否则 `docker pull`；失败则试更低版本。用户指定 `docker_image` / `--image` 则只解析该镜像（不回退）。`--name` 必须按环境修改。

**多机硬约束**：≥2 台 `host_ip` 时，先解析一次 `IMAGE_SELECTED`，所有机器 `ensure_host_container.sh --image "$IMAGE_SELECTED"`；禁止各机独立回退成不同 tag。已有容器镜像不一致 → failed（或经确认后按统一镜像重建）。

### 推荐：仓库脚本（宿主机仅 docker）

```bash
# 仅 docker 相关：把脚本 docker cp / scp 后执行
bash /tmp/ensure_host_container.sh --name {container_name} --device-type {A2|A3}
# 或 --image $IMAGE 覆盖默认镜像
```

### A3 拉起模板（官方 tab；Agent 用 -d + sleep infinity 常驻）

```bash
export IMAGE=quay.io/ascend/vllm-ascend:v0.23.0rc1-a3   # 或回退到 v0.22.1rc1-a3
export NAME={container_name}

docker run -d \
  --name $NAME \
  --privileged \
  --security-opt label=disable \
  --net=host \
  --shm-size=1g \
  --device /dev/davinci0 \
  --device /dev/davinci1 \
  --device /dev/davinci2 \
  --device /dev/davinci3 \
  --device /dev/davinci4 \
  --device /dev/davinci5 \
  --device /dev/davinci6 \
  --device /dev/davinci7 \
  --device /dev/davinci8 \
  --device /dev/davinci9 \
  --device /dev/davinci10 \
  --device /dev/davinci11 \
  --device /dev/davinci12 \
  --device /dev/davinci13 \
  --device /dev/davinci14 \
  --device /dev/davinci15 \
  --device /dev/davinci_manager \
  --device /dev/devmm_svm \
  --device /dev/hisi_hdc \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/Ascend/driver/tools/hccn_tool:/usr/local/Ascend/driver/tools/hccn_tool \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
  -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info \
  -v /etc/ascend_install.info:/etc/ascend_install.info \
  -v /root/.cache:/root/.cache \
  $IMAGE sleep infinity
```

官方交互调试等价（须改 `NAME`/`IMAGE`；加 `-d` 以免会话结束退出）：

```bash
docker run -itd --name $NAME ...同上 devices/volumes... $IMAGE bash
```

### A2 拉起模板（官方 tab；仅 davinci0–7）

```bash
export IMAGE=quay.io/ascend/vllm-ascend:v0.23.0rc1   # 或回退到 v0.22.1rc1
export NAME={container_name}

docker run -d \
  --name $NAME \
  --privileged \
  --security-opt label=disable \
  --shm-size=1g \
  --net=host \
  --device /dev/davinci0 \
  --device /dev/davinci1 \
  --device /dev/davinci2 \
  --device /dev/davinci3 \
  --device /dev/davinci4 \
  --device /dev/davinci5 \
  --device /dev/davinci6 \
  --device /dev/davinci7 \
  --device /dev/davinci_manager \
  --device /dev/devmm_svm \
  --device /dev/hisi_hdc \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/Ascend/driver/tools/hccn_tool:/usr/local/Ascend/driver/tools/hccn_tool \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
  -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info \
  -v /etc/ascend_install.info:/etc/ascend_install.info \
  -v /root/.cache:/root/.cache \
  $IMAGE sleep infinity
```

> A2/A3 **不得混用**设备列表或镜像 tag。A3 必须挂满 davinci0–15 + `*-a3` 镜像；A2 仅 0–7 + 非 a3 镜像。  
> **容器权限（硬）**：A2/A3 模板必须带 `--privileged` 与 `--security-opt label=disable`。缺省时 CANN 对 OPP proto 目录 `realpath` 会 EPERM，Worker/`torch.zeros` 报 `SpaceRegistry is nullptr` / `ZerosLike` 361001。openEuler 同机可跑 NPU 的容器均为 privileged。

### 状态检查（宿主机仅 docker）

```bash
docker inspect -f '{{.State.Status}}' {container_name}
# 期望：running
```

## 容器内检查（经 docker exec）

```bash
docker exec {container_name} bash -lc 'npu-smi info -l || true'
```

角色级卡隔离靠拉起命令里的 `ASCEND_RT_VISIBLE_DEVICES` / `npu_ids`。

## 交互等价壳（部署/Mooncake 校验必用）

```bash
docker exec {container_name} bash -ic 'your_command'
# 或
docker exec {container_name} bash -lc 'source ~/.bashrc 2>/dev/null || true; your_command'
```

后台拉起：

```bash
docker exec -d {container_name} bash -ic 'nohup bash /path/to/user_launch.sh > /tmp/pd-logs/prefill.log 2>&1 &'
```

## Mooncake 预装与路径（硬门禁 · 容器内）

```bash
docker exec {container_name} bash -ic '
  set -e
  echo shell=interactive_equiv
  test -d {mooncake_lib_dir} || { echo MISSING_MOONCAKE_DIR; exit 2; }
  export LD_LIBRARY_PATH={mooncake_lib_dir}:$LD_LIBRARY_PATH
  python -c "from mooncake.engine import TransferEngine; print(\"TransferEngine_OK\")" \
    || { echo IMPORT_TransferEngine_FAIL; exit 4; }
  command -v mooncake_master >/dev/null && echo mooncake_master_OK || echo mooncake_master_MISSING
'
```

- 交互等价下仍失败 → `pd-check-status=failed`。
- **禁止**为过检把路径塞进用户 `rendered` 命令；**禁止**在宿主机安装 Mooncake。
