# Configuration Tuning Agents

vLLM-Ascend 服务化性能优化编排，架构对齐 CANNBot **Plugin → Agent → Skill**，目录命名与 [`configuration-tuning-skills/`](../configuration-tuning-skills/) 对称。

- **Primary**：[`AGENTS.md`](AGENTS.md) — `serving-perf-optimization`
- **Subagents**：[`agents/`](agents/) — 各 step 子角色定义（当前 Step 1：`serving-baseline-reproduce-subagent`）
- **工作流**：[`workflows/`](workflows/) — 编排步骤与派发模板
- **安装**：[`init.sh`](init.sh) — 挂载 skills / agents / **workflows** 到目标项目

## 安装（推荐）

在**目标服务项目**根目录执行（或指定 `install_path`）：

```bash
/path/to/ascend-tune-lab/configuration-tuning-agents/init.sh project cursor
# 或
/path/to/ascend-tune-lab/configuration-tuning-agents/init.sh project cursor /path/to/your/project
```

`init.sh` 会安装：

| 挂载项 | 目标位置（Cursor project 示例） |
| --- | --- |
| Primary | `./AGENTS.md`、`.cursor/AGENTS.md` |
| Subagents | `.cursor/agents/*.md` |
| Skills | `.cursor/ascend-tune-lab/skills/*` |
| **Workflows** | `.cursor/workflows/` **与** `./workflows/`（符号链接到本插件 `workflows/`） |
| 仓库路径 | `./configuration-tuning-skills/`、`./configuration-tuning-agents/` |

安装后 primary 读取的工作流入口为：**`workflows/serving-perf-optimization-workflow.md`**。

支持 `level`：`project`（默认）、`global`；支持 `tool`：`opencode`、`claude`、`trae`、`cursor`、`copilot`、`codearts`。详见 `./init.sh --help`。

## 手动使用（不运行 init）

1. 将 `AGENTS.md` 复制或链接到项目编排入口。
2. 将 `workflows/` 链接到项目根 `workflows/`，保证 AGENTS 内相对路径可解析。
3. 准备 MD 配置（参考 `configuration-tuning-skills/ascend-baseline-generator/config.example.md`）。

## 目录结构

```
configuration-tuning-agents/
├── init.sh                      # CANNBot 风格安装脚本
├── AGENTS.md                    # primary orchestrator
├── README.md
├── agents/                      # subagent 定义
│   └── serving-baseline-reproduce-subagent.md
└── workflows/                   # init.sh 挂载到目标项目的 workflows/
    ├── serving-perf-optimization-workflow.md
    ├── templates/
    │   ├── baseline-summary-template.md
    │   └── baseline-summary-example.md
    └── references/
        └── subagent-prompt-templates.md
```

## 与 Skills 的对应关系

| Agent 步骤 | Subagent | Skill |
| --- | --- | --- |
| Step 1 基线复现 | `serving-baseline-reproduce-subagent` | `ascend-baseline-generator` |
| Step 3+ | （规划中） | `serving-cfg-extract`, `serving-perf-metrics`, … |
