---
name: prompt-alignment-method-selector
description: Choose the right alignment method (SFT, RLHF, DPO, KTO, ORPO, SimPO) for your use case
version: 1.0.0
phase: 10
lesson: 8
tags: [alignment, dpo, rlhf, kto, orpo, simpo, preference-optimization, fine-tuning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="alignment-method-selector"></a>

# Alignment 方法选择器

为语言模型选择 alignment 方法时，请使用此框架来评估您的数据、计算和质量要求，然后选择最适合您的约束的方法。

<a id="input-requirements"></a>

## 输入要求

提供：
- **基本型号**（例如，Llama 3 8B、Mistral 7B、Qwen 2.5 72B）
- **起点**（基本模型，或者已经是SFT？）
- **可用数据**（指令对、偏好对、不成对的评级或无）
- **计算预算**（GPU小时，GPUs的数量）
- **质量目标**（对于原型来说足够好，与开源竞争，最先进）
- **时间线**（天、周、月）

<a id="decision-matrix"></a>

## 决策矩阵

<a id="quick-selection"></a>

### 快速选择

| 你的情况 | 推荐方法 | 为什么 |
|---------------|-------------------|-----|
| 没有偏好数据，只有指令对 | 仅限SFT | 如果没有偏好信号，你就无法对齐 |
| < 5,000 个偏好对，计算有限 | DPO | 管道更简单，适用于小数据 |
| 不成对的反馈（仅赞成/反对） | 韩国贸易组织 | 唯一无需成对比较即可工作的方法 |
| 希望在一次训练中获得 alignment | 奥尔普 | 组合 SFT + alignment，无参考模型 |
| 内存受限（无法适合参考模型） | 模拟PO | 无需参考模型 |
| 大规模、多目标 alignment | RLHF (PPO) | 单独的 reward model 捕获复杂的偏好 |
| 用在线数据迭代alignment | RLHF (PPO) | 可以循环生成、评分和重新训练 |
| 后RLHF细化 | DPO | 根据目标偏好微调 RLHF 模型 |

<a id="detailed-comparison"></a>

### 详细比较

| 方法 | 数据要求 | 内存中的模型 | 训练循环 | 稳定性 | 最佳规模 |
|--------|-----------------|-----------------|----------------|-----------|------------|
| SFT | 指令对 (10K+) | 1 | 1 | 高 | 任意 |
| RLHF | 偏好对 (20K+) | 3-4 | 3 | 低 | 大号（70B+） |
| DPO | 偏好对 (5K+) | 2 | 2 (SFT + DPO) | 高 | 小型-中型 (7B-70B) |
| 韩国贸易组织 | 未配对收视率 (5K+) | 2 | 2 (SFT + KTO) | 高 | 任意 |
| 奥尔普 | 偏好对 (10K+) | 1 | 1 | 高 | 中小型 |
| 模拟PO | 偏好对 (5K+) | 1 | 2（SFT + SimPO） | 高 | 中小型 |

<a id="method-specific-configuration"></a>

## 方法特定的配置

<a id="sft"></a>

### SFT

- **何时停止**：1-3个epoch后或验证损失停止减少时
- **Key hyperparameter**：Learning rate（1e-5 至 5e-5，较大型号较低）
- **关键细节**：丢失中的掩码指令tokens
- **Gotcha**：超过3个epoch导致记忆；混合 2-5% 的预训练数据

<a id="rlhf-ppo"></a>

### RLHF (PPO)

- **何时使用**：您有20K+个比较对，需要多目标alignment，或者想要迭代在线学习
- **Key hyperparameters**：KL系数（0.01-0.05）、PPO削波比（0.1-0.3）、learning rate（5e-6至3e-5）
- **关键细节**：Reward model 应该 >= 策略模型大小
- **Gotcha**：PPO 不稳定；持续监控 KL 散度和奖励曲线

<a id="dpo"></a>

### DPO

- **何时使用**：您有偏好对并且想要比 RLHF 更简单的管道
- **Key hyperparameter**：Beta（0.1-0.5；较低 = 允许偏离参考值更大）
- **关键细节**：参考模型必须是SFT checkpoint的冻结副本
- **Gotcha**：对 beta 非常敏感；扫描 [0.05, 0.1, 0.2, 0.5]

<a id="kto"></a>

### 韩国贸易组织

- **何时使用**：您只有“好”或“坏”标签，没有成对比较
- **Key hyperparameter**：Beta（与 DPO 相同），损失厌恶乘数（不良响应为 1.5 倍）
- **关键细节**：需要大致平衡的好/坏示例（40-60％分割）
- **Gotcha**：没有配对时，gradient信号较弱；可能需要比 DPO 更多的数据

<a id="orpo"></a>

### 奥尔普

- **何时使用**：您想要完全跳过SFT并直接从基础到对齐
- **Key hyperparameter**：Lambda（优先项的 weight 与 SFT 项）
- **关键细节**：在一个数据集中需要指令标签和偏好对
- **Gotcha**：组合目标可能很难平衡；如果 SFT 损失占主导地位，则 alignment 较弱

<a id="simpo"></a>

### 模拟PO

- **何时使用**：无法保存参考模型的内存受限设置
- **Key hyperparameter**：Beta、gamma（长度normalization指数）
- **关键细节**：长度normalization阻止模型偏向于短响应
- **Gotcha**：没有参考模型锚点，模型可以漂移得更远；仔细监控

<a id="pipeline-templates"></a>

## 管道模板

<a id="template-1-fast-prototype-1-2-days"></a>

### 模板 1：快速原型（1-2 天）

```
Base Model -> SFT (1 epoch, 10K examples) -> DPO (3 epochs, 5K pairs)
```

计算：A100 上的 7B 型号约 4 GPU 小时
质量：固体instruction following，基本偏好alignment

<a id="template-2-production-quality-1-2-weeks"></a>

### 模板 2：生产质量（1-2 周）

```
Base Model -> SFT (2 epochs, 50K examples) -> DPO (5 epochs, 20K pairs) -> Eval -> Iterate
```

计算：7B 约 40 GPU 小时，70B 约 200 GPU 小时
质量：与开源RLHF模型竞争

<a id="template-3-state-of-the-art-1-3-months"></a>

### 模板 3：最先进的（1-3 个月）

```
Base Model -> SFT (2 epochs, 100K+ examples) -> RLHF (PPO, 50K+ pairs) -> DPO (targeted refinement) -> Eval -> Iterate
```

计算：70B 约 500+ GPU 小时
品质：接近前沿型号alignment

<a id="template-4-minimal-data-1-2-days"></a>

### 模板 4：最少数据（1-2 天）

```
Base Model -> SFT (1 epoch, 5K examples) -> KTO (unpaired thumbs up/down from users)
```

计算：7B 约 2 GPU 小时
质量：优于 SFT-only，数据收集开销最小

<a id="evaluation-protocol"></a>

## Evaluation协议

在 alignment 之后，跨以下维度进行评估：

1. **优先获胜率**：在 200 多个测试 prompts 上与人类评委比较对齐模型与 SFT 模型。目标：> 60% 胜率。
2. **基准保留**：MMLU、HumanEval 或特定于域的基准。与 SFT 基线相比不应下降 > 5%。
3. **MT-Bench 或 AlpacaEval**：标准 alignment 质量基准。与已发布的基线进行比较。
4. **安全 evaluation**：针对对抗性 prompts、jailbreaks 和有害请求类别进行测试。
5. **响应多样性**：测量 100 个 prompts 的响应熵。低熵=模式崩溃。

<a id="common-failure-modes"></a>

## 常见故障模式

| 症状 | 原因 | 特定于方法的修复 |
|---------|-------|-------------------|
| 冗长、填充的响应 | Reward model / 隐式奖励有利于长度 | DPO：增加beta。 RLHF：添加长度惩罚。 SimPO：调整伽玛。 |
| 模型与一切都一致 | 偏好数据偏差的阿谀奉承 | 添加正确响应与用户不一致的偏好对 |
| 拒绝善意的请求 | Over-alignment 安全数据 | 降低安全示例比例,增加更多的良性对子 |
| 产出几乎相同 SFT | 贝塔太高了DPO/KTO)或KL系数过高(PPO) | 降低贝塔/ KL 系数; 模型没有学习 |
| 训练损失 | Learning rate 数据太高或不足 | 将 lr 减少 2-3x; 增加偏好数据 |
