<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="prefix-cache-serving--radixattention-and-kv-reuse"></a>

# 前缀缓存服务：RadixAttention 与 KV 复用

> 处理 KV cache 作为一种头等、可重复使用的资源,存储在一棵射线树上,并与之一起进行时间安排修改:而不是FCFS(先到先得) vLLM 计划,一个缓存记录器优先处理请求,并使用较长的共享前缀——实际上是深度第一线的穿梭式 branches 留在HBM住。 SGLang 是一个围绕这个想法的引擎。 Llama 3.1 8B 与shareGPT类似 1K prompts, SGLang 点击~16 200 吨/秒 vLLM~12 500, 边缘~ 29%。 在前缀重度 RAG 使用语音钩工作量,缓冲率86%清除。 GPUs 2026年横跨 xAI, LinkedIn, Cursor, Oracle, GCP, Azure, AWS。 错误是,6.4x的编号在前缀顺序不一致时会蒸发—— 订单是工程师的杠杆。

**类型:** 学习
**语言:** Python (stdlib, 玩具 radex- trree 缓存 + 缓存记录器)
**先修要求:** 阶段17 -04(内部维修发动机),阶段14(Agentic RAG)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 图解 RadixAttention: 如何将前缀存储在 radex 树上, 以及如何在根植于同一序列的 KV 区块共享 branch.
- 解释缓存意识调度以及FCFS为什么对前缀重流量错误 。
- 计算工作量的预期速度,给前缀缓存点击率和 prompt 长度分布。
- 名称 prompt- 命令纪律,使6.4x数字 真实的和失去的反向。

<a id="the-problem"></a>

## 问题

古典服务 对待每一个请求 prompt 即使是当有5000个 RAG 要求全部从相同的2000 -token system prompt 加上相同的检索序言, vLLM prefills 那2000年的... . . .token 前缀 5000 次。 GPU 做同样的工作 一遍又一遍。

意见: prompts 在 agentic 和 RAG 工作量几乎总是有很长的前缀。 System prompt工具图案 few-shot 示例、 检索信头、 对话历史 - 在所有请求中重复。 如果您存储了 KV cache 之前的字条,你不会 prefill 再来一次

辐射力控制就是这么做的 Tokens 以 raidx 树为索引;每个节点拥有用于 token 树上行走的新请求: 任何节点 token 匹配点的KV区块的重新使用。 Prefill 成本与“ 新” 后缀成正比, 而不是全部 prompt.

问题是日程安排 如果两个请求是2千token 前缀和第三股仅200 tokens 在同一前缀中,您想要一起满足两个长期共享的请求,这样长的前缀就留在 HBM 。 FCFS 却相反,它为先到者服务,有可能驱逐热门 branch 在下一个长前缀请求点击之前 。

<a id="the-concept"></a>

## 概念

<a id="the-radix-tree-as-a-kv-index"></a>

### 以 KV 指数为例的 radex 树

一条射线树(分三)仓库 token 序列。 每个节点都拥有 a token 区域,并计算出该范围的 KV 区块。 tokens.

```
root
 |- "You are a helpful assistant..."  (2,000 tokens, 124 KV blocks)
      |- "Context: <doc A>..."        (500 tokens, 31 blocks)
           |- "Question: Alice..."    (80 tokens, 5 blocks)
           |- "Question: Bob..."      (95 tokens, 6 blocks)
      |- "Context: <doc B>..."        (520 tokens, 33 blocks)
```

新的申请 system prompt + "内容: <doc A>" + " 问题:Carol " 。排程器走动:系统前缀匹配(124个区块已重新使用), doc-A branch 匹配(31个区块已重新使用),然后只为“问题:卡罗尔”(4个区块)分配新区块。 Prefill 费用:4个新区块 tokens。没有树:160个街区。~40x prefill.

<a id="cache-aware-scheduling"></a>

### 缓存意识排程

如果缓存杂交, 以 Radix 树背为后盾的再利用是毫无意义的。 有两个关键策略 :

1. **深度 - 第一次发送**。在从队列中选择下一个请求时,更喜欢同一方向 branch 以当前运行设置。 这样可以保持热 branch pinned.
2. **卢俄在 branch 级别, 不是区块级别**整个 Evict branches 而不是单个的区块 所以缓存形状和射线形匹配

联邦粮安委违反了这两条 一份共享2千份的申请 tokens 坐在一份50分钱申请的后面 然后是2000分钱token branch 被赶出去承认50岁token one.

<a id="benchmark-numbers-you-should-memorize"></a>

### 基准数 您应该记住

- Llama 3.1 8B, H100, ShareGPT 1K 等号 prompts: SGLang ~16,200吨对 vLLM ~12,500(~29%边缘)。
- Prefix-heavy RAG (同一系统+同一医生,不同的问题):最多6.4x SGLang.
- 语音克隆工作量:86.4%的前缀卡塞点击率。
- 整个生产点点擊率 SGLang 客户:50-99%取决于 prompt discipline.
- 部署于40万+ GPUs 2026年 开始

<a id="the-ordering-gotcha"></a>

### 订货被查住了

6.4x 数字依赖于一致 prompt- 板块订购。 如果您的客户端构建 prompts 作为 `[system, tools, context, history, question]` 某些请求和 `[system, context, tools, history, question]` 在其它情况下,树找不到共享的前缀。 人类的共享前缀是 射线树的两个不同的序列。

工程师的杠杆: prompt 模板是一个缓存密钥。 固定顺序。 先将所有不可更改的( 系统、 工具、 系统) 放在前面, 下放检索上下文。 将用户问题放在最后。 不要将动态内容插入前缀 。

研究中的真实案例:将动态内容从可缓存的前缀移动到74%的缓存点击率,但有一个变化。

<a id="where-radixattention-wins-and-loses"></a>

### 在那里,RadixAttention 获胜和失败

Wins:
- RAG (相同的检索序言,不同的问题)。
- Agents (相同的工具图,不同的查询)
- 长话短说 system prompt.
- 反复序言的语音/视觉工作量。

损失(返回至 vLLM- 水平输送量:
- 独角兽一代 prompts (代码完成, 开放式聊天, 不包含 system prompt).
- Dynamic prompts 每一个请求都将独特的内容插入前缀。

<a id="why-this-is-a-scheduler-problem-not-just-a-kernel-problem"></a>

### 为什么这是排队问题 不仅仅是内核问题

您可以将 KV 重新使用作为内核的把戏 。 SGLang洞察到,再利用只有在排程器保持热量时才有回报 branch 使用一种天真的“ 如果可用的话重复” 策略会将缓存在混合负荷下。 将内核的游戏变成 29%的生产边缘 。

<a id="interplay-with-vllm"></a>

### 与 vLLM

两种制度并不是严格的竞争对手。 vLLM added prefix caching (`--enable-prefix-caching`和缓存识别路由器(vLLM 路由器已输入 Rust差距已经弥合,但并未完全消失。 SGLang整个堆叠是先射线 vLLM 将它绑在上方。对于以前置再利用为主的工作量, SGLang 对于没有强力前缀模式的普通用途服务, vLLM 保持平等或更好。

```figure
roofline
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行玩具的射线树 KV cache 加上一个包含两个策略的排程器: FCFS 和缓存能力。 通过这两个选项运行相同的工作量, 报告前缀缓冲率和吞吐量 。 然后运行一个“ 递解订单” 的工作量以显示 6.4x 崩溃 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-radix-scheduler-advisor.md`工作量说明(A/AC.96/9,第1段)prompt- 模板形状,检索模式,同时租户的数量,它产生 prompt- 订药和开药 SGLang adoption.

<a id="exercises"></a>

## 练习

1. Run `code/main.py`比较FCFS和缓存能力,以完成同样的工作量。 prefill 节约、解码节约或排队延迟?
2. 将工作量修改为 prompts 随机剪切 `[system, tools, context]`重新运行,出什么问题了?
3. 计算HBM的存取成本token system prompt 常住居民为一线 branch 在 Llama 3.1.8B. 与未进行前缀再利用的16个序列批次的费用相比。
4. 读 SGLang 辐射轴值纸。 在三句话中解释为什么树形的LRU驱逐在前缀重载下比块状的LRU强。
5. 客户只报告8%的缓存点击率。 列出三种可能的原因和您要对每种原因进行的诊断 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| RadixAttention | "该 SGLang thing" | KV cache 以射线树索引, 共享前缀再利用区块 |
| 半径树 | "连胜三局" | 每个节点都拥有的树 token 区域及其 KV 区块 |
| 缓存提醒调度器 | "hot-branch-first" | 更喜欢分享居民的调度器 branch |
| 前缀缓存点击率 | “你的 prompt 中有多少部分无需重新计算” | 分数 prompt tokens 使用已再利用的 KV 区块 |
| FCFS | 来先到先得 | 打破前缀位置的默认调度 |
| Branch- 级别 LRU | "避免叶子" | 驱逐政策与射线形相匹配 |
| Prompt 模板顺序 | "缓存密钥" | 该 prompt组件顺序决定了树可以分享什么 |
| System prompt pinning | 常住前缀 | 保持固定的系统部分,以避免被驱逐 |

<a id="further-reading"></a>

## 进一步阅读

- [SGLang GitHub](https://github.com/sgl-project/sglang) - 来源和医生。
- [SGLang documentation](https://sgl-project.github.io/) - 辐射跟踪和时间安排细节。
- [SGLang 高效编程大语言模型(arXiv:2312.07104)](https://arxiv.org/abs/2312.07104) - 设计参考。
- [LMSYS 博客 SGLang 使用 radix 注意](https://www.lmsys.org/blog/2024-01-17-sglang/) 基准数和时间表理由。
- [vLLM — Prefix Caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/) — vLLM自己的射线类执行,比较。
