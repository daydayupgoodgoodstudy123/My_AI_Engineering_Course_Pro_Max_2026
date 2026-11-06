<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="the-autonomous-coding-agent-landscape-2026"></a>

# 自主 Coding Agent 生态概览（2026）

> 3年以下的SWE-Bench 验证率从4%上升到80.9%。 Claude 索纳特4.5在SWE中得分43.2%agent i1和59.8%在Cline 自动操作上—— 围绕模型的脚架现在与模型本身同样重要。 OpenHands(前 OpenDevin) 是最活跃的麻省理工学院许可平台, 代码Act环执行 Python 直接在 sandbox 而非 JSON tool calls标题数字隐藏了一个方法问题:在500个SWE-bench核查任务中,161个只需要1-2行修改,而SWE-bench Pro (10+线任务) 则处于同一前沿模型的23-59%。

**类型：** 了解
**语言:** Python (stdlib, 代码法案对 JSON 工具呼叫比较)
**先修要求:** 阶段14 -07(使用工具),阶段15 -01(长-长 agents)
**时间：** ~45分钟

<a id="the-problem"></a>

## 问题

"Which coding agent 问题是错误的。正确的问题是:任务分配与我的工作相符, 与我生产时的脚架相匹配, 我能得到什么端对端的可靠性?

2022年至2026年间,实地了解到脚架——检索层、规划员、 sandbox,编辑-核查循环,反馈格式 - 包含载荷。 Claude 索纳特4.5在SWE -agent v1在SWE-Bench的验证中得43.2%;Cline的自主脚手架内的同一模型得59.8%。 weights。基准模型是一个组成部分;循环是产品。

相伴的问题是基准 saturation 隐藏回归。 SWE- Bench 验证程序接近饱和,而简单任务尾巴(500项任务中需要 2 行的161项)拉起顶级评分。 在SWE- Bench Pro (10+线变)这样的分布上,真实世界质量得到更好的衡量,因为同样的领先者仍然占23-59%。

<a id="the-concept"></a>

## 概念

<a id="swe-bench-one-paragraph"></a>

### SWE-Bench, 一段

SWE-bench(Jimenez等人) 代表真实 GitHub 与地面真相有关的问题 patches 问了一个 agent 生产 patch 测试室通过。 SWE-bench 验证 (OpenAI2024年,是人类500项任务的一部分,清除了模糊不清和破碎的任务。 SWE-Bench Pro是更难的接班人——任务需要10+条变化线,而目前处于边际 agents 占23-59%的席位。

<a id="what-the-2022--2026-curve-actually-shows"></a>

### 2022年 2026年的曲线实际显示什么

- **2022**:研究模型在原始SWE-bench上为~4%。
- **2024**: GPT- 4+ 14 %的脱衣舞脚架;agent 占到~12%。
- **2025**: Claude 3.5.3.7 辅助器和SWE内部的索纳特agent 将 40%-55% 的 范围 。
- **2026**: Claude 索纳特4.5和边境竞争对手 70 -80 在SWE Epoch AI的领头板 跟踪这个现场。

斜坡来自三个复合来源:更好的基建模型、更好的脚架(CodeAct、反射、校验环)和更好的基准(经过核查的消除噪音)。

<a id="codeact-vs-json-tool-calls"></a>

### 代码法案对 JSON tool calls

OpenHands(All-Hands-AI, ArXiv:2407.16741,前OpenDevin)投了特定的建筑赌注:而不是模型排放 JSON tool calls 模式的发布 Python 代码和a Jupyter- 风格的内核运行在 sandbox. 该 agent 可以在一个动作中 绕过文件、链工具 并捕捉到自己的例外

权衡:

- **JSON tool calls**:每次行动都有一个转折;审计容易;组成性有限;默认情况下安全,因为每次通话都经过一个明确的验证人。
- **CodeAct**:一个动作可以是整个程序; 构成; 需要一个硬化的动作 sandbox (打开手使用) Docker 独立; 失败模式包含 sandbox 运行时间允许 。

两种建筑都在生产中。 代码法案在开放平台( OpenHands, smoligents) 中占据主导地位 。 JSON tool calls 管理服务仍占支配地位(第1类)Anthropic Managed Agents, OpenAI 供应商控制执行人的地方。

<a id="scaffolds-in-the-2026-landscape"></a>

### 2026年风景中的脚手架

| Scaffold | 许可证 | 执行模式 | 显著财产 |
|---|---|---|---|
| 打开手( 打开 Devin) | 麻省理工学院 | 代码法 Docker | 最活跃的打开平台; 可重播事件流 |
| SWE-agent | 麻省理工学院 | Agent- 计算机接口(ACI) | 首个端到端 SWE - Bench 脚架 |
| Aider | Apache-2 | 本地副本中的编辑- 通过 diff | 最小脚架, 强大的回归稳定性 |
| Cline | Apache-2 | VS Code agent 带有工具策略 | 索纳特4.5号上最亮的手脚架 |
| 德文( 目标) | Proprietary | 管理 VM + 计划器 | 第一种“AI软件工程师”产品类别 |
| Claude Code | Proprietary | 权限模式+例行 | 第十课涵盖 agent loop 详细 |

<a id="why-scaffolding-dominates"></a>

### 为什么脚架占优势

编码运行是一个长方位的轨道( Lesson 1) 。 跨步的可靠性化合物。 脚手架购买点的三个地方 :

1. **Retrieval**:找到正确的文件是沉默的瓶颈。 SWE-agentACI, OpenHands的档案索引 艾达的重写图 都攻击了这个
2. **验证环**:运行测试,读取堆叠 traces,并再次尝试在 SWE 台上有一个10+点三角洲。
3. **失败遏制**: 一个 sandbox 错误后返回防止损坏。同样的模型,无论有没有验证环,看起来都是两种不同的产品。

<a id="benchmark-saturation-and-the-real-distribution"></a>

### Benchmark saturation 和真实分布

开关作者和 Epoch AI 都标注SWE-Bench 验证的SWE-Bench 具有简单尾巴:500项任务中有161项只需要1-2行修改。 高分部分是由尾巴驱动的。 SWE-Bench Pro限制在10+线修改和23-59%的回报分数,即使是边境系统也是如此。 您的生产分布几乎肯定比验证更接近于Pro 。

选择一个 agent:运行一个适合您的错误积压子集。重要的分数是代表您所运货物的任务的分数。

```figure
a5-scaffold-delta
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 比较两个玩具 agent 固定小型任务分布上的脚架:

1. 一个 **JSON tool-call** 脚架每转一个动作
2. 一个 **CodeAct** 脚架可以放出一个小 Python 开始行动

两者都使用“ 模型” (确定规则) , 这样比较就能将脚架与模型质量分开。 输出显示代码法脚架以更大的每起爆炸半径的成本以更少的转弯方式解决更多任务 。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-scaffold-audit.md` 帮助您审核一个提议的编码 --agent 采用前的脚架:检索质量、验证员存在、 sandbox 隔离, 和基准到分布合适。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。每个脚手架要多少次旋转, 同一个任务组?每个动作的爆炸半径是多少?

2. 阅读 OpenHands 纸张 (arXiv: 24007.16741)。 论文论证代码法比对 。 JSON tool calls 确定一个失败模式, 纸张确认并写下一句话, 说明该模式何时会主宰生产 。

3. 从您的错误积压中选择一个需要两个文件上10+线修改的任务。 估计( a) 下的边框模型端到端成功概率 JSON tool calls (b) 法典法案。

4. SWE-bench 验证有161个单页, 1-2行任务。 构建一个排除它们的分数。 头板如何打乱 ?

5. 读“引入 SWE-Bench 验证” (OpenAI解释用于消除模糊任务的具体方法,并列出翻译时遗漏的类别。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| SWE-bench | "编码基准" | Real GitHub 与地面真相有关的问题 patches 和测试套房 |
| 验证 SWE-Bench | "干净的子集" | 500件人手活,容易处理 |
| 妇女网 | "硬化子集" | 10+线条变化;边界座标为23-59% |
| CodeAct | "Code-as-action" | Agent emits Python; Jupyter- 式内核执行 sandbox |
| JSON tool call | "Function calling" | 每项行动都是有条理的 JSON 有效载荷在执行前得到验证 |
| Scaffold | "Agent framework" | 检索+规划器+执行器+验证器环绕基模 |
| ACI (美国)Agent- 计算机接口) | "SWE-agent格式 | 用于 LLM 人类工程学,不是人体Shell |
| 验证环 | "Test-and-retry" | 运行测试, 读取输出, 修改 patch;最大的非模型可靠性收益 |

<a id="further-reading"></a>

## 进一步阅读

- [Jimenez等人——瑞典妇女网-Bench](https://www.swebench.com/) 原基准和方法。
- [OpenAI - 介绍SWE-Bench 验证](https://openai.com/index/introducing-swe-bench-verified/) 如何建造 子集。
- [Wang等人- OpenHands: AI 软件开发者开放平台](https://arxiv.org/abs/2407.16741) - 代码法建筑和事件流设计。
- [Epoch 大赦国际——SWE-Bench 领导板](https://epoch.ai/benchmarks) - 现场记录分数
- [Anthropic 计量 agent autonomy](https://www.anthropic.com/research/measuring-agent-autonomy) 长方圆编码agent 可靠性框架。
