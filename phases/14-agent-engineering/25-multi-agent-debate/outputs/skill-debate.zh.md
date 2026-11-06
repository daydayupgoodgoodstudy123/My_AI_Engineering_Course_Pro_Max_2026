---
name: debate
description: Scaffold a multi-agent debate with N debaters, R rounds, configurable topology (full mesh, star, ring), and a convergence rule.
version: 1.0.0
phase: 14
lesson: 25
tags: [debate, multi-agent, society-of-minds, sparse-topology]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以问题类别和准确性目标, 推敲辩论程序。

显示 :

1. `Debater` 与不同 prompts 避免同质化。
2. 圆形选手: 满网状, 星形, 或环形地形学。
3. 趋同规则:多数投票,以信任加权,或超级多数背负。
4. 第1轮强迫分歧:每个辩论者都提出不同的建议。
5. 成本核算:批评总业务+ token 每个问题的成本。

艰难的拒绝 :

- 所有的争论者都一样 prompt 和同样的模型,保证集体思维
- 在 N >= 6 时采用全连接拓扑，却不检查成本。辩论操作量按 O(N*R) 增长。
- 没有趋同规则,回到辩论者0的圆R回答不是趋同。

拒绝规则 :

- 如果产品对潜伏敏感( < 1s 预算),则拒绝辩论。 使用自定义( Lesson 05) 或平行表决( Lesson 12) 。
- 如果问题类别是简单的事实查询( 资本、 日期、 定义) , 则拒绝辩论 。 查找+ CRITIC (Lesson 05)便宜些。
- 如果辩论者在第一轮之后对《公约》中的任何问题没有异议 eval set,拒绝协议。您需要模型/prompt diversity.

输出: `debater.py`, `topology.py`, `convergence.py`, `runner.py`, `README.md` 解释关于《京都议定书》的N/R选择、 地形原理和成本与成本-五准确度测量 eval set。结尾处使用“下一步读什么”指向12号课(工作流程模式),如果任务简单,或28号课(课程)。orchestration 类型) embedding 在一个更大的系统中辩论。
