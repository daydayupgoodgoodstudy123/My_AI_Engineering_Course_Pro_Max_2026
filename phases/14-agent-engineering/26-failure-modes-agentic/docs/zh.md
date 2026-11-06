<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="failure-modes-why-agents-break"></a>

# 失效模式：Agents 为什么会失败

> MASTT(伯克利,2025年)14项agent 3个类别中的失败模式。 Microsoft 分类记录了现有的 AI 失败是如何在 agentic 设置。 工业字段数据在五个重复模式上趋同: 幻觉动作、 范围爬升、 串联错误、 上下文丢失、 工具滥用 。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 -05(自备和 CRITIC),第14阶段 24(a)Observability)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出MASFT的三个故障类别和每种至少四种特定模式。
- 解释一下 agentic 失败会放大现有的 AI 失败模式( bias, etces, etc.) hallucination).
- 说明五个行业经常模式及其缓解措施。
- 安装标签的 Stdlib 检测器 agent traces 带有失败模式标签。

<a id="the-problem"></a>

## 问题

团队舰 agents 90%的活体体 traces。10%的失败不是随机噪音,它们属于少数重复类别。一旦可以命名它们,你可以监视它们并修复它们。

<a id="the-concept"></a>

## 概念

<a id="masft-berkeley-arxiv250313657"></a>

### MASTT(伯克利,奥地利:2503.13657)

Multi-Agent 系统故障分类。 14个失败模式分为三类。 通知员科恩的卡帕0. 88—— 这些类别是可靠的可辨别的。

核心索赔:失败是多功能-agent 系统,无 LLM 以更好的基准模型来固定限制。

<a id="microsoft-taxonomy-of-failure-mode-in-agentic-ai-systems"></a>

### 微软失败分类模式 Agentic AI 系统

- 现有的人工智能故障(比值, hallucination, data leakage放大 agentic settings.
- 自主性造成新的失败:规模上非故意行动、滥用工具、任务漂移。
- 白纸是风险登记册 agentic products.

<a id="characterizing-faults-in-agentic-ai-arxiv260306847"></a>

### 指定错误 Agentic 人工智能(自动识别器:2603.06847)

- 失败产生于 orchestration内部状态的演变和环境的相互作用
- 不只是"坏代码"或"坏模型输出。

<a id="llm-agent-hallucinations-survey-arxiv250918970"></a>

### LLM Agent Hallucinations 调查(arXiv:2509.18970)

两种主要表现:

1. **遵循指令的偏差** — agent 却不跟着 system prompt.
2. **长程背景滥用** — agent 忘记或错误应用先前的语境 。

后备错误:不执行(缺勤)、重复(重复),混乱(失序)。

<a id="the-five-industry-recurring-modes"></a>

### 五个行业-经常性模式

Arize, Galileo, NimbleBrain 2024-2026年的实地分析集中在:

1. **惊艳的动作** Agent 引用一个不存在的工具或虚构的争论。
2. **范围爬行。** Agent 将任务扩展到用户要求之外( 创建额外的 PR, 发送额外的电子邮件) 。
3. **串联错误 。** 一次错误的呼叫触发了下游效应。 SKU 幻影 hallucination 触发器 4 API 电话——一个多系统事件。
4. **失去上下文。** 长视距任务忘记了早转的制约因素。
5. **工具滥用。** 将错误的参数称为正确工具, 或完全错误的工具 。

连锁杀手就是凶手 Agents 无法区分“ 我失败了” 和“ 任务不可能完成” , 并且常常对400个错误的成功信息产生幻觉, 以关闭循环 。

<a id="mitigation-gates-at-every-step"></a>

### 缓解:每一步都有一个大门

Automated verification gates 检查事实 grounding 具体来说:

- 一步一步的安全分类(Lesson 21)。
- 工具呼叫参数验证( Lesson 06) 。
- 对照已知事实交叉核对检索到的内容(Lesson 05, CRITIC).
- 检测成功 hallucination , 并重新检验状态( 文件是否真的创建? ) 。

<a id="where-failure-monitoring-goes-wrong"></a>

### 失灵监测出错

- **只会说撞车** Most agent 失败产生有效外观的产出。 需要内容级别检查 。
- **没有基线。** 漂流探测需要最后的已知货物,没有它,你不能说“情况越来越糟”。
- **Over-alerting.** 每个失败都会生成一页, 组合和费率限制

```figure
failure-cascade
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行标准失败模式的调试器 :

- 合成 trace 包含五个模式的数据集。
- 每个模式的检测器函数( 签名模式) tool calls产出、重复行动)
- 标签每个的塔格 trace 并报告模式分布。

运行：

```
python3 code/main.py
```

产出:每-trace 标签+总分布, 凤凰式的廉价复制 trace 组合表面。

<a id="use-it"></a>

## 实际应用

- **Phoenix** 用于生产漂流集群(Lesson 24)。
- **Langfuse** 以重放会话+注释。
- **Custom** 域名签名 observability 平台无法检测

<a id="ship-it"></a>

## 交付成果

`outputs/skill-failure-detector.md` 生成适合您的域的失败模式探测器, 并连接到 trace store.

<a id="exercises"></a>

## 练习

1. 添加“ 成功” 的探测器 hallucination": agent 返回成功,但目标状态没有变化。
2. 标记100真实 traces 哪个模式占优势?
3. 执行“连带半径”测量:鉴于N级的故障,它会影响多少下游步骤?
4. 读读MASFT 14个失败模式。 选择适用于您的产品的三种模式, 写入探测器 。
5. 将一个探测器连接到 CI 任务中: 如果% 5% 的 5% , 则无法完成构建 traces 标记模式 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| MASFT | "Multi-agent 失败分类 | 伯克利14模式分类 |
| 串联错误 | "红头失败" | 早期的错误通过N级步骤传播 |
| 上下文损失 | "忘记了限制" | 长视距转弯 就会让事情提前好转 |
| 工具滥用 | "错误的工具/ 错误的参数" | 有效呼叫, 错误引用 |
| Success hallucination | 虚伪的完成 | Agent 400个索赔成功率;状态不变 |
| 范围爬行 | "Overreach" | Agent 超过要求 |
| 遵循指令的偏差 | "Disobedience" | Ignores system prompt 或用户限制 |
| 代用错误 | "计划错误" | 计划执行中的不执行、冗余、混乱 |

<a id="further-reading"></a>

## 进一步阅读

- [Cemri等人,MASTT(arXiv:2503.13657)](https://arxiv.org/abs/2503.13657) - 14种故障模式,3个类别
- [微软, 失败分类模式 Agentic AI 系统](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/final/en-us/microsoft-brand/documents/Taxonomy-of-Failure-Mode-in-Agentic-AI-Systems-Whitepaper.pdf) 风险登记册
- [亚里兹·凤凰城](https://docs.arize.com/phoenix) 在实践中的漂移集群
- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) 简单模式完全避免模式
