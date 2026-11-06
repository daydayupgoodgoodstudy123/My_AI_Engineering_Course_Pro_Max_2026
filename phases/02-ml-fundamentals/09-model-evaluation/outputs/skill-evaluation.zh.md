---
name: skill-evaluation
description: Evaluation strategy checklist for classification and regression models
version: 1.0.0
phase: 2
lesson: 9
tags: [evaluation, metrics, cross-validation, model-selection]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="model-evaluation-strategy"></a>

# 型号 Evaluation 策略

用于正确评估任何 ML 模型的清单。请遵循此顺序以避免最常见的 evaluation 错误。

<a id="step-1-split-the-data-correctly"></a>

## 步骤一：正确分割数据

- 在任何预处理（缩放、插补、编码）之前进行分割
- 使用分层分割进行分类任务
- 保留一个测试集，最后只触摸一次
- 对于小型数据集，使用 5 倍或 10 倍交叉验证而不是单次分割
- 对于时间序列，使用基于时间的分割（切勿随机播放）

<a id="step-2-pick-the-right-metric"></a>

## 第 2 步：选择正确的指标

<a id="classification"></a>

### 分类

| 情况 | 使用这个指标 | 为什么 |
|-----------|----------------|-----|
| 均衡类别，简单比较 | 准确度 | 易于解释，在班级平等时有意义 |
| 误报代价高昂（垃圾邮件过滤器、欺诈警报） | 精度 | 衡量有多少标记的项目实际上是积极的 |
| 假阴性的代价高昂（癌症筛查、安全） | 召回 | 衡量您捕获到的实际阳性数量 |
| 需要平衡准确率和召回率 | F1分数 | 调和平均值，惩罚极端不平衡 |
| 跨阈值比较模型 | AUC-ROC | 与阈值无关的排名质量 |
| 数据不平衡 | F1、AUC-ROC 或 PR-AUC | 类别不平衡导致准确性产生误导 |

<a id="regression"></a>

### 回归

| 情况 | 使用这个指标 | 为什么 |
|-----------|----------------|-----|
| 标准回归，可接受异常值 | 均方根误差 | 与目标单位相同，惩罚大错误 |
| 异常值稳健 evaluation | MAE | 平等对待所有错误，不受异常值支配 |
| 比较不同尺度的模型 | R平方 | 归一化 0-1 等级（已解释方差分数） |
| 业务需要美元金额 | MAE 或 RMSE | 直接解释为误差大小 |

<a id="step-3-establish-baselines"></a>

## 第 3 步：建立基线

在评估模型之前，计算基线性能：
- 分类：多数类预测器（始终预测最常见的类）
- 回归：始终预测训练目标的均值
- 任何无法超越这些基线的模型都不是在学习

<a id="step-4-cross-validate"></a>

## 第 4 步：交叉验证

- 使用 K 倍（K=5 或 K=10）进行稳定估计
- 使用分层K折进行分类
- 报告折叠的平均值和标准差
- 平均值 = 0.85 和 std = 0.02 的模型比平均值 = 0.87 和 std = 0.10 更值得信赖

<a id="step-5-compare-models-statistically"></a>

## 第 5 步：统计比较模型

- 在未检查显着性的情况下，不要选择平均得分最高的模型
- 在交叉验证折叠中使用配对 t 检验
- 如果 |t| < 2.78（对于 K=5，df=4，p<0.05），差异可能是由于偶然造成的
- 当性能差异不显着时，考虑更简单的模型

<a id="step-6-check-for-common-mistakes"></a>

## 第 6 步：检查常见错误

- Data leakage：有没有测试数据信息流入训练？ （分割前缩放，目标导出features）
- 类别不平衡：准确性是否掩盖了少数类别的不良表现？
- Overfitting：训练和验证性能差距大吗？
- 太多了 evaluations：您是否多次查看测试集？

<a id="step-7-report-final-performance"></a>

## 第 7 步：报告最终表现

- 火车上训练+验证相结合
- 对保留的测试集进行一次评估
- 如果可能的话，报告所选指标的置信区间
- 说明基线比较（比随机/平均值好多少）
