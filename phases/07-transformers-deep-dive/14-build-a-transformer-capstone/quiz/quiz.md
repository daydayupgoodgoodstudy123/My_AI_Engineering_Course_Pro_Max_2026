# 测验 · 从零构建 Transformer——综合项目（Build a Transformer from Scratch — The Capstone）

> **阶段 07 · Transformers 深入 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | decoder-only 全流程 | `(B, N)` token id → token embedding + 位置 embedding → L 个 Block → 最终 RMSNorm → lm_head → `(B, N, V)` logits |
| 2 | Pre-norm 残差 | `x = x + attn(norm(x))`、`x = x + ffn(norm(x))`：归一化在子层**之前**，残差主干是恒等映射，深层训练更稳 |
| 3 | RMSNorm | `weight · x / √(mean(x²) + eps)`：不减均值、没有 bias，比 LayerNorm 便宜，是现代 LLM 默认 |
| 4 | SwiGLU FFN | `w2(silu(w1·x) ⊙ w3·x)`，三个矩阵；隐藏层取 `≈ 8/3·d ≈ 2.67·d`，参数量与经典 4d 两矩阵 FFN 持平 |
| 5 | 因果多头 attention | 一个 `qkv` 线性层一次算出 Q、K、V，拆头 → `QKᵀ/√d_head` → 下三角 mask 填 `-inf` → softmax → 乘 V → 合头 → 输出投影 |
| 6 | 权重绑定（tied embeddings） | `lm_head.weight = tok_emb.weight`，输入输出共用一个 `V×d` 矩阵，省下 V·d 个参数 |
| 7 | 错位一位的交叉熵 | `y` 就是 `x` 向右平移一位；每个位置都预测下一个 token，`(B·N, V)` 与 `(B·N,)` 做 `cross_entropy` |
| 8 | 训练配方 | AdamW（`betas=(0.9, 0.95)`、`weight_decay=0.1`）+ 梯度裁剪 1.0 + 90/10 训练/验证切分 + 定期评估 |
| 9 | 自回归采样 | 截断到 `block_size` → 取最后一个位置 → 除以 temperature → top-k 过滤 → `multinomial` 抽样 → 拼接；无 KV cache 时每步重算整段前缀 |
| 10 | 参数量估算 | 每层 `4d²`（attention）+ `3·d·h`（SwiGLU）+ `2d`（两个 RMSNorm），加上 embedding；nano 配置（4 层、d=128）约 80 万 |

### 核心技能（能动手做到）

- [ ] 从零写出 `RMSNorm`、`CausalSelfAttention`、`SwiGLUFFN`、`Block`、`GPT`，并能逐行说出每个张量的形状
- [ ] 用公式手算参数量，再与 `sum(p.numel() for p in model.parameters())` 对上，能解释权重绑定和最终 norm 带来的差异
- [ ] 写出 `get_batch`：随机取窗口，`x` 与 `y` 错开一位
- [ ] 写出 `generate`：截断上下文、temperature、top-k、`torch.multinomial`
- [ ] 做"第 0 步 loss ≈ ln(V)"的健全性检查，并能定位初始化问题
- [ ] 给训练循环加上 warmup + cosine 学习率调度
- [ ] 读懂 train/val loss 曲线，判断是欠拟合、正常还是过拟合

---

## 二、基础自测（选择题）

**Q1.** 本节 `Block.forward` 写成 `x = x + self.attn(self.n1(x))`。相比原始 Transformer 的 post-norm（`x = norm(x + attn(x))`），pre-norm 最主要的好处是：

- A. 参数更少
- B. 残差主干上没有归一化，梯度可以沿恒等路径直达底层，深层网络训练更稳定
- C. 推理时不再需要归一化层
- D. 可以去掉 causal mask

**Q2.** 下面关于本节 `RMSNorm` 的说法，正确的是：

- A. 它先减去均值，再除以标准差
- B. 它只除以均方根，不减均值，只有一个可学习的缩放向量 `weight`，没有 bias
- C. 它在 batch 维度上做归一化
- D. `eps` 是为了让输出均值为 0

**Q3.** `SwiGLUFFN` 的隐藏层宽度取 `int(d * 2.67)`，而经典 FFN 常用 `4d`。取 2.67 的原因是：

- A. 2.67 是 SiLU 函数的最大值
- B. SwiGLU 有三个矩阵，取 `h ≈ 8d/3` 时 `3·d·h ≈ 2·d·4d`，与经典两矩阵 FFN 参数量持平
- C. 为了让隐藏层宽度是 2 的幂
- D. 这是 head 数的整数倍

**Q4.** 对 `base` 配置（V = 50257，d = 768），把 `lm_head` 和 `tok_emb` 绑定能省下大约多少参数？

- A. 约 0.6M
- B. 约 2.4M
- C. 约 38.6M
- D. 约 77M

**Q5.** `CausalSelfAttention` 用 `self.register_buffer("mask", ...)` 保存下三角矩阵，而不是 `nn.Parameter` 或普通属性。主要原因是：

- A. buffer 会参与梯度更新
- B. buffer 会随 `model.to(device)` 一起搬到 GPU 并写进 `state_dict`，但不会被优化器训练
- C. buffer 可以自动扩展到任意长度
- D. 普通属性无法保存 tensor

**Q6.** `generate` 里每一步都先做 `idx_cond = idx[:, -self.block_size:]`。如果删掉这一行，生成超过 `block_size` 个 token 后会：

- A. 自动切换成滑动窗口 attention
- B. 正常运行，只是变慢
- C. 报错：位置 embedding 只有 `block_size` 个位置，mask 也只有 `block_size × block_size`
- D. 生成结果变成全是同一个字符

**Q7.** 讲义说 65 个字符的 char-level 模型"随机初始化时 loss 约 4.2"。这个数字来自：

- A. `log₂(65)`
- B. `ln(65) ≈ 4.17`，即对 65 个字符做均匀预测时的交叉熵
- C. `65 / 16`
- D. AdamW 的默认学习率

**Q8.** 本节的 `generate` 没有 KV cache。生成第 t 个 token 时，它的主要开销是：

- A. 只计算新 token 的 Q、K、V
- B. 把当前整段前缀（最多 `block_size` 个 token）重新前向一遍，前面 token 的 K、V 全部重算
- C. 只重算最后一层
- D. 只重算 embedding 层

---

## 三、动手 / 代码题

**Q9.** 设 `B=16, N=64, D=64, h=4`，逐行写出下面每个变量的形状，并解释为什么 `.view(B, N, D)` 前必须先 `.contiguous()`：

```python
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

**Q10.** `param_count` 给 nano 配置算出 811904。请对照 `GPT` 类的实际结构找出公式里一处与模型不一致的地方，并说明对实际训练配置（嵌入摘录 V=46、d=64、L=3、block_size=64）会差多少。

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

**Q11.** 用嵌入摘录训练时（V = 46），第 0 步打印的 `train` loss 会接近 `ln(46) ≈ 3.83` 吗？请结合 `GPT.__init__` 中的这两行分析，并给出修复方法：

```python
            self.tok_emb = nn.Embedding(vocab_size, d)
            # ...
            self.lm_head = nn.Linear(d, vocab_size, bias=False)
            self.lm_head.weight = self.tok_emb.weight  # tied
```

**Q12.** 讲义声称训练循环带 cosine 学习率调度，但代码里 `lr = 3e-4` 全程不变。请写一个 `get_lr(step)`（线性 warmup 50 步，然后余弦衰减到峰值的 10%），并说明怎么接进训练循环。

---

## 四、面试高频题

**Q13.**（基础必考）请手写（或口述）一个现代 decoder-only Transformer Block 的 forward，并解释 pre-norm、RMSNorm、SwiGLU、去掉 bias、权重绑定各自为什么成为默认选择。

**Q14.**（原理深挖）causal self-attention 里：为什么要除以 `√d_head`？mask 为什么填 `-inf` 而不是 0？如果 mask 写反（用了上三角）会出现什么现象？

**Q15.**（工程实践）你从零写的 GPT 训练时 loss 不降、或者突然变成 NaN、或者有尖峰，你会按什么顺序排查？

**Q16.**（场景设计）要把本节的 char-level nano 模型升级成一个能写流畅英文的 125M 参数 GPT，你会改哪些东西？给出一个优先级清单。

**Q17.**（追问型）本节 `generate` 没有 KV cache。加上 KV cache 后复杂度怎么变？实现时要注意哪些细节？显存怎么估算？

---

## 五、参考答案与解析

### Q1 — 答案：B

Pre-norm 把归一化放到子层内部，残差相加之后不再归一化，所以从输出到输入存在一条"纯加法"的恒等路径，梯度不会被每层的 norm 反复缩放，深层网络更稳、对 warmup 的依赖更小。A 错：两者参数量相同。C 错：norm 仍在。D 与 mask 无关。代价是 pre-norm 的残差流幅度随层数增长，所以需要最后那个 `norm_f`。

### Q2 — 答案：B

代码是 `rms = x.pow(2).mean(-1, keepdim=True).add(self.eps).sqrt()`，再 `self.weight * (x / rms)`：只除以均方根，沿最后一维（特征维）计算，不减均值，没有 bias。A 描述的是 LayerNorm；C 描述的是 BatchNorm；D 错，`eps` 是防止除以 0。

### Q3 — 答案：B

经典 FFN：`d→4d→d`，参数 `2·d·4d = 8d²`。SwiGLU 有 `w1、w3`（d→h）和 `w2`（h→d）三个矩阵，参数 `3dh`。令 `3dh = 8d²` 得 `h = 8d/3 ≈ 2.67d`。这样对比实验时"参数量相同"，SwiGLU 的收益来自门控结构本身。

### Q4 — 答案：C

不绑定时 lm_head 需要一个独立的 `V×d` 矩阵：`50257 × 768 = 38,597,376 ≈ 38.6M`，约占 `base` 配置 123.7M 的 31%。词表越大、模型越小，绑定的节省比例越高。D 是把两份都算进去了。

### Q5 — 答案：B

`register_buffer` 注册的 tensor 属于模块状态：`.to(device)` 时一起搬运、`state_dict()` 时一起保存，但不在 `model.parameters()` 里，优化器不会更新它。如果用 `nn.Parameter`，mask 会被当成可训练权重（还会被 weight decay）；如果用普通属性，`.to("cuda")` 后 mask 还留在 CPU，会触发设备不一致错误。C 错：buffer 大小固定为 `block_size × block_size`。

### Q6 — 答案：C

`pos_emb = nn.Embedding(block_size, d)` 只有 `block_size` 行，`torch.arange(N)` 中超出的位置会触发索引越界；`self.mask[:, :, :N, :N]` 也只能切到 `block_size`，与 `att` 的形状对不上。截断到最后 `block_size` 个 token 是"固定上下文窗口"模型的标准做法。

### Q7 — 答案：B

如果模型对所有字符给出均匀分布，每个位置的交叉熵就是 `−ln(1/V) = ln V`。V=65 时约 4.17。PyTorch 的 `cross_entropy` 用自然对数，所以不是 A。这个数是检查初始化是否正常的基准线（见 Q11）。

### Q8 — 答案：B

每一步都调用 `self(idx_cond)`，对整个窗口做完整前向，前面 token 的 K、V 在每一步都被重新计算，单步 attention 开销与前缀长度的平方成正比。KV cache 把历史 K、V 存下来，新一步只算一个新 token 的 Q/K/V，attention 只做一行。讲义练习 3 预计在笔记本上能快 5–20 倍。

### Q9 — 参考答案

| 变量 | 形状 | 说明 |
|------|------|------|
| `x` | `(16, 64, 64)` | B, N, D |
| `self.qkv(x)` | `(16, 64, 192)` | 一个线性层一次算出 Q、K、V |
| `q, k, v`（split 后） | 各 `(16, 64, 64)` | 沿最后一维每 64 列切一份 |
| `q`（view + transpose） | `(16, 4, 64, 16)` | 拆成 4 个头，每头 16 维，头维度提前 |
| `k.transpose(-2, -1)` | `(16, 4, 16, 64)` | 为 `QKᵀ` 做准备 |
| `att` | `(16, 4, 64, 64)` | 每个头一个 N×N 分数矩阵 |
| `att @ v` | `(16, 4, 64, 16)` | 加权求和 |
| `.transpose(1, 2)` | `(16, 64, 4, 16)` | 头维度放回去 |
| `.view(B, N, D)` → `y` | `(16, 64, 64)` | 合并多头 |

`transpose` 只改步长（stride）不搬数据，得到的张量在内存里不再连续；`view` 要求内存连续才能重新解释形状，否则报 `RuntimeError`。`.contiguous()` 会真的拷贝出一份连续内存。也可以直接用 `.reshape(B, N, D)`，它在需要时自动拷贝。

### Q10 — 参考答案

问题在 `final = 2 * d_model`。注释说的是"final norm + lm head（绑定，所以为 0）"，而 `norm_f = RMSNorm(d)` 只有一个长度为 d 的 `weight`，所以应该是 `final = d_model`。公式多算了 d 个参数。

对实际训练配置：

- 正确值：`46·64 + 64·64 + 3·(4·64² + 3·64·170 + 2·64) + 64 = 154,560`（`int(64·2.67) = 170`）
- `param_count(46, 64, 3, 4, block_size=64)` = `154,624`，多 64

另外两点需要注意：①`model.parameters()` 默认对共享参数去重，所以绑定后的 `tok_emb.weight` 只被数一次，`n_params` 与上面正确值一致；②`n_heads` 参数在公式里没有用到，这是对的——多头只是把 d 维切开，不改变参数量。

### Q11 — 参考答案

**不会。** `nn.Linear` 先按自己的规则初始化，但紧接着 `lm_head.weight` 被替换成 `tok_emb.weight`，而 `nn.Embedding` 默认是 `N(0, 1)` 初始化。于是：

- 残差流 `x = tok + pos` 中含有当前 token 的 embedding `e_cur`，最后经过 RMSNorm 后幅度约为 1/元素；
- logits = `x_norm @ Eᵀ`，其中"当前 token 自己"那一项约等于 `|e_cur|² / √2 ≈ 64/1.4 ≈ 45`，其他 token 的 logit 只是标准差约 8 的随机数；
- 模型在第 0 步极度自信地预测"下一个字符等于当前字符"，而目标几乎从来不是它。

用 NumPy 按 PyTorch 默认初始化规则复现这个前向（本环境没有 torch，未实际运行原脚本），得到第 0 步 loss 约 **42**，远高于 3.83。改成 nanoGPT 式的小方差初始化后，模拟结果回到 **3.83**：

```python
def _init_weights(module):
    if isinstance(module, (nn.Linear, nn.Embedding)):
        torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

model = GPT(vocab_size, d_model, n_heads, n_layers, block_size, ffn_expansion)
model.apply(_init_weights)   # 绑定的权重是同一个 tensor，被初始化一次或两次结果都一样
model = model.to(device)
```

要点：**第 0 步 loss ≈ ln V 是最便宜的健全性检查**。显著高于它说明初始 logits 过大（初始化问题），显著低于它通常说明标签泄漏（例如 mask 写错让模型看到了未来）。

### Q12 — 参考答案

```python
import math

def get_lr(step, max_steps=500, warmup=50, max_lr=3e-4, min_lr=3e-5):
    if step < warmup:
        return max_lr * (step + 1) / warmup
    progress = (step - warmup) / max(1, max_steps - warmup)
    return min_lr + 0.5 * (max_lr - min_lr) * (1 + math.cos(math.pi * progress))
```

验证（纯 Python，可直接跑）：`get_lr(0)=6.00e-06`，`get_lr(49)=3.00e-04`，`get_lr(275)=1.65e-04`，`get_lr(499)=3.00e-05`。

接入训练循环：在 `opt.step()` 之前设置每个参数组的学习率。

```python
        lr_now = get_lr(step)
        for g in opt.param_groups:
            g["lr"] = lr_now
        opt.step()
```

warmup 的作用是在 AdamW 的二阶矩估计还不准、参数还在随机区域时避免大步长把训练打崩；余弦衰减让后期以小步长精细收敛。也可以用 `torch.optim.lr_scheduler.LambdaLR` 实现同样的效果。

### Q13 — 参考回答要点

```python
def block_forward(x):
    x = x + attn(rmsnorm1(x))   # pre-norm + 残差
    x = x + ffn(rmsnorm2(x))    # ffn = w2(silu(w1 x) * w3 x)
    return x
```

- **Pre-norm**：残差主干是恒等映射，梯度直通，几十上百层也能稳定训练；最后加一个 final norm。
- **RMSNorm**：去掉均值和 bias，计算更省；实验上效果与 LayerNorm 相当。
- **SwiGLU**：门控（一路做 SiLU 激活，一路做线性"闸门"，逐元素相乘）比 ReLU/GELU FFN 表达力更强，同参数量下 loss 更低；隐藏层取 8d/3 对齐参数量。
- **去掉 bias**：大模型里 bias 几乎没有收益，去掉后参数、显存更省，训练更稳。
- **权重绑定**：输入与输出 embedding 共享，省 V·d 参数，小模型收益明显。
- **加分点**：提到大模型里还会用 RoPE、GQA、Flash Attention（`F.scaled_dot_product_attention`），并说明本节代码为了简洁用了可学习位置 embedding 和手写 attention。
- **常见误区**：把 pre-norm 写成 `x = norm(x + attn(x))`；忘记 final norm。

### Q14 — 参考回答要点

- **除以 √d_head**：q、k 各分量若独立、方差 1，点积方差为 d_head；不缩放时分数很大，softmax 饱和成 one-hot，梯度几乎为 0。除以 √d_head 把方差拉回 1。注意这里是**每个头**的维度，不是 d_model。
- **填 -inf**：mask 要在 softmax **之前**生效。填 `-inf` 后 `exp(-inf)=0`，被遮住的位置权重严格为 0，且剩余权重自动重新归一化；填 0 只是"分数为 0"，`exp(0)=1`，未来位置仍然拿到权重。
- **mask 写反**：每个位置能看到未来 token，训练 loss 会异常快地降到接近 0（模型直接"抄答案"），但生成时没有未来可看，输出完全乱码。这是"训练 loss 好得不正常"的典型原因。
- **加分点**：整行都被 mask 的情况（例如 padding）会出现 `softmax` 全 `-inf` → NaN，需要特殊处理；用 SDPA 的 `is_causal=True` 可以避免手写 mask。

### Q15 — 参考回答要点

1. **第 0 步 loss**：应接近 ln V。远高于 → 初始化过大（见 Q11）；远低于 → 标签泄漏（mask 错、x/y 没错位）。
2. **过拟合一个小 batch**：同一个 batch 反复训练，loss 应能降到接近 0；降不下去说明模型/反传有 bug。
3. **形状与错位**：检查 `y` 是否真的是 `x` 右移一位，`view(-1, V)` 与 `view(-1)` 是否对齐。
4. **学习率与 warmup**：loss 尖峰或 NaN 常因 lr 过大、没有 warmup。
5. **梯度范数**：打印 `clip_grad_norm_` 的返回值，观察是否持续爆炸。
6. **数值精度**：bf16/fp16 下的 softmax、norm 是否溢出；`eps` 是否太小。
7. **数据**：是否有异常样本、数据是否重复多轮导致过拟合（val loss 上升）。

- **加分点**：讲义术语表把梯度裁剪定义为"把全局梯度范数限制在 1.0，防止训练爆炸"，并说明裁剪只是止血，根因多在 lr/init/数据。

### Q16 — 参考回答要点

按讲义 "Use It" 和练习整理，优先级从高到低：

1. **换 tokenizer**：char-level → BPE（如 `tiktoken` 的 `cl100k_base`），词表从 65 涨到数万；embedding 和 lm_head 随之变大，模型容量要同步放大。
2. **换语料**：tinyshakespeare（约 1.1MB）→ OpenWebText 或 fineweb-edu；讲义估计 125M 模型在单张 A100 上训练 10B token 约需 24 小时。
3. **模型规模**：参考 `base` 配置（12 层、12 头、d=768，`param_count` 约 1.24 亿）；加大 `block_size`。
4. **位置编码**：可学习绝对位置 → RoPE（讲义练习 2）。
5. **attention 实现**：手写 attention → `F.scaled_dot_product_attention`，可自动走 Flash Attention 内核。
6. **训练配方**：warmup + cosine、bf16 autocast、梯度累积、按 Q11 做小方差初始化、对 norm/bias 不做 weight decay。
7. **推理**：加 KV cache（练习 3）。
8. **评估**：固定的 held-out 验证集、多批次平均的 val loss，而不是单个 batch。

- **加分点**：用上一节的 scaling law 估算 125M 模型需要多少 token；用 MFU 监控硬件利用率（讲义称 2026 年稠密模型 40% 算强）。

### Q17 — 参考回答要点

- **复杂度**：无 cache 时第 t 步要对长度 t 的前缀做完整前向，attention 部分约 O(t²)，生成 T 个 token 总计约 O(T³)（不截断时）。有 cache 时每步只算新 token 的 Q/K/V，attention 只做一行 `1×t`，单步 O(t)，总计 O(T²)，线性层部分也从"每步 t 个 token"降到"每步 1 个 token"。
- **实现细节**：
  - 每层各存一份 K、V，形状 `(B, h, t, d_head)`，每步沿序列维拼接；
  - 新 token 的位置 id 必须是 `t`，不能再从 0 开始（用 RoPE 时旋转角度同理）；
  - 单个新 query 能看到所有历史 key，不需要因果 mask；prefill 阶段仍需要 mask；
  - 超过 `block_size` 时，可学习位置 embedding 的模型不能简单滑窗，需要截断后重新 prefill。
- **显存估算**：`2（K 和 V）× 层数 × 序列长度 × d_model × batch × 每元素字节数`。GQA/MQA 通过减少 KV 头数来缩小这块显存。
- **常见误区**：cache 了 K、V 却在每步仍然把整段前缀喂进模型；位置 id 没有偏移导致生成退化。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 Self-Attention 从头开始](../../02-self-attention-from-scratch/docs/zh.md)：`QKᵀ/√d`、softmax、加权求和。
- [阶段 07 · 03 多头 Attention](../../03-multi-head-attention/docs/zh.md)：拆头、合头的 view/transpose。
- [阶段 07 · 04 位置编码](../../04-positional-encoding/docs/zh.md)：本节用可学习位置 embedding，练习要求换成 RoPE。
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：pre-norm、RMSNorm、SwiGLU 的出处。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：因果 mask 与错位一位的交叉熵。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：`nn.Module`、`register_buffer`、自动求导。

### 本节被哪些后续内容用到
- [阶段 07 · 11 专家混合 (MoE)](../../11-mixture-of-experts/docs/zh.md)：练习 5 把单个 FFN 换成 4 专家 MoE。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：练习 3 的 KV cache、讲义提到的 SDPA。
- [阶段 07 · 15 Attention 变体](../../15-attention-variants/docs/zh.md)：在本节的 attention 上改成滑动窗口 / GQA / 差分。
- [阶段 07 · 16 Speculative Decoding](../../16-speculative-decoding/docs/zh.md)：在本节的 `generate` 基础上做草稿 + 验证。
- [阶段 10 · 04 预训练 mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：把这套代码放到更大语料上预训练。
- [阶段 10 · 18 多 token 预测](../../../10-llms-from-scratch/18-multi-token-prediction/docs/zh.md)：练习 4 的 MTP 头。
- [阶段 19 · 34 Transformer Block](../../../19-capstone-projects/34-transformer-block/docs/zh.md)、[阶段 19 · 35 GPT 模型组装](../../../19-capstone-projects/35-gpt-model-assembly/docs/zh.md)：更工程化的同类综合项目。
- [阶段 19 · 44 余弦学习率与 warmup](../../../19-capstone-projects/44-cosine-lr-warmup/docs/zh.md)：Q12 的完整版本。

### 延伸关键词
`nanoGPT` · `pre-norm vs post-norm` · `RMSNorm` · `SwiGLU / GLU variants` · `weight tying` · `F.scaled_dot_product_attention` · `top-k / top-p sampling` · `KV cache` · `MFU` · `bf16 autocast`
