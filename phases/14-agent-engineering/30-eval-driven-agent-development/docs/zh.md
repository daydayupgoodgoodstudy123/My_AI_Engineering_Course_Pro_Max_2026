<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="eval-driven-agent-development"></a>

# 评估驱动的 Agent 开发

> Anthropic指导: "从简单的开始 prompts,以综合的方式优化它们 evaluation,并添加多步 agentic 系统只有需要的时候。" Evaluation 并不是最后一步,而是外环驱动着14阶段的每一个选择。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 整个第14阶段
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 三个名字 evaluation 层——静态基准、自定义离线、在线生产——以及每个层的用途。
- 解释一下评价员...optimizer 紧绕
- 描述2026年的最佳做法:评估员在代码旁边,在CI运行,在门公关。
- 将14阶段的每个课 与它产生的反射案例连接起来

<a id="the-problem"></a>

## 问题

Agents 测试失败 无法预测。基准回答“ 这个模型是否具有广泛的能力?” 不是“这是” agent 向右运 patches 答案是: evaluation 以三层为单位, guardrail 并学习规则 绘制为反演案例。

<a id="the-concept"></a>

## 概念

<a id="three-evaluation-layers"></a>

### Three evaluation layers

1. **静态基准** - SWE-Bench 校验代码(Lesson 19)、WebArena/OSWorld 校验/桌面(Lesson 20)、GAIA 校验通用(Lesson 19)、BFCL V4 工具使用(Lesson 06) 。用于跨模范比较和回归带宽。污染是真实的:SWE-bench+发现32.67%的溶液渗漏。总是报告经验证的/+经审核的分数。

2. **自定义离线电子算法** - 你的产品形状:
   - LLM- 法官(Langfuse, Phoenix, Opik-课程24)。
   - 基于执行(运行 patch检查)
   - 基于轨迹( 比较对黄金的动作序列; OS World- Humman 显示在顶端) agents ) 1.4-2.7x高于黄金)。

3. **在线评价** 生产:
   - 会话重播( 朗弗斯 ) 。
   - Guardrail- 触发警报(Lesson 16, 21)。
   - 单步费用/潜伏跟踪(Lesson 23 OTel 范围)。

<a id="evaluator-optimizer-anthropic"></a>

### Evaluator-optimizer (Anthropic)

紧绕环 :

1. 投标人产生输出。
2. 评审员
3. 仔细看,直到评价员通过

这是自定义( Lesson 05) 通用的。 agent 流动你关心 可以包在评价员 -optimizer 以证明可靠性

<a id="2026-best-practice"></a>

### 2026年最佳做法

- 爱华斯住在代码旁边
- 在每个公关上都用CI
- 门在 Eval 分数上合并( 例如“ 没有回归 > 5% 相对于主数 ” ) 。
- 每个 guardrail 地图显示为反演案例。
- 每一个学习规则(弹性、支持工作流程的学习规则)都映射出失败案例。

<a id="tying-phase-14-together"></a>

### 将第14阶段合并

14阶段的每一个课程都产生反演案例:

| 课程 | 生成 Eval 大小写 |
|--------|------------------------|
| 01 Agent Loop | 预算耗尽,无穷无尽的警卫 |
| 02 连线 | 当工具失败时, 计划者会正确重排计划 |
| 03 反射 | 重试时应用已学的反射 |
| 05 自译自审/CRITIC | 法官通过精细产出 |
| 06 个工具使用 | 参数强制工作; 拒绝未知工具 |
| 07-10 内存 | 检索引用匹配源; 无效的淡化事实 |
| 12 工作流程模式 | 每种模式产生正确的输出 |
| 13 LangGraph | 恢复原样 |
| 14 自动Gen Actors | DLQ 抓取崩溃的处理器 |
| 16 OpenAI Agents SDK | Guardrail 正确输入的行程 |
| 17 Claude Agent SDK | Subagent 结果返回到管弦乐队 |
| 19-20 基准 | 测试SWE-Bench 得分, WebArena 成功率,OSWorld效率 |
| 21 计算机使用 | 注射DOM的每步安全渔获量 |
| 23 OTel | Spans 发布所需的属性 |
| 26 失败模式 | 检测器标记已知的失败 |
| 27 Prompt Injection | 个人防护系统拒绝中毒的回收 |
| 28 Orchestration | 通往右侧专家的督导路线 |
| 29 运行时形状 | DLQ 处理 N% 失败 |

如果你的Eval套房每个都有案例, 你覆盖了14阶段。

<a id="where-eval-driven-development-fails"></a>

### 由电子逆向拍卖驱动的发展失败

- **没有基线。** 没有最后已知商品的 Evals 无法读取。 保存基线 。
- **LLM- 判断没有 grounding.** 法官也幻觉 CRITIC 系统(Lesson 05)——外部工具法官。
- **超配评估** 优化电子交易与生产用途不同。 旋转实例 。
- **闪亮的电算** 非决定性情况引起假警报, 刺籽,快照状态。

```figure
ae-eval-three-layers
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 是一个标准值的 Eval harness:

- 案件登记册,有类别(基准、定制、在线)。
- 脚本 agent 正在测试中。
- Evaluator-optimizer 循环: 法官, 精细到通过或最大回合。
- CI门:总通过率+基准回归率。

运行：

```
python3 code/main.py
```

产出:每个案件出入证/失败、回归旗、CI门判决。

<a id="use-it"></a>

## 实际应用

- 写反演案 与您相同 agent code.
- 每一个公关都通过CI来查
- 无法在回归的基础上发展。
- 跟踪通过率随时间推移。
- 把所有生产失败都绑在新箱子上

<a id="ship-it"></a>

## 交付成果

`outputs/skill-eval-suite.md` 建立一个三层电子化套件 agent 带有光导门和回归跟踪的产品。

<a id="exercises"></a>

## 练习

1. 选择一个生产失败。 写入一个复制的反射案例。 您是否 agent 现在通过它?
2. 构建 LLM- 法官为您域设置三个维度( 事实、 音量、 范围) 。 得分 50 个会话 。
3. 将电子交易套件连接到 CI。 无法在 +% 5% 回归的基础上进行扩展 。
4. 增加轨迹效率衡量标准: agent 与金色的轨迹对立?
5. 将14阶段的课都映射到你套房的重审中。 缺少吗? 这是要弥补的缺口 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 静态基准 | 现货的Eval | 妇女、环境和发展网、两性平等全球倡议、Bench探员、WebArena、OSWorld |
| 自定义离线反演 | "主电量" | LLM- 判断/执行/ 运行轨道 |
| 在线电子估价 | "生产电子学" | 会话重播, guardrail 警报、费用/延迟跟踪 |
| Evaluator-optimizer | "Propose-judge-refine" | 转接法官 |
| CI门 | "梅格阻塞器" | 失败后退 |
| 基线 | "Last-known-good" | 检测回归的参考分数 |
| 轨迹效率 | "金子上铺垫" | Agent 以人类专家最低限数除以步数 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) -"开始简单, 优化与反省"
- [OpenAI, SWE-Bench 验证](https://openai.com/index/introducing-swe-bench-verified/) 确定的基准
- [Berkeley Function Calling Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html) 工具使用基准
- [兰弗兹医生](https://langfuse.com/) 实际中,评价+会话重播
