<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="hierarchical-architecture-and-its-failure-mode"></a>

# 层级架构及其失效模式

> 上级是嵌套的。 管理器 agents 而不是工人 CrewAI `Process.hierarchical` 是教科书版本: a `manager_llm` 动态代表任务和验证产出。 LangGraph 等值为 `create_supervisor(create_supervisor(...))`。当任务是一个真正的大行星图时,它是一种自然模式。它也是最有可能崩溃到管理循环——经理的格局。 agents 工作分配不善,错误的次产出,或者未能达成共识。 顺序往往胜过它。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 -05 (高级模式)
**时间:** ~60分钟

<a id="problem"></a>

## 问题

一旦主管的风格点击,自然的下一步是“如果工人自己是主管呢?” 团队有子团队;公司有部门。等级结构就反映了这一点。

问题: LLM 管理人员与人力资源管理者不同。 人力资源管理者对他们所了解的情况有着稳定的经验。 LLM 管理者对每个转折的大小都重新进行解释。 稍有变化,整个树群都错位了。

<a id="concept"></a>

## 概念

<a id="the-shape"></a>

### 形状

```
                 Manager
                 ┌─────┐
                 └──┬──┘
           ┌────────┴────────┐
           ▼                 ▼
       Sub-Mgr A         Sub-Mgr B
       ┌─────┐           ┌─────┐
       └──┬──┘           └──┬──┘
         ┌┴──┬──┐          ┌┴──┐
         ▼   ▼  ▼          ▼   ▼
       W1  W2  W3         W4  W5
```

每个内部节点都计划、代表与合成。只有叶子才能工作。

<a id="where-it-shines"></a>

### 闪耀着

- **清除兽形映射** 如果真正的任务是部门性的(“法律审查文件,财务审查文件,工程审查文件,然后总结执行文件”),那么等级制度是明确的。
- **当地总结。** 每个副经理在高层经理看到之前综合了团队的产出。 高层经理看到三个次级经理的摘要,而不是15个工人的产出。

<a id="where-it-breaks"></a>

### 哪里断了

三个失败模式 2026年的尸检结果不断发现:

1. **任务分配错误 。** 管理者读取目标,幻觉分解,并代表错误的子管理员。 因为子管理员顺从地按给定的操作,错误只在顶层合成上出现 — — 从一个人可能抓住它的地方去除一个级别。
2. **输出错误解释 。** 副经理返回“无法验证索赔要求X”。高级经理总结为“未确认索赔要求X”。这意味着在各个层面都漂移。
3. **共识循环。** 两位副经理意见不一;高层经理要求他们和解;他们再次撤走;工人重新运行;副经理返回的答案略有不同;循环。 CrewAI的 `Process.hierarchical` 防守在台阶上 但极限本身现在 hyperparameter.

<a id="the-deciding-question"></a>

### 决定性问题

序列( 线性管道) 对等级 : 您的任务是否真的有独立的子团队, 或者是一个假扮成树的线性流? 如果后者, 则使用顺序。 如果前者使用等级规则, 但预算明确的对调规则 。

<a id="role-framework-implementation"></a>

### 作用框架的执行

CrewAI的 `Process.hierarchical` 电线管理器 LLM 由专家组组成

- 接受最高层的任务,
- 给船员分配子任务,
- 评估乘员产出,
- 决定是否接受, 重新退出,还是转接。

Documentation: https://docs.crewai.com/en/introduction 以“等级进程”为核心概念。

<a id="graph-framework-implementation"></a>

### 图框架执行情况

LangGraph 使用嵌套 `create_supervisor` 调用。 内部主管有自己的图表; 外部主管将内部图形视为不透明的节点。 这比 CrewAI 用于调试(您可以单独通过每个图表),但更难表达树的动态重塑。

Reference: https://reference.langchain.com/python/langgraph-supervisor.

```figure
swarm-hierarchy-token
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 运行3级等级 :

- 顶级管理器: 将任务分为“ 工程” 和“ 法律” branches,
- 工程副经理:分成“前端”和“后端”工人,
- 法律助理管理人员:一名工人。

与幸福之路(大家同意)对比 **受扰动的路径** 顶级合成人报告财务结果, 原始法律问题则得不到回答。

Run:

```
python3 code/main.py
```

输出显示两个路径, 清晰的边边边“ 问什么” 和“ 交付什么” 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-hierarchy-fitness.md` 评估某一任务是否应该使用等级、顺序或平坦的主管。输入:任务描述、 org结构、 校对预算。 输出: 模式建议, 带有要防范的具体失败模式 。

<a id="ship-it"></a>

## 交付成果

船舶等级:

- **树冠深度为2** 三个级别已经隐藏了大多数错误 observability.
- **明确调节预算。** 在高级管理器必须前设定最大回合 commit通常为 2。
- **证明每个合成。** 每个节点的摘要必须说明产出的成分。
- **注意分解漂移** 记录管理器每步的分解; diff 与用户查询。 如果分解不再覆盖查询, 请发出警告 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 并比较快乐与不安。在顶级输出完全偏离用户的问题之前, 经理要交接多少级别 ?
2. 添加第三级( i 子子子子子子子子子子子子子工 ) 。 测量受扰动的路径在深度增长时如何纠正自身与完全差异 。
3. 在每个子管理员中安装一个“ canery” 工人, 总是被询问原始用户问题, 而不改变 。 使用金丝雀回答来检测分解漂移 。 管理器应该如何操作 。 react 当金丝雀不同意合成的答案时?
4. Read CrewAI的 `Process.hierarchical` 确定一个混凝土 guardrail CrewAI 应用( 步骤限制, 管理器)_说明它所针对的失败模式。
5. 比较嵌入 LangGraph 主管到 CrewAI 如何使对调循环更便宜于检测?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 分层的 | "圆形图案" | 主管对主管;只有休假才管用。 |
| Manager LLM | 老板,我说 | 该 LLM 分解,分配,和验证 在内部节点。 |
| 分解漂移 | 老板输了 | 顶级经理的分数不再涵盖最初的问题。 |
| 调节循环 | "无会议" | 副经理意见不一;最高职位的再任;工人重新运行;循环,直到预算用完。 |
| 深度-2上限 | "不要深到2层" | Empirical guardrail:3+级崩溃 observability. |
| 加那利问题 | "在每一层都彻底了解真相" | 总是被问到原始查询的工人 来检测漂移 |
| 证明链 | "谁说了什么" | Trace 从每次合成到叶子产出 产生它。 |

<a id="further-reading"></a>

## 进一步阅读

- [CrewAI 介绍——过程. 等级](https://docs.crewai.com/en/introduction) - 教科书等级与经理 LLM
- [LangGraph 主管参考](https://reference.langchain.com/python/langgraph-supervisor) 嵌套主管通过 `create_supervisor`
- [Anthropic 工程-研究系统](https://www.anthropic.com/engineering/multi-agent-research-system) - 为什么? Anthropic 故意选择平板主管而不是等级
- [Cemri等人——为什么要做多Agent LLM 系统失效?](https://arxiv.org/abs/2503.13657) MAST分类;关于协调失败的文件分解漂流的一节
