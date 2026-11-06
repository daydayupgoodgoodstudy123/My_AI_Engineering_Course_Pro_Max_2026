<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-08--production-rag-chatbot-for-a-regulated-vertical"></a>

# 综合项目 08：面向受监管行业的生产级 RAG 聊天机器人

> 哈维、葛莱恩、门可、拉玛克卢德在2026年都运行同样的生产形状。 使用文档或无结构的和ColPali用于视觉搜索。 混合搜索。 重新排序时使用 bge-reranker-V2Gemma 与 Claude 索纳特4.7使用 prompt 以60-80%的速率缓冲。 Llama 卫兵4和尼莫 Guardrails与兰福斯和凤凰队一起观看,与RAGAS队在200个问题金牌赛上比赛。 在受监管的领域(法律、临床、保险)建一个赛车场, 顶峰正在穿过金牌赛车场, 红队和漂流仪表板。

**类型:** Capstone
**语言:** Python (管道+ API), TypeScript (聊天界面)
**先修要求:** 第五阶段(无法律授权),第七阶段(transformers阶段11(LLM 工程,第12阶段(多式),第17阶段(基础设施),第18阶段(安全)
**实施阶段:** P5 ; P7 ; P11 ; P12 ; P17 ; P18
**时间:** 30小时

<a id="problem"></a>

## 问题

Regulated-domain RAG 2026年最先进的生产形式是,因为ROI显而易见,利害关系也非常具体。哈维(Alllen & Overy)为合法建造了它。可以修饰的船舶有开发者-医生的口味。Glean覆盖企业搜索。模式是: 最不忠, 回收混合的重新排位, 与引言执行相结合, 以及 prompt 捕捉,多层安全防护, 并监视不断漂移。

硬部分不是模式,它们是管辖权遵守(HIPAA、GDPR、SOC2)、引证一级的可审计性、成本控制(HIPAA、GDPR、SOC2)prompt 击中率高时,Caching购买60-90%的折扣) hallucination 使用RAGAS 的忠诚检测, 当源文件更新时没有赶上索引。 这个综合项目要求您将所有文件 放在200号金牌上, 并配有红色队套件。

<a id="concept"></a>

## 概念

管道有两面。 **Ingestion**: 编织或无结构的剖析文档结构; ColPali 处理视觉上丰富的文档; 块获得摘要、 标签和基于角色的访问标签。 矢量进入 pgvictor + pgvictor 比例( 低于 50M 矢量) 或 Qdrant Cloud; 稀疏 BM25 跟着跑 **Conversation**: LangGraph 处理内存和多转;每个查询运行 hybrid retrieval重排,带BGE -reranker-V2-地球- 2b, 与 Claude 索内特4.7 (prompt- 焦块,通过输出 Llama 卫兵4和尼莫 Guardrails,并发出一个引证 - 锁定的答复。

电子书架有四层 **黄金套** (200份标注为Q/A的引文)正确无误。 **红队** (jailbreaks安全性。 **RAGAS** /回答相关性/上下文精确度自动的每倾角。 **漂移仪表板** (阿瑞兹凤凰) 观看检索质量和 hallucination 每周得分。 得分。

Prompt 缓存是降低成本的关键。Claude 4.5+ 和 GPT-5+ 支持缓存 system prompts 与检索得到的上下文。命中率达到 60–80% 时，每次查询的成本可降至原来的 1/3–1/5。管道必须围绕稳定的前缀设计，将 system prompt 与重排后的上下文放在最前面，才能实现较高的缓存命中率。

<a id="architecture"></a>

## 建筑

```
documents (contracts, protocols, policies)
      |
      v
docling / Unstructured parse + ColPali for visuals
      |
      v
chunks + summaries + role-labels + jurisdiction tags
      |
      v
pgvector + pgvectorscale  +  BM25 (Tantivy)
      |
query + role + jurisdiction
      |
      v
LangGraph conversational agent
   +--- retrieve (hybrid)
   +--- filter by role + jurisdiction
   +--- rerank (bge-reranker-v2-gemma-2b or Voyage rerank-2)
   +--- synthesize (Claude Sonnet 4.7, prompt cached)
   +--- guard (Llama Guard 4 + NeMo Guardrails + Presidio output PII scrub)
   +--- cite + return
      |
      v
eval:
  RAGAS faithfulness / answer_relevance / context_precision (online)
  Langfuse annotation queue (sampled)
  Arize Phoenix drift (weekly)
  red team suite (pre-release)
```

<a id="stack"></a>

## 堆栈

- 摄入:结构化文档无结构化的.io或编译;视觉富集的PDF的ColPali
- 矢量 DB: 位数+ 位数,在 5 0M 矢量下; 方位云
- 粗略: 长相 BM25 与字段 weights
- Orchestration: LlamaIndex 工作流量(摄入)+ LangGraph (conversation)
- 重排顺序: bge-reranker-V2-gemma-2b 自行托管或Voyage 重新排序-2
- LLM: Claude 索内特4.7与 prompt 缓冲; 后退 Llama 3.3 70B自行主办
- Eval: RAGAS 0.2 在线,深爱华 hallucination 和 jailbreak suites
- Observability: 兰福斯自办,配有注解队列; 漂移为凤凰城
- Guardrails: Llama 警卫4 输入/产出分类, NeMo Guardrails 五. 0.12 政策,Presidio PII清洗
- 合规:块上基于角色的准入标签;GDPR/HIPAA的管辖标签

```figure
canary-rollout
```

<a id="build-it"></a>

## 动手实现

1. **Ingestion.** 分析您的文稿( 10000- 1000 份文件, 用于重度构建) 。 对于扫描/ 视觉重的页面, 可以通过 ColPali 路径。 生成含有摘要、 角色标签、 管辖区标记的块 。

2. **Index.** Dense embeddings (Voyage-3或Nomic-embied-v2) 改为 pgvector + pgvictor 标度。 BM25 角色和管辖权过滤器作为有效载荷

3. **混合回收。** 先用角色+司法管辖权过滤; 然后平行密度+ BM25; 合并为 reciprocal rank fusion; 上20个到 reranker; 上个 5 到 合成。

4. **合成大小 prompt caching.** System prompt + 缓存信头中的静态策略; 将上下文重新排序为缓存扩展名; 用户质疑为未剪切的后缀。 目标 60- 80% 缓存按下速度稳定 。

5. **Guardrails.** Llama 输入时守卫 4; NeMo Guardrails 铁路阻断外域问题或政策禁止的主题; 输出中Presidio清除意外的 PII; 引用后过滤器。

6. **黄金套装** 200对Q/A,由域专家标注(回答、引用)。 agent 准确的引用匹配,回答正确,忠诚。

7. **红队** 50 对抗性 prompts: jailbreaks 搜索和救援小组试图从外域、跨管辖区渗漏。

8. **漂浮仪表板** 凤凰城每周跟踪检索质量( nDCG, 引用忠诚度) 。 警告 5% 的下降 。

9. **成本报告。** Langfuse: prompt- 惊人的打击率, tokens 每个查询,美元/克格丽特细目,按阶段分列。

<a id="use-it"></a>

## 实际应用

```
$ chat --role=analyst --jurisdiction=GDPR
> what is the data-retention obligation for EU user profiles under our contract?
[retrieve]  hybrid top-20 filtered to GDPR + analyst-role
[rerank]    top-5 kept
[synth]     claude-sonnet-4.7, cache hit 74%, 0.8s
answer:
  The contract (Section 12.4, Master Services Agreement dated 2024-03-11)
  obligates EU user profile deletion within 30 days of termination per GDPR
  Article 17. The DPA amendment (DPA-v2.1, Section 5) extends this to 14 days
  for "restricted" category data.
  citations: [MSA-2024-03-11 s12.4, DPA-v2.1 s5]
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-production-rag.md` 显示交付品。 安装有合规标签的受监管的聊天室, 通过标注, 并用实时漂移监测观察 。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | RAGAS 忠诚+回答相关性 | 金牌系列的在线评分(200 Q/A) |
| 20 | 引用正确 | 含有可核查源锚的回答分数 |
| 20 | Guardrail coverage | Llama 警卫4人及格率+ jailbreak 套件结果 |
| 20 | 费用/潜伏工程 | Prompt- 破烂弹,p95 延迟,$/克雷 |
| 15 | 漂移监测仪表板 | 凤凰号直播仪表板,具有每周检索质量趋势 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 在不同的法域(例如,HIPAA和GDPR)下建立第二块体片。 显示作用+司法过滤防止交叉渗漏到一个20个问题跨司法探测器上。

2. Measure prompt- 一周的生产流量中,缓冲率被击中。 确定哪个查询会打破缓存的前缀。 重建 。

3. 添加多方向内存, 带有 10 k-token 简要缓冲。 测量是否随着对话的不断增长而忠诚度下降 。

4. Swap Claude 索纳特4.7为 Llama 3.3 70B自营,测量美元/克丽丝和忠诚三角洲。

5. 添加“ 不确定” 模式: 如果最高分排位低于阈值, 则 agent 说"我没有自信的引用"而不是回答。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Prompt caching | “ 生成系统+上下文” | Claude/OpenAI feature: 已缓存的前缀 tokens 被击中者折扣60-90% |
| 拉加斯 | "RAG evaluator" | 忠诚、回答相关性、上下文精确度的自动评分 |
| 黄金套 | "彩排的反射" | 200+ 标有专家标签的问答/A,附有引文;事实真相 |
| 管辖权标记 | “合规标签” | GDPR/HIPAA/SOC2 范围附于块上;通过检索过滤器实施 |
| 引用的忠诚 | 答案率四舍五入 | 附有可检索源范围的索赔件数 |
| Drift | "检索质量衰变" | 每周更改NDCG或引用分数;警戒门槛5% |
| 红队 | 反向评估 | Pre-release jailbreak外外探测器 |

<a id="further-reading"></a>

## 进一步阅读

- [哈维・艾尔](https://www.harvey.ai) 参考合法生产堆
- [古兰企业搜索](https://www.glean.com) 参考 RAG 企业规模
- [可修正文档](https://mendable.ai) 开发者-医生 RAG reference
- [LlamaCloud 分析 + 索引](https://docs.cloud.llamaindex.ai/llamaparse/getting_started) 管理下的摄入
- [Anthropic prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) 成本- 从未提及
- [RAGAS 0.2 文档](https://docs.ragas.io/) - RAG 电子估价框架
- [亚里兹·凤凰城](https://github.com/Arize-ai/phoenix) 参考漂移 observability
- [Llama 警卫4](https://www.llama.com/docs/model-cards-and-prompt-formats/llama-guard-4/) - 2026年安全分类
- [NeMo Guardrails v0.12](https://docs.nvidia.com/nemo-guardrails/) 政策铁路框架
