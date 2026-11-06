<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="model-routing-as-a-cost-reduction-primitive"></a>

# 将模型路由作为降低成本的基本手段

> 动态经纪人对每一项请求进行评估(任务类型, token length, embedding 生产案例研究显示,美国/英国/欧盟部署的低质量成本降低了20-60%;高容量SaaS的30%的节能提高变成了6位数的年度节约。 LLM inference 每年价格下跌~10x-a GPT-4-class token 从2022年底到2026年,从20/M美元到~0.40/M。 下降的多数是更好地服务堆叠( 第17阶段 · 04-09),而不是硬件。 运行是如何将价格下跌转化为利润,而不导致产品回归。 失败模式是廉价的模式流: 路线将40%推向较弱的模式, 质量下降3-5 % 用于推理任务, 四分之一没有任何人注意到。 门路通过在线质量衡量标准, 而不仅仅是离线 。 eval sets.

**类型：** 了解
**语言:** Python (stdlib,玩具条条路由器模拟器)
**先修要求:** 阶段17 · 0.1 (管理) LLM 平台,第17阶段 · 19(AI网关)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释模型的级联: 廉价第一, 以信心检查, 升级在低信心。
- 计算四个路径信号(任务分类, prompt length, embedding 与已知的硬体组合相似,
- 计算目标路径分割和质量损失承受力的预期混合成本。
- 列出能捕捉廉价模型爬虫的漂移监测度量(在线质量门)。

<a id="the-problem"></a>

## 问题

服务费八万块,每月八千块 GPT-5. 你的分析显示70%的查询是简单的:“在巴黎几点?” “改写这句话。”一个海库级模型以3%的成本处理那些问题。30%需要 GPT-5的推理 编码 数学 多重步骤 planning.

如果将70%的价位降低到便宜,30%的价位降低到昂贵,那么你的账单就会以同样的产品质量下降~65%。这是路径选择。技巧是建立经纪人而不退缩。

<a id="the-concept"></a>

## 概念

<a id="four-routing-signals"></a>

### 四个路由信号

1. **任务分类**:简单/复杂/编码/数学/聊天。可以是一个基于规则的分类器,一个小 LLM (海库级,0.25美元/M),或 embedding 与标签的桶相似。 输出: 路径 = 便宜/ 平衡/ 边框 。

2. **Prompt length**: prompts >4K tokens 往往需要边界来协调。 Prompts <500 tokens 通常不会

3. **Embedding 与已知硬集相似**:如果查询接近已知硬桶(cosine > 0.88),则直接升级到边界。

4. **由第一通行证提供的自信**:发送到廉价的地址;如果模型的日志显示信心低,或者拒绝或输出套用语言,则在边界上重试。在~10%的流量上添加P95的延迟度,但在其他90%上则节省50。

<a id="three-patterns"></a>

### 三种模式

**Pre-route** 插入~ 5- 10 m 的延迟度; 整体速度最快 。

**Cascade** (先是便宜,低置信度升级):~1.2x中位延迟(先是小便,再加核查),~2x升格。最佳质量的地板。

**组合路径** (为抽样、奖赏模型选手同时管理廉价和前沿):质量最高、成本最高;仅用于关键A/B。

<a id="implementation"></a>

### Implementation

AI网关(第17阶段 · 19)暴露路径。 `router` 配置后退和成本路径。 端口有警卫+路径。 Kong AI 网关有基于插件的路径。 OpenRouter 的模型市场披露了一条建议 API.

开放来源:路由LUCLLM(LMSYS),非钻石(商业), Prompt Mule.

<a id="the-2026-price-curve"></a>

### 2026年的价格曲线

| 模型类 | 2022年晚间 | 2026 | 改变 |
|-------------|-----------|------|--------|
| GPT- 4级质量 | ~$20/M | ~$0.40/M | 50x便宜点 |
| 边境(GPT-5, Claude 4) | — | ~$3-10/M | 新级别 |

大部分改进是提高效率——第17阶段的核心教训 04-09变成了供方成本的下降。 运行让您在应用层捕捉到这些收益,而不是等待所有用户都转移到廉价的层次。

<a id="drift-is-the-real-risk"></a>

### 漂流才是真正的风险

这条路能把40%的车运到廉价的模型上 distribution shifts 路由器没有注意到它的分类器是用Q1数据训练的。 质量会悄悄下降。 没有人抱怨得够大声。 您在竞争者基准中发现了您丢失的数据 。

以在线质量衡量的门路:

- 每个路径的用户缩略图/缩略图下移。
- Automated LLM- 判断一个悬停样本(5%)的路线。
- 升温率:如果级联正在踢出路径 > 30%,那么廉价模式就会超前。
- 拒绝率每条路线。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 2026年按等质计算节省的路线:20%至60%的案例研究。
- LLM 价格下跌2022-2026年:每年总计~10x。
- GPT2022年4级与2026年: ~ 20/M ~ 0. 40/M.
- 层叠的延迟影响:~1.2x中位数,~2x升级(流量的10%)。

```figure
model-cascade-router
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟前路程、级联和混合工作量,报告将成本、质量损失和升级率混在一起。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-router-plan.md`鉴于工作量和质量预算,选择了路线模式和信号。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。级联在什么准确度的楼层上打之前的路线?
2. 您的用户基础是 30% 的企业( 复杂查询) , 70% 的自由级别( 简单) 。 设计路径分割 。 是什么在线公关 ?
3. 路线质量下降2%,但节省40%。这是一艘船舶吗?取决于产品——两者都存在。
4. 使用来自 OpenAI / Anthropic APIs你从什么开始?
5. 六个月来,上升率从8%上升到22%。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 模式路线 | "成本经纪人" | 每一请求的模型动态选择 |
| 型号级联 | "便宜的第一次升级" | 低调跑,低调的跑到边境 |
| Pre-route | "先分类" | 前方分类; 不重运行 |
| 组合路径 | "平行选择" | 跑多步,奖赏模特儿选得最好 |
| 升级率 | "上调%" | 升级的级联要求数目 |
| RouteLLM | "LMSYS路由器" | OSS 路由器库 |
| 不是钻石 | "商业路由器" | SaaS 模型路由产品 |
| Drift | "廉价的爬行" | Distribution shift 无路由器注意到 |
| 在线质量门 | "活体检查" | Automated LLM-judge sampling 现场交通 |

<a id="further-reading"></a>

## 进一步阅读

- [阿布亚什·苏奇-示范路由 LLM 2026 最佳做法](https://web.archive.org/web/20260413143335/https://abhyashsuchi.in/model-routing-llm-2026-best-practices/)
- [卢卡斯·布伦纳—— Inference 优化2026年](https://dev.to/lukas_brunner/the-rise-of-inference-optimization-the-real-llm-infra-trend-shaping-2026-4e4o)
- [路由LLM 纸张/代码](https://github.com/lm-sys/RouteLLM)
- [非钻石-模式路线](https://www.notdiamond.ai/)
- [OpenRouter](https://openrouter.ai/) - 多型的入口,有原始人
