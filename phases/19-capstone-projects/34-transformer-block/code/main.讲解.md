# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 34 节 从零实现 Transformer 模块 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m pytest -q` 或 `python3 tests/test_block.py` ｜ **依赖**：`torch`（第三方，CPU 即可）；`math`、`dataclasses`（标准库）

---

## 1. 这份代码在考察什么

这是"从零搭 GPT"系列的第五步：把第 33 节的注意力层包装成一个完整的 Transformer block。代码考察：

1. **Block 的四个零件**：手写 LayerNorm、融合 QKV 的多头因果注意力、逐位置 MLP（GELU）、两条残差连接。
2. **Pre-LN 与 Post-LN**：同一个类用 `pre_ln` 开关切换两种 LN 摆放方式。
3. **配置对象**：用一个 `BlockConfig` dataclass 统一传递超参数（下一节的 `GPTConfig` 沿用这种做法）。
4. **生产细节**：布尔 mask buffer、`resid_dropout`、`bias` 开关。
5. **对比实验**：构建 6 层 pre-LN 栈与 6 层 post-LN 栈（相同权重），比较一次反传后 embedding 的梯度范数。

> 一句话：**写出一个可以直接堆叠的 GPT block，并对比两种 LayerNorm 摆放**。但要清醒地看到：demo 的梯度对比使用了一个几乎为常数的 loss，**"210 倍"这个数字不能证明 pre-LN 更好训练**（第 3.6 节与第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BlockConfig` | dataclass | d_model、头数、上下文长度、MLP 倍数、两种 dropout、bias、pre_ln | 超参数集中管理 |
| `LayerNorm` | `nn.Module` | 沿最后一维减均值、除以 `√(有偏方差 + eps)`，再 `scale`/`shift` | 层归一化 |
| `MultiHeadAttention` | `nn.Module` | 融合 QKV（`split`）、拆头、缩放点积、布尔因果 mask、softmax、dropout、合头、输出投影、残差 dropout | 因果多头注意力 |
| `FeedForward` | `nn.Module` | `Linear(D,4D)` → GELU(tanh) → `Linear(4D,D)` → dropout | 逐位置 MLP |
| `TransformerBlock` | `nn.Module` | 根据 `pre_ln` 选择两种组合方式 | Pre-LN / Post-LN |
| `BlockStack` | `nn.Module` | `Embedding(128, D)` → N 个 block → `final_ln`（无位置编码、无 LM head） | 演示用的栈 |
| `gradient_norm_at_embedding` | 函数 | 一次前向 + `out.pow(2).sum()` 反传，返回 embedding 梯度范数 | 梯度流"诊断" |
| `_set_eval_mode` | 函数 | 调 `stack.eval()` 关闭 dropout | 确定性 |
| `demo` | 函数 | 构建两栈、复制权重、对比形状与梯度、打印参数量 | 演示 |

数据流：`tokens (2,32)` → `embed` `(2,32,192)` → 6 × block（形状不变）→ `final_ln` → `(2,32,192)` → `pow(2).sum()` 标量 → `backward()` → `embed.weight.grad` 的范数。

---

## 3. 逐段精讲

### 3.1 `BlockConfig`：一个对象装下所有超参数

```python
@dataclass
class BlockConfig:
    d_model: int = 768
    num_heads: int = 12
    context_length: int = 1024
    mlp_expansion: int = 4
    attn_dropout: float = 0.1
    residual_dropout: float = 0.1
    use_bias: bool = True
    pre_ln: bool = True
```

- 默认值就是 GPT-2 Small 的 block。每个子模块构造时都接收整个 `cfg`，只取自己需要的字段——加一个新超参数时不用改一串函数签名。
- 测试里的 `_cfg(**overrides)` 先建一个基础字典再 `update`，最后 `BlockConfig(**base)` 解包成关键字参数，这是测试中常见的"默认值 + 局部覆盖"写法。

### 3.2 手写 LayerNorm

```python
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mean = x.mean(dim=-1, keepdim=True)
        var = x.var(dim=-1, keepdim=True, unbiased=False)
        return self.scale * (x - mean) / torch.sqrt(var + self.eps) + self.shift
```

- 每个 token 独立归一化（只在 D 维上统计），与 batch 无关。
- `unbiased=False`：除以 N 而不是 N−1，与 `nn.LayerNorm` 一致（我们实测与 `nn.LayerNorm(64)` 的输出 `allclose`）。
- 参数名用 `scale`/`shift`（而不是 PyTorch 的 `weight`/`bias`）。第 37 节加载 GPT-2 权重时需要做名字映射。
- `eps` 放在根号里面，防止方差为 0 时除零。

### 3.3 `MultiHeadAttention`：与第 33 节的三处差异

```python
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=cfg.use_bias)
        self.out_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=cfg.use_bias)
        self.attn_dropout = nn.Dropout(cfg.attn_dropout)
        self.resid_dropout = nn.Dropout(cfg.residual_dropout)

        mask = torch.triu(
            torch.ones(cfg.context_length, cfg.context_length, dtype=torch.bool),
            diagonal=1,
        )
        self.register_buffer("causal_mask", mask, persistent=False)
```

1. **布尔 mask，语义反过来**：第 33 节存的是"允许看"的下三角（float 1），用 `mask == 0` 选未来；这里直接存"要屏蔽"的严格上三角（`True` = 屏蔽），`masked_fill(mask, -inf)`。布尔张量每个元素 1 字节，比 float32 省 4 倍（L=1024 时 1 MiB）。
2. **`split` 代替 `chunk`**：`qkv.split(self.d_model, dim=-1)` 按"每块 d_model 大"切分，结果与 `chunk(3)` 相同。
3. **多了 `resid_dropout`**：`out_proj` 之后再做一次 dropout（GPT-2 参考实现的做法）。

```python
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.head_dim)
        mask = self.causal_mask[:seq, :seq]
        scores = scores.masked_fill(mask, float("-inf"))
        attn = F.softmax(scores, dim=-1)
        attn = self.attn_dropout(attn)

        out = attn @ v
        out = out.transpose(1, 2).contiguous().view(batch, seq, dim)
        out = self.out_proj(out)
        out = self.resid_dropout(out)
```

形状（demo：B=2, T=32, D=192, H=6, head_dim=32）：`qkv (2,32,576)` → q/k/v 各 `(2,6,32,32)` → `scores (2,6,32,32)` → `out (2,6,32,32)` → 合头 `(2,32,192)`。

- ⚠️ 没有检查 `dim == d_model`（第 33 节检查了）；维度不对时会在 `self.qkv(x)` 报 PyTorch 的矩阵形状错误。

### 3.4 `FeedForward`：逐位置 MLP

```python
        hidden = cfg.mlp_expansion * cfg.d_model
        self.fc1 = nn.Linear(cfg.d_model, hidden, bias=cfg.use_bias)
        self.act = nn.GELU(approximate="tanh")
        self.fc2 = nn.Linear(hidden, cfg.d_model, bias=cfg.use_bias)
        self.dropout = nn.Dropout(cfg.residual_dropout)
```

- `nn.Linear` 只作用于最后一维，所以 `(B, T, D)` 的每个位置独立计算：**token 之间的信息交换只在注意力里发生**。
- `approximate="tanh"`：`0.5x(1 + tanh(√(2/π)(x + 0.044715x³)))`，GPT-2 原版就是这个近似；与精确 GELU 在 `[-3, 3]` 上最大差约 4.7e-4（实测）。
- MLP 的参数是注意力的两倍（`8D²` vs `4D²`），block 的大部分参数在这里。

### 3.5 `TransformerBlock`：一个开关两种结构

```python
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.pre_ln:
            x = x + self.attn(self.ln1(x))
            x = x + self.mlp(self.ln2(x))
        else:
            x = self.ln1(x + self.attn(x))
            x = self.ln2(x + self.mlp(x))
        return x
```

| | Pre-LN | Post-LN |
|---|---|---|
| LN 位置 | 子层之前，残差支路内 | 残差相加之后，主干上 |
| block 输出 | 未归一化，残差流方差随深度增长 | 每层都被归一化（实测标准差 1.0000） |
| 反传 | 主干是恒等路径，`∂y/∂x = I + ∂F/∂x` | 每层都要乘 LN 的雅可比 |
| 需要 `final_ln` | 需要 | 原始论文不需要（本节 `BlockStack` 仍然加了） |

- 两种结构的参数完全相同（同样的 `ln1/attn/ln2/mlp`），所以 demo 能用 `load_state_dict` 把 pre-LN 栈的权重复制给 post-LN 栈，做"只差 LN 位置"的对照。
- 我们实测 12 层 pre-LN 栈在初始化时残差流标准差从 1.01 逐层增至 1.37——这就是讲义说的"The residual connection carries the unnormalized signal forward"。

### 3.6 `BlockStack` 与梯度"诊断"

```python
class BlockStack(nn.Module):
    def __init__(self, cfg: BlockConfig, depth: int) -> None:
        super().__init__()
        self.embed = nn.Embedding(num_embeddings=128, embedding_dim=cfg.d_model)
        self.blocks = nn.ModuleList([TransformerBlock(cfg) for _ in range(depth)])
        self.final_ln = LayerNorm(cfg.d_model)
```

- `nn.ModuleList` 让列表里的每个 block 被注册为子模块（普通 Python list 不会，参数会"丢失"）。
- 词表固定为 128、**没有位置编码**、embedding 用 PyTorch 默认的 `N(0, 1)` 初始化——只是演示用。

```python
def gradient_norm_at_embedding(stack: BlockStack, tokens: torch.Tensor) -> float:
    stack.zero_grad(set_to_none=True)
    out = stack(tokens)
    loss = out.pow(2).sum()
    loss.backward()
    grad = stack.embed.weight.grad
    if grad is None:
        return 0.0
    return float(grad.norm().item())
```

- `zero_grad(set_to_none=True)`：把 `.grad` 设为 `None` 而不是置零，省内存，也能区分"没有梯度"和"梯度为 0"。
- ⚠️ **核心问题**：`out` 是 `final_ln` 的输出（`scale=1, shift=0`），每个 token 满足 `Σ y² = D·var/(var+eps) ≈ D`。整个 loss ≈ `B·T·D = 2×32×192 = 12288`，我们实测 pre-LN 为 12287.91、post-LN 为 12287.88——**loss 几乎与输入无关**，梯度只来自 `eps` 引起的微小偏差。所以两个梯度范数都非常小（0.0023、0.000011），比值反映的是数值细节而非梯度流：
  - 把深度改成 1、6、12，比值分别是 256.8×、210.2×、162.9×（实测）——越浅比值越大，与"深层 post-LN 梯度衰减"的解释相反；
  - 把 loss 换成 `(out * R).sum()`（R 为固定随机张量），三个深度下比值都约为 **1.00**（实测 113.54/113.52、109.84/109.33、113.32/113.97）。
- 因此 docstring 和讲义中"pre-LN 的 embedding 梯度大一个数量级，这是 pre-LN 无需 warmup 的经验信号"这一结论**不被这个 demo 支持**；而且 demo 根本没有训练，也不涉及学习率。真正能体现差别的是训练动态（第 7 节练习 1，结果见测验 Q12）。

### 3.7 `demo`：对照实验的搭建

```python
    pre_stack = BlockStack(cfg_pre, depth=depth)
    post_stack = BlockStack(cfg_post, depth=depth)

    post_stack.load_state_dict(pre_stack.state_dict())
    _set_eval_mode(pre_stack)
    _set_eval_mode(post_stack)
```

- 两个配置只差 `pre_ln`，两种结构的参数名与形状完全一致，`load_state_dict` 可以直接复制——这是做"控制变量"对照的好习惯。
- dropout 已经设为 0，`eval()` 是双保险。
- 参数量 `2,694,144 = 6 × 444,864 + 128×192 + 2×192`（实测）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一个 `pre_ln` 开关 | 同一份代码对比两种结构 | 生产代码只保留 pre-norm，避免分支 |
| 手写 LayerNorm | 看清 eps 位置与参数形状 | 比 `nn.LayerNorm` 的融合 kernel 慢；参数名与 PyTorch 不同，加载权重要映射 |
| 布尔 mask buffer | 只分配一次，比 float 省 4 倍内存 | 仍是 `O(L²)`；生产用 `is_causal=True` |
| GELU tanh 近似 | 与 GPT-2 一致 | LLaMA 系换成 SwiGLU |
| 三处 dropout | 与 GPT-2 参考实现一致 | 讲义写"两处"，与代码不符；大模型预训练常设为 0 |
| `use_bias` 开关 | 支持讲义练习 1 | 去 bias 只省约 0.07% 参数，动机主要是工程简化 |
| `BlockStack` 无位置编码、embedding `N(0,1)` | demo 足够 | 不是可训练的语言模型；下一节补齐 |
| 用 `out.pow(2).sum()` 衡量梯度 | 简单 | LN 输出的平方和≈常数，结论无效；应使用随机读出或真实训练 loss |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 带默认值 | `class BlockConfig` | 自动生成 `__init__`，`BlockConfig(d_model=192, pre_ln=False)` 只覆盖部分字段 |
| 文档字符串 | `"""Layer normalization with learnable scale and shift..."""` | 类和函数的说明，`help()` 可以看到 |
| `nn.Parameter` | `self.scale = nn.Parameter(torch.ones(d_model))` | 把张量登记为可训练参数 |
| `keepdim=True` | `x.mean(dim=-1, keepdim=True)` | 规约后保留维度，便于广播 |
| `torch.Tensor.split` | `qkv.split(self.d_model, dim=-1)` | 按固定大小切分，返回元组 |
| 布尔 `dtype` | `torch.ones(L, L, dtype=torch.bool)` | 布尔张量作为 mask |
| `masked_fill` 布尔 mask | `scores.masked_fill(mask, float("-inf"))` | `True` 的位置被填充 |
| 方法链 | `q.view(...).transpose(1, 2)` | 连续调用，每步返回新张量 |
| `nn.ModuleList` | `nn.ModuleList([TransformerBlock(cfg) for _ in range(depth)])` | 注册一组子模块 |
| 链式比较 | `assert pre_out.shape == post_out.shape == (2, 32, 192)` | 等价于两个 `==` 用 `and` 连接 |
| `torch.Size` 与元组比较 | `out.shape == (2, 32, 192)` | `torch.Size` 是元组子类 |
| `state_dict` / `load_state_dict` | `post_stack.load_state_dict(pre_stack.state_dict())` | 复制所有参数与持久 buffer |
| `zero_grad(set_to_none=True)` | `gradient_norm_at_embedding` | 清梯度 |
| `float(tensor.item())` | `float(grad.norm().item())` | 张量 → Python 数字 |
| f-string 格式符 | `{pre_grad:.6f}`、`{ratio:.2f}x`、`{n_params:,}` | 小数位数、千分位 |
| `**kwargs` 解包 | 测试中 `BlockConfig(**base)`、`_cfg(**overrides)` | 字典转关键字参数 / 收集关键字参数 |
| `pathlib.Path` | 测试中 `Path(__file__).resolve().parent.parent` | 面向对象的路径操作 |
| `if __name__ == "__main__":` | 文件末尾调用 `demo()` | 被 import 时不运行 demo |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU，约 1.9 秒）：

```text
Pre-LN output shape : (2, 32, 192)
Post-LN output shape: (2, 32, 192)
Pre-LN  embedding grad norm: 0.002251
Post-LN embedding grad norm: 0.000011
Pre-LN / Post-LN ratio    : 210.24x
Stack parameter count     : 2,694,144
Block check passed.
```

逐项解读：

- **形状**：两种结构都保持 `(B, T, D)`，可以任意堆叠。
- **两个梯度范数都极小**：因为 loss ≈ 12288 是常数（3.6 节）。如果梯度流真的正常，用对输出敏感的 loss 时 embedding 梯度范数是 100 量级（随机读出实验约 110）。
- **210 倍不是 pre-LN 的优势证据**：换成随机读出 loss，比值约 1.00；深度 1 时退化 loss 的比值反而更大（256.8×）。
- **参数量** `2,694,144`：6 个 block 各 444,864，加 embedding 24,576 与 `final_ln` 384。

我们另外做了一个**训练**对照实验（12 层、D=192、6 头，Adam 无 warmup，300 步，重复片段语言建模任务，见测验 Q12）：lr = 3e-4 时两者都能学到 loss ≈ 0.6；lr = 1e-3 时 pre-LN 降到 0.55，post-LN 卡在 4.88（≈ `ln 128`，等于什么都没学到）。这才是讲义想说明的现象。

---

## 7. 动手改一改

1. **修正对比实验**：把 `gradient_norm_at_embedding` 的 loss 改成 `(out * R).sum()` 或"加 LM head 的交叉熵"，分别在 depth = 1、6、12 下比较两种结构；再做一个真正的训练对比（lr = 1e-3、无 warmup），然后给 post-LN 加 100 步线性 warmup，看它能否恢复。
2. **讲义练习 1**：令 `BlockConfig(use_bias=False)`，验证 768 维 block 从 7,087,872 降到 7,080,960，12 层共省 82,944。
3. **讲义练习 2**：手写 RMSNorm 替换 `LayerNorm`，与 `nn.RMSNorm` 对比数值，并确认输出形状不变（参考测验 Q10）。
4. **讲义练习 3**：给 `MultiHeadAttention.forward` 加 `return_first_head` 开关，在 dropout 之前取 `attn[:, 0]`，验证上三角为 0（参考测验 Q11）。
5. **讲义练习 4**：`(2, 16, 384)`、`H=6`，相同权重、dropout 为 0，断言两种结构输出 `not torch.allclose`（我们实测成立：pre-LN 输出标准差 1.024，post-LN 为 1.000）。
6. **进阶**：把 `FeedForward` 换成 SwiGLU（隐藏宽度取 `8D/3` 并取整），检查参数量与原 MLP 接近。

---

## 8. 常见坑

- **用 LN 输出的范数/平方和当 loss**：结果几乎是常数，梯度没有意义（本节 demo 就踩了这个坑）。
- **post-LN 栈末尾再加 `final_ln`**：输出被连续归一化两次，第二个 LN 几乎是恒等变换。
- **用普通 list 存 block**：`self.blocks = [Block() for ...]` 的参数不会被 `parameters()` 收集，优化器不会更新它们。
- **`torch.std` 与 LN 方差口径不同**：测 LN 输出时 `std()` 默认无偏，D 小时差异明显（D=64 时 0.8%）。
- **mask 语义混淆**：第 33 节的 mask 是"1 = 可看"，本节是"True = 屏蔽"，混用会把模型变成"只能看未来"。
- **eval 忘记关 dropout**：对照实验或评估前务必 `model.eval()`。
- **残差上加 dropout**：`x = dropout(x) + f(x)` 会破坏恒等路径。

---

## 9. 测试在验证什么

`tests/test_block.py` 共 10 个 `unittest` 测试，用 `pathlib` 把 `code/` 加入 `sys.path` 后导入。实际运行：`python3 -m pytest -q` → `10 passed in 1.29s`。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `LayerNormTests` | `test_output_shape_matches_input` | 形状不变 |
| | `test_normalizes_last_dim_to_zero_mean_unit_var` | 对 `randn*5+3` 的输入，输出每个 token 均值≈0（atol 1e-5）、标准差≈1（atol 1e-2，容差放宽是因为 `std()` 无偏，实际约 1.0079） |
| `MultiHeadAttentionTests` | `test_invalid_head_count_raises` | `64 % 5 != 0` 报错 |
| | `test_causal_mask_blocks_future_tokens` | 扰动位置 5 之后的输入：前 5 个位置输出不变、后面的位置**必须**变化（双向检查，能同时发现"mask 失效"和"mask 过度"） |
| | `test_sequence_longer_than_context_raises` | T=16 > 8 报错 |
| `FeedForwardTests` | `test_expansion_width_is_four_d_model` | `fc1` 输出与 `fc2` 输入为 `4D`，`fc2` 输出为 D |
| `TransformerBlockTests` | `test_output_shape_matches_input` | block 形状不变 |
| | `test_pre_ln_and_post_ln_differ` | 相同权重下两种结构输出不同（讲义练习 4） |
| `GradientFlowTests` | `test_embedding_gradient_is_nonzero_for_pre_ln_stack` | 4 层 pre-LN 栈 embedding 梯度 > 0 且非 NaN/Inf |
| | `test_both_variants_run_forward_without_error` | 两种结构 3 层栈都能前向 |

测试没有覆盖的地方：没有测 post-LN 的梯度、没有检查"pre-LN 梯度更大"这一 demo 的核心论断（这也说明它无法被可靠测试）；`GradientFlowTests` 用的仍是退化的平方和 loss，梯度虽然非零但数值极小，只能说明"计算图是连通的"。
