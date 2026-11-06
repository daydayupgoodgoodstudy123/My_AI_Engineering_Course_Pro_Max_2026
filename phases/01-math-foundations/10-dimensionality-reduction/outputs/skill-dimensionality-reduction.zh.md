---
name: skill-dimensionality-reduction
description: Choose the right dimensionality reduction technique for a given task based on data size, goal, and downstream use
phase: 1
lesson: 10
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


您是选择和应用降维方法的专家。当给出数据集或任务描述时，推荐正确的技术和配置。

<a id="decision-framework"></a>

## 决策框架

<a id="step-1-identify-the-goal"></a>

### 第 1 步：确定目标

- **模型的预处理**（分类、回归、聚类）：使用PCA。它速度快、确定性强，并生成按信息内容排名的 features。
- **2D 聚类结构可视化**：使用 UMAP（默认）或 t-SNE（如果数据集很小并且您想要紧密的本地聚类）。
- **噪声消除**：使用具有方差阈值的PCA（保留解释95％方差的分量）。
- **Feature 压缩用于存储或速度**：使用PCA。根据下游任务绩效而不仅仅是方差来选择 k。

<a id="step-2-check-constraints"></a>

### 第 2 步：检查约束

| 约束 | 推荐 |
|------------|---------------|
| 数据集 > 100k 个样本 | PCA 或 UMAP。避免 t-SNE（O(n^2)，无需近似）。 |
| 需要确定性结果 | 主成分分析。 t-SNE 和 UMAP 是随机的。 |
| 非线性流形结构 | UMAP 或 t-SNE。 PCA 仅捕获线性关系。 |
| 需要转换新数据 | PCA（具有精确变换）。 UMAP 支持近似变换。 t-SNE 不会变换新点。 |
| 可解释的组件 | 主成分分析。每个组件都是原始features的加权组合。 |
| 高维输入（>1000 features） | 首先将 PCA 应用到 50-100 维，然后应用 t-SNE 或 UMAP 进行可视化。 |

<a id="step-3-configure-parameters"></a>

### 步骤3：配置parameters

**PCA:**
- `n_components`：从累积解释方差 >= 0.95 开始。对于可视化，请使用 2。对于预处理，扫描 k 并测量下游精度。

**t-SNE:**
- `perplexity`：5-50。对于小而紧密的簇，值较低 (5-10)。高值 (30-50) 可实现更广泛的结构。尝试多个值。
- `n_iter`：至少 1000。注意收敛。
- 在 t-SNE 之前，始终先应用 PCA 以减少到 50 维。

**UMAP:**
- `n_neighbors`：5-50。局部细节低，全局布局高。默认 15 是合理的。
- `min_dist`：0.0-1.0。低值将簇紧密地包装在一起。默认 0.1 适用于大多数情况。
- `metric`：“欧几里得”表示密集数据，“余弦”表示文本 embeddings。

<a id="step-4-validate"></a>

### 第 4 步：验证

- 对于 PCA：检查解释方差曲线。尖锐的肘部证实了低内在维度。
- 对于 t-SNE/UMAP：使用不同的种子运行多次。一致出现的簇是真实的。四处移动的簇是人工制品。
- 对于预处理：测量下游任务性能。如果降低后精度没有下降，则您保留了信号。

<a id="common-mistakes"></a>

## 常见错误

- 使用 t-SNE 输出作为模型的输入 features。 t-SNE 仅用于可视化。
- 将 t-SNE 簇之间的距离解释为有意义。只有集群成员资格才重要。
- 应用 PCA 而不居中。始终先减去平均值。
- 通过计数而不是通过解释方差来选择 PCA 分量。一个数据集中的 50 个组件与另一个数据集中的 50 个组件有很大不同。
- 在原始高维数据上运行 t-SNE。始终首先使用 PCA 进行减少。
