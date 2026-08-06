---
name: msprof-mcp-setup
description: 当用户需要在 opencode / Cursor / Claude Code 等工具中接入 msprof-mcp（MindStudio Profiler 的 MCP server，用于分析 Ascend profiling 数据）时使用此技能。涵盖 Linux / macOS / WSL 与 Windows 原生两种安装路径，以及各 IDE 的 MCP 配置写入方式。重点解决 Windows 上 pandas 3.x C 扩展加载失败、opencode 桌面版无 CLI、opencode 配置格式仅认 mcp.<name> 等已知坑。
---

# msprof-mcp 安装与 MCP 接入

## 1. 技能目标

把 `msprof-mcp`（FastMCP stdio server，提供 Ascend Profiler 数据分析工具集）安装到本机，并正确写入目标 IDE/工具的 MCP 配置，使该工具能拉起 msprof-mcp。

核心约束：**MCP server 进程空间必须与 IDE 进程空间一致**——Windows 桌面版 opencode 不能直接执行 WSL 里的 binary，反之亦然。安装前必须先判定 IDE 跑在哪一侧。

## 2. 适用范围

- 用户要在 opencode / Cursor / Claude Code 中接入 msprof-mcp
- 用户已有 Ascend profiling 数据，希望 LLM 通过 MCP 工具直接分析（csv/db/json/trace）
- 已安装或准备安装 msprof-mcp

不适用：
- msprof-mcp 各分析工具的具体用法（见 `ascend-msprof-analyze-cli` 等技能）
- 非 Ascend 场景的通用 MCP 接入

## 3. 前置确认（必须先做）

按 IDE 实际运行的进程空间选择安装侧：

| IDE 形态 | 安装侧 | 判定方法 |
| --- | --- | --- |
| opencode 桌面版（`OpenCode.exe`） | Windows 原生 | `Get-Command opencode` 找不到，但 `%LOCALAPPDATA%\Programs\@opencode-aidesktop\OpenCode.exe` 存在 |
| opencode CLI | 与 CLI 同侧 | 命令行能执行 `opencode --version` |
| Cursor（Windows 安装） | Windows 原生 | 进程在 Windows |
| Cursor（WSL Remote） | WSL | Cursor 连了 WSL 远程 |
| Claude Code | 与 claude CLI 同侧 | `command -v claude` 在哪侧 |

**关键事实**：opencode 桌面版 **没有 `opencode mcp list` 等 CLI 子命令**——这是 CLI 版才有的。桌面版只能改配置后重启 App 验证。

## 4. 安装路径选择

| 平台 | 推荐方式 | 入口 |
| --- | --- | --- |
| Linux / macOS / WSL | `bootstrap-msprof-mcp.sh`（uv tool install） | 第 5 节 |
| Windows 原生 | `pip install`（脚本对 MINGW 会拒绝） | 第 6 节 |

固定版本与约束（两侧一致）：

```
msprof-mcp==0.1.8
mcp>=1.26.0,<2        # msprof-mcp 0.1.8 依赖 mcp 1.x 的 fastmcp，2.x 已移除
pandas>=2,<3          # Windows 上 pandas 3.x C 扩展 DLL 加载失败；Linux 脚本一并约束
```


## 5. 路径 A：Linux / macOS / WSL（用 bootstrap 脚本）

脚本位置（本 skill 内）：

```text
configuration-tuning-skills/msprof-mcp-setup/scripts/bootstrap-msprof-mcp.sh
```

兼容入口（转发到上述脚本）：`configuration-tuning-agents/scripts/bootstrap-msprof-mcp.sh`

### 5.1 用法

参数风格对齐 `init.sh`：`[level] [tool] [install_path]`

```bash
SKILL=configuration-tuning-skills/msprof-mcp-setup
cd /path/to/ascend-tune-lab   # 或任意目标项目根

# Cursor 项目级（写 <project>/.cursor/mcp.json）
bash $SKILL/scripts/bootstrap-msprof-mcp.sh project cursor

# Claude Code 项目级（写 <project>/.mcp.json）
bash $SKILL/scripts/bootstrap-msprof-mcp.sh project claude

# opencode 项目级（写 <project>/.opencode/opencode.json，仅 mcp.<name>）
bash $SKILL/scripts/bootstrap-msprof-mcp.sh project opencode

# 同时写 cursor + claude + opencode
bash $SKILL/scripts/bootstrap-msprof-mcp.sh project all

# 全局 Cursor / Claude / opencode
bash $SKILL/scripts/bootstrap-msprof-mcp.sh global cursor
bash $SKILL/scripts/bootstrap-msprof-mcp.sh global claude
bash $SKILL/scripts/bootstrap-msprof-mcp.sh global opencode

# 已装好 msprof-mcp，只写配置
SKIP_UV_INSTALL=1 bash $SKILL/scripts/bootstrap-msprof-mcp.sh project cursor
```

### 5.2 脚本行为（Linux）

1. 若无 `uv` → 安装 uv  
2. `uv tool install -U --python <py> msprof-mcp==0.1.8`（默认国内镜像）  
3. constraints：`mcp>=1.26.0,<2`、`pandas>=2,<3`  
4. 解析 `~/.local/bin/msprof-mcp` 为**绝对路径**写入 MCP 配置  
5. 不在 MINGW/MSYS/Cygwin 上运行（直接退出，改走第 6 节）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MSPROF_MCP_PIN` | `msprof-mcp==0.1.8` | 版本钉子 |
| `MSPROF_MCP_CONSTRAINTS` | `mcp>=1.26.0,<2 pandas>=2,<3` | uv constraints |
| `MSPROF_MCP_PYTHON` | 系统 `python3`（≥3.11）否则 `3.11` | 优先本机 Python，避免再下 CPython |
| `USE_CN_MIRROR` | `1` | 阿里云 PyPI + 南大 python-build-standalone |
| `SKIP_UV_INSTALL` | `0` | 1=假定已装好，只写 MCP 配置 |
| `SKIP_MCP_JSON` | `0` | 1=只装不写配置 |

opencode：**只写** `mcp.msprof-mcp`（`type/local` + `command` 数组 + `enabled`）。不写 `mcp.servers`、`disabled`、`.opencode/mcp/`、顶层 `mcpServers`。

### 5.3 Linux / WSL 烟测

```bash
# binary 与 uv tool
ls -la ~/.local/bin/msprof-mcp
uv tool list | grep msprof

# import（确认不是坏掉的 mcp 2.x）
~/.local/share/uv/tools/msprof-mcp/bin/python -c \
  'from mcp.server.fastmcp import FastMCP; from msprof_mcp.server import create_server; print("ok")'

# stdio 短起（stdin 关闭后应干净退出，exit 0；不应 ModuleNotFoundError）
timeout 2 "$(realpath ~/.local/bin/msprof-mcp)" >/dev/null
echo exit:$?
```

## 6. 路径 B：Windows 原生（pip 安装）

适用：opencode 桌面版、Windows 版 Cursor、Windows 版 Claude Code。

### 6.1 前置

需要 Windows Python 3.11+（`py -0p` 确认）。

### 6.2 安装

```powershell
# 用国内镜像加速
& "C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe" `
    -m pip install --upgrade `
    "msprof-mcp==0.1.8" `
    "mcp>=1.26.0,<2" `
    "pandas>=2,<3" `
    -i https://mirrors.aliyun.com/pypi/simple/
```

> 必须显式带 `pandas>=2,<3`。否则 pip 会拉 pandas 3.x，在 Windows 上导入时报
> `ImportError: DLL load failed while importing base`，msprof-mcp 启动即崩。
> 这是已验证的坑，不要省略这条约束。

### 6.3 定位 binary

```powershell
# 通常在 Python 安装目录的 Scripts 下
$bin = "C:\Users\<you>\AppData\Local\Programs\Python\Python311\Scripts\msprof-mcp.exe"
Test-Path $bin
```

### 6.4 烟测（确认 stdio server 可用）

向 msprof-mcp.exe 喂一条 `initialize` 请求，应返回带 `serverInfo` 的 JSON：

```powershell
$bin = "C:\Users\<you>\AppData\Local\Programs\Python\Python311\Scripts\msprof-mcp.exe"
$in  = "$env:TEMP\mcp_in.txt"
$out = "$env:TEMP\mcp_out.txt"
$init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
# 注意：必须写无 BOM 的 UTF8，否则 server 把 BOM 当非法 JSON 头部拒绝
[System.IO.File]::WriteAllText($in, $init + "`n", (New-Object System.Text.UTF8Encoding $false))
Remove-Item $out -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $bin -RedirectStandardInput $in -RedirectStandardOutput $out -NoNewWindow -PassThru
$p.WaitForExit(6000) | Out-Null
if (-not $p.HasExited) { $p.Kill() }
Get-Content $out -Raw
```

预期输出包含：

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"experimental":{},"prompts":{"listChanged":false},"resources":{"subscribe":false,"listChanged":false},"tools":{"listChanged":false}},"serverInfo":{"name":"msprof_mcp","version":"1.29.0"}}}
```

如果看到 `notifications/message ... Internal Server Error` 且 stderr 报 `Invalid JSON`、`input_value='\ufeff...'`，说明输入文件带了 BOM——按上面 `UTF8Encoding($false)` 写文件即可。

## 7. 配置到各 IDE

### 7.1 opencode（重点）

opencode 的 local MCP 配置**只认** `mcp.<name>` 一层，字段为 `type:"local"` + `command`(数组) + `enabled`。**不要**写 `mcp.servers`、`disabled`、`.opencode/mcp/<name>.json` 分体文件、或顶层 `mcpServers`（那是 Cursor/Claude 格式，opencode 不读）。

配置文件路径：

| 级别 | 路径 |
| --- | --- |
| 全局（Windows） | `%USERPROFILE%\.config\opencode\opencode.json` 或 `opencode.jsonc` |
| 全局（Linux/WSL） | `~/.config/opencode/opencode.json` |
| 项目级 | `<repo>/.opencode/opencode.json` |

最小配置（Windows 桌面版，全局）：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "msprof-mcp": {
      "type": "local",
      "command": [
        "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python311\\Scripts\\msprof-mcp.exe"
      ],
      "enabled": true
    }
  }
}
```

最小配置（Linux/WSL，全局）：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "msprof-mcp": {
      "type": "local",
      "command": ["/home/<you>/.local/bin/msprof-mcp"],
      "enabled": true
    }
  }
}
```

注意：
- `command` 是**数组**，每个元素是一个 argv。Windows 路径反斜杠在 JSON 里要双写 `\\`。
- 写绝对路径，避免依赖 PATH 解析。
- 改完配置必须**重启 opencode 桌面版**才生效。

验证：重启后在新对话里输入 `use the msprof-mcp tool to ...`，若工具被调用即接入成功。桌面版没有 `opencode mcp list` 命令可验。

### 7.2 Cursor

#### 配置路径与格式

| 级别 | Linux / WSL | Windows 原生 |
| --- | --- | --- |
| 项目级 | `<repo>/.cursor/mcp.json` | 同左 |
| 用户级 | `~/.cursor/mcp.json` | `%USERPROFILE%\.cursor\mcp.json` |

格式为顶层 `mcpServers`（**不是** opencode 的 `mcp.<name>`）：

```json
{
  "mcpServers": {
    "msprof-mcp": {
      "type": "stdio",
      "command": "/home/<you>/.local/share/uv/tools/msprof-mcp/bin/msprof-mcp",
      "args": []
    }
  }
}
```

要点：
- `command` 用**绝对路径**字符串；`args` 为空数组即可。
- Linux/WSL：优先跑 `bash .../bootstrap-msprof-mcp.sh project cursor`（第 5 节）自动写入。
- Windows 原生：`command` 指向 `...\Scripts\msprof-mcp.exe`（第 6 节装好后手写或脚本外配置）。
- 改完后必须 **Reload Window**，在 Settings → Tools & MCP 确认 Connected。

#### WSL Remote 注意（已踩坑）

| 现象 | 处理 |
| --- | --- |
| Settings 显示已连接，但 Agent 的 `GetMcpTools` 只有内置 server | Agents Window 有时读 Windows 用户配置；可同时写 WSL `~/.cursor/mcp.json` 与项目 `.cursor/mcp.json` |
| Agent 里 server 名变成 `user-msprof-mcp` | 来自**用户级** mcp.json；`CallMcpTool` 的 `server` 用实际名（`user-msprof-mcp` 或 `msprof-mcp`） |
| 启动报 `No module named mcp.server.fastmcp` | 装到了 `mcp` 2.x；重装并约束 `mcp>=1.26.0,<2`（脚本已带） |
| Windows Agents 要调 WSL 内 binary | 用户级可配 `"command":"wsl.exe","args":["-e","/home/.../msprof-mcp"]`（仅当 Agent 跑在 Windows 侧时） |

验证：Reload 后让 Agent 枚举 MCP；应对 `get_profiler_config` / `execute_sql` 等工具可见，并可用错误路径做一次烟测（应返回结构化 `FILE_NOT_FOUND` 而非进程崩溃）。

### 7.3 Claude Code

写入 `<project>/.mcp.json`（项目级）或 `~/.claude.json`（全局），格式同 Cursor 的 `mcpServers`。

验证：`claude mcp list`。

## 8. 已知问题与约束（避坑）

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| Windows 上 `msprof-mcp.exe` 启动报 `ImportError: DLL load failed while importing base` | pandas 3.x 在 Windows 的 C 扩展 ABI 不兼容 | `pip install "pandas>=2,<3"` |
| msprof-mcp 启动报 `Invalid JSON ... input_value='\ufeff...'` | 输入文件带了 UTF-8 BOM | 用 `[System.IO.File]::WriteAllText` + `UTF8Encoding($false)` 写无 BOM |
| opencode 桌面版连不上 WSL 里的 msprof-mcp | 跨进程空间，Windows exe 无法执行 `/home/...` binary | 在 Windows 侧重装一份（第 6 节），或改用 opencode CLI 跑在 WSL 内 |
| opencode 配了 `mcp.servers.<name>` / `disabled` 不生效 | opencode 不识别这些字段，只认 `mcp.<name>` + `enabled` | 只保留 V1 结构（第 7.1 节） |
| `opencode mcp list` 命令不存在 | 桌面版无 CLI，仅 CLI 版有 | 改配置后重启 App 验证 |
| `bootstrap-msprof-mcp.sh` 在 MINGW/MSYS/Cygwin 直接退出 | 脚本对 Windows 类环境拒绝运行 | 走第 6 节 Windows 原生 pip 方案 |

## 9. 标准操作流程

1. 判定目标 IDE 跑在 Windows 还是 WSL/Linux（第 3 节）
2. 在**同一侧**安装 msprof-mcp：
   - WSL/Linux → 第 5 节脚本
   - Windows 原生 → 第 6 节 pip（带 `pandas>=2,<3`）
3. 用第 6.4 节方法做 stdio 烟测，确认 server 能应答 `initialize`
4. 写入对应 IDE 的 MCP 配置（第 7 节，注意格式差异）
5. 重启 IDE 验证

## 10. 输出建议

- 安装/配置完成后，明确告知用户：binary 路径、配置文件路径、已绑定的 IDE
- 如果遇到第 8 节的已知问题，直接给出对应解决命令
- 不要在 Windows 上跑 `bootstrap-msprof-mcp.sh`，它只支持 Linux/macOS/WSL
