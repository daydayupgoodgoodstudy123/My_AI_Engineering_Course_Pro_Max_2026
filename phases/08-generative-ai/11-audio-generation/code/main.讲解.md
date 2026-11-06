# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 11 节 音频生成 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，瞬间完成） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

真实的音频生成管线是"**codec 把波形变成 token → 生成器生成 token → codec 解码回波形**"。这份代码跳过了 codec，直接在合成的"音频 token"上演示生成器这一环：

1. **音频 = token 序列**：假设 codec 已经把音频编码成 0–15 的离散 token，两种"风格"对应两种序列规律。
2. **按条件训练一个下一个 token 预测器**：用最简单的 bigram 计数表 `counts[style][prev][next]` 代替 transformer。训练就是数数，预测就是按行归一化。
3. **自回归采样 + 温度**：从起始 token 开始逐个采样，温度控制分布的尖锐程度。
4. **熵**：用来衡量"下一个 token 有多不确定"。
5. **提示续写**：模仿 VALL-E 用一段"语音提示"作前缀往后续写（但 bigram 模型其实只看得到提示的最后一个 token，见 3.5）。

> 一句话：**token 化之后，音频生成就是语言建模**——"数据 → 交叉熵训练（这里是计数）→ 自回归采样"这条链路与 GPT 完全相同。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VOCAB = 16`、`NUM_STYLES = 2` | 常量 | 码本大小、风格（条件）数 | codec 码本大小（真实为 1024/2048）、条件类别 |
| `make_tokens(style, length, rng)` | 函数 | 生成两种风格的合成 token 序列 | codec 编码后的训练数据 |
| `init_counts()` | 函数 | 建 `2×16×16` 的计数表，初值全为 1.0 | 加一平滑（Laplace smoothing） |
| `update_counts(counts, sequence, style)` | 函数 | 统计相邻 token 对出现的次数 | "训练"：最大似然估计 |
| `probs(counts, style, prev_tok)` | 函数 | 取一行计数并归一化 | 条件分布 `p(next | style, prev)` |
| `entropy(p)` | 函数 | 计算香农熵（nats） | 预测的不确定性 |
| `sample_from(p, rng)` | 函数 | 逆累积分布采样 | 从分类分布中抽样 |
| `generate(counts, style, start, length, rng, temperature)` | 函数 | 带温度的自回归生成 | 自回归解码 |
| `main()` | 函数 | 训练 → 两种风格 × 两种温度生成 → 打印熵 → 提示续写 | 实验编排 |

数据流：`make_tokens → update_counts`（训练）；`generate → probs → (温度) → sample_from`（生成）。

---

## 3. 逐段精讲

### 3.1 合成"音频 token"：`make_tokens`

```python
VOCAB = 16
NUM_STYLES = 2


def make_tokens(style, length, rng):
    """Synthetic 'audio token' sequences by style."""
    if style == 0:  # alternating, speech-like
        return [(i + rng.randint(0, 1)) % VOCAB for i in range(length)]
    return [(i * 3 + rng.randint(0, 1)) % VOCAB for i in range(length)]
```

- `rng.randint(0, 1)` 返回 0 或 1（**两端都包含**），给每个位置加一点抖动；`% VOCAB` 让 token 在 0–15 之间循环。
- style 0：第 i 个 token ≈ `i`，相邻差为 `1 + bᵢ₊₁ − bᵢ ∈ {0, 1, 2}`，概率 1/4、1/2、1/4——是一条**步长约为 1 的上升斜坡**。
- style 1：相邻差为 `{2, 3, 4}`，是一条步长约为 3 的斜坡。
- ⚠️ 注释和 `main` 里的标签写的是 "alternating, speech-like"，讲义 Build It 也说 style A 是"高低交替"，但代码生成的并不是交替序列；讲义 Step 1 的代码片段（`i % vocab_size`）同样是斜坡。两种风格的区别其实是**步长不同**。这不影响演示"按条件学习不同的转移规律"，但读输出时别被标签误导。
- 真实 codec token 的规律复杂得多：相邻帧的 token 会随音素、音高、音色变化，这正是需要 transformer 的原因。

### 3.2 训练 = 数数：`init_counts` / `update_counts` / `probs`

```python
def init_counts():
    return [[[1.0 for _ in range(VOCAB)] for _ in range(VOCAB)] for _ in range(NUM_STYLES)]


def update_counts(counts, sequence, style):
    for i in range(len(sequence) - 1):
        counts[style][sequence[i]][sequence[i + 1]] += 1.0


def probs(counts, style, prev_tok):
    row = counts[style][prev_tok]
    total = sum(row)
    return [x / total for x in row]
```

- 三层嵌套推导式建出形状为 `[style][prev][next]` 的表，`2 × 16 × 16 = 512` 个"参数"。
- **初值 1.0 = 加一平滑**：保证每个转移都有非零概率，避免 `log(0)`，也让模型能生成训练中没见过的转移。代价是给不可能的转移分配了概率，会造成"毛刺"（见第 6 节）。
- `update_counts` 遍历所有相邻对 `(sequence[i], sequence[i+1])`，在对应风格的表里加 1。计数再归一化，就是 bigram 模型的**最大似然估计**——等价于用交叉熵训练一个只看上一个 token 的模型，并且能直接得到闭式解。
- 条件（style）通过"每个风格一张表"实现。真实系统中，条件是文本 / 风格标签 / 说话人提示，通过前缀或 cross-attention 输入 transformer。

### 3.3 采样与温度：`sample_from` / `generate`

```python
def sample_from(p, rng):
    r = rng.random()
    acc = 0.0
    for i, pi in enumerate(p):
        acc += pi
        if r <= acc:
            return i
    return len(p) - 1


def generate(counts, style, start, length, rng, temperature=1.0):
    out = [start]
    for _ in range(length - 1):
        p = probs(counts, style, out[-1])
        if temperature != 1.0:
            p = [pi ** (1 / temperature) for pi in p]
            total = sum(p)
            p = [x / total for x in p]
        out.append(sample_from(p, rng))
    return out
```

- `sample_from` 是**逆 CDF 采样**：在 [0,1) 里抽一个随机数 `r`，沿着累积概率走，第一个使累积和 ≥ r 的下标就是结果。最后的 `return len(p) - 1` 防止浮点舍入导致累积和略小于 1 时找不到结果。
- `out[-1]` 取最后一个已生成的 token——bigram 的"上下文"只有它。
- **温度**：`p^(1/T)` 再归一化，等价于 `softmax(logits / T)`（因为 `p = softmax(logits)`，`p^(1/T) ∝ exp(logits/T)`）。`T < 1` 分布更尖、`T > 1` 更平。
- `if temperature != 1.0` 跳过 `T = 1` 时不必要的计算。⚠️ 温度为 0 时 `1 / temperature` 会除零；要实现贪心解码，应单独分支取 `argmax`。

### 3.4 熵：`entropy`

```python
def entropy(p):
    return -sum(pi * math.log(max(pi, 1e-10)) for pi in p)
```

- `H(p) = −Σ pᵢ ln pᵢ`，用自然对数，单位是 nats。
- `max(pi, 1e-10)` 防止 `log(0)`；这里由于加一平滑，`pi` 不会是 0，但写上更安全。
- `main` 打印的标题是 "entropy at each position"，⚠️ 实际只计算了 `style=0, prev=5` 这一行的熵。

### 3.5 "VALL-E 式"提示续写

```python
    prompt = make_tokens(0, length=5, rng=rng)[:5]
    print(f"  3-second voice prompt (tokens): {prompt}")
    continuation = list(prompt)
    for _ in range(15):
        p = probs(counts, 0, continuation[-1])
        continuation.append(sample_from(p, rng))
```

- 用 style 0 生成 5 个 token 作为"语音提示"，然后往后续写 15 个（`[:5]` 是多余的切片，长度本来就是 5）。
- `list(prompt)` 复制一份，避免修改 `prompt` 本身。
- ⚠️ **bigram 只看最后一个 token**：提示的前 4 个 token 对续写毫无影响，"音色"根本无从体现。真实 VALL-E 把 3 秒提示的 codec token 和目标文本一起放进 transformer 的上下文，靠注意力从提示中提取说话人特征（测验 Q15）。这里只演示了"前缀 + 续写"的**形式**。
- 续写直接用 `probs`，没有经过温度（相当于 T = 1）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 跳过 codec，直接用合成 token | 聚焦"token 上的生成" | 真实系统中 codec（Encodec/DAC）决定质量上限 |
| bigram 计数表代替 transformer | 训练即计数，零依赖、瞬间完成 | 上下文只有 1 个 token，无法利用提示、无法建模长结构；讲义 Build It 说的 "tiny next-token transformer" 实际是 bigram |
| 加一平滑 | 避免零概率 | 给不可能的转移分配约 2.6% 的概率，产生毛刺；生产中用 top-k/top-p/低温截断 |
| 每个风格一张表 | 条件生成最直观的实现 | 条件多时表的数量爆炸；transformer 用 embedding 共享参数 |
| 单码本 | 简化 | 真实 codec 每帧有 K 个 RVQ 码本，需要 delay pattern 或分层生成 |
| 温度用 `p^(1/T)` | 与 softmax 温度等价 | `T = 0` 需要单独处理 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `VOCAB = 16`、`NUM_STYLES = 2` | 全局共享的配置 |
| 取模 `%` | `(i + rng.randint(0, 1)) % VOCAB` | 让 token 在 0–15 之间循环 |
| `rng.randint(a, b)` | `rng.randint(0, 1)` | 闭区间 [a, b] 内的整数，**两端都包含**（与 `randrange` 不同） |
| 三层嵌套列表推导 | `[[[1.0 for _ in range(VOCAB)] for _ in range(VOCAB)] for _ in range(NUM_STYLES)]` | 建三维表；每层都新建列表，避免共享引用 |
| 多级下标 | `counts[style][sequence[i]][sequence[i + 1]] += 1.0` | 访问三维嵌套列表 |
| `enumerate` | `for i, pi in enumerate(p)` | 同时拿到下标和值 |
| 负下标 | `out[-1]`、`continuation[-1]` | 取最后一个元素 |
| 幂运算 | `pi ** (1 / temperature)` | 温度缩放 |
| 生成器表达式 + `sum` | `-sum(pi * math.log(max(pi, 1e-10)) for pi in p)` | 计算熵 |
| `sorted` + `key` + `lambda` | `sorted(range(VOCAB), key=lambda i: -p[i])[:3]` | 按概率从大到小排序下标，取前 3 |
| `round` | `round(p[i], 3)` | 保留 3 位小数 |
| 列表推导生成元组 | `[(i, round(p[i], 3)) for i in top3]` | 打印 `(token, 概率)` 对 |
| `list()` 复制 | `continuation = list(prompt)` | 浅拷贝，避免修改原列表 |
| f-string 中的 `\n` | `print(f"\nstyle {style}: {label}")` | 先输出空行 |
| 默认参数 | `temperature=1.0` | 不传时使用默认温度 |

---

## 6. 运行结果解读

实际运行输出：

```text
=== training codec-token bigram per style on 500 sequences each ===

=== generate 20 tokens per style, start=0 ===

style 0: speech-like (alternating)
  temp 0.7: [0, 2, 3, 4, 4, 5, 6, 7, 8, 9, 9, 11, 12, 14, 14, 15, 0, 2, 3, 4]
  temp 1.0: [0, 2, 2, 3, 3, 4, 4, 5, 6, 6, 6, 7, 8, 10, 11, 11, 12, 13, 13, 14]

style 1: music-like (ramp)
  temp 0.7: [0, 3, 6, 9, 12, 15, 2, 5, 8, 12, 15, 3, 5, 8, 12, 0, 4, 7, 11, 15]
  temp 1.0: [0, 4, 6, 13, 15, 1, 4, 7, 9, 12, 0, 2, 5, 9, 10, 12, 15, 2, 4, 8]

=== entropy at each position for style 0 conditional on token 5 ===
  p(next | style=0, prev=5): H = 1.201
  top-3: [(6, 0.482), (7, 0.25), (5, 0.242)]

=== VALL-E-style prompt continuation ===
  3-second voice prompt (tokens): [0, 2, 2, 3, 5]
  continuation: [0, 2, 2, 3, 5, 6, 6, 7, 8, 8, 9, 10, 12, 14, 14, 15, 12, 13, 13, 14]

takeaway: tokens + transformer = entire TTS / music generation substrate.
          RVQ of Encodec / DAC makes real audio fit in the same loop.
```

逐段解读：

- **style 0**：两条序列都是每步 +0/+1/+2 的上升斜坡，到 15 之后回绕到 0（`15, 0, 2`）——模型学到了"步长约为 1"的规律。注意它**不是**标签所说的"交替"。
- **style 1**：`temp 0.7` 那行几乎都是 +3 或 +4，非常规整；`temp 1.0` 中出现了 `6, 13`（+7），这是训练数据中**不可能**出现的转移，来自加一平滑分配给未见转移的那点概率。
- **熵与 top-3**：理论分布是 `{6: 0.5, 7: 0.25, 5: 0.25}`，熵约 1.040 nats。实测 0.482 / 0.25 / 0.242，剩下约 2.6%（= 13/508，这一行计数总和为 508）分散在 13 个不可能的 token 上，把熵抬高到 1.201。
- **续写**：前半段 `5, 6, 6, 7, 8, ...` 符合 style 0 规律，但出现了 `15, 12`（−3），又是一次平滑毛刺。在真实音频中，这种 token 相当于一声"咔哒"。
- 我们在临时副本中估算：温度 1.0 时，长度 20 的序列中至少出现一次毛刺的概率约 39%；温度 0.7 时，单步非法概率从 2.56% 降到约 0.28%。这正是生产中普遍使用 top-k / top-p / 低温度的原因。

---

## 7. 动手改一改

1. **讲义练习 1**：写一个函数检查生成序列的相邻差是否都落在该风格的合法集合内（style 0：{0,1,2}；style 1：{2,3,4}），统计不同温度下的违规率。
2. **去掉平滑**：把 `init_counts` 的初值改成 `1e-6`，观察毛刺是否消失、熵是否接近 1.040；再想想如果遇到训练中没出现过的 `prev`，会发生什么。
3. **加 top-k 截断**：在 `generate` 里只保留概率最高的 k 个 token 再归一化，对比温度与 top-k 的效果。
4. **改成真正的"交替"风格**：把 style 0 改成 `[(0 if i % 2 == 0 else 8) + rng.randint(0, 1) for i in range(length)]`，看看 bigram 能否学会高低交替。
5. **让提示起作用**：把模型改成 trigram（`counts[style][prev2][prev1][next]`），对比提示前缀不同时续写的分布变化。
6. **讲义练习 2：delayed parallel**：构造两路码本流（第二路是第一路的某个函数），按 delay pattern 错开 1 步排布，训练一个"输入上一列、输出下一列"的联合计数模型（delay pattern 的排布函数见测验 Q11）。

---

## 8. 常见坑

- **`randint` 与 `randrange` 混淆**：`randint(0, 1)` 包含 1，`randrange(0, 1)` 永远返回 0。
- **温度为 0 时除零**：`1 / temperature` 会抛 `ZeroDivisionError`，贪心解码要单独写 `argmax`。
- **以为 bigram 能利用长提示**：一阶马尔可夫模型只看最后一个 token。
- **平滑的副作用**：加一平滑在小词表、大数据量时影响不大，但在长序列生成中，"小概率 × 很多步"会累积成明显的毛刺。
- **信标签不信代码**：输出里写着 "alternating"，实际却是斜坡；分析结果时以代码逻辑为准。
- **三维列表的浅拷贝陷阱**：`[[[1.0]*16]*16]*2` 会让各行共享同一个列表，`+= 1.0` 会同时改到很多位置；本文件用推导式规避了这个问题。
