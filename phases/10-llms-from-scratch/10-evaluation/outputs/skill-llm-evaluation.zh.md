---
name: skill-llm-evaluation
description: Decision framework for choosing the right LLM evaluation strategy based on task type, budget, and requirements
version: 1.0.0
phase: 10
lesson: 10
tags: [evaluation, evals, benchmarks, llm-as-judge, elo, metrics]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="llm-evaluation-strategy"></a>

# LLM Evaluation Strategy

评估时 LLM 系统,应用此决定框架来选择正确的方法。

<a id="when-to-use-each-eval-type"></a>

## 何时使用每种反演类型

**基准(MLU、人道评估、SWE-bench):** 您正在做初始模型选择。 您需要将 10 个候选模型缩小到 3 个 。 基准给出粗略的排名, 费用为零 。 不要使用基准作为最终 evaluation.

**自定义反调 :** 您正在构建用于生产。 您有特定故障模式的具体任务。 唯一 evaluation 预测真实世界的性能。 原型的最低50个测试病例, 生产200+。

**LLM- 判决:** 你的任务没有期限(总结、写作、对话)。 Exact match 和 token 重叠度量太僵硬。 LLM- 法官费用 - 每判决费用 - 0.01美元, 并且同意人 ~ 80%的时间。 总是使用标语, 不含糊 prompt.

**人类评估:** 利害关系重大,自动衡量标准不一致。 人类评估是事实真相,但每次判决要花费1美元至2.00美元。 calibration 自动测量。

**双向比较的 ELO :** 你正在比较同一任务上的多重模型。 相配比绝对评分更可靠, 因为人类( 和 LLM 法官)比相对判决要好。

<a id="scoring-function-selection"></a>

## 排序函数选择

- **Exact match**:分类、实体采掘、 structured outputs 有已知答案
- **Token F1**:部分信贷很重要的提取任务
- **ROUGE-L -L -我没事**缩略语: 翻译
- **BLEU**:机器翻译
- **LLM- 以判决方式**:无限制的一代、对话质量、有用性
- **Execution-based**: 代码生成(运行代码,检查测试通过与否)
- **符合方案要求**: structured outputs (进行 JSON 是否与计划相符? )

<a id="red-flags-in-eval-design"></a>

## 模拟设计中的红旗

- Eval set 少于50个案例:结果在统计上毫无意义
- 没有突出的例子: 你测量的是快乐的状态, 总是高于现实世界
- 单一度量:不同的度量显示不同的故事,至少使用两个
- 无版本: 您无法跟踪未版本的改进 eval sets
- Eval set 污染: 从未包括 eval 示例 fine-tuning 数据或 few-shot prompts
- 只测试一个模型:您需要一个基准( 即使是简单的超常) 来比较

<a id="eval-pipeline-checklist"></a>

## Eval 输油管核对表

1. 准确定义任务( 不是“ 回答问题” 而是“ 将支持票分类为5 类 ” )
2. 创建横跨幸福路径、边缘路径和已知回归的测试案例
3. 选择适合任务类型的 2-3 评分函数
4. 根据生产要求设定出/失关阈值
5. 自动执行: 一个命令运行整个套件
6. 版本一切: 测试案例, 评分函数, prompts, 模型版本
7. 运行于每个变化 : prompt 更新、 模式交换、 代码部署
8. 跟踪趋势:一个分数就是噪音,一个趋势线是信号
9. 每季度校准人类判断
10. 发现生产失败时添加回归案例
