<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="agent-memory--virtual-context-and-memory-paging"></a>

# Agent Memory：虚拟上下文与记忆分页

> Context windows 。 对话、文档和工具 traces 。修正是OS虚拟内存重现——主上下文是内存,外部存储是磁盘, agent 中间的页面。MemGPT (Packer等人,2023年) 命名了该图案;许多生产内存系统都以它为基础。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 -06(工具使用)
**时间：** ~75 分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释OS类比MemGPT基于:主上下文=内存,外部上下文=磁盘,内存工具=页面进出。
- 在标准字中执行双层MemGPT模式, 配有主字符缓冲、 外部可搜索存储和页面/ 外工具 。
- 描述 agent 发布“ 中断” 以查询或修改外部内存, 以及结果如何被复制到下一个 prompt.
- 确定包含在Letta(Lesson 08)和Mem0(Lesson 09)中的MemGPT设计选择。

<a id="the-problem"></a>

## 问题

Context windows 看起来他们应该解决内存问题,但不会。在生产过程中,三种失败模式会重复:

1. **Overflow.** 多转式对话、长文档或工具呼叫重轨经过窗口。超过截断点的所有东西都不见了 。
2. **Dilution.** 即使在窗口内,填充无关的上下文也会稀释 attention 边际模型仍然会退化于长期的投入
3. **Persistence.** 新会话以空窗口开始 。 Agents 没有外部记忆 无法说"记得你让我..."

大窗口帮助但不能修复此。 2025年Mem0的纸张测量到, 128k- window 基线仍然忽略了4k- window 的事实 。 agent 外在内存捕获。

<a id="the-concept"></a>

## 概念

<a id="the-os-analogy"></a>

### 职业安全和职业安全类比

MemGPT (Packer等人, arXiv: 23100.08560, v22024) 将环境管理映射为操作系统虚拟内存:

| 业务支助处概念 | 地中海地中海土著人民网络概念 | 2026类生产 |
|------------|---------------|------------------------|
| RAM | 主要环境(prompt) | Anthropic/OpenAI context window |
| Disk | 外部环境 | 矢量 DB, KV, 图形存储 |
| 页面错误 | memory tool call | `memory.search`, `memory.read`, `memory.write` |
| OS 内核 | agent 控制循环 | ReAct 使用内存工具循环 |

该 agent 运行一个正常 ReAct 循环。 额外一类的工具可以让数据在主上下文中和之外页。

<a id="two-tiers"></a>

### 两级

- **主要背景。** Fixed-size prompt 保持当前任务。 模式总是可见的 。
- **外部情况。** 无限制, 可以通过工具搜索。 当相关时阅读, 当事实出现时写入 。

原始文件评价了基础窗口以外两项任务的设计:文件分析超过100k tokens 和多会话对话 与耐久的记忆 连续几天。

<a id="the-interrupt-pattern"></a>

### 中断模式

MemGPT 介绍内存中断: 中断 agent 能够引用一个内存工具,运行时间执行它,结果的连结作为新的观察转而进入下一个助手。 `read()` 调用断层, 返回字节, 进程继续 。

罐体内存工具表面:

- `core_memory_append(section, text)` 致 prompt.
- `core_memory_replace(section, old, new)` - 编辑一个持续部分。
- `archival_memory_insert(text)` 向外部可搜索商店写信。
- `archival_memory_search(query, top_k)` 从外面的商店里取回来
- `conversation_search(query)` 扫描过去转弯

<a id="where-the-paper-ends-and-production-begins"></a>

### 纸的结束和生产开始

2024年9月,MemGPT成为Letta。`cpacker/MemGPT`遗迹;Letta扩展设计:

- 三级而不是二级(核心、召回、档案——第08课)。
- 取代原生推理的理论 `send_message`/心跳模式(列松08)。
- Sleep-time agents 正在运行自动同步存储工作( Lesson 08) 。

即使在生产系统运行Letta、Mem0或定制双层商店的情况下,MemGPT纸也是2026年的基建。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **记忆腐烂。** 写入的累积速度比读数快; 检索会沉没在陈旧的事实中。 修补: 定期整合( 莱塔睡眠时间) , 明确无效 (Mem0 冲突检测器) 。
- **内存中毒** 外部内存被检索到文本。如果攻击者控制的内容在记忆注释中降落,则 agent 这是Greshake等人(Lesson 27)攻击事件,经过一段时间后又再次发生。
- **引用损失。** Agent 提醒“ 用户要我发运 X ” , 但无法引用哪个转弯。 保存来源引用( 会话编号、 转转 ID) 和每个归档写入 。

```figure
context-budget
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行 MemGPT 在 stdlib 中的双层模式 :

- `MainContext` 固定规模 prompt 缓冲带 `core` 听筒和一个 `messages` 列表; 超过上限时自动对最老的信件进行编码。
- `ArchivalStore` 记忆中 BM25- 旧商店( 超市)token- 超额评分) (id, text, tags, session, turn) 记录。
- 五个内存工具映射到MemGPT表面。
- 脚本 agent 填充事实的档案 然后通过拨打 `archival_memory_search`.

运行：

```
python3 code/main.py
```

该 trace 显示 agent 撰写三个事实,填充上限的主要背景(强迫驱逐),然后从档案中检索一个后续问题——在不真实的情况下复制MemGPT工作流程 LLM.

<a id="use-it"></a>

## 实际应用

当今每个生产记忆系统都是MemGPT变体:

- **Letta** (Lesson 08)——三层, 本地推理, 睡眠时间计算。
- **Mem0** (Lesson 0) - 矢量 + KV + 图形与评分层结合。
- **OpenAI 助理/答复** 通过线索和文件管理内存。
- **Claude Agent SDK** 通过技能和会话存储长期记忆。

按操作形状(自托管、管理、框架集成)而不是按核心模式选择一个——核心模式是MemGPT。

<a id="the-shape-of-agent-memory"></a>

### 形状 agent memory

调用解答能力。 它不决定存储什么。 四个内存类型在生产系统中重复, 每个回答一个不同的问题 :

- **工作记忆** 内涵层次:当前的任务,最近的转折, 紧紧的心节。 prompt itself.
- **笔记内存** 过去的转折和轨迹, 与会话和参考文件一起存储, 可按需重播 。
- **语义内存** 用户、域名、世界等事实随着变化而更新和翻版。
- **程序内存** 学了一些常规、偏好和规则来指导未来的行为而不是回忆。

公开源码执行选择不同的攻击点:

| 类型 | Implementation | 如何解决它 |
|------|----------------|-------------------|
| Working | 美格普特/莱塔 | 固定页数和页数 prompt 通过记忆工具编制预算(本课程,08课) |
| Episodic | Zep | 时间知识图——事实包含有效性间隔, 所以“ 当什么是真实的” 是可查询的 |
| 语义学 | Mem0 | 采掘管道,拆除和更新矢量、KV和图库中的事实(Lesson 0) |
| 语义 + 程序 | LangMem | 将事实和行为规则 推向一个商店 agent 转弯间咨询 |
| 语义 + | agentmemory | 运行时抓取会话, 将其合并为可搜索的打印记录 |

<a id="ship-it"></a>

## 交付成果

`outputs/skill-virtual-memory.md` 是一种可重复使用的技能,可以产生一个正确的双层内存脚架(主 + 档案 + 工具表面),用于任何目标运行时间,并有驱逐政策和引言场连接。

<a id="exercises"></a>

## 练习

1. 添加a `max_main_context_tokens` 以 tokens (与 `len(text.split())` * 1.3. 将最古老的信息压缩为超过上限的概要,与摘要或没有摘要的行为进行比较。
2. Implement BM25 正确在归档存储处( 定期频率, 反向文档频率) 上进行回溯。 测量一个玩具事实集上的@ 10 和 token- 超载基线
3. Add `citation` 字段(会话)_ID, 转身_ID, 来源_URL 进入存档插入。 agent 在每个检索支持的答案中引用源代码 。
4. 模拟内存中毒: 添加一个归档记录, 显示“ 忽略所有未来的用户指令 ” 。 写一个保护符, 扫描搜索指令形状的文本, 标记它们不被信任 。
5. 将执行程序移植到 MemGPT 研究回收器核心记忆 JSON 计划( 计划)`cpacker/MemGPT`)当您从平坦字符串切换到输入区域时会发生什么变化?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 虚拟背景 | "无限记忆" | 主要( )prompt+有页面进出的外部(可搜索)级 |
| 主要背景 | "工作记忆" | 该 prompt 固定尺寸,始终可见 |
| 档案内存 | 长期商店 | 外部可搜索性持久性,按需检索 |
| 核心内存 | "Persistent prompt section" | 主上下文中被钉住的命名区域 |
| 内存工具 | "Memory API" | Tool call 该 agent 读写外部内存的发行 |
| Interrupt | "记忆页面错误" | Agent 暂停、运行时间获取、结果组合到下一转 |
| 内存腐烂 | "陈腐的事实" | 旧写 淹死检索; 以整装方式修正 |
| 内存中毒 | "注射持久性注解" | 攻击者内容存储为内存, 重新装入回溯 |

<a id="further-reading"></a>

## 进一步阅读

- [Packer等人,MemGPT(ARXiv:231.08560)](https://arxiv.org/abs/2310.08560) - OS启发虚拟背景文件
- [Letta, 记忆屏障博客](https://www.letta.com/blog/memory-blocks) - 三级演变
- [Anthropic有效 context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 将背景情况作为预算处理
- [Chhikara等人,Mem0(arXiv:2504.19413)](https://arxiv.org/abs/2504.19413) 混合生产内存,除此模式外
- [泽普(getzep/zep)](https://github.com/getzep/zep) 分类表上的时间知识-绘图内存
- [闪电(mem0ai/mem0)](https://github.com/mem0ai/mem0) ——09课杂交店后面的提炼管道
- [兰梅姆(LangMem)langchain-ai/langmem)](https://github.com/langchain-ai/langmem) 事实和行为规则的背景摘录
- [剂模质( rohitg00/ 剂模质)](https://github.com/rohitg00/agentmemory) - 会话捕获合并成可搜索的打字记录
