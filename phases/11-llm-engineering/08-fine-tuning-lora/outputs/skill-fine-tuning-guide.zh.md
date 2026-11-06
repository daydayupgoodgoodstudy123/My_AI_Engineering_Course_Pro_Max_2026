---
name: skill-fine-tuning-guide
description: Decision tree for when and how to fine-tune LLMs with LoRA and QLoRA
version: 1.0.0
phase: 11
lesson: 8
tags: [fine-tuning, lora, qlora, peft, llm-engineering]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="fine-tuning-decision-guide"></a>

# Fine-Tuning 决定指南

之前 fine-tuning试试看

```
1. Prompt engineering (minutes, $0)
2. Few-shot examples in prompt (minutes, $0)
3. RAG for knowledge retrieval (days, $10-100/month)
4. Fine-tuning with LoRA/QLoRA (days, $5-50 per experiment)
5. Full fine-tuning (weeks, $100-10,000 per run)
```

只有上一个步骤明显不足时,才能进入下一步。

<a id="when-to-fine-tune"></a>

## 何时微调

- 模型需要一致的输出样式或格式,而提示无法实现
- 你在蒸馏一个更大的模型GPT- 8B模型质量为4)
- 长期性事项和 few-shot 示例添加太多 tokens
- 你需要模型 可靠地遵循复杂的推理模式
- 您有1,000+高质量的例子 来说明您想要的投入-产出行为

<a id="when-not-to-fine-tune"></a>

## 当不微调时

- 模型已经做了你想做的右 prompt
- 你需要模型了解事实(使用) RAG 改为)
- 您的训练案例不足500个( 可能过于适合)
- 任务变化频繁(再培训费用昂贵)
- 您需要审计哪些数据影响特定输出( ) 。fine-tuning 是一个黑盒)

<a id="method-selection"></a>

## 选择方法

| GPU VRAM | 7B 型号 | 13B 型号 | 70B 型号 |
|----------|----------|-----------|-----------|
| 16GB (T4) 国家 | QLoRA | 不可行 | 不可行 |
| 24GB(3090/4090) | QLoRA 或 LoRA | QLoRA | 不可行 |
| 40GB(A100) | LoRA 满 | QLoRA 或 LoRA | QLoRA |
| 80GB(A100/H100) | Full | LoRA 满 | QLoRA 或 LoRA |

<a id="lora-configuration-checklist"></a>

## LoRA 配置核对表

1. 以 r=16, alpha=32 开始( 大多数任务的安全默认)
2. 目标q_第2类和第5类_(最低限度可行) LoRA)
3. 使用 learning rate 2e-4 个 QLoRA, 5e-5 表示 LoRA fp16
4. 设置 Lora_辍学=0.05
5. 1-3个epoch的火车(更多风险) overfitting)
6. 每100个步骤评价一套搁置措施
7. Save checkpoints 并选择最好的 以反射损失

<a id="common-mistakes"></a>

## 常见错误

- 为太多的epoch提供培训overfitting 之后 epoch 2-3小数据集)
- 使用相同的 learning rate 满 fine-tuning (LoRA 需要更高LR)
- 忘记设置垫子 token (因为 NaN B. 损失与 Llama 模型)
- 不冻结基准模型( 破坏 LoRA)
- 仅评价训练数据(在评估中总是有10-20%)
- 跳过 prompt engineering 基线(fine-tuning 引发问题已经解决)

<a id="quality-verification"></a>

## 质量核查

培训后,比较200+的搁置例子:
1. 最佳基础模型 prompt (基线)
2. 基数模型 LoRA 适配器( 您的微调模型)
3. GPT-4个或 Claude 相同 prompt (上限)

如果 : LoRA 模型不跳过提示的基线, 您的训练数据或配置需要工作, 而不是更多计算 。

<a id="adapter-management"></a>

## 适应器管理

- 多任务服务时将适应器分开(按请求抽取适配器)
- 将适配器合并到基底 weights 用于单任务部署
- 在 Hugging Face 枢纽上存储适配器( 10- 100MB, 易于版本和共享)
- 在部署前测试合并的模型产出匹配未合并的产出
- 使用 NYE- Merging 或 DARE 将多个适配器合并成一个

<a id="debugging-training"></a>

## 调试培训

如果损失不减少:
1. Check learning rate (太低 LoRA,尝试2e-4)
2. Verify LoRA 正在实际接收层 gradients
3. 确认基准模型 weights 冻结
4. 检查数据格式(tokenizer 必须匹配模型的预期格式)

如果损失减少,但电子逆向拍卖质量很差:
1. 训练数据质量问题(垃圾处理、垃圾处理)
2. Overfitting (减少epoch,增加) dropout,添加更多数据)
3. 错误的目标模块( 为复杂任务添加 MLP 层)
4. 等级过低(r=32或r=64)
