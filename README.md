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

未指定工作目录时，默认写到 **`./workspace`**。

### 流水线（三条，互斥）

| 功能 | 提示词示例 | 你会得到什么 |
| --- | --- | --- |
| **服务化调优** | 「帮我做服务化调优」「生成某某模型的基线部署」「做并行策略调优」 | 基线启动脚本 + 离线并行策略建议（`workspace/cases/.../baseline/`、`tuning/`） |
| **Profiling 分析** | 「分析这份 profiling 数据」并带上本地 `*_ascend_pt` / `PROF_*` 目录 | 计算 / 通信 / 调度分析报告（`workspace/profiling/profiling-report.md`） |
| **最佳 PD 配比** | 「帮我算最佳 PD 配比」「做 Prefill-Decode 配比实测」 | 环境检查、部署与实测后的推荐配比（`workspace/pd-ratio/`） |

Profiling 需要本地已有采集数据；PD 配比会在真实机器上部署并压测。不要和下面的独立 skill 混在一句里同时提。

### 独立 Skill（不进流水线）

只要白名单工具、且没有上面三条产品意图时，Agent 直接跑对应 skill，不派发 subagent，也不问 A/B/C。产物在 **`workspace/skills/<skill-name>/`**。

| Skill | 提示词示例 | 你会得到什么 |
| --- | --- | --- |
| `op-mfu-calculator` | 「算这个 matmul 的 MFU」并给出形状、耗时、芯片型号 | MFU 公式、代入过程与结论 |
| `ascend-dump-analyzer` | 「对比这两台机器的环境信息」「比对这两份环境 dump」并给出 1～2 个 dump JSON | 环境差异 / 配置漂移报告；没有 dump 时会先问路径或采集 |
| `cluster-analysis` | 「分析这份 cluster_analysis_output」「比对这两个集群目录」 | 集群全景 MD / HTML（或双集群比对报告） |
| `vllm-ascend-tuning` | 「jemalloc / Graph Mode / HCCL 怎么调」 | 手册式调优建议（**不是**基线脚本，也**不是** PD 配比实测） |

独立 skill 的分类与调用约定见 [`configuration-tuning-skills/README.md`](configuration-tuning-skills/README.md)。

有原始 `PROF_*` 且要做完整 Profiling → 仍走上面的 **Profiling 分析**，不要用 `cluster-analysis` 代替。要基线复现或并行策略流水线 → 仍走 **服务化调优**，不要用 `vllm-ascend-tuning` 代替。

读 GitHub 文件、安装 msprof-mcp、从日志抽配置/吞吐、抽取 vLLM 配置开关或模型特性表、解析 msprof-analyze compare xlsx，已并入流水线，**不能**单独触发。
