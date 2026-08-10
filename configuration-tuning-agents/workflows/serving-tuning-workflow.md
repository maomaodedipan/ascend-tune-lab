# 路径 A · 服务化调优工作流

由 primary 在选定 **路径 A（服务化调优）** 后强制 Read 并严格推进。  
顶层路由见 [`primary-workflow.md`](primary-workflow.md)。

**范围**：Phase 0 配置门禁 → Phase 1 基线配置生成 → Phase 2 **离线并行策略调优**（入口 skill `serving-parallel-strategy-tuning` + 三子 skill）。

> 用户输入：先定 `workdir`（未指定则 `./workspace`），再在其中放 MD 配置（默认 `deploy-config.md`）。`## 基本参数` 必填，`## 服务化配置` / `## SLO约束` 可选。格式见 [`references/user-config-format.md`](references/user-config-format.md)。

## 报告落盘约定（硬要求）

**运行过程中生成的全部报告 / 中间产物 / 汇总状态，一律写在工作目录（`workdir`）下**。

| 类别 | 路径（相对 `workdir`） |
| --- | --- |
| 用户配置 | `deploy-config.md`（或用户指定的 `config_md_path`） |
| 模型 config | **`model_config.json`**（Phase 0 从 ModelScope 下载；失败则用户手供） |
| Case 根 | `{case_dir}/`（默认 `cases/<model>-<device>/`） |
| Phase 1 | `{case_dir}/baseline/`（`baseline-launch.sh`、`baseline-summary.md` 等） |
| Phase 2 报告 | `{case_dir}/tuning/`（`tuning-process.md` / `.json`、`tuning-status.md`、各阶段 JSON） |
| 源码仓（独立） | **`repos/`**（`vllm-ascend`、`msmodeling`；跨 case 复用） |
| 进度 | `{case_dir}/progress.md` |

## 流程总览

```text
+--------------------------------------------------------------+
| Phase 0 · 工作目录 + 配置文件 + 模型 config                     |
|    未指定 workdir → 创建并使用 ./workspace/                      |
|    默认 {workdir}/deploy-config.md；不存在则生成模板并停止     |
|    未填完 ## 基本参数 → 停止                                   |
|    ModelScope 下载 model_config.json；失败 → 警告并要求手供    |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Phase 1 · 基线配置生成 【serving-baseline-reproduce-subagent】|
|    读取配置 → 匹配 baseline → baseline-launch.sh + baseline-summary.md   |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
| Phase 2 · 并行策略调优 【serving-tuning-subagent】            |
|    SLO(读/问/默认) → clone → 三子 skill                       |
|    → tuning-process.* + tuning-status.md                     |
+--------------------------------------------------------------+
```

## Subagent 映射

| Phase | Subagent | 状态 |
| --- | --- | --- |
| 1 | `serving-baseline-reproduce-subagent` | **已实现** |
| 2 | `serving-tuning-subagent` | **已实现（离线）** |

派发模板见 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)。

## 执行规则

进入本路径后建立 TaskList，**严格按 Phase 0 → 1 → 2 顺序**推进。

### 全局约束

- **路径互斥**：本路径内 **禁止**派发 `serving-profiling-analysis-subagent`。
- **workdir 默认**：未指定则创建并使用 `{cwd}/workspace`。
- **配置文件硬门禁**：`workdir` 无合法配置文件，或 `## 基本参数` 未填完 → **不得进入 Phase 1**。
- **模型 config 硬门禁**：Phase 0 必须拿到 `{workdir}/model_config.json`；缺失则 **不得进入 Phase 1**。
- **报告落盘硬门禁**：全部生成报告只写 `workdir` 内。
- **Phase 1 硬门禁**：无 `baseline-launch.sh` 与 `baseline-summary.md` 不得进入 Phase 2。
- **Phase 2 约束**：禁止部署/压测/改写 `baseline-launch.sh`；clone 目标为 **`{workdir}/repos/`**。
- **源码仓下载失败**：警告用户并要求手供后重试；不得静默跳过（测试 `--allow-without-repos` 除外）。
- **流水线终点**：`{case_dir}/tuning/tuning-status.md` + `{case_dir}/tuning/tuning-process.md`。
- **进度文件**：`{case_dir}/progress.md`。

### TaskList 骨架

```text
T0. 确定 workdir；定位/生成/校验 deploy-config.md（Phase 0）
T0b. 从 ModelScope 下载模型 config → {workdir}/model_config.json；失败则警告并停止
T1. 确定 case_dir（默认在 workdir 下）
T2. 派发 serving-baseline-reproduce-subagent（Phase 1）
T3. 用户确认低时延/高吞吐（若 Phase 1 回报双匹配）
T4. Primary 验收 baseline-summary.md
T5. 派发 serving-tuning-subagent（Phase 2）
T6. Primary 验收 tuning-process.md + tuning-status.md，路径 A 结束
```

## Phase 0 · 工作目录 + 配置文件

### 配置文件路径

| 优先级 | 来源 | 路径 |
| --- | --- | --- |
| 1 | 用户在消息中指定 | 用户给出的 `config_md_path` |
| 2 | 默认 | **`{workdir}/deploy-config.md`** |

### Primary 步骤

1. Read [`references/user-config-format.md`](references/user-config-format.md)。
2. **确定 `workdir`**：用户指定 → 否则创建并使用 `{cwd}/workspace`；告知用户。
3. 确定 `config_md_path`（见上表）。
4. **文件不存在**：在 `workdir` 生成模板并停止。
5. **文件存在但未填完**：列出缺失项并停止。
6. **校验通过后立刻下载模型 config（硬门禁）**：
   ```bash
   python configuration-tuning-skills/serving-parallel-strategy-tuning/scripts/download_modelscope_config.py \
     --workdir {workdir} \
     --config {config_md_path} \
     --json
   ```
   - 成功 → `{workdir}/model_config.json` + `{workdir}/model_config.fetch.json`，继续。
   - 已存在合法 `model_config.json` → 复用。
   - **失败** → 给出脚本 `warning`，**停止**，不得进入 Phase 1。
7. 记录 `workdir`、`config_md_path`、`model_config_path`，进入 Phase 1。

### case_dir

- 默认 `{workdir}/cases/<model>-<device>-<quant>/`。
- 可选：复制配置 / `model_config.json` 到 `{case_dir}/` 归档。

## Phase 1 · 基线配置生成

1. 传入已校验的 `config_md_path` 与 `case_dir`。
2. 按模板派发 `serving-baseline-reproduce-subagent`。
3. 产出须符合 [`templates/baseline-summary-template.md`](templates/baseline-summary-template.md)。
4. Primary Read `{case_dir}/baseline/baseline-summary.md`，确认完整后进入 Phase 2。

## Phase 2 · 并行策略调优

1. 派发 `serving-tuning-subagent`（模板见 subagent-prompt-templates § Phase 2）。
2. Subagent：SLO → clone → 三子 skill。
3. Primary 验收 `{case_dir}/tuning/tuning-process.md` 与 `{case_dir}/tuning/tuning-status.md`（`status=completed`）。
4. 路径 A 结束；交付：`{case_dir}/baseline/baseline-launch.sh` + `{case_dir}/tuning/` 下报告。
