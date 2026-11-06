<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="tree-of-thoughts-and-lats-deliberate-search"></a>

# Tree of Thoughts 与 LATS：审慎搜索

> 单 chain-of-thought 轨道没有回溯的余地。 ToT(Yao等人,2023年)将推理变成一棵自树。evaluation LATS(Zhou等人,2024年)将TT与 ReAct 和反射 Monte Carlo 树搜索。 24 的游戏从4%( 计算机) 到74%( 计算机); LATS 点击92. 7%的通过率@ 1 在 HumanEval 上 。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 -03(调整)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 框架推理作为搜索:节点是“想法”,边缘是“增加”,价值是“多么有希望”。
- 使用自定义的 标准TT型 BFS 树搜索evaluation scoring.
- 扩展至带有选择 / 扩展 / 模拟 / 后方推进的玩具 LATS MCTS 循环 。
- 何时决定搜索值 token 乘数(24的伽梅,代码生成)和单轨足够时(简单A)。

<a id="the-problem"></a>

## 问题

Chain-of-thought 是一个线性行走。 如果第一步错误, 以后的每一步都会在错误的前提下工作。 在24 游戏中( 用四个数字加上 + - ×  来做 24) , GPT-4 COT 点击4%的精确度。 模型早期选择错误的子表达式, 无法恢复 。

理性需要的是提出多个候选人、评估他们、选择有希望的候选人和在死胡同出现时进行反向选择的能力。 这就是搜索。 思想树和LATS是两种卡通式的配方。

<a id="the-concept"></a>

## 概念

<a id="tree-of-thoughts-yao-et-al-neurips-2023"></a>

### 思想树(Yao等人,NeurIPS 2023)

每个节点都是一个连贯的中间步骤。 每个节点都可以扩展为 K 儿童的想法。 LLM 以评分对每个节点进行自我评价 prompt搜索探寻树——BFS、外勤部或光束。

```
                     (root: "find 24 from 4 6 4 1")
                    /               |            \
           ("6 - 4 = 2")    ("4 + 1 = 5")    ("4 * 6 = 24")  <- Score: HIGH
              /   \              |                  |
          ...    ...          ...                finish
```

Self-evaluation 是包含装入的片段。 纸张显示三种变量 : `sure / likely / impossible` classification, `1..10` 数字分数, 并在候选人中投票。 所有三个击打的 CoT 都基本上在24 的游戏上( 4% - > 74 % ) GPT-4).

<a id="lats-zhou-et-al-icml-2024"></a>

### LATS(周等人,ICML 2024)

激光器将陶特统一起来 ReAct和MCTS下反射 LLM 发挥三种作用:

- **Policy**:提出候选人的下一个行动(ReAct-style).
- **Value function**:分到部分轨道(T- T式自我反射)。
- **Self-reflector**: 在失败时, 写入一种自然语言的反射( 反射式) 并用它重新播种未来 rollouts.

环境反馈(观察)结合到 value function 搜索时使用真实的工具结果, 而不仅仅是模型意见。 打印时的结果: HumanEval pass@ 11 92. 7% 和 GPT- 4个(SOTA),WebShop平均75.9个 GPT-3.5(接近目标) gradient-based fine-tuning).

<a id="mcts-minimally"></a>

### 最低程度的MCTS

每个迭代的四个阶段:

1. **Select** 使用UCT(树的高度置信)从根到叶子。
2. **Expand** 通过这项政策培养K级儿童。
3. **Simulate** — rollout 使用保险单的孩子, value function (或环境奖励)。
4. **Backpropagate** 更新访问次数和估价。

UCT 公式 : `Q(s, a) + c * sqrt(ln N(s) / N(s, a))`第一个术语是开发;第二个术语是勘探。 `c` 每项任务。

<a id="the-cost-reality"></a>

### 成本现实

搜索爆炸 tokens。在游戏中,24个用途 ToT 100-1 000x tokens LATS 相似。 这不是免费的; 保留搜索 :

- 单一轨道明显不足的任务(24号组合,复杂代码)。
- 以墙为时的工作比正确性更重要。
- 任务要便宜可靠 value function (单位代码测试, 明确的数学目标)

搜索往往会让事情更糟,

<a id="2026-positioning"></a>

### 2026 个位置

大部分生产 agents 不要运行LATS。 他们运行 ReAct 具有基于工具的核查(CRITIC搜索显示在特殊位置:

- Coding agents 测试 value function (HumanEval-style).
- Deep-research agents 来探索多个查询路径。
- Planning- 内部的繁忙工作流程 LangGraph subgraphs.

AlphaEvoluve(列松11)是2025年的极端:对代码进行进化搜索,机能检查,边际收益(56年来头4x4马图尔改良)。

```figure
tree-of-thoughts
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- 小型的TTOBFS 在一个标准化的“选算”任务。
- 使用 UCT 选项, 在同一任务( 选择 / 扩展 / 模拟 / 后方方案) 上进行玩具 LATS MCTS 循环 。
- 一个 value function 构成一个象征性分数 加上自我反射分数

运行：

```
python3 code/main.py
```

该 trace 显示 ToT 将BFS的每个节点扩大为3个候选人,而LATS则在最佳节点上相融合 rollout 通过MCTS。 Token 两者的计数都打印。

<a id="use-it"></a>

## 实际应用

LangGraph 以托尔图式勘探为子图案; LangChain 校对:Soup LlamaIndex 船舶a `TreeOfThoughts` agent. 2026年大部分生产 agents 这种模式存在于 `if task_complexity > threshold: use_search()` 大门——见评价员——optimizer 模式,第05课。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-search-policy.md` 在线性之间选择 ReAct, ToT, LATS, 和进化搜索给定任务形状、预算和评价员的忠诚度。

<a id="exercises"></a>

## 练习

1. 使用 UCT c=0. 1 和 c= 2. 0 运行玩具 LATS。 trace?
2. 交换 value function 用于音响计分器( 添加随机的音效) 。 MCTS 仍然能找到最好的叶子吗? 它能容忍什么最低信号到噪音 ?
3. 执行光束搜索托特( 保持每层最高端) , 并比对 BFS 。 这比较紧 token budget?
4. 阅读LATS第5.1. 复制人类地球轨道数: rollouts 需要打中报告通行证吗?
5. 阅读LATS文件关于“ LATS帮助较少”的讨论。 撰写一个段落的决定规则映射任务形状, 以搜索策略 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 思想树 | "破译 CoT" | 姚等人——自带思想节点的树evaluation |
| LATS | "MCTS为 LLMs" | Zhou等人——统一TT+ ReAct + MCTS下反射 |
| UCT | 绝对的自信 | 选择平衡开采(Q)和勘探的公式(nn/n) |
| Value function | "这状况有多好" | Prompted LLM 得分或环境奖励; 反馈反向 |
| 政策 | "行动建议者" | ReAct- 风格生成器; 释放候选人的下一步想法/行动 |
| Rollout | "模拟轨道" | 使用策略从节点走向叶子, 得分值 |
| Backpropagate | 最新的祖先 | 将叶子的奖励推上路 更新访问量和Q |
| 搜索费用 | "Token explosion" | 100-1000x 24 游戏的 CoT; 采用前的预算 |

<a id="further-reading"></a>

## 进一步阅读

- [Yao等人,《思想树》(arXiv:2305.10601)](https://arxiv.org/abs/2305.10601) - 银色纸
- [Zhou等人,LATS(ARXiv:231.04406)](https://arxiv.org/abs/2310.04406) - 具有反射反馈的MCTS
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) 搜索的子图案
- [阿尔法演化(arXiv:2506.13131)](https://arxiv.org/abs/2506.13131) 与方案评价员进行渐进式搜索
