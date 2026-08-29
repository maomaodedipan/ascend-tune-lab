# ascend-tune-lab 快速入门

## 概述

面向 **vLLM-Ascend** 的服务化性能优化 Agent。安装后在 Cursor / Claude Code / OpenCode 等工具中直接对话即可。一次对话只走一种功能：独立 skill（含最佳 PD 配比），或路径 A 服务化调优、路径 B Profiling 分析。

不适用于训练侧调优、非 Ascend NPU 上的 vLLM 部署。

---

## 一、环境搭建

### 前置条件

- **Git**、**Bash**（Linux / macOS / WSL / Git Bash）、**Python ≥ 3.11**
- 已安装 OpenCode、Claude Code、TRAE、Cursor、Copilot、CodeArts 等受支持的 AI 编程工具
- 做 PD 配比实测时，目标机还需要 Docker 与 Ascend 环境

Windows 请在 **WSL 或 Git Bash** 中跑 `init.sh`，不要用 PowerShell 直接执行。

### OpenCode（默认）

```bash
git clone <this-repo-url> ascend-tune-lab
cd ascend-tune-lab/configuration-tuning-agents
bash init.sh project opencode   # 项目级（默认）
bash init.sh global opencode    # 全局级
```

验证：项目下应有 `.opencode/`（含 skills / agents / workflows）以及 `AGENTS.md` 符号链接。

启动：

```bash
opencode
```

### 其他工具

<details>
<summary>Claude Code</summary>

```bash
git clone <this-repo-url> ascend-tune-lab
cd ascend-tune-lab/configuration-tuning-agents
bash init.sh project claude     # 项目级
bash init.sh global claude      # 全局级
```

验证：项目下应有 `.claude/` 与根目录 `CLAUDE.md`。

启动：

```bash
claude
```

</details>

<details>
<summary>TRAE</summary>

```bash
git clone <this-repo-url> ascend-tune-lab
cd ascend-tune-lab/configuration-tuning-agents
bash init.sh project trae
```

`init.sh` 会检测 TRAE IDE（`~/.trae`）、Plugin（`~/.marscode`）或 CLI（`~/.traecli`）。验证：对应目录下有 `skills/`、`agents/`。

启动：在 TRAE IDE / 插件 / CLI 中打开安装目标项目。

</details>

<details>
<summary>Cursor（推荐）</summary>

```bash
git clone <this-repo-url> ascend-tune-lab
cd ascend-tune-lab/configuration-tuning-agents
bash init.sh project cursor     # 项目级
bash init.sh global cursor      # 全局级
```

验证：

- 安装目标下 `.cursor/skills/`、`.cursor/agents/`、`.cursor/workflows/`
- 若在插件目录执行（`PLUGIN_ROOT` = 当前目录），`AGENTS.md` 已在该目录，不再重复挂载

与 CANNBot 相同：Cursor 自动发现项目 `.cursor/skills` 与 `.cursor/agents`，**不会**复制到 `~/.cursor/plugins/local`，也不是 Marketplace 插件。装完后 **Developer: Reload Window**。

若 Cursor 打开的是仓库根而不是 `configuration-tuning-agents/`，把仓库根传给第三个参数：

```bash
cd ascend-tune-lab/configuration-tuning-agents
bash init.sh project cursor /path/to/ascend-tune-lab
```

启动：用 Cursor 打开安装目标项目。

</details>

<details>
<summary>Copilot</summary>

```bash
git clone <this-repo-url> ascend-tune-lab
cd ascend-tune-lab/configuration-tuning-agents
bash init.sh project copilot    # 项目级 → .github/
bash init.sh global copilot     # 全局级 → ~/.copilot/
```

启动：VS Code Copilot CLI / IDE。

</details>

<details>
<summary>CodeArts</summary>

```bash
git clone <this-repo-url> ascend-tune-lab
cd ascend-tune-lab/configuration-tuning-agents
bash init.sh project codearts
bash init.sh global codearts
```

验证：`.codeartsdoer/skills/`（项目级）或 `~/.codeartsdoer/skills/`（全局级）。

启动：CodeArts CLI / IDE。

</details>

### 安装到其他项目

第三个参数为安装目标，省略则安装到当前目录：

```bash
# 安装到当前目录
bash /path/to/ascend-tune-lab/configuration-tuning-agents/init.sh project cursor

# 安装到指定服务化项目
bash /path/to/ascend-tune-lab/configuration-tuning-agents/init.sh project cursor /path/to/your/project
```

### 安装路径

| 工具 | 项目级 | 全局级 |
| --- | --- | --- |
| OpenCode | `.opencode/` + `AGENTS.md` | `~/.config/opencode/` |
| Claude | `.claude/` + `CLAUDE.md` | `~/.claude/` |
| TRAE | `.trae/` / `.marscode/` / `.traecli/` | 对应全局目录 |
| Cursor | `.cursor/` + `AGENTS.md` | `~/.cursor/` |
| Copilot | `.github/` | `~/.copilot/` |
| CodeArts | `.codeartsdoer/` | `~/.codeartsdoer/` |

`init.sh` 参数：`[level] [tool] [install_path]`。`level` 为 `project`（默认）或 `global`。更多见 `bash init.sh --help`。

更新：在插件目录重新执行同一条 `bash init.sh ...` 即可。

---

## 二、快速上手

未指定工作目录时，默认写到 **`./workspace`**。用自然语言说明要做的事即可；缺配置时代理会列出缺失项。说不清时会先问：独立工具 / A / B。

### 流水线（A/B 互斥）

```text
Primary 锁 path
  ├── 快路径 → 只跑白名单 skill（含最佳 PD 配比）
  ├── A 服务化调优 → Phase 0 → 基线 → 离线并行策略
  └── B Profiling  → 本地数据路径 → 分析报告
```

| 功能 | 提示词示例 | 你会得到什么 |
| --- | --- | --- |
| **服务化调优** | 「帮我做服务化调优」「生成某某模型的基线部署」 | `workspace/cases/.../baseline/`、`tuning/` |
| **Profiling 分析** | 「分析这份 profiling 数据」并带上本地 `*_ascend_pt` / `PROF_*` | `workspace/profiling/profiling-report.md` |

Profiling 需要本地已有采集数据。不要和下面的独立 skill 混在一句里同时提。

### 独立 Skill（不进流水线）

只要白名单工具、且没有上面两条产品意图时，不派发 subagent。

| Skill | 提示词示例 |
| --- | --- |
| `op-mfu-calculator` | 「算这个 matmul 的 MFU」并给出形状、耗时、芯片型号 |
| `ascend-dump-analyzer` | 「比对这两份环境 dump」 |
| `cluster-analysis` | 「分析这份 cluster_analysis_output」 |
| `vllm-ascend-tuning` | 「jemalloc / Graph Mode / HCCL 怎么调」 |
| `pd-ratio-benchmark` | 「帮我算最佳 PD 配比」→ `workspace/pd-ratio/`（独立 skill：`PD-ratio-benchmark/SKILL.md`） |

分类见 [`configuration-tuning-skills/README.md`](configuration-tuning-skills/README.md)。有原始 `PROF_*` 且要做完整 Profiling → 走路径 B，不要用 `cluster-analysis` 代替。要基线或并行策略流水线 → 走路径 A，不要用 `vllm-ascend-tuning` 代替。

读 GitHub 文件、安装 msprof-mcp、从日志抽配置/吞吐、抽取 vLLM 配置开关或模型特性表、解析 msprof-analyze compare xlsx，已并入流水线，**不能**单独触发。

编排入口是 `workflows/primary-workflow.md`（A/B / 快路径）。最佳 PD 配比是独立 skill：`PD-ratio-benchmark/SKILL.md`。

---

## 三、常见问题

### Q: 如何查看帮助？

```bash
bash configuration-tuning-agents/init.sh --help
```

### Q: 项目级和全局安装如何选择？

- **项目级**：每个服务项目一份配置，互不影响
- **全局**：本机该工具下所有项目共用

### Q: 为什么仓库里没有 `.cursor-plugin/plugin.json`？

与 CANNBot 一致：`init.sh` 不生成 Cursor Marketplace 清单。项目级安装把 skills / agents 挂到 `.cursor/`，由 Cursor 自动发现。`.cursor-plugin/` 若出现在本地，已 gitignore，不要提交。

### Q: 项目根出现了 `AGENTS.md`？

装到**其它目录**时会按 CANNBot 规则在安装目标放 `AGENTS.md` 符号链接。在插件目录自身执行时，文件已在当前目录，会跳过。请把安装产物加入该项目 `.gitignore`。

### Q: 如何更新？

在 `configuration-tuning-agents/` 下重新执行当初那条 `bash init.sh project <tool>`。
