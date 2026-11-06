# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 18 节 Multi-Token 预测（MTP） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`、`typing`），无需 NumPy、PyTorch、GPU 或网络

---

## 1. 这份代码在考察什么

这份代码用纯 Python 列表搭出 DeepSeek-V3 顺序 MTP（Multi-Token Prediction，多 token 预测）模块的**结构**，并做三件事：

1. **前向结构**：共享 embedding 表 `E` → 对"上一深度隐藏状态"和"真实下一个 token 的 embedding"分别做 RMSNorm → 融合 → 投影 `M_k` → 一个 Transformer block（注意力 + SwiGLU MLP）→ 共享输出头（`E` 转置，weight tying）。
2. **联合损失**：按深度累加交叉熵，`L_MTP = (λ / D) · Σ L_k`。
3. **参数账**：对玩具、mini GPT、7B、70B、"DeepSeek-V3 形状"五种配置，计算 MTP 模块相对主模型的参数开销。

它对应讲义的 "The sequential MTP recipe"、"Parameter accounting" 两节。注意它**没有任何训练**：所有权重都是随机初始化，Step 3 只是改变构造隐藏状态时的噪声大小。

> 一句话：**看清一个 MTP 模块由哪些零件组成、哪些参数是共享的、损失怎么按深度加权**；同时要能识别出它在深度索引、注意力实现和"模拟训练"上的几处简化与错误。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `rand_matrix` / `matvec` / `add` | 函数 | 用嵌套列表实现随机矩阵、矩阵乘向量、向量加法 | 线性代数基础 |
| `rms_norm` | 函数 | `x / sqrt(mean(x²) + eps)`，无可学习缩放 | RMSNorm |
| `silu` / `swiglu` | 函数 | `W_down · (SiLU(W_gate·x) ⊙ (W_up·x))` | SwiGLU MLP |
| `softmax` / `cross_entropy` | 函数 | 数值稳定 softmax；`-log p[target]` | 交叉熵损失 |
| `MTPModule` | dataclass | 存放一个深度的 `M_k` 与 block 的 7 个矩阵 | MTP 模块的新增参数 |
| `make_mtp_module` | 函数 | 按形状随机初始化一个模块 | 初始化 |
| `attention_single` | 函数 | 单 token 的"注意力"占位实现 | Transformer block 中的注意力 |
| `mtp_forward` | 函数 | `h^(k) = T_k(M_k · (RMSNorm(h^(k-1)) + RMSNorm(E(t))))` | 顺序 MTP 递推 |
| `shared_head_logits` | 函数 | `logits[v] = E_v · h` | 共享输出头 |
| `mtp_loss` | 函数 | 对每个位置、每个深度累加交叉熵，乘 `λ/D` | 联合损失 |
| `ParamReport` / `count_parameters` | dataclass / 函数 | 主模型与 MTP 模块的参数量 | 参数账 |
| `fmt` | 函数 | 把整数格式化成 K/M/B | 输出美化 |
| `main` | 函数 | Step 1 玩具损失 → Step 2 参数表 → Step 3 噪声扫描 | 演示入口 |

数据流：`random.Random(23)` → 随机 `E`（32×8）与 12 个随机 token → 用 `E[t_i] + 噪声` 构造 "backbone 隐藏状态" → 2 个随机 MTP 模块 → `mtp_loss` 打印每深度损失 → `count_parameters` 打印参数表 → 换 4 档噪声重算损失。

---

## 3. 逐段精讲

### 3.1 列表版线性代数与 RMSNorm

```python
def matvec(M: List[List[float]], v: List[float]) -> List[float]:
    out = [0.0] * len(M)
    for i, row in enumerate(M):
        out[i] = sum(row[j] * v[j] for j in range(len(v)))
    return out


def rms_norm(v: List[float], eps: float = 1e-6) -> List[float]:
    ms = sum(x * x for x in v) / len(v)
    r = 1.0 / math.sqrt(ms + eps)
    return [x * r for x in v]
```

- 矩阵用"行的列表"表示，`M` 形状为 `(rows, cols)`，`matvec(M, v)` 要求 `len(v) == cols`，输出长度为 `rows`。例如 `W_gate` 是 `(ff, hidden) = (16, 8)`，把 8 维变成 16 维。
- `rms_norm` 只除以均方根，不减均值，这正是 RMSNorm 与 LayerNorm 的区别；它省去了均值计算，Llama、DeepSeek 等模型都用它。真实实现还会乘一个可学习的增益向量 `g`，这里省略了。
- 归一化后向量的均方为 1，因此 8 维向量的 L2 范数约为 `√8 ≈ 2.83`。

### 3.2 SwiGLU MLP

```python
def silu(x: float) -> float:
    return x / (1.0 + math.exp(-x))


def swiglu(v, W_gate, W_up, W_down):
    gate = [silu(x) for x in matvec(W_gate, v)]
    up = matvec(W_up, v)
    inner = [g * u for g, u in zip(gate, up)]
    return matvec(W_down, inner)
```

- SwiGLU = `W_down · (SiLU(W_gate·x) ⊙ W_up·x)`，有**三块**矩阵，所以参数是 `3 · h · ff`（代码 `count_parameters` 中 `mlp = 3 * hidden * ff`）。
- 讲义说"`8h²` for SwiGLU with ratio 8/3"：ff = `8h/3` 时 `3 · h · 8h/3 = 8h²`。代码中 7B/70B 配置用的是 Llama 风格 ff = 3.5h，MLP 实际是 `10.5h²`。
- ⚠️ `silu` 在 `x` 很负时 `math.exp(-x)` 可能溢出（`x < -709` 时抛 `OverflowError`）；玩具数值很小所以没问题。

### 3.3 `MTPModule`：哪些参数是新增的

```python
@dataclass
class MTPModule:
    hidden: int
    ff: int
    M_k: List[List[float]]
    Wq: List[List[float]]
    Wk: List[List[float]]
    Wv: List[List[float]]
    Wo: List[List[float]]
    W_gate: List[List[float]]
    W_up: List[List[float]]
    W_down: List[List[float]]
```

- 一个模块只包含**投影 `M_k` + 一个 Transformer block**（4 个注意力矩阵 + 3 个 MLP 矩阵）。embedding 表 `E` 不在里面，而是作为参数传给 `mtp_loss`——这就是讲义强调的"shared embedding / shared output head：literally the same tensor"。
- ⚠️ `M_k` 由 `make_mtp_module` 创建为 `rand_matrix(hidden, hidden)`，即 `h × h`。真实 DeepSeek-V3 是把两个 h 维向量**拼接**成 2h 维，再用 `h × 2h` 的矩阵投影回 h 维；代码用"相加"代替拼接（注释已说明），参数因此少了 `h²`。
- 相加与拼接不等价：拼接后 `M_k` 可以给"历史隐藏状态"和"下一个 token embedding"不同的权重；相加后两者在进入 `M_k` 之前就已经混在一起、无法区分。

### 3.4 `attention_single`：一个退化的注意力

```python
def attention_single(v_in, Wq, Wk, Wv, Wo):
    q = matvec(Wq, v_in)
    k = matvec(Wk, v_in)
    v = matvec(Wv, v_in)
    score = sum(q[i] * k[i] for i in range(len(q))) / math.sqrt(len(q))
    weight = 1.0
    attended = [weight * vi for vi in v]
    return matvec(Wo, attended)
```

- 只有一个 token 自己看自己，softmax 对单个分数归一化恒为 1，所以 `weight = 1.0`。
- ⚠️ 结果是：`score` 算了但**从未被使用**，`Wq`、`Wk` 对输出没有任何影响，这个"注意力"在数学上就是 `Wo · Wv · x` 这个线性映射。`count_parameters` 却仍按 `4h²` 计入了 `Wq`、`Wk`。
- 真实的 `T_k` 是完整的因果自注意力：深度 k 上，对所有位置 i 的组合表示构成一条序列，位置 i 注意它之前的所有位置。推理时 MTP 模块也需要自己的 KV cache。

### 3.5 `mtp_forward`：顺序 MTP 的一步递推

```python
def mtp_forward(prev_hidden, next_embed, module):
    a = rms_norm(prev_hidden)
    b = rms_norm(next_embed)
    folded = add(a, b)
    projected = matvec(module.M_k, folded)
    post_attn = add(projected, attention_single(projected, module.Wq, module.Wk,
                                                  module.Wv, module.Wo))
    post_mlp = add(post_attn, swiglu(rms_norm(post_attn), module.W_gate,
                                       module.W_up, module.W_down))
    return post_mlp
```

对应论文公式：

```
h_i'^(k) = M_k [ RMSNorm(h_i^(k-1)) ; RMSNorm(E(t_{i+k})) ]
h_i^(k)  = T_k( h_i'^(k) )
```

- 两个输入**各自**先 RMSNorm：主模型隐藏状态与 embedding 的尺度可能相差很大，先归一化再融合，避免一方淹没另一方。
- block 内是"残差 + 注意力"、"残差 + MLP"两段。⚠️ 注意力前**没有** RMSNorm（MLP 前有），与标准 pre-norm block 不一致；也没有 block 末尾的 norm。
- 形状：所有中间向量都是 `hidden = 8` 维；SwiGLU 内部是 `ff = 16` 维。

### 3.6 共享输出头与交叉熵

```python
def shared_head_logits(hidden, E):
    return [sum(E[v][i] * hidden[i] for i in range(len(hidden)))
            for v in range(len(E))]


def cross_entropy(logits, target):
    probs = softmax(logits)
    return -math.log(max(probs[target], 1e-12))
```

- `logits[v] = E_v · h`：输出头就是 embedding 表的转置（weight tying），形状 `(V, h) × (h,) → (V,)`，即 32 个 logit。DeepSeek-V3 的主模型其实并不 tie embedding 和输出头，但 MTP 模块与主模型**共享输出头**，这一点代码用"同一个 `E`"表达出来了。
- `max(probs[target], 1e-12)` 防止 `log(0)`；`softmax` 先减最大值防止 `exp` 溢出。
- 实测 logit 范围约 `[-1.48, 1.13]`，最大概率只有约 0.07，所以损失都在 `ln 32 ≈ 3.466` 附近。

### 3.7 `mtp_loss`：联合损失（本文件最需要细看的地方）

```python
    D = len(modules)
    per_depth = [0.0] * D
    n_valid = 0
    for i in range(len(backbone_hidden) - D):
        h_prev = backbone_hidden[i]
        for k in range(1, D + 1):
            logits = shared_head_logits(h_prev, E)
            tgt = tokens[i + k]
            per_depth[k - 1] += cross_entropy(logits, tgt)
            next_embed = E[tokens[i + k]]
            h_prev = mtp_forward(h_prev, next_embed, modules[k - 1])
        n_valid += 1
    per_depth = [loss / n_valid for loss in per_depth]
    total = (lam / D) * sum(per_depth)
```

逐行含义：外层遍历起点 i（seq = 12、D = 2 时 i = 0…9，共 10 个有效位置）；内层先用当前 `h_prev` 预测 `t_{i+k}`，再把真实 `t_{i+k}` 的 embedding 喂进第 k 个模块得到下一个隐藏状态（teacher forcing）。

它忠实实现了讲义写的 `logits_{i+k} = Out(h_i^(k-1))`，但这个索引与 DeepSeek-V3 论文不同，导致两个问题（均已实验验证）：

| 现象 | 原因 | 验证 |
|------|------|------|
| `L_1` 是**主模型**的 next-token 损失 | k = 1 时 logits 来自 `h_i^(0)`（backbone），还没经过任何 MTP 模块 | 单独对 10 个位置算 `CE(Out(h_i^(0)), t_{i+1})` 得 3.6723，与 `L_1` 完全相同 |
| 最后一个模块 `modules[D-1]` 从未影响损失 | k = D 时先算 logits 再调用 `mtp_forward`，其输出被丢弃 | 把 `modules[1]` 换成另一个随机模块，`(total, per_depth)` 不变；换 `modules[0]` 后 `L_2` 从 3.272 变为 3.340 |

论文中模块 k 的输出 `h_i^(k)` 预测的是 `t_{i+k+1}`，主模型单独负责 `t_{i+1}`。因此正确写法应是"先 `mtp_forward` 再算 logits，目标 `tokens[i+k+1]`，外层 `range(len - D - 1)`"，并把主损失放在 `L_MTP` 之外（见测验 Q9）。按现在的写法，`L_MTP = (λ/D)(L_main + L_MTP,1)`：主损失被重复计入，而 D = 2 实际只训练 1 个模块。

### 3.8 参数账：`count_parameters`

```python
    emb = vocab * hidden
    attn = 4 * hidden * hidden
    mlp = 3 * hidden * ff
    main = emb + n_layers * (attn + mlp) + hidden
    per_mtp = hidden * hidden + attn + mlp
    mtp_total = D * per_mtp
```

- 主模型 = embedding + 每层（注意力 `4h²` + MLP `3·h·ff`）× 层数 + 一个最终 norm（`hidden`）。没有计各层的 norm、没有单独的输出头（假设 tie）。
- 每个 MTP 模块 = `M_k`（代码口径 `h²`，论文口径应为 `2h²`）+ 一个 block。embedding、输出头共享，不计。
- `vocab` 对所有非 toy 配置都用 128000。这让"mini GPT"的主模型变成 211.6M（GPT-2 Small 真实词表 50257，约 124M）；"DeepSeek-V3-shape" 是**稠密**的 61 层 7168 维模型，主模型只有 37.6B，远不是 671B 的 MoE。
- 各配置每模块参数与 `h²` 的倍数（实算）：mini GPT 17.0h²、7B 15.5h²、70B 15.5h²、DeepSeek 形状 12.7h²；讲义的经验值是 14h²。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、列表实现 | 无依赖，零件全部可见 | 极慢，只能跑 8 维玩具；生产用 PyTorch + 融合算子 |
| 用相加代替拼接，`M_k` 为 `h×h` | 少写一个 concat 与形状变换 | 无法分别加权两路输入；参数少 `h²`；论文是 `h×2h` |
| 单 token 退化注意力 | 不必维护序列与 KV cache | `Wq/Wk` 成为死参数；真实 `T_k` 是完整因果注意力 |
| 共享 `E` 作 embedding 与输出头 | 体现"共享、不新增参数" | 真实 V3 的主模型 embedding 与输出头是两套参数，MTP 与主模型共享这两套 |
| 隐藏状态 = `E[t_i]` + 噪声 | 不需要真正的 backbone | 隐藏状态编码的是当前 token 而非下一个，导致 `L_1 > ln V` |
| 不训练、只扫噪声 | 演示简单 | 无法体现"损失随训练下降"；Step 3 的单调下降是偶然 |
| 沿用讲义的深度索引 | 与讲义公式一致 | 与论文不符：`L_1` 实为主损失、最后一个模块无用 |
| 参数账统一用 vocab=128000、稠密 FFN | 一张表横向对比 | 主模型规模失真；DeepSeek 的 MoE 无法体现（讲义用"MTP block 也是 MoE"解释 14B） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可以在旧版本 Python 中写 `tuple[float, List[float]]` 这类注解 |
| 类型注解 | `def matvec(M: List[List[float]], v: List[float]) -> List[float]` | 标注参数与返回类型，只做文档/静态检查用，运行时不强制 |
| `typing.List` 与内置泛型 | `List[List[float]]`、`tuple[float, List[float]]` | 前者是旧写法，后者是 Python 3.9+ 写法，本文件混用 |
| `@dataclass` | `class MTPModule`、`class ParamReport` | 自动生成 `__init__`、`__repr__`，适合"只装数据"的类 |
| 关键字参数构造 | `MTPModule(hidden=hidden, ff=ff, M_k=..., ...)` | 按字段名传参，可读性好、不怕顺序错 |
| 嵌套列表推导式 | `[[rng.gauss(0, scale) for _ in range(cols)] for _ in range(rows)]` | 外层生成行，内层生成每行的元素 |
| 生成器表达式 | `sum(row[j] * v[j] for j in range(len(v)))` | 不建中间列表，边算边求和 |
| `enumerate` / `zip` | `for i, row in enumerate(M)`、`zip(gate, up)` | 同时拿下标和元素；并行遍历两个序列 |
| 独立随机数生成器 | `rng = random.Random(23)`、`rng.gauss`、`rng.randrange` | 每个 `Random` 实例有自己的状态，便于复现、互不干扰 |
| 默认参数 | `scale: float = 0.1`、`eps: float = 1e-6` | 调用时可以省略 |
| 列表乘法初始化 | `[0.0] * len(M)`、`[0.0] * D` | 创建定长列表（元素为不可变数字时安全） |
| 条件表达式 | `vocab=128000 if name != "toy" else vocab` | 一行内的 if/else |
| 循环中元组解包 | `for name, h, ff_h, L, D_h in [(...), ...]` | 每个元组直接拆成多个变量 |
| 数字下划线 | `1_000_000_000` | 仅提高可读性，等同于 `1000000000` |
| f-string 格式符 | `{loss:.3f}`、`{name:<22}`、`{fmt(...):>7}`、`{noise_scale:>7.2f}` | 小数位、左/右对齐与宽度 |
| f-string 中调用函数与表达式 | `{100.0 * r.mtp_total / r.main_total:.1f}%` | 花括号里可以写任意表达式 |
| 字符串重复与拼接 | `"=" * 70`、`"..." + ", ".join(...)` | 打印分隔线；`join` 拼接多个字符串 |
| `float("nan")` | `per_depth[1] if len(per_depth) > 1 else float("nan")` | 表示"无值"的浮点数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行（测验中的验证脚本就是 import 本文件） |

---

## 6. 运行结果解读

实际运行（Python 3，`python3 main.py`，耗时约 0.05 秒）：

```text
Step 1: toy setup  vocab=32, hidden=8, ff=16, seq=12, D=2
  per-depth losses   : L_1=3.672, L_2=3.272
  joint L_MTP (lam=0.3)  : 1.0417
  (uniform random-guess reference: 3.466 per depth)

Step 2: parameter accounting
  toy                    main=   1.5K  + 2 MTP module(s) =   1.4K  (91.2% overhead)
  mini GPT               main= 211.6M  + 1 MTP module(s) =  10.0M  (4.7% overhead)
  7B dense               main=   8.3B  + 1 MTP module(s) = 260.0M  (3.1% overhead)
  70B dense              main=  78.9B  + 1 MTP module(s) =   1.0B  (1.3% overhead)
  DeepSeek-V3-shape      main=  37.6B  + 1 MTP module(s) = 653.3M  (1.7% overhead)

Step 3: per-depth loss vs training progress (synthetic)
    noise     L_1     L_2    L_MTP
     0.50   3.600   3.320   1.0381
     0.30   3.563   3.310   1.0310
     0.15   3.513   3.301   1.0220
     0.05   3.489   3.295   1.0176
```

逐项解读：

- **`L_MTP = 1.0417`**：`0.3 / 2 × (3.672 + 3.272) = 1.0416`，与打印值一致。
- **`L_1 = 3.672` 高于 `ln 32 = 3.466`**：隐藏状态由 `E[t_i]` 加噪声构造，共享头打分时 argmax 有 9/12 个位置命中**当前** token `t_i`，命中下一个 token `t_{i+1}` 的次数为 0（实测）。模型"自信地预测了错误的 token"，所以比均匀猜测还差。另外如 3.7 所述，这个 `L_1` 实际是主模型损失。
- **`L_2 = 3.272`**：来自经过第 1 个 MTP 模块后的隐藏状态，随机权重下接近 `ln 32`。它比 `L_1` 低只是偶然。
- **toy 行**：主模型 `256 + 2×(256+384) + 8 = 1,544`；每模块 `64 + 256 + 384 = 704`，两模块 1,408，开销 91.2%——玩具规模下 MTP 开销与主模型同量级，这正是讲义说"1B 以下不划算"的直观版本。
- **70B dense 行**：每模块 1,040,187,392（`h² + 4h² + 3·8192·28672`），讲义口径 `14h² ≈ 939.5M`；开销 1.3%。
- **DeepSeek-V3-shape 行**：653.3M（约 12.7h²），与讲义的"~720M"同量级；DeepSeek 实际报告 14B 是因为 MTP block 里也有 MoE 专家。
- **Step 3**：噪声变小时隐藏状态更接近 `E[t_i]` 的方向，损失随之变化，但这与训练无关。实测连同 `E`、tokens、模块一起换 50 组随机种子时，`L_1` 单调下降只有 14 组，说明打印出的"单调下降"是种子 23/42 的巧合。

---

## 7. 动手改一改

1. **修正深度索引**（必做）：把 `mtp_loss` 改为"先 `mtp_forward` 再算 logits、目标 `tokens[i+k+1]`"，外层 `range(len(backbone_hidden) - D - 1)`；验证替换 `modules[1]` 后 `L_2` 会改变。
2. **真正的拼接**：把 `M_k` 改为 `rand_matrix(hidden, 2 * hidden)`，`folded = a + b`（列表拼接）；同步把 `count_parameters` 中 `per_mtp` 改为 `2 * hidden * hidden + attn + mlp`，对比 DeepSeek 形状下的数字是否接近 `14h²`。
3. **讲义练习 1**：构造有规律的序列（如 `t_{i+1} = (t_i + 3) % vocab`），让 backbone 隐藏状态编码 `E[t_{i+1}]`；对 `M_k` 做有限差分梯度下降若干步，观察 `L_1`、`L_2` 都下降。
4. **讲义练习 4（并行 MTP 对照）**：新增 D 个独立输出矩阵 `H_k`（`V × h`），全部作用于 `h_i^(0)` 预测 `t_{i+k}`；在同一合成数据上训练后与顺序版对比 depth-2 损失。
5. **讲义练习 5（MTP 作为 draft）**：在训练好的玩具上，用模块 1 的 argmax 作为 draft，与"主模型在下一位置的 argmax"比较，统计接受率；再按 `1 + α` 估算理论加速。
6. **进阶**：把 `attention_single` 改为在整条序列上的因果注意力（为深度 k 的所有位置维护 K、V 列表），让 `Wq`、`Wk` 真正起作用。

---

## 8. 常见坑

- **把主模型损失当成 MTP 损失**：论文里模块 k 预测 `t_{i+k+1}`，`t_{i+1}` 是主模型的事。照抄讲义的 `logits_{i+k} = Out(h_i^(k-1))` 就会出现本代码的"`L_1` = 主损失、最后一个模块不参与"问题。
- **以为 `Wq`/`Wk` 在起作用**：单 token 注意力的权重恒为 1，这两个矩阵完全不影响输出。数参数时要区分"存在的参数"和"起作用的参数"。
- **相加 ≠ 拼接**：拼接后再线性投影可以学到两路输入的独立权重；相加会把两路信息提前混合。
- **λ 的位置**：λ 只乘在 MTP 损失上，并且要除以 D；主损失权重恒为 1。
- **把噪声扫描当训练曲线**：没有梯度更新就没有"训练"；单一随机种子的单调趋势不能作为证据。
- **参数账的口径**：词表大小、是否 tie 输出头、FFN 维度、是否 MoE、是否 GQA 都会显著改变数字；引用"14h²"时要说明是 MHA + SwiGLU(8/3) + 拼接投影的估算。
- **λ 调度的出处**：讲义写"前 10% 训练用 0.3"，DeepSeek-V3 技术报告原文是"前 10T token 用 0.3、其余 4.8T token 用 0.1"，即大约前 2/3 的训练，复现时以论文为准。
