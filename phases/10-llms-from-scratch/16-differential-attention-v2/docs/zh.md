<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="differential-attention-v2"></a>

# Differential Attention（V2）

> Softmax attention 使每个不匹配的概率小化 token超过100公里 tokens 噪音加起来 并淹没了信号。 Transformer (Ye等人,《2025年国际法案例汇编》)通过计算加以修正 attention 两者之差 softmaxes,减去共同噪音层。DIFF V2(微软,2026年1月)是生产堆叠的重写:匹配脱钩到基线 Transformer没有定制的内核, FlashAttention- 兼容。 此课是 V1 到 V2 端到端, 使用工作玩具执行您可以在 Stdlib 中运行的差异操作 Python.

**类型:** Build
**语言:** Python (斯迪利布)
**先修要求:** 阶段7 · 02(self-attention第7阶段 15(a)attention 第10阶段 · 14(建筑横穿)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 确切地说为什么 softmax attention 有个噪音层,为什么它会随着上下文长度而增长。
- 产生差数 attention 公式,并解释为何减法在保存信号的同时取消共享噪音组件。
- 沿着V1到V2的距离走:什么更快,什么更简单,什么更稳定,为什么每次变化都对生产前训练是必要的。
- 实施差异 attention 纯净地从零开始 Python 在合成信号加噪声查询中,从经验上核实噪音取消特性。

<a id="the-problem"></a>

## 问题

Standard softmax attention 具有一个数学属性,该属性在比例上变成操作性头痛。对于查询 `q`, 该 attention weights 是 `softmax(qK^T / sqrt(d))`. Softmax 永远不能产生精确的零——每个非匹配 token 获得一些正质量。剩余质量是噪音,且与上下文长度相乘。 值为 128 k tokens,即使每次不匹配 token 只有0.001%的概率,其中127,999人合起来占总量的12%。模型必须学会绕着随上下文增长的噪音层走下去。

这很正常 attention- 头部干扰:幻觉引用长语 RAG中途失灵的100公里...token 回收任务,以及针头在哈伊斯塔克基准的细微精度降解超过32k。 Transformer 纸张(arXiv:24 1005258,2025国际克拉里昂研究中心)测量了差距: Transformers 下击 perplexity,提高长文本准确度,减少 hallucinations 大于相同大小的基线。

DIFF V1有三个问题,使它无法进入边境训练前的管道。 它的缓存必须每条解码步骤装上两次,它需要定制 CUDA 破碎的内核 FlashAttention 兼容性, 及其每个头 RMSNorm 破坏70B+级的长期训练。 DIFF V2( 微软 unilm 博客, 1月 20 、 2026 ) 修复了所有三个版本。 此课分两个版本, 构建了差异操作器, 并在玩具查询中设定取消噪音的基准 。

<a id="the-concept"></a>

## 概念

<a id="the-noise-floor-of-softmax"></a>

### 噪音地板 softmax

用于查询 `q` 键 `K = [k_1, ..., k_N]`, attention weights 是:

```
w_i = exp(q . k_i / sqrt(d)) / sum_j exp(q . k_j / sqrt(d))
```

否 `w_i` 永远是零。如果 `k_i` 完全无关 `q`,分数 `q . k_i` 并非0——波动在零左右,且有差异 `||q||^2 / d`. 之后 softmax normalization,每个不相干 token 仍在捐款 `O(1/N)` 对加权总和。 tokens 是 `O((N-1)/N) = O(1)` - 数量不小

模特儿想要的是像硬顶K一样的东西:高 weight 匹配时 tokens,接近零 weight 到处都有 Softmax 太光滑了 无法直接做到这一点。

<a id="the-differential-idea"></a>

### 不同的想法

将每个头的Q和K预测分成两个:Q=(Q)_1 Q 级_2)和K=(K)_1个K_2. 计算二 attention 地图 :

```
A_1 = softmax(Q_1 K_1^T / sqrt(d))
A_2 = softmax(Q_2 K_2^T / sqrt(d))
```

输出:

```
DiffAttn = (A_1 - lambda * A_2) V
```

减法取消了两个地图共享的噪音分布。 如果两个地图大致一致, 则取消 weight 在127K无关的 tokens (他们随机初始化时)取消这些信号。 weight 关于少数实际相关的 tokens 只有在两个地图上出现相同程度的,才会取消,而模型一旦出现,它就不会取消。

`lambda` 是每头可学习的标量, 参数化为 `lambda = exp(lambda_q1 dot lambda_k1) - exp(lambda_q2 dot lambda_k2) + lambda_init`可能是负数 `lambda_init` 默认为0.8这样的小正数。

<a id="why-this-matches-headed-noise-canceling"></a>

### 为什么这和防声器吻合

想象一下两个响声的麦克风, 记录着同一个声音。 两者都接收了扬声器加上相关的背景噪音。 将一个从另一个中减掉, 共同噪音就会消失。 声音之所以能够生存, 是因为两个信号在阶段或振幅上存在差异, 足以防止完全取消 。 `lambda` 完全了解这种平衡。

<a id="v1-vs-v2-the-diff"></a>

### V1 vs V2: diff 的变量

V1 保存 parameter 等于基准数 Transformer。要获得每个头的两个查询,它将头部的尺寸减半。这个成本是头部的清晰度,更令人痛苦的是,将头部的价值缓存减半。 softmax branch结果:尽管匹配,但解码慢于基线 parameter 计数

V2 将查询头数增加一倍,并使 KV 头保持相同( 借用) parameters 。头部维值与基准保持相同。减法后,额外维度被投向到基准线 TransformerO级_W投影,三件事同时发生:

1. 解码速度匹配基线(KV cache 已经装入一次)
2. FlashAttention 运行未变( 没有自定义内核 )
3. 解码时的自学强度上升( 从 HBM 装入的字节中更多计算) 。

V2 也删除了每个头部 RMSNorm V1 用于稳定减法。 RMSNorm V2系统用一个更简单的初始化计划来取代它,使培训稳定下来,而没有额外的模块。

<a id="when-to-reach-for-it"></a>

### 什么时候能拿到它

| Workload | Benefit |
|----------|---------|
| 长上下文 RAG (64k+) | Cleaner attention 地图,减少幻觉引用 |
| 针头在哈伊斯塔克的基准 | 高度精度提升超过32公里 |
| 多文档QA | 减少交叉文件干扰 |
| 代码完成时间为8k | 边际,不值得改变建筑 |
| 简短聊天( < 4k) | 基本上无法与基线相区别 |

值随上下文长度增长。 值为 4k tokens 噪音地板够小了 attention 128公里处很痛

<a id="how-it-stacks-with-other-2026-knobs"></a>

### 如何堆叠与其他2026个按钮

| Feature | 和DIFF V2兼容吗? |
|---------|------------------------|
| 质量保证局 | 是( V2 增加 Q 头, 不是 KV 头) |
| 司法协助(DeepSeek) | 原则上是的,没有发表任何合并它们的论文 |
| MoE | 是 (attention 独立于 MLP 块) |
| RoPE | 是(未作改动) |
| YaRN / 长文本缩放 | 是(确切地说,是贸易部帮助最多的地区) |
| FlashAttention | 是 V2(在V1中为否) |
| Speculative decoding | 是 (attention 更改在分解循环中是不可见的) |

```figure
differential-attention
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行差异 attention 纯 Python。一个已知信号加噪音结构的玩具查询,可以直接测量噪声取消比率。

<a id="step-1-standard-softmax-attention"></a>

### 步骤1:标准 softmax attention

Stdlib 矩阵行动: 列表列表、 手动 matmul, softmax 与最大数值的稳定性减法。

```python
def softmax(row):
    m = max(row)
    exps = [math.exp(x - m) for x in row]
    s = sum(exps)
    return [e / s for e in exps]
```

<a id="step-2-split-q-k-into-two-halves"></a>

### 步骤2:将Q分成两半

V1 样式: 将头部尺寸减半。 V2 样式: 保持头部尺寸, 并将头部数目增加一倍。 玩具执行使用 V1 来进行教学清晰度 —— 数学相同, 只有簿记不同 。

<a id="step-3-two-softmax-branches--subtraction"></a>

### 步骤3:二 softmax branches +减法

```python
A1 = [softmax([dot(q1, k) / scale for k in K1]) for q1 in Q1]
A2 = [softmax([dot(q2, k) / scale for k in K2]) for q2 in Q2]
diff_weights = [[a1 - lam * a2 for a1, a2 in zip(r1, r2)] for r1, r2 in zip(A1, A2)]
out = [[sum(w * v[j] for w, v in zip(row, V)) for j in range(d_v)] for row in diff_weights]
```

注:产出 weights 可能是负的。这很好—— 价值缓存仍然会处理签名捐款。 随后的V预测吸收了信号。

<a id="step-4-noise-cancellation-measurement"></a>

### 第4步:噪音取消测量

构建长度为1024的合成序列。 放置信号 token 在一个已知的位置上, rest 计算(a)标准 softmax attention weight 和(b)差数 attention weight。测量每个系统中信号对噪音的比例。 attention 可靠地产生更高的信号对噪音比,因子为3x-10x,取决于两者的多少 branches 已经接受了不同的训练。

<a id="step-5-v1-vs-v2-parameter-accounting"></a>

### 步骤5:V1对V2 parameter accounting

给定一个配置( 隐藏= 4096, 头= 32, d)_头=128, 打印 :

- Baseline Transformer: Q, K, V 每个大小 `hidden * hidden`, MLP 值 4 * 隐藏 。
- DIFF V1: Q, 每一大小K `hidden * hidden`, V 大小 `hidden * hidden` (未改变),头部缩小 内部一半。 `lambda` parameters (O(头) * d_(见E/CN.4/Sub.2/2001/L.10号文件。)
- DIFF V2: Q 大小 `2 * hidden * hidden`, K 大小 `hidden * hidden`, V 大小 `hidden * hidden`。在 O 前投影后会变暗_W. 增加同样内容 `lambda` parameters.

玩具测量额外 parameter V2类费用(约) `hidden * hidden` 额外每 attention 并打印它。

<a id="use-it"></a>

## 实际应用

DIFF V2尚未在每次生产中进行货运 inference 到2026年4月为止的服务器, 但正在整合 vLLM 和 SGLang。同时,图案出现在:

- 微软内部长文本生产模型。
- 在若干开放式模式训练中,以256k-plus为对象进行研究复制。
- 结合贸易、工业和发展部的混合结构 attention 带有滑动窗口 attention 于各层。

当你在2026年达到这个目标的时候:

- 以64k+有效环境为目标,从零开始培训新的模式。 attention 从一开始,再培训费用就很高。
- Fine-tuning 一种长期的通俗模式 迷途的中途失败主宰了你的评估。 LoRA 关于质变预测,可以大致了解贸易、森林和林业部的结构。

当你不会:

- 你正在为一个训练有素的密集型号服务 具有稳定的长文本性能。 weights.
- 你的上下文总是在16公里以下 噪音地板可忽略不计

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-diff-attention-integrator.md`鉴于模型结构,目标范围长度, hallucination 简介和训练预算,它为增加差异制定了一个融合计划。 attention 参加新的训练前活动或 LoRA 细调。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。核实所报告的信号对噪音比率差异 attention 高于标准 softmax attention 在合成查询中。 变异噪音振幅并显示标准交叉点 attention 无法使用。

2. 计算 parameter- 将7B级模型的从基线到DIFF V1和从基线到DIFF V2的三角洲计数(隐藏=4096,头=32,d)_头=128, 32 层) 显示获得的组件 parameters 和它保持不变。

3. 阅读国际劳工联合会V1文件(arXiv:24 1005258)第3节和DIFF V2 Hugging Face博客第2节。 RMSNorm 以及为什么V2可以消除它而不引起培训分歧。

4. 执行折价:计算差数 attention 与 `lambda = 0` (仅次于第一个) softmax) 和 `lambda = 1` 在合成查询中,测量整个扫描中的信号到噪音变化。 `lambda` 使信号到噪音最大化

5. 将玩具扩展至 GQA + DIFF V2 选择 8 KV 头和 32 Q 头。 显示 KV cache 大小与基准GQA模型相匹配,配置相同(8、32)。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Differential attention | "两个 softmaxes 互相减低" | 将Q,K分成两半,计算二 softmax 地图,从第一个中减去第二个(以羊羔标尺),然后乘以V |
| 噪音地板 | "非零尾巴的 softmax" | O(1/ N) 类 weight softmax 将一切无关的东西都穿上 token,在长背景下与O(1)相加 |
| lambda | "减法比例" | 每个头可以学习的天平参数 `exp(lq1.lk1) - exp(lq2.lk2) + lambda_init`; 可以是负 |
| FF V1 组织 | "2025年的ICLR版本" | 原始差异 Transformer; 将头部缩小一半以保存 parameter 计数, 需要自定义内核, 较慢解码 |
| FF V2 组织 | "2026年1月的修补" | 双倍的 Q 头保持 KV 头; 匹配基线解码速度并使用 FlashAttention |
| Per-head RMSNorm | "V1稳定器" | 差异后适用额外规范V1;V2删除了该规范,以防止培训迟到的不稳定性 |
| 信号对噪音比率 | "多少钱 attention 已经浪费了 | 比率 weight 在真实信号位置到平均位置 weight 关于不相关职位的 |
| Lost in the middle | 长发失败模式 | 在较长的背景下检索文件的准确性降低的经验现象——贸易法司 attention 减少此值 |
| 测量强度 | “每装入字节的FLOPs” | V2比率在解码时增加,每千伏下加倍查询;对内存解码很重要 |

<a id="further-reading"></a>

## 进一步阅读

- [Ye等人——差别 Transformer (arXiv:24 1005258,《2025年国际法案例汇编》)](https://arxiv.org/abs/2410.05258) - 原始文件,其中含有取消噪音理论和长文折叠
- [微软单线——差异 Transformer V2 (2026年1月)](https://huggingface.co/blog/microsoft/diff-attn-v2) - 生产堆叠重写,匹配基线解码, FlashAttention- 兼容
- [理解差异 Transformer 解锁器 Self-Attentions (arXiv:2505.16333)](https://arxiv.org/abs/2505.16333) 理论分析减法为何提前恢复 attention structure
- [共享 DIFF Transformer (arXiv:2501.179900)](https://arxiv.org/html/2501.17900) — parameter- 分享变式
- [瓦斯瓦尼等人- Attention 需要的一切(arXiv:1706.03762)](https://arxiv.org/abs/1706.03762) 基线 Transformer DIFF 减法
- [刘等人- Lost in the Middle (arXiv:2307.07372)](https://arxiv.org/abs/2307.03172) - 长文本基准 attention targets
