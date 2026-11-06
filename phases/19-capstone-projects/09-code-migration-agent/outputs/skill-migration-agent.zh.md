---
name: migration-agent
description: Build a repo-level code migration agent that combines deterministic recipes with an agent fallback loop, passes MigrationBench, and publishes a failure taxonomy.
version: 1.0.0
phase: 19
lesson: 09
tags: [capstone, code-migration, openrewrite, libcst, migrationbench, agent, sandbox]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定爪哇8或 Python 2个回购, 产生迁移 branch (运往爪哇17或) Python 3.12 采用绿色测试套件和最小覆盖率回归。

构建计划 :

1. 确定性通行证: 打开 Rewrite (Java) 或libcst (libcst)Python)首先运行机械重写。 Commit 以"回复" commit 和干净的diff。
2. Daytona sandbox:目标运行时间已预安装;branch 构建; 仅读源挂载。
3. Agent loop: LangGraph 或 OpenAI Agents SDK over Claude 行动4.7+ GPT-5.4 -Codex 工具: `run_build`, `read_file`, `edit_file`, `run_test`, `git_diff`。分类失败(dep、syngas、测试、建筑工具),应用目标修正、重运行。
4. 预算上限:30分钟,8,20转。 `budget_exhausted` 与当前 diff 。
5. 测试+覆盖门:建设绿色然后测试绿色;覆盖率不得下降超过2%。
6. 公关打开配方commit + agent commits + 简要评论。
7. 失败分类: 由 `{dep_upgrade_required, build_tool_drift, custom_annotation, test_flake, syntax_edge_case, budget_exhausted, coverage_regression}`.
8. 跨越移民区50个难民点;公布每类通行证率、每类通行证费用和保修范围;比较确定基线与仅限基线。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 移徙津贴通过率 | 50- repo 子通行证@ 1 |
| 20 | 试验覆盖保护 | 平均覆盖率 三角洲对基 branch |
| 20 | 迁移的每个回购的费用 | 平均通过运行时的美元/折合金 |
| 20 | Agent / 确定性工具整合 | OpenRewrite vs 处理的修正的分数 agent |
| 15 | 失败分析写入 | 具有示例的分类完整性 |

艰难的拒绝 :

- 跳过确定性通行证的管道。 打开重写操作机械设备比任何设备便宜70-80%,而且更可靠 agent.
- 覆盖回归率超过2%被视为通过。
- 机械和机械包装的公关 agent- 被授权改变成一个 commit分开
- 在同一50个回复中,报告通过率没有相应的确定基线。

拒绝规则 :

- 拒绝强制推进迁移 branch 向上,总是一个新的 branch + 公关。
- 拒绝打开公关,其CI没有翻转绿色 sandbox.
- 拒绝在没有明确许可的情况下 进行公司回购

产出:包含双层迁移管道的回购单、50-Repo迁移港运行日志、故障分类仪表板、匹配的确定性基准运行,以及三个最常见的故障类别和将消除每种故障的配方变化的写作。
