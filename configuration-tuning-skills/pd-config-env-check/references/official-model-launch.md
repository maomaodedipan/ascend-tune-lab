# 官方模型拉起命令回退

索引：[vLLM Ascend 模型教程](https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/)

当 `pd-deploy-config.md` 中 **Prefill / Decode 拉起命令缺失或为空** 时，Agent **必须**从上述教程站点按模型名取官方命令，禁止凭空编造。

## 何时触发

| 条件 | 行为 |
| --- | --- |
| 用户已给出完整 Prefill（及 Decode，除非 `same_launch_cmd=true`） | **只用用户命令**；仅允许网络/`kv_port`/`engine_id`/`*.dp_size` 改写 |
| Prefill 或 Decode 段为空 / 仅占位注释 | 按本页从官方教程回填，并在报告注明 `launch_cmd_source=official_docs` |
| 教程中找不到匹配模型 | `pd-check-status=failed`，列出已尝试的 URL，请用户补命令或核对模型名 |

## 查找步骤

1. 读取配置 **模型名称**（及量化后缀，如 `w8a8` / `w4a8`）。
2. 打开索引页，或按常见 slug 尝试文档 URL：

```text
https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/{Slug}.html
```

`{Slug}` 试探顺序示例（按模型名归一化，保留官方大小写与连字符）：

- 原样：`Qwen3.6-27B` → 文档可能为系列名如 `GLM5`、`DeepSeek-V3.1`、`Kimi-K2.5`
- 去权重路径只留模型族；量化变体优先选教程中对应 w8a8/w4a8/BF16 章节
- 在索引或站内搜索模型关键字，打开命中的教程页

3. 在教程页中按优先级取命令：

| 优先级 | 章节（名称因页而异） | 用途 |
| --- | --- | --- |
| 1 | **单节点在线部署** 的 `--tensor-parallel-size` / `--data-parallel-size` | **路径 C 配比基线的实例 size**（最小 P/D = DP×TP） |
| 2 | **Prefill-Decode 分离 / PD 分离**（含 A2/A3 分 tab） | `kv_connector` / `kv_role` / Mooncake；**不要**取其满机 DP 与全卡 `VISIBLE_DEVICES` |
| 3 | **多节点在线部署** 中带 `kv_transfer_config` / Mooncake 的示例 | 可拆成 P/D 的网络与 KV 字段 |
| 4 | 仅当用户明确独占整机 P 或 D 节点 | 才使用 PD 章里的整机 DP |

4. **设备类型对齐**：配置为 A2/A3 时，必须选用教程中对应 **A2 系列 / A3 系列** tab 或小节的命令，禁止混用。
5. **路径 C 配比 QPS 基线（硬，优先于「整机 PD 示例」）**：
   - 每个 P/D 实例的 **TP/DP** 取教程 **单实例 / 单节点在线部署** 命令（例如 Qwen3.6-27B-w8a8 的 §5.1：`--data-parallel-size 1 --tensor-parallel-size 2` → 最小实例 **2 卡**）。
   - PD 分离 / 多节点章（如 §5.2「每节点 TP=2 DP=8」）只用于提取 `kv_connector` / `kv_role` / Mooncake 字段，**禁止**把满机 DP 或 `ASCEND_RT_VISIBLE_DEVICES=0..N-1` 当作本路径的实例 size。
   - 仅当用户明确要求「P 或 D 独占整机节点」时，才使用满机 DP。
   - 回填后为同机 1P1D 设置可见卡：P 连续 `DP×TP` 张，D 紧接着同等最小 size；剩余卡不写进命令。
6. 将提取的 bash 写入工作副本（报告 + 供 `render_pd_launch` 使用的命令源），保留官方 `kv_connector` 等字段；随后仍走既有「仅允许字段」改写与校验。
7. 模型权重路径：优先用用户配置/机器上的路径；教程里的 `/root/.cache/...` 仅当用户未给路径时作为占位，并在报告标明 **须用户确认权重路径**。

## 报告必填字段

- `launch_cmd_source`: `user` | `official_docs`
- `official_docs_url`: 实际使用的教程页 URL
- `official_docs_section`: 如 `5.2.1 A3系列PD分离`
- `device_tab`: `A2` | `A3`
- 若权重路径仍为文档占位：`weight_path_needs_user_confirm: true`

## 禁止

- 教程未覆盖该模型时编造 `vllm serve` / PD 参数
- 无视 A2/A3 tab 混用命令
- 把官方命令改写成另一套 connector/量化「优化」而不经用户确认（仍只允许网络与公式缺省字段）
- 官方回填完成后视为与用户命令同等：拉起失败不得擅自去掉 MTP、加 `VLLM_WORKER_MULTIPROC_METHOD=spawn`、改 `LD_LIBRARY_PATH` 或其它业务参数后再试；须停止并等用户确认
- 路径 C 配比基线把教程「整机/多节点 DP」缩放到本机当最小实例，或把全部卡写入 P/D 的 `ASCEND_RT_VISIBLE_DEVICES`
