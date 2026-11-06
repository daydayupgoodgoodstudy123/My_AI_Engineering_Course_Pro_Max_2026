<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="shared-memory-and-blackboard-patterns"></a>

# 共享记忆与黑板模式

> 2026年的多种办法中,有两种办法并存。agent 系统: **信息库** (每个人都能看到每个人的信息,如AutoGen Gen GroupChat或MetaGPT) **订阅黑板** (agents 订阅相关活动,如上下文 MCP 或矩阵框架)),两者都是多个-agent 系统,这意味着两个都是有趣的错误所在。 引用失败模式是 **内存中毒**: 1个 agent 幻觉是"事实",其他 agents 将它作为被验证的,而精确度逐渐衰减,其方式比直接崩溃更难调试。 这一课在标准级构建了两种结构,注入中毒袭击,并展示了生产过程中实际有效的三种缓解措施。

**类型:** 学习 + 构建
**语言:** Python (stdlib, `threading`)
**先修要求:** 阶段16 · 04(初级模型),阶段16 · 09(Parallel) Swarm Networks)
**时间：** ~75 分钟

<a id="problem"></a>

## 问题

Multi-agent 系统需要位置 agents 来分享事实。一个字面上的选择是“传递信息中的一切”——但这种方式又重新创造共同状态,同时增加复制。另一个办法是“给每个人一个全球日志”——但全球日志变得不受约束,容易中毒。第三个选择是“预测每个日志的视图 ” 。 agent" ——可伸缩但有计划。

当其中之一 agents 幻觉和写 hallucination 共享状态,每个下游 agent 中,该句改为: hallucination 人类的认知,推理链是五步深, 根本原因就是第三条信息。agent 精确度衰减比调试崩溃要困难。

这是记忆中毒。它是MAST分类中第二大有记录的故障家庭(Cemri等人,ArXiv:2503.13657),并且是结构性的:任何没有来源和无法写明的验证器的共享模拟设计最终都会展示出来。

<a id="concept"></a>

## 概念

<a id="the-two-main-topologies"></a>

### 两大主题

**完整消息池。**每个 agent 都读取所有消息。AutoGen GroupChat 和 MetaGPT 采用这种方式。它简单、透明、易于检查，但难以扩展到约 10 个以上的 agents，因为每个 agent 的上下文都会被其他 agents 的工作内容填满。

```
agent-A ──write──▶ ┌────────────────┐ ◀──read── agent-D
                   │ message pool   │
agent-B ──write──▶ │                │ ◀──read── agent-E
                   │ (global log)   │
agent-C ──write──▶ └────────────────┘ ◀──read── agent-F
```

**订书的黑板** Agents 声明对议题感兴趣; 基础路径仅相关信息。MCP 使用此选项(arXiv:2601.11595)和矩阵分散框架(arXiv:2511.21686),但需要先行设计,才能使订阅有意义。

```
                   ┌─ topic: prices ──┐
agent-A ──pub────▶ │                  │ ──▶ agent-D (subscribed)
                   ├─ topic: orders ──┤
agent-B ──pub────▶ │                  │ ──▶ agent-E (subscribed)
                   ├─ topic: alerts ──┤
agent-C ──pub────▶ │                  │ ──▶ agent-F (subscribed)
                   └──────────────────┘
```

<a id="when-each-wins"></a>

### 等每个人赢了

- **满池子** 赢的时候 agents 其语言是:少数,且有多种差异,对话时间短。其原因是谁说了当每个人都看到一切时微不足道的话。
- **Blackboard** 赢的时候 agents 具有许多相同的作用,但数量众多(例如,swarms),而对话是长期的。 token 成本和背景污染。

生产系统往往混合:在顶部有一个小型的全池(A/C.5/49/70,第1段)。planning 层)下黑板(工人层)。

<a id="memory-poisoning-in-one-scenario"></a>

### 一种情况下的内存中毒

Three agents 研究任务。 Agent A 是检索 agent. Agent B是总结。 Agent C是分析师

1. 取出一页,写一个信息给共享状态:“研究报告精确度提高了42%。”
2. 取出的页面上实际上写着“4.2%的改进”。
3. 表示「大部分准确率均提高42%(资料来源:A)」。
4. 校对:Soup
5. 最终报告引用了42%的绝对不存在的数字。

否 agent 崩溃, 没有测试失败。 系统“ 正常 ” hallucination 从一个 agent进入每个下游的背景 agent共同状态的推理

<a id="why-this-is-structural"></a>

### 为什么这是结构性的

没有共同的状态, agent A's hallucination 留在 A 的上下文中。 agents 将重新拉动或重新发芽,并可能赶上错误。 随着天真的共同状态,A的上下文成为每个人的背景,而A的上下文也成为了每个人的上下文。 hallucination 被洗成事实

问题不是共同的状态本身——共同的状态 **未经证明和独立核查**三个缓解措施都涉及这一点:

1. **每一个书写上属性来源 。** 每一个在共享的州记录  谁写,何时,根据什么 prompt,以及(如果适用)什么来源 agent 引用。 agents 读到的怀疑 关键出处。
2. **版本写作; 将其作为附件处理 。** 校正是取代旧的而非在位更新的新条目。 审计线索被保存 。
3. **保留至少一个 agent 无法写到共享状态。** 仅读校验器 agent 样本条目、 重设源和标记不一致。 由于无法写入该池, 它不能被池子毒死 。

<a id="blackboard-precedent-hayes-roth-1985"></a>

### 黑板先例(Hayes-Roth,1985年)

黑板模式在日期前 LLM agents 海斯罗斯(1985年,“黑板结构用于控制”)描述了观察全球黑板、提供部分解决方案和触发其他来源的专家知识来源。MCP,矩阵)是相同的模式 LLM agents 知识来源和 JSON 泡沫是部分解决方案。 旧文献记载了现代系统重新发现的写作争议、机会控制和一致性的解决方案。

<a id="projection-vs-full-view"></a>

### 投影与完整视图

纯黑板给每个用户都提供相同的投影(主题范围)。 **per-agent projection**: 每个 agent 获得一个适合其角色的视图。 LangGraph州级的减肥剂是2026年的卡尼科化执行——减肥剂功能将全球状态折叠成一个角色特有片。

Per-agent 投影比例进一步,但需要一种计划。没有这种计划,你就会在每一个 agent的 prompt.

<a id="write-contention-patterns"></a>

### 书写方式

Multiple agents 同时写是一个货币问题,而不仅仅是 LLM 问题。三种模式的工作:

- **序列编剧(单曲制片人)。** 全部都写成,通过一个协调员 agent 简单,但有瓶颈
- **与版本的优化共通货币。** 每个条目都有版本; 作者在版本不匹配和重试时失败。 经典数据库技术 。
- **主题分割 。** Different agents 具有不同的主题。 没有跨主题的争论。 需要设计分割边界 。

大部分 2026 框架默认为连续写入, 因为 LLM 电话太慢了 争吵很少 瓶颈也没有伤害

<a id="the-unwritable-verifier"></a>

### 不可写校验程序

最能吸收载荷的缓解是只读核查器。

- 验证人与团队共享信息(读黑板或游泳池)。
- 验证者没有共享状态的写手柄,只有单独的核查渠道。
- 验证者独立获取文章引用的来源。
- 验证人自己的产出被置于人类或单独决定的轨道上 agent永远不要进水池

如果不进行这种分离,核查者的产出将成为池内的新条目,这意味着一个有毒的池子毒害了核查者,从而毒害了其核查工作。

```figure
swarm-blackboard
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 在标准字中执行两个表层 Python 加上玩具中毒袭击和三点缓解

- `MessagePool` - 安全附件,只读出全数。
- `Blackboard` - 主题保镖/子公司,每 -agent subscriptions.
- `ProvenanceEntry` - 每一笔记录(写作、时间戳、提示)_散列, 源代码_uri).
- `PoisoningScenario` - 运行一个三 -agent 研究任务 agent 幻觉小数点,打印最终报告。
- `Verifier` - 仅读 agent 重新输入源代码和标记不一致。 使用相同的假设情景, 由当前验证者执行 。

Run:

```
python3 code/main.py
```

预期产出:
- 运行 1 (无验证器): 42%的幻觉会传播到最终报告 。
- 运行 2 ( 带有核查器): 验证人标出不一致之处, 集合点被标为“ 标签” , 最后报告包含一个撤回 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-memory-auditor.md` 是一种审计任何多功能的技巧agent 系统共享的原始设计, 版本和验证分离。 运行于新的多功能-agent 生产前的建筑。

<a id="ship-it"></a>

## 交付成果

对于任何共享的模拟设计:

- 记录每篇著作的出处 : `(writer, timestamp, prompt_hash, tool_calls_cited, source_uri)`.
- 仅设置日志附件。 校正是引用被取代的条目的新条目 。
- 至少部署一个只读校验器 agent 具有独立的源访问。
- 路线验证器输出到一个单独的频道, 而不是返回到共享的池子 。
- 记录写作比例,即超会话——上升比例早期证明 hallucination patterns.

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。确认运行 1 将 hallucination 跑两步就抓到了
2. 添加一个秒 hallucination: agent B 发明了一个数据集大小。 验证器应该同时进行, 而不是手动为两者调整 。
3. 将整池切换为带有主题分区的黑板( A)`prices`, `summaries`, `analyses`哪些中毒情况使专题分割更难完成,哪些情况没有帮助?
4. 读海斯- 罗斯(1985年,“黑板结构用于控制”),从本文中未讨论过的2026年系统将从中受益的论文中找出两种控制模式。
5. 读 CA -MCP 将共享上下文存储器映射为信件 Pool 或 Blackboard 类, 以 `code/main.py`哪个原始人...MCP 在上面加吗?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 信件库 | "分享聊天历史" | 仅附加日志 agent 完全透明,缩放不力 |
| Blackboard | “共享的工作空间” | 主题主播酒吧/子。 Agents 订阅相关主题。 缩放更远 。 |
| 出处 | "谁写的" | 每一书上的数据: 作家、时间戳 prompt来源 |
| 内存中毒 | "Hallucinations spreading" | One agent错误进入共享状态, 下游 agents 把它当作事实 |
| Append-only | "没有现成的更新" | 校正是取代新条目。 保存审计线索 。 |
| 不可写校验器 | (独立审计员) | Read-only agent 重新定位源头和标记不一致 |
| 投影 | "扫荡的风景" | Per-agent 视图从全球状态计算。 LangGraph 减少是卡门式的 |
| 知识来源 | "Specialist agent" | 海斯罗斯的1985年黑板参与者任期 |

<a id="further-reading"></a>

## 进一步阅读

- [Cemri等人——为什么要做多Agent LLM 系统失效?](https://arxiv.org/abs/2503.13657) MAST分类;记忆中毒是一个协调失败的子家庭
- [CA-MCP - 上下文软件多功能服务 MCP](https://arxiv.org/abs/2601.11595) - 共同使用环境仓库,以进行协调 MCP servers
- [矩阵——分散式多agent framework](https://arxiv.org/abs/2511.21686) 信息队的黑板没有中央管弦
- [LangGraph 状态和减少因素](https://docs.langchain.com/oss/python/langgraph/workflows-agents) - 每一个...agent 生产预测模式
- [Anthropic - 我们如何建造我们的多 -agent 研究系统](https://www.anthropic.com/engineering/multi-agent-research-system) 生产部署的出处和核查说明
