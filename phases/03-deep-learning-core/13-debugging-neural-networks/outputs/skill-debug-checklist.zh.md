---
name: skill-debug-checklist
description: Decision-tree checklist for debugging neural network training failures
version: 1.0.0
phase: 3
lesson: 13
tags: [debugging, neural-networks, training, diagnostics, deep-learning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="neural-network-debug-checklist"></a>

# 神经网络调试清单

训练出错时的系统调试协议。按顺序完成这些步骤——大多数错误都是在前 3 个步骤中发现的。

<a id="before-training-prevent-bugs"></a>

## 训练前（防止错误）

1. 打印模型架构和 parameter 计数。这个大小对您的数据有意义吗？
2. 使用随机输入运行单个 forward pass。输出形状与您的目标形状匹配吗？
3. 检查标签是否是正确的数据类型（CrossEntropyLoss 需要 Long，BCELoss 需要 Float）
4. 验证数据 normalization：输入的平均值应接近 0，标准差应接近 1
5. 打印 5 个随机（输入、标签）对。标签符合您的预期吗？
6. 确认训练/测试拆分没有重复样本

<a id="overfit-one-batch-test-60-seconds-catches-80-of-bugs"></a>

## 批量过拟合测试（60 秒，捕获 80% 的错误）

1. 从训练集中抽取 8-32 个样本
2. 使用合理的 learning rate 训练 200 步
3. 损失应接近 0。训练准确率应达到 100%
4. 如果失败：错误存在于您的模型、loss function 或训练循环中——而不是您的数据或 hyperparameters
5. 如果通过：继续全面训练

<a id="loss-not-decreasing"></a>

## 损失不减

1. 检查learning rate。尝试 3 个值：current/10、current、current*10
2. 每层打印gradient规范。全零意味着死网络或分离图
3. 在parameters上检查`requires_grad=True`。检查`loss.backward()`是否被调用
4. 检查`optimizer.zero_grad()`是否在`loss.backward()`之前被调用
5. 检查 `optimizer.step()` 在 `loss.backward()` 之后调用
6. 验证模型parameters是否传递给optimizer：`optimizer = Adam(model.parameters())`

<a id="loss-is-nan-or-inf"></a>

## 损失为 NaN 或 Inf

1. 将 learning rate 减少 10 倍
2. 将 epsilon 添加到所有 log() 调用中：`torch.log(x + 1e-7)`
3. 将 epsilon 添加到所有分区：`x / (y + 1e-8)`
4. 钳位预测：BCE 丢失前的 `torch.clamp(pred, 1e-7, 1 - 1e-7)`
5. 使用`torch.autograd.detect_anomaly()`查找准确操作
6. 检查输入数据中是否有 NaN：`assert not torch.isnan(x).any()`

<a id="loss-oscillating"></a>

## 损耗振荡

1. 将 learning rate 减少 3-10 倍
2. 增加batch size（减少gradient噪音）
3. 添加gradient clipping：`torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)`
4. 从 SGD 切换到 Adam（根据 parameter 的自适应 LR）
5. 添加 learning rate warmup 进行前 5-10% 的训练

<a id="overfitting-train-acc-high-test-acc-low"></a>

## Overfitting（训练acc高，测试acc低）

1. 添加dropout（从p=0.1开始，增加到0.5）
2. 将weight decay添加到optimizer：`Adam(params, weight_decay=1e-4)`
3. 减小模型尺寸（更少的层或更窄的层）
4. 添加data augmentation
5. 使用提前停止：当验证损失增加 5 个以上时期时停止
6. 检查训练集和测试集之间是否有 data leakage

<a id="underfitting-both-train-and-test-acc-low"></a>

## Underfitting（训练和测试acc都低）

1. 增加模型容量（更多层、更宽层）
2. 训练更多epoch
3. 增加learning rate（仔细）
4. 暂时删除正则化以验证模型是否可以学习
5. 检查您的模型对于任务是否具有足够的表现力

<a id="dead-relu-neurons"></a>

## 死亡 ReLU 神经元

1. 检查每层零激活的比例。 >50%是个问题
2. 切换到 LeakyReLU(0.01) 或 GELU
3. 使用凯明初始化weights
4. 减少learning rate（大的更新可以将神经元推入死区）
5. 在activation functions之前添加批次normalization

<a id="quick-reference-learning-rate-starting-points"></a>

## 快速参考：learning rate 起点

| Optimizer | 任务 | 起始LR |
|-----------|------|------------|
| Adam | 从头开始训练 | 1e-3 |
| Adam | Fine-tuning 预训练 | 1e-5 |
| 新元+动力 | 从头开始训练 | 1e-1 |
| 新元+动力 | Fine-tuning 预训练 | 1e-3 |
| AdamW | Transformer培训 | 3e-4 |

<a id="quick-reference-batch-size-effects"></a>

## 快速参考：batch size 效果

| Batch size | Gradient 噪音 | 内存 | 概括 |
|-----------|---------------|--------|---------------|
| 8-16 | 高（嘈杂） | 低 | 往往更好 |
| 32-64 | 中等 | 中等 | 良好的默认值 |
| 128-256 | 低（平滑） | 高 | 可能需要warmup |
| 512+ | 很低 | 非常高 | 需要 LR 缩放 |

<a id="when-nothing-works"></a>

## 当什么都不起作用的时候

1. 将模型简化为 1 个隐藏层。它学会了吗？
2. 将数据简化为 100 个样本。是否过度拟合？
3. 用 MSE 代替你的损失。它收敛吗？
4. 将您的 optimizer 替换为 SGD(lr=0.01)。它有进步吗？
5. 将您的数据替换为合成数据（例如，y = x[0] > 0）。它学会了吗？
6. 如果这些都不起作用：错误出在您没有查看的代码中（数据加载、预处理、tensor 形状）
