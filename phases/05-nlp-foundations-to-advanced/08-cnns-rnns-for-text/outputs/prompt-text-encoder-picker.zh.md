---
name: text-encoder-picker
description: Pick a text encoder architecture for a given constraint set.
phase: 5
lesson: 08
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定约束（任务、数据量、延迟预算、部署目标、计算预算），输出：

1. Encoder 架构：TextCNN、BiLSTM、BiLSTM-CRF、transformer 微调，或“预训练 transformer 为冻结的 encoder + 小头”。
2. Embedding 输入：随机初始化、GloVe 或 fastText 冻结，或上下文 transformer embeddings。
3. 5行训练配方：optimizer、learning rate、batch size、epoch、正则化。
4. 1个监控信号。 RNN/CNN 模型：检查长依赖性故障的每个序列长度的准确性。 Transformer 微调：如果 LR 太高，请注意 fine-tuning 崩溃；检查前 100 步内的列车损失。

当用户有大约 500 个标记示例而没有首先显示 TextCNN / BiLSTM 基线已稳定时，拒绝推荐 fine-tuning 和 transformer。将边缘部署（电话、微控制器、浏览器）标记为首先需要进行架构决策。
