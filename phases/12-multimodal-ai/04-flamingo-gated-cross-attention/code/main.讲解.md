# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 04 节 Flamingo：面向 Few-Shot VLM 的门控 Cross-Attention ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码用纯 Python 演示 Flamingo 的三个关键机制，每个机制一个 DEMO：

1. **Perceiver resampler**：任意数量的 patch → 固定数量的 latent。演示"输出形状与输入 patch 数无关"。
2. **Gated cross-attention**：`y = tanh(alpha) · cross_attn(text, visual) + text`。演示 `alpha = 0` 时输出与输入**严格相等**（冻结 LLM 在初始化时被完整保留），`alpha = 2` 时视觉信息被混入。
3. **交错序列的 cross-attention mask**：对 `IMG0 t0a t0b IMG1 ...` 这样的序列，构造"每个文本 token 只看最近一张前置图像"的二维布尔矩阵。

> 一句话：**用三个小实验看清 Flamingo"不动 LLM、只在层间加一个初始为零的门"这条设计主线**。同时要看到：resampler 的 latent 不是共享参数、mask 构造了却没被使用、cross-attention 没有任何投影——这些都是为了简洁做的取舍，测验里会追问。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `rng = random.Random(7)` | 模块级随机数生成器 | 所有随机向量共用 | — |
| `vec` / `mat` | 函数 | 生成 `N(0, 0.3²)` 向量 / 矩阵 | 初始化（`mat` 实际未被使用） |
| `matvec` | 函数 | 矩阵乘向量 | 线性层（实际未被使用） |
| `dot` / `softmax` / `add` / `scale` | 函数 | 点积、稳定 softmax、向量加法、数乘 | 基本运算 |
| `cross_attention` | 函数 | 无投影的缩放点积注意力，Q、K、V 直接传入 | Cross-attention |
| `perceiver_resampler` | 函数 | 随机 latent 对 patch 做 `num_blocks` 次 cross-attn + 残差 | Perceiver resampler |
| `gated_cross_attention_step` | 函数 | `text + tanh(alpha) · cross` | Gated cross-attention |
| `interleaved_mask` | 函数 | 生成 `(文本 token 数) × (图像数)` 的布尔 mask | 交错输入 mask |
| `demo_resampler` | 函数 | 36 / 196 / 900 个 patch → 8 个 latent | 固定输出形状 |
| `demo_gate` | 函数 | alpha = 0 与 2.0 的输出偏差；打印 tanh 表 | 门的作用 |
| `demo_interleaved_mask` | 函数 | 打印 9 个位置序列的 mask 表 | 交错 mask |
| `main` | 函数 | 依次运行 3 个 DEMO 并打印要点 | — |

数据流（概念上）：patch（每图 N 个）→ `perceiver_resampler` → 每图 K 个视觉 token → 文本隐状态经 `gated_cross_attention_step` 读取视觉 token（应按 `interleaved_mask` 限制可见图像）→ 送入下一个冻结 LLM block。代码中三个 DEMO 是彼此独立的，没有串成这条完整流水线。

---

## 3. 逐段精讲

### 3.1 工具函数与初始化尺度

```python
rng = random.Random(7)

def vec(n):
    return [rng.gauss(0, 0.3) for _ in range(n)]

def add(a, b):
    return [x + y for x, y in zip(a, b)]

def scale(a, s):
    return [x * s for x in a]
```

- 所有向量从 `N(0, 0.3²)` 采样，比第 03 节代码的 `N(0, 1)` 小很多。这个尺度决定了后面注意力的形态（见 3.3）。
- `mat` 和 `matvec` 定义了却从未被调用——本文件的注意力完全没有 Q/K/V 投影矩阵。
- `add` / `scale` 是向量加法与数乘的列表版，后面实现残差和门。

### 3.2 无投影的 cross-attention

```python
def cross_attention(queries, keys, values):
    d = len(queries[0])
    scale_f = 1.0 / math.sqrt(d)
    out = []
    for q in queries:
        logits = [dot(q, k) * scale_f for k in keys]
        w = softmax(logits)
        mixed = [0.0] * d
        for i, wi in enumerate(w):
            for j in range(d):
                mixed[j] += wi * values[i][j]
        out.append(mixed)
    return out
```

- 标准的 `softmax(QKᵀ/√d)V`，但 Q、K、V **直接就是输入向量**，没有 `W_q`、`W_k`、`W_v`、`W_o`。调用处常写成 `cross_attention(latents, patches, patches)`——K 和 V 是同一组 patch。
- 输出个数 = query 个数；每个输出是 values 的凸组合。
- 变量名 `scale_f` 是为了避开同名函数 `scale`；如果写成 `scale = ...` 就会在函数内部遮蔽全局的 `scale` 函数。

### 3.3 Perceiver resampler

```python
def perceiver_resampler(patches, num_latents, num_blocks=2):
    dim = len(patches[0])
    latents = [vec(dim) for _ in range(num_latents)]
    for _ in range(num_blocks):
        attended = cross_attention(latents, patches, patches)
        latents = [add(lat, att) for lat, att in zip(latents, attended)]
    return latents
```

- 核心性质正确：输出 `num_latents` 个向量，与 `len(patches)` 无关。这就是讲义中"196 个或 900 个 patch 都输出 64 个 token"的机制。
- 每个 block：latent 作 Q，patch 作 K/V，结果加回 latent（残差）。
- ⚠️ **latent 不是共享参数**：`latents = [vec(dim) ...]` 在函数内部、每次调用都重新采样。讲义："K fixed learnable latents"。实测对同一组 36 个 patch 连续调用两次，输出的最大逐元素差异约 1.14。正确做法是在模型初始化时创建一次 latent，所有图像共用、训练时更新。
- ⚠️ **注意力几乎均匀**：`N(0, 0.3²)` 的 16 维向量点积标准差约 0.36，乘以 1/4 后约 0.09（实测 0.089）；softmax 输入几乎相同，8 个 latent 在 36 个 patch 上的平均注意力熵为 3.579，而均匀分布为 `ln 36 = 3.584`。于是每个 latent 得到的 `attended` 都约等于 patch 的平均值，resampler 退化成"平均池化 + 随机偏移"。
- ⚠️ 与讲义的其它差异：讲义每个 block 是"cross-attn → latent 间 self-attn + FFN"、共 6 个 block、K = 64、输出 1024 维；代码只有 cross-attn + 残差、2 个 block、K = 8、16 维；没有 LayerNorm，也没有视频需要的时间位置编码。

### 3.4 Gated cross-attention

```python
def gated_cross_attention_step(text_hidden, visual_tokens, alpha):
    """y = tanh(alpha) * cross_attn(text, visual) + text_hidden."""
    cross = cross_attention(text_hidden, visual_tokens, visual_tokens)
    gate = math.tanh(alpha)
    out = [add(t, scale(c, gate)) for t, c in zip(text_hidden, cross)]
    return out
```

- 文本隐状态作 Q，视觉 token 作 K/V——与 resampler 方向相同（"谁要读信息谁当 Q"）。
- `gate = tanh(alpha)`：alpha = 0 时 gate 精确为 0.0，`scale(c, 0.0)` 全为 0，`t + 0` 不产生任何舍入误差，所以 DEMO 2 打印 `max delta = 0.000000` 是**严格**的零。这就是讲义"A Flamingo at step 0 is a perfect Chinchilla 70B on text-only inputs"。
- **梯度分析**（测验 Q3）：`∂y/∂W_cross = tanh(alpha) · ∂cross/∂W`，alpha = 0 时为 0；`∂y/∂alpha = (1 − tanh² alpha) · cross`，在 0 处等于 `cross`。用有限差分实测：令 L = 输出元素之和，`dL/dalpha ≈ −1.75405`，与 `Σ cross` 完全相等。门先动起来，cross-attention 权重随后才开始学习。
- ⚠️ 这里没有 mask：每个文本 token 都能看到全部 8 个视觉 token，与 DEMO 3 构造的 mask 没有联系。
- ⚠️ 讲义的伪代码把 gated 层放在 LLM block **之后**（`cross_attn(x_after, ...)`），并且只描述了 cross-attention 一个门。阅读原论文时可以留意：Flamingo 的插入层还包含一个带门的前馈子层，插入位置是在冻结 LM 层之前，细节以论文为准。

### 3.5 交错序列 mask

```python
def interleaved_mask(sequence):
    text_positions = [i for i, s in enumerate(sequence) if not s.startswith("IMG")]
    image_positions = [i for i, s in enumerate(sequence) if s.startswith("IMG")]

    mask = [[False] * len(image_positions) for _ in text_positions]
    for ti, tpos in enumerate(text_positions):
        preceding = [i for i in image_positions if i < tpos]
        if not preceding:
            continue
        most_recent_img = preceding[-1]
        img_index = image_positions.index(most_recent_img)
        mask[ti][img_index] = True
    return mask
```

- 用标签前缀 `"IMG"` 区分图像位置和文本位置，分别记录它们在序列中的下标。
- 对每个文本位置，找出所有在它之前的图像，取最后一个（最近的）并在对应列标 True。结果是一个 `(文本 token 数) × (图像数)` 的布尔矩阵，每行至多一个 True。
- `preceding` 为空时（文本在所有图像之前）整行保持 False。若之后用 −∞ 屏蔽再 softmax，这一行会产生 NaN；正确做法是让这一行的 cross 分支直接输出 0（测验 Q10 给出了实现）。
- `image_positions.index(most_recent_img)` 是 O(n) 查找；因为 `preceding` 本身是按顺序筛出来的，也可以直接用 `len(preceding) - 1` 作为列号。
- ⚠️ mask 的粒度是"每张图一列"。真实模型中每张图对应 64 个 resampler token，应扩展为"每张图 64 列"；而且本文件的 mask 只用于打印，**没有接入任何 cross-attention**。

### 3.6 三个 DEMO

```python
    for num_patches in (36, 196, 900):
        patches = [vec(16) for _ in range(num_patches)]
        latents = perceiver_resampler(patches, num_latents=8, num_blocks=2)
```

- DEMO 1：196 = 14×14（224/16），900 = 30×30（480/16），对应讲义中的两种分辨率；输出都是 8 个 16 维 latent。
- DEMO 2：5 个文本隐状态、8 个视觉 token；alpha = 0 时比较"最大偏差"，alpha = 2 时比较"平均绝对偏差"（两种不同的统计量，阅读时注意）。随后打印 tanh 表。
- DEMO 3：9 个位置的序列，打印 6 × 3 的 mask 表，`ok` 表示可见。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| cross-attention 无 Q/K/V 投影 | 代码最短，聚焦"谁当 Q、谁当 K/V" | 无法学习；真实模型每个注意力层都有投影，且为多头 |
| resampler 的 latent 在函数内随机生成 | 不需要类和状态 | 同一图像结果不确定；应作为共享可学习参数 |
| `N(0, 0.3²)` 初始化 | 数值温和 | 注意力几乎均匀，resampler 退化为平均池化 |
| 门用 `tanh(alpha)`、alpha = 0 | 初始 no-op 且梯度最大 | 门开太大会进入饱和区（alpha = 5 时导数仅 0.0002）；实践中给门单独调学习率 |
| mask 只构造、不使用 | 单独展示 mask 的形状 | 读者看不到 mask 如何作用于 attention；应接入 cross-attention 并处理全屏蔽行 |
| 一张图 = 序列中一个位置 | 便于打印 | 真实情况一张图对应 64 个视觉 token；序列里放的是图像标记 |
| 三个 DEMO 相互独立 | 每个概念单独看清 | 没有串成"resampler → gated xattn → LLM block"的完整前向 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解 |
| 类型注解 | `def interleaved_mask(sequence: list[str]) -> list[list[bool]]:` | 标注输入是字符串列表、输出是布尔矩阵 |
| 默认参数 | `def perceiver_resampler(patches, num_latents, num_blocks=2)` | 不传时用 2 |
| 关键字参数调用 | `perceiver_resampler(patches, num_latents=8, num_blocks=2)`、`alpha=0.0` | 提高可读性 |
| 列表推导式 + 条件过滤 | `[i for i, s in enumerate(sequence) if s.startswith("IMG")]` | 筛选满足条件的下标 |
| `str.startswith` | `s.startswith("IMG")` | 判断前缀 |
| 嵌套列表初始化 | `[[False] * n for _ in text_positions]` | 每行独立的布尔列表 |
| 负索引 | `preceding[-1]` | 取最后一个元素 |
| `list.index` | `image_positions.index(most_recent_img)` | 查找元素位置 |
| `continue` | `if not preceding: continue` | 跳过本次循环剩余部分 |
| 空列表为假 | `if not preceding` | 空列表在布尔上下文中为 False |
| `zip` + 推导式 | `[add(t, scale(c, gate)) for t, c in zip(text_hidden, cross)]` | 逐对组合两个列表 |
| 嵌套生成器 + `max` | `max(abs(a - b) for a, b in zip(o, t))` | 求最大绝对差 |
| 避免变量遮蔽 | `scale_f = 1.0 / math.sqrt(d)` | 不与全局函数 `scale` 重名 |
| 条件表达式拼字符串 | `" ok " if mask[i][j] else "  . "` | 打印表格 |
| f-string 格式符 | `{max(deltas):.6f}`、`{a:4.1f}`、`{g:+.4f}`、`{x:4s}`、`{tk:5s}` | 小数位、宽度、正负号、字符串宽度 |
| `math.tanh` | `gate = math.tanh(alpha)` | 双曲正切，值域 (−1, 1) |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，便于被 `import` 复用 |

---

## 6. 运行结果解读

实际运行（Python 3，瞬间完成）：

```text
DEMO 1: Perceiver resampler
  36 patches in -> 8 latents of dim 16 out  (fixed shape regardless of input)
  196 patches in -> 8 latents of dim 16 out  (fixed shape regardless of input)
  900 patches in -> 8 latents of dim 16 out  (fixed shape regardless of input)

DEMO 2: gated cross-attention
  alpha=0.0 (tanh=0.0): max delta vs input = 0.000000
  -> frozen LLM preserved exactly at init
  alpha=2.0 (tanh=0.96): avg delta vs input = 0.0884
  -> visual contribution mixed in
    alpha= 0.0  tanh(alpha)=+0.0000
    alpha= 0.5  tanh(alpha)=+0.4621
    alpha= 1.0  tanh(alpha)=+0.7616
    alpha= 2.0  tanh(alpha)=+0.9640
    alpha= 5.0  tanh(alpha)=+0.9999

DEMO 3: interleaved attention mask
         IMG0  IMG1  IMG2
  t0a  :  ok     .     .
  t0b  :  ok     .     .
  t1a  :   .    ok     .
  t1b  :   .    ok     .
  t1c  :   .    ok     .
  t2a  :   .     .    ok
```

逐项解读：

- **DEMO 1**：输出形状固定为 8 × 16，验证了 resampler"固定输出长度"的性质。但这里只验证了形状；由于注意力近乎均匀（熵 3.579 / 3.584），8 个 latent 的内容几乎只是"随机初值 + patch 平均值"。
- **DEMO 2 alpha = 0**：严格为 0，说明零初始化门是真正的 no-op。
- **DEMO 2 alpha = 2**：平均每个元素偏移 0.0884。视觉 token 的元素尺度约 0.3，而注意力近乎均匀，cross 的输出接近 8 个视觉 token 的平均值（各元素约 0.1 量级），乘以 0.964 后得到这个量级的偏移。
- **tanh 表**：门在 alpha ≈ 2 时已开到 96%；alpha = 5 时 0.9999，对应导数 `1 − tanh²` 只有约 0.0002，门进入饱和区，很难再关小。
- **DEMO 3**：每行恰好一个 `ok`，且总在左侧最近的图像列；没有任何文本能看到它之后的图像（因果性）。序列中没有"位于所有图像之前"的文本，所以没有出现全 False 的行。

---

## 7. 动手改一改

1. **（讲义练习 2）**把 `gated_cross_attention_step` 用 PyTorch 改写，`alpha = nn.Parameter(torch.zeros(1))`，用 `torch.equal(y, x)` 验证初始化时严格相等；再对随机 loss 调用 `backward()`，打印 `alpha.grad` 与 cross-attention 投影权重的 `.grad`，验证"只有门有梯度"。
2. **共享 latent**：把 `perceiver_resampler` 改成类 `PerceiverResampler`，在 `__init__` 中创建 latent 和 Q/K/V 投影；验证同一图像两次调用的输出完全相同。
3. **补全 resampler block**：每个 block 加入 latent 间的 self-attention 与 FFN（带残差），并把 block 数提高到 6；观察注意力熵在 `N(0, 1/d)` 初始化下的数值。
4. **接入 mask**：给 `gated_cross_attention_step` 增加 `mask` 参数，每张图改为 K 个 token，正确处理"前面没有图像"的文本 token（参考测验 Q10），在序列开头加入 `"t_pre"` 测试。
5. **门的训练动力学**：写一个最小训练循环，目标是让输出逼近 `x + 0.5 · cross`，分别用学习率 0.01、0.1、1.0 更新 alpha，画出 `tanh(alpha)` 随步数的曲线，观察"门开太快"和饱和现象。
6. **（讲义练习 1）**写一个函数计算 Flamingo 类模型的可训练比例与"视觉 token 读取量"（K × 插入层数），对比 BLIP-2 的上下文占用（测验 Q12）。

---

## 8. 常见坑

- **以为零初始化会让模型学不动**：门的梯度在 0 处最大，只有 cross-attention 自身权重在第一步梯度为 0。
- **用 sigmoid 门**：`sigmoid(0) = 0.5`，初始化时就混入一半视觉信号，破坏冻结 LLM。
- **门学习率过大**：tanh 很快饱和，文本能力退化，且很难自行恢复。
- **全屏蔽行直接 softmax**：得到 NaN；要对"前面没有图像"的文本单独处理。
- **mask 方向写反**：让文本看到之后出现的图像，会造成信息泄露，few-shot 评估结果虚高。
- **resampler latent 写在前向函数里**：每次调用都是新的随机参数，无法训练、结果不可复现。
- **只验证形状不验证内容**：DEMO 1 的形状正确，但注意力近乎均匀，resampler 实际只做了平均池化。
