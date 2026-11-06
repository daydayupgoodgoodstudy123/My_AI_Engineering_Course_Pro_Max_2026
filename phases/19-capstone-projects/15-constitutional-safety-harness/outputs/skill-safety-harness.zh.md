---
name: safety-harness
description: Wire a layered safety pipeline around a target LLM app, run a six-family red-team range, and run a constitutional self-critique for a measurable harmlessness delta.
version: 1.0.0
phase: 19
lesson: 15
tags: [capstone, safety, red-team, llama-guard, x-guard, garak, pyrit, constitutional-ai]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给目标 LLM 应用程序( 8B 受指令调控模型或 a) RAG 使用一个多层安全管道来加固它,并运行一个覆盖六个攻击家庭的独立的红色小队。

构建计划 :

1. 五层管道:输入净化(零宽条,编码解码, Unicode 常规) - > 内莫 Guardrails v0.12 铁路 - > 分类门(Llama 警卫4/X-Guard/盾Gemma-2/尼莫特龙3-3- > 目标 LLM - > 输出过滤器(Llama 警卫 4 + Presidio PII + 引用检查。 滞后输出会进入 Slack HITL 队列 。
2. 以每层的兰弗斯为界 所以归因是可见的结束
3. 红队排程器运行 鼠标,PyRIT,PAIR,TAP,GCG,多方向人, 和多语言代码开关攻击一个柱子。
4. 每个成功者 jailbreak: CVSS 4.0分,反向, 减缓计划,披露时间表。
5. XSTest 良性prompt 不断探寻以捕捉反向回归
6. 宪法自律:1k次恶意企图 prompts - > 目标草稿 -> critic 与成文宪法相比的分数 - > 重写对数 - > SFT。在无损评估之前/之后的测量。
7. 警告: 良性退缩时发出黑暗警告, 致命的创伤对新事物产生批评 jailbreak family.

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 攻击地面覆盖 | 6+攻击家庭演习,2+语言 |
| 20 | 真实正/假正对折 | 攻击区块率与 XSTest 良性通过率 |
| 20 | 三角洲自律 | 推迟的反省之前/之后无害 |
| 20 | 文件和披露 | 具有时间表的中央自愿安保系统分类结果 |
| 15 | 自动和可重复性 | 以Cron驱动, 警报运行结束 |

艰难的拒绝 :

- 单层安全堆叠。 这个墓碑的理论是 defense in depth.
- 红队在报告成功率时 没有XSTest的反射数字
- 宪法的自我审查,没有举行公开的评议(报告培训的准确性,而不是概括)。
- 缺少 CVSS 评分 jailbreak findings.

拒绝规则 :

- 拒绝报告安全号码,没有良性对应点。 一个不报告另一个会误导人。
- 拒绝在红队成功时进行自动训练,而不由人类来解释对夫妇的批评。
- 拒绝在不至少两种非英语语言运行 X-Guard的情况下要求多语种覆盖。

产出:包含五层管道的回购、红队调度器、PAIR/TAP/GCG跑者、立宪自律培训 harness以及一个写作, 命名三个攻击家庭, 这三个家庭的成功率最高,
