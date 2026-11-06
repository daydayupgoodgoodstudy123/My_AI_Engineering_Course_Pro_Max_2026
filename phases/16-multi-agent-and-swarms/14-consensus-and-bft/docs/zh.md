<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="consensus-and-byzantine-fault-tolerance-for-agents"></a>

# 面向 Agents 的共识与拜占庭容错

> 古典分布系统BFT 满足随机性 LLMs2025-2026年出现了三个研究方向: **CP-WBFT** (arXiv: 2511. 10.400) 由信任调查器对每张选票进行加权; **DecentLLMs** (arXiv:250714928)没有领头人,没有平行工人提议和几何中间线汇总; **WBFT** (arXiv:2505.05103) 将加权投票与等级结构组合合并,将核心节点和边缘节点分割开来。 Agents 是否认为今天甚至连卡勒协议都脆弱? agent 能够折中混合Agents。BFT是必需的,但还不够。这一课程建立了一个最低限度的BFT协议,输入了三 agent- 特定攻击(拜占庭谎言、合影性、相关-危险单一培养),以及衡量每个共识变异如何应对。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 第16阶段 -07(思想和辩论学会),第16阶段 13(共同记忆)
**时间：** ~75分钟

<a id="problem"></a>

## 问题

已经是N了 LLM agents 多数投票选错了,因为两个 agents 具有相关性(相同的基准模型、相同的训练数据、相同的失败模式)。 agent 碰巧是新颖的错误——因此多数人是一个虚假的多数。

现在添加一个欺骗 agent:它有目的,或者是一个共鸣者 agent: 它同意最后一位发言的人。在经典的BFT中,假设拜占庭节点是一个小部分 `f < n/3` 2026年的现实是 LLM 节点即使诚实、相互关联、互相影响,也具有随机性。 你不能把他们视为独立的伯努利选民。

经典BFT(PBFT,1999年)没有错——它不完整,它处理任意的位移。 agents 共享 a hallucination 因为他们分享了训练数据。"这个课程建基于PBFT的基金会和层次, 并基于2025-2026年的三次调整。

<a id="concept"></a>

## 概念

<a id="what-classical-bft-gives-you"></a>

### 古典BFT给你什么

Byzantine 实际的容忍失灵(Castro & Liskov, OSDI 1999) `f < n/3` 拜占庭节点。协议分为三个阶段(预设前,准备, commit)和两个原始数据(签名信件、法定人数证书)。 `n >= 3f + 1` 诚实或邪恶的节点。

保障是强有力的,但假定:

1. **独立缺陷。** 拜占庭没有协调
2. **诚实的节点是真正的诚实。** 诚实产出的正确性不是一个问题;协议只对分歧进行统一。
3. **这个问题有一个事实答案。** 就一个错误的事实达成共识仍然是协商一致。

LLM agents 违反所有三个。 agents 运行相同的基数共享错误。 “ 诚实” LLM 说到模糊的问题,"真相"就是 agents ——没有外来的神谕。

<a id="the-three-llm-specific-attacks"></a>

### 三个 LLM- 特定攻击

**拜占庭说谎** One agent 输出故意错误的回答。如果 `f < n/3`.

**阳极合身** One agent 阅读其他人在投票前的回答, 并与最后发言的人一致。 不是恶意的, 而是与最响亮的声音相关。 经典的 BFT 并不阻止这一点, 因为 agent 检查所有签名

**与性关系严重的单一文化。** Three agents 共享一个基本模型。 他们给错误的答案带来幻觉。 多数是错误的。 经典的 BFT 并不起作用, 因为所有三个“ 诚实” 都同意 。

<a id="the-2025-2026-responses"></a>

### 2025-2026年的对策

**CP-WBFT** 选民在回答时附上信任调查(自报概率,或单独报告) calibration 模型预测。 weights 以信任度标定。 报告称, 在完整图形中, +85.71% BFT 改进 。 用于缓解: 相符合性( 符合) agents 也有些人认为,

**DecentLLMs** (arXiv:250714928)无领者。 agents 提议同时进行,评价员 agents 得分建议,最后答案是得分位置的几何中位数。 `f < n/2`。Byzantine 的测谎和相关的差错(测空中位数对外值是强大的,并会拉向密度大的集群,而不是模型偏差的平均值)。

**WBFT** 具有等级结构的加权BFT组合。 weights 以响应质量加上从历史中学习的信任分来分配。 agents 变成核心和边缘; 核心 agents 一定要先达成共识,边缘 agents 缓解:可扩展性(核心共识小而快)和部分单一文化(可选择核心为多样性)。

<a id="empirical-can-ai-agents-agree-arxiv260301213"></a>

### 经验: "能爱吗? Agents 同意吗?" (arXiv:2603.01213)

文件衡量了标度协议(A/C.5/49/70,第1段)。LLM agents 同意一个单一的数值),跨多个边框模型。

- 即使没有对手 LLM agents 在许多基准中,在标度超过30%的标度上的问题上意见不一。
- 单 agent 能够拉动混合体Agents 公认为40+ 百分比离诚实基线。
- 分歧率与模式多样性相关——不同组合的分歧多于同质的(好的:与不相干的错误),但也缓慢地流动(坏的:较长的时间到协议)。

取出: BFT 赋予您对输出进行匹配的机制, 但无法告诉您对齐的产出是否正确。 与核查( 16 · 08 角色专业化)、 多样性( 16 · 15 辩论变量) 以及评价员相结合 agents (第16阶段 · 24个基准)

<a id="the-core-protocol-stripped-down"></a>

### 核心协议, 被拆掉

最小 BFT 圆 LLM agents:

```
1. task arrives; each agent i produces answer a_i
2. each agent attaches confidence probe c_i in [0, 1]
3. aggregator collects (a_i, c_i) from all n agents
4. aggregator groups by semantic cluster (equivalent answers)
5. aggregator computes weight for each cluster C:
     w(C) = sum_{i in C} c_i
6. winner = cluster with max weight, if max > threshold * sum(c_i)
   else: retry or escalate
7. minority clusters logged with provenance for post-hoc audit
```

语义组合步骤是 LLM两种答案“ 研究报告报告4. 2% ” 和“ 4.2% 改进” 是相同的组。 一次天真的弦平比检查会错过这一点。 在生产中,使用廉价的 embedding 模型或直线金银化。

<a id="threshold-tuning"></a>

### 阈值调整

该 `threshold` parameter 决定何时接受和何时重试。 太低了 : 您接受多数。 太高了 : 您从不接受任何东西 。 经验范围: 0.5-0. 67 `n=5-7` agents,小的则更高 `n`。在阈值以下,升至人或变异 agent ensemble.

<a id="where-consensus-does-not-help"></a>

### 协商一致无济于事

- **疑惑的问题** 如果问题没有事实根据,协商一致就是意见。
- **复杂的问题** 写下代码解释它——两个答案,每个独立投票。
- **反向多轮。** 如果 agents 它可以观察前几轮并模仿(Du 2023辩论),它们开始彼此同意而不管真相如何。

```figure
swarm-consensus-wave
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `AgentVoter` · 附有(回答、信任)的文字政策。
- `MajorityVote` - 传统的多元化。
- `CPWBFT` 以语义组合方式进行信心加权投票。
- `DecentLLMs` - 得分提案的几何中间汇总。
- `Scenario` 每一个集合器都按三种攻击模式运行。

执行攻击模式:

1. `byzantine`: 1个 agent 充满信心
2. `sycophancy`: 1个 agent 复制第一个答案,它看到, 匹配的信心。
3. `monoculture`:三个 agents 以适度的自信共享错误的回答( 与 cor 相关的错误) 。

Run:

```
python3 code/main.py
```

预期产出: 一张表格( 攻击、 聚合器) - > 最后答案, 并突出正确答案。 多元性失败了单一文化案例。 CPWBFT 的自信加权减轻了矛盾。 体面LLMs的几何中间值在单种文化不足人口一半时会拉向诚实的组合。

<a id="use-it"></a>

## 实际应用

`outputs/skill-consensus-designer.md` 设计一个多功能协议agent 组合:分组方法、加权、阈值和次临界轮的升级政策。

<a id="ship-it"></a>

## 交付成果

在运送任何协商一致机制之前:

- **至少用三种模式进行攻击试验** 协议应该可以预测失败,而不是沉默。
- **记录每个少数群体群集** 少数群集是您对相关错误的早期预警系统。
- **强制发射** 不准“继续辩论直到达成协议”——这奖励了恋情。
- **分开协议和正确性** 协商一致的产出交给核查者;核查者独立于整体。
- **监控协议费率** 急剧上升意味着符合性偏差;锐减意味着模型漂移。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`. 确认多元性失败了单一文化攻击,但是当单一文化信心低于0.7时,CPWBFT部分地减轻了这种攻击。
2. 添加第四个攻击模式: **静音弃权** - 一个 agent 拒绝回答 (“ 我不知道 ” ) 。 每个聚合者应该如何对待弃权者? 执行您的选择 。
3. 将语义组合从字符串卡门化转换为 embedding- 相似性(使用任何开放源码) embedding 血吸血攻击会怎么样?
4. 读取CP-WBFT( arXiv: 2511. 10. 0400) 。 执行信任方案 calibration 级数( 单行) calibration 每一个模型检查 agent自我报告的信心。 测量单种情景的准确性收益 。
5. 读 "能" Agents 同意吗?" (arXiv:2603.01213) 复制一个简化的天平-协议实验: agents,一个讽刺的问题,欺骗性的人a promptCPBBFT还是像样的LLMS会抓住它吗?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| BFT | 贝赞丁断层耐受性 | Castro-Liskov 1999年关于与美利坚合众国 `f < n/3` 任意的错误。 |
| Byzantine | "任何不检点的行为" | 一个可以说谎、传递信息、无声失败的节点——除了安全坠毁之外,什么都行。 |
| 信心调查 | "你有多确定?" | 投票时附带自报或校准者预测的概率。 |
| 语义组合 | "同样的答案,不同的词" | 将同等的答案分组后再计票。 |
| 几何中位数 | "暴风雨中心" | 最小化到取样点的距离总和。 与平均值不同, 强到外端 。 |
| Monoculture | "同样的模型,同样的失败" | 与下列情况有关的错误 agents 共享训练数据或基准模型。 |
| 阳性合体 | "用大声的声音向您求婚" | 一个 agent投票偏向谁先说/最大声。 |
| Core/Edge | 统治者BFT | 世贸贸易基金会分裂:先达成小核心共识,然后是边缘节点。 |

<a id="further-reading"></a>

## 进一步阅读

- [卡斯特罗和利斯科夫-拜占庭实际的容忍失灵(OSDI,1999年)](https://pmg.csail.mit.edu/papers/osdi99.pdf) 基金会
- [CP-WBFT——有信誉的BFT](https://arxiv.org/abs/2511.10400) 以信任为重的选票
- [体面-无头型多功能-agent consensus](https://arxiv.org/abs/2507.14928) 几何中间体汇总
- [世贸贸易基金会——带有等级结构的加权BFT](https://arxiv.org/abs/2505.05103) 核心/部分因边嵌而分开
- [爱尔 Agents Agree?](https://arxiv.org/abs/2603.01213) 卡拉萨协议的脆弱性和欺骗性攻击
