# Subagent 派发模板

Primary 将 `{占位符}` 换成实际值。`subagent_type` 必须等于 `agents/*.md` 的 `name`，且 ∈ 当前 path 派发表。

**禁止**：prompt 粘贴 workflow / SKILL 正文或长【强制】清单；按 `description` 另选子代理；一次并行多个 Phase。细则在对应 `agents/*.md` 与 `SKILL.md`。

快路径不使用本文件。Phase 0（A/C）由 Primary 自己做，见各路径一页工作流。

通用骨架（各 Phase 只改表内字段）：

```text
scene: {scene}
path: {A|B|C}
phase: {n}
workdir: {workdir}

执行本 scene。Read：
- configuration-tuning-agents/agents/{agent}.md
- configuration-tuning-skills/{skill}/SKILL.md（invoke=pipeline）

禁止：其它 path；本路径其它 Phase；快路径 skill 落盘到 {workdir}/skills/。
错 scene/path → 写本 Phase status=failed 并停止，不执行业务。
完成后必须写约定 status/report。
```

---

## 路径 B

```
Task:
  description: Profiling 性能分析
  subagent_type: serving-profiling-analysis-subagent
  prompt: |
    scene: profiling-analysis
    path: B
    phase: 1
    workdir: {workdir}
    profiler_path: {profiler_path}
    output_dir: {output_dir}
    focus: {focus}

    执行本 scene。Read agents/serving-profiling-analysis-subagent.md
    与 msprof-mcp-setup 等 pipeline skill（invoke=pipeline）。
    MCP 未就绪则只 setup 并停止。禁止路径 A/C。
```

---

## 路径 A · Phase 1

```
Task:
  description: 基线配置生成
  subagent_type: serving-baseline-reproduce-subagent
  prompt: |
    scene: baseline-reproduce
    path: A
    phase: 1
    workdir: {workdir}
    config_md_path: {config_md_path}
    model_config_path: {workdir}/model_config.json
    case_dir: {case_dir}
    progress_md_path: {progress_md_path}

    执行本 scene。Read agents/serving-baseline-reproduce-subagent.md
    与 ascend-baseline-generator/SKILL.md（invoke=pipeline）。
    只从 config_md_path 读场景参数。禁止路径 B/C。
    交付：{case_dir}/baseline/ 下 launch + baseline-summary.md + config.used.md。
```

## 路径 A · Phase 2

```
Task:
  description: 并行策略调优
  subagent_type: serving-tuning-subagent
  prompt: |
    scene: serving-parallel-strategy-tuning
    path: A
    phase: 2
    workdir: {workdir}
    case_dir: {case_dir}
    baseline_summary_path: {case_dir}/baseline/baseline-summary.md
    config_md_path: {config_md_path}

    执行本 scene。Read agents/serving-tuning-subagent.md
    与 serving-parallel-strategy-tuning/SKILL.md（invoke=pipeline）。
    禁止部署/压测/改 baseline-launch.sh。禁止路径 B/C。
```

---

## 路径 C · Phase 1

```
Task:
  description: PD配置环境检查
  subagent_type: serving-pd-config-check-subagent
  prompt: |
    scene: pd-config-env-check
    path: C
    phase: 1
    workdir: {workdir}
    config_md_path: {config_md_path}

    执行本 scene。Read agents/serving-pd-config-check-subagent.md
    与 pd-config-env-check/SKILL.md（invoke=pipeline）。
    禁止路径 A/B 与本路径其它 Phase。
```

## 路径 C · Phase 2

```
Task:
  description: AISBench安装
  subagent_type: serving-aisbench-install-subagent
  prompt: |
    scene: aisbench-install
    path: C
    phase: 2
    workdir: {workdir}

    执行本 scene。Read agents/serving-aisbench-install-subagent.md
    与 aisbench-install/SKILL.md（invoke=pipeline）。
    须 pd-check-status=passed。禁止部署与压测。
```

## 路径 C · Phase 3

```
Task:
  description: PD分离部署
  subagent_type: serving-pd-deploy-subagent
  prompt: |
    scene: pd-deploy
    path: C
    phase: 3
    workdir: {workdir}

    执行本 scene。Read agents/serving-pd-deploy-subagent.md
    与 pd-deploy/SKILL.md（invoke=pipeline）。
    仅用 pd-ratio/check/rendered/。failed → rollback_to_phase1，禁止进 Phase 4。
```

## 路径 C · Phase 4

```
Task:
  description: PD配比实测
  subagent_type: serving-pd-ratio-benchmark-subagent
  prompt: |
    scene: pd-ratio-benchmark
    path: C
    phase: 4
    workdir: {workdir}
    config_md_path: {config_md_path}
    proxy_base_url: {proxy_base_url}

    执行本 scene。Read agents/serving-pd-ratio-benchmark-subagent.md
    与 pd-ratio-benchmark/SKILL.md（invoke=pipeline）。
    须 aisbench passed|skipped 且 deploy passed。禁止路径 A/B。
```
