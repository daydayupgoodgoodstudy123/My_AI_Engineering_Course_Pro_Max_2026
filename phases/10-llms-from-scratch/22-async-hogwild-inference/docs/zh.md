<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="async-and-hogwild-inference"></a>

# 异步与 Hogwild! Inference

> Speculative decoding (第10阶段 · 15)平行 tokens 在一个序列中。 多重 -agent 框架平行于整个顺序,但强制进行明确的协调(投票、分任务分割)。 Inference (Rodianov等人,ArXiv:2504.06261)做了其他事情:同样的情况。 LLM 每个工人都看到其他工人所创造的 tokens 现代推理模型——QwQ, DeepSeek-R1 -可以自我协调 通过共享的缓存 没有任何 fine-tuning。该方法是实验性的,但它打开了一个全新的轴,即 inference 此课在 Stdlib 中执行双人模拟器 Python 并解释了为什么共同的交流合作 产生于现有模型的推理能力。

**类型:** Build
**语言:** Python (斯迪利布)
**先修要求:** 阶段10 · 12 (inference 优化,第10阶段 15(speculative decoding)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述三个共同的平行LLM 以及每个目标都有问题的名称。
- 说明核心霍格维尔德! 设置: 多个工人, 一个共享 KV cache即时协调 通过自我促进
- 计算霍格维尔德的墙上时间速度! 由工人计数函数计算 `N`任务级别平行 `p`以及协调间接费用 `c`.
- 执行两个工人Hogwild! 模拟玩具问题, 并观察新任务部门 。

<a id="the-problem"></a>

## 问题

Modern LLMs 提出长长的推理,解决棘手问题——5000 tokens 几万个 tokens 发生于深刻的数学问题。 tokens70B型号的密码,50k tokens 24分钟。互动模式不是。

Speculative decoding (第10阶段 = 15) 在一个序列中平行, 使您获得3-5x的加速。 以往的 autoregressive 解码是硬天花板,每个新的 token 取决于之前的每一个 token.

显而易见的问题:我们能否在不同的序列中平行进行?在同一问题上运行同一个模型的多个副本,让他们合作,让它们分开工作?

先前的工作:投票集合(运行N型,选择多数回答) tree-of-thought (branch 推理路径和复健),和多 -agent 框架( 指定 agent 这些都有助于具体的任务领域,它们还引入明确的协调机制——表决规则, branch- 和原状逻辑, agent-以-agent 通讯协议。

霍格维德! Inference 采取不同的做法。 KV cache每个工人都看到其他工人产生的结果 tokens 工人——没有受过任何训练或没有受到任何训练—— fine-tuning 现代推理模型(QwQ, DeepSeek-R1, 来 Claude- 家庭推理模式)可以读到共享缓存, 并说,“我看到工人2已经处理过基本案件, 所以我会做感应步骤。”

从2026年4月起,加速是取决于工作量和实验性的。 但这一想法值得了解,因为它开启了一个新的轴线,即: inference 平行。

<a id="the-concept"></a>

## 概念

<a id="the-setup"></a>

### 设置

初始化 N 工人进程, 全部运行相同 LLM,而不是每个工人 KV caches保持一个共享缓存。 `i` 生成 token `t_j`, 该 token 写入下一个位置的共享缓存。 当工人 `k` 下一步,它读取缓存的现状(包括迄今为止所有N工人产生的一切)。

一步步走,工人争着写作 tokens。没有每个工人的位置索引——缓存是一个不断增长的序列,顺序由写入到达时间决定。

<a id="why-coordination-emerges"></a>

### 为何要进行协调

工人们共用 prompt。 典型的类似 : “ 你是N 实例之一, 共同处理此问题。 每个实例都读取共享记忆, 并能看到其他实例写了什么。 避免重复工作 。 prompt 加上共享缓存就足够了。 理性模型读取缓存, 通知哪些部分的问题已经被尝试过, 并且( 通常但并不总是) 连接到未探索的部分 。

Hogwild! 论文(Rodianov等人,2025年)报导如下:

- 工人制定计划,并通过储藏处与其他工人沟通。
- 工人注意到其他工人的推理有误,并把他们叫出来。
- 工人在计划失败时会调整,并提出替代方案。
- 当被要求检查冗余时, 工人会检测到它, 并会发现它。

这一切都不需要 fine-tuning。刚出现的行为来自模型已经具备的推理能力。

<a id="the-naming"></a>

### 命名

本文名为《Hogwild! SGD》(Richt等人,2011年),无同步更新。 optimizer类比:SGD的无序工人都写给共享 parameter 向量,霍格维德! Inference工人都写到共享 KV cache两者都依赖于经验上的趋同而不是同步的保证。

<a id="rope-makes-this-tractable"></a>

### RoPE 使此可拖动

旋转位置 Embeddings (RoPE, Su 等人 2021 通过 Q 和 K 矢量的旋转编码位置信息。 token位置可以移位, 而不对齐 KV cache 加入时。 `i` 写入共享缓存的位置 `p`,其他读到这个位置的工人可以直接使用缓存条目——不需要重新轮换。

在一个有学识或绝对位置模型中, Hogwild! 需要将每个同时写的文件缓存失效 。 RoPE 让缓存保持稳定。

<a id="wall-time-math"></a>

### 长时数学

Let `T_serial` 是一个工人单独解决问题的时候。 `p` 成为任务级别可平行的分数。 `c` 是每一步的协调管理( 读取扩展缓存, 决定写什么) 。

单职工时间 : `T_serial`.
N - 工人霍格维尔德! 如果协调是免费的: `T_serial * ((1 - p) + p / N)`典型的阿姆达
包括协调间接费用: `T_serial * ((1 - p) + p / N) + c * steps_per_worker`.

工人要有生产力 `c` 与每步解码时间相比必须小。 tokens工人可以买得起几百个 tokens 在短短的聊天任务中,协调占据主导地位,霍格维尔德(Hogwild)比连环新闻还糟糕。

<a id="concrete-example"></a>

### 具体例子

理由问题:10k tokens 的 chain-of-thought假设问题 `p = 0.7` 可平行的内容(不同的证明战略、不同的案例分析)和 `c = 200` tokens 与每个工人的协调间接费用。 `N = 4` 工人:

- 序列时间: 十万分解步骤。
- 霍格维尔德! * (0.3 + 0.7 / 4) + 200 * 4 = 10000 * 0.475+800=5550解码步骤。
- 速度:10 000/5550=1.8x。

说来话长,但推理问题(50k) tokens),协调平面板板板和加速推进 2.5 -3x。 inference 等同于一种语言的线性平行, 使您能够自然地写出多线代码 。

<a id="when-to-reach-for-hogwild"></a>

### 什么时候联系霍格维德!

- 长期推理问题(千) tokens任务可以平行地在独立的次级目标之间进行。
- 受过逐步思考训练的理性模型,非理性模型不能自我协调。
- 使用一个节点, 有足够的 VRAM 来控制共享缓存和 N 工人进程。 缓存是共享的, 但每个工人都有自己的激活内存 。

<a id="when-not-to"></a>

### 何时不能

- 简短的交互聊天 协调管理控制着一切
- 不平行的任务( 单一线性证明、 单项编译) 。 N= 1 是最大值 。
- 毫无道理的模型,没有协调。
- 多节点部署。 共享缓存需要非常快速的跨工作同步 。 内节是好的; 交叉节点是潜伏灾难 。

<a id="the-experimental-status"></a>

### 实验状态

到了2026年4月,霍格维尔德(Hogwild) 是一个开放源头的研究方法 PyTorch 尚未采用生产方法。

1. Shared KV cache 整个并行流程的管理是非三重工程。
2. 新出现的协调取决于任务;基准仍在建立之中。
3. 与什么相比,速度是适度的 speculative decoding 已经交付了, 两者可以合并, 但合并工程是另一层。

值得一提,值得一试,不值得一试

```figure
continuous-batching
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行玩具霍格维尔德!

- 两个工人过程,每个过程都具有决定性 "LLM" 产生一个 token 类别(工作-)token观察...token协调...token具有已知概率。
- 共享缓存( 只列出 tokens工人们都读和写。
- 一个简单的协调逻辑:当工人看到另一个人已经做了足够的工作时 tokens 在一个类别中,它选择了另一个类别。

模拟器运行为固定的阶梯预算并报告:

- 工作总数-tokens 生产。
- 总工时(工薪级数)。
- 有效加快一个工人的速度。
- 一个 trace 哪个工人写了 token.

<a id="step-1-the-shared-cache"></a>

### 步骤1:共享缓存

两个工人都附在列表中。 简单锁定( I)Python `threading.Lock`)在实际执行中;我们模拟一个计数器。

<a id="step-2-the-worker-loop"></a>

### 步骤2:工人循环

每个工人,每一步:

- 读取当前共享缓存 。
- 决定哪些类别 token 来根据已经存在的内容进行写作。
- 写一个 token.

<a id="step-3-the-coordination-heuristic"></a>

### 步骤3:协调的累赘

如果X类已经拥有K tokens 在缓存和工人的预期类别是X, 工人切换到Y类。 这是一个玩具的备用 用于推理模型的行为 "注意这已经覆盖了, 做别的事情。"

<a id="step-4-measured-speedup"></a>

### 步骤4:计量速度

用N=1工人和N=2工人运行模拟器,总级数预算相同。tokens N=2应产生大约1.5-1.8倍以上的工作tokens 因为协调驱动的任务司。

<a id="step-5-stress-the-coordination"></a>

### 步骤5:强调协调

降低协调疲劳的敏感度。 再运行。 注意, 没有良好的协调, N=2 重复产生同样的效果 tokens 这符合报纸的观察: 诀窍只有在工人有自我协调的推理能力时才能起作用。

<a id="use-it"></a>

## 实际应用

Hogwild! 到2026年4月, 生产整合为研究级。 Yandex/ HSE/ IST 的参考实施 PyTorch- 基于和针对单节多进程设置 DeepSeek-R1和QwQ模型。

实用的采纳路径 :

1. 描述您的推理任务工作量。 tokens 与线性比较的探讨(多重战略、案件分析、搜索)。
2. 如果勘探占优势, 运行一个两个工人的实验! 测量墙壁时间改进 。
3. 如果改进低于1.3x,您将进入协调主导制度。您将返回到单一员工的行列。
4. 如果改进超过1.5x, 请按 N=4 键并再次测量。 最小化的返回通常在 N=4-8 左右 。

组合 speculative decoding:每个霍格维尔德!工人可以独立地使用分解码。两种加速法(粗略地)成倍增加,将3x分解码和1.8x霍格维尔德(Hogwild)变成对幼稚的单人解码的有效5.4x。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-parallel-inference-router.md`鉴于推理工作量概况(A/AC.96/9,第1段)token budget任务平行配置,模范家庭,部署目标) 它在投票之间, tree-of-thought, 多个 -agent霍格维尔德! speculative decoding 战略。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 使用默认设置。 确认 N=2 Hogwild! 配置产生更多工作-tokens 在同一墙壁时间,比 N=1 基线值高。

2. 降低协调的力度(套) `coordination_weight=0.1`) 重新运行。显示加速崩溃。解释为什么:当工人无法协调时,他们重复工作。

3. 计算预期的霍格维尔德!token 推理任务 `p=0.8, c=500` N=4工人,1k-token 聊天任务 `p=0.3, c=200` 和N=4。为什么一个是赢,另一个是输?

4. 读读Hogwild! 报纸第4节(初步) evaluation确定作者报告的两种失败模式。 prompt 可能会减轻每个人的痛苦。

5. 和霍格维尔德合并! speculative decoding 在玩具中:每个工人使用2 -token 内部设置代码。 报告多倍加速。 当两个工人都想要扩展相同的共享缓存前缀时, 会出现什么账务问题 ?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 霍格维德! | "帕拉列尔工人,共享缓存" | 类似情况 LLM 与共享运行同步 KV cache; 通过自我促进进行紧急协调 |
| Shared KV cache | "协调媒介" | 一个所有工人阅读和写过的单一的 KV 缓冲; 启用即时 token 工人的能见度 |
| 新兴协调 | "不需要训练" | Reasoning-capable LLMs 能够读取共享缓存和分割工作,而没有任何 fine-tuning 或明确的协议 |
| 协调间接费用(c) | "Tokens 花费的定向" | 阅读扩展缓存并决定做什么的每个工人的成本; 必须保持小与总解码时间 |
| 可平行分数(p) | "什么可以平行运行" | 任务级别平行:在全部工作中并非依次完成的部分 |
| RoPE 让霍格维德进来! | 扶轮员位置变换 | 由于位置是旋转的, 写入共享缓存不需要在之前进行重新比较 tokens |
| 表决合议 | "跑N,选择多数" | 最简单的平行 inference 地形学;可用于分类,但用于长式推理 |
| 思想树 | "Branch 和纯度" | 探讨多重问题的理由战略 branches 和小号;明确的协调逻辑 |
| Multi-agent framework | (指派子任务) | 每个 agent 获得一个角色; 一个协调器; 繁忙的协议管理 |

<a id="further-reading"></a>

## 进一步阅读

- [Rodionov等人——霍格维德! Inference: 平行 LLM 通过同时生成 Attention (arXiv:2504.06261) (单位:美元)](https://arxiv.org/abs/2504.06261) 霍格维尔德号! evaluation 在QwQ 和 DeepSeek- R1 - 转动
- [Recht, Re, Wright, Niu - Hogwild! 一种无锁平行方法 Stochastic Gradient Descent (arXiv:1106.5730, NeurIPS 2011年)](https://arxiv.org/abs/1106.5730) 原始霍格维尔德! 命名来源
- [Su等人-Roformer:增强 Transformer 具有旋转位置 Embedding (arXiv:2104.099864)](https://arxiv.org/abs/2104.09864) — RoPE的属性 inference tractable
- [姚等人——思想树:用大语言模型解决蓄意问题(arXiv:2305.10601)](https://arxiv.org/abs/2305.10601) — 该 tree-of-thought 推理策略 Hogwild! 坐直线到
- [利维坦等人——快速 Inference 来自 Transformers 通过 Speculative Decoding (arXiv:2211.17192) (单位:千美元)](https://arxiv.org/abs/2211.17192) — speculative decoding,后继平行主义Hogwild!
- [霍格维尔德! PyTorch implementation](https://github.com/eqimp/hogwild_llm) - 报纸实验的唯一真相来源
