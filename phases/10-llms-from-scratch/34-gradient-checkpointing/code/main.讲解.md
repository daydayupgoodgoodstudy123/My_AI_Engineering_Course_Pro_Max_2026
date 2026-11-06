# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 34 节 Gradient Checkpointing 与激活重计算 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`numpy`（第三方）；不需要 PyTorch（讲义写"optional torch"，但代码完全没用到）、GPU 或网络

---

## 1. 这份代码在考察什么

代码分成两部分：

1. **可运行的机制演示**：用一个"每层 = Linear → ReLU → Linear"的小 MLP，分别实现普通 forward/backward 与"每 k 层存一次输入、backward 时分段重算"的 checkpointed 版本，验证二者的梯度**逐位相同**——这是 gradient checkpointing "数学上等价、只改变时间和显存"的直接证据。
2. **纸面成本模型**：`checkpoint_cost`（重算 FLOP 开销）、`activation_memory_mb` / `memory_after_checkpoint`（激活显存）、`optimal_segment`（√L 规则）、`should_recompute`（selective 决策）。它们对应讲义 Recompute Cost Model、Memory Savings Model 与 Step 4–7。

对应讲义概念：backward 需要什么、naive full checkpointing、√L 规则、selective checkpointing、FLOP 与显存的折中。

> 一句话：**用"重跑一遍 forward"换"少存一堆激活"，并给这笔交易记账**。但本文件的几个账本彼此口径不一致（详见 3.6、3.7 与测验 Q9、Q10），读懂这些不一致比记住数字更重要。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `linear_forward` / `relu` / `layer_forward` | 函数 | 单层 `relu(x@w1+b1)@w2+b2` | 被 checkpoint 的"层" |
| `model_forward` | 函数 | 逐层前向，返回输出和每层输入列表 `activations` | 普通 forward（保存激活） |
| `layer_backward` | 函数 | 单层反向：重算 `h_pre`，求 4 个参数梯度与输入梯度 | 反向传播 |
| `model_backward` | 函数 | 从最后一层往前调用 `layer_backward` | 普通 backward |
| `model_forward_checkpointed` | 函数 | 只在每 k 层的边界保存输入 | checkpoint forward |
| `model_backward_checkpointed` | 函数 | 从后往前逐段：用段输入重算段内激活 → 段内 backward | 激活重计算 |
| `checkpoint_cost` | 函数 | 按段长或 selective 估算重算 FLOP 开销 | 成本模型 |
| `activation_memory_mb` / `memory_after_checkpoint` | 函数 | 不 checkpoint / checkpoint 后的激活显存（MB） | 显存模型 |
| `optimal_segment` | 函数 | `round(√L)` | √L 规则 |
| `should_recompute` | 函数 | 按层类型和激活大小判断是否重算 | selective 决策（未被 main 调用） |
| `make_params` / `verify_equivalence` | 函数 | 生成参数；对比两种实现的输出与梯度 | 正确性验证 |
| `if __name__ == "__main__":` | 入口 | 打印等价性、各 k 的开销、显存表 | 演示 |

数据流：`make_params` → `model_forward` + `model_backward`（基线梯度）→ `model_forward_checkpointed` + `model_backward_checkpointed`（重算梯度）→ 比较；随后独立地调用 `checkpoint_cost`、`optimal_segment`、`activation_memory_mb`、`memory_after_checkpoint` 打印表格。

---

## 3. 逐段精讲

### 3.1 一层的前向

```python
def linear_forward(x, w, b):
    return x @ w + b

def relu(x):
    return np.maximum(x, 0.0)

def layer_forward(x, w1, b1, w2, b2):
    h = relu(linear_forward(x, w1, b1))
    return linear_forward(h, w2, b2)
```

- 形状（`verify_equivalence` 默认）：`x (4, 16)` → `x@w1+b1 (4, 32)` → ReLU → `@w2+b2 (4, 16)`。这是一个最简化的 FFN 子层，没有残差、没有注意力。
- `b` 形状 `(32,)` 与 `(4, 32)` 相加靠**广播**。

### 3.2 普通 forward：保存每层输入

```python
def model_forward(x, params):
    activations = [x]
    h = x
    for w1, b1, w2, b2 in params:
        h = layer_forward(h, w1, b1, w2, b2)
        activations.append(h)
    return h, activations
```

- `activations` 长度为 L+1：`[x, out_0, out_1, …, out_{L-1}]`，其中 `activations[i]` 是第 i 层的输入。
- 注意它**只存层与层之间的张量**，没有存层内部的 `h_pre`、`h`——层内部的东西在 backward 里重算（见 3.3）。这和讲义"每层 12 份中间激活都要存"的设定不同。

### 3.3 单层反向

```python
def layer_backward(g, x_in, w1, b1, w2, b2):
    h_pre = linear_forward(x_in, w1, b1)
    h = relu(h_pre)
    gw2 = h.T @ g
    gb2 = g.sum(axis=0)
    gh = g @ w2.T
    g_pre = gh * (h_pre > 0)
    gw1 = x_in.T @ g_pre
    gb1 = g_pre.sum(axis=0)
    gx = g_pre @ w1.T
    return gx, (gw1, gb1, gw2, gb2)
```

逐行对应链式法则（`g` 为输出梯度，形状 `(B, 16)`）：

| 量 | 公式 | 形状 | 讲义对应 |
|----|------|------|---------|
| `gw2` | `hᵀ @ g` | `(32, 16)` | "`grad_params = input.T @ grad_output`" |
| `gb2` | `Σ_batch g` | `(16,)` | bias 梯度是对 batch 求和 |
| `gh` | `g @ w2ᵀ` | `(4, 32)` | 传给上一个子层 |
| `g_pre` | `gh * (h_pre > 0)` | `(4, 32)` | ReLU 导数需要激活值本身 |
| `gw1` | `x_inᵀ @ g_pre` | `(16, 32)` | 需要层输入 |
| `gx` | `g_pre @ w1ᵀ` | `(4, 16)` | 传给前一层 |

- 第一、二行重新计算了 `h_pre`、`h`：这正是"backward 需要的中间结果"。**即使是基线**，也在这里做了一次层内重算（约占该层 forward 一半的 FLOPs，因为两个线性层大小相同）。
- `(h_pre > 0)` 是布尔数组，与浮点相乘时自动当作 0/1。

### 3.4 普通 backward

```python
def model_backward(grad_output, activations, params):
    grads = [None] * len(params)
    g = grad_output
    for i in range(len(params) - 1, -1, -1):
        w1, b1, w2, b2 = params[i]
        x_in = activations[i]
        g, grads[i] = layer_backward(g, x_in, w1, b1, w2, b2)
    return g, grads
```

- 倒序遍历层，`g` 不断被替换为"当前层输入的梯度"，最后返回的 `g` 是对整个网络输入 `x` 的梯度。
- `g, grads[i] = ...`：一次解包同时更新 `g` 和列表的第 i 项。
- 它只读 `activations[0 .. L-1]`，**从不读 `activations[L]`（最终输出）**——这一点是 3.6 优化的依据。

### 3.5 Checkpointed forward：只存段边界

```python
def model_forward_checkpointed(x, params, k=4):
    saved_inputs = [x]
    h = x
    for i, (w1, b1, w2, b2) in enumerate(params):
        h = layer_forward(h, w1, b1, w2, b2)
        if (i + 1) % k == 0 and (i + 1) < len(params):
            saved_inputs.append(h)
    saved_inputs.append(h)
    return h, saved_inputs
```

- 每完成 k 层，就把当前输出（即下一段的输入）存下来；`(i + 1) < len(params)` 避免在最后一层重复保存。循环结束后再追加一次最终输出。
- 6 层、k = 2：`saved_inputs = [x, out_1, out_3, out_5]`，长度 4 = 段数 3 + 1。最后一项（最终输出）在 backward 中不会被用到，只是让列表"对齐"。
- 与讲义 Step 3 的差别：讲义版在 L 能被 k 整除时会多出一个"空段"，靠 `if start >= end: continue` 跳过；代码版用 `n_seg = ceil(L/k)` 计算段数，更干净。
- 显存：存了 ⌈L/k⌉ 个段输入（加一个输出），而不是 L+1 个。

### 3.6 Checkpointed backward：分段重算

```python
def model_backward_checkpointed(grad_output, saved_inputs, params, k=4):
    grads = [None] * len(params)
    g = grad_output
    n_seg = (len(params) + k - 1) // k
    for seg_idx in range(n_seg - 1, -1, -1):
        start = seg_idx * k
        end = min(start + k, len(params))
        x_in = saved_inputs[seg_idx]
        _, seg_acts = model_forward(x_in, params[start:end])
        g, seg_grads = model_backward(g, seg_acts, params[start:end])
        for j, gr in enumerate(seg_grads):
            grads[start + j] = gr
    return g, grads
```

- `(L + k − 1) // k` 是整数向上取整的惯用写法。
- 从最后一段往前：取该段输入 → 用 `model_forward` 重算段内所有层的输入（`seg_acts`）→ 用普通 `model_backward` 在段内反传 → 把段内梯度写回全局 `grads` 的对应位置。`g` 在段与段之间接力传递。
- 峰值显存：⌈L/k⌉ 个段输入 + 当前段的 k+1 个张量。
- ⚠️ **实现与成本模型不一致**：`model_forward(x_in, params[start:end])` 重算了段内**全部 k 层**，6 层 k = 2 时实测调用 `layer_forward` 6 次；但 `checkpoint_cost` 按 `L·(k−1)/k` 计 3 次。段内最后一层的输出从不被 `model_backward` 使用，改成 `params[start:end - 1]` 即可只重算 k−1 层（测验 Q10，已验证梯度仍逐位相同）。

### 3.7 成本模型 `checkpoint_cost`

```python
def checkpoint_cost(n_layers, segment_size=1, flops_per_layer=1.0,
                    attention_fraction=0.15, selective=False):
    fwd = n_layers * flops_per_layer
    if selective:
        recompute = n_layers * attention_fraction * flops_per_layer
    else:
        recompute = n_layers * flops_per_layer * (
            (segment_size - 1) / max(segment_size, 1)
        )
    bwd = 2 * n_layers * flops_per_layer
    ...
        "overhead_vs_no_ckpt": total / baseline - 1.0,
```

- backward 记为 forward 的 2 倍（对激活、对权重各一次矩阵乘）。
- 非 selective：重算量 `L·(k−1)/k`。k = 1 → 0；k = 64 → 63 层 → `63/192 = 32.8%`；k → ∞ 趋于 33.3%。
- selective：只重算 attention 的 15%，`9.6/192 = 5.0%`。
- ⚠️ 讲义的成本模型是"全量重算 = 每段多一次 forward = 33%"，且明确说"32 段每段 1 层"也是 33%；代码的 `(k−1)/k` 则把层视为原子（只需层输入），k = 1 时开销为 0。两套假设都能自圆其说，但**不能和下面的显存模型混用**。
- ⚠️ 与讲义 Step 4 的差别：讲义的 `checkpoint_cost` 不管 `segment_size` 是多少都返回 33%（参数没被使用）；代码修改了公式，却没在讲义中说明。

### 3.8 显存模型

```python
def activation_memory_mb(n_layers, hidden=8192, seq=8192, batch=1,
                         bytes_per_value=2):
    per_layer = 12 * batch * seq * hidden * bytes_per_value
    return n_layers * per_layer / 1e6

def memory_after_checkpoint(n_layers, segment_size, hidden=8192,
                            seq=8192, batch=1, bytes_per_value=2):
    n_seg = (n_layers + segment_size - 1) // segment_size
    saved = (n_seg + segment_size) * batch * seq * hidden * bytes_per_value
    return saved / 1e6
```

- 记 1 单位 = `B·S·d·2` 字节 = 134.2 MB。不 checkpoint：每层 12 单位 = 1.61 GB，64 层 = 103,079 MB。讲义正文写"800 MB/layer in BF16、64 层 51 GB"，少算了 2 倍（把 805M 个**值**当成了字节数）。
- checkpoint 后：`n_seg`（段输入）+ `segment_size`（当前段内每层 1 单位）。k = 8 时 8 + 8 = 16 单位 = 2,147.5 MB，正是 √L 的最优点。
- ⚠️ **口径不一致**：基线按每层 12 单位算，重算中的段却按每层 1 单位算。如果层内确有 12 单位激活，重算一段时它们会全部重新出现，峰值应为 `n_seg + 12·k` 单位：k = 2 时约 7.5 GB 最小，k = 8 时约 14.0 GB（测验 Q9）。再结合 3.7 的 k = 1 "零开销"，就会得到"不花算力、显存省 12 倍"的错误结论。
- 模型也没有包含 attention softmax 的 `B·heads·S²` 项——而那正是 selective checkpointing 存在的理由。

### 3.9 √L 与 selective 决策

```python
def optimal_segment(n_layers):
    return max(1, int(round(np.sqrt(n_layers))))

def should_recompute(layer_type, activation_bytes_mb, recompute_flops_ratio):
    if layer_type == "attention" and activation_bytes_mb > 100:
        return True
    if layer_type == "ffn" and activation_bytes_mb > 500:
        return recompute_flops_ratio < 0.1
    return False
```

- `optimal_segment(64) = 8`。`max(1, …)` 防止 L = 0 时返回 0 导致后续除零。
- `should_recompute` 是一个按阈值的规则：attention 激活 > 100 MB 一律重算；FFN > 500 MB 且重算比例 < 0.1 才重算；其余不重算。`main` 中**没有调用**它。参数单位由讲义的"字节、阈值 `100 * 1e6`"改成了"MB、阈值 100"，调用方若沿用讲义习惯会出错（测验 Q12）。

### 3.10 等价性验证

```python
def make_params(n_layers, hidden, inner, seed=0):
    rng = np.random.default_rng(seed)
    ...
        w1 = rng.standard_normal((hidden, inner)).astype(np.float32) * (1.0 / np.sqrt(hidden))

def verify_equivalence(n_layers=6, hidden=16, inner=32, batch=4, k=2):
    ...
    max_diff = 0.0
    for gf, gc in zip(grads_full, grads_ck):
        for a, b in zip(gf, gc):
            max_diff = max(max_diff, float(np.max(np.abs(a - b))))
    return {
        "output_match": bool(np.allclose(out_full, out_ck, atol=1e-5)),
        "max_grad_diff": max_diff,
    }
```

- 权重按 `1/√fan_in` 缩放（类似 LeCun 初始化），保持各层激活尺度稳定；全部转为 float32。
- 双重 `zip`：外层按层配对，内层按 `(gw1, gb1, gw2, gb2)` 配对，取全部元素差的最大值。
- 由于重算完全复现相同运算，差值为 **0.0**（不是"很小"，是严格 0）。
- `bool(np.allclose(...))`：把 NumPy 的 `np.bool_` 转成 Python `bool`，打印更干净。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 2 层 MLP 当"层" | 手写反向传播只需十几行 | 没有注意力、没有 S² 激活，体现不出 selective 的意义；生产中由 autograd 处理 |
| 基线只存层输入、层内重算 `h_pre` | 代码最短 | "基线"本身已经含重算，和讲义"存全部中间激活"的设定不同 |
| 段内用普通 `model_forward` 重算 | 复用代码，正确性一目了然 | 多重算了每段最后一层；可改为 `params[start:end-1]` |
| FLOP 模型 `(k−1)/k` | 与"层为原子"的实现假设一致 | 与讲义 33% 的说法冲突，k = 1 时显示 0% |
| 显存模型混用 12 单位与 1 单位 | 简单地得到 √L 最优 | 结论自相矛盾；应统一用 `L/k + c·k`（c 为层内激活/层输入之比） |
| 纸面模型不含 S² 项 | 讲义只给了 `12·B·S·d` | 长序列下严重低估；可用 Korthikanti 等的 `S·B·h·(34 + 5·a·S/h)` 字节估算 |
| 阈值式 `should_recompute` | 演示 selective 的决策思路 | 不看显存预算、FlashAttention、offload；生产按预算整体规划 |
| 用 `max_grad_diff == 0` 验证 | CPU NumPy 确定性 | GPU 上应改用 `allclose` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@` 矩阵乘 | `x @ w + b`、`h.T @ g` | 二维数组的矩阵乘法；`.T` 是转置 |
| 广播 | `x @ w + b`（`(4,32)` + `(32,)`） | 低维数组自动沿缺失的维度扩展 |
| `np.maximum` | `np.maximum(x, 0.0)` | 逐元素取最大值，实现 ReLU |
| 布尔数组参与运算 | `gh * (h_pre > 0)` | `True/False` 当作 `1/0` |
| `axis` 规约 | `g.sum(axis=0)` | 沿 batch 维求和，得到 bias 梯度 |
| 元组解包 | `for w1, b1, w2, b2 in params:`、`g, grads[i] = layer_backward(...)` | 一次取出多个值；可以直接解包到列表元素 |
| `enumerate` + 嵌套解包 | `for i, (w1, b1, w2, b2) in enumerate(params):` | 同时拿到下标和被解包的元组 |
| 列表预分配 | `grads = [None] * len(params)` | 先占位，再按下标填入 |
| 倒序 `range` | `range(len(params) - 1, -1, -1)`、`range(n_seg - 1, -1, -1)` | 从后往前遍历 |
| 切片 | `params[start:end]` | 取出一段层的参数（左闭右开） |
| 整除向上取整 | `(len(params) + k - 1) // k` | `ceil(L / k)` 的整数写法 |
| 取模 | `(i + 1) % k == 0` | 每 k 层触发一次 |
| `zip` | `for gf, gc in zip(grads_full, grads_ck):` | 并行遍历两个序列 |
| 字典字面量 | `return {"fwd": fwd, ...}`、`cost['overhead_vs_no_ckpt']` | 用键名返回多个结果 |
| 默认参数 / 关键字参数 | `checkpoint_cost(64, selective=True)` | 只改需要的参数 |
| 新式随机数 | `np.random.default_rng(seed)`、`rng.standard_normal((a, b))` | 可复现的随机数生成器 |
| `.astype` | `.astype(np.float32)` | 转换 dtype |
| f-string 格式符 | `{seg:3d}`、`{cost['overhead_vs_no_ckpt']:.1%}`、`{...:.1f}` | 宽度 3 的整数、百分比格式（自动 ×100 加 %）、1 位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时（如本讲解用来做实验）不执行演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16 + NumPy，`python3 main.py`，约 0.13 秒）：

```text
equivalence: {'output_match': True, 'max_grad_diff': 0.0}   ← 梯度逐位相同
k=  1  overhead=0.0%      ← 代码模型：层为原子，k=1 无需重算（与讲义 33% 冲突）
k=  2  overhead=16.7%     ← 64 × 1/2 = 32 层重算 / 192
k=  4  overhead=25.0%
k=  8  overhead=29.2%
k= 16  overhead=31.2%
k= 32  overhead=32.3%
k= 64  overhead=32.8%     ← 63/192，趋近讲义的 33%
selective overhead: 5.0%  ← 9.6/192
optimal segment for L=64: 8
activation memory (no ckpt), L=64, d=8192, seq=8192, batch=1: 103079.2 MB   ← 每层 1.61 GB
  checkpoint k=  1: 8724.2 MB   ← 64 + 1 = 65 单位
  checkpoint k=  4: 2684.4 MB   ← 16 + 4 = 20 单位
  checkpoint k=  8: 2147.5 MB   ← 8 + 8 = 16 单位，最小
  checkpoint k= 16: 2684.4 MB   ← 4 + 16 = 20 单位
  checkpoint k= 32: 4563.4 MB   ← 2 + 32 = 34 单位
```

逐项解读：

- **等价性**：输出与梯度完全一致，说明 checkpointing 不改变训练结果。我们另外验证了 L 不能被 k 整除（7 层 k=3、6 层 k=4）以及 k = 1、k > L 的情况，差值都是 0.0。
- **开销随 k 增大而增大**：在代码的模型里，段越长，需要重算的层越多（`(k−1)/k`），趋向 33%。注意这里**没有**任何"代价"出现在显存一侧的 k 小端——这正是 3.8 所说的口径问题。
- **显存表**：呈 U 形，k = 8 = √64 处最低，展示了 √L 规则；但"103 GB → 8.7 GB（k=1）"的大幅下降是 12 单位 vs 1 单位的口径差造成的，若按自洽模型，k = 1 约 10.2 GB 且需要约 33% 的重算，k = 2 约 7.5 GB 才是最优（测验 Q9）。
- **讲义数字核对**：代码的 103 GB 是对的，讲义正文的"800 MB/layer、51 GB"少算了一半。

---

## 7. 动手改一改

1. **只重算 k−1 层**：把 `model_forward(x_in, params[start:end])` 改成 `params[start:end - 1]`，用一个计数包装器统计 `layer_forward` 调用次数，确认等于 `L − ⌈L/k⌉`，且 `verify_equivalence` 仍为 0.0。
2. **统一显存模型**：给 `memory_after_checkpoint` 增加参数 `inner_units=12`，峰值改为 `n_seg + inner_units * segment_size`；同时把 `checkpoint_cost` 的非 selective 分支改为"恒为一次完整 forward"。扫描 k = 1…64，找到新的最优 k 并与 `√(L/12)` 对比（讲义练习 2）。
3. **加入 S² 项**：给显存估算增加 `heads` 参数和 `B·heads·S²·bytes` 的 softmax 项，画出 S 从 2K 到 32K 时 attention 项占比的变化；再实现"selective = 只丢弃 softmax 项"的显存/开销计算（讲义练习 3）。
4. **模拟 offload**：把 `saved_inputs` 换成一个"CPU 缓冲区"类，记录写入/读出的字节数，按给定带宽计算传输时间，与重算时间比较，找出盈亏平衡带宽（讲义练习 4，参考测验 Q11）。
5. **递归 checkpoint**：在段内再按 √k 做一次 checkpoint，比较 O(√L) 与 O(log L) 显存方案的重算次数。
6. **进阶（需要 PyTorch）**：用 `torch.utils.checkpoint.checkpoint(block, x, use_reentrant=False)` 包装一个小 Transformer 的每个 block，在 GPU 上用 `torch.cuda.max_memory_allocated` 和步时间对比开关前后（讲义练习 5）。

---

## 8. 常见坑

- **以为 k = 1 是"零成本 checkpoint"**：只有当层内没有需要保存的中间激活时才成立；真实 Transformer 层内有大量中间激活，按层重算约 +33%。
- **把"值的个数"当字节数**：BF16 每个值 2 字节，讲义的 800 MB/51 GB 就是这样少算了一半。
- **只用 √L 规则不看比例**：段输入与段内激活体积相差很大时，√L 不是最优。
- **重算段内最后一层**：它的输出在 backward 中不会用到，白算一层。
- **checkpoint 段内有 in-place 操作**：保存的段输入被原地修改，重算时得到不同结果，梯度悄悄出错。
- **dropout 重算时 mask 不同**：要恢复 RNG 状态（PyTorch 默认 `preserve_rng_state=True`）。
- **FP8 重算更新了 amax**：scale 漂移，梯度被悄悄污染（讲义与 skill 都强调）。
- **已用 FlashAttention 仍做 attention selective 重算**：几乎没有收益，只增加开销。
- **单位混乱**：`should_recompute` 收 MB、讲义版收字节，调用方必须一致。
