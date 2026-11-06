---
name: prompt-reward-model-designer
description: Design reward model training pipelines for RLHF alignment
version: 1.0.0
phase: 10
lesson: 7
tags: [rlhf, reward-model, ppo, alignment, human-feedback, preference-learning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="reward-model-designer"></a>

# Reward Model设计师

当构建 RLHF 管道以使语言模型与目标行为（有用性、编码能力、安全性、诚实）保持一致时，使用此框架来设计数据收集协议、训练 reward model 并配置 PPO。

<a id="input-requirements"></a>

## 输入要求

提供：
- **目标行为**（例如“乐于助人且无害的助手”、“专家Python编码器”、“安全医疗问答”）
- **基本模型**（例如，SFT、Mistral 7B聊天后的Llama 3 8B）
- **Reward model 尺寸**（通常与保单模型尺寸相同或更大）
- **注释预算**（可用人力小时或比较对）
- **计算预算**（reward model培训的GPU小时+PPO）

<a id="step-1-preference-data-collection"></a>

## 第 1 步：偏好数据收集

<a id="annotation-protocol"></a>

### 注释协议

1. **Prompt选择**：来自SFT训练分布的样本加上分布外的prompts（10-20%新颖）
2. **响应生成**：使用具有不同temperatures（0.3、0.7、1.0）的SFT模型为每个prompt生成2-4个响应
3. **比较格式**：准确地向注释者显示2个响应并询问“哪个响应更好？”
4. **Criteria rubric**：定义“更好”对您的用例意味着什么

<a id="rubric-template"></a>

### 标题模板

| 标准 | Weight | 描述 |
|-----------|--------|-------------|
| 乐于助人 | 40% | 它是否完整、正确地回答了问题？ |
| 无害化 | 25% | 它是否避免有害、有偏见或误导性的内容？ |
| 诚实 | 20% | 它是否承认不确定性而不是幻觉？ |
| 简洁 | 15% | 回答的长度对于问题来说是否合适？ |

根据您的用例调整 weights。编码助理可能会 weight 正确性为 60%，简洁性为 20%。

<a id="data-size-guidelines"></a>

### 数据大小指南

| 规模 | 比较对数 | 注释者时间 | 预期 RM 准确度 |
|-------|-----------------|-----------------|---------------------|
| 最低可行 | 5,000-10,000 | 400-800 | 60-65% |
| 生产版 v1 | 20,000-50,000 | 1,600-4,000 | 65-72% |
| 生产版 v2 | 100,000-500,000 | 8,000-40,000 | 72-78% |

InstructGPT 使用了来自 40 个承包商的 33,000 次比较。 Anthropic 的初始论文使用了来自 20 个注释者的 22,000 个注释。注释者间的一致性通常为 70-75%——reward model 不能超过人类一致性水平。

<a id="quality-control"></a>

### 质量控制

- **协议过滤**：丢弃少于70％的注释者同意的对
- **Annotator calibration**：在真正注释之前使用已知良好对运行 calibration 轮
- **偏差检测**：监视注释者是否始终喜欢较长的响应、正式语言或特定模式
- **对抗性示例**：包括 5-10% 的示例，旨在捕获不仔细阅读的注释者

<a id="step-2-reward-model-architecture"></a>

## 步骤2：Reward Model架构

<a id="architecture-decisions"></a>

### 架构决策

| 决定 | 推荐 | 基本原理 |
|----------|---------------|-----------|
| 基础架构 | 与策略相同transformer | Weight 来自 SFT checkpoint 的初始化给出了强有力的启动 features |
| 输出头 | 来自最后一个隐藏状态的单个线性投影 | 来自最完整位置表示的标量奖励 |
| 型号尺寸 | >= 策略模型大小 | 较小的 RM 产生不可靠的信号，导致不稳定 PPO |
| 初始化 | SFT checkpoint 带新输出头 | 已预训练 features 捕获语言质量 |

<a id="training-configuration"></a>

### 训练配置

| Parameter | 范围 | 注释 |
|-----------|-------|-------|
| Learning rate | 1e-5 至 5e-5 | 低于 SFT 因为任务更简单 |
| epoch | 1-3 | Overfitting 是重大风险，对比数据有限 |
| Batch size | 64-256 | 每个“例子”都是一对，所以有效数据是2x |
| Loss function | 布拉德利-特里：-log（sigmoid（r_首选 - r_拒绝）） | 成对比较标准 |
| 验证分割 | 10-20% | 监控保留对的准确性 |

<a id="evaluation-metrics"></a>

### Evaluation 指标

1. **成对准确度**：RM 正确排名的保留偏好对的比例是多少？目标：> 65%
2. **保证金分布**：绘制（r_preferred - r_rejected）的分布。应以 0 以上为中心，且负值很少。
3. **Calibration**：sigmoid(r_preferred - r_rejected)是否接近人类实际偏好概率？
4. **OOD 泛化**：在来自与训练不同的分布的 prompts 上进行测试。准确度应下降 < 10%。

<a id="step-3-ppo-configuration"></a>

## 步骤3：PPO配置

<a id="hyperparameters"></a>

### Hyperparameters

| Parameter | 典型值 | 过高的影响 | 太低的影响 |
|-----------|--------------|-------------------------|------------------------|
| KL系数（β） | 0.01-0.05 | 模型几乎没有学习，与 SFT 太接近 | 奖励黑客行为，退化输出 |
| Learning rate | 5e-6 至 3e-5 | 训练不稳定、发散 | 收敛速度慢，计算浪费 |
| 削波比（epsilon） | 0.1-0.3 | 可能会造成不稳定的大型更新 | 更新非常保守，学习缓慢 |
| PPO 每批次 epoch | 1-4 | Overfitting 至当前批次 | 每批次利用率不足 |
| 代batch size | 128-512 | 内存问题 | 吵闹的gradient估计 |
| 最大响应长度 | 256-1024 | 生成缓慢，内存问题 | 截断有用的响应 |

<a id="monitoring-dashboard"></a>

### 监控仪表板

在 PPO 训练期间跟踪这些指标：

1. **平均奖励**：应该增加训练。高原还好；减少意味着不稳定。
2. **KL 分歧**：应保持在 10-20 纳特以下。尖峰=奖励黑客行为。
3. **响应长度**：应该保持稳定。单调增加=冗长奖励黑客行为。
4. **Entropy**：Token 分布熵应该缓慢减少。快速下降=模式崩溃。
5. **Reward model协议**：用reward model对PPO响应进行评分；协议应该有所改善。

<a id="red-flags-during-ppo"></a>

### PPO 期间的危险信号

| 症状 | 可能的原因 | 修复 |
|---------|-------------|-----|
| 奖励增加但产出下降 | 奖励黑客行为 | 增加 KL 系数，在对抗性示例上重新训练 RM |
| KL 背离爆炸 | Learning rate太高或KL系数太低 | 减少lr，增加beta |
| 响应长度单调增长 | RM 奖励冗长 | 添加长度惩罚奖励，用长度控制对重新训练 RM |
| 所有响应都变得相同 | 模式崩溃 | 增加世代temperature，减少PPO epochs |
| 奖励剧烈波动 | PPO 不稳定 | 减少learning rate，增加削波比 |

<a id="step-4-end-to-end-validation"></a>

## 第 4 步：端到端验证

在部署 RLHF 训练的模型之前：

1. **A/B 测试与 SFT**：在 200 多个测试 prompts 上运行 SFT 和 RLHF 模型。让 3 名以上评估者比较回复。 RLHF 模型应该在 > 60% 的情况下获胜。
2. **安全 evaluation**：对已知对抗性 prompts 进行测试（jailbreaks，有害请求）。 RLHF型号应适当拒绝。
3. **回归检查**：运行标准基准测试（MMLU、HumanEval、MT-Bench）以确认RLHF模型没有丢失核心功能。
4. **忘记检查**：在通用文本语料库上测量perplexity。与 SFT 模型相比，增加应小于 10%。
5. **长度分析**：比较SFT和RLHF模型之间的平均响应长度。如果 RLHF 的长度 > 50%，则 reward model 可能存在详细程度偏差。
