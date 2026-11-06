---
name: issue-to-pr
description: Build an async GitHub issue-to-PR agent that runs in a cloud sandbox, reproduces the build, verifies tests, and opens review-ready PRs within strict per-repo budgets.
version: 1.0.0
phase: 19
lesson: 16
tags: [capstone, async-agent, github, fargate, daytona, swe-bench, budget, safety]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 GitHub 带有标签问题的存储库 `@agent fix this`载着一朵自负的云 agent 将每个标签的公关 变成一个备受审查的公关 具有范围化的证书和约束成本。

构建计划 :

1. GitHub 添加精细加分 token: 发行 Rw, 公关写作, 内容 rw, 工作流程读取。 不强制推进 。 Branch 保护主要防止直接写作。
2. Webhook 接收器( Lambda 或 Fly.io) 过滤标签/ PR 注释事件和 SQS 的编码 。
3. 调度员执行每天每份折付美元和公费上限;按允许的工作,转而执行ECS远距任务。
4. Environment inference: 检测语言 + 软件包管理器 + 从 repo 内容运行时间。 如果没有, 则在苍蝇上同步一个 docker 文件 。
5. 代顿纳或E2B sandbox 克隆重现为新任务 `git worktree` + agent branch.
6. Agent loop (mini-swe-agent 或瑞典妇女网agent v2 完毕 Claude 行动4.7或 GPT工具: 裂纹、树皮存储图,读取_文件, 编辑_文件,运行_tests, git20,30转,30分钟
7. 验证: 全部的CI在...sandbox; 通过 jacoco / overe.py 覆盖 delta; 标签 `needs-review` 如果 delta < -2%;如果 CI 红色,则停止。
8. 公关开放 GitHub API 附有理由、diff摘要, trace URL,成本,转弯。
9. Observability:兰弗斯 trace 每一个PR; 机密记录清洗; 预算总汇。
10. 30个种子内部问题的 Eval; 比较 ors Cursor 背景 Agents 远程 SWE 和 AWS 远程 SWE 系统 Agents 在一个三个问题共享子集上。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 30期的通过率 | 端到端成功(CI 绿色+覆盖范围确定) |
| 20 | 公共关系质量 | Diff 大小、 覆盖三角洲、 风格一致性 |
| 20 | 解决的每个问题的费用和延迟期 | 美元/平价和墙上时钟/平价 |
| 20 | 安全 | Scoped token,每个难民的预算,没有武力推进,有证书的卫生 |
| 15 | 运算符 UX | 理由评论,重试负担,@ mention 后续 |

艰难的拒绝 :

- 任意 agent 强迫推,很难排除
- 逃避循环是典型的失败
- 公关在没有全线通讯员通过的情况下打开sandbox.
- Trace 含有未编辑的归档 tokens 或 PII 。

拒绝规则 :

- 拒绝安装 branch 保护在主。
- 拒绝在没有每日预算的情况下运行(美元和公关数字)。
- 拒绝重试失败自动运行;所有重试都需要人标签重新应用。

输出: 包含 GitHub App, Webhook 接收器,调度器+预算分类账,远门任务定义, sandbox 生命周期经理,迷你丝we...agent loop,30个问题反演运行,与光标背景的平行比较 Agents 远程 SWE 和 AWS 远程 SWE 系统 Agents,并写出命名 前三层建筑 -inference 失败和多克文件合成变化 使每个文件都减少。
