# 用户配置文件格式

流水线 **必须** 以工作目录中的一份 MD 配置文件作为唯一场景输入（`config_md_path`）。Primary 在 Phase 0 定位/生成/校验该文件；**配置文件填写完成前不得进入 Phase 1**。

参考示例：[`configuration-tuning-skills/ascend-baseline-generator/config.example.md`](../../configuration-tuning-skills/ascend-baseline-generator/config.example.md)

## 默认路径

| 场景 | `config_md_path` |
| --- | --- |
| 用户未指定路径 | 工作目录根下的 **`deploy-config.md`** |
| 用户指定路径 | 用户给出的相对或绝对路径 |

工作目录 = 当前项目根目录（Agent 会话所在项目）。

## 必填：`## 基本参数`

配置文件 **必须** 包含 `## 基本参数` 章节，且以下 7 项 **全部存在且有效**（键存在且冒号后有非空值）：

| MD 键名 | 对应字段 | 示例 |
| --- | --- | --- |
| 输入长度 | input_seq_len | 4096 |
| 输出长度 | output_seq_len | 1024 |
| 设备类型 | device_type | A3 |
| 模型名称 | model_name | Qwen3.5-27B |
| 量化格式 | quantization | w8a8 |
| NPU卡数 | num_npus | 1 |
| 部署策略 | deploy_strategy | 单机混部 |

缺少章节、缺少任一项、或任一项值为空 → Primary **停止并提示补全**，**不得**进入 Phase 1，**不得**在对话中零散收集参数替代配置文件。

## 可选：`## 服务化配置`

`## 服务化配置` 章节 **可以没有**。若存在，应为 bash 代码块，用于覆盖匹配结果中的：

- 模型权重路径（`vllm serve` 第一个参数）
- `--host`
- `--port`

三项 **都** 提供时才覆盖；缺任一则 Phase 1 subagent 使用 baseline 文档默认值，并在 `baseline-summary.md` §4.2 标注 `overrides_applied: no`。

## 配置文件骨架

```markdown
# 部署配置

## 基本参数

- 输入长度: 4096
- 输出长度: 1024
- 设备类型: A3
- 模型名称: Qwen3.5-27B
- 量化格式: w8a8
- NPU卡数: 1
- 部署策略: 单机混部

## 服务化配置

```bash
vllm serve /path/to/model \
    --host 0.0.0.0 \
    --port 8000 \
    ...
```
```

（`## 服务化配置` 整节可省略。）

## Phase 0 流程（Primary）

```text
1. 确定 config_md_path（用户指定 → 否则 deploy-config.md）
2. 文件不存在？
   → Read workflows/templates/deploy-config.template.md
   → 写入 {config_md_path}
   → 告知用户填写后重新发起 → **停止**
3. 文件存在但未填完？
   → 列出缺失/空字段 → **停止**
4. 校验通过 → 进入 Phase 1
```

### Phase 0 校验清单

- [ ] 已确定 `config_md_path`（默认 `deploy-config.md` 或用户指定）
- [ ] 文件存在且可读（不存在则已生成模板并停止）
- [ ] 包含 `## 基本参数`
- [ ] 7 个基本参数字段均已解析且值非空
- [ ] （可选）若存在 `## 服务化配置`，内容为 bash 代码块

校验通过后，将 `config_md_path` 与 `case_dir` 传入 Phase 1 subagent；可将配置文件复制到 `{case_dir}/config.md` 便于归档，**但以工作目录中的原文件为匹配输入**。
