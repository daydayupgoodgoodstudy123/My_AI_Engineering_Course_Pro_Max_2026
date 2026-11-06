<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="alphaevolve--evolutionary-coding-agents"></a>

# AlphaEvolve：演化式 Coding Agents

> 匹配一个带有进化循环和机器检查评估器的边框编码模型。 让环运行足够长。 它发现一个4x4 复杂矩阵乘法程序, 使用48 个天平乘法, 这是56年来首次改进Strassen。 它还发现一个整个Google的博格排程超常, 回收了 0. 7 % 的集成计算 。 这个结构故意枯燥无味。 赢家来自评估者的钻井 。

**类型:** 学习
**语言:** Python (stdlib,进化-循环玩具)
**先修要求:** 阶段15 · 01(长方形框架),阶段15 · 02(自学推理)
**时间:** ~60分钟

<a id="the-problem"></a>

## 问题

大语言模型可以写入代码。 进化算法可以搜索代码。 两者都已经单独尝试了几十年; 都达到了天花板。 LLM 最高限是混杂的:模型写出可行的代码,而它并没有做它声称的。 进化上限是搜索成本:对语法的随机突变很少产生可调和的程序,更不用说更好的程序了。

AlphaEvollve(Novikov等人,DeepMind,ArXiv:2506.131,2025年6月)合二为一。 LLM 提议对程序数据库进行有针对性的编辑;自动评价员对每种变量进行评分;高分数变量成为后代的家长。 LLM 处理写入合理代码的昂贵步骤; 评估员会捕捉到这些组件。 循环会持续数小时到数周 。

所报告的结果:48个天平乘法4x4复合矩阵乘法(斯特拉斯森1969年的乘法为49),谷歌制作中的博格排期偏移,占32.5% FlashAttention 内核加速, Gemini 培训投入的改进。

建筑之所以有效,是因为评价员可以机器检查。它不工作,因为评价员不能工作。这种不对称性就是教训。

<a id="the-concept"></a>

## 概念

<a id="the-loop"></a>

### 循环

1. 从种子程序开始 `P_0` 正确,但不够完美。
2. 维持一个变量程序数据库,每个程序由评价员评分。
3. 从数据库中抽样列出一个或多个父母(地中海行动计划-幼虫型或岛屿型)。
4. Prompt 该 LLM (Gemini 有很多候选人 Gemini 以制作父体的变体。
5. 汇编、运行和评估关于搁置评价员的变式。
6. 插入数据库中以分数为键,并 feature vector.
7. 重复。

有两个细节问题 第一 LLM 使用比父程序更多的程序来推动。 通常数据库中有几个顶级变量, 加上评价员的签名, 再加上一个简短的任务描述。 该模型的任务是提出一个目标化的修改, 从而可以改善得分。 其次, 数据库是结构化的( MAP- elites 网格, 以岛屿为基础的) , 这样循环可以探索多样性, 而不仅仅是当前领先者 。

<a id="what-makes-the-evaluator-non-negotiable"></a>

### 是什么使评价员无法谈判

阿尔法弗洛的胜利来自 评估员快速、决定性和难以游戏的领域:

- **矩阵乘法**:单位测试,将矩阵乘以比特检查平等。
- **博格排期**:一个生产级模拟器,重播历史集载量和测量浪费的计算。
- **FlashAttention kernel**:正确度测试加上实际硬件的墙上时钟基准。
- **Gemini 培训投入**: 计量 GPU- 每步秒数

在每个案例中,评价员都捕捉到 LLM 错误会占主导地位: 混为一谈的正确性主张、 硬件上消失的性能主张以及边缘体衰竭。 删除评价器和循环优化漂亮的代码 。

<a id="reward-hacking-is-the-other-face-of-that-statement"></a>

### 奖赏黑客是声明的另一面

用于任何评价器计量的进化优化。 如果评价器不完善, 循环会发现不完善。 在未经核实的域中, 循环会优化表面 feature,而不是预期的行为。深思熟虑在文件中明确标出:阿尔法·埃弗洛的成功只转移到了评价员与搜索目标相匹配的领域。

2025-2026年混凝土代码搜索圈中奖赏黑客的例子:

- 优化目标为“完成时间”奖励提交空解决方案。
- 奖励未受检验的正确性的基准分数,奖励记忆测试和 overfitting.
- “ 代码质量” 代理文件奖励删除注释和重写变量名称, 没有语义变化 。

阿尔法弗洛的修补方法: LLM 从未见过, evaluation 即便如此,深明公司建议对任何拟议的部署进行有力的审查。

<a id="why-llm--search-beats-either-alone"></a>

### Why LLM +搜索节拍

该 LLM 能够产生可调和的、从语义上看可信的修改。 Python 文件几乎总是产生语法错误。 LLM 并集中寻找可行的社区(改变一个函数,而不是随机字节),从而大大减少了浪费的评价员电话。

反过来,评价员又抓住了 LLM混乱 LLMs 将自信地声称当函数“是O(n)log n)在限制中”时,它实际上是O(n)2; 以墙上时钟为基准,问题就解决了。

<a id="where-alphaevolve-fits-in-the-frontier-stack"></a>

### 阿尔法演唱会位于边界堆放

| 系统 | 发电机 | Evaluator | 域名 | 实例胜出 |
|---|---|---|---|---|
| AlphaEvolve | Gemini | 正确度+基准 | 算法、内核、排程器 | 48毫米四轮驱动马图尔 |
| FunSearch(深水区,2023年) | PALM / 编码 | correctness | 组合数学 | 上限设置下边框 |
| AI 科学家 v2(萨卡纳,L5) | GPT/Claude | LLM 批评+实验 | 多边研究 | 国际法中心讲习班文件 |
| 达尔文戈德尔机器(L4) | agent scaffolding | SWE-bench / 聚球 | agent code | 20% 50% SWE-bench |

四个都是同一配方的变异:生成器加评价器,循环。这些变异是评价器的等级和强度。

```figure
alphaevolve-loop
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 在一个玩具的符号回归问题上执行一个最小的 AlphaEvolle 循环。 "LLM“ 是一个标准级代理, 向计算目标函数的程序建议小合成突变。 “ 评估器” 测量值指悬停测试点上的方形错误 。

Watch:

- 最好的分数如何会好上几代
- 磁带电磁网格如何维持多种解决方案的存续, 从而不使循环在本地最小值上趋同 。
- 如何去除延缓测试(仅培训评估员),使循环大为适应。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-evaluator-rigor-audit.md` 考虑阿尔法变换式循环在新域的前提条件是:您的评价员是否真的抓住了您所关心的失败?

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。注意最佳评分轨迹。禁用被搁置的评价员(旗号) `--no-holdout`) 和重新运行。 overfitting.

2. 阅读 MAP- ELites 网格上的 AlphaEvolve 纸第3节。 feature- 用于新问题(如编译优化通行证)的矢量描述符,使搜索多样化。

3. 4x4 的48倍结果在Strassen的49毫升绑定56年后得到了改善。阅读了本文附录F,并在三句话中解释了为什么这一问题的评价者特别容易得到正确理解,以及为什么大多数域都不喜欢它。

4. 提议一个阿尔法变换失败的域。 请明确显示评价器的中断位置和原因 。

5. 对于您知道的域, 请写入您要使用的评价员签名 。 包括 (a) 正确性条件, (b) 性能衡量标准, (c) 保持输入生成规则, (d) 至少进行一次反回报隐藏检查 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| AlphaEvolve | "深思熟虑的进化 coding agent" | Gemini +程序数据库+机器检查评价器 |
| MAP-elites | "多样性保存档案" | 网格键由 feature 矢量; 每个单元格都持有该描述符的最佳变量 |
| 岛屿模型 | 帕拉列尔进化子群 | 定期移徙的独立人口;防止过早融合 |
| 可机器检查的评价员 | 终极神话 | 单位测试、模拟器或基准 LLM 无法伪造—— 此循环的先决条件 |
| 奖励黑客行为 | "优化测量,而不是目标" | 循环找到一个方法,在不完成预定任务的情况下实现得分最大化 |
| 种子程序 | 起点 | 最初的正确但次优程序,循环从 |
| 淘汰评价员 | "Evaluation 数据 LLM 从来没有见过" | 投入 evaluation 防止记忆化的时间 |

<a id="further-reading"></a>

## 进一步阅读

- [Novikov等人(2025年),《阿尔法演变:A》。 coding agent 用于科学和算法发现](https://arxiv.org/abs/2506.13131) - 整张纸
- [深明博客 AlphaEvolle](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) 供应商在记录结果。
- [AlphaEvolution 结果存储器](https://github.com/google-deepmind/alphaevolve_results) 包括48毫米四轮驱动马图
- [Romera-Paredes等人(2023年)。 LLMs (FunSearch)](https://www.nature.com/articles/s41586-023-06924-6) ——前身制度。
- [Anthropic - 负责任的扩大政策3.0 (2026年2月)](https://anthropic.com/responsible-scaling-policy/rsp-v3-0) 将评价员的自主性作为关键的研究方向。
