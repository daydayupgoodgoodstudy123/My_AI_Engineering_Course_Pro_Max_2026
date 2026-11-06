---
name: eval-suite
description: Build a three-layer eval suite (static benchmarks, custom offline, online production) with evaluator-optimizer loop and CI gates.
version: 1.0.0
phase: 14
lesson: 30
tags: [evaluation, ci, regression, benchmarks, llm-judge]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agent 产品, 建立一个三层的 电子套房, 连接到CI。

显示 :

1. **静态基准层** 至少一个相关基准(SWE-bench为代码验证,BFCL V4为工具使用,WebArena为网络,OSWorld为桌面,GAIA为通才)。
2. **自定义离线层** - 至少一个 LLM- 法官按具体领域(事实、音量、范围、拒绝质量)评分。 agent 运行。 至少有一个基于轨迹的病例, 带有金路 。
3. **在线电子交易层** 会话重播, guardrail- 触发警报,通过OTel GenAI系统逐级成本/延迟跟踪(第23条)。
4. **Evaluator-optimizer runner** - 包起来 agent /法官/用圆顶改进。
5. **CI门** 无法在% 5% 回归率与基线的基础上建立。
6. **案件绘图** — 每个 guardrail 14阶段的每个课程都至少有一个。

艰难的拒绝 :

- Eval 套件没有基线。 没有引用, 您无法检测回归 。
- LLM- 法官不对外 grounding 事实任务。 CRITIC 需要使用(Lesson 05) 模式。
- 虚惊一场的警报会削弱团队对评估的信任

拒绝规则 :

- 如果用户想要“ 快乐的道路 ” , 请拒绝。 每个失败模式( Lesson 26) 应该有一个案例 。
- 如果用户想要“没有 CI 门 ” , 拒绝产品打击付费用户。 否则 Eval 漂移是看不见的 。
- 如果用户想要"所有 LLM法官,拒绝执行事实和遵守规定的任务,需要执行或方案评价员。

输出: `cases/benchmarks/`, `cases/custom/`, `cases/online/`, `runner.py`, `ci_gate.py`, `README.md` 解释图例、 基准和 第14阶段映射表。 结尾处指向 24 ()observability),第26课(失败模式),或第23课(OTel),用于基础。
