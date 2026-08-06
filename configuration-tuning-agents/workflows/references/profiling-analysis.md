# Profiling 分析约定（独立流水线）

与服务化 Phase 0–2 **完全独立**（对齐 msagent Profiler）。**不**嵌入 `serving-perf-optimization-workflow`，也**不**在 baseline / tuning 过程中触发。

由 primary 在 **同时满足** 下列条件时派发 `serving-profiling-analysis-subagent`：

1. 用户明确要做 profiling / profiler / msprof 数据分析；
2. 用户提供了本地 `profiler_path`（`*_ascend_pt` / `*_ascend_ms` / `PROF_*` 或其可唯一定位的父目录）。

缺路径 → 只索取路径并停止；缺分析意图 → 不派发。服务化进行中 **禁止**顺带派发。

## 首次安装硬门禁（必须）

**每次进入 Profiling 前**先确认 msprof-mcp 已就绪：

1. `GetMcpTools` / Settings → MCP 检查 `msprof-mcp` 或 `user-msprof-mcp` 是否 ready  
2. **未就绪（含首次使用）** → **必须**执行 `configuration-tuning-skills/msprof-mcp-setup/SKILL.md`  
   - Linux/macOS/WSL：`scripts/bootstrap-msprof-mcp.sh project cursor`（或 claude/opencode）  
   - Windows 原生：按技能第 6 节 pip（含 `mcp<2`、`pandas<3`）  
3. 安装后用户 **Reload Window / 重启 IDE**，再次确认 ready  
4. **禁止**跳过 setup 直接分析，也禁止在未 setup 时静默改用纯本地读文件冒充 MCP 分析

## 前置依赖

| 依赖 | 用途 | 安装 |
| --- | --- | --- |
| `msprof-mcp==0.1.8` | MCP 工具面 | **首次：`msprof-mcp-setup`**（bootstrap 或 Windows pip） |
| `msprof-analyze==8.5.2`（可选） | 集群 / advisor / free_analysis CLI | `pip install msprof-analyze==8.5.2` |
| Python ≥ 3.11、glibc ≥ 2.34 | uv tool + Perfetto | 系统环境 |

工具一览：`msprof-mcp-tools.md`。Cursor 下 server 名可能是 `msprof-mcp` 或 `user-msprof-mcp`（以 `GetMcpTools` 为准）。

## 输入

- **必填**：`profiler_path` — 用户给出的本地路径。
- **workdir**：默认 `./workspace`；报告写在 workdir 下。
- **禁止**：用户未给路径时用 ls/glob/递归搜索猜测位置。
- **禁止**：执行服务化 Phase 0–2 / 读写 `deploy-config.md` 作为本流水线门禁。

## 输出

| 路径 | 说明 |
| --- | --- |
| `{workdir}/profiling/profiling-report.md` | 默认报告（可用 `output_dir` 覆盖；仅 MCP ready 后产出） |

## Skill 套件（msagent Profiler.yml）

- `msprof-mcp-setup`（**首次硬门禁**）
- `ascend-profiler-data-validation`
- `ascend-profiler-db-explorer`
- `ascend-computation-analysis`
- `ascend-communication-analysis`
- `ascend-schedule-analysis`
- `ascend-msprof-analyze-cli`
- `ascend-cluster-fast-slow-rank-detector`
- `op-mfu-calculator`
- `github-raw-fetch`

## 分析顺序（摘要）

1. **步骤 0**：MCP ready？否则只跑 `msprof-mcp-setup` 并停止等 Reload  
2. 数据校验（validation）  
3. 单卡：Timeline → 算子 → 通信 → 配置；多卡：advisor → Rank 下钻  
4. 交叉验证（Timeline vs CSV/DB）  
5. 落盘报告（问题 / 证据 / 影响 / 建议 / 验证方法）
