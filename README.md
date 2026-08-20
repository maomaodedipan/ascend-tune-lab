# ascend-tune-lab

面向 **vLLM-Ascend** 的服务化性能优化 Agent。安装后在 Cursor / Claude Code / OpenCode 等工具中直接对话即可，按提示词走不同功能。

不适用于训练侧调优、非 Ascend NPU 上的 vLLM 部署。

---

## 安装

需要：**Git**、**Bash**（Linux / macOS / WSL / Git Bash）、**Python ≥ 3.11**。做 PD 配比实测时，目标机还需要 Docker 与 Ascend 环境。

### 1. 克隆本仓库

```bash
git clone <this-repo-url> ascend-tune-lab
cd ascend-tune-lab
```

### 2. 挂载 Agent 到目标项目

在**要打开 Agent 的项目根目录**执行（本仓库自身也可以作为目标项目）：

```bash
# Cursor（推荐）
./configuration-tuning-agents/init.sh project cursor

# 安装到另一个服务化项目
./configuration-tuning-agents/init.sh project cursor /path/to/your/project
```

`init.sh` 参数：`[level] [tool] [install_path]`

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `level` | `project`（默认） / `global` | 项目级或用户全局 |
| `tool` | `cursor` / `claude` / `opencode` / `trae` / `copilot` / `codearts` | 目标 IDE |
| `install_path` | 可选 | 不填则安装到当前目录 |

Windows 请在 **WSL 或 Git Bash** 中跑 `init.sh`，不要用 PowerShell 直接执行。更多参数见 `./configuration-tuning-agents/init.sh --help`。

### 3. 打开项目并启动对话

用对应工具打开安装目标目录，新开一次 Agent 对话即可。无需再配环境变量或手动选 skill。

---

## 如何触发

用自然语言说明你要做的事即可。缺配置、缺材料时，Agent 会提示你补什么；跑完后会给出结果说明（报告路径与结论）。一次对话只走一种功能；说不清时 Agent 会先问你选哪一项。

| 功能 | 提示词示例 | 你会得到什么 |
| --- | --- | --- |
| **服务化调优** | 「帮我做服务化调优」「生成某某模型的基线部署」「做并行策略调优」 | 基线启动脚本 + 离线并行策略建议 |
| **Profiling 分析** | 「分析这份 profiling 数据」并带上本地采集目录 | 计算 / 通信 / 调度分析报告 |
| **最佳 PD 配比** | 「帮我算最佳 PD 配比」「做 Prefill-Decode 配比实测」 | 环境检查、部署与实测后的推荐配比 |

三种功能互斥，不要混在一句里同时提。Profiling 分析需要本地已有采集数据；PD 配比会在真实机器上部署并压测。
