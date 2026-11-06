# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 07 节 GPT — 因果语言建模 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码不训练任何模型，而是把 GPT 里"除了 Transformer 主体之外"的三件关键小事单独拎出来，用最朴素的 Python 写清楚：

1. **因果掩码**：一个下三角为 0、上三角为 `-inf` 的矩阵，加到 attention 分数上再做 softmax，未来位置的权重就精确地变成 0。
2. **next-token 交叉熵（shift-by-one）**：位置 i 的 logits 去预测位置 i+1 的 token，并和"均匀猜测"的基线 `ln V` 对比。
3. **五种采样策略**：greedy、temperature、top-k、top-p（nucleus）、min-p——都是"拿到一行 logits 之后怎么选下一个 token"。
4. **数值细节**：softmax 减最大值防溢出、全 `-inf` 行的保护、`log` 前对概率下限截断、累积采样的浮点兜底。

> 一句话：**掩码一行、loss 一个循环、采样十行**——GPT 和普通 Transformer 的区别，全部浓缩在这 180 行里。

⚠️ 文件顶部 docstring 写的是"Tiny GPT with random weights … four sampling strategies on a 20-token vocab"，但实际代码里**没有**任何模型权重：attention 分数和 logits 都是直接随机生成的；词表大小是 10；采样策略是 5 种（含 greedy）。讲义 Build It 第 2、3 步描述的"2 层 GPT + 绑定 embedding"在本文件中并未实现，读代码时以实际实现为准。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `softmax(logits, temperature)` | 函数 | 带温度的数值稳定 softmax | logits → 概率；temperature |
| `causal_mask(n)` | 函数 | 生成 n×n 因果掩码 | `M[i,j] = 0 if j<=i else -inf` |
| `attention_scores_with_mask` | 函数 | 分数矩阵与掩码逐元素相加 | 掩码加在 softmax **之前** |
| `apply_softmax_row(row)` | 函数 | 对含 `-inf` 的一行做 softmax，全屏蔽行返回全 0 | 掩码后的行归一化 |
| `cross_entropy_shifted` | 函数 | 位置 i 的 logits 对 `target[i+1]` 求平均 CE | shift-by-one loss |
| `sample_greedy` | 函数 | 取概率最大的下标 | greedy |
| `sample_from_distribution` | 函数 | 按累积概率做一次随机抽样 | 逆 CDF 采样 |
| `sample_temperature` | 函数 | 温度 softmax 后抽样 | temperature |
| `sample_top_k` / `sample_top_p` / `sample_min_p` | 函数 | 三种截断后再抽样 | top-k / nucleus / min-p |
| `demo_causal_mask` / `demo_sampling` / `demo_ce_loss` | 演示 | 分别打印三块内容 | — |
| `main()` | 入口 | 依次调用三个 demo | — |

数据流：`demo_causal_mask` 用 `causal_mask → attention_scores_with_mask → apply_softmax_row`；`demo_sampling` 用 `softmax` 和各个 `sample_*`（它们内部都复用 `softmax`；`sample_temperature`、`sample_top_k` 调用 `sample_from_distribution`，而 `sample_top_p`、`sample_min_p` 把同样的累积抽样循环内联写了一遍）；`demo_ce_loss` 用 `cross_entropy_shifted`。

---

## 3. 逐段精讲

### 3.1 带温度的 softmax

```python
def softmax(logits, temperature=1.0):
    if temperature != 1.0:
        logits = [x / temperature for x in logits]
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]
```

- **温度**：先把 logits 除以 T。T<1 放大差距（更尖锐），T>1 缩小差距（更平坦）。除以正数不改变大小顺序，所以 argmax 不变。
- **减最大值**：`softmax(z) = softmax(z - c)` 对任意常数 c 成立，减掉最大值后最大的指数是 `exp(0)=1`，避免 `math.exp(1000)` 溢出（`OverflowError`）。这是所有框架 softmax 的标准写法。
- `if temperature != 1.0` 只是省一次无用的除法；同时它**不修改**调用者传进来的列表（重新绑定局部变量 `logits`），没有副作用。
- ⚠️ `temperature=0` 会除零。真实框架会把 T→0 特判为 greedy。

### 3.2 因果掩码与加掩码

```python
def causal_mask(n):
    return [[0.0 if j <= i else float("-inf") for j in range(n)] for i in range(n)]


def attention_scores_with_mask(raw_scores, mask):
    return [[s + m for s, m in zip(row, mrow)] for row, mrow in zip(raw_scores, mask)]
```

- `causal_mask` 就是讲义里的定义：行 i 是 query 位置，列 j 是 key 位置，`j <= i`（过去和自己）为 0，`j > i`（未来）为 `-inf`。这正是 PyTorch 里一行 `torch.tril` 能做的事。
- 用**加法**而不是乘法：`s + 0 = s`（不变），`s + (-inf) = -inf`（屏蔽）。加到 softmax 之前，`exp(-inf) = 0`，归一化只在可见位置之间进行。
- 两层嵌套列表推导：外层 `zip(raw_scores, mask)` 按行配对，内层 `zip(row, mrow)` 按元素配对。
- 为什么不是"softmax 之后再置 0"：那样每行和会小于 1，而且未来位置的分数仍然出现在分母里，信息照样泄漏。

### 3.3 能处理 `-inf` 的逐行 softmax

```python
def apply_softmax_row(row):
    finite = [x for x in row if x != float("-inf")]
    if not finite:
        return [0.0] * len(row)
    m = max(finite)
    exps = [math.exp(x - m) if x != float("-inf") else 0.0 for x in row]
    s = sum(exps)
    return [e / s if s > 0 else 0.0 for e in exps]
```

- 和 3.1 的 `softmax` 相比多了两层保护：
  - **只在有限值中求最大值**；
  - **整行都是 `-inf` 时返回全 0**。否则 `max(row) = -inf`，`-inf - (-inf) = nan`，整行变 NaN。
- 在因果掩码下对角线永远是 0，不会出现全屏蔽行，所以这里换成 `softmax(row)` 结果一样；这份保护是为 padding 掩码等场景准备的"防御式编程"。
- 条件表达式 `a if cond else b` 写在推导式里，是 Python 中很常见的"逐元素分支"。

### 3.4 shift-by-one 交叉熵

```python
def cross_entropy_shifted(logits_per_pos, target_ids):
    """Next-token CE: logit_i vs target_{i+1}."""
    total = 0.0
    count = 0
    for i in range(len(target_ids) - 1):
        probs = softmax(logits_per_pos[i])
        p = probs[target_ids[i + 1]]
        total += -math.log(max(p, 1e-12))
        count += 1
    return total / count
```

- 核心是 `target_ids[i + 1]`：位置 i 的预测对应下一个 token。循环到 `len - 1` 为止，最后一个位置没有"下一个"，所以 N 个 token 只产生 N-1 个 loss——讲义里"输入 `[t1,t2,t3]`、目标 `[t2,t3,t4]`"说的就是这件事。
- `max(p, 1e-12)`：防止 `log(0) = -inf`（`math.log(0)` 实际会抛 `ValueError`）。生产框架用 `log_softmax` 直接在对数域计算，数值更稳。
- 返回**平均** loss（`total / count`），与 PyTorch `F.cross_entropy` 默认的 `reduction="mean"` 一致。讲义写的是"Sum"，二者只差一个常数因子。
- ⚠️ 简化：这里 logits 是外部给的；真实 GPT 中 `logits_per_pos` 来自一次前向（因果掩码保证位置 i 只看到 `≤ i` 的 token），并且会在 batch 维度上一起平均。

### 3.5 greedy 与基础抽样

```python
def sample_greedy(probs):
    return max(range(len(probs)), key=lambda i: probs[i])


def sample_from_distribution(probs, rng):
    r = rng.random()
    cum = 0.0
    for i, p in enumerate(probs):
        cum += p
        if r <= cum:
            return i
    return len(probs) - 1
```

- `max(range(n), key=...)` 是 Python 版的 argmax：遍历下标，按 `probs[i]` 比较。
- `sample_from_distribution` 是**逆 CDF 采样**：在 [0,1) 抽一个 r，沿累积概率走，第一次 `r <= cum` 的位置就是采样结果。概率越大的 token 占的区间越长，被抽中的机会越大。
- 最后的 `return len(probs) - 1` 是**浮点兜底**：概率加起来可能是 `0.9999999999` 而 r 恰好更大，此时循环走完也没返回。
- `rng` 是外部传入的 `random.Random` 实例，而不是全局 `random`：可复现、互不干扰，这是写可测试随机代码的好习惯。

### 3.6 temperature 与 top-k

```python
def sample_temperature(logits, t, rng):
    probs = softmax(logits, temperature=t)
    return sample_from_distribution(probs, rng)


def sample_top_k(logits, k, rng, temperature=1.0):
    indexed = sorted(enumerate(logits), key=lambda x: -x[1])
    keep = indexed[:k]
    keep_ids = [i for i, _ in keep]
    keep_logits = [v for _, v in keep]
    probs = softmax(keep_logits, temperature=temperature)
    chosen = sample_from_distribution(probs, rng)
    return keep_ids[chosen]
```

- `sorted(enumerate(logits), key=lambda x: -x[1])`：把 `(下标, logit)` 按 logit 降序排序。用 `enumerate` 是为了**排序后还记得原始下标**。
- 只对前 k 个 logits 做 softmax，等价于"其余 token 概率置 0 后重新归一化"。
- 采样得到的是在 `keep` 里的位置 `chosen`，最后要用 `keep_ids[chosen]` **映射回词表下标**——漏掉这一步是手写 top-k 最常见的 bug。
- 温度在截断之后应用也没关系：温度不改变排序，top-k 选出的集合不变。

### 3.7 top-p（nucleus）

```python
def sample_top_p(logits, p, rng, temperature=1.0):
    probs = softmax(logits, temperature=temperature)
    indexed = sorted(enumerate(probs), key=lambda x: -x[1])
    cum = 0.0
    cutoff = len(indexed)
    for i, (_, pi) in enumerate(indexed):
        cum += pi
        if cum >= p:
            cutoff = i + 1
            break
    kept = indexed[:cutoff]
    total = sum(pi for _, pi in kept)
    renorm = [(idx, pi / total) for idx, pi in kept]
    # ... 之后与 sample_from_distribution 相同的累积抽样，返回 idx
```

- 先算概率、按概率降序，再累加，**首次 `cum >= p`** 时截断，`cutoff = i + 1` 让"跨过 p 的那个 token"也被保留。
- 和 top-k 不同，这里温度必须**先**应用：温度改变分布形状，从而改变需要几个 token 才能累计到 p。
- 截断后除以 `total` 重新归一化，再抽样。返回的 `idx` 已经是原始词表下标（因为 `renorm` 里保存的是 `(idx, prob)` 对）。
- 在本文件的分布上，top-p=0.9 会保留 6 个 token（累计到第 6 个时为 0.916）。

### 3.8 min-p

```python
def sample_min_p(logits, min_p, rng, temperature=1.0):
    probs = softmax(logits, temperature=temperature)
    max_p = max(probs)
    threshold = min_p * max_p
    kept = [(i, pi) for i, pi in enumerate(probs) if pi >= threshold]
    total = sum(pi for _, pi in kept)
    renorm = [(i, pi / total) for i, pi in kept]
    # ... 累积抽样
```

- 阈值是 `min_p × 最大概率`，**随分布尖锐程度自适应**：模型很确定时只保留少数头部 token，分布平坦时保留更多。
- 不需要排序，一次遍历即可，比 top-p 更便宜。
- 本例 `max_p = 0.380`，阈值 0.038，保留 `the, cat, dog, ran, jumped, mat` 6 个（ran 的 0.0381 恰好压线）。
- 讲义表格写的是 `p > min_p * max_p`，Key Terms 和本代码用的是 `≥`；只在恰好等于阈值时有区别。

### 3.9 三个 demo

```python
def demo_causal_mask():
    # ...
    n = 6
    rng = random.Random(42)
    raw = [[rng.gauss(0, 1) for _ in range(n)] for _ in range(n)]
    mask = causal_mask(n)
    masked = attention_scores_with_mask(raw, mask)
    attn = [apply_softmax_row(row) for row in masked]
```

```python
def demo_ce_loss():
    # ...
    for i in range(len(seq) - 1):
        logits[i][seq[i + 1]] += 2.0
    loss_trained = cross_entropy_shifted(logits, seq)
```

- `demo_causal_mask`：用 `N(0,1)` 随机数代替 `QKᵀ/√d_k` 的分数，加掩码、逐行 softmax，打印 6×6 矩阵。
- `demo_sampling`：固定 10 个词和 10 个 logits，打印概率表，然后用同一个 `random.Random(0)` 依次调用 6 种选择方式。注意 rng 是**共享**的，每次采样都会消耗一个随机数，所以调换调用顺序会改变结果。
- `demo_ce_loss`：给正确的下一个 token 的 logit 加 2.0，模拟"训练过一点"的模型；另一组完全随机；再和 `ln V` 对比。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表、无 NumPy | 每一步都看得见，和讲义公式一一对应 | 慢；生产中用张量运算，掩码用 `torch.tril` 或 kernel 内置 causal 模式 |
| 随机分数代替真实 `QKᵀ` | 本节重点是掩码，不是 attention 本身 | 看不到真实模型的注意力模式 |
| 掩码用加法 + `-inf` | `exp(-inf)=0`，归一化只在可见位置进行 | 全屏蔽行会出 NaN；框架常用 `finfo.min` 代替 `-inf` |
| `apply_softmax_row` 单独处理 `-inf` | 防御全屏蔽行 | 多一份重复代码 |
| `max(p, 1e-12)` 截断 | 避免 `log(0)` | 生产中用 `log_softmax` 在对数域计算 |
| 采样函数接收 `rng` 参数 | 可复现、可测试 | 调用方需要管理随机状态 |
| 采样逐个函数实现 | 每种策略独立可读 | 真实框架（如 HF 的 logits processor）把它们串成流水线，可叠加使用 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def softmax(logits, temperature=1.0)` | 调用时可省略，省略时取默认值 |
| `float("-inf")` | `causal_mask` 里的 `-inf` | Python 的负无穷浮点数；`math.exp(float("-inf"))` 等于 `0.0` |
| 列表推导式 | `[x / temperature for x in logits]` | 一行生成新列表 |
| 嵌套列表推导 | `[[... for j in range(n)] for i in range(n)]` | 外层产生行、内层产生列，生成二维列表 |
| 推导式中的条件表达式 | `0.0 if j <= i else float("-inf")` | `A if 条件 else B`，逐元素二选一 |
| 推导式中的过滤 | `[x for x in row if x != float("-inf")]` | 末尾的 `if` 用来筛选元素 |
| `zip` | `zip(row, mrow)` | 按位置配对多个序列 |
| `enumerate` | `for i, p in enumerate(probs)` | 同时拿到下标和元素 |
| 元组解包 | `for i, (_, pi) in enumerate(indexed)` | 可嵌套解包；`_` 表示"不关心的值" |
| `lambda` + `key=` | `sorted(..., key=lambda x: -x[1])`、`max(range(n), key=lambda i: probs[i])` | 自定义排序/比较依据；取负号实现降序 |
| 切片 | `indexed[:k]`、`indexed[:cutoff]` | 取前若干个元素 |
| 生成器表达式 | `sum(pi for _, pi in kept)` | 不建中间列表直接求和 |
| `random.Random(seed)` | `rng = random.Random(42)` | 独立的随机数生成器实例，`rng.random()`、`rng.gauss(0, 1)` |
| f-string 格式符 | `f"{v:.3f}"`、`f"{l:+.2f}"`、`f"{w:<8}"` | `.3f` 三位小数；`+` 总显示正负号；`<8` 左对齐占 8 格 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13）输出如下：

```text
=== causal attention matrix (post-softmax) ===
  1.000  0.000  0.000  0.000  0.000  0.000
  0.646  0.354  0.000  0.000  0.000  0.000
  0.547  0.317  0.136  0.000  0.000  0.000
  0.269  0.232  0.439  0.060  0.000  0.000
  0.295  0.097  0.180  0.158  0.270  0.000
  0.327  0.041  0.013  0.101  0.074  0.444
  (every row is a valid probability distribution over positions 0..i)
```

- 对角线以上全是 0.000：掩码生效，第 i 行只在列 0…i 上有权重（讲义练习 1 的"第 3 行只在列 0–3 有权重"可以直接看到）。
- 第 0 行只能看自己，所以恒为 `1.000`；每一行加起来都是 1。
- 非零部分的大小是随机的——这里没有训练，分数来自 `gauss(0,1)`。

```text
token       logit   prob
  the       +3.20   0.380
  dog       +2.80   0.255
  mat       +2.10   0.127
  ...
greedy:         the
temp=0.7:       jumped
temp=2.0:       mat
top-k=3:        the
top-p=0.9:      the
min-p=0.1:      dog
```

- greedy 永远选概率最大的 `the`（0.380）。
- `temp=0.7` 选中了 `jumped`：T=0.7 时 `jumped` 的概率只有约 0.044，这次是第一个随机数 0.844 恰好落在它的区间里——**采样就是会选中非最优 token**，这正是多样性的来源，也是风险的来源。
- `temp=2.0` 选中 `mat`：高温使分布变平（`the` 从 0.380 降到约 0.226），尾部 token 更容易被选中。
- top-k=3 只可能在 `the/dog/mat` 中选；top-p=0.9 在 6 个 token 中选；min-p=0.1 在 6 个 token（阈值 0.038）中选。具体选中谁取决于共享 rng 的随机数序列。

```text
loss with biased logits (trained-ish):  1.145
loss with random logits:                2.418
random-baseline loss (ln V = ln 10):      2.303
```

- 给正确 token 加 2.0 的 logits 得到 1.145，明显低于基线：模型"学到了点东西"。
- 随机 logits 的 2.418 **高于** `ln 10`：均匀分布（所有 logits 相等）才恰好是 `ln V`；随机 logits 会"随机地自信"，平均比均匀还差。训练第 0 步的 loss 应该在 `ln V` 附近，这是排查初始化的常用信号。

---

## 7. 动手改一改

1. **验证行和**：在 `demo_causal_mask` 里对每行 `assert abs(sum(row) - 1) < 1e-9`，再检查 `row[j] == 0 for j > i`。
2. **温度扫描**：对 `demo_sampling` 的 logits，打印 T ∈ {0.1, 0.5, 1, 2, 10} 时 `the` 的概率和分布的熵，观察 T→0 与 T→∞ 的两个极限。
3. **蒙特卡洛统计**：对每种采样方法抽 10000 次，统计每个词被选中的频率，验证 top-k=3 从不选出第 4 名、top-p 与 min-p 的支持集都是 6 个词。
4. **加 repetition penalty**：写 `apply_repetition_penalty(logits, generated_ids, penalty=1.2)`，对已出现 token 的正 logit 除以 penalty、负 logit 乘以 penalty。
5. **写一个生成循环**：用一个"假模型"函数 `fake_model(ids) -> logits`（例如根据最后一个 id 查一张随机转移表），实现 `generate(prompt_ids, max_new_tokens, sampler)`，对比 greedy 与 min-p 的输出是否会陷入循环。
6. **进阶**：用 NumPy 把 `demo_causal_mask` 改成真实的 `QKᵀ/√d_k`（随机 X、Wq、Wk），并验证"改最后一个 token 的输入，前面位置的 attention 输出不变"。

---

## 8. 常见坑

- **掩码方向写反**：`j <= i` 写成 `j >= i` 会得到"只看未来"的上三角掩码，模型训练 loss 会异常地低（直接抄答案），推理时却完全不能用。
- **在 softmax 之后屏蔽**：行和小于 1，且未来信息已经通过分母泄漏。
- **全屏蔽行产生 NaN**：padding 掩码和因果掩码叠加时可能出现；要么用有限大负数，要么像 `apply_softmax_row` 一样特判。
- **top-k / top-p 忘记映射回原下标**：排序后的位置不等于词表 id。
- **temperature 与 top-p 的顺序**：先截断再加温度，和先加温度再截断，得到的 nucleus 集合不同；常规做法是先温度后截断。
- **共享 rng 导致结果"看起来随机"**：调换 `demo_sampling` 里几行的顺序，输出就会变；比较不同采样方法时应为每种方法单独设种子，或做大量抽样统计。
