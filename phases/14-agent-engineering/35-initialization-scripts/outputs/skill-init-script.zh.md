---
name: init-script
description: Interview a project and emit a deterministic init_agent.py with five probes plus a CI workflow that refuses to launch the agent if any probe fails.
version: 1.0.0
phase: 14
lesson: 35
tags: [init, probes, ci, workbench, fail-loud]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


有了回购, agent 产品及其依赖面产生一个特定项目的内置脚本和CI线。

显示 :

1. `tools/init_agent.py` 使用这些探测器:运行时间版本、列出依赖性、测试命令可解性、需要的 env vars、状态文件更新性。
2. `init_report.json` 脚本旁边的图案记录。 每个探测器返回 `(name, status: pass|warn|fail, detail)`.
3. `.github/workflows/agent-init.yml` 运行脚本并屏蔽 agent 任何故障严重性探测器的工作
4. 一个 `pre-task` 勾勾脚本 agent 运行时间可在每次会话开始前拨打 。
5. 文件以英文印发 `docs/init.md` 列出每个探测器,其严重程度,以及如何纠正失败。

艰难的拒绝 :

- 无法超时的信号显示 启动系统必须快速且安全
- 需要的检测 LLM 电话,是确定性管道
- 包装纸吞下的非零退出代码。 失败是整个点 。
- 触摸状态的探险 idempotency。必须连续两次生成相同的报告模杜洛时间戳。

拒绝规则 :

- 如果项目没有测试命令, 请拒绝发运脚本。 将空白添加到工作台审计中 。
- 如果 env var 列表包含机密, 脚本会打印、 拒绝和强制编辑。 Init 报告不应该包含秘密 。
- 如果探针在干运行中需要超过三秒钟, 则在运货前将时间显示。 长探针会变成仪式 。

产出结构:

```
<repo>/
├── tools/
│   ├── init_agent.py
│   └── pre_task.sh
├── docs/
│   └── init.md
└── .github/
    └── workflows/
        └── agent-init.yml
```

结尾处指向“ 下一步要读什么” :

- 课程36,每个任务 scope contract 使用Init报告 `repo_paths`.
- 运行时反馈循环的37课 使用解析测试命令。
- 课程38 verification gate 取决于探针的通过
