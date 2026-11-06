<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="generative-agents-and-emergent-simulation"></a>

# 生成式 Agents 与涌现模拟

> 朴等人,2023年(UIST ' 23,arXiv:2304.0442) **Smallville**, 一个 sandbox 第25项 agents,有一个三部分结构: **内存流** (自然语言日志) **reflection** (高层次综合 agent 产生它自己的溪流), **plan** 里程碑式的结果是情人节派对的出现: agent 制作了邀请函, 由24个用户组成, agents 。 缩写显示所有三个组成部分都是要证明可信的。 记录中的错误是空间- 北向错误( 进入封闭的商店, 共享单人浴室) 。 这是用于此目的的参考结构 。 agent 模拟和多agent social evaluation 2026年 开始

**类型：** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 · 04(原始模型),阶段16 · 13(共有内存)
**时间：** ~75分钟

<a id="problem"></a>

## 问题

多数是多agent 系统是严格标定的团队: 计划、 代码、 审评员审查。 这对定义明确的任务有效。 它不捕捉当 agents 人类的记忆力、优先秩序和开放世界。 研究、社会模拟以及日益激烈的游戏AI需要第二种类型。

小型村建筑是它的基准 直到公园2023年 agent 模拟是浅脚本追随者; 之后, 模式是默认的基因 agents 在一个开放的世界里,如果你建立一个 agent 2026年的模拟,你要么是使用Smallville的三个组件,要么是明确说明为什么你没有。

<a id="concept"></a>

## 概念

<a id="the-three-components"></a>

### 三个组成部分

**记忆流** 仅附加的观察、 动作、 反射和计划日志。 每个条目都有时间戳、 类型、 描述( 自然语言) 和衍生元数据 : **recency**, **importance** (自评10) agent), 和 **relevance** (cosine similarity 至当前查询)

```
[2026-02-14 09:12:03] observation: Isabella Rodriguez asked me if I like jazz
[2026-02-14 09:14:22] reflection:   I enjoy long conversations about music
[2026-02-14 10:05:00] plan:         Attend Isabella's Valentine's Day party tonight
```

记忆检索结合了三个分数: `score = w_recency * e^(-decay * age) + w_importance * importance + w_relevance * cos_sim`。最大条目输入当前 prompt.

**Reflection.** 定期(每场回忆或重要事件) agent 生成从最近记忆中生成的更高级的合成。 反射条目会回到流中, 并且可以像其他任何记忆一样被检索到 。 agents 建立“谅解”——建筑相当于长期的信念。

**Plan.** 上下分解。 首先, 日间计划( “ 去工作, 和克劳斯一起吃晚饭 ” ) 。 然后是小时计划。 然后是行动计划。 计划可以被重新显示: 当观察与计划相矛盾时, 计划 agent 重新规划受影响的部分。

<a id="why-all-three-matter-ablation"></a>

### 为什么这三件事都重要

朴等人在每次观察、反射和计划上都流出污点。

- 不使用 **observation** 该 agent 错过了背景 和行为 陈旧的信仰。
- 不使用 **reflection** 该 agent 无法形成更高层次的信念; 互动保持浅薄 。
- 不使用 **plan** 行为会变成反应性噪音;目标会消失。

三个人的可信任得分最高;任何一种的下降都会产生可衡量的倒退。

<a id="the-valentines-day-emergence"></a>

### 情人节的出现

One agent以「2月14日下午5点在霍布斯咖啡厅举办情人节派对」为目的。 agents 不接受这种种子。模拟天数:

1. 伊莎贝拉的计划包括邀请人们
2. 每份邀请都变成邻居记忆流中的观察。
3. 邻居的反射产生了信念: "伊莎贝拉在办派对"
4. 邻居的计划包括"2月14日的派对"
5. 邻居告诉邻居,邀请函没有中央协调
6. 2月14日下午5点, agents 集合在霍布斯咖啡厅。

这是技术意义上的出现:系统层面的行为(一个政党)产生于当地的互动(双边邀请+个人邀请)。 planning没有中央指挥员

<a id="the-documented-failure-modes"></a>

### 记录失败模式

朴等人明确文件:

- **空间规范错误。** Agents 走进封闭的商店 Agents 试着用同一个单人浴室 Agents 模式不能从环境本身推断出社会-物理规范。
- **记忆溢出。** 深模拟会增加记忆- 恢复成本。 实际的补救方法: 定期记忆压缩( 缩放和质) , 低重要性条目的衰变 。
- **Reflection hallucination.** 反射可以创造在内存流中不存在的关系。 减缓: 包括反射中的源内存代号 prompts 并在检索时进行验证。

这些是生产相关的故障模式:任何2026年 agent 模拟继承它们。

<a id="three-component-implementation-rules"></a>

### 三部分执行规则

1. **记忆是只附加的 。** 绝不变换记忆条目。 校正是新条目 。
2. **重要分数便宜** 打电话 LLM 以在写时对重要性1-10进行评分。
3. **检索排行, 不过滤 。** 以组合分数表示最大分数; 不使用硬过滤器( 它会丢失上下文) 。
4. **反射定期运行。** 当未处理记忆的重要性总和超过一个阈值(例如150)时触发。
5. **计划是可改的** 当新的观察与计划相矛盾时,只恢复受影响的部分,而不是整个计划。

<a id="generative-agents-beyond-smallville"></a>

### Generative agents 斯莫维尔城外

2024-2026年的后续文献扩展了这一结构:

- **Multi-agent 社会模拟,用于政策/市场研究。** 类似小村的人口模拟用户行为,以应对 features。比 A/B 测试快;准确性受到质疑。
- **NPC 游戏AI。** 小型村火箭榴弹 agents 产生突发故事线,而不是脚本式的探索。
- **Generative-agent evaluation benchmarks.** 衡量标准不是任务准确性,而是可信赖性+长期行为的一致性。

结构是参考。 扩展交换组件( 存储存储器、 检索放大反射器、 神经同步计划) , 但保留三部分结构 。

<a id="why-this-matters-for-multi-agent-engineering"></a>

### 为什么这对多 -agent engineering

斯莫维尔就是这个概念的证明agent 当组件正确时, 生成是廉价的。 架构现已在开放源码模型上复制( 较小) LLMs 任何需要生产系统 **新出现的社会行为** 使用此形状。 任何需要的系统 **执行紧凑的任务** 使用主管/角色/原始模式 。

```figure
a5-memory-reflection
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行标准字中的三部分 Python 带有脚本 agent 政策(无实际数据) LLM演示以小型形式复制了情人节的派对:

- `MemoryStream` - 仅附记录,并附有回音/重要性/相关性检索。
- `reflect(stream)` 刻画的反射力 超过最近的高度重要性记忆
- `plan(agent_state)` - 根据目前信仰制定日间和小时级计划。
- 设想:5 agents. Agent 1个开始于“下午5点的推倒派对”。 agents converge.

Run:

```
python3 code/main.py
```

预期产出: 滴答勾 trace。在最后的勾点上,至少5个中3个 agents 向党展示他们的计划,他们聚集在党的地点。

<a id="use-it"></a>

## 实际应用

`outputs/skill-simulation-designer.md` 设计一个基因化的agent 模拟: agents记忆力、反射声、计划视野 evaluation metric.

<a id="ship-it"></a>

## 交付成果

生产模拟规则:

- **记忆是数据库。** 选择一个比例尺的实行( 矢量 DB, Postgres) 。 内模标准是原型 。
- **记录检索 trace.** 每一次动作,都要记录驱动它的顶级记忆。这是你的调试能力。
- **预算/agent tokens.** 每个 agent检索 + 反射 + 每个勾选为 O(k) LLM 电话 agents × T t 勾选 × 电话- 点击 可能会使预算相形见绌。
- **定期的内存** 总结低重要性条目。 保留政策是一个设计决定, 不是细节 。
- **侦查空间/社会规范的违反情况** 很明显,建筑学没有学习它们

<a id="exercises"></a>

## 练习

1. Run `code/main.py`确认 3+ agents 聚到派对上,加把劲 agents 至10——这种出现是否仍然发生?
2. 移除反射步骤。 行为看起来像什么? 公园2023年的烧伤结果地图 。
3. 引入一个竞争的种子目标 (“ Klaus 想要在下午5点做研究演讲 ” ) 。 Do agents 分裂,还是一个目标主宰?什么决定它?
4. 增加空间限制:霍布斯咖啡厅最多4个 agents。模拟是优雅地处理溢出,还是击中了“单人浴室”的故障模式?
5. 读 Park 等人(arXiv:2304.0442) 第6节(行为实验)。 识别一种在您的微型中无法复制的行为。 您需要强化该建筑的哪个组成部分 ?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 内存流 | "该 agent日记 | 仅附加观测、行动、反思和计划记录。 |
| Recency | "记忆有多新" | 年龄指数分数 |
| Importance | "多少钱 agent care" | 写作时的10分分,快 |
| Relevance | "与当前查询的关系" | Cosine similarity (embedding-based). |
| 反思 | 高阶信仰 | 由最近记忆产生的合成,重新作为新的记忆被吸收。 |
| Plan | "日/小时/行动分解" | 上下计划树,当观测结果相矛盾时可以反射 |
| Smallville | 帕克2023年的 sandbox" | 25-agent 模拟了情人节的出现 |
| Believability | 质量衡量标准 | 人类的强盗对行为是否合理有分数 agent. |

<a id="further-reading"></a>

## 进一步阅读

- [朴等人——创造 Agents:人类行为互动模拟](https://arxiv.org/abs/2304.03442) 参考结构
- [UIST ' 23 页面](https://dl.acm.org/doi/10.1145/3586183.3606763) 出版地点
- [小镇代码发布](https://github.com/joonspk-research/generative_agents) 参考 Python implementation
- [海斯罗斯1985年-控制黑板建筑](https://www.sciencedirect.com/science/article/abs/pii/0004370285900639) 结构模拟的前科 agents
