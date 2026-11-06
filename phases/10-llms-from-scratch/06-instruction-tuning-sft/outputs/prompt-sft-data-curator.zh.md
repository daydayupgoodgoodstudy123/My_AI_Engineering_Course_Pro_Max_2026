---
name: prompt-sft-data-curator
description: Design and curate instruction datasets for supervised fine-tuning
version: 1.0.0
phase: 10
lesson: 6
tags: [sft, instruction-tuning, fine-tuning, data-curation, alignment]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="sft-data-curator"></a>

# SFT 数据管理员

在为特定功能（代码生成、数学、对话、安全）设计指令调整数据集时，请使用此框架来规划数据收集、定义质量标准并构建训练管道。

<a id="input-requirements"></a>

## 输入要求

提供：
- **目标能力**（例如“Python代码生成”、“医疗问答”、“多轮对话”）
- **基本型号**（例如，Llama 3 8B、Mistral 7B、Qwen 2.5 72B）
- **Budget**（注释小时，API合成生成成本）
- **格式偏好**（Alpaca、ShareGPT、ChatML）

<a id="step-1-dataset-design"></a>

## 第 1 步：数据集设计

<a id="size-guidelines"></a>

### 尺寸指南

| 质量等级 | 需要的例子 | 预期成果 |
|--------------|----------------|------------------|
| 研究原型机 | 1,000-5,000 | LIMA 质量：如果示例是专家编写的，则可与更大的数据集相媲美 |
| 生产版 v1 | 10,000-50,000 | 斯坦福羊驼级别：在常见任务中扎实的 instruction following |
| 生产版 v2 | 50,000-200,000 | Vicuna/Llama 2 聊天级别：稳健的多轮、域覆盖 |

质量永远胜过数量。 1,000 个专家编写的示例（LIMA，2023 年 5 月）与在 50,000 多个示例上训练的模型相匹配。优先考虑：

1. **Diversity**——覆盖全方位目标能力
2. **Accuracy** -- 每个响应都必须真实正确
3. **Clarity** -- 回复应该简洁且结构良好
4. **难度 gradient** -- 包括简单、中等和困难示例

<a id="diversity-checklist"></a>

### 多样性清单

对于通用助理：
- 开放式问题 (20%)
- 事实问答 (20%)
- 创意写作（10%）
- 代码生成 (15%)
- 推理和数学 (15%)
- 总结（10%）
- Instruction following 有约束 (10%)

调整特定领域模型的百分比。编码助理可能会分配 60% 的时间用于代码生成，20% 的时间用于代码解释。

<a id="step-2-data-format"></a>

## 第2步：数据格式

<a id="alpaca-format-single-turn"></a>

### 羊驼毛格式（单圈）

```json
{
  "instruction": "Write a function that reverses a string in Python.",
  "input": "",
  "output": "def reverse_string(s):\n    return s[::-1]"
}
```

使用场合：单轮任务、简单的指令-响应对、快速原型设计。

<a id="sharegpt-format-multi-turn"></a>

### ShareGPT 格式（多轮）

```json
{
  "conversations": [
    {"from": "system", "value": "You are a Python expert."},
    {"from": "human", "value": "How do I reverse a string?"},
    {"from": "gpt", "value": "Use slicing: s[::-1]"},
    {"from": "human", "value": "What about for a list?"},
    {"from": "gpt", "value": "Same syntax works: my_list[::-1]"}
  ]
}
```

使用时机：会话式应用程序，多轮上下文很重要。

<a id="chatml-format-with-special-tokens"></a>

### ChatML 格式（带有特殊 tokens）

```
<|im_start|>system
You are a Python expert.<|im_end|>
<|im_start|>user
How do I reverse a string?<|im_end|>
<|im_start|>assistant
Use slicing: s[::-1]<|im_end|>
```

使用时间：定位原生使用 ChatML 的模型（Qwen，Yi）。

<a id="step-3-quality-criteria"></a>

## 第 3 步：质量标准

<a id="per-example-checks"></a>

### 每个示例检查

1. **响应相关性**：响应实际上回答了指令吗？
2. **事实准确性**：所有声明都可验证且正确吗？
3. **完整性**：响应是否完全寻址指令？
4. **简洁**：同样的信息能否用更少的文字来传达？
5. **格式一致性**：响应是否遵循预期的风格？

<a id="red-flags-reject-the-example"></a>

### 危险信号（拒绝该示例）

- 回应自相矛盾
- 回应包含有害内容，无需拒绝
- 回应幻觉事实或引文
- 指令不明确且响应不明确
- 响应是改写的指令的副本

<a id="dataset-level-checks"></a>

### 数据集级检查

- 来自任何单一来源/模板的示例不超过 5%
- 至少 80% 的响应 tokens 是有意义的（不是填充符）
- 平均响应长度为 50-200 tokens（避免太短或太长）
- System prompt多样性：至少代表10个不同的system prompts

<a id="step-4-training-configuration"></a>

## 第4步：训练配置

| Parameter | 推荐范围 | 注释 |
|-----------|------------------|-------|
| Learning rate | 1e-5 至 5e-5 | 较大型号的较低（70B 为 1e-5，7B 为 5e-5） |
| epoch | 1-3 | 监控验证损失，在出现增加迹象时停止 |
| Batch size | 32-128 | 如果 GPU 受限，则使用 gradient accumulation 进行扩展 |
| Warmup | 步数的 0-5% | 不如预训练那么重要 |
| Weight decay | 0.0-0.1 | 短期运行可选 fine-tuning |
| 损失掩蔽 | 仅响应 tokens | 掩码指令和 system prompt tokens |
| 预训练数据混合 | 2-5% | 混合原始文本以防止灾难性遗忘 |

<a id="step-5-evaluation-protocol"></a>

## 步骤5：Evaluation协议

训练后，评估：

1. **Instruction following 比率**：模型产生相关、完整响应的测试 prompts 的百分比
2. **遗忘分数**：与基本模型相比，在保留的一般文本语料库上的Perplexity
3. **格式合规性**：遵循预期聊天格式的响应百分比
4. **MT-Bench 或 AlpacaEval**：指令调整模型的标准基准
5. **特定于域的评估**：针对您的目标功能自定义 evaluation

<a id="warning-signs"></a>

### 警告标志

- epoch 1后验证损失增加：你是overfitting，减少epochs或增加数据
- 遗忘分数增加 > 15%：learning rate 太高或太多 epoch
- 模型逐字重现训练示例：严重的overfitting，需要更多样化的数据
- 模型拒绝良性指令：对安全数据进行过度训练，重新平衡数据集
