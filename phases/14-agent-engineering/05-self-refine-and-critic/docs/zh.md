<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="self-refine-and-critic-iterative-output-improvement"></a>

# Self-Refine 与 CRITIC：迭代改进输出

> 自译自审(Madaan等人,2023年)使用一种 LLM 平均收益:7项任务中20项绝对收益。 CRITIC (Gou等人,2023年)通过外部工具进行路径核查,使反馈步骤更加硬化。optimizer" (Anthropic) 或一个 guardrail 循环( 循环) (C)OpenAI Agents SDK).

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 -03(调整)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 州议会三号 prompts 解释历史为何对改进工作很重要 prompt.
- Explain CRITIC关键的观点: LLMs 无需外部核查,自我核查不可靠 grounding.
- 使用历史的自定义循环和可选外部验证器。
- 映射此图案到 Anthropic蒸发器optimizer" 工作流程和 OpenAI Agents SDK输出 guardrails.

<a id="the-problem"></a>

## 问题

一个 agent 生成一个几乎正确的答复。 也许一行代码有语法错误。 也许摘要太长。 也许计划漏掉了一个边缘框。 您想要的是: agent 批评自己的输出,然后修正它。

自我注释显示它使用单一模型, 没有训练数据, 没有RL。 但有一个渔获 : LLMs 很难在事实上自我验证 CRITIC 命名修正-通过外部工具(搜索、代码解释、计算、测试运行)的校验步骤。

这两份文件共同界定了2026年的迭代改进默认值:生成、核实(尽可能外部)、完善、核查员通过时停止。

<a id="the-concept"></a>

## 概念

<a id="self-refine-madaan-et-al-neurips-2023"></a>

### 自译自审(Madaan等人,NeurIPS 2023年)

One LLM三个角色:

```
generate(task)            -> output_0
feedback(task, output_0)  -> critique_0
refine(task, output_0, critique_0, history) -> output_1
feedback(task, output_1)  -> critique_1
refine(task, output_1, critique_1, history) -> output_2
...
stop when feedback says "no issues" or budget exhausted.
```

关键细节 : `refine` 该文件指出,历史和品质都急剧下降。

标题:+20 7项任务(数学、代码、缩略语、对话框)的平均绝对改进 GPT-4. 没有训练,没有外部工具,没有单一模型

<a id="critic-gou-et-al-arxiv230511738-v4-feb-2024"></a>

### CRITIC (Gou等人,ArXiv:2305.11738, v 2024年2月4日)

自我反省的弱点:反馈步骤 LLM 事实索赔不可靠(a) hallucination ) 通常认为生产这种产品的模式是令人信服的。 CRITIC replaces `feedback(task, output)` 与 `verify(task, output, tools)` where `tools` includes:

- 事实索赔的搜索引擎。
- 代码解释器,用于代码正确性。
- 计算器
- 具体域的核查(单位测试、打字检查、 Iinters)

核查员根据工具结果提出结构化的批评。 精细者然后对这项批评提出条件。

Headline: CRITIC 超越事实任务自我反思, 因为批评是依据的。 在没有外部验证器的任务上( 创造性的写作、 格式化) , CRITIC 减为自省。

<a id="the-stop-condition"></a>

### 停止条件

两个常见形状:

1. **验证人通过** 外部测试返回成功。 首选时( 单位测试、 键盘检查、 密码) guardrail assertion).
2. **没有发出反馈。** 模特说"产出是好的" 但很便宜,但不可靠;配有最大功率上限。

2026 默认值: 合并它们。 “ 如果验证员通过或模型表示正常, 重复= = 2 或迭代= 最大_iterations."

<a id="evaluator-optimizer-anthropic-2024"></a>

### Evaluator-Optimizer (Anthropic, 2024)

Anthropic2024年12月的日志将此名称作为五个工作流程模式之一。

- 评估者:评分输出并发表评论。
- Optimizer:根据批评修改输出。

循环直到评价员通过。 这是自定义/ 自动编辑CRITIC 在 Anthropic设计。 关键工程细节 Anthropic 补充:评价员和 optimizer prompts 其设计应大不相同,因此模型不只是橡胶印。

<a id="openai-agents-sdk-output-guardrails"></a>

### OpenAI Agents SDK 输出 guardrails

OpenAI Agents SDK 船舶的这种模式为“输出” guardrails." 一个 guardrail 是运行于 agent。如果 guardrail 旅行(筹款) `OutputGuardrailTripwireTriggered`),输出被拒绝, agent 可以重试。 Guardrails 能够调用工具(CRITIC- 型号)或纯功能(自定义式)。

<a id="2026-pitfalls"></a>

### 2026 年常见陷阱

- **橡胶戳环。** 同样的模型 与同一代人和批评 prompt 风格会集中在"看起来不错"上 prompts或更便宜的批评模式
- **Over-refinement.** 每一个精细的通行证都增加潜伏 tokens预算1-3通过;之后,升级为人性审查。
- **CRITIC 做些琐事** 如果没有外部核查器, CRITIC 堕落到自律状态; 不支付悬浮剂的检查员。

```figure
self-refine
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行自定义和 CRITIC 用于玩具任务: 生成一个给定主题的短项目列表。 校验器检查格式( 3个子弹, 每一发低于60个字符) 。 CRITIC 添加一个外部“ 事实验证器” , 惩罚已知的 hallucinations.

Components:

- `generate` - 编剧制片人
- `feedback` — LLM- 风格的自我礼仪。
- `verify_external` — CRITIC- 典型的禁闭验证器
- `refine` - 重写给定历史的输出 。
- 停止条件——验证员通过或最多4次重复。

运行：

```
python3 code/main.py
```

比较自定义对齐 CRITIC runs. CRITIC 捕获一个事实错误 grounding 自我感觉...critic 不.

<a id="use-it"></a>

## 实际应用

Anthropic评估员optimizer 是否此模式在 Claude- 友好的语言。 OpenAI Agents SDK输出 guardrails 是 CRITIC- 形状( 缩写)guardrails ) (可以调用工具)。 LangGraph 装上一个反射节点,读起来像自定义。 Google Gemini 2.5 计算机使用增加一个每步安全评价员,即 CRITIC 变量:在之前对每个动作进行验证 commit.

<a id="ship-it"></a>

## 交付成果

`outputs/skill-refine-loop.md` 配置一个评价员-optimizer 循环给定任务形状, 校验器 availability,以及循环预算。 prompts 用于发电机、评价员/验证员,以及 optimizer加上停产政策

<a id="exercises"></a>

## 练习

1. 用最大功能运行玩具_迭代=1. 是否 CRITIC 还在帮忙吗?
2. 将外部验证器替换为噪音( 随机 30% 假阳性) 。 循环能做什么 ? 这是大多数 2026 年的实际情况 guardrail stacks.
3. 执行“发电机-critic 不同的模型的变体:大模型产生,小模型批评。它比相同的模型强吗?
4. Read CRITIC 第3节(arXiv:2305.11738 v4)列出三个核查工具类别,并举一个例子。
5. Map OpenAI Agents SDK的 `output_guardrails` 以 CRITIC验证员的作用。 SDK 错什么了,有什么不对?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Self-Refine | "LLM 自己修补的 | 生成 - > 反馈 - > 在一个模式中精细循环,并有历史 |
| CRITIC | "工具基础核查" | 用外部核查器(搜索、代码、计算、测试)替换反馈 |
| Evaluator-Optimizer | "Anthropic 工作流程模式" | 两项作用——评价员的分数, optimizer 修订——循环到趋同 |
| 输出 guardrail | 检查后 | OpenAI Agents SDK 运行于 agent 产生输出 |
| 校验步骤 | 关键阶段 | 载荷决定:有根据或自定等级 |
| 校正历史 | "模型已经尝试了" | 预作改进的先前产出+评论 prompt; 下降和质量崩溃 |
| 橡胶戳环 | "自签协议失败" | Same-prompt 批评返回“ 看起来不错”; 用结构上不同的方式修正 prompts |
| 停止条件 | "信念测试" | 验证者通过或没有反馈和迭代上限;从不单项条件 |

<a id="further-reading"></a>

## 进一步阅读

- [Madaan等人,自备(arXiv:2303.17651)](https://arxiv.org/abs/2303.17651) - 银色纸
- [Gou等人, CRITIC (arXiv:2305.11738)](https://arxiv.org/abs/2305.11738) 工具基础核查
- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) ——评价员——optimizer 工作流程模式
- [OpenAI Agents SDK docs](https://openai.github.io/openai-agents-python/) — 输出 guardrails 作为 CRITIC- 形状验证器
