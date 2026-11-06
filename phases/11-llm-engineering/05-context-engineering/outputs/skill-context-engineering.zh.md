---
name: skill-context-engineering
description: Decision framework for designing context assembly pipelines based on task type, window size, and latency budget
version: 1.0.0
phase: 11
lesson: 05
tags: [context-engineering, context-window, rag, memory, tool-selection, lost-in-the-middle]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="context-engineering"></a>

# Context Engineering

当建造一个 LLM 应用此框架设计上下文组装管道。

<a id="core-principles"></a>

## 核心原则

1. **环境很少。** 128K 窗口听起来很大, 但填充速度很快。 每个组件的预算都明确。
2. **Attention 并不平衡** 模型在开始和结束时要多注意。 输入关键信息。 中间是死区 。
3. **动态跳过静态。** 不同的查询需要不同的上下文。 组合每个查询, 而不是在启动时一次 。
4. **少就少了点** 缩放的 10K 上下文优于倾弃的 100K 上下文。 信号对噪音比比信息总量重要得多 。
5. **测量一切。** 您无法优化您不测量的东西。 计数 tokens 每个请求的每个构成部分。

<a id="context-budget-guidelines"></a>

## 背景预算准则

| 组件 | 典型范围 | Priority | 压缩战略 |
|-----------|-------------|----------|---------------------|
| System prompt | 200-1,000 tokens | 固定,高 | 仔细写, 删除冗余 |
| 工具定义 | 500-3,000 tokens | 动态, 介质 | 以查询意向冲淡 |
| 检索上下文 | 1,000-5,000 tokens | 动态, 高 | 重新排序 + 阈值 + 非重复 |
| 对话历史 | 500-5,000 tokens | 动态, 介质 | 总结旧的转弯 |
| Few-shot 示例 | 500-2,000 tokens | 动态, 高 | 根据任务相似性选择 |
| 用户查询 | 50-500 tokens | 固定,最高 | 不适用 |
| 生产储备 | 2,000-8,000 tokens | Fixed | 按预期产出长度调整 |

<a id="when-to-use-each-memory-type"></a>

## 何时使用每个内存类型

**短期(对话历史):** 当前会话 。 由摘要管理 。 压缩旋转时间大于 5 - 10 个交换点 。 保持最后 3 - 4 个旋转 。

**长期( 事实数据库) :** 首选项和工程事实, 始终存在各个会话。 开始获取会话。 例如 : “ 用户喜欢 Python"项目使用PostgreSQL","团队跟踪基于干线的开发"。 CLAUDE. md, 数据库, 或结构化的内存系统。

**Episodic( 以往的交互作用) :** 与当前任务相关的以往具体对话。 embeddings“上个星期我们调试了类似的授标问题”是偶发记忆。

<a id="tool-selection-strategy"></a>

## 工具选择战略

不在每次请求中包含全部工具。 此废件 tokens 并混淆了模型。

1. 分类查询意图(代码、电子邮件、日历、研究、数据)
2. 用于工具类别的地图意图
3. 只包含匹配工具
4. 如果意图不明确,请列入前两类的工具
5. 总是包含一个“ 常规” 工具( 如 Web 搜索) 作为备份

预期节余:工具定义的60-80% tokens 明确意图的询问。

<a id="retrieval-best-practices"></a>

## 回收最佳做法

- **检索后重新排序。** 矢量相似性是一个粗略的过滤器。 A reranker (跨类-)encoder 或 LLM- 基于)使精确度大大提高。
- **设定关联性阈值 。** 不包含0.3以下的块 cosine similarity他们会增加噪音
- **重复的 重复 重复 重复 重复 重复 重复 重复** 如果两块共享 80 %+ 内容, 只保留高分数之一 。
- **执行中途失落的命令** 将最相关的块先放在最后。
- **限制总检索量 tokens.** 3-5个高度相关的块 击败了15个平庸的块

<a id="history-management"></a>

## 历史管理

- 将最后的3-4 个旋转逐字( 模型需要最近的上下文)
- 总结旧的变成一个摘要 (“我们讨论过X,决定Y,并封锁在Z”)
- 丢弃系统生成的不添加信息的旋转( 工具引用, 没有用户端内容)
- 当历史超过可用预算的30%时触发压缩

<a id="red-flags"></a>

## 红旗

- System prompt 超过2 000 tokens:可能包括应该动态的信息
- 每项请求都包含所有工具:执行基于意图的选择
- 检索时没有相关过滤: 您正在向窗口倾弃噪音
- 历史日益不受约束:没有实施总结
- 没有代际储备:模型截断其响应
- 3个地点的信息相同(system prompt,检索到文件,历史:
- 超过60%的背景利用率:你给模型留下的空间太小,无法“思考”
