<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="prompt-caching-and-semantic-caching-economics"></a>

# Prompt 缓存与语义缓存的经济性

> **2026-04年的定价快照** 下文的数字索赔反映了该课程的出版时所捕捉的供应商费率卡;在下游引用之前,先对照相关的文件加以核实。

> 缓冲发生于两个层次。 L2( 提供者级别) prompt/prefix caching reuses attention 重复的前缀的 KV - Anthropic的 prompt- 公布高达90%的成本削减和85%的延迟时间长期减少的广告 prompts; 用于 Claude 3.5 索纳特缓冲剂读数为0.30美元/M对3.00美元/M新鲜,5分钟TTL和2x1小时TTL选项(剂量)的写价。anthropiccom, 2026-04. 收到 2026-04. OpenAI prompt 自动缓存应用 prompts ≥1024 tokens 价格和缓存输入 大约90%的折扣与新鲜(平台)openaicom, 2026-04; 准确的每个模型缓存率取决于活费率卡。 L1 (应用级别) 语义缓冲跳过 LLM 完全开着 embedding 相似点。 供应商“ 95% 准确度” 是指正确性,而不是点击率 — 报告的产量点击率从10%( 开放式聊天) 到70%( 结构化的 FAQ ) ; 供应商都没有公布官方基线, 所以不将其作为社区遥测而非保证。 生产陷阱: 平行化会杀死缓冲( 在第一个缓存写之前发布的平行请求会增加数倍) , 以及前缀内动态内容会完全防止缓存点击 。 发现项目报告,通过将动态文字移出可缓存的前缀,其点击率从7% 上升到74% (2025-11)。

**类型:** 学习
**语言:** Python (stdlib,玩具双层缓存模拟器)
**先修要求:** 阶段17 -04(内部维修发动机),阶段17 -06(SGLang RadixAttention)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 区别L2 prompt/prefix caching (在供应商重复使用KV)来自L1语义缓冲(LLM 类似绕行 prompts).
- Explain Anthropic的 `cache_control` 明确标记和两个TTL选项(5-min 相对于 1小时)及其价格乘数。
- 计算每月预计节省的金额,以创用率计, prompt/反应组合,以及 token prices.
- 列出平行的反模式, 将账单膨胀5 -10x 和动态的反模式 崩溃率。

<a id="the-problem"></a>

## 问题

您添加 prompt 紧紧地抱着你 RAG 服务。 账单保持平坦。 您测量了点击率, 达到7% 。 prompts 看上去是静态的,但其实不是 system prompt 包括当前格式化为分钟的日期、请求代号、随机排序多样性示例。每个请求都写下一个新的缓存条目,读作零。

分开,你的 agent 运行十个平行 tool calls 用户问题。 所有 10 个都到提供者处, 然后再写完第一个缓存。 10 个写, 零个读取 。 您的帐单是 5 - 10x " 缓存" 应该要花费多少 。

缓存是一个协议, 不是旗帜。 两层, 两个不同的失败模式 。

<a id="the-concept"></a>

## 概念

<a id="l2--provider-promptprefix-caching"></a>

### L2——供应商 prompt/prefix caching

供应商储存 attention KV 用于可缓存的前缀, 并在下一个符合前缀的请求中重新使用。 您支付一次写入成本, 几乎可以免费阅读 。

**Anthropic (Claude 3.5 / 3.7 /4 号编)**:明确 `cache_control` 标记请求中的标记。 您标记哪些块可以缓存 。 TTL: 5分钟( 写成本 1. 25x 基数) 或 1小时( 写成本 2x 基数) 。 缓存读取 : 0. 30/ M Claude 3.5 索内特对3.00美元/百万新元——10美元便宜(医生:anthropiccom,截至2026-04年,每种价格的费率不同(Opus/Haiku单独出版);总是交叉核对现场定价页面。

**OpenAI**: 自动缓存 prompts ≥1024 tokens (platform.openaicom, 2026-04. 无明确的旗帜。 缓存输入比当前新输入的便宜约10x gpt-4o/gpt- 5 速率卡。文件或发布说明都没有公布官方的命中率基准;社区报告以谨慎的方式将30-60%左右汇总 prompt 设计。 `usage.cached_tokens` 来测量你自己的

**谷歌( 谷歌)Gemini)**:通过明确缓存上下文 API; 1米 -token 上下文意味着缓冲支付更多。

**自办(vLLM, SGLang)**:第17阶段 : 06涵盖RadixAttention——用你自己的计算方式来计算。

<a id="l1--app-level-semantic-caching"></a>

### L1 - 应用程序级语义缓冲

之前打电话 LLM 完全没有,哈希 prompt,并查找类似的缓存请求(cosine similarity 超过阈值,通常为0.95+) 被击中时,返回缓存响应。 LLM 并隐藏结果。

公开来源:Redis矢量相似性, GPTCache, Qdrant。 商业: 端口缓存, Helicone缓存 。

供应商准确性索赔是指退回的缓冲反应在语义上是否适当,而不是你击中的次数。

- 开放式聊天:10-15%。
- 结构化的常见问题/支助:40-70%。
- 代码问题: 20%-30%(小变体会击败点击)。
- Voice agents repeating prompts:50-80%(声音) normalization 固定的)

<a id="the-parallelization-anti-pattern"></a>

### 平行反模式

你的 agent 10个 tool calls 平行的,10个都一样token system prompt. Anthropic 缓存写法是每个请求; 提供者看到后, 第一个缓存-  write 完成大约 300 毫秒 prompt。2-10请求到达同一个毫秒窗口,每个窗口都看到缓存误差。您支付10笔写溢价,0份读取折扣。

固定: 批次顺序第一—— 单发请求 1, 然后在 1 的缓存已有人居住时开火 2 - 10。 向第一个 添加 300 毫秒 tool call; 省下5-10的帐单。

<a id="the-dynamic-content-anti-pattern"></a>

### 动态内容反模式

你的 system prompt 看起来像:

```
You are a helpful assistant. The current time is 14:32:17.
User ID: abc123. Today is Tuesday...
```

每一个请求都是独一无二的 每个请求都写了 零点击

修正: 将所有真正静态的移动到可缓存的前缀; 在缓存边界之后附加动态内容 :

```
[cacheable]
You are a helpful assistant. [rules, examples, instructions]
[/cacheable]
[dynamic, not cached]
Current time: 14:32:17. User: abc123.
```

发现项目从7% 移动到74%的缓存点击率 这样,公布解剖。

<a id="stack-batch--cache-for-overnight-workloads"></a>

### 堆放批次+过夜工作量的缓存

Batch APIs 17 = 15) 24小时周转时给予50%的折扣。 顶部的缓存输入会增加~ 10x。 隔夜分类、 标签和报告生成工作量可以通过堆叠方式下降到~ 10%的同步- 无焦的成本 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

定价点从相关的供应商文件上记录2026-04,每几个月一次——在依赖它们之前再进行检查。

- Anthropic 已缓存读取: 0.30美元/米 Claude 3.5 索纳特,比新鲜投入约便宜10倍(医生:anthropic.com).
- Anthropic 缓存写入溢价: 1. 25x( 5- min TTL) 或 2x ( 1- 小时 TTL) 。
- OpenAI 自动缓存: 应用到 prompts ≥1024 tokens; 缓存输入价格约为当前速率卡(平台)新输入的10%。openai.com).
- Semantic cache 点击率(社区报告):~10%打开聊天;高达~70%的结构化常见问题。不是供应商记录的基线。
- 发现项目:7% +74% 被击中率,通过移动前缀的动态(项目博客,2025-11)。
- 平行反模式: 典型的报告显示, N 平行请求错过首封缓存文件时, 5 - 10x帐单通胀率。

```figure
semantic-cache-hit
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟 L1 + L2 的杂交工作量,报告点击率、账单和显示平行处罚。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-cache-auditor.md`。给定 prompt 模板和流量,审计可隐藏性,并建议进行重组。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。切换平行标志。法案更改了多少?
2. 你的 system prompt 有个约会, 移动出去。 在计算出点击率之前/之后显示 。
3. 计算 1小时 TTL (2x write) 的折中时间, 与 5 分钟 TTL (1. 25x write) 的折中时间, 以您申请到达的速度 。
4. Semantic cache 0.95 下限为 20%。 0.85 下限为 50%, 但您看到错误的缓存响应。 选择正确的阈值并解释 。
5. 每个用户问题都分批十次平行查询。 重写方便缓存而不添加端到端的延迟度 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| L2 prompt cache | "前缀缓存" | 重复前缀的 KV 供应商 |
| `cache_control` | "Anthropic 缓存标记" | 明确属性标记可缓存区块 |
| 缓存写入溢价 | 写字税 | 第一次误差额外费用(1.25x或2x) |
| L1 semantic cache | "embedding cache" | 调用前先装配散列和组装 LLM |
| GPTCache | “LLM 缓存库” | 普通的 OSS L1 缓存库 |
| 缓存点击率 | "打/总" | 从缓存中发送的请求的分数 |
| 平行反模式 | "N -write陷阱" (N -wride陷阱) | 平行请求丢失缓存次数 |
| 动态内容陷阱 | 时间到prompt trap" | 以前缀为首的动态字节 |
| RadixAttention | "复制缓存" | SGLang执行前缀缓存 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) - 公务人员 `cache_control` 语义和TTLs。
- [OpenAI Prompt Caching](https://platform.openai.com/docs/guides/prompt-caching) 自动缓冲行为和资格
- [天潘语语语语语语语语语语 LLMs Production](https://tianpan.co/blog/2026-04-10-semantic-caching-llm-production)
- [项目发现——切换 LLM 费用59% Prompt Caching](https://projectdiscovery.io/blog/how-we-cut-llm-cost-with-prompt-caching)
- [数字海洋 / Anthropic — Prompt Caching](https://www.digitalocean.com/blog/prompt-caching-with-digital-ocean)
