<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-05--autonomous-research-agent-ai-scientist-class"></a>

# 综合项目 05：自主研究 Agent——AI-Scientist 级系统

> 萨卡纳的AI -Scientist -v2 发表了完整的论文。 Agent 实验室进行了实验。 traces。2026年形状是:计划执行树类搜索,而不是实验,预算成本,沙箱代码执行,视觉反馈的LaTeX作家,以及自动NeurIPS型的审查器组合。综合项目是建造一个,每张纸30美元之内结束,并维持下去 sandbox- 逃离了红色小队,萨卡纳记录。

**类型:** Capstone
**语言:** Python (agent + sandbox), LaTeX(产出)
**先修要求:** 第二阶段(ML),第三阶段(深层学习),第7阶段(transformers第十阶段(LLMs 14阶段(从零开始)agents,第15阶段(自治),第16阶段(多至agent,第18阶段(安全)
**实施阶段:** P0 ; P2 ; P3 ; P7 ; P10 ; P14 ; P15 ; P16 ; P18 ; P18 ; P6 ; P6 ; P6 ; P6 ; P6 ; P6 ; P8 ; P6 ; P6 ; P6 ; P6 ; P6 ; P6 ; P6 ; P6 ; P8 ; P6 ; P6 ; P6 ; P2 ; P2 ; P2 ; P2 ; P2 ; P2 ; P2 ; P2 ; P2 ; P3 ; P7 ; P10 ; P10 ; P14 ; P15 ; P16 P16 ; P16 ; P18
**时间:** 40小时

<a id="problem"></a>

## 问题

自主研究 agents 2026年,Sakana AI的AI-Scientist-v2号卫星在《自然》上发表,并发表了论文,为讲习班同行审议扫清了障碍。 Agent 实验室运出可复制 traces. 该 agents 并不是魔术,而是一棵有成本上限、种子含量的实验树上 所运行的、计划执行的循环 sandboxes自动审查。 飞行器在循环中, 预算, 和安全故事。

在一个狭窄的域内,通过执行一个种子概念来学习循环(例如, attention-100米上的血迹parameter transformer) 。该值不是在第一次运行时发现新的东西。该值存在于基础设施:树的搜索、实验 sandbox作者-评论员循环, 红色团队报告。 sandbox- 逃生失败; agent 必须通过同样的红色队。

<a id="concept"></a>

## 概念

该 agent 是一个最佳的树搜索。 节点是实验性规格 :( 假话、 配置、 代码、 预期结果) 。 扩展步骤建议使用小编辑( swap) 来子化 optimizer转换 batch size每个孩子在新旧的 sandbox 以硬资源上限。 结果反馈到一个按节点排序的评分函数( 新标准x质量x剩余预算) 。 树长到预算用完, 然后是最好的 branch 写好了

作者是多式的。 它生成了 LaTeX 草稿, 编译它, 制作数字, 并输入 pDF 格式 Claude Opus 4.7的视觉模式,用于对布局、图象可辨性和索赔证据进行评议 alignment审评员共五人 LLM 法官们会分出NeurIPS式的分数(新颖、严谨、清晰、可复制、影响);如果平均跌到阈值以下,则纸张会带着批评回报给作者。

安全性是载荷的,每个实验都以E2B或代顿为单位进行。 sandbox 没有任何网络反射, 被隔墙时钟绑住, 并被钉住资源限制。 agent代码生成的步进穿过一个政策层 阻止了那些逃避 sandbox红色小组报告复制了萨卡纳有记录的攻击表面(叉弹、档案系统脱逃, LLM- 写网络电话)

<a id="architecture"></a>

## 建筑

```
seed idea + domain
      |
      v
  literature search (Semantic Scholar + OpenAlex + FAISS cache)
      |
      v
  LangGraph plan-execute-verify tree
      |
      v
  +--- expand node ----+      per-node sandbox
  |                    |      (E2B / Daytona)
  v                    v      resource caps
  child_1           child_k   no network egress
  |                    |      deterministic seeds
  v                    v
  run experiment       run experiment
  |                    |
  v                    v
  score nodes by (novelty, quality, budget)
      |
      v
  best branch -> LaTeX writer
      |
      v
  compile + vision critique (Opus 4.7 vision)
      |
      v
  reviewer ensemble (5 LLM judges, NeurIPS rubric)
      |
      v
  paper.pdf + review.md + trace.json
```

<a id="stack"></a>

## 堆栈

- Orchestration: LangGraph 检查和人approval gates
- 树搜索: 自定义的实验节点第一(来自 Sakara v2 的AB- MCTS 型号)
- Sandbox:每个实验的E2B, Docker-在-Docker 后退; 通过分组设定资源上限
- 文学:语义学学者图 API + OpenAlex + 本地 FAISS 摘要缓存
- 作家: LaTeX 模板+ Claude 图表评论和布局的Opus 4.7(视觉模式)
- 审阅员:共5名法官(Opus 4.7, GPT-5.4, Gemini 3 专业, DeepSeek R1, Qwen3- Max), 加权汇总
- 实验框架: PyTorch 2.5 用于物理实验,W&B用于记录
- Observability: 兰福斯 agent traces,每张纸30美元硬预算

```figure
ce-experiment-tree
```

<a id="build-it"></a>

## 动手实现

1. **种子和域范围界定。** 采用种子概念(例如,“投资扩张模式” attention 子-1B地图 transformers" )界定搜索空间:模型、数据集、计算预算。

2. **文学传记** 查询语义学者+开放亚历克斯,共50份最有名的相关论文;本地缓存摘要;生成一页域摘要。

3. **树架** 使用种子假设初始化根。 执行 `expand(node) -> children` 带有小版建议(每个儿童一个配置变化)。 `score(node)` 是一个加权新颖的x质量x预算术语。

4. **Sandbox wrapping.** 每一个实验都进行着 `docker run --network=none --memory=8g --cpus=2 --pids-limit=256 --read-only` 种子是写到 sandbox;输出被挂载为只读后退。

5. **计划执行循环 。** `plan` 提议孩子。 `execute` 运行 sandbox,捕捉日志和测量仪。 `verify` 运行单位检查测量标准( 损失是否减少? 烧损是否分离了效果?) 。 失败的节点会在树上找到一个故障原因 。

6. **Writer.** 预算之后,选择最好的 branch。使用 matplotlib 生成一个 LaTeX 草稿 Claude 行动4.7与 branch trace 将编译的 PDF 反馈到 Opus 4. 7 视图中进行评论。

7. **评论者组合。** 五名法官以NeurIPS(NeurIPS)式的标语评分草稿(小写、硬写、清晰、可复制、撞击)。如果表示 < 4.0/5, 则用批评回写。 3次重写后会很难停止 。

8. **红队** 构建或整合一套针对 sandbox叉弹,网络的清除尝试,文件系统逃脱, LLM确定所有被封存,写下结论

9. **Reproducibility.** 每一艘纸船都用树来搜索 trace JSON种子,W&B运行链接, sandbox 配置,和README复制结束。

<a id="use-it"></a>

## 实际应用

```
$ ai-scientist run --seed "attention sparsity in sub-1B transformers" --budget 30
[lit]    50 papers, digest in 12s
[tree]   expanded 8 nodes, budget 12/30
[exec]   node #3 sparsity=top-8, loss=2.83 (best so far)
[exec]   node #6 sparsity=top-4, loss=3.12 (worse)
[exec]   ...
[tree]   chose branch rooted at node #3 (novelty 0.62, quality 0.81)
[write]  LaTeX draft v1 complete
[vision] critique: figure 2 legend too small, claim-evidence ok
[write]  draft v2 after 3 edits
[review] mean 4.2/5 (novelty 3.9, rigor 4.3, clarity 4.1, repro 4.5, impact 4.2)
[done]   paper.pdf + review.md + trace.json     $28.40 spent
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-ai-scientist.md` 是一个种子想法+一个域+30美元的预算,它运行整个管道,并发行一份可审查的纸和可复制的包。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 纸张质量 | 与已发表的讲习班论文相比的盲人图示审查 |
| 20 | 实验性硬化剂 | 基线、种子、污点;结果表中每个索赔都有一个单元格支持 |
| 20 | 费用和计算纪律 | 30美元/纸顶,朗弗斯追踪 |
| 20 | 安全 | Sandbox 红色小队通过; 网络策略和杀法验证 |
| 15 | 再现性 | 单命令重播, 以相同的种子复制纸张 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 运行管道时要对同一域的三个不同的种子想法进行对比。 比较树类搜索的哪些部分重叠。 识别重复的浪费计算 。

2. 添加a human-in-the-loop 实验执行前门,估计超过5美元。测量总成本下降多少。

3. 将审阅者合在一起换成一个法官。 测量一组已知的坏文件的错误接受率 。

4. 引入网络过滤红色团队测试 : agent 写下试图 `curl` 外部地址。 确认 `--network=none` 政策阻止它。记录尝试。

5. 比较您的树搜索与一个平坦的随机基线( 预算相同, 没有扩展策略) 。 报告新颖的质量增益 x 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 树搜索 | "AB-MCTS型扩张" | 与新颖x质量x预算分数的实验节点相比, 最佳第一次探索 |
| Sandbox | 实验隔离 | 无网络的集装箱,捆绑 CPU/ 模拟、 钉子种子, 仅读输入 |
| 批评愿景 | "Render-then-read" | 将文件编译为 PDF, 将 PDF 反馈到 VLM 上, 以便进行布局和索赔证据的批评 |
| 评论员合写 | “自动化同行审查” | Multiple LLM 法官用NeurIPS标记评分纸;加加权总门输油管 |
| 超赞分数 | "这是新的吗?" | 刺激的情绪,惩罚接近50页文献库 |
| 费用上限 | "美元预算" | 每张纸总开支的硬上限;朗富斯计数器+预运行估计数 |
| 红队 | "Sandbox- 逃生审计" | 避免被 sandbox 如果政策有错 |

<a id="further-reading"></a>

## 进一步阅读

- [Sakana AI-Scientist-v2 库](https://github.com/SakanaAI/AI-Scientist-v2) 参考生产研究 agent
- [Sakana AI-Scientists-v1 纸张(arXiv:2408.0292)](https://arxiv.org/abs/2408.06292) 最初的方法
- [ShinkaEvoluve(萨卡纳ICLR 2026)](https://sakana.ai) - 演进扩展
- [Agent 实验室(AMD)](https://github.com/SamuelSchmidgall/AgentLaboratory) - 多功能研究实验室框架
- [LangGraph documentation](https://langchain-ai.github.io/langgraph/) 参考 orchestration layer
- [语义学学者图 API](https://api.semanticscholar.org/) 文献搜索
- [E2B sandboxes](https://e2b.dev) 参考试验孤立
- [NeurIPS 审评员指南](https://neurips.cc/Conferences/2026/ReviewerGuidelines) - 评论者共同编码的标语
