---
name: research-pipeline-bottleneck-audit
description: Audit a claimed AI research speedup by decomposing the pipeline into stages, computing the Amdahl ceiling, and checking whether the claim's compute assumption is explicit.
version: 1.0.0
phase: 20
lesson: 3
tags: [compute-bottleneck, amdahl, takeoff, ai-rnd-automation, research-pipeline, two-factor]
---
<!-- zh: 人工撰写中文版；英文版为依据。 -->

给定一条"AI 正在（或将要）把 AI 研究加速 X 倍"的声明——可以是预测（AI 2027、Forethought），可以是实验室表态（"我们内部研究快了 X 倍"），可以是部署 N 个 agent 副本的内部计划，也可以是治理阈值（RSP 的 AI R&D-4）——产出一页**瓶颈审计**，说清这个数字能表示什么、不能表示什么。

产出以下内容：

1. **流水线分解。** 把一个研究周期拆成若干阶段（默认：ideation、coding、experiment compute、evaluation、decision），为每个阶段分配基线墙钟时间份额 `f_i`（总和为 1）。标注每个阶段是 `labour`（AI 副本能加速）还是 `compute`（需要加速器时间）。说明份额来源：实测、估计，还是沿用本课默认值。若存在人工签字环节，单列出来并把倍率设为 1。
2. **Amdahl 天花板。** 计算 `speedup(k) = 1 / Σ_i f_i / m_i`，劳动阶段 `m_i = k`，算力阶段 `m_i = g`。报告纯软件天花板 `1 / f_compute`（g = 1）、含算力天花板 `g / f_compute`、声明隐含的 k 对应的加速比，以及达到天花板 95% 所需的 k。用 `code/main.py --compute-fraction <f_compute> --automation <k> --compute-growth <g>` 算，不要目测。
3. **串行 / 并行检查。** 若声明涉及 agent 副本数 N，按声明的或假定的 GPU 池 C 与实验时长 E 计算拐点 `N_knee = (C / E) × 单 agent 周期时间`，说明 N 在拐点之下还是之上。在拐点之上时，把"N 个 agent"翻译成"池上限加一条队列"，并报告每个副本的周期时间被拉长了多少倍。
4. **算力假设分类。** 把声明归为三类之一：
   - `software-only`（明确把算力固定；例如 AI 2027 起飞推算中的 "assuming no increases in training compute"、Forethought 的 SIE 模型）；
   - `compute-inclusive`（标尺本身已含算力增长；例如 RSP v3.1 的 "compress two years of 2018-2024 AI progress into a single year"）；
   - `ambiguous`（只给倍数、不说哪个因子动了）。
   对 `ambiguous`，把两种读法并排写出，并说明 Amdahl 天花板使哪一种更可信。
5. **点名逃生口。** 列出声明明示或暗含依赖的瓶颈逃生口：小规模实验（降低 `f_compute`，有外推风险）、更好的实验设计（每个决策需要更少实验）、把算力从部署挪到研究、硬件增长。对每一项说明什么证据能表明它真的在发生。
6. **可观测性说明。** 说明声明中的加速有多少对外部可见（算力采购、电力、训练次数），多少不可见（算法增益）。这一节供 Lesson 21 的治理分析使用。

直接否决：
- 任何不给算力份额就报告加速比的审计。"agent 快 30 倍"而没有 `f_compute`，只是关于劳动阶段的陈述，不是关于流水线的陈述。
- 任何在 N 超过拐点后仍宣称 N 个副本交付 N 倍实验的说法。拐点之上的吞吐就是池上限，到此为止。
- 任何不加说明就拿纯软件预测与含算力阈值互比（或反过来）的做法。两种标尺相差一个该时期的算力增长因子。
- 任何把公司自报的内部加速（例如由二手来源转述的 Anthropic 2026 年 8 月 "faster but not yet 2x"）当作外部实测事实的审计。必须标注来源类别。

拒绝规则：
- 若声明方说不清他们测量的周期是否包含实验算力，拒绝给出天花板，改为返回分解模板。基于猜测的 `f_compute` 算出的天花板是事后合理化。
- 若流水线根本没有实验算力阶段（纯理论或纯工程任务），直接说明 Amdahl 框架不适用，不要硬套。
- 若请求是"证明加速没有上界"，拒绝：只要存在任何一个固定阶段，加速比就被该阶段份额的倒数封顶。

输出格式（一页）：
- **阶段表**（阶段 | 份额 | 种类 | 所用倍率）
- **天花板**（纯软件 | 含算力 | 声明的 k 处 | 达 95% 所需 k）
- **队列拐点**（C、E、N_knee、N 所处位置、每副本周期拉长倍数）
- **分类**（software-only | compute-inclusive | ambiguous，附一句理由）
- **逃生口与证据**
- **可观测性**（可见 | 不可见）
- **来源类别**（原始论文 | 公司自报 | 媒体报道 | 本审计的假设）
