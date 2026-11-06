<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="attention-variants--sliding-window-sparse-differential"></a>

# Attention 变体 — 滑动窗口、稀疏、差分

> 完整的attention是一个圆圈。每个 token 都会看到每个 token，并且内存付出了代价。四种变体可以弯曲圆的形状并收回一半的成本。

**类型：** 构建
**语言：** Python
**先决条件：** 第 7 相·02 (Self-Attention)、第 7·03 相（多头）、第 7·12 相 (KV Cache / 闪存 Attention)
**时间：** ~60 分钟

<a id="the-problem"></a>

## 问题

完整的 attention 消耗 `O(N²)` 内存和 `O(N²)` 序列长度计算。对于 128K 上下文 Llama 3 70B，每层有 160 亿个 attention 条目，乘以 80 层。闪存 Attention（第 12 课）隐藏了 `O(N²)` 激活内存，但不改变算术成本 — 每个 token 仍然关注其他每个 token。

三类变体改变了 attention 矩阵本身的拓扑：

1. **滑动窗口 attention (SWA).** 每个 token 关注邻居的固定窗口，而不是完整的前缀。内存和计算下降到 `O(N · W)`，其中 `W` 是窗口。 Gemma 2/3，Mistral 7B 的第一层，Phi-3-Long。
2. **稀疏/块 attention.** 仅选定的对 `(i, j)` 获得得分； rest 被强制归零 weight。 Longformer、BigBird、OpenAI 稀疏 transformer。
3. **Differential attention.** 计算两个具有单独 Q/K 投影的 attention 地图，从另一个中减去一个。杀死将 weight 渗入前几个 tokens 的“attention 汇”。 Microsoft 的 DIFF Transformer (2024)。

这些是共存的。 2026 年的前沿模型经常将它们混合在一起：大多数层是 SWA-1024，每五层是全局完整的 attention，少数是清理检索的差分头。 Gemma 3 的 5:1 SWA 与全局比率是当前教科书的默认值。

<a id="the-concept"></a>

## 概念

<a id="sliding-window-attention-swa"></a>

### 推拉窗 Attention (SWA)

位置 `i` 处的每个查询仅关注 `[i - W, i]`（因果 SWA）或 `[i - W/2, i + W/2]`（双向）中的位置。窗外的Tokens 得到得分矩阵中的`-inf`。

```
full causal:           sliding window (W=4):
positions 0-7          positions 0-7, W=4
    0 1 2 3 4 5 6 7        0 1 2 3 4 5 6 7
0 | x                0 |  x
1 | x x              1 |  x x
2 | x x x            2 |  x x x
3 | x x x x          3 |  x x x x
4 | x x x x x        4 |    x x x x
5 | x x x x x x      5 |      x x x x
6 | x x x x x x x    6 |        x x x x
7 | x x x x x x x x  7 |          x x x x
```

对于 `N = 8192` 和 `W = 1024`，分数矩阵预期有 1024 × 8192 个非零行 — 减少了 8 倍。

**KV cache随SWA收缩。** 每层只需要保留K和V的最后一个`W` tokens。对于 Gemma-3 左右的配置（1024 个窗口，128K 上下文），KV cache 下降 128 倍。

**质量成本。** 仅 SWA transformers 难以进行远程检索。修复方法：将 SWA 层与完整的 attention 层交错。 Gemma 3 使用 5:1 SWA:global。 Mistral 7B 使用因果 SWA 堆栈，其中信息通过重叠窗口“向前流动”——每层将有效感受野扩展 `W`，在 `L` 层之后，模型可以参加 `L × W` tokens回来。

<a id="sparse--block-attention"></a>

### 稀疏/块 Attention

提前选择 `N × N` 稀疏模式。三种规范形状：

- **本地+跨步（OpenAI稀疏transformer）。**参加最后`W` tokens加每之前的 `stride`-第 token。在 `O(N · sqrt(N))` 计算中捕获本地和远程。
- **Longformer / BigBird.** 本地窗口 + 一小组全局 tokens（例如 `[CLS]`），关注所有人并被所有人关注 + 随机稀疏链接。质量匹配的经验 2× 上下文。
- **Native Sparse Attention (DeepSeek, 2025).** 了解 `(Q, K)` 的哪些块很重要；在内核级别跳过零块。 FlashAttention 兼容。

Sparse attention 是一个内核工程故事。数学很简单（掩盖分数矩阵）；胜利来自于从不将零条目加载到 SRAM 中。 FlashAttention-3 和 2026 FlexAttention API 使自定义稀疏模式在 PyTorch 中成为一流。

<a id="differential-attention-diff-transformer-2024"></a>

### 差速器 Attention（差速器 Transformer，2024）

常规 attention 有一个“attention 接收器”问题：softmax 强制每一行总和为 1，因此不想关注任何特定内容的 tokens 在第一个转储 weight token（或前几个）。这窃取了本应用于实际内容的容量。

差分 attention 通过计算 **two** attention 映射并减去来修复此问题：

```
A1 = softmax(Q1 K1^T / √d)
A2 = softmax(Q2 K2^T / √d)
DiffAttn = (A1 - λ · A2) V
```

其中 `λ` 是学习标量（通常为 0.5–0.8）。 A1捕获真实内容weights； A2 捕获水槽。减法取消接收器，将 weight 重新分配给相关的 tokens。

报告结果（Microsoft 2024）：perplexity 降低 5-10%，在相同训练长度下有效上下文延长 1.5-2 倍，大海捞针检索更清晰。

<a id="variant-comparison"></a>

### 变体比较

| 变体 | 计算 | KV cache | 质量与完整 | 生产用途 |
|---------|---------|----------|-----------------|----------------|
| 完整 attention | O(N²) | 每层 O(N) | 基线 | 每个模型的默认层 |
| SWA（窗口 1024） | O(N·W) | 每层 O(W) | -0.1 ppl，适合全局层 | 杰玛 2/3，Phi-3-Long |
| 局部+跨步稀疏 | O(N·√N) | 混合的 | 类似于 SWA | OpenAI 稀疏 transformer，Longformer |
| BigBird（本地+全局+随机） | O(N) 约 | 混合的 | 在 2× 上下文中完全匹配 | 早期长上下文 BERT |
| 原生稀疏（DeepSeek-V3.2） | O(N · active fraction) | O(N) | 0.05人以内 | DeepSeek-V3.2, 2025 |
| 差速器 | O(2·N²) | O(2N) | -5 至 -10% 人 | DIFF Transformer，2026 年初型号 |

```figure
gqa-kv-sharing
```

<a id="build-it"></a>

## 动手实现

参见 `code/main.py`。我们实现了一个因果掩码比较器，可以在玩具序列上并排显示完整、SWA、局部+跨步和差分 attention。

<a id="step-1-full-causal-mask-baseline"></a>

### 第 1 步：完整因果掩模（基线）

```python
def causal_mask(n):
    return [[0.0 if j <= i else float("-inf") for j in range(n)] for i in range(n)]
```

第 07 课的基线。下三角；对角线上方零 weight。

<a id="step-2-sliding-window-causal-mask"></a>

### 步骤 2：滑动窗口因果掩模

```python
def swa_mask(n, window):
    M = [[float("-inf")] * n for _ in range(n)]
    for i in range(n):
        lo = max(0, i - window + 1)
        for j in range(lo, i + 1):
            M[i][j] = 0.0
    return M
```

一个 parameter — `window`。对于 `window >= n`，您恢复完全因果 attention。对于 `window = 1`，每个 token 仅关注其自身。

<a id="step-3-local--strided-sparse-mask"></a>

### 步骤3：局部+跨步稀疏掩模

```python
def strided_mask(n, window, stride):
    M = [[float("-inf")] * n for _ in range(n)]
    for i in range(n):
        lo = max(0, i - window + 1)
        for j in range(lo, i + 1):
            M[i][j] = 0.0
        for j in range(0, i + 1, stride):
            M[i][j] = 0.0
    return M
```

密集本地窗口加上每个 `stride`-th token 回到序列的开头。随着附加层的增加，感受野以对数步长增长。

<a id="step-4-differential-attention"></a>

### 第四步：差分attention

```python
def diff_attention(Q1, K1, Q2, K2, V, lam):
    A1 = softmax_causal(Q1 @ K1.T / sqrt_d)
    A2 = softmax_causal(Q2 @ K2.T / sqrt_d)
    return (A1 - lam * A2) @ V
```

两次 attention 通过，用学习到的混合系数相减。在代码中，我们比较了单通道和差分通道的 attention 接收器热图，并观察接收器崩溃。

<a id="step-5-kv-cache-sizes"></a>

### 步骤5：KV cache尺寸

在 `N = 131072` 中为每个变体打印每层的缓存大小。 SWA 和稀疏变体下降了 10-100 倍。差分双打。有意识地支付你的记忆费用。

<a id="use-it"></a>

## 实际应用

2026年生产模式：

```python
from transformers import AutoModelForCausalLM
# Gemma 3 mixes SWA (window=1024) and global layers at 5:1.
model = AutoModelForCausalLM.from_pretrained("google/gemma-3-27b-it")
# print(model.config.sliding_window, model.config.layer_types)
```

PyTorch 2.5+中的FlexAttention接受掩码函数：

```python
from torch.nn.attention.flex_attention import flex_attention, create_block_mask

def swa_pattern(b, h, q_idx, kv_idx):
    return (q_idx - kv_idx < 1024) & (q_idx >= kv_idx)

mask = create_block_mask(swa_pattern, B=batch, H=heads, Q_LEN=n, KV_LEN=n)
out = flex_attention(q, k, v, block_mask=mask)
```

这将编译为自定义 Triton 内核。对于常见模式，速度在 FlashAttention-3 速度的 10% 以内，并且掩码函数是 Python 可调用的。

**何时挑选每个：**

- **Pure full attention** - 每层最多约 16K 上下文，或者当检索质量至关重要时。
- **SWA + 全局 mix** — 长上下文 (>32K)、训练和 inference 内存限制。 2026年默认32K以上。
- **稀疏块 attention** — 自定义内核，自定义模式。为专门的工作负载（检索、音频）保留。
- **Differential attention** — attention 水槽污染造成伤害的任何工作负载（长上下文 RAG，大海捞针）。

<a id="ship-it"></a>

## 交付成果

参见 `outputs/skill-attention-variant-picker.md`。该技能为给定目标上下文长度、检索需求和训练/inference 计算配置文件的新模型选择 attention 拓扑。

<a id="exercises"></a>

## 练习

1. **Easy.** 运行`code/main.py`。验证 `window=4` 处的 SWA 将每行最后 4 个 tokens 之外的所有内容归零。验证 `window=n` 位相同地再现完整因果 attention。
2. **Medium.** 在第 07 课综合项目的基础上使用 `window=1024` 实现因果 SWA。在小莎士比亚上训练 1,000 步。与完整的 attention 相比，val 损失回归了多少？峰值内存下降多少？
3. **Hard.** 在综合项目模型中实现 Gemma-3 风格的 5:1 层混合（5 个 SWA，1 个全局）。将损耗、内存和生成质量与匹配的 parameters 处的纯 SWA 和纯全局基线进行比较。
4. **Hard.** 每个头使用已学习的 `λ` 实现差分 attention。训练综合检索任务（一根针，2,000 个干扰物）。与匹配的 parameters 处的单个 attention 基线相比，测量检索精度。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 推拉窗 attention (SWA) | “本地attention” | 每个查询都会关注其最后一个 `W` tokens； KV cache 缩小为 `O(W)`。 |
| 有效感受野 | “模型能看到多远的距离” | 在具有窗口 `W` 的 `L` 层 SWA 堆栈中，最多为 `L × W` tokens。 |
| 长形器/BigBird | “本地+全局+随机” | 稀疏模式，具有一些始终参与的全局 tokens；早期的长上下文方法。 |
| 原生稀疏 Attention | “DeepSeek的内核技巧” | 学习块级稀疏性；在内核级别跳过零块，同时保持质量。 |
| 差速器attention | “两张地图，一张减去” | DIFF Transformer：从第一个映射中减去学习的 `λ` 乘以第二个 attention 映射以取消 attention 接收器。 |
| Attention水槽 | “Weight 出血至 token 0” | Softmax normalization 强制行总和为 1；无信息查询将 weight 转储到位置 0。 |
| FlexAttention | “掩码为 Python” | PyTorch 2.5+ API 将任意掩码函数编译为 FlashAttention 形状内核。 |
| 层型混合 | “5:1 SWA 到全球” | 在堆栈中交错稀疏和完整的 attention 层，以在较低内存下保持质量。 |

<a id="further-reading"></a>

## 进一步阅读

- [Beltagy、Peters、Cohan (2020)。 Longformer：长文档 Transformer](https://arxiv.org/abs/2004.05150) — 规范的滑动窗口 + global-token 论文。
- [Zaheer 等人。 （2020）。 Big Bird：Transformers 用于更长的序列](https://arxiv.org/abs/2007.14062) — 局部+全局+随机。
- [Child 等人。 （2019）。使用稀疏 Transformers](https://arxiv.org/abs/1904.10509) 生成长序列 — OpenAI 的本地+跨步模式。
- [Gemma 团队（2024）。 Gemma 2：以实用的规模改进开放语言模型](https://arxiv.org/abs/2408.00118) — 1:1 SWA：全局组合。
- [Gemma 团队（2025）。 Gemma 3 技术报告](https://arxiv.org/abs/2503.19786) — 5:1 与 window=1024 的混合，现在是教科书的默认值。
- [Ye 等人。 （2024）。差异 Transformer](https://arxiv.org/abs/2410.05258) — 差异 Transformer 纸。
- [Yuan 等人。 （2025）。原生稀疏 Attention](https://arxiv.org/abs/2502.11089) — DeepSeek-V3.2 的学习稀疏性 attention。
- [PyTorch — FlexAttention 博客和文档](https://pytorch.org/blog/flexattention/) — API 有关 Use It 中的 mask-as-callable 模式的参考。
