# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 35 节 组装 GPT 模型 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下，需构建两个 124M/163M 模型，约 1 GB 内存、10 秒左右）；测试：`python3 -m pytest -q` 或 `python3 tests/test_model.py` ｜ **依赖**：`torch`（第三方，CPU 即可）；`math`、`dataclasses`（标准库）

---

## 1. 这份代码在考察什么

这是"从零搭 GPT"系列的第六步：把第 34 节的 pre-LN block 堆成一个**完整的 GPT-2 Small**，并实现文本生成。代码考察：

1. **模型组装**：token embedding + learned 位置 embedding + embedding dropout + 12 个 block + `final_ln` + LM head。
2. **参数量核对**：精确复现 124,439,808（GPT-2 Small 的真实参数量），并用 untied 版本验证 tying 节省 `V × D`。
3. **Weight tying**：参数级共享（同一个 `Parameter`），用 `data_ptr()` 验证。
4. **GPT-2 风格初始化**：`N(0, 0.02²)` + 残差投影按 `1/√(2·num_layers)` 缩放。
5. **生成**：temperature、top-k、multinomial 采样、滑动窗口、`eval`/`no_grad` 与状态恢复。

> 一句话：**把前几节的零件拼成一个参数量与 GPT-2 Small 完全一致的模型，并让它能"说话"**（虽然未训练时说的是随机 token）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GPTConfig` | dataclass | 124M 默认配置 + `dropout`、`use_bias`、`weight_tying` 开关 | 模型超参数 |
| `LayerNorm` / `MultiHeadAttention` / `FeedForward` | `nn.Module` | 第 34 节的本地副本（dropout 统一用 `cfg.dropout`） | block 零件 |
| `TransformerBlock` | `nn.Module` | 只保留 pre-LN | GPT-2 block |
| `GPTModel` | `nn.Module` | 组装、tying、位置 id buffer、初始化、前向 | 完整模型 |
| `_init_weights` / `_scale_residual_projections` | 方法 | std 0.02 初始化；残差投影再缩放 | GPT-2 初始化 |
| `count_parameters` | 函数 | 按 `id()` 去重统计参数 | 参数量 |
| `top_k_filter` | 函数 | 小于第 k 大值的 logits 置 `-inf` | top-k 截断 |
| `generate` | 函数 | 滑动窗口 + temperature + top-k + multinomial 的自回归循环 | 文本生成 |
| `demo` | 函数 | 124M 参数量、tying 检查、untied 差值、一次前向、tiny 模型生成、超长 prompt | 演示 |

数据流：`tokens (B,T)` → `tok_embed (B,T,768)` + `pos_embed(position_ids[:T]) (T,768)` → dropout → 12 × block → `final_ln` → `lm_head`（= `tok_embed.weight`）→ `logits (B,T,50257)`；生成时取 `logits[:, -1, :]` → `/T` → top-k → softmax → `multinomial` → 拼接。

---

## 3. 逐段精讲

### 3.1 `GPTConfig` 与本地 block 副本

```python
@dataclass
class GPTConfig:
    vocab_size: int = 50257
    context_length: int = 1024
    d_model: int = 768
    num_heads: int = 12
    num_layers: int = 12
    mlp_expansion: int = 4
    dropout: float = 0.1
    use_bias: bool = True
    weight_tying: bool = True
```

- 与第 34 节相比，两种 dropout 合并成一个 `dropout`，删掉了 `pre_ln` 开关（只用 pre-LN），新增 `vocab_size`、`num_layers`、`weight_tying`。
- `LayerNorm`、`MultiHeadAttention`、`FeedForward`、`TransformerBlock` 都是第 34 节的复制品（讲义："reimplements the same block pattern from lesson 34 locally"）。保持每节代码自包含，代价是同一逻辑在多个文件里重复。
- `FeedForward.forward` 写成了一行嵌套调用：`self.dropout(self.fc2(self.act(self.fc1(x))))`。

### 3.2 `GPTModel.__init__`：组装 + tying + buffer + 初始化

```python
        self.tok_embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.pos_embed = nn.Embedding(cfg.context_length, cfg.d_model)
        self.embed_dropout = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([TransformerBlock(cfg) for _ in range(cfg.num_layers)])
        self.final_ln = LayerNorm(cfg.d_model)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)

        if cfg.weight_tying:
            self.lm_head.weight = self.tok_embed.weight
```

- `nn.Linear(768, 50257)` 的权重形状是 `(50257, 768)`，与 `nn.Embedding(50257, 768)` 的权重形状**恰好相同**，所以可以直接共享，不需要转置（`Linear` 计算 `x @ Wᵀ`）。
- `self.lm_head.weight = self.tok_embed.weight`：把 `lm_head` 的 `weight` 属性换成 embedding 的 `Parameter` 对象——两个模块持有**同一个对象**。原来 `Linear` 自己创建的权重被丢弃（会被垃圾回收）。
- `lm_head` 没有 bias（`bias=False`），与 GPT-2 一致；有 bias 的话 tying 也只共享权重部分。

```python
        position_ids = torch.arange(cfg.context_length, dtype=torch.long)
        self.register_buffer("position_ids", position_ids, persistent=False)

        self.apply(self._init_weights)
        self._scale_residual_projections()
```

- 位置 id 预先生成并注册为 buffer，前向时切片 `[:seq]`，讲义 "Cache the position id tensor, do not recompute"。它随 `.to(device)` 移动，`persistent=False` 不进 checkpoint。
- `self.apply(fn)`：递归地对自己和所有子模块调用 `fn`。注意 tying 在 `apply` **之前**完成：共享矩阵先作为 `Linear` 的权重被初始化一次，再作为 `Embedding` 的权重被初始化一次，两次都是 std 0.02，结果没有问题。

### 3.3 初始化：std 0.02 与残差投影缩放

```python
    def _init_weights(self, module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def _scale_residual_projections(self) -> None:
        scale = 1.0 / math.sqrt(2 * self.cfg.num_layers)
        for block in self.blocks:
            block.attn.out_proj.weight.data.mul_(scale)
            block.mlp.fc2.weight.data.mul_(scale)
```

- 手写的 `LayerNorm` 不是 `nn.Linear`/`nn.Embedding`，`apply` 不会碰它，保留 `scale=1`、`shift=0`。
- 残差流每层被加两次（注意力、MLP），共 `2N` 次。把两个"写入残差流"的投影缩小 `√(2N)` 倍，让残差流方差不随深度线性增长。12 层时缩放因子 `1/√24 ≈ 0.204`，std 从 0.02 变成约 0.0041；tiny 配置（2 层）实测 `out_proj` std 为 0.00999、QKV 为 0.0201。
- 我们实测（12 层、D=192）初始化时残差流标准差：有缩放增长 2.39 倍，去掉缩放增长 11.62 倍（测验 Q12）。
- `.data.mul_()`：直接修改底层数据、绕过 autograd；更现代的写法是 `with torch.no_grad(): w.mul_(scale)`。

### 3.4 前向

```python
    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        batch, seq = tokens.shape
        if seq > self.cfg.context_length:
            raise ValueError(...)
        tok = self.tok_embed(tokens)
        pos = self.pos_embed(self.position_ids[:seq])
        x = self.embed_dropout(tok + pos)
        for block in self.blocks:
            x = block(x)
        x = self.final_ln(x)
        logits = self.lm_head(x)
        return logits
```

| 步骤 | 形状（124M，B=1，T=32） |
|------|----------------------|
| `tokens` | `(1, 32)` |
| `tok` | `(1, 32, 768)` |
| `pos` | `(32, 768)`，与 `tok` 广播相加 |
| 12 个 block 后 | `(1, 32, 768)` |
| `logits` | `(1, 32, 50257)` |

- 每个位置都输出一个词表分布：训练时 T 个位置同时计算 loss，生成时只用最后一个。
- `final_ln` 是 pre-LN 结构必需的（block 输出没有归一化）。
- 未训练时 logits 接近 0、分布接近均匀：tiny 模型实测初始 loss 6.2448，`ln 512 = 6.2383`。

### 3.5 `count_parameters`：按对象 id 去重

```python
def count_parameters(model: nn.Module) -> int:
    seen: dict[int, int] = {}
    for param in model.parameters():
        seen[id(param)] = param.numel()
    return sum(seen.values())
```

- `id(obj)` 是对象在内存中的唯一标识；同一个 `Parameter` 被两个模块引用时只计一次。
- 其实 `model.parameters()` 默认已经去重（`remove_duplicate=True`）：我们实测 tiny 模型朴素求和与本函数都是 136,960；`named_parameters(remove_duplicate=False)` 才会多出 `lm_head.weight` 一项（29 vs 28）。这里的 `id()` 去重是保险，不影响结果。
- 注意 `state_dict()` 里 `tok_embed.weight` 与 `lm_head.weight` 两个键都存在（实测），只是指向同一块存储。

### 3.6 `top_k_filter`

```python
def top_k_filter(logits: torch.Tensor, top_k: int) -> torch.Tensor:
    if top_k is None or top_k <= 0:
        return logits
    top_k = min(top_k, logits.size(-1))
    values, _ = torch.topk(logits, top_k, dim=-1)
    threshold = values[..., -1:]
    return torch.where(logits < threshold, torch.full_like(logits, float("-inf")), logits)
```

- `torch.topk` 返回前 k 大的值（降序）和下标；`values[..., -1:]` 取第 k 大的值，用 `-1:` 而不是 `-1` 是为了**保留最后一维**，形状 `(B, 1)` 能与 `(B, V)` 广播比较。
- `torch.where(cond, a, b)`：条件为真取 a，否则取 b。
- `top_k=None` 或 ≤ 0 时不截断；`min(top_k, V)` 防止 k 超过词表大小时 `topk` 报错。
- ⚠️ 并列时保留数可能超过 k（`[3, 3, 3, 1, 0.5]`、k=2 实测保留 3 个）。
- 类型注解写的是 `top_k: int`，实际也接受 `None`（`generate` 中注解为 `int | None`），注解不够准确。

### 3.7 `generate`：自回归循环

```python
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    if seed is not None:
        torch.manual_seed(seed)

    was_training = model.training
    model.eval()
    tokens = prompt.clone()
    try:
        with torch.no_grad():
            for _ in range(max_new_tokens):
                window = tokens[:, -model.cfg.context_length:]
                logits = model(window)
                next_logits = logits[:, -1, :] / temperature
                next_logits = top_k_filter(next_logits, top_k)
                probs = F.softmax(next_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                tokens = torch.cat([tokens, next_token], dim=1)
        return tokens
    finally:
        model.train(was_training)
```

- **T ≤ 0 直接报错**：避免除以 0 产生 NaN（阶段 10 第 04 节的 NumPy 代码就踩了这个坑）。代价是没有贪心模式——讲义说"Temperature near zero collapses to greedy"，但这里 T=0 不可用；讲义练习 3 要求加 `greedy` 开关。
- **状态保存与恢复**：记下 `model.training`，生成时切到 `eval()`（关闭 dropout），`finally` 中无论是否异常都用 `model.train(was_training)` 恢复。这样在训练循环里调用 `generate` 做定性评估不会意外改变模型状态。
- **滑动窗口**：`tokens[:, -context_length:]` 永远只取最后 `context_length` 个；`tokens` 本身持续增长，返回完整序列。
- `torch.multinomial(probs, 1)`：按概率分布采样 1 个下标，返回 `(B, 1)`，正好可以沿 dim=1 拼接。
- ⚠️ `torch.manual_seed(seed)` 修改**全局**随机状态：我们实测调用 `generate(seed=42)` 后，外部后续的 `torch.rand` 结果被改变。更好的做法是创建独立的 `torch.Generator` 并传给 `multinomial(generator=...)`。
- ⚠️ 没有 KV cache，每步对整个窗口重新前向；没有 EOS 停止条件；没有 top-p。

### 3.8 `demo`

依次：构建 124M 模型并计数 → 用 `data_ptr()` 检查 tying → 构建 untied 模型并断言差值等于 `V × D` → 124M 模型前向一次 `(1, 32)` → tiny 模型（`vocab 512, ctx 64, d 64, 4 头, 2 层`，136,960 参数）生成 12 个 token → 80 长度的 prompt（> 64）生成 4 个 token，验证滑动窗口。

- `abs(ref_params - 124_000_000) / 124_000_000:.2%`：数字字面量里的下划线只为可读性；`:.2%` 把小数格式化为百分比（0.0035 → `0.35%`）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 精确复现 GPT-2 Small 结构（含 bias） | 参数量可以与参考值逐位核对；第 37 节能直接加载 OpenAI 权重 | 现代模型多去 bias、换 RMSNorm/SwiGLU/RoPE |
| learned 绝对位置 embedding | 与 GPT-2 一致、最简单 | 长度上限固定为 1024，生成时窗口平移导致无法复用 KV cache |
| 参数级 weight tying | 省 38.6M 参数，梯度共享 | 保存/加载/分布式切分时要维护共享关系 |
| std 0.02 + 残差投影缩放 | 与 GPT-2 一致，残差流尺度稳定 | 更大模型会用其他方案（如按宽度缩放的 μP 等） |
| 位置 id buffer | 避免每次前向分配 | 收益很小，但是好习惯 |
| `generate` 中 `try/finally` 恢复训练状态 | 可以在训练中安全调用 | — |
| T ≤ 0 报错 | 防止 NaN | 缺少贪心模式 |
| 全局 `manual_seed` | 写法简单、可复现 | 污染调用方的随机状态 |
| 无 KV cache、手写注意力 | 代码直观 | 生成慢，`O(T²)` 的权重矩阵 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 属性赋值共享参数 | `self.lm_head.weight = self.tok_embed.weight` | 两个模块引用同一个对象（"引用"不是"复制"） |
| `self.apply(fn)` | `self.apply(self._init_weights)` | 递归地对每个子模块调用函数 |
| `isinstance` 分派 | `if isinstance(module, nn.Linear): ... elif isinstance(module, nn.Embedding):` | 根据模块类型执行不同的初始化 |
| `nn.init.normal_` / `zeros_` | `nn.init.normal_(module.weight, mean=0.0, std=0.02)` | 原地初始化（自动在 no_grad 下执行） |
| `.data.mul_()` | `block.attn.out_proj.weight.data.mul_(scale)` | 绕过 autograd 原地乘法 |
| `id()` 与字典去重 | `seen[id(param)] = param.numel()` | 用对象标识作为键 |
| 联合类型 `int \| None` | `top_k: int \| None = None` | 参数可以是整数或 None |
| `try ... finally` | `generate` 中恢复 `model.train(was_training)` | 无论是否异常都执行清理 |
| `return` 在 `try` 中 | `return tokens` 后仍执行 `finally` | `finally` 总会运行 |
| 负数切片 | `tokens[:, -model.cfg.context_length:]` | 取最后 N 个 |
| 保留维度的切片 | `values[..., -1:]` | `...` 表示前面所有维度；`-1:` 保留最后一维 |
| `torch.where` | `torch.where(logits < threshold, -inf, logits)` | 按条件逐元素选择 |
| `torch.topk` | `values, _ = torch.topk(logits, top_k, dim=-1)` | 前 k 大的值与下标 |
| `torch.multinomial` | `torch.multinomial(probs, num_samples=1)` | 按概率采样 |
| `torch.cat` | `torch.cat([tokens, next_token], dim=1)` | 沿序列维拼接 |
| `data_ptr()` | `ref_model.lm_head.weight.data_ptr() == ref_model.tok_embed.weight.data_ptr()` | 底层存储地址，判断是否共享 |
| 数字字面量下划线 | `124_000_000` | 提高可读性，值不变 |
| f-string 百分比 | `{x:.2%}` | 乘 100 并加 `%` |
| `.tolist()[0]` | `prompt.tolist()[0]` | 张量转嵌套列表再取第一行 |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU，约 11.6 秒，主要耗时在构建两个大模型）：

```text
Building 124M reference GPT...
  reference params         : 124,439,808
  expected near 124M       : within 5% target 0.35%
  weight tying enforced    : True

Untying and re-counting to confirm the 38M delta...
  untied params            : 163,037,184
  delta                    : 38,597,376
  expected (vocab*d_model) : 38,597,376

Single forward through 124M reference, batch 1, seq 32...
  logits shape             : (1, 32, 50257)

Generating with a tiny model end to end (faster demo)...
  tiny params              : 136,960
  prompt                   : [1, 2, 3, 4, 5]
  generated tokens         : [1, 2, 3, 4, 5, 436, 498, 383, 383, 498, 202, 270, 435, 490, 9, 433, 202]

Sliding window check: prompt longer than context...
  long prompt shape        : (1, 80)
  generated shape          : (1, 84)

Model assembly check passed.
```

逐项解读：

- **124,439,808**：token 表 38,597,376 + 位置表 786,432 + 12 × 7,087,872 + `final_ln` 1,536，与 Hugging Face GPT-2 的参数量完全一致。打印的 "within 5% target 0.35%" 是与 124,000,000 这个整数的偏差。
- **163,037,184 − 124,439,808 = 38,597,376**：正好是 `50257 × 768`。
- **logits `(1, 32, 50257)`**：每个位置一个完整词表分布。
- **tiny 参数 136,960**：`512×64 + 64×64 + 2 × 49,984 + 128`，其中一个 64 维 block 为 `12×64² + 9×64 + 4×64 = 49,984`。
- **生成的 token**：模型未训练，输出是 top-20 内的随机采样；出现 `383, 383`、`498 ... 498` 的重复只是巧合。讲义说"generated token ids from a random prompt"，实际 prompt 是固定的 `[1,2,3,4,5]`。
- **滑动窗口**：80 > 64 的 prompt 不报错，返回 84 个 token。
- 讲义学习目标提到"Measure ... forward pass cost against the 124M target"，但 demo 并没有测量耗时或 FLOPs，只做了一次前向。

---

## 7. 动手改一改

1. **讲义练习 1**：`GPTConfig(weight_tying=False)` 并重新计数，确认差值 38,597,376（demo 已经做了）；再检查 untied 模型 `lm_head.weight` 的 `data_ptr()` 不同。
2. **讲义练习 2**：用第 32 节的 sinusoidal 表替换 `pos_embed`（注册为 buffer），确认能前向且参数量变为 123,653,376（少 786,432）。
3. **讲义练习 3 + 5**：给 `generate` 加 `greedy` 与 `top_p` 参数，验证贪心结果与 seed 无关、top-p 保留集合的概率和 ≥ p（参考测验 Q11）。
4. **讲义练习 4（注意修正）**：实现 repetition penalty，正 logit 除以 penalty、负 logit 乘以 penalty，而不是讲义说的一律"除以"；在固定 prompt 上统计重复次数随 penalty 的变化。
5. **验证残差缩放**：逐层打印残差流标准差，对比有/无 `_scale_residual_projections`（我们实测 12 层时 2.39× vs 11.62×）。
6. **进阶**：为 `MultiHeadAttention` 加 KV cache，在窗口未满时实现增量生成；窗口满后思考为什么 learned 绝对位置会让缓存失效。

---

## 8. 常见坑

- **tying 写成复制**：`self.lm_head.weight.data.copy_(self.tok_embed.weight.data)` 只在初始化时相同，之后各自更新（讲义 "Tie weights at parameter level, not just by copying"）。
- **tying 后重新创建 `lm_head`**：之后再 `self.lm_head = nn.Linear(...)` 会悄悄解除共享。
- **加载权重破坏共享**：`load_state_dict` 会把两个键的值依次拷进同一张量，通常没问题；但若手工替换 `Parameter` 对象（如 `model.tok_embed.weight = nn.Parameter(w)`），`lm_head` 仍指向旧对象，共享被打破。
- **数参数时重复计数**：自己遍历 `state_dict()` 求和会把共享矩阵算两次。
- **忘记 `final_ln`**：pre-LN 结构的最后一个 block 输出没有归一化，直接接 LM head 会让 logits 尺度失控。
- **位置超出上限**：输入超过 `context_length` 时 `forward` 报错；生成时必须截断窗口。
- **生成时没切 `eval()`**：dropout 仍在工作，输出更随机且不可复现（本节用 `try/finally` 处理了）。
- **用 `torch.manual_seed` 做局部可复现**：会影响调用方之后的所有随机数。

---

## 9. 测试在验证什么

`tests/test_model.py` 共 11 个 `unittest` 测试，用 `pathlib` 把 `code/` 加入 `sys.path` 后导入。实际运行：`python3 -m pytest -q` → `11 passed in 2.89s`（其中一个测试会构建 124M 模型）。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `ShapeTests` | `test_forward_returns_vocab_logits` | `(2,16)` → `(2,16,V)` |
| | `test_sequence_overflow_raises` | T=16 > 8 时 `forward` 报错 |
| `WeightTyingTests` | `test_tied_model_shares_storage` | tying 时两者 `data_ptr()` 相同 |
| | `test_untied_model_does_not_share_storage` | 不 tying 时不同 |
| | `test_untie_increases_parameter_count_by_vocab_times_dmodel` | 差值 = `V × D`（tiny 配置为 `128 × 64`） |
| `GenerationTests` | `test_generate_appends_requested_tokens` | 输出长度 = prompt + `max_new_tokens` |
| | `test_top_k_filter_keeps_exactly_k` | `[1,5,2,4,3]`、k=2 只保留 5 和 4（值互不相同，测不出并列情况） |
| | `test_temperature_must_be_positive` | T=0 报错 |
| | `test_sliding_window_handles_long_prompt` | prompt 40 > context 16 仍能生成 |
| | `test_seeded_generation_is_reproducible` | 相同 seed 两次生成完全相同 |
| `ParameterCountTests` | `test_124m_reference_parameter_count_in_range` | 参数量在 1.2 亿到 1.3 亿之间（比 demo 的精确核对宽松得多） |

测试没有覆盖的地方：残差投影缩放是否生效、`generate` 结束后训练状态是否恢复、tying 后梯度是否累加到同一参数、`top_k` 并列、`generate` 对全局随机状态的副作用。
