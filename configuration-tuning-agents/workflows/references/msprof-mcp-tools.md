# msprof-mcp 工具一览

与 msagent / PyPI `msprof-mcp==0.1.8` 对齐。Cursor 下 server 名可能为 `msprof-mcp` 或 `user-msprof-mcp`；调用前用 `GetMcpTools` 确认。

| 工具名称 | 数据载体 | 核心能力 |
| --- | --- | --- |
| `get_flow_data` | `trace_view.json` | 按 Flow 关联 CPU/NPU 算子明细 |
| `find_slices` | `trace_view.json` | 搜索 Trace Slice（contains / exact / glob） |
| `execute_sql_query` | `trace_view.json` | PerfettoSQL 自定义查询 |
| `analyze_overlap` | `trace_view.json` | 计算/通信/调度重叠占比 |
| `analyze_kernel_details` | `kernel_details.csv` | 算子耗时分布、Top N、设备分布 |
| `get_operator_details` | `kernel_details.csv` | 特定算子执行明细 |
| `analyze_op_statistic` | `op_statistic.csv` | 调用次数、总耗时、Core 类型 |
| `get_op_type_details` | `op_statistic.csv` | 按类型/Core 过滤统计 |
| `get_csv_info` | 任意 CSV | 结构探索与样本 |
| `search_csv_by_field` | 任意 CSV | 字段搜索与过滤 |
| `get_profiler_config` | `profiler_info.json` | Profiler 配置与环境信息 |
| `analyze_communication` | `communication_matrix.json` | P2P/集合通信瓶颈与带宽 |
| `analyze_communication_trace` | `communication.json` | 通信时间分解与带宽详情 |
| `execute_sql` | `ascend_pytorch_profiler*.db` | 只读 SQL 预览 |
| `execute_sql_to_csv` | 同上 | 大结果导出 CSV |
| `msprof_analyze_advisor` | Profiling 数据目录 | 封装 `msprof-analyze advisor` |
| `create_dispatch_view` | profiler DB | 创建 dispatch 持久视图 |

## 维度速查

| 维度 | 工具 |
| --- | --- |
| Timeline | `analyze_overlap`、`find_slices`、`get_flow_data`、`execute_sql_query` |
| 算子 | `analyze_kernel_details`、`get_operator_details`、`analyze_op_statistic` |
| 通信 | `analyze_communication`、`analyze_communication_trace` |
| 配置 | `get_profiler_config` |
| 数据库 | `execute_sql`、`execute_sql_to_csv`、`create_dispatch_view` |
| 全局顾问 | `msprof_analyze_advisor` |
