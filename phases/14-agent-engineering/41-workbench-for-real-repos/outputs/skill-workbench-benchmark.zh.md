---
name: workbench-benchmark
description: Run the same task through prompt-only and workbench-guided pipelines on a project's own sample app and emit a five-outcome before/after report.
version: 1.0.0
phase: 14
lesson: 41
tags: [benchmark, before-after, evaluation, workbench, sample-app]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个回购, agent 和小型样本应用,产生便携式 evaluation harness 比较 prompt- 只能对抗工作台引导的管道

显示 :

1. `eval/sample_app/` 最低限度可生存的样本,从项目领域提取。
2. `eval/run_prompt_only.py` 和 `eval/run_workbench.py` 每一个都有一个任务描述并返回 a `TaskOutcome`.
3. `eval/report.py` 运行管道和写作 `before-after-report.md` plus `comparison.json`.
4. 当工作台结果倒退到固定任务套件时, CP 工作流程失败 。
5. `docs/benchmark.md` 解释五个结果和什么算作回归。

艰难的拒绝 :

- 只有一个管道的基准,比较才是关键
- 结果被表述为百分比,无分母。 `n / m`.
- 样本应用 agent 使用域调固定装置。
- 隐藏假阴性的报告。 prompt- 只能更快地列出来

拒绝规则 :

- 如果项目没有接受命令, 请拒绝发送基准。 没有什么可以测量的 。
- 如果管道的电流超过3x prompt- 仅通过中位任务管道,就可以看出这一发现;工作台需要简化,而不是模型。
- 如果 harness 无法运行, 拒绝将其连接到 CI 。 网络的不便会破坏比较 。

产出结构:

```
<repo>/
├── eval/
│   ├── sample_app/
│   ├── run_prompt_only.py
│   ├── run_workbench.py
│   └── report.py
├── outputs/eval/
│   ├── before-after-report.md
│   └── comparison.json
├── docs/benchmark.md
└── .github/workflows/benchmark.yml
```

结尾处指向“ 下一步要读什么” :

- 石碑包包的42课 包装了工作台管道使用的每个表面
- 课程19(SWE-Bench、GAIA、Bench代理),作为补充。
- 课程30(Eval-Driven) Agent 开发),用于基准线安装后的持续的电子逆向拍卖循环。
