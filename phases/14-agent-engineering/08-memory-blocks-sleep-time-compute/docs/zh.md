<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="memory-blocks-and-sleep-time-compute"></a>

# 记忆块与休眠时计算

> 分解功能内存块, 模型可以直接编辑, 并且睡眠时间 agent 以不同步的方式整合记忆 agent 空闲。这两个想法是,如何将记忆比一个对话更深。

**类型:** Build
**语言:** Python (stdlib)
**先修要求:** 阶段14 -07(MEMGPT)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出Letta使用的三种记忆层(核心、回溯、存档)和每个存储层的作用。
- 解释内存区块模式: 人类区块、 人块和用户定义的区块作为头等键。
- 描述睡眠时间计算,为什么它不走关键的道路, 为什么它可以运行一个比主菜更强大的模型 agent.
- 执行脚本二agent loop 初级 agent 服务于反应和睡眠时间 agent 将两个回合之间的块块合并。

<a id="the-problem"></a>

## 问题

MemGPT (Lesson 07) 解决了虚拟模拟控制流程。 出现了三个生产问题 :

1. **Latency.** 每个记忆操作都位于关键路径。如果 agent 用户要等待时, 必须进行精密、 总结或对齐 。 tail latency 爆炸了,我们得去
2. **记忆腐烂。** 书写累积, 事实相反, 检索会沉没在陈旧的内容中。
3. **结构损失。** 平板档案店无法表达"人类街区总是在 prompt; 人际关系区块总是在 prompt;任务区块的交换每会话。”

Letta( letta. com) 是2024年通过的最初MemGPT项目平台名称—— 纸张的图案保留了MemGPT的名称, 而2026年Letta V1 重写是一个后继、 单独的步骤。 内存块使结构清晰; 睡眠时间计算移动合并到关键路径上 。

<a id="the-concept"></a>

## 概念

<a id="three-tiers"></a>

### 三个层次

| Tier | Scope | 住在哪里吗? | 编写者 |
|------|-------|----------------|------------|
| Core | 总是可见 | 内侧 prompt | Agent tool call + 睡眠时间重写 |
| 召回 | 对话历史 | Retrievable | 自动转转记录 |
| Archival | 任意事实 | 矢量 + KV + 图 | Agent tool call +睡眠时间摄入量 |

核心是 MemGPT 核心。 回想是与其被拆卸的尾巴对话的缓冲。 档案是外部商店。 分割会清理MemGPT 的双层超载 。

<a id="memory-blocks"></a>

### 内存块

块是指核心层中一个打印、持续和可编辑的部分。 MemGPT 原始纸张定义了两个:

- **人类块** 用户的事实(名称、作用、偏好、目标)。
- **人际区块** — 该 agent自我概念(身份、语气、限制)。

常规化为任意自定义的区块: a `Task` 当前目标的块, a `Project` 代码基础事实块 a `Safety` 硬性限制的区块。 `id`, `label`, `value`, `limit` (字符上限), `description` (因此模型知道何时编辑它)

块可通过工具表面编辑 :

- `block_append(label, text)`
- `block_replace(label, old, new)`
- `block_read(label)`
- `block_summarize(label)` - 凝结一个接近极限的街区

<a id="sleep-time-compute"></a>

### 睡眠时间计算

2025年Letta加法:运行一秒钟 agent 以背景为主,远离关键路径。 agents 处理对话记录和代码库上下文,写入 `learned_context` 合并或废止档案记录

掉出属性 :

- **不需要潜伏费** 主要反应不等待记忆行动。
- **更强的模型允许。** 睡觉时间 agent 它可以是一个更昂贵, 慢模式 因为它不是 延缓。
- **自然整合窗口。** 用户不等待,Dedup、General、无效的事实。

形状与人类的工作方式相符: 你做这个任务,你睡在它上, 长期记忆一夜之间就解决了。

<a id="native-reasoning"></a>

### 原生推理

莱塔V1 (`letta_v1_agent`2026年 折旧 `send_message`心跳和内线 `Thought:` tokens 支持本地推理。 API (OpenAI和消息 API 并有深入的思维(第2条),Anthropic) 发布对一个单独的频道的推理,通过转弯(在生产过程中被跨供应商加密)。 ReAct。想法 trace 结构,不是 prompt-shaped.

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **块状的浮肿** Infinite `block_append` 快速点击限制。 在写作前用一个块摘要器连接, 将它推向顶部 。
- **安静的漂移。** Sleep-time agent 重写块块和主 agent 从未注意到。 版本块和表面 diffs in the trace.
- **中毒的整合。** Sleep-time agent 将攻击者接触的内容处理成核心。课程27也适用于睡眠表面。

```figure
memory-blocks
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `Block` - id, 标签, 值, 限制, 描述 。
- `BlockStore` - 体积+ `near_limit(label)` helper.
- 两个脚本 agents — `PrimaryAgent` 转弯 `SleepTimeAgent` 旋转间合并。
- 一个 trace 加上一张睡眠时间通行证 总结了一块块 否定了一个破碎的事实

运行：

```
python3 code/main.py
```

记录显示分裂:主转弯速度很快,生写;睡眠压紧,打扫干净。

<a id="use-it"></a>

## 实际应用

- **Letta** 用于参考执行。 自我主机或管理云层 。
- **Claude Agent SDK skills** 是一个名为、已版本、可检索的指令块 agent 随叫随到
- **自定义构建** 用于想要控制存储后端的团队。 请使用 Letta API 合同,以便您日后可以迁移。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-memory-blocks.md` 产生一个Letta形的块状系统,在任何运行时都带有睡眠时间钩,包括安全规则和引力线。

<a id="exercises"></a>

## 练习

1. 添加a `block_summarize` 工具,当 `near_limit` 返回真实。哪个触发阈值会最小化汇总电话和块溢出 ?
2. 实施睡眠时间脱口而入的档案:两个记录,其文本 > 90% token 将折叠重叠为一。 只在睡眠通行证中做, 永远不要在关键路径上做 。
3. 版本块。 在每一个写入记录中, 都含有旧值和 diff 。 Explosion `block_history(label)` 操作员可以调试“为什么 agent 忘记X。"
4. 治疗睡眠时间 agents 被当成不可靠的作家 当他们碰上人或安全区时agent 承诺前先审查。
5. 将示例移植到 Letta API (`letta_v1_agent`))块图案的哪些变化,以及本地推理如何改变 trace shape?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 内存块 | "Editable prompt section" | 输入, 耐久, LLM- 核心内存的可编辑部分 |
| 人类块 | "用户内存" | 用户的真相, 被钉在核心 |
| 人际区块 | "Agent identity" | 自我定位、语气和约束，固定保存在核心记忆中 |
| 睡眠时间计算 | "同步记忆工作" | Second agent 正在整合关键路径 |
| 核心/回顾/档案 | "Tiers" | 三层内存分割: 总是可见/ 对话/ 外部 |
| 块限制 | "Cap" | 每个区块的字符限制; 强制总和 |
| 原生推理 | 思考频道 | 供应商级推理输出,非 prompt-level `Thought:` |
| 学习背景 | "睡眠输出" | 睡眠时间的事实 agent 写入共享区块 |

<a id="further-reading"></a>

## 进一步阅读

- [Letta, 记忆屏障博客](https://www.letta.com/blog/memory-blocks) 块图案
- [Letta, 睡眠时间计算博客](https://www.letta.com/blog/sleep-time-compute) 合并合并
- [丽塔,重新组织 Agent Loop](https://www.letta.com/blog/letta-v1-agent) - 本地推理重写
- [Packer等人,MemGPT(ARXiv:231.08560)](https://arxiv.org/abs/2310.08560) 来源
