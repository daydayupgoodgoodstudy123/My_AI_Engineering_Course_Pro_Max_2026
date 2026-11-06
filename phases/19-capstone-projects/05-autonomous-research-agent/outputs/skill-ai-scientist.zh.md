---
name: ai-scientist
description: Build an autonomous research agent that runs experiment tree search, writes LaTeX papers with vision critique, and passes a sandbox-escape red team.
version: 1.0.0
phase: 19
lesson: 05
tags: [capstone, autonomous-agent, ai-scientist, sakana, langgraph, sandbox, research]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


有了种子想法,一个狭窄的领域, 和30美元计算预算, agent 运行实验树搜索, 写一份可审查的 LaTeX 纸张, 并发布复制包 。

构建计划 :

1. 文学通行证:语义学学者图 API + OpenAlex; 在 FAISS 中缓存摘要; 生成一页域摘要 。
2. 树搜索: 在实验节点上执行最佳第一扩展 `expand(node) -> children` (每个子节编辑一个配置) 和 `score(node) = novelty*0.4 + quality*0.5 + budget*0.1`.
3. Per-node sandbox:每个实验都运行 `docker run --network=none --memory=8g --cpus=2 --pids-limit=256 --read-only` 或E2B等值; 确定性种子; 实施资源上限。
4. 计划执行核查:核实步骤检查是否损失趋同、基线运行、抽查分离索赔。
5. 作家: 生成 LaTeX, 编译到 PDF, 将 PDF 输入到 Claude 4.7 版面和索赔证据的评议视觉模式 alignment,循环最多三次。
6. 审阅员:五名法官(Opus 4.7, GPT-5.4, Gemini 3 专业, DeepSeek 内尔里普斯标注R1、Quen3-Max(新颖、硬度、清晰度、可复制性、冲击)的分数; 平均 < 4.0 返回写作者。
7. 红队:整合对抗任务(叉弹、文件系统逃跑、 LLM- 网络电话)确认所有被封锁。 `red_team.md`.
8. 可复制包: paper.pdf + view.md + 树类搜索 trace JSON +种子+W&B运行链接+ sandbox 配置 + 一行重运行命令 。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 纸张质量 | 参照已发表的关于同一种子专题的讲习班论文进行盲人图示审查 |
| 20 | 实验性硬化剂 | 基线、种子、污点;结果表中每个索赔都有一个单元格支持 |
| 20 | 费用和计算纪律 | 朗弗斯追踪每张纸30美元上限 |
| 20 | 安全 | Sandbox 红色团队通过; 网络策略和杀法转换经登录尝试验证 |
| 15 | 再现性 | 单命令重播以相同的种子复制纸张 |

艰难的拒绝 :

- 外边的实验 sandbox。 墓碑的全部理论是,处决是被遏制的。
- 不重读已编译的 PDF 的写作步骤( 视图评论包含载荷) 。
- 纸上没有基线,没有种子,也没有烧伤部分
- 费用预算仅作为热后警告而不是硬上限而执行。

拒绝规则 :

- 拒绝发表带有评论员的论文,系指低于4.0/5,而没有明显的人为超度。
- 拒绝运行种子想法 需要网络从内部访问 sandbox。将单选一个只读数据集卷。
- 拒绝重新运行未执行和登录的红队纸张。

输出:包含树搜索引擎的回购 sandbox 政策, 作家/ 评论者循环, 三个例子运行着复制包, 红色团队报告, 成本引导器 csv, 以及写出名称, 您复制的 Sakana v2 失败模式中哪些, 以及减缓效果如何 。
