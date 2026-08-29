---
name: aisbench-install
description: >-
  Probe or install AISBench from source inside a target container for PD-ratio
  benchmarking. Runs after pd-config-env-check and before pd-deploy. Skip if
  ais_bench is already available. Pin numpy for vLLM Ascend co-install.
  Sub-skill 2 of pd-ratio-benchmark.
---

# aisbench-install

## 调用约定

`pd-ratio-benchmark` 的第 2 个子 skill。Read 本 `SKILL.md` 后在当前会话执行。产物写 `{workdir}/pd-ratio/aisbench/`。前置：`pd-check-status.md` = `passed`。

**部署前**在目标容器内探测或源码安装 [AISBench](https://github.com/AISBench/benchmark)，确保后续部署完成后可立刻压测。

## 前置

- `pd-check-status.md` 为 `passed`。
- 目标容器来自 `pd-deploy-config.md` / Phase 1 报告（优先 **Prefill 容器**，或用户指定）；容器须已存在且可联网（clone + pip）。
- **不依赖** PD 服务已部署（本 Phase 在部署之前）。

## 探测（先做）

在目标容器内：

```bash
command -v ais_bench && ais_bench -h
```

若帮助信息正常打印 → `already_installed=true`，`status=skipped`，仍可进入 Phase 3 部署。  
**即使 skipped**：若目标容器还将跑 vLLM，仍须做下一节 **numpy 兼容检查**（历史安装可能已把 numpy 升到 2.5+）。

## 安装步骤（首选源码）

在工作目录（建议 `{workdir}/pd-ratio/aisbench/src` 或容器内约定目录）：

```bash
git clone https://github.com/AISBench/benchmark.git
cd benchmark/
# 国内网络优先使用镜像源（阿里云 / 清华）
pip3 install -e ./ --use-pep517 \
  -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip3 install -r requirements/api.txt \
  -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip3 install -r requirements/extra.txt \
  -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
ais_bench -h
```

备用 index：`https://pypi.tuna.tsinghua.edu.cn/simple`。默认 PyPI 过慢或卡住时改用国内镜像，勿长时间干等。

成功判据：`ais_bench -h` 打印 AISBench 评测工具帮助信息。

## numpy / Numba 兼容硬门禁（与 vLLM 同容器时必做）

AISBench 依赖可能把 `numpy` 升到 **2.5+**，而 vLLM Ascend worker（Numba）实测会直接失败：

```text
ImportError: Numba needs NumPy 2.4 or less. Got NumPy 2.5
```

这会导致 Phase 3 Prefill/Decode **Engine core initialization failed**，与业务启动参数无关。

**硬规则**（安装目标 == 将跑 vLLM 的 P/D 容器时）：

1. 安装或 skip 探测之后执行：

```bash
python3 -c "import numpy; print(numpy.__version__)"
```

2. 若主版本为 `2.5+`（或 Numba 报错），立即钉回兼容区间后再交付 `passed`：

```bash
pip3 install 'numpy>=2.0,<2.5' \
  -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

3. 在报告中记录 `numpy_before` / `numpy_after`。  
4. 更稳妥：AISBench 装到**不跑 vLLM** 的独立容器/venv，经网络访问 proxy（可避免与 serving 抢依赖）。

> 说明：AISBench 声明可能要求 `numpy<2.0`，与 Numba/`numpy<2.5` 存在张力；同容器共装时优先保证 **vLLM 可启动**（`<2.5`），并以 `ais_bench -h` 仍可用为准。

## Agent 步骤

1. Read 本 SKILL 与 `workflows/templates/aisbench-install-report-template.md`。
2. 验收检查步骤 `passed`；从配置/检查报告选容器（优先 Prefill；用户指定优先）。
3. 探测 → 安装或跳过 → **numpy 兼容检查/钉回** → 写报告与 status。
4. 国内环境：**默认走阿里云 PyPI**；默认 PyPI 卡住超过约 1–2 分钟即切换镜像，勿长时间干等。
5. `failed` → **不得**进入子 skill 3 部署。

## 产物

```text
{workdir}/pd-ratio/aisbench/
  aisbench-install-report.md
  aisbench-install-status.md
```

`status`：`passed` | `skipped` | `failed`（前两者可进 Phase 3 部署）。
