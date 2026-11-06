---
name: skill-naive-bayes-chooser
description: Choose the right Naive Bayes variant for your classification task
phase: 2
lesson: 14
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


您是概率分类方面的专家。当有人需要选择朴素贝叶斯变体时，引导他们完成这个决策过程。

<a id="decision-checklist"></a>

## 决策清单

<a id="step-1-what-are-your-features"></a>

### 第1步：您的features是什么？

- **字数或 TF-IDF 值** -> 多项式NB
- **连续测量（temperature，高度，传感器读数）** -> GaussianNB
- **二进制指示器（单词存在/不存在，复选框状态）** -> BernoulliNB
- **混合类型** -> 拆分为子集，或全部转换为一种类型

<a id="step-2-how-much-data-do-you-have"></a>

### 第 2 步：您有多少数据？

- ** 1,000 个样本以下**：朴素贝叶斯是一个强有力的选择。其强大的先验（独立假设）阻止了 overfitting。
- **1,000到50,000个样品**：NB仍然有竞争力。与逻辑回归进行比较。
- **超过 50,000 个样本**：逻辑回归或 gradient 提升可能会优于 NB。使用 NB 作为基线。

<a id="step-3-tune-smoothing"></a>

### 第 3 步：调整平滑度

- 从 alpha=1.0（拉普拉斯平滑）开始。
- 如果精度较低并且您有足够的数据，请尝试 alpha=0.1 或 0.01。
- 如果模型是overfitting（训练>>测试精度），则将alpha增加到5.0或10.0。
- 始终通过交叉验证来验证平滑，而不是单个训练/测试分割。

<a id="step-4-check-assumptions"></a>

### 第 4 步：检查假设

- **MultinomialNB**：Features 必须为非负数。如果有负值，请移动或使用 GaussianNB。
- **GaussianNB**：当 features 在每个类中大致呈钟形时效果最佳。检查直方图。
- **BernoulliNB**：首先对 features 进行二值化。仔细选择阈值（对于文本：present=1，absent=0）。

<a id="common-mistakes"></a>

## 常见错误

1. **在文本数据上使用 GaussianNB。** 字数统计不是高斯分布。使用多项式NB。
2. **忘记拉普拉斯平滑。** 单个未见过的单词会将整个概率归零。始终顺利。
3. **信任概率输出。** NB概率校准不佳。将它们用于排名，而不是作为置信度得分。如果您需要校准概率，请使用 CaliberatedClassifierCV。
4. **忽略类别不平衡。** NB先验反映类别频率。 99% 为阴性，1% 为阳性，先验压倒了可能性。手动调整先验或重新采样。

<a id="quick-reference"></a>

## 快速参考

| 问题 | 多项式NB | 高斯NB | 伯努利NB |
|----------|:---:|:---:|:---:|
| 文本分类？ | 是的 | 否 | 也许（短文） |
| 连续features？ | 否 | 是的 | 否 |
| 二进制 features？ | 否 | 否 | 是的 |
| 需要非常快速的培训吗？ | 是的 | 是的 | 是的 |
| 小训练集？ | 好 | 好 | 好 |
| 需要校准概率吗？ | 否 | 否 | 否 |

<a id="when-not-to-use-naive-bayes"></a>

## 何时不使用朴素贝叶斯

- Features 高度相关，并且您有足够的数据用于处理相关性的模型（逻辑回归、gradient 提升）
- 您需要尽可能高的准确性并拥有大量数据
- 您的 features 是图像、序列或图形（使用神经网络）
- 您需要一个捕获 feature 交互的模型（使用基于树的方法）
