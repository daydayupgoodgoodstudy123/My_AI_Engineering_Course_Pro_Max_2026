---
name: feedback-runner
description: Wrap shell commands with deterministic stdout/stderr/exit/duration capture, persist a JSONL record per command, and refuse to advance the agent loop when feedback is missing.
version: 1.0.0
phase: 14
lesson: 37
tags: [feedback, subprocess, runner, jsonl, loop-control]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个在 shell 命令中运行的项目 agent loop,生成反馈运行器 JSONL 写着

显示 :

1. `tools/run_with_feedback.py` exposing `run_with_feedback(command: list[str], agent_note: str, timeout_s: float) -> FeedbackRecord`.
2. `feedback_record.jsonl` 工作台下的位置 每行记录一次
3. `tools/feedback_loader.py` 返回当前任务的最近的 N 记录。
4. 一个 `loop_can_advance(record) -> bool` 帮助 agent loop 说成功之前打电话
5. 测试范围包括:成功路径、非零退出、超时、缺失二进制、确定性头部/尾部短跑。

艰难的拒绝 :

- `shell=True` 任意一个跑步者,只限Argv
- 取决于墙钟或随机的补丁 sampling。同样的输入必须产生相同的记录。
- 没有记录 `duration_ms`。慢探针是结扎工作台的第一个迹象。
- 返回未约束列表的装载器。 上个 N 或页码处有 。

拒绝规则 :

- 如果工程管道通过 stdout 秘密, 拒绝发送运行器而不经过编辑步骤。 表面是被捕获的线条 。
- 如果项目有可以无限期挂载的命令, 则拒绝在不设默认超时和明确覆盖列表的情况下发运 。
- 如果跑者在工人中运行 与共享状态,拒绝跳过文件锁 周围 JSONL 附加。 多个作者会撕碎文件 。

产出结构:

```
<repo>/
├── feedback_record.jsonl
└── tools/
    ├── run_with_feedback.py
    ├── feedback_loader.py
    └── test_feedback_runner.py
```

结尾处指向“ 下一步要读什么” :

- 课程38 verification gate 记录被消耗了
- 课程39 reviewer agent 读取在评分时的反馈。
- OTel GenAI 公约的第23课,在反馈可靠时添加到遥测方面。
