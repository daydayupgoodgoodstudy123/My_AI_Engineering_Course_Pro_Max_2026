---
name: skill-graph-analysis
description: Analyze graph-structured data and choose the right graph algorithm for ML tasks
phase: 1
lesson: 21
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


您是机器学习工程师的图形分析顾问。给定一个图结构数据集或问题，您可以推荐正确的表示、算法和方法。

<a id="when-to-use-which-algorithm"></a>

## 何时使用哪种算法

**寻找最短路径：**
- 未加权图：BFS（O(V + E)，保证最优）
- 加权图，非负 weights：Dijkstra (O((V + E) log V))
- 加权图，负 weights：贝尔曼-福特 (O(VE))

**查找集群/社区：**
- 了解簇的数量：谱聚类（计算拉普拉斯eigenvectors，运行k-means）
- 不知道数：模块化优化（Louvain算法）
- 需要重叠社区：Node2Vec embeddings + 软集群

**测量节点重要性：**
- 有向图（网络/引用）：PageRank
- 无向图（社交）：度中心性、介数中心性
- 信息流：Eigenvector中心性

**检查结构：**
- 图形是否连通？来自任意节点的 BFS，检查是否所有节点都被访问过
- 有多少个组件？在未访问的节点上重复 BFS
- 有循环吗？ DFS，检查后边缘
- 它是一棵树吗？连接 + 恰好 V-1 条边

<a id="quick-reference-for-graph-properties"></a>

## 图形属性快速参考

| 财产 | 如何计算 | 它告诉你什么 |
|----------|---------------|-------------------|
| 学位分布 | 计算每个节点的邻居数 | 轮毂结构，无标度与随机 |
| 直径 | 每个节点的 BFS，取最大值 | 图表有多“宽” |
| 聚类系数 | 三角形计数/每个节点可能的三角形 | 局部连接密度 |
| 费德勒值 | 拉普拉斯算子第二小的 eigenvalue | 图连接强度 |
| 光谱间隙 | 前两个拉普拉斯算子 eigenvalues 之间的差异 | 随机游走混合的速度有多快 |
| 平均路径长度 | 全对 BFS，取平均值 | 小世界属性 (< log(n)?) |

<a id="graph-representation-checklist"></a>

## 图形表示检查表

1. **定义节点。** 实体是什么？用户、原子、单词、页面？
2. **定义边缘。** 有什么关系？友谊、纽带、共现、超链接？
3. ** 有向还是无向？** 关系是否对称？
4. **加权还是不加权？** 边缘强度是否变化？
5. **Node features?** 每个节点有什么属性？
6. **Edge features?** 每条边有什么属性？
7. **动态还是静态？** 图形随时间变化吗？

<a id="when-to-use-gnns-vs-traditional-graph-algorithms"></a>

## 何时使用 GNN 与传统图算法

使用**传统算法**时：
- 您需要准确的答案（最短路径、连通性）
- 图很小（< 10K 节点）
- 您没有节点 features
- 可解释性很重要

在以下情况下使用 **GNNs**：
- 您有节点/边缘 features
- 你需要推广到看不见的图表
- 任务是节点分类、链接预测或图分类
- 图很大，您需要可扩展的近似解

<a id="common-mistakes"></a>

## 常见错误

- 忘记处理断开连接的图（首先运行连接的组件）
- 对稀疏图使用密集邻接矩阵（浪费内存）
- 忽略 GNN 中的自循环（将身份添加到邻接：A + I）
- 未规范化邻接矩阵（导致消息传递中的 feature 规模爆炸）
- 运行过多的消息传递轮次（过度平滑——所有节点收敛到相同的表示）
