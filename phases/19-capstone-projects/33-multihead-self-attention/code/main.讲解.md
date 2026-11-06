# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 33 节 多头 Self-Attention ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m pytest -q` 或 `python3 tests/test_attention.py` ｜ **依赖**：`torch`（第三方，CPU 即可）；`math`、`dataclasses`（标准库）

---

## 1. 这份代码在考察什么

这是"从零搭 GPT"系列的第四步：在第 32 节的 `(B, T, D)` 输入上实现**带因果 mask 的多头自注意力**。代码考察：

1. **高效的 QKV 投影**：一个 `Linear(D, 3D)` + `chunk(3)` 代替三个线性层。
2. **拆头与合头**：`view + transpose` 把 `(B, T, D)` 变成 `(B, H, T, d_head)`，算完再拼回来。
3. **缩放点积注意力**：`Q Kᵀ / √d_head`、softmax、`weights @ V`。
4. **因果 mask**：下三角 buffer + `masked_fill(-inf)`，保证位置 t 看不到 t 之后的 token。
5. **可解释性入口**：`return_weights=True` 返回 `(B, H, T, T)` 的注意力权重，用 ASCII 热力图打印。
6. **梯度能流过整个块**：用一个"嵌入 + 注意力 + LM head"的小模型在 repeat 任务上训练，确认 loss 下降。

> 一句话：**把"多头因果自注意力"写成生产风格的 PyTorch 模块，并用形状断言、mask 检查和一个小训练验证它**。但要注意：demo 的 repeat 任务太简单，看任何位置都能答对，因此它**无法**展示讲义所说的"头的专门化"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MultiHeadSelfAttention` | `nn.Module` | QKV 投影、拆头、缩放点积、因果 mask、softmax、dropout、合头、输出投影 | 本节主角 |
| `_split_heads` / `_merge_heads` | 方法 | `(B,T,D) ↔ (B,H,T,dh)` | 多头 reshape |
| `TokenEmbedding` | `nn.Module` | 第 32 节的精简副本（无输入校验） | token 查表 |
| `SinusoidalPositionalEmbedding` | `nn.Module` | 第 32 节的精简副本 | 位置编码 |
| `TinyAttentionLM` | `nn.Module` | 嵌入 → 注意力 → `Linear(D, V)`；**没有残差、没有 FFN、没有 LayerNorm** | 最小可训练模型 |
| `DemoConfig` | dataclass | V=64、D=32、H=4、T=12、B=16、3 轮 × 120 步、lr=5e-3、seed=42 | 配置 |
| `_make_repeat_batch` | 函数 | 每行一个随机 id 复制 T+1 次，输入/目标错开一位 | 玩具任务 |
| `_train` | 函数 | Adam + 交叉熵训练循环，返回每轮平均 loss | 训练 |
| `_heatmap_row` | 函数 | 把一行权重映射成 `" .:-=+*#%@"` 字符 | 可视化 |
| `main` | 函数 | 形状契约 → mask 检查 → 训练 → 热力图 | 演示 |

数据流：`ids (B,T)` → token emb + 位置 emb → `(B,T,D)` → `qkv_proj` `(B,T,3D)` → 3 × `(B,H,T,dh)` → scores `(B,H,T,T)` → mask + softmax → `@V` `(B,H,T,dh)` → 合头 `(B,T,D)` → `out_proj` → `lm_head` → logits `(B,T,V)`。

---

## 3. 逐段精讲

### 3.1 构造函数：两层线性 + 一张 mask

```python
        self.qkv_proj = nn.Linear(d_model, 3 * d_model, bias=True)
        self.out_proj = nn.Linear(d_model, d_model, bias=True)
        self.attn_dropout = nn.Dropout(attn_dropout)
        self.out_dropout = nn.Dropout(out_dropout)

        causal_mask = torch.tril(torch.ones(max_context_length, max_context_length))
        self.register_buffer("causal_mask", causal_mask, persistent=False)
```

- 参数只有两层：`qkv_proj` 的权重 `(3D, D)` + bias `3D`，`out_proj` 的权重 `(D, D)` + bias `D`。D=32 时合计 `3,168 + 1,056 = 4,224`（实测）。讲义："The two linear layers ... are the only parameters in the block."
- `nn.Linear(in, out)` 内部存的权重形状是 `(out, in)`，计算 `x @ Wᵀ + b`。
- 合并 QKV 与三个独立线性层等价：`(3D, D)` 的权重就是 `W_q、W_k、W_v` 上下堆叠。
- `torch.tril(ones)`：下三角（含对角线）为 1，严格上三角为 0。用 buffer 注册：跟随 `.to(device)`、不是参数、`persistent=False` 不进 `state_dict`。
- ⚠️ mask 是 float32 的 `L × L` 张量：L=1024 时 4 MiB，L=131,072 时 64 GiB（计算值）。生产实现用 `is_causal=True` 不物化 mask（见测验 Q12）。
- 构造函数校验 `d_model % n_heads == 0`，否则 `view(b, t, H, dh)` 无法切分。

### 3.2 拆头与合头

```python
    def _split_heads(self, x: torch.Tensor) -> torch.Tensor:
        b, t, _ = x.shape
        return x.view(b, t, self.n_heads, self.d_head).transpose(1, 2)

    def _merge_heads(self, x: torch.Tensor) -> torch.Tensor:
        b, h, t, dh = x.shape
        return x.transpose(1, 2).contiguous().view(b, t, h * dh)
```

| 步骤 | 形状（demo：B=16, T=12, H=4, dh=8） |
|------|-----------|
| 输入 `x` | `(16, 12, 32)` |
| `.view(b, t, H, dh)` | `(16, 12, 4, 8)`：把 32 维切成 4 段 |
| `.transpose(1, 2)` | `(16, 4, 12, 8)`：头维挪到 batch 维旁边 |
| 合头 `.transpose(1, 2)` | `(16, 12, 4, 8)` |
| `.contiguous().view(b, t, 32)` | `(16, 12, 32)` |

- `view` 不复制数据，只改变"怎么解释同一块内存"，要求内存布局兼容。`transpose` 只交换步长（stride），得到**不连续**的张量，之后再 `view` 会报错，所以合头时必须先 `.contiguous()`（复制成连续内存）。
- `_split_heads` 的输入来自 `chunk`，它是原张量最后一维的切片，最后一维内部仍然连续，所以 `view` 拆最后一维是允许的。
- ⚠️ 合头时**不能省略 transpose**：`x.contiguous().view(b, t, h*dh)` 形状正确但会把同一头的不同位置拼成一个 token 的特征（测验 Q9，我们实测往返结果不等于原输入）。

### 3.3 前向：投影 → 分数 → mask → softmax → 加权 → 合头 → 投影

```python
        qkv = self.qkv_proj(x)
        q, k, v = qkv.chunk(3, dim=-1)

        q = self._split_heads(q)
        k = self._split_heads(k)
        v = self._split_heads(v)

        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_head)
        mask_slice = self.causal_mask[:t, :t]
        scores = scores.masked_fill(mask_slice == 0, float("-inf"))

        weights = F.softmax(scores, dim=-1)
        weights = self.attn_dropout(weights)

        context = torch.matmul(weights, v)
        context = self._merge_heads(context)

        out = self.out_proj(context)
        out = self.out_dropout(out)
```

- `qkv.chunk(3, dim=-1)`：沿最后一维均分成 3 份，各 `(B, T, D)`。
- `k.transpose(-2, -1)`：`(B, H, T, dh)` → `(B, H, dh, T)`；`torch.matmul` 对四维张量把前两维当 batch，结果 `(B, H, T, T)`。
- 除以 `√d_head`（demo 中 `√8 ≈ 2.83`）：q、k 分量方差为 1 时点积方差约 `d_head`，缩放后回到约 1。我们实测 d=4/64/512 时缩放前方差约 3.97/64.1/506，缩放后都约 1.0。
- `causal_mask[:t, :t]`：取左上角 `(T, T)`，广播到 `(B, H, T, T)`；`mask == 0` 选中严格上三角（未来位置），填 `-inf`，softmax 后为精确的 0。
- `F.softmax(scores, dim=-1)`：沿 key 维归一化，每个 query 行和为 1。对角线始终保留，所以不会出现整行 `-inf` 导致的 NaN；如果以后叠加 padding mask 就要小心（测验 Q8）。
- `attn_dropout` 作用在**归一化后的权重**上（训练时随机置零并放大 `1/(1-p)`），所以训练模式下行和不再严格为 1；而 `return_weights=True` 返回的正是 dropout 之后的权重（我们用 `p=0.5` 实测某一行和为 1.56）。默认 `p=0`，demo 不受影响。
- 前向开头还有三项校验：必须是三维、最后一维等于 `d_model`、`T ≤ max_context_length`。

```python
        if return_weights:
            return out, weights
        return out
```

- 返回类型注解 `torch.Tensor | tuple[torch.Tensor, torch.Tensor]`：根据标志返回一个或两个值。这种"返回类型随参数变化"的写法简单但不利于静态检查。

### 3.4 `TinyAttentionLM`：最小可训练模型

```python
    def forward(self, ids, return_weights=False):
        b, t = ids.shape
        tok = self.token_emb(ids)
        pos = self.pos_emb(t)
        x = tok + pos.unsqueeze(0)
        if return_weights:
            attn_out, weights = self.attn(x, return_weights=True)
            logits = self.lm_head(attn_out)
            return logits, weights
        attn_out = self.attn(x)
        logits = self.lm_head(attn_out)
        return logits
```

- 结构：嵌入 → **单层**注意力 → `nn.Linear(D, V)`（独立的 LM head，没有 weight tying）。参数量：token 表 2,048 + 注意力 4,224 + LM head 2,112 = 8,384（实测）。
- ⚠️ 没有残差连接：logits 完全由注意力的输出决定，token 本身的信息必须"经过注意力"才能到达 LM head。对 repeat 任务这没问题（见 3.6）。
- `TokenEmbedding` 和 `SinusoidalPositionalEmbedding` 是第 32 节的复制品（精简了校验），讲义系列每一节都保持代码自包含。

### 3.5 repeat 任务与训练循环

```python
    base = torch.randint(
        0, cfg.vocab_size, (cfg.batch_size, 1), generator=generator, dtype=torch.long
    )
    ids = base.expand(cfg.batch_size, cfg.seq_len + 1).contiguous()
    return ids[:, :-1], ids[:, 1:]
```

- 每行一个随机 id，用 `expand` 复制成 `T+1 = 13` 列（`expand` 不复制内存，`contiguous()` 才真正复制），输入取前 12 列、目标取后 12 列。
- 独立的 `torch.Generator`：数据采样的随机数与模型初始化的全局随机数分开，可复现。

```python
            logits = model(inputs)
            loss = F.cross_entropy(logits.reshape(-1, cfg.vocab_size), targets.reshape(-1))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item()
```

- `F.cross_entropy` 要求 logits 为 `(N, V)`、目标为 `(N,)`，所以把 `(B, T, V)` 展平成 `(B·T, V)`。
- 标准的"清梯度 → 反传 → 更新"三步；优化器是 Adam，lr=5e-3（对这么小的模型偏大但收敛快）。
- `loss.item()` 把标量张量转成 Python float，避免把计算图累积在 `total` 上。

### 3.6 热力图与"头的专门化"

```python
def _heatmap_row(row: torch.Tensor, width: int = 28) -> str:
    glyphs = " .:-=+*#%@"
    cells: list[str] = []
    for v in row.tolist():
        idx = int(min(len(glyphs) - 1, max(0, v * len(glyphs))))
        cells.append(glyphs[idx])
    return "".join(cells[:width])
```

- 10 个字符代表 10 个区间：权重 `v ∈ [0, 0.1)` 为空格，`≥ 0.9` 为 `@`。`min/max` 把下标夹在 `[0, 9]` 内。
- `main` 中先 `model.eval()` 再 `with torch.no_grad()` 取权重：前者关闭 dropout，后者不建计算图。

⚠️ **任务设计的问题**：每一行所有位置都是同一个 id，目标"下一个 token"永远等于"当前 token"。因为每个位置的 value 里都有这个 id 的信息，注意力看哪里都能答对。我们打印了训练后第 11 行各头的权重：

| 头 | 主要关注 |
|----|---------|
| head 0 | 位置 2（0.55）、位置 1（0.24） |
| head 1 | 位置 0（0.79） |
| head 2 | 接近均匀（0.05–0.18） |
| head 3 | 位置 0（0.67）、位置 1（0.27） |

没有一个头是"前一个 token"头。docstring 写"A single attention head looking one token back is enough to solve it"——够用，但不是必需，所以训练出来的模型不会这样做。想真正看到位置相关的模式，需要一个**必须**依赖相对位置的任务（见第 7 节练习 4）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 单个 `Linear(D, 3D)` | 一次 matmul，初始化方便 | 与三个线性层等价；GQA 时 K、V 维度不同，需要拆开或调整切分 |
| 手写 softmax 注意力 | 每一步可见，能返回权重 | 物化 `(B,H,T,T)`，显存 `O(T²)`；生产用 `F.scaled_dot_product_attention`/FlashAttention |
| `L × L` float mask buffer | 实现直观，跟随设备 | 长上下文内存爆炸（131K 时 64 GiB）；生产用 `is_causal=True` 或布尔 mask |
| mask 值 `-inf` | 被屏蔽位置权重精确为 0 | 整行屏蔽时 NaN；混合精度下常用 `finfo.min` |
| `return_weights` 标志 | 方便可视化与测试 | 返回类型不固定；融合 kernel 无法返回权重 |
| dropout 默认 0 | demo 与测试确定性 | 训练模式下返回的是 dropout 后的权重 |
| `TinyAttentionLM` 无残差、无 FFN | 只验证注意力本身能被训练 | 不是真正的 Transformer block，下一节补上 |
| repeat 玩具任务 | 3 秒内收敛，确认梯度流通 | 不需要位置信息，热力图无法展示头的专门化 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 联合类型注解 | `-> torch.Tensor \| tuple[torch.Tensor, torch.Tensor]` | 返回值可能是两种类型之一（配合 `from __future__ import annotations` 可在旧版本使用） |
| 关键字参数默认值 | `attn_dropout: float = 0.0` | 不传时使用默认值 |
| 方法名前单下划线 | `_split_heads`、`_merge_heads` | 约定为内部方法，但测试仍可以直接调用 |
| 元组解包与 `_` | `b, t, _ = x.shape` | 不需要的值用 `_` 占位 |
| 多重赋值 | `q, k, v = qkv.chunk(3, dim=-1)` | 一次接收三个返回值 |
| `float("-inf")` | `masked_fill(..., float("-inf"))` | Python 中的负无穷 |
| `torch.tril` / `torch.triu` | `torch.triu(torch.ones(T, T), diagonal=1).bool()` | 下 / 上三角；`.bool()` 转成布尔张量用作索引 |
| 布尔索引 | `weights[0, 0][upper]` | 用布尔矩阵取出所有上三角元素 |
| `masked_fill` | `scores.masked_fill(mask_slice == 0, ...)` | 条件为真的位置填入指定值（非原地，返回新张量） |
| `view` / `transpose` / `contiguous` | `_split_heads`、`_merge_heads` | 改形状 / 交换维度 / 复制成连续内存 |
| `expand` | `base.expand(B, T + 1)` | 广播式复制，不分配新内存 |
| `torch.Generator` | `generator.manual_seed(cfg.seed)` | 独立的随机数流 |
| `assert` 带消息 | `assert upper_mass < 1e-5, "future positions must have zero weight"` | 断言失败时显示消息 |
| `with torch.no_grad()` | 热力图部分 | 推理时不记录计算图 |
| `model.eval()` | 热力图前 | 切换到推理模式（关闭 dropout） |
| `.tolist()` | `row.tolist()` | 张量转 Python 列表，便于逐元素处理 |
| 嵌套 `min/max` 夹取 | `int(min(9, max(0, v * 10)))` | 把值限制在区间内 |
| `str.join` | `"".join(cells[:width])` | 拼接字符列表 |
| f-string 格式符 | `{avg:.4f}`、`{upper_mass:.6f}`、`{t:>2}` | 小数位数、右对齐宽度 |
| `@dataclass` | `DemoConfig` | 自动生成构造函数；`DemoConfig(n_heads=8)` 可覆盖单个字段 |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU，约 3.7 秒）：

```text
Shape contract
--------------
input  : (16, 12, 32)
output : (16, 12, 32)

Causal mask check
-----------------
weights shape          : (16, 4, 12, 12)
sum over future cells  : 0.000000
row sums (head 0, batch 0): min=1.0000, max=1.0000

Train tiny model on repeat task
-------------------------------
random-init expected loss ~ log(V) = 4.1589
epoch 1/3  avg loss: 2.8808
epoch 2/3  avg loss: 0.0501
epoch 3/3  avg loss: 0.0036

Per-head attention heatmap
--------------------------
head 0, query rows top-down, key cols left-to-right
  q= 0: |@           |
  q= 1: |.%          |
  q= 2: | +=         |
  q= 3: | ==         |
  ...
  q=11: | :+         |

Demo OK.
```

逐项解读：

- **形状契约**：输入输出同形 `(16, 12, 32)`，注意力块可以像积木一样堆叠。
- **mask 检查**：上三角权重和为 0，每行和为 1——但 demo 只检查了 batch 0、head 0，测试覆盖了全部。
- **loss**：`ln 64 = 4.1589` 是随机预测的理论值。第 1 轮平均 2.88（包含从 4.16 降下来的过程），第 2 轮已降到 0.05，第 3 轮 0.0036，符合讲义"well under 1.0 over three epochs"。
- **热力图**：q=0 只能看自己（`@`）；q=1 时 0.18/0.82（`.%`）；之后的行主要关注位置 1、2（例如 q=11 为 `0.02, 0.24, 0.55, 0.09, ...`，显示为 ` :+`）。这是一种"关注固定的绝对位置"的模式，而不是讲义描述的"前一个 token"模式——原因见 3.6。热力图右侧全空，直观展示了因果三角。
- 把 `n_heads` 改成 8（讲义建议的实验），三轮 loss 为 `2.8814 → 0.0475 → 0.0035`，与 4 头几乎一样；这个任务对头数不敏感。

---

## 7. 动手改一改

1. **讲义建议**：`DemoConfig(n_heads=8)`（`d_head=4`），对比热力图和 loss。再试 `n_heads=32`（`d_head=1`）看看会发生什么。
2. **打印所有头**：把热力图循环改成遍历 `head_id in range(cfg.n_heads)`，观察不同头的关注模式（我们看到一个头几乎均匀、两个头集中在位置 0）。
3. **换成 SDPA**：用 `F.scaled_dot_product_attention(q, k, v, is_causal=True)` 替换手写部分（`return_weights=False` 时），验证输出与原实现 `allclose`（我们实测成立）。
4. **一个真正需要位置的任务**：把数据改成交替序列 `a b a b a b …`（目标 = 前一个 token）。我们试过：5 轮后 loss 约 0.79（理论下限约 `ln 64 / 12 ≈ 0.35`，因为位置 0 的目标无法预测），各头学会了"看与自己奇偶性不同的位置"，例如 q=4 几乎全部看位置 1。对比 repeat 任务的热力图，体会"任务决定头学什么"。
5. **KV cache**：实现 `forward_cached(x_new, past)`，mask 取 `causal_mask[start:t_total, :t_total]`，验证逐 token 增量结果与整体前向一致（参考测验 Q11，我们实测最大误差约 9e-8）。
6. **进阶：RoPE**：在 `_split_heads` 之后、计算分数之前对 q、k 做旋转位置编码，并把 `TinyAttentionLM` 的 sinusoidal 加法去掉，看看交替任务是否学得更快。

---

## 8. 常见坑

- **合头漏 transpose**：形状对、结果错，只有往返测试能发现。
- **transpose 后直接 view**：报 "view size is not compatible with input tensor's size and stride"；用 `.contiguous().view` 或 `.reshape`。
- **softmax 维度写错**：`dim=-2` 会沿 query 维归一化，列和为 1 而不是行和，因果性也被破坏。
- **mask 方向写反**：用 `triu` 当保留区域，模型会看到未来，训练 loss 异常地低。
- **把 mask 存成参数**：会被优化器更新；固定张量用 buffer。
- **`-inf` + padding**：整行屏蔽产生 NaN，并通过反向传播污染所有参数。
- **用热力图下结论**：权重高不等于"这个头在做某件事"，还要看 value 的内容；另外玩具任务的热力图不代表真实模型。
- **训练模式下取权重**：dropout 打开时返回的是被随机置零并放大过的权重。

---

## 9. 测试在验证什么

`tests/test_attention.py` 共 16 个 `unittest` 测试，开头把 `code/` 加入 `sys.path` 后导入 `MultiHeadSelfAttention` 和 `TinyAttentionLM`。实际运行：`python3 -m pytest -q` → `16 passed in 2.82s`。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TestConstruction` | `test_d_model_must_divide_n_heads` | `D=10, H=3` 构造时报错 |
| | `test_zero_heads_rejected` | `H=0` 报错 |
| | `test_d_head_set_correctly` | `D=32, H=4 → d_head=8` |
| `TestShape` | `test_output_shape_matches_input` | `(2,7,16)` 进、`(2,7,16)` 出 |
| | `test_weights_shape` | 权重为 `(B,H,T,T) = (2,4,7,7)` |
| | `test_rejects_wrong_feature_dim` | 最后一维 32 ≠ 16 报错 |
| | `test_rejects_seq_len_past_max` | T=5 > 4 报错 |
| `TestCausalMask` | `test_upper_triangle_has_zero_weight` | **所有** batch、所有头的上三角权重和 < 1e-5 |
| | `test_weight_rows_sum_to_one` | 每行和为 1 |
| | `test_future_tokens_do_not_change_past_output` | 把位置 4 之后的输入换成随机值，位置 0–3 的输出不变——端到端的因果性检查，比只看权重更强 |
| `TestHeadSplit` | `test_split_then_merge_round_trip` | 拆头形状 `(2,6,5,4)`，合头后与原输入完全相等（能抓住合头漏 transpose 的 bug） |
| | `test_qkv_proj_outputs_3d` | QKV 投影输出 `3D = 48` 维 |
| `TestScalingAndSoftmax` | `test_softmax_row_sums` | 行和为 1（与上面的测试有重复） |
| | `test_weights_non_negative` | 权重非负 |
| `TestGradientFlow` | `test_gradients_reach_qkv_and_out_proj` | 反传后两层权重的梯度都非零 |
| `TestTinyTraining` | `test_loss_drops_on_repeat_task` | 152 步后 loss 小于第一步的一半 |

说明：类名 `TestScalingAndSoftmax` 并没有真正测试"缩放"（例如没有验证分数除以了 `√d_head`）；若把 `/ math.sqrt(self.d_head)` 删掉，这些测试仍会全部通过。可以补一个测试：用固定权重构造 q、k，手算分数并与 `return_weights` 的结果对比。
