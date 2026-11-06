# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 04 节 预训练 Mini GPT (124M Parameters) ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：`numpy`（无需 GPU、无需 PyTorch、无需网络）

---

## 1. 这份代码在考察什么

这份代码用纯 NumPy 搭出了 GPT-2 的完整结构，并在一个 4 层、128 维的小模型上演示训练与生成：

1. **GPT 的每一个零件**：Embedding（token + 位置）、LayerNorm、多头因果注意力、FFN、pre-norm Transformer block、weight tying 的输出层。
2. **张量形状的变化**：尤其是多头注意力里 `reshape → transpose → reshape` 的"拆头—合头"过程。
3. **数值稳定性**：softmax 与交叉熵都先减最大值；因果 mask 用 `-1e9` 而非 `-inf`。
4. **训练的核心机制**：输入/目标错开一位的 next-token prediction、交叉熵、手写反向传播与 SGD 更新。
5. **规模直觉**：GPT-2 四个尺寸的参数量、推理时权重与 KV cache 的显存估算。
6. **自回归生成**：temperature 采样与上下文窗口截断。

> 一句话：**把"124M 参数如何协同预测下一个 token"拆成一行行看得见的矩阵运算**。同时也要看清它在哪些地方做了简化——这些简化恰好是面试追问的高发区。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Embedding` | 类 | token 查表 + 位置查表，二者相加 | 输入表示 |
| `LayerNorm` | 类 | 在最后一维归一化，带 γ、β | 层归一化 |
| `MultiHeadAttention` | 类 | Q/K/V 投影、拆头、缩放点积 + mask、合头、输出投影 | 多头因果注意力 |
| `FeedForward` | 类 | `d → 4d → d`，中间 ReLU | FFN |
| `TransformerBlock` | 类 | `x + attn(ln1(x))`，`x + ffn(ln2(x))` | Pre-norm block |
| `MiniGPT` | 类 | 组装上述模块；`forward` 返回 logits；`count_parameters` 数参数 | GPT 模型 |
| `cross_entropy_loss` | 函数 | 数值稳定的 log-softmax + 负对数似然 | 训练目标 |
| `generate` | 函数 | 自回归逐 token 采样 | 文本生成 |
| `layernorm_backward` / `ffn_backward` | 函数 | 手写的 LayerNorm、FFN 反向传播 | 反向传播 |
| `train_mini_gpt` | 函数 | 随机取窗口 → 前向 → loss → 部分反向 → SGD 更新 | 训练循环 |
| `parameter_breakdown` | 函数 | 打印 GPT-2 Small/Medium/Large/XL 参数量 | 规模估算 |
| `memory_estimate` | 函数 | 打印 FP16 下权重与 KV cache 显存 | 推理显存 |

数据流：`__main__` 固定随机种子 → 打印参数表与显存表 → `train_mini_gpt`（内部构造 `MiniGPT`）→ `generate` → 把字节解码成文本打印。

---

## 3. 逐段精讲

### 3.1 Embedding：查表 + 相加

```python
class Embedding:
    def __init__(self, vocab_size, embed_dim, max_seq_len):
        self.token_embed = np.random.randn(vocab_size, embed_dim) * 0.02
        self.pos_embed = np.random.randn(max_seq_len, embed_dim) * 0.02

    def forward(self, token_ids):
        seq_len = token_ids.shape[-1]
        tok_emb = self.token_embed[token_ids]
        pos_emb = self.pos_embed[:seq_len]
        return tok_emb + pos_emb
```

- `self.token_embed[token_ids]`：用整数数组做**花式索引**，`(B, S)` 的 ID 直接取出 `(B, S, D)` 的向量——这就是 embedding "查表"的本质。
- `pos_embed[:seq_len]` 形状为 `(S, D)`，与 `(B, S, D)` 相加时自动**广播**到每个 batch。
- 标准差 0.02 来自 GPT-2：太大会让初始前向数值失控，太小会让所有输入的输出几乎一样、早期梯度没信息。
- ⚠️ 位置 embedding 只有 `max_seq_len` 行，序列超过它就会出错（`generate` 用滑动窗口规避）。

### 3.2 LayerNorm

```python
    def forward(self, x):
        mean = x.mean(axis=-1, keepdims=True)
        var = x.var(axis=-1, keepdims=True)
        return self.gamma * (x - mean) / np.sqrt(var + self.eps) + self.beta
```

- 在**特征维**（最后一维）上求均值和方差，每个 token 独立归一化，与 batch 无关。
- `keepdims=True` 让结果形状为 `(B, S, 1)`，可以直接与 `(B, S, D)` 广播相减。
- `eps = 1e-5` 防止方差为 0 时除零；γ 初始化为 1、β 为 0，初始时等价于纯归一化。

### 3.3 多头注意力：拆头 → 注意力 → 合头

```python
    def forward(self, x, mask=None):
        batch, seq_len, d = x.shape
        Q = (x @ self.W_q).reshape(batch, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        K = (x @ self.W_k).reshape(batch, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        V = (x @ self.W_v).reshape(batch, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)

        scores = Q @ K.transpose(0, 1, 3, 2) / np.sqrt(self.head_dim)
        if mask is not None:
            scores = scores + mask
        weights = np.exp(scores - scores.max(axis=-1, keepdims=True))
        weights = weights / weights.sum(axis=-1, keepdims=True)
        attn_out = weights @ V

        attn_out = attn_out.transpose(0, 2, 1, 3).reshape(batch, seq_len, d)
        return attn_out @ self.W_out
```

形状追踪（以 GPT-2 Small 为例，`B` 个样本、`S` 个 token）：

| 步骤 | 形状 |
|------|------|
| `x @ W_q` | `(B, S, 768)` |
| `.reshape(B, S, 12, 64)` | 把 768 维切成 12 段，每段 64 维 |
| `.transpose(0, 2, 1, 3)` | `(B, 12, S, 64)`：头维提前，每个头一个 `(S, 64)` 矩阵 |
| `K.transpose(0, 1, 3, 2)` | `(B, 12, 64, S)` |
| `scores = Q @ Kᵀ / √64` | `(B, 12, S, S)` |
| `+ mask` | mask `(S, S)` 广播到每个 batch、每个头 |
| `weights @ V` | `(B, 12, S, 64)` |
| `.transpose(0, 2, 1, 3).reshape(B, S, 768)` | 合头，拼回 768 维 |
| `@ W_out` | `(B, S, 768)` |

- `@` 对 4 维数组做**批量矩阵乘法**：前两维当作 batch，最后两维做矩阵乘。
- softmax 先减去每行最大值：`softmax(x − c) = softmax(x)`，但能防止 `exp` 溢出。
- 构造函数里的 `assert embed_dim % num_heads == 0`：维度必须能被头数整除，否则 reshape 失败。
- ⚠️ 与 GPT-2 原版的差异：Q/K/V 和输出投影都**没有 bias**；Q/K/V 用三个独立矩阵（GPT-2 原实现是一个 `768 → 2304` 的合并矩阵，数学上等价）。
- ⚠️ 合头前的 `transpose` 会产生非连续数组，NumPy 的 `reshape` 会自动复制；PyTorch 中则需要 `.contiguous()`。

### 3.4 FFN 与 Transformer block

```python
class FeedForward:
    # ...
    def forward(self, x):
        h = x @ self.W1 + self.b1
        h = np.maximum(0, h)
        return h @ self.W2 + self.b2


class TransformerBlock:
    # ...
    def forward(self, x, mask=None):
        x = x + self.attn.forward(self.ln1.forward(x), mask)
        x = x + self.ffn.forward(self.ln2.forward(x))
        return x
```

- FFN 把每个位置独立地从 `d` 扩到 `4d` 再压回 `d`，提供逐位置的非线性变换。
- ⚠️ `np.maximum(0, h)` 是 ReLU；GPT-2 实际用 GELU。讲义练习 2 要求换成 `GELU(x) = x · 0.5 · (1 + erf(x/√2))` 并对比 loss。
- block 是 **pre-norm**：先 LayerNorm 再进子层，最后加回残差。残差主干上没有 LayerNorm，梯度能沿 `x + ...` 直通到底层。

### 3.5 `MiniGPT`：组装与 weight tying

```python
    def forward(self, token_ids):
        seq_len = token_ids.shape[-1]
        mask = np.triu(np.full((seq_len, seq_len), -1e9), k=1)

        x = self.embedding.forward(token_ids)
        for block in self.blocks:
            x = block.forward(x, mask)
        x = self.ln_f.forward(x)

        logits = x @ self.embedding.token_embed.T
        return logits
```

- **因果 mask**：`np.full` 生成全为 −1e9 的方阵，`np.triu(..., k=1)` 只保留主对角线**以上**的部分（其余置 0）。于是位置 i 对位置 j > i 的分数加上 −1e9，softmax 后约为 0。用 −1e9 而不是 `-inf`，可以避免整行都被屏蔽时出现 `inf − inf = NaN`。
- `self.blocks` 是用**列表推导式**创建的 12（或 4）个**独立** block，每个都有自己的权重。
- **weight tying**：`x @ token_embed.T` 把 `(B, S, D)` 映射到 `(B, S, V)`，输出层没有单独的权重矩阵。
- 因为是 pre-norm，所有 block 之后还要一个最终的 `ln_f`。
- `count_parameters` 逐项累加 `.size`（元素个数）；输出层因为共享权重不重复计数。

### 3.6 交叉熵与生成

```python
def cross_entropy_loss(logits, targets):
    batch, seq_len, vocab_size = logits.shape
    logits_flat = logits.reshape(-1, vocab_size)
    targets_flat = targets.reshape(-1)

    max_logits = logits_flat.max(axis=-1, keepdims=True)
    log_softmax = logits_flat - max_logits - np.log(
        np.exp(logits_flat - max_logits).sum(axis=-1, keepdims=True)
    )

    loss = -log_softmax[np.arange(len(targets_flat)), targets_flat].mean()
    return loss
```

- 展平成 `(B·S, V)`，每一行是一个位置的预测。
- `log_softmax = x − max − log Σ exp(x − max)`：这是 **log-sum-exp 技巧**，直接计算对数概率，既不溢出也不会出现 `log(0)`。
- `log_softmax[np.arange(N), targets_flat]`：用两组整数数组做花式索引，一次取出每一行"正确 token"的对数概率，取负再平均。

```python
def generate(model, prompt_tokens, max_new_tokens=100, temperature=0.8):
    tokens = list(prompt_tokens)
    seq_len = model.embedding.pos_embed.shape[0]

    for _ in range(max_new_tokens):
        context = np.array(tokens[-seq_len:]).reshape(1, -1)
        logits = model.forward(context)
        next_logits = logits[0, -1, :]

        next_logits = next_logits / temperature
        probs = np.exp(next_logits - next_logits.max())
        probs = probs / probs.sum()

        next_token = np.random.choice(len(probs), p=probs)
        tokens.append(next_token)

    return tokens
```

- `tokens[-seq_len:]`：只保留最近 `seq_len` 个 token，这就是"上下文窗口"。
- 只取最后一个位置的 logits `logits[0, -1, :]`，作为下一个 token 的分布。
- `np.random.choice(len(probs), p=probs)` 按概率采样一个下标。
- ⚠️ 每生成一个 token 都对整个窗口重新做一次完整前向——没有 KV cache（讲义练习 3 要求加上）。
- ⚠️ `temperature=0` 会除以 0 产生 NaN，`np.random.choice` 报错；讲义说"T = 0 是贪心"，但实现需要单独分支（见测验 Q10）。
- ⚠️ 没有 top-k/top-p，也没有遇到 EOS 停止的逻辑。

### 3.7 训练循环：前向、loss、部分反向、SGD

```python
    for step in range(num_steps):
        start_idx = np.random.randint(0, max(1, len(tokens) - seq_len - 1))
        batch_tokens = tokens[start_idx:start_idx + seq_len + 1]

        input_ids = batch_tokens[:-1].reshape(1, -1)
        target_ids = batch_tokens[1:].reshape(1, -1)
```

- 每步随机截取 `seq_len + 1 = 65` 个字节：前 64 个作输入、后 64 个作目标——**错开一位**就是 next-token prediction。一个窗口同时提供 64 个训练样本（每个位置预测它的下一个字节）。
- batch size 恒为 1。

```python
        probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
        probs = probs / probs.sum(axis=-1, keepdims=True)
        dlogits = probs.copy()
        dlogits[np.arange(batch_size)[:, None], np.arange(s_len), target_ids] -= 1.0
        dlogits /= (batch_size * s_len)

        grad_token_embed = np.zeros_like(model.embedding.token_embed)
        for b in range(batch_size):
            grad_token_embed += dlogits[b].T @ x_normed[b]

        dx_normed = dlogits @ model.embedding.token_embed
```

- **softmax + 交叉熵的梯度 = 预测概率 − one-hot**，再除以位置总数（因为 loss 取了平均）。
- `dlogits[np.arange(B)[:, None], np.arange(S), target_ids]`：三组索引广播成 `(B, S)`，一次把每个位置正确 token 的概率减 1。
- 输出头 `logits = x_normed @ Eᵀ` 的梯度：对 E 是 `dlogitsᵀ @ x_normed`，对 `x_normed` 是 `dlogits @ E`。
- `layernorm_backward` 与 `ffn_backward` 是标准公式；我们用有限差分额外做了梯度检查，两者对输入的梯度误差分别约为 1e-9 和 1e-12，实现正确。

```python
            ln2_in = block_in + block.attn.forward(block.ln1.forward(block_in), mask)
            ln2_out = block.ln2.forward(ln2_in)

            dffn, gW1, gb1, gW2, gb2 = ffn_backward(dx, ln2_out, block.ffn)
            # ...
            dx = dx + dln2_in
```

- 从最后一个 block 往前：**重算**该 block 的中间结果（注意力输出、`ln2` 的输入输出），再依次反传 FFN、`ln2`，并把梯度加到残差上。
- ⚠️ **这是不完整的反向传播**（已用训练前后权重快照验证）：
  - 注意力子层的梯度**没有反传**，`W_q/W_k/W_v/W_out` 和 `ln1` 从未被更新；
  - 位置 embedding 从未被更新；
  - token embedding 只收到输出头一侧的梯度，输入侧的梯度（应按 token ID 累加到对应行）被丢弃；
  - 合计约 32.6% 的参数（271,360 / 832,256）在训练中保持随机初始值。
- ⚠️ 优化器是最朴素的 SGD（`W -= lr * grad`），学习率 3e-4、没有 warmup、没有 Adam。讲义中说生产会用 Adam + warmup + 梯度累积 + 梯度裁剪。
- 讲义称"Every gradient is computed by your code"，与实际代码不符；讲义正文里的 `train_mini_gpt` 甚至只有前向和 loss、完全没有更新步骤。真正训练 124M 模型应使用 PyTorch 等自动微分框架。

### 3.8 规模估算：参数表与显存表

```python
    for name, vocab, dim, heads, layers, seq_len, ff in configs:
        token_emb = vocab * dim
        pos_emb = seq_len * dim
        per_block_attn = 4 * dim * dim
        per_block_ff = 2 * dim * ff + dim + ff
        per_block_ln = 4 * dim
        # ...
        total = token_emb + pos_emb + layers * per_block + final_ln
```

- 注意力只算权重（`4·d²`），FFN 算了权重和 bias，因此结果比 Hugging Face 的真实值少了注意力 bias（GPT-2 Small 少 `12 × 3,072 = 36,864`，输出 124,402,944，真实值 124,439,808）。详见测验 Q11。

```python
    for name, params, layers, heads, head_dim, max_seq in models:
        weight_bytes = params * 2
        kv_per_token = 2 * layers * heads * head_dim * 2
        kv_full = kv_per_token * max_seq
```

- 权重显存 = 参数量 × 2 字节（FP16）；KV cache = `2(K,V) × 层数 × 头数 × head_dim × 2 字节 × 序列长度`。
- 内部函数 `fmt(b)` 定义在循环里，负责把字节数格式化为 MB/GB。
- ⚠️ Llama 3 系列使用 GQA，只有 8 个 KV 头，但代码用的是查询头数（32/64/128），导致 KV cache 分别被高估 4、8、16 倍（405B 输出 1082.3 GB，按 8 个 KV 头应约 67.6 GB）。详见测验 Q12。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 NumPy 实现 | 每个矩阵运算都可见 | 没有 GPU、没有自动微分；生产用 PyTorch/JAX |
| 演示用 4 层 128 维、字节级词表 | 几秒内跑完 | 学不到有意义的语言；真实 124M 需要 GPU 和海量数据 |
| ReLU 代替 GELU | 简单 | 与 GPT-2 不一致；练习 2 可替换 |
| 注意力无 bias、Q/K/V 分开 | 代码清晰 | 参数量与 GPT-2 原版略有差异 |
| mask 用 −1e9 | 避免整行屏蔽时出现 NaN | 在 FP16 下 −1e9 会溢出成 −inf，低精度实现需改用类型相关的最小值 |
| 手写**部分**反向传播 + SGD | 展示梯度公式，代码量可控 | 注意力、`ln1`、位置 embedding 不更新，模型学不会用上下文；应使用 autograd + AdamW |
| 无 KV cache 的生成 | 逻辑最简单 | 每步重算整个窗口；生产必须用 KV cache |
| 参数/显存估算函数 | 建立规模直觉 | 漏注意力 bias、忽略 GQA，数字需修正 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `class` 与普通方法 | `class LayerNorm: def forward(self, x)` | 用类保存参数，`forward` 执行计算（模仿 PyTorch 的写法） |
| 默认参数 | `def __init__(self, dim, eps=1e-5)`、`MiniGPT(vocab_size=50257, ...)` | 调用时可省略 |
| `assert` + f-string | `assert embed_dim % num_heads == 0, f"..."` | 条件不满足时立即报错并给出信息 |
| 列表推导式创建对象 | `[TransformerBlock(...) for _ in range(num_layers)]` | `_` 表示不使用的循环变量 |
| 元组解包 | `batch, seq_len, d = x.shape` | 一次取出多个维度 |
| NumPy 随机初始化 | `np.random.randn(a, b) * 0.02`、`np.random.seed(42)` | 标准正态 × 0.02；固定种子保证可复现 |
| 花式索引 | `self.token_embed[token_ids]`、`log_softmax[np.arange(N), targets_flat]` | 用整数数组批量取元素 |
| 广播 | `tok_emb + pos_emb`、`scores + mask` | 形状不同的数组按规则自动扩展 |
| `axis` 与 `keepdims` | `x.mean(axis=-1, keepdims=True)` | 沿最后一维规约并保留维度，便于广播 |
| `reshape` / `transpose` | `.reshape(B, S, H, Dh).transpose(0, 2, 1, 3)` | 改变形状 / 交换维度顺序 |
| `@` 矩阵乘法 | `x @ self.W_q`、`Q @ K.transpose(...)` | 高维时做批量矩阵乘 |
| `np.triu` / `np.full` | `np.triu(np.full((S, S), -1e9), k=1)` | 构造上三角 mask |
| `np.maximum` | `np.maximum(0, h)` | 逐元素取最大值，实现 ReLU |
| 布尔数组转浮点 | `(h > 0).astype(float)` | ReLU 的导数 |
| 原地运算 | `W -= lr * grad`、`dlogits /= (...)` | 直接修改数组，不新建对象 |
| `np.zeros_like` / `.copy()` | `np.zeros_like(model.embedding.token_embed)`、`probs.copy()` | 同形状全零数组；显式复制避免共享内存 |
| 倒序 `range` | `range(len(model.blocks) - 1, -1, -1)` | 从最后一层往前遍历（反向传播顺序） |
| 嵌套函数 | `memory_estimate` 里的 `def fmt(b)` | 函数内部定义只在本地使用的小函数 |
| 字节与文本 | `list("The transformer".encode("utf-8"))`、`bytes(output_tokens).decode("utf-8", errors="replace")` | 字节级 token 与字符串互转 |
| 多行字符串 | `corpus = """..."""` | 三引号字符串保留换行 |
| f-string 格式符 | `{total:>14,}`、`{name:<16}`、`{loss:.4f}`、`{step:4d}` | 右/左对齐、千分位、小数位、宽度 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy，固定 `np.random.seed(42)`，耗时约 4.5 秒）：

```text
GPT-2 Family Parameter Counts
Model            Layers  Heads   Dims         Params
GPT-2 Small          12     12    768    124,402,944   ← 少了注意力 bias（真实 124,439,808）
GPT-2 Medium         24     16   1024    354,724,864
GPT-2 Large          36     20   1280    773,845,760
GPT-2 XL             48     25   1600  1,557,304,000

Memory Requirements for Inference (FP16)
Model                       Weights     KV Cache      Total
GPT-2 Small (124M)           248 MB        38 MB     286 MB   ← 18,432 值/token × 2B × 1024
Llama 3 8B                  16.0 GB       4.3 GB    20.3 GB   ← KV 按 32 头算，GQA 下应约 1.07 GB
Llama 3 70B                140.0 GB      21.5 GB   161.5 GB   ← 应约 2.68 GB
Llama 3 405B               810.0 GB    1082.3 GB  1892.3 GB   ← 应约 67.6 GB

Training Mini GPT
Model parameters: 832,256
Training tokens: 876                  ← 语料只有 876 字节
Config: 4 layers, 4 heads, 128 dims

Step    0 | Loss: 5.5682              ← ≈ ln(256) = 5.545，初始化正常
Step   20 | Loss: 5.5720
Step   40 | Loss: 5.4632
...
Step  160 | Loss: 5.1051
Step  180 | Loss: 5.0556              ← 下降很慢

Prompt: 'The transformer'
Generated: The transformer��1�!� -^�����+6%� ...   ← 几乎是随机字节
```

逐项解读：

- **参数量 832,256** 可以手算验证：token 256×128 = 32,768；位置 64×128 = 8,192；每个 block 注意力 65,536 + FFN 131,712 + LN 512 = 197,760，×4 = 791,040；最终 LN 256。合计 832,256。
- **Step 0 的 loss 5.5682** 与 `ln 256 ≈ 5.545` 吻合，说明初始化和 loss 实现都正常。
- **loss 只从 5.57 降到 5.06**：原因有三——SGD + 很小的学习率；只有约 2/3 的参数在更新，注意力完全没在学；每步只用 1 个 64 字节的窗口，且每次记录的是随机窗口上的 loss（有噪声，例如 Step 20 比 Step 0 还略高）。
- **生成结果是乱码**：模型输出的字节分布只比均匀分布略尖，会采样到大量 ≥ 128 的字节，它们组不成合法的 UTF-8，于是 `errors="replace"` 显示为 `�`。讲义说"semi-coherent at best"，在这个实现下实际连半通顺都达不到；这本身就是一个好教训：**模型能否学会上下文依赖，取决于梯度能否流到注意力层**。
- **KV cache 数字**：GPT-2 Small 的 38 MB 是对的（FP32 时约 75 MB，与讲义一致）；Llama 3 的三行因为忽略 GQA 被严重高估。

---

## 7. 动手改一改

1. 完成讲义练习 1：把配置改成 24 层 16 头（保持 768 维）和 12 层 1536 维（保持 12 头），用 `count_parameters` 对比"加深"和"加宽"带来的参数增长（加宽是平方增长）。
2. 完成讲义练习 2：实现 GELU（`x * 0.5 * (1 + erf(x / sqrt(2)))`，可用 `math.erf` 配合 `np.vectorize`，或用 tanh 近似），同时修改 `ffn_backward` 中的导数，比较 500 步后的 loss。
3. 修复 `generate`：temperature 为 0 时走 `np.argmax`，并加入 top-k 与 top-p（参考测验 Q10）。
4. 修正 `memory_estimate`：给每个模型加上 `num_kv_heads=8`，用 KV 头数计算 KV cache；再给 `parameter_breakdown` 加上注意力 bias，使 GPT-2 Small 输出 124,439,808（别忘了最终 LayerNorm）。
5. 完成讲义练习 3：为 `generate` 实现 KV cache——首次前向后保存每层的 K、V，之后每步只算新 token 的 Q/K/V 并拼接到缓存，测量生成 200 个 token 的耗时差异。
6. 进阶：用 PyTorch 重写 `MiniGPT`（结构一一对应），用 `loss.backward()` + AdamW + warmup/cosine 训练 1000 步，画出 loss 曲线并与本代码对比（讲义练习 5 描述了"快速下降—缓慢下降—平台"三个阶段）。

---

## 8. 常见坑

- **以为 loss 下降就说明反向传播正确**：只更新部分参数 loss 也会下降。应做有限差分梯度检查，并确认每个参数确实发生了变化。
- **mask 方向写反**：`np.triu(..., k=1)` 屏蔽的是"未来"（列号大于行号）；写成 `np.tril` 会让模型偷看答案，训练 loss 会异常低。
- **合头时漏了 transpose**：直接 `attn_out.reshape(B, S, D)` 不会报错，但会把不同位置的数据混在一起，结果是错的。
- **temperature = 0 直接相除**：得到 NaN，需单独走贪心分支。
- **数参数不说明口径**：是否含 bias、是否 weight tying、是否含最终 LN，都会导致不同的数字。
- **估算 KV cache 用查询头数**：GQA/MQA 模型应使用 KV 头数，否则会高估数倍到十几倍。
- **超出位置 embedding 长度**：输入超过 `max_seq_len` 时 `pos_embed[:seq_len]` 只取到 `max_seq_len` 行，与 token embedding 相加会因形状不匹配报错；生成时务必截断上下文。
