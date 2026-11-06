---
name: skill-perceptron
description: Understand the perceptron pattern and when to use single-layer vs multi-layer architectures
version: 1.0.0
phase: 3
lesson: 1
tags: [perceptron, neural-networks, classification, deep-learning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="the-perceptron-pattern"></a>

# 感知器模式

感知器计算输入的加权和加上偏差，然后应用阶跃函数来产生二进制输出。它是神经网络的基本单元。

```
output = step(w1*x1 + w2*x2 + ... + wn*xn + bias)
```

<a id="when-a-single-perceptron-is-enough"></a>

## 当单个感知器就足够时

- 该问题是线性可分的：一条直线（或超平面）可以划分两个类
- 逻辑门：AND、OR、NOT、NAND
- 简单的阈值决策：“分数是否高于 X？”
- 聚类为两个不重叠区域的数据的二元分类器

<a id="when-you-need-multiple-layers"></a>

## 当您需要多层时

- 问题不是线性可分离的：没有一条线可以分离类
- 异或和奇偶校验问题
- 任何需要“这个而不是那个”推理的任务（条件组合）
- 现实世界的分类：图像、文本、音频——几乎总是非线性的

<a id="decision-checklist"></a>

## 决策清单

1. 绘制或检查您的数据。你能在类之间画出一条直线边界吗？
   - 是的：单个感知器有效
   - 否：您至少需要两层
2. 问题可以分解为更简单的线性决策的 AND/OR 吗？
   - 这个分解告诉你最小的网络结构
   - XOR = (A OR B) AND (NOT (A AND B)) = 2 层中的 3 个感知器
3. 对于两个以上类的问题，每个类需要一个输出节点

<a id="the-training-rule"></a>

## 训练规则

```
error = expected - predicted
weight_new = weight_old + learning_rate * error * input
bias_new = bias_old + learning_rate * error
```

如果预测正确，则不会发生任何变化。如果错误，weights 移位以减少错误。这仅适用于单层感知器。多层网络需要backpropagation。

<a id="common-mistakes"></a>

## 常见错误

- 尝试用单个感知器学习非线性模式（它永远不会收敛）
- 将 learning rate 设置得太高（weights 振荡）或太低（训练需要很长时间）
- 忘记偏差项（没有它，决策边界必须通过原点）
- 将感知器收敛（保证线性可分离数据）与一般神经网络收敛（不保证）混淆
