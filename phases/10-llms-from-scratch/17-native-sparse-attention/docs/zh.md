<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="native-sparse-attention-deepseek-nsa"></a>

# 原生稀疏 Attention（DeepSeek NSA）

> 64公里处 tokens, attention 每个开放型实验室都有计划来修复它 DeepSeekNSA(ACL 2025年最佳文件)是卡住了: attention branches - 压缩粗粗谷物 tokens,有选择地保留精细谷物 tokens和为当地环境而滑动的窗口——通过一个有知识的大门加以结合。 inference),在64k的解码中,它运行的速度比 FlashAttention 匹配或跳动时 attention 质量。 此课构建了 3 branches 端对端,并显示为什么垃圾是端对端可以区分的。

**类型:** Build
**语言:** Python (斯迪利布)
**先修要求:** 阶段7 · 12 (KV cache闪光...attention第7阶段 15(a)attention 第10阶段 16(不同类别) attention)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 说明三个消极安全保证 attention branches 和每个捕捉。
- 解释为什么NSA是"原始训练" 在以前稀少的地方...attention 方法 inference-仅.
- 计算 attention 计算NSA的节余与全额 attention 键,以64k 上下文为函数压缩区块大小和选择顶部- k。
- 执行三 -branch 以 stdlib 组合 Python 在一个简短的合成序列上 校验格子 weights 行为。

<a id="the-problem"></a>

## 问题

Full attention N级费用 `O(N^2)` 时间和 `O(N)` KV cache 每层。 64公里 tokens,计算和内存带宽数字是灾难性的。 attention 占64公里总解码潜伏量的70-80%。 tokens/秒,费用每百万 tokens - 被主宰着 attention 成本.

Sparse attention 答案是显而易见的。 先前的尝试会落到两个桶里。 固定模式的垃圾堆( 滑动窗口、 斜坡、 块状本地) 丢弃信息, 无法完成远程召回任务 。 Inference- 时间短暂(年)KV cache 修剪,H2O,流体LLM)应用到一个在密度上经过预先训练的模型 attention 并且只恢复了可能加速的一小部分 因为模型从未被要求通过稀疏的模式 来传递信息。

原生粗糙 Attention (Yuan等人, DeepSeek + PKU + UW,ACL 2025 最佳纸张,arXiv:2502.11089 两者兼有:模型在训练前学习的宽度模式,作为内部匹配算法实施,实际提供计算节省 inference。两年后,NSA或直系后裔即为默认 attention 每一个边界的长文本模型。

<a id="the-concept"></a>

## 概念

<a id="three-parallel-branches"></a>

### 三个平行 branches

每个查询, NSA 运行 attention 3次,对 KV cache:

1. **Compressed branch.** Tokens 组合成大小块 `l` 每个区块压缩成一个摘要 token 通过一个小的学习 MLP 查询。 询问会用这些压缩的 tokens,获得粗糙的视图 整个序列。

2. **Selected branch.** 使用 attention 从压缩的分数 branch,将确定与当前查询最相关的上方-k区块。 tokens 从这些区块中读取查询, 查询会覆盖所有区块。 想想压缩-branch attention 作为选择的路径信号 。

3. **Sliding-window branch.** 查询对象为最近 `W` tokens 当地情况(通常为512)。 branch 捕捉其他两个可能错过的结构重短程模式(语法、本地连字符)。

三个 branch 产出通过学习的每个位置的大门合并:

```
out = g_cmp * out_cmp + g_sel * out_sel + g_win * out_win
```

`g_cmp, g_sel, g_win` 是大门 weights 在查询中从一个小的 MLP 中找到。 他们不必对 1 进行总和, 他们可以 weight branches 独立。

<a id="why-this-is-natively-trainable"></a>

### 为什么这叫"本地训练"?

选择步骤( 上方- k 区块) 是离散的。 分立操作中断 gradient 流。 先前的稀疏 -attention 工作或者通过选择跳过反向(限制培训),或者使用不给 inference.

NSA绕过这个: 压缩...branch attention 粗粗粗粗的粗糙 attention 整个序列。 顶级操作只是重新使用顶级 attention 从压缩的分数 branch 选择要装载的精细块。 Gradients 穿过压缩的流...branch 分数(它影响压缩输出和选择逻辑)和选定区块对最终输出的贡献也是可以区分的。 `top_k` 操作是前方计算图上的无操作,它只控制从内存装入的块。

因此,NSA可以被用于培训前阶段,直至培训结束。 branches 产生一种稀疏的模式 inference 确实能带来承诺的加速。

<a id="hardware-aligned-kernel"></a>

### 硬件连接内核

NSA的内核是为现代设计而成 GPU 内存等级。 GQA 组( 外环) 的内核装入查询, 每个组获取相应的稀疏 KV 区块( 内部环) 并运行 attention 。 因为每个查询组会看到相同的选定区块( 选择为每个查询组, 不是每个查询组) , KV 的负荷会在整个组间摊销 。 Arithmetic 强度将保持高 。

文件报告 Triton 运行速度为 9x 的内核 FlashAttention 在 64 k 代码中, 加速率随着序列长度而增长。 提供前向和后向内核 。

<a id="the-compute-budget"></a>

### 计算预算

Let `N` 是序列长度, `l` 压缩块大小, `k` 最上面的点数, `w` 滑动窗口, `b` 选定区块大小(通常等于) `l`).

- Compressed branch: `O(N/l)` 每个查询的密钥, 所以 `O(N * N / l)` 总计。
- Selected branch: `O(k * b)` 每个查询的密钥, 所以 `O(N * k * b)`.
- Sliding branch: `O(w)` 每个查询的密钥, 所以 `O(N * w)`.

共计: `O(N * (N/l + k*b + w))`.

与 `N = 64k, l = 64, k = 16, b = 64, w = 512`:每份询问费用为 `1000 + 1024 + 512 = 2536 keys`完全 attention 是 `64000 keys`25x计算减法。

与 `N = 128k, l = 64, k = 16, b = 64, w = 512`:每份询问费用为 `2000 + 1024 + 512 = 3536 keys`完全 attention 是 `128000 keys`减少36倍,好处随着序列长度的增加而增加,这是关键所在。

<a id="how-does-it-compare"></a>

### 如何比较

| 方法 | Differentiable | Real inference speedup | 远程召回 |
|--------|---------------|----------------------|-------------------|
| 仅滑动窗口 | 是的 | 是的 | fails |
| 摆放/ 块分割 | 是的 | 是的 | partial |
| KV 运行( H2O, 流体LLM) | 无(无)inference-时间) | 是的 | partial |
| 摩巴(月光) | partial | 是的 | 好 |
| NSA | 是(按原样) | 是(9x64k) | 匹配齐全 attention |

同时出版了Moonshot, arXiv:2502.13189, 并采取了类似的三比一的方法, MoE 原则至 attention NSA和摩巴银行是2026年长期培训前的两个机构。

```figure
sliding-window-attention
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行三项 branches 以简短的合成序列显示:

- 压缩 MLP( 用于教学清晰度的简单平均资源库基线; 真正的NSA 使用学习的 MLP) 。
- 由压缩驱动的顶部块选择branch 得分数。
- 滑动窗口 attention 上一个 `w` tokens.
- 门锁的组合。
- 计算计数打印值 attention.

<a id="step-1-compress-tokens-into-blocks"></a>

### 步骤1:压缩 tokens 块形

```python
def compress(K, l):
    n = len(K)
    n_blocks = (n + l - 1) // l
    out = []
    for b in range(n_blocks):
        start, end = b * l, min((b + 1) * l, n)
        block = K[start:end]
        summary = [sum(row[d] for row in block) / len(block) for d in range(len(K[0]))]
        out.append(summary)
    return out
```

<a id="step-2-compressed-branch-attention"></a>

### 步骤2:压缩branch attention

Run softmax attention 键。压缩键branch 双倍得分作为选中顶点的信号 。

<a id="step-3-top-k-block-selection"></a>

### 第3步:选择顶部块

选择索引 `k` 最高比例的压缩块。 加载未压缩的原始区块 tokens 从那些街区跑 attention - 对他们。

<a id="step-4-sliding-window-attention"></a>

### 步骤4:滑动窗口 attention

最后一个 `w` tokens 运行标准 attention 对他们不利

<a id="step-5-gate--combine"></a>

### 第5步:大门+组合

查询上的小型 MLP 产生三扇门 weights。最后产出是这三个数字的加权总和 branch 输出.

<a id="step-6-compute-counting"></a>

### 步骤6:计算计算

打印每个查询的密钥数 branch 和总计。 `N` (全额) attention1024号token 合成与 `l = 32, k = 4, w = 128`NSA看到 `32 + 128 + 128 = 288` 每个查询的密钥对 1024 全 attention - 减少3.5x。

<a id="use-it"></a>

## 实际应用

NSA正在运输 DeepSeek自己的长期训练前编程。 inference 截至2026年4月的堆叠 :

- **DeepSeek internal**本地出版 weights (a) 使用消极安全保证或其后续的每日生活津贴Deepseek Sparse Attention).
- **vLLM*** NSA在发展方面的试验性支助。 DeepSeek-V3.x 电磁波 weights.
- **SGLang**公布消极安全保证基准;生产途径 vLLM.
- **llama. cpp / 缩略语 CPU**:不支持;内核分解的间接费用不值得 CPU 输油管

何时联系NSA:

- 训练前或继续训练以64k-plus为对象,并认真计算预算。
- Inference 的 DeepSeek自己的长字符 checkpoints. 该 weights 是NSA的本地人。

当不:

- 服务于一个现存的密度...attention 事先训练过的模型,没有继续训练,你无法改造NSA
- 16k下的背景 三个...branch 管理费支配着储蓄。
- 批次 - 1 交互式聊天。 时间敏感解码的好处, 但只在长的环境下 。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-nsa-integrator.md`。鉴于训练前的长文本规格,它产生了一个消极安全保证一体化计划:压缩区块大小、顶部k、滑动窗口、门式MLP宽度、内核选择以及证明改变结构有理的具体长文本电子估价。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 在1024 - 时间token 合成。 `(l, k, w)` 在三个预设和打印计算计数。 标明每个查询实现最小密钥计数的预设, 同时保持95%的整数 attention 在针头在海斯塔克测试。

2. 将平均资源库压缩器替换为略微学习的 MLP (2层,隐藏32层)。 将它训练成合成任务, 其信号是块的平均值。 测量该数字 perplexity 与持有数据的平均资源库基线的差额。

3. 执行 MLP 门。 它将查询作为输入和输出 3 标度。 显示门的感知性: 随机查询时几乎不统一重量, 重 weight 在选定的 branch 当查询到达一个遥远的街区时。

4. 计算 KV cache KV 头为 8, 头低 128, BF16。 attention 和司法协助(第10阶段 · 14 显示司法协助编号) branch KV cache 等于满数 attention.

5. 阅读消极安全保证文件第4节(arXiv:2502.11089),并在三句中解释为何压缩 branch的 attention 分数被重新用于顶级选择,而不是计算单独的路由分。 gradient 流动。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Compressed branch | "粗糙的视野" | Attention 组合平均键,以 O(N/l) 每个查询提供全局背景 |
| Selected branch | "Top-k区块" | Fine-grained attention 过 `k` 压缩率最高的区块-branch scores |
| 推拉窗 | “当地环境” | Attention 上一个 `W` tokens 用于短期模式 |
| 本地培训能力 | 开学前训练 | 在训练前学到垃圾模式 而不是在训练前 inference |
| 压缩块大小 I | “ 粗糙视图的组大小” | 多少个 tokens 合并成一个摘要;32-64典型 |
| 前k | "要紧的锁" | 未压缩的压缩区块数 tokens 读取; 16个典型 |
| 滑动窗口 W | " 当地 attention 半径" | 通常为512; 较短的篇幅会损害当地的一致性, 计算废物的时间会更长 |
| Branch gate | "如何混合三个" | 位置 MLP 输出 weights 三个 branches缴款 |
| Hardware alignment | "轻率的野兽" | 选择的粗略模式 GPU 内核实现理论加速 |
| DSA | "NSA的继任者" | Deepseek Sparse Attention, NSA在 DeepSeek线条 |

<a id="further-reading"></a>

## 进一步阅读

- [Yuan等人——土著粗皮 Attention:硬件组合和本地可培训的粗糙 Attention (ARXiv:2502.11089,ACL 2025最佳文件)](https://arxiv.org/abs/2502.11089) - 报纸
- [DeepSeek-V3技术报告(arXiv:2412.19437)](https://arxiv.org/abs/2412.19437) - 建筑家庭NSA的目标
- [月射 AI - MoBA: 块状混音 Attention 用于长字符的 LLMs (arXiv:2502.13189)](https://arxiv.org/abs/2502.13189) - 并行工作, MoE- 风格 attention 在区块上
- [Beltagy等人——长者:长文件 Transformer (arXiv:2004.05150)](https://arxiv.org/abs/2004.05150) - 滑动窗口来源
- [Xiao 等人——流体LLM:效率 Streaming 语言模型 Attention Sinks (arXiv: 2309.17453)](https://arxiv.org/abs/2309.17453) — inference- 时间宽度基线
- [Dao等人 - FlashAttention-2 (arXiv:2307.08691)](https://arxiv.org/abs/2307.08691) - 满的...attention NSA核心节拍64公里
