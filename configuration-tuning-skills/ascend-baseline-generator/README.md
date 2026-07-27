# ascend-baseline-generator

自动根据模型参数匹配最佳 vLLM-Ascend 部署基线配置。

## 快速开始

### 1. 编辑配置文件

复制 `config.example.md` 并按你的需求修改基本参数：

```markdown
## 基本参数

- 输入长度: 4096          # 业务平均输入长度
- 输出长度: 1024          # 业务平均输出长度
- 设备类型: A3            # A2 或 A3
- 模型名称: Qwen3.5-27B   # 模型名称
- 量化格式: w8a8          # 量化格式
- NPU卡数: 1              # NPU 卡数
- 部署策略: 单机混部       # 部署策略
```

可选——如果填了 `## 服务化配置` 中的模型路径/IP/端口，会覆盖文档默认值。

### 2. 调用 skill

在 Cursor 中调用 `ascend-baseline-generator` skill，并提供配置文件路径，例如：

```
使用 ascend-baseline-generator 处理 configuration-tuning-skills/ascend-baseline-generator/config.example.md
```

### 3. 选择配置

**本地 `baseline-docs/` 命中时**：展示**低时延**和**高吞吐**两个配置供你选择：

- **低时延** — 适合在线推理、对话等延迟敏感场景
- **高吞吐** — 适合离线批量处理等高并发场景

**本地未命中时**（含本地暂不支持的 `PD分离` / `双机混部` 等）：自动从 [vLLM-Ascend 模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/) 拉取对应模型页配置（例如 [GLM5](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/GLM5.html)），**固定使用高吞吐**，不再询问 profile。也可手动跑：

```bash
python3 configuration-tuning-skills/ascend-baseline-generator/scripts/fetch_docs_baseline.py \
  --config your-config.md --json
```

选择/拉取后输出完整的 vllm 启动命令，可直接复制使用。

## 设备类型对照

| 配置文件填写 | 对应的硬件 |
|:------------|:----------|
| A3 | Atlas 800I A3 |
| A2 | Atlas 800I A2 |

## 目录结构

```
ascend-baseline-generator/
├── SKILL.md
├── config.example.md
├── scripts/fetch_docs_baseline.py
├── references/docs_model_page_aliases.json
├── baseline-docs/          # 本地优先
│   ├── Qwen/
│   ├── DeepSeek/
│   ├── GLM/
│   └── MiniMax/
└── README.md
```
