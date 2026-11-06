<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="hybrid-memory-vector--graph--kv"></a>

# 混合记忆：向量、图与 KV

> 混合内存平行运行三个仓库——语义相似矢量,快速查寻KV,实体关系推理图——在检索时将其连接起来的评分层。 这是一个广泛使用的外部内存生产模式;Mem0(Chikara等人,2025年)是一个参考实施。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 -07(MemGPT),阶段14 -08(莱塔区块)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么单家商店(仅向量,仅图,仅KV)不够用 agent memory.
- 命名Mem0的三家平行商店 以及每个商店的优化。
- 描述Mem0的聚合分数——相关性、重要性、耐性——以及为什么它是加权总和而不是等级。
- 在标准里卜用一个 `add()` 写给所有三个和一个 `search()` 保险丝的结果。

<a id="the-problem"></a>

## 问题

三个查询类中的一个是错的 :

- **语义相似性** -"我们讨论过什么 agent 上星期漂移?" 矢量赢; KV 和图误差。
- **调查事实** ─“用户的电话号码是多少?” KV赢;矢量是浪费的,图是过度杀戮。
- **关系推理** ——“哪个客户拥有相同的账单实体?” “图赢;矢量和KV无法回答。

Production agents 三个都在一个会话中发布。 其中两个会话总是有错的。 Mem0的贡献是将所有三个都连接到一个 `add`/`search` 表面有能导引它们的评分功能

<a id="the-concept"></a>

## 概念

<a id="three-stores-in-parallel"></a>

### 三个平行商店

2025年4月, 2025年4月, 公元前 254 `add(text, user_id, metadata)`:

1. 从文本中摘录候选人事实(a) LLM- 驱动步骤)
2. 将每个事实写入矢量仓库( W)embedding) 用于 semantic search.
3. 将每个事实都写到 KV 密钥仓库( 用户)_id, 事实上_类型、实体)的 O(1) 查询。
4. 将每个事实写入图形存储处( Mem0g) 作为用于关系查询的打印边框 。

在 `search(query, user_id)`:

1. 矢量存储返回顶部 K 由 embedding cosine.
2. KV 存储返回直接点击, 键入查询源( 用户)_编号、类型、实体)。
3. 图形存储返回查询实体可达到的子图。
4. 分数层能让三者合二为一

<a id="fusion-scoring"></a>

### 组合评分

```
score = w_relevance * relevance(q, record)
      + w_importance * importance(record)
      + w_recency * recency(record)
```

- **Relevance** 矢量余弦, KV exact match图形路径 weight.
- **Importance** · 在写作时或学习时贴上标签(有些事实更重要:姓名、身份证、政策)。
- **Recency** ——自上次写或读以来,指数逐渐衰减。

Weights 调高每件产品。 `w_recency` 用于聊天 agents; 高点 `w_importance` 遵约 agents; 高点 `w_relevance` 用于检索 agents.

<a id="mem0g-and-temporal-reasoning"></a>

### 时间推理

菜单格添加冲突检测器。 当新事实与现有边缘相矛盾时, 现有的边框会标记无效, 但不会删除 。 时间查询 (“ 用户在三月的城市是哪个城市 ” ) 时空查询会绕过有效的实时分页 。

这是Letta的 无效模式 概括。

<a id="benchmark-numbers"></a>

### 基准数

备忘录报告(2025年):

- **LoCoMo** (长式对话记忆):91.6
- **LongMemEval** (长视距偶发记忆):93.4
- **北京1时** (1M-token 内存基准: 64.1

比较基线(全文128k) LLM,平面矢量存储,平面 KV) 损失10+点。仅靠基准并不能证明选择是正确的——操作形状是有效的——但数字显示聚变设计不是一个圆差。

<a id="scope-taxonomy"></a>

### 范围分类

内存范围为 mm0 :

- **用户内存** ——会议间一直坚持,主要 `user_id`.
- **会话内存** - 坚持在一条线内。
- **Agent memory** — 每-agent 实例状态。

每个写入选择一个范围。 检索可使用每个范围查询 weights混合镜是"助理告诉爱丽丝鲍勃的工程"

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **Embedding drift.** 向量结果,在头一百个查询中显示正确,随着体积的增大,会降低。添加定期的重新embedding 中,在前N类记录中。
- **科幻怪兽** `(user_id, type, entity)` 看上去很简单,直到每个团队都加入他们自己的 `type`. 每季度对设定的类型进行审计。
- **图形爆炸** 一台噪音提取器每封信增加50个边缘。 Cap picture pritoms patters per `add` 调用;降低低信心边缘。

```figure
ae-memory-fusion
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 在 stdlib 中执行三层模式:

- `VectorStore` - 幼稚 token- 重叠相似性 embedding stand-in.
- `KVStore` ─按键 `(user_id, fact_type, entity)`.
- `GraphStore` - 输入边缘(主题、关系、对象、有效)。
- `Mem0` 顶级外表 `add()`, `search()`,核聚变评分,以及范围感应检索。
- 工作过 trace 在一个多用户,多会话。

运行：

```
python3 code/main.py
```

输出显示三个单独的回溯路径加上引信上方K。 翻转评分 weights 位于 `main()` 看着排名的变化。

<a id="use-it"></a>

## 实际应用

- **备忘录(Apache 2. 0)** 自动主机,带有 Postgres + Qdrant + Neo4j, 或使用管理好的云。
- **Letta** - 三级核心/召回/存档;带来自己的矢量和图形后端。
- **Zep** 具有时间KG和事实提取的商业替代物。
- **自定义构建** - 当你需要精确控制提取(合规)或聚变 weights (voice agents 由专制控制)。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-hybrid-memory.md` 产生一个三层内存的脚架,并配有聚变计分器、范围分类和时间失效。

<a id="exercises"></a>

## 练习

1. 将玩具矢量相似性替换为真的 embedding 模式(判决-)transformers奥拉马 OpenAI embeddings) 措施在合成长篇谈话中回顾@ 10。 排名流过1000 吗 ?
2. 添加时间查询 : `search(query, as_of=timestamp)`。只返回当时或之前有效的记录。哪个商店需要最精细的工作?
3. 执行冲突检测器: 如果一个输入的事实与图形边缘相矛盾, 则将旧边缘和日志都无效。 测试“ 用户生活在柏林” - “ 用户生活在里斯本 ” 。
4. 将聚变计分器移植到包含 `user_feedback` 维度(在检索的记录上拖动),如何防止游戏( agent 仅返回已经喜欢的记录)?
5. 读下Mem0 文档( MEM0 docs) (% 1)`docs.mem0.ai`))将玩具端到 `mem0` 客户端呼叫。 比较相同 20 个测试查询的检索质量 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 混合内存 | "Vector 加上图形加上 KV" | 三个商店平行写,在检索时装订 |
| 事实提取 | "记忆摄入" | LLM 将文字切入( 实体、 关系、 事实) tuples |
| 组合评分 | 相关排名 | 相关、重要、坚忍的加权总额 |
| Scope | "记忆命名空间" | 用户/ 会话/ agent - 确定谁看到了什么 |
| Mem0g | "记忆图" | 输入关系查询的有时间有效性的边 |
| 时间失效 | "轻轻地删除" | 标记相矛盾的边缘无效; 永远不删除 |
| Embedding drift | 寻回腐烂 | 矢量质量随着体质的增大而降解;定期重新组装 |

<a id="further-reading"></a>

## 进一步阅读

- [Chhikara等人,Mem0(arXiv:2504.19413)](https://arxiv.org/abs/2504.19413) - 原始文件
- [菜单](https://docs.mem0.ai/platform/overview) 生产 API, SDKs,管理云层
- [Packer等人,MemGPT(ARXiv:231.08560)](https://arxiv.org/abs/2310.08560) 虚拟文字的前身
- [Letta, 记忆屏障博客](https://www.letta.com/blog/memory-blocks) - 三级兄弟姐妹设计
