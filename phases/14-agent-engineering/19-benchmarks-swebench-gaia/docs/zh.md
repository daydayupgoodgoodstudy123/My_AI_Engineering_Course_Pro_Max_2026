<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="benchmarks-swe-bench-gaia-agentbench"></a>

# 基准评测：SWE-bench、GAIA、AgentBench

> 三个基准锚 agent evaluation SWE- Bench 测试代码补丁。 GAIA 测试通用工具的使用。 Agent Bench 测试多环境推理。 了解它们的构成、 污染故事和它们不测量的事物 。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 阶段14 -06(使用工具)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 命名 SWE - Bench 测试 harness (FAIL_以_并解释为什么它关闭 单位测试。
- 解释为什么SWE-Bench 验证(OpenAI,500个任务)存在,它删除了什么。
- 描述GAIA的设计:对于人类来说简单,对于AI来说困难;三个难度。
- 命名为Bench探员的八个环境及其用于公开源代码的主要阻塞器 LLMs.
- 总结SWE-bunch+污染发现及其影响。

<a id="the-problem"></a>

## 问题

头板告诉你哪个模型能赢

- 基准是否受到污染(训练数据的解决办法、测试渗漏)。
- 基准是否衡量您关心的( 代码与浏览比一般论) 。
- 评估员是否健全( AST 匹配、 州检查、 人审查) 。

在引用数字之前,先知道三个锚定基准和它们的失败模式。

<a id="the-concept"></a>

## 概念

<a id="swe-bench-jimenez-et-al-iclr-2024-oral"></a>

### SWE-bench(Jimenez等人,2024年ICLR口头)

- 2 294 实际 GitHub 12个受欢迎的 Python repos.
- Agent 获得: 预置的代码库 commit + 自然语言问题说明。
- Agent 生产: a patch.
- 评价者:应用 patch运行回购的测试套房。 patch 必须翻转 FAIL_以_PASS 测试( 先前失败, 现在通过) 未打破 PASS_以_测试PASS。

SWE-agent (Yang等人,2024年)强调释放时达到12.5% agent- 计算机界面(文件编辑器命令,搜索模型理解的语法)。

<a id="swe-bench-verified"></a>

### 验证 SWE-Bench

OpenAI, 2024年8月。 人类完成500项任务子集。 清除模糊的问题、 不可靠的测试和确定错误的任务。 “ 完成您的 agent 船的真面目 patches?"

<a id="contamination"></a>

### 污染

- 超过94%的SWE-bench问题在大多数模式截止日期之前就已经存在。
- **SWE-bench+** 发现成功者占32.67% patches 问题文本中漏出的解决办法(模型在描述中看到了修正),31.08%由于测试覆盖率低而可疑。
- 验证后是干净的,但不是无污染的。

实际含义: SWE-bench 上得分50%的模型, 可能得35%的 SWE- bunch+。 如果您声称 SWE- bench 表现, 总是报告两者 。

<a id="gaia-mialon-et-al-nov-2023"></a>

### GAIA(Milalon等人,2023年11月)

- 466个问题;300个留给拥抱脸的私人领头板。
- 设计哲学: " 对人类而言,概念简单(92%),但对人工智能来说则困难(92%)。GPT- 4 个插件: 15%)"
- 测试推理,多modality网络,工具使用。
- 三个难度级别; 第三级需要跨越长的工具链 modalities.

通用能力是用来测量“通用能力”的。 不要与代码特定基准混淆。

<a id="agentbench-liu-et-al-iclr-2024"></a>

### Bench代理公司(Liu等人,ICLR 2024)

- 横跨代码的8个环境(Bash、DB、KG)、游戏(Alfworld、LTP)、网络(WebShop、Mind2Web)和无限制的一代。
- 多方向,~4k-13k 一次分叉转弯。
- 主要调查结果:长期推理、决策和 instruction following 阻断开放源码软件 LLMs 追赶广告

<a id="what-these-do-not-measure"></a>

### 这些人所不能衡量的,

- 实际业务成本tokens),以墙为时。
- 对抗条件下的安全行为。
- 性能在您的域(使用您自己的 反省, 课程 30) 。
- 尾部故障(基准平均值;生产操作员关心的幅度为1%)。

<a id="where-benchmarking-goes-wrong"></a>

### 基准错误的地方

- **单数固定。** SWE-bench 50%表示低于P50/P75/P95 成本+职档分配。
- **受污染的索赔。** 未经核实或经核实而报告SWE-bench+的做法有误导性。
- **Benchmark-as-development-target.** 优化基准不同于生产效用。

```figure
ae-swebench-gate
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行一个像SWE-bench(SWE)的玩具 harness:

- 合成错误修正任务( 3个任务) 。
- 脚本 "agent" 提议 patches.
- 测试员检查 FAIL_以_PASS( 错误现已修正) 和 PASS_以_护照(无损)。
- 以问题分解深度为基础的GAIA型困难分类器。

运行：

```
python3 code/main.py
```

产出显示每项任务+每项困难的分辨率率,并使评价员的规则具体化。

<a id="use-it"></a>

## 实际应用

- **验证 SWE-Bench** 代码 agents总是报告经核实的分数。
- **GAIA** 通用 agents使用私人领头板分割。
- **AgentBench** 用于多环境比较。
- **自定义的反估** 以你的产品的实际形状

<a id="ship-it"></a>

## 交付成果

`outputs/skill-benchmark-harness.md` 建立 SWE 键盘式 harness 用于任何有 FAIL 代码基对_以_平面/平面_以_口交。 口交。

<a id="exercises"></a>

## 练习

1. 端口玩具 harness 来做一个真正的回购(选择你的一个) 写3 FAIL_以_已知虫子的 PASS 测试 。
2. 添加一个分级计数标准。 在您的 3 个任务上, 有多少个 agent 每项决议的步骤?
3. 读取 SWE-bench+ 纸张。 执行解决方案漏漏检查( 将发行文本比对 diff ) 。
4. 下载一个GAIA问题 从公众分裂。 Trace 真是个 GPT-4-class agent 需要什么工具?
5. 读贝恩奇探员的每个环境分解。 哪个环境能反映您的产品表面? SOTA是什么样子的?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| SWE-bench | "Code agent benchmark" | 2,294 GitHub issues; patch 必须翻转 FAIL_以_PASS 测试 |
| 验证 SWE-Bench | 清净SWE -bench(清净的SWE -bench) | 500个人类完成的任务, OpenAI |
| FAIL_以_PASS | 固定门 | 之前失败的测试必须在 patch |
| PASS_以_PASS | "不倒退的大门" | 考试已经通过,必须经过 |
| GAIA | "通用基准" | 466个人类容易/AI-硬多工具问题 |
| AgentBench | "多点Env基准" | 8 个环境; 长方位多转 |
| 污染 | 训练队漏水 | 示范培训中的基准任务 |
| SWE-bench+ | “污染审计” | 32.67%溶液在成功的SWE-Bench中渗漏 patches |

<a id="further-reading"></a>

## 进一步阅读

- [Jimenez等人,SWE-bunch(arXiv:231.06770)](https://arxiv.org/abs/2310.06770) 原基准
- [OpenAI, SWE-Bench 验证](https://openai.com/index/introducing-swe-bench-verified/) - 分类子集
- [Mialon等人,《国际投资协议》,(arXiv:2311.12983)](https://arxiv.org/abs/2311.12983) 通用基准
- [Liu等人,Bench探员(arXiv:2308.083688)](https://arxiv.org/abs/2308.03688) - 多种环境套房
