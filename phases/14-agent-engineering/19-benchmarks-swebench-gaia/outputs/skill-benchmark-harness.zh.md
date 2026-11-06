---
name: benchmark-harness
description: Build a SWE-bench-style harness for a codebase with FAIL_TO_PASS / PASS_TO_PASS gating, contamination checks, and step-count metrics.
version: 1.0.0
phase: 14
lesson: 19
tags: [swe-bench, gaia, agentbench, harness, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个代码库和一个(bug, fix)对子列表, 构建一个基准 harness 并记录了操作指标

显示 :

1. 任务定义 : `(tid, description, state_before, fail_to_pass_tests, pass_to_pass_tests, solution)`.
2. 应用 agent的 patch运行回购的测试套房 sandbox和记录: FTP 算牌、 PTP 算牌、 步数、 tokens墙上时钟,成本。
3. 污染检查: 将发行文本与所生产的文本匹配 patch; 标记% 30% 重叠 。
4. 记者,他以 JSON+ P50/P75/P95级和费用。
5. 管理着一个CI的工作 harness 在每个公关上,并失败了 5%的回归。

艰难的拒绝 :

- Harness 中只报告一个总数字。需要每个任务的结果+分布。
- Harness 运行测试 sandbox. Agent-provided patches 是不可信的代码。
- Harness 无 PASS 的_以_帕斯门 Patches 打破其他试验 静静地退缩产品。

拒绝规则 :

- 如果用户问 "只是费利克斯_以_密码,拒绝。_以_PASS; 打破现有的测试比缺少修正更糟糕。
- 如果测试没有被锁定在特定 commit,拒绝。在测试中,漂流使得分数无法比拟。
- 如果任务与培训期间看到的问题文本重叠,请明确标出。

输出: `tasks.py`, `harness.py`, `contamination.py`, `report.py`, `README.md` 解释 sandbox,“关口,污染政策”。结尾是“下一个读什么”指向“30课”,用于在“Eval”驱动下开发 harness.
