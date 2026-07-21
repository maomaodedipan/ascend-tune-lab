# vLLM-Ascend 服务化性能优化 · 工作流

本工作流由 `serving-perf-optimization` primary agent 强制 Read 并严格推进。

**当前版本范围**：流水线分为两阶段；**仅 Phase 1（基线配置生成）执行完整逻辑**；Phase 2 为占位模块，落盘占位状态后 **流水线结束**。

> 用户输入：工作目录须有一份 MD 配置文件（默认 `deploy-config.md`）。`## 基本参数` 必填，`## 服务化配置` 可选。格式见 [`references/user-config-format.md`](references/user-config-format.md)，示例见 [`config.example.md`](../../configuration-tuning-skills/ascend-baseline-generator/config.example.md)。

## 流程总览

```text
+--------------------------------------------------------------+
| Phase 0 · 工作目录配置文件                                     |
|    默认 deploy-config.md；不存在则生成模板并停止               |
|    未填完 ## 基本参数 → 停止，不得进入下一步                    |
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
| Phase 2 · 服务化调优 【serving-tuning-subagent · 占位】        |
|    只读 baseline-summary.md → tuning-status.md (placeholder) → 结束      |
+--------------------------------------------------------------+
```

## Subagent 映射

| Phase | Subagent | 状态 |
| --- | --- | --- |
| 1 | `serving-baseline-reproduce-subagent` | **已实现** |
| 2 | `serving-tuning-subagent` | **占位** |

派发模板见 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md)。

## 执行规则

进入本工作流后建立 TaskList，**严格按 Phase 0 → 1 → 2 顺序**推进。

### 全局约束

- **配置文件硬门禁**：工作目录无合法配置文件，或 `## 基本参数` 未填完 → **不得进入 Phase 1**；禁止用对话零散参数代替配置文件。
- **Phase 1 硬门禁**：无 `baseline-launch.sh` 与 `baseline-summary.md` 不得进入 Phase 2。
- **Phase 2 占位约束**：禁止部署、解析日志、调参；只写 `tuning-status.md`。
- **流水线终点**：Phase 2 占位完成后结束。
- **进度文件**：`{case_dir}/progress.md` 记录各 Phase 状态。

### TaskList 骨架

```text
T0. 定位/生成/校验工作目录 MD 配置文件（Phase 0）
T1. 确定 case_dir，可选复制 config 到 case 目录归档
T2. 派发 serving-baseline-reproduce-subagent（Phase 1）
T3. 用户确认低时延/高吞吐（若 Phase 1 回报双匹配）
T4. Primary 验收 baseline-summary.md
T5. 派发 serving-tuning-subagent（Phase 2 · 占位）
T6. Primary 验收 tuning-status.md，流水线结束
```

## Phase 0 · 工作目录配置文件

### 配置文件路径

| 优先级 | 来源 | 路径 |
| --- | --- | --- |
| 1 | 用户在消息中指定 | 用户给出的 `config_md_path` |
| 2 | 默认 | 工作目录根下的 **`deploy-config.md`** |

### Primary 步骤

1. Read [`references/user-config-format.md`](references/user-config-format.md)。
2. 确定 `config_md_path`（见上表）。
3. **文件不存在**：
   - Read [`templates/deploy-config.template.md`](templates/deploy-config.template.md)。
   - 写入 `{config_md_path}`（相对工作目录）。
   - 明确告知：「已在工作目录生成 `{config_md_path}`，请填写 `## 基本参数` 后重新发起；**完成前不会进入下一步**。」
   - **停止**，不派发任何 subagent。
4. **文件存在但未填完**（缺 `## 基本参数`、缺字段、或字段值为空）：
   - 列出缺失项，提示参考 `configuration-tuning-skills/ascend-baseline-generator/config.example.md`。
   - **停止**，不派发任何 subagent。
5. **校验通过**（7 项基本参数齐全且非空）：
   - 若存在 `## 服务化配置`，确认其为 bash 代码块（可选节，缺失不报错）。
   - 记录 `config_md_path`，进入 Phase 1。

### 禁止行为

- 不得替用户填写 `## 基本参数` 的值。
- 不得从对话拼参数绕过配置文件。
- 不得在 Phase 0 未通过时进入 Phase 1。

### case_dir

- 由用户指定或 Primary 按配置内容派生（如 `optimization/<model>-<device>/`）。
- 可选：复制配置文件到 `{case_dir}/config.md` 归档；Phase 1 仍以工作目录中的 `config_md_path` 为匹配输入。

## Phase 1 · 基线配置生成

### Primary 派发

1. 传入已校验的 `config_md_path` 与 `case_dir`。
2. 按模板派发 `serving-baseline-reproduce-subagent`。
3. 产出须符合 [`templates/baseline-summary-template.md`](templates/baseline-summary-template.md)。

### Primary 验收

- Read `{case_dir}/baseline/baseline-summary.md`。
- 确认 `baseline-summary.md` 完整后进入 Phase 2。

## Phase 2 · 服务化调优（占位）

见 [`references/subagent-prompt-templates.md`](references/subagent-prompt-templates.md) § Phase 2。

## 后续版本预留

Phase 2 实装后可扩展部署验证、日志解析、调优迭代。
