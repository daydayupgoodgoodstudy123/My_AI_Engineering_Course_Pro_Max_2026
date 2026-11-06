# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 14 节 从零构建 Transformer——综合项目 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；若同目录有 `tinyshakespeare.txt` 则用它，否则用文件内嵌的约 1000 字符摘录） ｜ **依赖**：标准库（`math`、`os`、`random`、`sys`）+ 可选 `torch`。没装 torch 时只打印参数量预估表，不会报错退出

---

## 1. 这份代码在考察什么

这是第 07 阶段的"毕业设计"：把前 13 节的零件拼成一个能训练、能生成文本的 decoder-only GPT。读完你应该能：

1. **把架构图翻译成代码**：embedding → N 个 Block → 最终 norm → 绑定的 lm_head，每个张量的形状都能说清楚。
2. **掌握 2026 年的"默认零件"**：pre-norm 残差、RMSNorm、SwiGLU、无 bias 线性层、权重绑定。
3. **写出最小训练闭环**：随机取窗口 → 错位一位的交叉熵 → AdamW → 梯度裁剪 → 定期看 train/val loss。
4. **写出自回归采样**：截断上下文、temperature、top-k、多项式抽样。
5. **用参数量公式做预算**：不建模型也能估出 nano / mini / small / base 四档配置的规模。
6. **优雅降级**：没有 torch 时脚本仍然能跑完，只输出能算的部分。

> 一句话：**这是本课程版的 nanoGPT——200 多行代码把一个真实 LLM 的骨架完整走一遍。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TINY_SHAKESPEARE` | 字符串常量 | 内嵌的约 1000 字符莎士比亚摘录，作为后备语料 | 训练数据 |
| `param_count(...)` | 函数 | 纯公式估算参数量（不依赖 torch） | 参数预算 |
| `run_param_preview()` | 函数 | 打印 nano/mini/small/base 四档配置的参数量 | 模型规模直觉 |
| `try_train()` | 函数 | 导入 torch；准备数据；定义模型；训练；采样 | 端到端训练 |
| `RMSNorm` | 类（`try_train` 内部） | 均方根归一化 | 第 05 节 |
| `CausalSelfAttention` | 类（内部） | 融合 qkv 的因果多头自注意力 | 第 02、03、07 节 |
| `SwiGLUFFN` | 类（内部） | 门控前馈网络 | 第 05 节 |
| `Block` | 类（内部） | pre-norm 的 attention + FFN，各带残差 | Transformer block |
| `GPT` | 类（内部） | embedding、Block 堆叠、final norm、绑定 lm_head、`generate` | decoder-only LM |
| `get_batch(split)` | 闭包函数 | 随机抽 `batch_size` 个长度 `block_size` 的窗口 | 数据加载 |
| `main()` | 函数 | 先打印参数表，再尝试训练 | 入口 |

调用关系：`main` → `run_param_preview`（总能运行）→ `try_train`（torch 存在才继续）→ 定义模型类 → 训练循环反复调用 `get_batch` 和 `model(x, y)` → 最后 `model.generate` 采样。

---

## 3. 逐段精讲

### 3.1 参数量公式：不建模型也能做预算

```python
def param_count(vocab_size, d_model, n_layers, n_heads, ffn_expansion=2.67, block_size=128):
    # token emb + pos emb
    emb = vocab_size * d_model + block_size * d_model
    # per-layer: 4*d*d (attn) + 3*d*(exp*d) (SwiGLU) + 2*d (RMSNorm)
    per_layer = 4 * d_model * d_model + 3 * d_model * int(d_model * ffn_expansion) + 2 * d_model
    # final norm + lm head tied to token emb (so 0 extra if tied)
    final = 2 * d_model
    return emb + per_layer * n_layers + final
```

逐项对应模型结构：

| 项 | 公式 | 来自哪里 |
|----|------|---------|
| token embedding | `V·d` | `nn.Embedding(vocab_size, d)` |
| 位置 embedding | `block_size·d` | `nn.Embedding(block_size, d)` |
| attention | `4d²` | `qkv`（d→3d）的 `3d²` + `out`（d→d）的 `d²`，无 bias |
| SwiGLU | `3·d·h` | `w1`、`w3`（d→h）和 `w2`（h→d），`h = int(d·2.67)` |
| 两个 RMSNorm | `2d` | 每个 norm 只有一个长度 d 的 `weight` |
| lm_head | 0 | 与 token embedding 绑定 |

- `n_heads` 出现在参数里但没有被用到——这是对的：多头只是把 d 维切成几份，**不改变参数量**。
- ⚠️ `final = 2 * d_model` 多算了一个 d：最终只有 `norm_f` 一个 RMSNorm（d 个参数），lm_head 绑定后为 0，所以应是 `final = d_model`。对 nano 配置只差 128，不影响量级判断。
- ⚠️ `block_size` 默认 128，而 `try_train` 里实际用 64；`base` 配置的位置 embedding 也只按 128 算（GPT-2 是 1024）。这张表用来建立量级直觉，不追求精确。

### 3.2 优雅降级：把 torch 导入放进函数里

```python
def try_train():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
    except ImportError:
        print("torch not installed. install with: pip install torch")
        print("once installed, rerunning will train a 4-layer char-level GPT")
        print("on the embedded Shakespeare excerpt and sample from it.")
        return
```

- `import` 写在函数内部 + `try/except ImportError`：没有 torch 时打印提示后 `return`，前面的参数表照常输出，脚本退出码为 0。课程里很多读者第一次运行时没装 torch，这样不会一上来就看到一大段报错。
- 正因为 `torch`、`nn`、`F` 只是 `try_train` 的局部变量，下面所有模型类都**定义在函数内部**（嵌套类），否则类定义时找不到 `nn.Module`。
- ⚠️ 提示里说"4-layer"，但下面实际配置是 `n_layers = 3`。

### 3.3 数据：字符级 tokenizer 与 90/10 切分

```python
    data_path = os.path.join(os.path.dirname(__file__), "tinyshakespeare.txt")
    if os.path.exists(data_path):
        with open(data_path) as f:
            text = f.read()
    else:
        text = TINY_SHAKESPEARE

    chars = sorted(set(text))
    vocab_size = len(chars)
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long)
    n = int(0.9 * len(data))
    train_data = data[:n]
    val_data = data[n:]
```

- `os.path.dirname(__file__)`：以**脚本所在目录**为基准找数据文件，而不是当前工作目录，在别的目录执行 `python path/to/main.py` 也能找到。
- `sorted(set(text))`：去重后排序，保证每次运行字符→编号的映射一致。`stoi`（string to int）和 `itos`（int to string）是一对互逆字典。
- 完整 tinyshakespeare 有 65 个字符；内嵌摘录只有 999 个字符、46 个不同字符，切分后训练 899 个、验证 100 个。
- 验证集取**末尾** 10%，而不是随机打散：语言数据前后相关，随机切会让验证集和训练集共享大量上下文，val loss 失真。
- ⚠️ 讲义说脚本会"缺失时自动下载 tinyshakespeare.txt"，实际代码不下载，只回退到内嵌摘录。999 个字符对一个 15 万参数的模型来说太少，训练会严重过拟合（见第 6 节）。

### 3.4 超参数与设备选择

```python
    block_size = 64
    d_model = 64
    n_heads = 4
    n_layers = 3
    ffn_expansion = 2.67
    batch_size = 16
    max_steps = 500
    eval_interval = 100
    lr = 3e-4
    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
```

- 嵌套的条件表达式按 CUDA → Apple 的 MPS → CPU 的优先级选设备。
- `d_head = 64 / 4 = 16`。
- ⚠️ 与讲义、docstring 不一致：讲义写的是 4 层、d_model=128、2000 步；docstring 写 4 层、d_model=128、seq_len=128；实际是 3 层、d_model=64、block_size=64、500 步。按代码为准，这是一个能在 CPU 上较快跑完的缩小版。

### 3.5 RMSNorm

```python
    class RMSNorm(nn.Module):
        def __init__(self, d, eps=1e-6):
            super().__init__()
            self.weight = nn.Parameter(torch.ones(d))
            self.eps = eps

        def forward(self, x):
            rms = x.pow(2).mean(-1, keepdim=True).add(self.eps).sqrt()
            return self.weight * (x / rms)
```

- 公式：`y = weight · x / √(mean(x²) + eps)`。沿最后一维（每个 token 的 d 维特征）计算。
- 与 LayerNorm 的区别：**不减均值、没有 bias**，只做缩放。少一次归约、少一组参数，效果相当，所以成了现代 LLM 默认。
- `keepdim=True` 让 `rms` 形状为 `(B, N, 1)`，才能和 `(B, N, d)` 的 `x` 广播相除。
- `weight` 初始化为全 1，起始时 RMSNorm 就是纯归一化。
- `super().__init__()` 必须先调用，`nn.Module` 才能登记后面的 `nn.Parameter`。

### 3.6 CausalSelfAttention：融合 qkv + 手写因果 mask

```python
    class CausalSelfAttention(nn.Module):
        def __init__(self, d, h, block_size):
            super().__init__()
            assert d % h == 0
            self.h = h
            self.d_head = d // h
            self.qkv = nn.Linear(d, 3 * d, bias=False)
            self.out = nn.Linear(d, d, bias=False)
            self.register_buffer("mask", torch.tril(torch.ones(block_size, block_size)).view(1, 1, block_size, block_size))

        def forward(self, x):
            B, N, D = x.shape
            q, k, v = self.qkv(x).split(D, dim=2)
            q = q.view(B, N, self.h, self.d_head).transpose(1, 2)
            k = k.view(B, N, self.h, self.d_head).transpose(1, 2)
            v = v.view(B, N, self.h, self.d_head).transpose(1, 2)
            att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(self.d_head))
            att = att.masked_fill(self.mask[:, :, :N, :N] == 0, float("-inf"))
            att = F.softmax(att, dim=-1)
            y = (att @ v).transpose(1, 2).contiguous().view(B, N, D)
            return self.out(y)
```

- **融合 qkv**：一个 `d → 3d` 的矩阵乘代替三个 `d → d`，GPU 上一次大矩阵乘比三次小的更快；`split(D, dim=2)` 再切回三份。
- **拆头**：`view(B, N, h, d_head)` 把 d 维切成 h 份，`transpose(1, 2)` 把头维度提前成 `(B, h, N, d_head)`，之后的 `@` 会对 B、h 两个维度批量计算。
- **缩放**：乘以 `1/√d_head`（**每个头的维度**），防止点积过大让 softmax 饱和。
- **因果 mask**：`torch.tril` 生成下三角全 1 矩阵；`== 0` 的位置（上三角，即"未来"）填 `-inf`，softmax 后权重严格为 0。`view(1, 1, bs, bs)` 加两个长度为 1 的维度，便于对 `(B, h, N, N)` 广播；`[:, :, :N, :N]` 支持比 `block_size` 短的输入（生成初期只有几个 token）。
- **`register_buffer`**：mask 随 `.to(device)` 搬运、写进 `state_dict`，但不是可训练参数。
- **合头**：`transpose` 回 `(B, N, h, d_head)`，`.contiguous()` 拷贝成连续内存，`view(B, N, D)` 拼回 d 维，再过输出投影 `out`。
- ⚠️ 讲义说使用 `F.scaled_dot_product_attention`（可自动走 Flash Attention），实际代码是手写的四步 attention。好处是每一步都看得见；代价是要显式构造 `(B, h, N, N)` 的分数矩阵，长序列时显存是 O(N²)。

### 3.7 SwiGLUFFN 与 Block

```python
    class SwiGLUFFN(nn.Module):
        def __init__(self, d, expansion):
            super().__init__()
            h = int(d * expansion)
            self.w1 = nn.Linear(d, h, bias=False)
            self.w2 = nn.Linear(h, d, bias=False)
            self.w3 = nn.Linear(d, h, bias=False)

        def forward(self, x):
            return self.w2(F.silu(self.w1(x)) * self.w3(x))

    class Block(nn.Module):
        # ...
        def forward(self, x):
            x = x + self.attn(self.n1(x))
            x = x + self.ffn(self.n2(x))
            return x
```

- **SwiGLU**：`w1` 分支经过 SiLU（`x·sigmoid(x)`）激活，`w3` 分支保持线性，两者逐元素相乘起"门控"作用，再由 `w2` 投回 d 维。
- `expansion = 2.67 ≈ 8/3`：三个矩阵共 `3·d·h ≈ 8d²`，与经典 `d→4d→d` FFN 的参数量相同。d=64 时 `h = int(170.88) = 170`。
- **Pre-norm 残差**：先 norm 再进子层，结果加回主干。主干 `x` 本身从不被归一化，梯度可以沿加法路径直达底层。
- 所有线性层都 `bias=False`：现代 LLM 的通行做法，省参数、对效果几乎无影响。

### 3.8 GPT：embedding、堆叠、权重绑定

```python
    class GPT(nn.Module):
        def __init__(self, vocab_size, d, h, n_layers, block_size, expansion):
            super().__init__()
            self.tok_emb = nn.Embedding(vocab_size, d)
            self.pos_emb = nn.Embedding(block_size, d)
            self.blocks = nn.ModuleList([Block(d, h, block_size, expansion) for _ in range(n_layers)])
            self.norm_f = RMSNorm(d)
            self.lm_head = nn.Linear(d, vocab_size, bias=False)
            self.lm_head.weight = self.tok_emb.weight  # tied
            self.block_size = block_size

        def forward(self, idx, targets=None):
            B, N = idx.shape
            tok = self.tok_emb(idx)
            pos = self.pos_emb(torch.arange(N, device=idx.device))
            x = tok + pos
            for b in self.blocks:
                x = b(x)
            x = self.norm_f(x)
            logits = self.lm_head(x)
            loss = None
            if targets is not None:
                loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
            return logits, loss
```

- **`nn.ModuleList`**：必须用它而不是普通 list，否则里面各个 Block 的参数不会被 `model.parameters()` 收集到，优化器也就训练不到它们。
- **位置 embedding**：`torch.arange(N, device=idx.device)` 生成 `0..N-1`，查表得 `(N, d)`，与 `(B, N, d)` 的 `tok` 广播相加。这是可学习的绝对位置编码，讲义练习 2 要求换成 RoPE。
- **final norm**：pre-norm 结构下残差流幅度会随层数增长，进入 lm_head 前要再归一化一次。
- **权重绑定**：`nn.Linear(d, V).weight` 的形状是 `(V, d)`，正好和 `nn.Embedding(V, d).weight` 相同，直接把同一个 `Parameter` 对象赋过去即可，两处共享内存和梯度。
- **损失**：`logits` 是 `(B, N, V)`，展平成 `(B·N, V)`；`targets` 展平成 `(B·N,)`。`F.cross_entropy` 内部做 log-softmax，所以传 logits 而不是概率。
- 返回 `(logits, loss)` 二元组：训练时用 loss，生成时用 logits。
- ⚠️ **初始化问题**：绑定发生在构造函数里，`lm_head` 因此继承了 `nn.Embedding` 的默认 `N(0, 1)` 初始化。残差流里带着当前 token 的 embedding，经 RMSNorm 后与自身的点积约为 `64/√2 ≈ 45`，模型在第 0 步会非常自信地"预测当前字符会再出现一次"。用 NumPy 按 PyTorch 默认初始化规则复现这个前向，第 0 步 loss 约 42，而不是 `ln(46) ≈ 3.83`。nanoGPT 的做法是把 Linear 和 Embedding 都用 `std=0.02` 的正态分布初始化，模拟结果就回到 3.83（详见测验 Q11）。

### 3.9 generate：自回归采样

```python
        @torch.no_grad()
        def generate(self, idx, max_new_tokens, temperature=1.0, top_k=None):
            for _ in range(max_new_tokens):
                idx_cond = idx[:, -self.block_size:]
                logits, _ = self(idx_cond)
                logits = logits[:, -1, :] / temperature
                if top_k is not None:
                    v, _ = torch.topk(logits, top_k)
                    logits[logits < v[:, [-1]]] = float("-inf")
                probs = F.softmax(logits, dim=-1)
                next_id = torch.multinomial(probs, num_samples=1)
                idx = torch.cat((idx, next_id), dim=1)
            return idx
```

- `@torch.no_grad()`：装饰器写法，整个函数内不建计算图，省显存、提速。
- `idx[:, -self.block_size:]`：位置 embedding 只有 `block_size` 个位置，超出就会越界，所以只保留最近的窗口。
- `logits[:, -1, :]`：只要最后一个位置的预测，形状 `(B, V)`。
- **temperature**：除以 T 后再 softmax。T < 1 让分布更尖（更保守），T > 1 更平（更随机）。
- **top-k**：`torch.topk` 返回前 k 大的值，`v[:, [-1]]` 是第 k 大的值（用 `[-1]` 而不是 `-1` 索引以保留维度，形状 `(B, 1)`，便于广播比较），小于它的全部设为 `-inf`，softmax 后概率为 0。
- `torch.multinomial` 按概率抽样，而不是 `argmax` 贪心，这样输出有多样性。
- ⚠️ 讲义说"从 top-p logits 采样"，代码实际是 **top-k**。另外这里没有 KV cache，每生成一个 token 都把整个窗口重新前向一遍，讲义练习 3 要求补上。

### 3.10 get_batch 与训练循环

```python
    def get_batch(split):
        src = train_data if split == "train" else val_data
        ix = torch.randint(len(src) - block_size, (batch_size,))
        x = torch.stack([src[i:i + block_size] for i in ix]).to(device)
        y = torch.stack([src[i + 1:i + 1 + block_size] for i in ix]).to(device)
        return x, y
```

- 随机挑 `batch_size` 个起点，`x` 取 `[i, i+bs)`，`y` 取 `[i+1, i+1+bs)`——**y 就是 x 右移一位**，于是位置 t 的标签是第 t+1 个字符，一个窗口同时提供 `block_size` 个训练样本。
- 上界 `len(src) - block_size` 保证 `y` 不越界。验证集只有 100 个字符，起点只能在 0～35 之间。
- `get_batch` 是定义在 `try_train` 内部的**闭包**，直接读外层的 `train_data`、`block_size`、`device` 等变量，不需要传参。

```python
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.1)

    for step in range(max_steps + 1):
        if step % eval_interval == 0:
            model.eval()
            with torch.no_grad():
                x, y = get_batch("train")
                _, train_loss = model(x, y)
                x, y = get_batch("val")
                _, val_loss = model(x, y)
            model.train()
            print(f"  step {step:>4}  train={train_loss.item():.3f}  val={val_loss.item():.3f}")
        if step == max_steps:
            break
        x, y = get_batch("train")
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
```

- **`range(max_steps + 1)` + `break`**：在第 0、100、…、500 步评估（共 6 次），但只做 500 次参数更新。这样"训练前"和"训练后"的 loss 都能打印出来。
- **AdamW 超参**：`β₂ = 0.95`（比默认 0.999 小）让二阶矩对近期梯度更敏感，是 LLM 训练的常见选择；`weight_decay=0.1` 是解耦的权重衰减。
- **`zero_grad(set_to_none=True)`**：把梯度置为 `None` 而不是 0 张量，省一次内存写入。
- **梯度裁剪**：把所有参数梯度拼成一个向量，若 L2 范数超过 1.0 就整体等比缩小，防止单步更新过猛。
- `model.eval()` / `model.train()`：本模型没有 dropout，切换模式不影响结果，但这是好习惯。
- ⚠️ 评估只用**一个 batch**，loss 估计噪声较大；nanoGPT 会对多个 batch 取平均。
- ⚠️ 讲义声称有 cosine 学习率调度和 bf16 autocast，代码里都没有：学习率全程固定 3e-4，精度是默认 fp32。
- ⚠️ `weight_decay` 作用于所有参数，包括 RMSNorm 的 `weight` 和 embedding；常见做法是只对二维权重矩阵做衰减。

### 3.11 采样输出

```python
    prompt = torch.tensor([[stoi["F"], stoi["i"], stoi["r"], stoi["s"], stoi["t"]]], dtype=torch.long, device=device)
    out = model.generate(prompt, max_new_tokens=200, temperature=0.9, top_k=10)
    sampled = "".join(itos[int(i)] for i in out[0].tolist())
```

- 以 "First" 为开头（形状 `(1, 5)`，batch 维为 1），再生成 200 个字符，输出共 205 个字符。
- `out[0].tolist()` 取出第一条序列转成 Python 列表，`itos` 查回字符再拼接。
- 字符 F、i、r、s、t 在两种语料中都存在，`stoi` 不会 KeyError。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 函数内 `import torch` + 降级 | 没装 torch 也能跑出参数表 | 模型类只能嵌套定义，无法被其他文件 import；生产中拆成独立模块 |
| 字符级 tokenizer | 零依赖、词表小、好调试 | 序列长、效率低；生产用 BPE（如 `tiktoken`） |
| 可学习绝对位置 embedding | 实现最简单 | 不能超出 `block_size` 外推；生产多用 RoPE |
| 手写 attention + 显式 mask | 每一步可见，便于教学 | O(N²) 显存；生产用 `F.scaled_dot_product_attention` / Flash Attention |
| Pre-norm + RMSNorm + SwiGLU + 无 bias | 2026 年主流 LLM 的默认配方 | — |
| 权重绑定 | 省 V·d 参数，小模型收益明显 | 需配合合适的初始化（本代码缺失） |
| 固定学习率、fp32 | 代码短 | 生产中用 warmup + cosine、bf16 autocast |
| 单 batch 评估 | 快 | 噪声大；生产中多 batch 平均 |
| 无 KV cache 的生成 | 逻辑最直白 | 生成慢；生产必须有 KV cache |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 三引号多行字符串 | `TINY_SHAKESPEARE = """First Citizen: ..."""` | 保留换行，适合嵌入一段文本 |
| `try / except ImportError` | `try: import torch ... except ImportError: ... return` | 可选依赖缺失时优雅降级 |
| 函数内 import | `try_train` 里的 `import torch` | 只有调用函数时才导入，导入的名字是局部变量 |
| 嵌套类 / 闭包 | `class GPT` 和 `def get_batch` 都定义在 `try_train` 里 | 内部定义可以直接读取外层函数的局部变量 |
| 类继承与 `super()` | `class RMSNorm(nn.Module)`、`super().__init__()` | 继承 PyTorch 模块基类，先初始化父类 |
| `assert` | `assert d % h == 0` | 条件不成立时抛 `AssertionError`，用于检查前提 |
| 集合与排序 | `sorted(set(text))` | 去重后排序 |
| 字典推导式 | `{c: i for i, c in enumerate(chars)}` | 一行构建映射；`stoi.items()` 再反转得到 `itos` |
| 列表推导式 | `[Block(...) for _ in range(n_layers)]` | `_` 表示不使用的循环变量 |
| 生成器表达式 | `sum(p.numel() for p in model.parameters())` | 不建中间列表直接求和 |
| 元组解包 | `B, N, D = x.shape`、`q, k, v = ...split(...)`、`_, loss = model(x, y)` | `_` 丢弃不需要的返回值 |
| 条件表达式（三元） | `"cuda" if ... else ("mps" if ... else "cpu")` | 可以嵌套 |
| 装饰器 | `@torch.no_grad()` | 给整个函数套上"不记录梯度"的上下文 |
| `with` 上下文管理器 | `with open(data_path) as f:`、`with torch.no_grad():` | 自动关闭文件 / 自动恢复梯度记录 |
| `os.path` | `os.path.join(os.path.dirname(__file__), ...)`、`os.path.exists` | 基于脚本位置拼路径、检查文件存在 |
| 关键字参数与默认值 | `generate(prompt, max_new_tokens=200, temperature=0.9, top_k=10)` | 调用时显式命名，可读性好 |
| `is not None` | `if targets is not None:`、`if top_k is not None:` | 判断可选参数是否传入 |
| f-string 格式 | `{step:>4}`、`{train_loss.item():.3f}`、`{name:<16}` | 右对齐宽 4、3 位小数、左对齐宽 16 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

本环境**没有安装 torch**，脚本只完整运行了参数量预估部分（在临时副本中执行一次），实际输出：

```text
=== parameter counts for capstone configs ===
name                  V    L    H      d     ~params
  nano               65    4    4    128      811904
  mini               65    6    6    192     2693952
  small              65   12   12    384    21331584
  base            50257   12   12    768   123705600

torch not installed. install with: pip install torch
once installed, rerunning will train a 4-layer char-level GPT
on the embedded Shakespeare excerpt and sample from it.
```

- **nano ≈ 81 万**：与讲义"4/4/128 约 800K"一致。
- **每档规模的跳跃主要来自 d²**：d 从 128 → 192 → 384，每层参数大致按 `≈ 12d²`（`4d² + 3·d·2.67d ≈ 12d²`）增长，层数也在增加。
- **base ≈ 1.24 亿**：其中 `50257 × 768 ≈ 3860 万` 是 token embedding，占 31%。词表从 65 变成 5 万后，embedding 从"可以忽略"变成"大头"，这正是讲义说"换 BPE 后模型容量要同步放大"的原因。

**训练部分：未实际运行（缺少 torch）。** 根据代码，安装 torch 后预期会看到：

- 一段配置信息：`vocab_size: 46`（用内嵌摘录时）、`block_size: 64`、`d_model: 64`、`n_heads: 4`、`n_layers: 3`。`parameters` 按结构手算应为 154,560（绑定参数只计一次）。
- 6 行 `step 0/100/.../500  train=...  val=...`。按 3.8 节的分析，第 0 步 loss 很可能远高于 `ln(46) ≈ 3.83`（NumPy 按同样的默认初始化模拟约为 42）。
- 由于训练集只有 899 个字符，500 步 × 16 × 64 ≈ 51 万个 token 位置相当于把训练集反复看了几百遍，预期 train loss 持续下降、val loss 明显高于 train loss 甚至回升——典型过拟合。讲义里"val loss 紧跟 train loss、不过拟合"的结论针对的是完整 tinyshakespeare（约 1.1MB）。
- 最后一段以 "First" 开头的 205 个字符。由于是在小摘录上过拟合，输出很可能大段复现摘录中的原句（如 "First Citizen:"）。

---

## 7. 动手改一改

1. 修正 `param_count` 的 `final = d_model`，并在 `try_train` 中加一行断言：`param_count(...) == n_params`（注意传入实际的 `block_size=64`）。
2. 加入 nanoGPT 式初始化（`std=0.02`），对比第 0 步 loss 是否从几十降到约 `ln(V)`。
3. 把手写 attention 换成 `F.scaled_dot_product_attention(q, k, v, is_causal=True)`，删掉 mask buffer，确认输出数值一致（`torch.allclose`）。
4. 加 warmup + cosine 学习率调度（参考测验 Q12），以及 `torch.autocast` 的 bf16 训练。
5. 下载完整 tinyshakespeare 放到 `code/` 目录，把配置改回讲义的 4 层、d=128、2000 步，验证 val loss 能否降到 2.0 以下。
6. 进阶：在 `generate` 中实现 KV cache（讲义练习 3），对比生成 500 个 token 的耗时；或者把可学习位置 embedding 换成 RoPE（练习 2）。

---

## 8. 常见坑

- **用普通 list 存子模块**：`self.blocks = [Block(...)]` 不会注册参数，模型"训练"了但 Block 根本没更新；必须用 `nn.ModuleList`。
- **transpose 后直接 view**：`transpose` 产生非连续张量，`view` 会报错；先 `.contiguous()` 或改用 `.reshape`。
- **mask 在 softmax 之后才加**、或填 0 而不是 `-inf`：未来位置仍有权重，训练 loss 好得不正常，生成却是乱码。
- **x、y 没错位**：`y = x` 时模型只需复制输入，loss 迅速降到接近 0，毫无意义。
- **权重绑定 + 默认初始化**：初始 logits 过大，第 0 步 loss 远高于 ln V；先做健全性检查。
- **生成时不截断上下文**：超过 `block_size` 后位置 embedding 越界报错。
- **在极小数据上下结论**：内嵌摘录只有约 1000 个字符，val loss 只能用来观察过拟合，不能用来评价模型结构好坏。
