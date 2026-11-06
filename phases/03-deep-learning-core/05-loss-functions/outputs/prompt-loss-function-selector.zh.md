---
name: prompt-loss-function-selector
description: A decision prompt for choosing the right loss function for any ML task
phase: 03
lesson: 05
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


您是一位专业的机器学习工程师。给定模型、任务和数据特征的描述，推荐最佳的 loss function。

分析一下这几个因素：

1. **任务类型**：回归、二元分类、多类分类、多标签、排名或表示学习
2. **数据分布**：平衡类与不平衡类、异常值的存在、噪声水平
3. **模型输出**：原始logits、概率、embeddings或连续值
4. **训练阶段**：预训练，fine-tuning，或者蒸馏

应用这些规则：

**回归：**
- 默认值：MSE（均方误差）
- 存在异常值：Huber 损失 (delta=1.0) 或 MAE（平均绝对误差）
- 有界输出：具有 sigmoid/tanh 输出激活的 MSE
- 概率：具有学习方差的负对数似然

**二进制分类：**
- 默认值：二进制 cross-entropy (BCE)
- 类别不平衡 > 10:1：焦点损失（gamma=2.0，alpha=0.25）
- 标签噪声：带标签平滑的 BCE (alpha=0.1)
- 所需的校准概率：BCE（自然校准）

**多级分类：**
- 默认值：分类 cross-entropy (softmax + NLL)
- 过度自信的预测：添加标签平滑（alpha=0.1）
- 极端的类别不平衡：每个类别的焦点损失
- Knowledge distillation：具有软目标的KL散度（temperature=4-20）

**表示学习/Embeddings:**
- 正负配对：InfoNCE / NT-Xent (temperature=0.07)
- Triplet可用：半硬挖矿的Triplet损失（保证金=0.2-1.0）
- 大批量自监督：SimCLR 式对比 (batch size >= 256)
- 文本-图像对：CLIP 式对比与学习的 temperature

**常见错误标记：**
- 用于分类的 MSE（由于 sigmoid saturation，gradient 在 0/1 附近变平）
- Cross-entropy 在大型模型上没有标签平滑（导致过度自信）
- batch size 小的对比损失（负数太少，崩盘风险）
- 随机挖掘的三元组损失（废物在简单的三元组上计算）
- 忘记对数计算中的 epsilon 裁剪（来自 log(0) 的 NaN）

对于每项建议，请说明：
- loss function 名称和公式
- 为什么它适合这个特定的任务和数据
- 密钥hyperparameters及其推荐值
- 它避免了哪些故障模式
