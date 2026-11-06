<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="multimodal-rag-and-cross-modal-retrieval"></a>

# 多模态 RAG 与跨模态检索

> 愿景文件 RAG 生产多式联运 RAG 范围更广——为像旅行这样的工作流程检索文本、图像、音频和视频 planning 2025年的三次调查——Abootorabi等人、Mei等人、赵等人,编纂了次级问题:跨模式检索、检索聚合、一代。 grounding多式联运 evaluation. 这一课程读取了调查结果,并设计了生产管道。

**类型：** 构建
**语言:** Python (stdlib, 带有聚变+固定发电机的跨式检索器)
**先修要求:** 阶段12 · 23(哥伦比亚),阶段11(RAG basics)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 设计跨式检索:文本 图像 文本 音频 视频等
- 比较三种聚变策略: 分聚变, attention- 基点核聚变, MoE fusion.
- 解释生成 grounding:当源头混合在一起时,“ 锁定你的来源” 是什么样子的? modalities.
- 列出三种卡尼卡多式联运 RAG 2025年的调查及其次级问题分类。

<a id="the-problem"></a>

## 问题

Single-modality RAG 是一个已解析的模式: 嵌入查询、 嵌入块、 检索、 东西进入 LLM多式联运 RAG 需要:

1. 多个检索头( 每个 modality needs embeddings 位于一个可兼容的空格中)。
2. 检索结果的融合 modalities.
3. Generation grounding 引用源 modalities.
4. Evaluation 覆盖跨模式信号的测量仪

2025年的调查都得出了相同的分类。

<a id="the-concept"></a>

## 概念

<a id="cross-modal-retrieval"></a>

### 跨模式检索

检索文档 modality B 给出查询 modality A. 三种模式:

1. Shared embedding space。 CLIP 和 CLAP 生成文本+图像/文本+音频 embeddings 在一个共同的空间。 Cosine similarity across modalities 直接工作,仅限于CLIP训练的夫妇

2. Per-modality encoder +翻译。 encoder + 图像 encoder + 一个小翻译模块, 由 Gupta 等人和其他2024年的设计在空格之间绘制。 灵活但又增加了复杂性 。

3. 甚低频Mm 以 encoder。使用 VLM 隐藏状态作为检索代表。 modality 甚低频磁共振支持工作,质量更高,成本更高。

选择: CLIP/ SigLIP 2 用于文本+图像; CLAP 用于文本+图迪奥; VLM-隐藏状态用于边境质量的交叉模式。

<a id="fusion-strategies"></a>

### 融合战略

您获取了10个结果: 5 张图像, 3 条文字, 2 个音频剪辑。 您如何合并 ?

分数混凝( 最便宜) 。 modality 有自己的检索器, 每个返回分数。 将分数在...modality 简单,经常有用

Attention- 以组合为基础。 将所有回收的物品集中起来, 让一个小的 attention network weight 需要训练

MoE 核聚变 连接网络线路 modality不同的查询类型不同,视觉问题 weights 图像更高。

生产默认: 分数混和, 略微偏向于查询的主导性 modality升级为 MoE 如果 A/B 显示在您的域上明显胜出 。

<a id="generation-grounding"></a>

### Generation grounding

该 LLM 索赔的金额应注明收回的物品是每项索赔的原由。

- 文本来源:标准引用 `[1]`.
- 图像来源 : `[img 3]` 有个短标题
- Audio: `[audio 2 at 0:34]`.

训练发电机 grounding- 了解数据:培训目标中的每项索赔都用源索引标出。 inference,该模型自然会发布引用。

<a id="the-2025-surveys"></a>

### 2025年调查

Abootorabi等人(arXiv:2502.08826, " 询问任何 Modality" :多式联运分类 RAG覆盖回收、聚变、生成,覆盖面最广

Mei等人(arXiv:2504.08748,“多式联运调查” RAG“):侧重于次级任务基准和失败模式。 evaluation design.

赵等人(arXiv:2503.18016):注重愿景的调查,大力开展Pali-家庭工作。

阅读所有三个版本,您就可以了解2025年春季的艺术水平。大部分子问题仍然未解决。

<a id="murag--the-foundational-paper"></a>

### 穆拉格——基础文件

MuRAG(Chen等人,2022年)是第一个多式联运公司。 RAG。从多式 KB 中检索到的图像+文字,生成了答案。在 VLM 波之前显示可行性。现代系统(System System)REACT维萨拉格,M3DocRAG) 在此基础上。

<a id="a-production-trip-planner-example"></a>

### 制作旅行计划实例

问:"找到我一个安静的素食早午餐 用自然光。"

Pipeline:

1. 解析查询。 “ 安静” 音频/ 审阅关键词; “ 蔬菜早午餐” 菜单项; “ 自然光” 图像 feature.
2. 获取每 modality:
   - 评论时的文字检索: "蔬菜早午餐,安静的香肠。"
   - 餐厅照片上的图像检索: "自然光,空气。"
   - 环境声音剪辑上的音频检索: "低调,没有音乐。"
3. 引信分数 每个餐馆都有综合分数
4. 高档餐厅VLM发电机 附有所有证据 回答引用。

这远远超出了文本的范围RAG. 每个 modality 添加信号, 单文本丢失 。

<a id="agentic-multimodal-rag"></a>

### Agentic multimodal RAG

多跳:如果第一次检索不返回高度自信的答案, LLM 重新配置并检索。 Agentic RAG 14阶段的图案在此应用。例如:

- 获取首字母首字母表 LLM 问"太吵,过滤器 <40 dB" 重新检索。
- 获取图像 LLM 发现一个菜单 \ 检索菜单文本 \ 回答。

添加复杂度, 但处理单发检索无法的查询 。

<a id="evaluation"></a>

### Evaluation

Cross-modal evaluation 仍然不成熟。 常见的代理 :

- Recall@k 每 modality.
- 完全失灵了
- 人类判断的终至终的满足感
- 具体任务(预订完成、采购完成)。

没有标准基准覆盖全部 modalities大多数文件评价了具体领域的任务。

```figure
contrastive-matrix
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- 三个模拟检索器(文字、图像、音频)在共享的餐馆群中运作。
- 组合的积分 modality 带有可配置的分数 weights.
- 发电机的根根子 发出最后的答案
- 简单 agentic 循环, 如果信任度低, 则重新配置查询 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-multimodal-rag-designer.md`。如果产品规格带有多式联运查询流程,则设计检索器、聚变器、发电机和 evaluation.

<a id="exercises"></a>

## 练习

1. 提议医疗-创伤多式联运 RAG:查询=受伤照片+文本症状。 modalities 从什么KB回收?

2. 分数聚合是一个简单的加权总和。 它有什么失败模式 MoE 核聚变会避免吗?

3. 阅读 Abotoorabi 等人的分类(第3节),这三个问题是什么? 它们如何映射到你所选产品?

4. 设计出一个旅行计划多式联运的电子逆向拍卖 RAG。什么衡量标准包括图像回溯、音频回溯和复合正确性?

5. Agentic multi-hop RAG 使用每轮轮假的潜伏税。 准确度的增益在什么情况下证明潜伏是合理的?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 跨模式检索 | "问一 modality,再找一个" | 文本查询获取图像; 图像查询获取文本; 需要共享空间或翻译 |
| 分数聚变 | 交配分数 | 加权总额modality 检索分数; 最简单的聚合 |
| MoE fusion | "Modality- 路由专家" | 星际网络选择 modality每个查询的分数 |
| 地下发电 | 联系你的线人 | 答复中的每项索赔都标有源索引 |
| MuRAG | "第一多式联运 RAG" | 2022年建立多式联运的论文 RAG pattern |
| Agentic multi-hop | "重新组合和重试" | LLM 第一次通过信任度低时的检索器 |

<a id="further-reading"></a>

## 进一步阅读

- [Abootorabi等人——问任何问题 Modality (arXiv:2502.08826)](https://arxiv.org/abs/2502.08826)
- [Mei等人——多式联运调查 RAG (arXiv:2504.08748)](https://arxiv.org/abs/2504.08748)
- [赵等人——愿景 RAG 调查(arXiv:2503.18016)](https://arxiv.org/abs/2503.18016)
- [陈等人-MuRAG(ARXiv:2210.02928)](https://arxiv.org/abs/2210.02928)
- [刘等人- REACT (arXiv:2301.10382)](https://arxiv.org/abs/2301.10382)
