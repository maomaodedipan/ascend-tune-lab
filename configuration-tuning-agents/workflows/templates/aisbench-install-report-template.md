# aisbench-install-report 模板

`aisbench-install-report.md` 是 **`serving-aisbench-install-subagent`（路径 C · Phase 2 · 部署前）** 的结构化输出。

下一环节 **`serving-pd-deploy-subagent`（Phase 3）**；须 `passed|skipped` 后才允许部署。

## 落盘布局

```text
{workdir}/pd-ratio/aisbench/
├── aisbench-install-report.md
└── aisbench-install-status.md
```

## 写者 / 读者

| 角色 | 关系 |
| --- | --- |
| **写者** | `serving-aisbench-install-subagent` |
| **读者** | `serving-pd-deploy-subagent`、`serving-pd-ratio-benchmark-subagent`；primary |

---

## 按下面结构落盘

```markdown
# AISBench Install Report

> producer: serving-aisbench-install-subagent
> phase: 2
> workdir: {workdir}

## 1. 安装目标

| 项 | 值 |
| --- | --- |
| host_ip | |
| container_name | |
| install_dir | |
| already_installed | true/false |
| numpy_before | |
| numpy_after | |
| numpy_pinned | true/false（与 vLLM 同容器时必填） |

## 2. 探测结果

| 探测 | 结果 | 证据 |
| --- | --- | --- |
| `command -v ais_bench` | | |
| `ais_bench -h` | | |

## 3. 安装步骤（若未跳过）

| 步骤 | 命令 | 结果 |
| --- | --- | --- |
| clone | `git clone https://github.com/AISBench/benchmark.git` | |
| editable install | `pip3 install -e ./ --use-pep517` | |
| api deps | `pip3 install -r requirements/api.txt` | |
| extra deps | `pip3 install -r requirements/extra.txt` | |
| verify | `ais_bench -h` | |

## 4. 结论

- overall: passed / skipped / failed
- ais_bench 可用路径：
```

---

## 配套 `aisbench-install-status.md`

```markdown
# AISBench Install Status

- status: passed|skipped|failed
- report: {workdir}/pd-ratio/aisbench/aisbench-install-report.md
- host_ip:
- container_name:
- ais_bench_path:
- timestamp:
- notes:
```

> `skipped` 与 `passed` 均可进入 Phase 4（表示工具可用）。
