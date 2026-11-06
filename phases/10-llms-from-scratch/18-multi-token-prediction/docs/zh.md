<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="multi-token-prediction-mtp"></a>

# Multi-Token 预测（MTP）

> 每个 autoregressive LLM 来自 GPT- 2个到 Llama 3辆火车每个位置损失1次:预测下一个 token. DeepSeek-V3 在每个位置上增加了第二个损失:预测 token 之后 额外的14B parameters (在671B模型上) 被蒸馏回主模型 通过 gradient 并且经过培训的MTP负责人在 inference 作为具有 80 %+ 接受的投机解码起草者。 1. 8x 生成量是免费的。 此课程从 $80 中构建了连续的 MTP 模块 。 DeepSeek 技术报告,计算损失和共有头 parameter 并解释为什么MTP保留因果关系链 而Gloeckle等人的原始平行MTP打破了它

**类型:** Build
**语言:** Python (斯迪利布)
**先修要求:** 阶段10 · 04(培训前一小笔) GPT第10阶段 15(a)speculative decoding)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 说明MTP的培训目标,并得出跨预测深度的共同损失。
- 解释Gloeckle等人的平行MTP(2024年)和 DeepSeek-V3的相继 MTP 模块和为什么序列设计保存因果链。
- 计算 parameter 以及将MTP模块添加到训练前运行的记忆管理。
- 从头执行一个MTP模块:共享 embedding,即直线 transformer 区块、投影和共享输出头。

<a id="the-problem"></a>

## 问题

Next-token 预测是标准 LLM 每一个隐蔽的国家都受到监督 来精确地预测一件事: token。这是一个令人惊讶的薄弱信号。大多数信息在顺序上超越一个 token 结构、一致性、事实质量、算术流。token 超过万亿的信号 tokens.

MTP问:如果每一个隐藏的国家都受到监督,以预测多重未来会怎样? tokens Gloeckle等人(Meta, 2024)表明了这一点。 它们的实施将几个独立的输出头放在骨干顶端,每个头预测不同的偏移。 平行的、简单的,但头部看到的是相同的隐藏状态,没有等级上的细化 — — 而预测并没有因果地连结,所以无法用于 speculative decoding.

DeepSeek-V3 (2024年12月)重新设计MTP作为连续模块,使因果链保持每个预测深度。 `t+1` 来自 `h_i^(0)`,然后预测 `t+2` 从新的隐藏状态中 `h_i^(1)` 合并后 `h_i^(0)` 与 `E(t+1)` embedding每个深度都是它自己的小 transformer 区块。 embedding 和共享输出头保存 parameter 平坦的顶部 DeepSeek-V3的尺码,14B额外 parameters 在671B主要模型之上跨MTP模块 weights2%的高压购买了更密集的培训信号 和在 inference.

此课程构建了一个单一的 MTP 模块和 D 深度从零到零损失。 数学是整齐的。 执行为150行 。

<a id="the-concept"></a>

## 概念

<a id="the-sequential-mtp-recipe"></a>

### 相继的 MTP 配方

DeepSeek- V3 添加 `D` 主模型之上的MTP模块。 `k` (用于 `k = 1..D`预测 token 在深度 `k` - 也就是说, `t_{i+k}` 通过位置给定前缀 `i`.

Module `k` 包括:

- 一个 transformer block `T_k` 与它自己的 attention 和MLP。
- 预测矩阵 `M_k` 将先前的深度隐藏状态与 embedding 下一个深入的地面实况报告 token.
- 共享 embedding `E` (与主要模式相同)。
- 共享输出头 `Out` (与主要模式相同)。

训练时,前缀通过位置 `i`, 深度隐藏状态是:

```
h_i^(0) = main model backbone at position i
h_i^(k) = T_k( M_k * concat(RMSNorm(h_i^(k-1)), RMSNorm(E(t_{i+k}))) )   for k >= 1
```

准确预测如下:

```
logits_{i+k} = Out(h_i^(k-1))   for k = 1..D
```

每一深度的损失是 cross-entropy 反地面真相组织 `t_{i+k}`:

```
L_k = CE(logits_{i+k}, t_{i+k})
```

共同损失的深度:

```
L_MTP = (lambda / D) * sum_{k=1..D} L_k
```

`lambda` 是一个小的权重因素—— DeepSeek- V3在训练的前10%和之后分别使用0.3%和0.1。 `L_main + L_MTP`.

<a id="why-sequential-not-parallel"></a>

### 为何相继, 而不是平行

Gloeckle 的原始平行 MTP 具有 D 输出头, 每个直接应用到 `h_i^(0)`。每个头都预测 `t_{i+k}` 这列火车很好,但预测并不是互相制约的。你不能使用 `head_1`用于帮助输出 `head_2` - 头部平行着火

DeepSeek-V3的相继设计 `h_i^(k)` 来自 `h_i^(k-1)` 加上实际的下一个...token embedding `E(t_{i+k})`。这保留了因果链:预测 `t_{i+k+1}`,该模块在深度上 `k+1` 看见什么了 `t_{i+k}`。这在结构上与 autoregressive decoder 消耗自己的产出——使MTP模块直接用作投机性解码起草者。

在 inference:喂养 `h_i^(k-1)` 和起草的 `t_{i+k}` 进入模块 `k+1`,得到一个预测 `t_{i+k+1}`重复。这完全是EAGLE式的草稿,使用训练有素的MTP模块作为网络草稿。 DeepSeek-V3报告第一个MTP模块接受80 和~1.8x加速。

<a id="parameter-accounting"></a>

### Parameter accounting

对于一个隐藏的模型 `h` 和 vocabulary `V`:

- 主要模式:10亿 parameters,加上一个输出头大小 `V * h`.
- 共享输出头: 重新使用主模型头。 没有额外参数 。
- Shared embedding:重新使用主要模型 embedding没有附加参数 。
- 每兆字节模式 :
  - Projection `M_k`: `(2h) * h = 2h^2`.
  - Transformer block `T_k`: attention (`4h^2` 和MLP(通常为MHA) `8h^2` 用于 SwiGLU 比率为8/3。 `12h^2` 每个街区。

每个模块的额外总计 : `~14h^2`. 用于 DeepSeek- V3 号 `h = 7168`D = 1个模块: `~14 * 7168^2 = ~720M` parameters 写在纸上 DeepSeek-V3报告14B——差别主要在于专家层面 MoE 在MTP模块中也是如此。

<a id="the-speculative-decoding-payoff"></a>

### 投机-解码收益

在培训前阶段,MTP模块使培训慢了大约10%(更远的计算、额外损失)。

1. Denser 培训信号。 每个隐藏状态都看到 D+1 监督目标。 MMLU、 GSM8K、 MATH、 HumanEval 的测量效果: 在 DeepSeek- V3是血迹

2. Free speculative decoding 草稿 inference。MTP模块已经接受了培训,以预测接下来的少数 tokens。重命名为网络草案,它提供80 %+接受率。在该级别上,N=3或N=5的代码解码给出1.8x输送量。10%的培训时间费用在您第一次运行时就得到回报 inference.

<a id="relation-to-eagle"></a>

### 与 EAGLE 的关系

EAGLE在预培训后对小型模型进行了培训。 MTP将预培训作为预培训内容。 两种方法在类似的接受率上趋于一致,但通过不同的管道:

| 尺寸 | EAGLE-3 | MTPDeepSeek-V3 级 |
|-----------|---------|------------------|
| 培训时 | Post-pre-training | 预培训期间 |
| 与现有 weights | 是的 | 否(需要再培训) |
| 条款草案 | 1-2 transformer layers | 1 transformer 区块+投影 |
| 录取率 | 0.88-0.92 | 深度1时0.80+ |
| 超过速度的效益 | Speculative decoding 仅 | 密度训练信号+加速 |

```figure
multi-token-predict
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 建立一个结束的单一MTP模块:共享 embedding预测, transformer 区块, 共享输出头。 然后它计算每个深度 cross-entropy 短合成序列损失并打印 parameter 按组件计数。 A 玩具 vocabulary 第32条 tokens 保持数字可读性。

<a id="step-1-shared-embedding-table"></a>

### 步骤1:共享 embedding table

单 `vocab_size x hidden` 表格由主模型和每个MTP模块在每一深度使用。 tensor.

<a id="step-2-the-per-depth-combination"></a>

### 第2步: 深度组合

```python
def combine(prev_hidden, next_token_embed, M_k):
    # concat along feature dim, then project down to hidden
    concat = rms_norm(prev_hidden) + rms_norm(next_token_embed)  # vector addition stand-in
    projected = matvec(M_k, concat)
    return projected
```

Real DeepSeek-V3 将两个RMSNormed矢量与 `[2h]` 和项目,包括 `h x 2h` 矩阵。 玩具使用矢量添加用于 stdlib brevity 。

<a id="step-3-the-transformer-block-at-depth-k"></a>

### 步骤3: transformer 深度时的块 k

Self-attention 外加 MLP. 在玩具中, 一层线性 attention 块和 SwiGLU MLP 保持结构可见, 没有 numpy.

<a id="step-4-the-shared-output-head"></a>

### 第4步:共享输出头

重新使用主模型的输出投影 。 Logits 过 vocabulary.

<a id="step-5-per-depth-loss"></a>

### 第5步:每笔损失

Cross-entropy 的 softmax(logits)反对地面真相 token 页:1 `k`。 `lambda / D` 缩放系数。

<a id="step-6-parameter-accounting"></a>

### 步骤6: parameter accounting

打印总计 parameter 计数, 共享 (embedding,头)数,以及每个模块的额外数。显示磁盘与主模型的比重。

<a id="use-it"></a>

## 实际应用

MTP纳入 DeepSeek- V3 (2024年12月)和 DeepSeek-R1系列 inference:

- DeepSeek自己的服务堆叠消耗了MTP模块作为推测 decoders 从盒子里出来
- vLLM 和 SGLang 具有整合路径 DeepSeek- 到2026年4月为止的V3MTP
- AMD 的 ROCM 记录器 SGLang 教程显示特定的 MTP 投机解码配置, V3 上测量到1.8x加速 checkpoint.

在新的训练前运行中使用 MTP 的时间 :

- 你控制整个训练前的管道 并想要银行 更密集训练信号。
- 你知道你会为模型服务 规模和想要 speculative decoding 免费。
- 你隐藏的大小至少4096。 1B 级时, 间接损失比收益要重 。

当不:

- Fine-tuning 现有训练前的密集型号。 MTP 模块没有经过培训。
- 研究模型,您想要一个干净的基线来比较。MTP会改变建筑。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-mtp-planner.md`。根据训练前运行规格(模型大小、数据、计算),它返回一个整合MTP的计划:深度数D, `lambda` 计划, 记忆管理, inference- 时间推测解码线路。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。随着合成信号的增强,显示每深度损失将单声道下降。修改合成以使用固定模式,并核实深度1和深度2损失的汇合。

2. 计算 parameter D=1 MTP 模块的密度70B型(隐藏 8192,80 层)的顶部。 DeepSeek- V3报告14B的间接费用。 DeepSeek数字更高: MTP transformer 区块继承相同 MoE 结构, 向每个模块充气 parameter 计数

3. 在玩具中执行 D=2: 添加第二个MTP模块, 需要 h^(1) 和预测 `t_{i+2}`核实合并损失 parameter 会计与 DeepSeek 纸的方程式是19 -21

4. 将玩具切换为平行的 MTP (Gloeckle- stype): 在主隐藏状态顶部添加 D 输出头, 每个都预测不同的偏移 。 测量每深度损失如何与同一合成信号上的相继版本相比较 。 相继版本应产生 k > 1 的低深度- k 损失, 因为它以中间预测为条件 。

5. 使用经过培训的 MTP 模块作为 EAGLE 式的草稿: 调用模块 k 来提议 `t_{i+k}` 在 inference衡量这些草案的接受率 tokens 相对于主模型对悬停序列的预测。 如果您在玩具上击中了 50 %+, 您复制了经验性 MTP 原样属性 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| MTP 模块 | "超损失区块" | 一点点 transformer 区块加预测 token `k` 主要模式之前的位置 |
| 预测深度 | "哪一个抵消" | 整数 `k` 这样的模块 `k` 预测 `t_{i+k}` 从前缀到位置 `i` |
| 平行MTP | "格洛克式" | D 独立头在同一个骨干隐藏状态,没有条件链 |
| 顺序 MTP | "DeepSeek-V3风格" | 每个模块的条件 在前一个深度的隐藏状态加上下一个 token的 embedding; 保存因果链 |
| 共享输出头 | "重用主头" | MTP模块称主模型 LM 头, 而不是单独的输出投影 |
| Shared embedding | "重用主桌" | Same vocabulary embedding 表格无处不在;无重复 parameters |
| 预测矩阵M_k | "隐藏的 + 下一个 -token" | 一个 `h x 2h` 折叠上一个隐藏状态和目标的线性层 --token embedding 进入下一个深度的输入 |
| 合并损失L_MTP | (预期额外损失) | 深度的自学平均值 cross-entropy 损失,按 `lambda` |
| 深度1的接受率 | "MTP的草稿多好" | D=1 MTP 模块上一号预测的速率等于主模型上一号预测的速率; DeepSeek- V3 电磁波 |
| 兰巴达体重 | "超值重要性" | 深度缩放因数;培训开始时0.3,以后0.1 DeepSeek- V3 电磁波 |

<a id="further-reading"></a>

## 进一步阅读

- [DeepSeek- 亚历克斯 DeepSeek-V3技术报告(arXiv:2412.19437)](https://arxiv.org/abs/2412.19437) - 全面连续的MTP说明(第2.2节),包括合并损失方程式和在1990年代的1.8x加速 inference
- [Gloeckle等人——通过多语种改进和加快大语言模式token 预测(arXiv:2404.19737)](https://arxiv.org/abs/2404.19737) 平行的MTP基线 DeepSeek设计改进
- [DeepSeek- V3 电磁波 model card 抱住脸](https://huggingface.co/deepseek-ai/DeepSeek-V3) - 总共685B(671B主要+14BMTP),部署说明
- [利维坦等人——快速 Inference 来自 Transformers 通过 Speculative Decoding (arXiv:2211.17192) (单位:千美元)](https://arxiv.org/abs/2211.17192) MTP的投机性解码框架符合
- [Li等人-EAGLE-3(arXiv:2503.01840)](https://arxiv.org/abs/2503.01840) EAGLE的2025年建筑草案,对应的MTP与
