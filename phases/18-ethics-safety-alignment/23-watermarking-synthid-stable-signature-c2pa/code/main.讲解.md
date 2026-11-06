# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 23 节 水印：SynthID、Stable Signature、C2PA ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`hashlib`、`math`、`random`），无需网络、无需 GPU

---

## 1. 这份代码在考察什么

这是一个约 110 行的"玩具版 SynthID-text / Kirchenbauer 水印"。它把词表抽象成整数 `0..199`，不涉及任何真实模型，只保留水印最核心的统计结构：

1. **嵌入**：每一步用前 `K = 4` 个 token 做哈希，把词表分成 green / red 两半，然后以 0.9 的概率从 green 中采样（讲义中的"给 green logits 加 δ"）。
2. **检测**：重算每个位置的 green 集合、数 green token，算 z-score——本质是一个**单侧二项检验**。
3. **攻击**：随机替换 30% / 60% 的 token，观察信号衰减（讲义 Limitations 中的 paraphrase 脆弱性）。
4. **误报**：对 100 段"人类文本"（均匀随机 token）测量 z ≥ 4 的比例（讲义练习 1）。

> 一句话：**文本水印 = 有偏采样 + 假设检验**；它的强度取决于文本长度、每步偏置和哈希上下文能否原样保留。同时要看清这个玩具在密钥、分区、分布假设上的简化——它们决定了真实系统的安全性。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VOCAB = 200`、`K = 4` | 模块常量 | 词表大小、哈希上下文长度 | 词表、context width |
| `random.seed(61)` | 模块级语句 | 固定随机性，保证输出可复现 | 可复现实验 |
| `green_set(prev_tokens)` | 函数 | SHA-256(前 K 个 token) → 按奇偶划分 green 集合 | 伪随机词表分区 |
| `unwatermarked_sample(n, seed_prefix)` | 函数 | 均匀随机采样 n 个 token | "人类文本" / H0 |
| `watermarked_sample(n, seed_prefix, bias)` | 函数 | 以 `bias` 的概率从 green 集合中采样 | 有偏采样嵌入 |
| `detect(tokens)` | 函数 | 统计 green 数并返回 z-score | 二项检验 |
| `paraphrase(tokens, ratio)` | 函数 | 每个位置以 `ratio` 概率换成随机 token | 改写攻击（简化版） |
| `main()` | 函数 | 依次跑：嵌入/检测 → 改写攻击 → FPR → 打印结论 | 实验流程 |

数据流：`seed`（4 个随机 token）→ `watermarked_sample` / `unwatermarked_sample` 生成 1004 个 token → `detect` 得 z → `paraphrase` 后再 `detect` → 100 次无水印样本的 `detect` 统计 FPR → 打印。

---

## 3. 逐段精讲

### 3.1 `green_set`：把哈希变成词表分区

```python
def green_set(prev_tokens: list[int]) -> set[int]:
    """Pseudorandom partition of the vocabulary into green (half of it)."""
    seed = ",".join(str(t) for t in prev_tokens[-K:])
    digest = hashlib.sha256(seed.encode()).hexdigest()
    h = int(digest, 16)
    # partition: token is green iff (token + h) mod 2 == 0
    return {t for t in range(VOCAB) if (t + h) % 2 == 0}
```

- `prev_tokens[-K:]` 取最后 4 个 token，拼成 `"12,7,199,3"` 这样的字符串，再做 SHA-256。`int(digest, 16)` 把 64 位十六进制串转成一个 256 比特的大整数——Python 整数没有上限，可以直接这么做。
- 划分规则 `(t + h) % 2 == 0`：只用到了 `h` 的**最低 1 位**。h 为偶数时 green = 全部偶数 token，h 为奇数时 green = 全部奇数 token。我们枚举了 200 个不同上下文，只得到 **2 种** green 集合。
- green 集合大小恒为 100，即 γ = 0.5，与 `detect` 中硬编码的 0.5 对应。
- ⚠️ **没有密钥**：哈希输入只有上下文 token。任何人读到这段代码就能检测、擦除（专挑 red token 替换）或伪造（往人写文本里塞 green token）。讲义说"Detectable with access to the vocabulary partition function"——生产中这个函数必须带密钥（如 HMAC），见测验 Q9 的改造版。
- ⚠️ 文件头 docstring 说"green (even hash) and red (odd hash)"，与实际规则"(token + hash) 为偶数则 green"不完全一致：是 token 与哈希的**和**的奇偶，而不是哈希本身的奇偶。
- 每次调用都会新建一个 100 元素的集合；`detect` 对 1000 个位置各调一次，复杂度 `O(n·V)`。玩具规模没问题，真实词表（十几万）下应只判断"这个 token 是否 green"，而不是构造整个集合。

### 3.2 两种采样：H0 与带水印

```python
def unwatermarked_sample(n: int, seed_prefix: list[int]) -> list[int]:
    out = list(seed_prefix)
    for _ in range(n):
        out.append(random.randrange(VOCAB))
    return out


def watermarked_sample(n: int, seed_prefix: list[int], bias: float = 0.9) -> list[int]:
    """Bias = probability of sampling from the green set."""
    out = list(seed_prefix)
    for _ in range(n):
        greens = green_set(out)
        use_green = random.random() < bias
        pool = list(greens) if use_green else list(set(range(VOCAB)) - greens)
        out.append(random.choice(pool))
    return out
```

- 两者都以 `seed_prefix`（4 个 token）开头，再追加 n 个 token，所以返回长度是 `n + K = 1004`。前 4 个 token 只作为第一步的哈希上下文，不参与计分。
- `list(seed_prefix)` 做了一次**复制**，避免修改调用方传入的列表。
- 无水印采样是均匀分布：每个 token 落入 green 的概率恰为 0.5——这就是检验的零假设 H0。
- 带水印采样：先抛一枚 `P(正面) = 0.9` 的硬币决定从 green 还是 red 里抽，再在该组内均匀抽一个。
- ⚠️ **与讲义的机制不同**：讲义是"adding δ to green logits"，即在模型原有分布上加偏置；代码是"直接以 0.9 的概率选 green"，并且基础分布是均匀的。均匀分布下二者等价（`e^δ/(e^δ+1) = 0.9 ⇒ δ = ln 9 ≈ 2.20`），但真实模型在低熵位置（下一个 token 几乎确定）加 δ 几乎改变不了选择。测验 Q10 算过：δ = 2 时，若 top-1 概率为 0.99，该步平均 green 概率只有 0.518。所以本节的 z = 25.3 是"最大熵 + 每步都生效"的**乐观上限**。
- `set(range(VOCAB)) - greens` 是集合差，得到 red 集合；`random.choice` 需要序列，所以先 `list(...)`。

### 3.3 `detect`：一次单侧 z 检验

```python
def detect(tokens: list[int]) -> float:
    """Returns z-score: (green count - expected) / sqrt(expected * p(1-p))."""
    if len(tokens) <= K:
        return 0.0
    green_count = 0
    for i in range(K, len(tokens)):
        greens = green_set(tokens[:i])
        if tokens[i] in greens:
            green_count += 1
    n = len(tokens) - K
    expected = n * 0.5
    std = math.sqrt(n * 0.5 * 0.5)
    return (green_count - expected) / std
```

- 从第 `K` 个位置开始，对每个 token 用它前面的上下文 `tokens[:i]`（`green_set` 内部再取最后 K 个）重算 green 集合——检测只需要**分区函数**，不需要模型。
- H0 下 green 数 `G ~ Binomial(n, 0.5)`，均值 `0.5n`，方差 `0.25n`；`z = (G − 0.5n)/√(0.25n)`。n = 1000 时标准差 15.81。
- 期望 z 的闭式：每 token green 概率为 p 时 `z ≈ (p − 0.5)√n / 0.5`。p = 0.9 时 `z = 0.8√n`，n = 1000 得 **25.30**，正是运行输出。
- ⚠️ docstring 写的是 `sqrt(expected * p(1-p))`，但代码实际是 `sqrt(n * p(1-p))`（代码是对的，docstring 多了一个 expected）。
- ⚠️ γ = 0.5 被硬编码在 `expected` 和 `std` 中；若把 `green_set` 改成其他比例，这里必须同步修改，否则 z 会系统性偏移。
- `tokens[:i]` 每次都复制一个前缀列表，`O(n²)` 的内存拷贝；可以改成直接传 `tokens[i-K:i]`。

### 3.4 `paraphrase`：随机替换攻击

```python
def paraphrase(tokens: list[int], ratio: float = 0.3) -> list[int]:
    """Replace ratio of tokens at random with random tokens."""
    out = list(tokens)
    for i in range(len(out)):
        if random.random() < ratio:
            out[i] = random.randrange(VOCAB)
    return out
```

- 每个位置（包括前 4 个种子 token）独立地以 `ratio` 的概率被替换。
- 为什么 30% 的替换就让 z 从 25 掉到 4 左右？因为位置 i 的 green 判定依赖 **5 个 token**（自己 + 前 4 个上下文），只要其中任何一个被换掉，这个位置就退化为 0.5 的随机水平。保留率 `(1 − r)^(K+1)`：
  - r = 0.3：`0.7^5 = 0.168`，期望 z ≈ 4.25（实测 3.86，30 次重复均值 4.19）
  - r = 0.6：`0.4^5 ≈ 0.010`，期望 z ≈ 0.26（实测 0.32）
- ⚠️ 这不是真正的 paraphrase：真实改写保持语义、会重排句子；这里的替换是随机噪声，会破坏语义。讲义练习 2 要求"同义词替换"，代码并未实现。
- K 的取舍：K 越大，一处改动连带破坏的位置越多。K = 1 时 30% 替换后期望 z 仍有 12.4，K = 8 时只有 1.0（测验 Q11）。

### 3.5 `main`：实验编排

```python
    seed = [random.randrange(VOCAB) for _ in range(K)]

    watermarked = watermarked_sample(1000, seed)
    plain = unwatermarked_sample(1000, seed)
    ...
    fprs = [detect(unwatermarked_sample(1000, seed)) for _ in range(100)]
    fpr_above_4 = sum(1 for z in fprs if z >= 4) / len(fprs)
```

- 带水印与无水印文本共用同一个 4-token 前缀，方便对比。
- FPR 估计：100 段无水印文本中 z ≥ 4 的比例。`sum(1 for z in fprs if z >= 4)` 是"用生成器表达式计数"的常见写法。
- ⚠️ **样本量不足以支撑结论**：0/100 的 95% 置信上界约 3%（rule of three），而 TAKEAWAY 说"<1% FPR at z=4"。理论上 z ≥ 4 的单侧 FPR 只有 `3.17e-5`，需要依赖正态近似而非 100 次抽样来论证。
- ⚠️ 讲义练习 1 要求"95% 置信阈值下的 FPR"，代码只报告了 z ≥ 4。补上 z ≥ 1.645 的统计后，我们用 1000 次抽样测得 4.2%（理论 5%）。
- TAKEAWAY 末尾提到"watermark survives compression, metadata survives (as long as it is not stripped)"——这是对讲义 C2PA 部分的总结，代码本身没有演示 C2PA 或压缩。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 词表 = 整数 0..199，均匀分布 | 不依赖模型，几秒跑完 | 熵最大，水印最容易检出；真实 LLM 需按 logits 加 δ，低熵位置信号很弱 |
| `bias = 0.9` 直接选 green | 一行代码表达"有偏采样" | 与讲义"加 δ"不等价；生产用 logit 偏置以控制质量损失 |
| 奇偶划分 `(t + h) % 2` | 简单、恰好 γ = 0.5 | 只有 2 种分区，规律极易被反推；生产用带密钥的种子打乱词表 |
| 无密钥 SHA-256 | 可复现、无需配置 | 任何人可检测/擦除/伪造；生产用 HMAC + 服务端保管密钥 |
| `K = 4` 的哈希上下文 | 分区更"随机" | 改写时一处改动破坏 5 个位置；Kirchenbauer 主实验只用前 1 个 token |
| 随机替换代替改写 | 易实现、可控比例 | 不保义，和真实 paraphrase 不同 |
| 100 次抽样估 FPR | 运行快 | 统计上不足以支撑 <1%；应报告理论尾概率或大样本 |
| γ 硬编码在 `detect` | 简单 | 改 γ 时容易忘记同步 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值；在旧版本 Python 上也能写 `list[int]` |
| 类型注解 | `def green_set(prev_tokens: list[int]) -> set[int]:` | 标注参数和返回值类型，不影响运行，方便阅读与静态检查 |
| 模块级常量 | `VOCAB = 200`、`K = 4` | 全大写表示"约定不改"的配置 |
| 全局随机种子 | `random.seed(61)` | 放在模块顶层，import 时就生效；所有 `random.*` 调用共享这个全局状态 |
| 生成器表达式 + `join` | `",".join(str(t) for t in prev_tokens[-K:])` | 把整数列表拼成逗号分隔字符串 |
| 负索引切片 | `prev_tokens[-K:]` | 取最后 K 个元素；列表不足 K 个时返回整个列表 |
| `str.encode` / `hexdigest` | `hashlib.sha256(seed.encode()).hexdigest()` | 哈希函数只接受 bytes；`hexdigest()` 返回十六进制字符串 |
| `int(s, 16)` | `int(digest, 16)` | 按 16 进制解析字符串为整数；Python 整数任意精度 |
| 集合推导式 | `{t for t in range(VOCAB) if (t + h) % 2 == 0}` | 用花括号构造 set |
| 集合差 | `set(range(VOCAB)) - greens` | 得到 red 集合 |
| 条件表达式 | `list(greens) if use_green else list(...)` | 一行内的 if/else |
| 默认参数 | `bias: float = 0.9`、`ratio: float = 0.3` | 调用时可省略 |
| `random` 常用函数 | `random.random()`、`random.randrange(VOCAB)`、`random.choice(pool)` | [0,1) 浮点、[0,VOCAB) 整数、从序列中随机取一个 |
| 列表复制 | `out = list(tokens)` | 生成新列表，修改 `out` 不影响原列表 |
| 生成器计数 | `sum(1 for z in fprs if z >= 4)` | 统计满足条件的元素个数 |
| f-string 格式符 | `{detect(watermarked):.2f}`、`{fpr_above_4:.3f}` | 保留 2 / 3 位小数 |
| 字符串乘法 | `"=" * 70` | 打印分隔线 |
| 主入口 | `if __name__ == "__main__": main()` | 直接运行时执行，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3，耗时约 2 秒）：

```text
======================================================================
TOY TOKEN WATERMARK (Phase 18, Lesson 23)
======================================================================

watermarked z-score       : 25.30     ← 理论 0.8×√1000 = 25.30，几乎精确
unwatermarked z-score     : -1.64     ← H0 下 z ~ N(0,1)，-1.64 属正常波动
(z >= 4 is very strong evidence of watermark.)
after 30% paraphrase      : 3.86      ← 已低于 z = 4 阈值：这次改写版本逃过了检测
after 60% paraphrase      : 0.32      ← 与人写文本无法区分

FPR (z >= 4) over 100 human draws : 0.000   ← 0/100，只能说明 FPR 大概率 < 3%

======================================================================
TAKEAWAY: the text watermark is detectable at >=1000 tokens with
strong z-scores and <1% FPR at z=4. paraphrase of 30% weakens the
signal; 60% destroys it. ...
======================================================================
```

逐项解读：

- **25.30**：期望 green 数 900，`(900 − 500)/15.81 = 25.3`。注意这里恰好取到期望值附近；不同种子下会在 25 ± 1 左右波动（G 的标准差约 `√(1000×0.9×0.1) ≈ 9.5`，换算到 z 约 ±0.6）。
- **-1.64**：无水印文本的 z。我们另外跑了 1000 次：均值 −0.022、标准差 1.034，正好是标准正态；z ≥ 1.645 的比例 4.2%，最大值 3.54。
- **3.86 / 0.32**：与 `(1−r)^5` 推导的 4.25 / 0.26 吻合。30 次重复中，30% 改写后 z 在 2.15～5.95 之间，只有约 60% 仍 ≥ 4——TAKEAWAY 的"weakens"偏乐观，在本配置下 30% 改写已经让检测变成"抛硬币"。
- **长度的影响**（补充实验，各 50 次均值）：n = 25 → 3.87，50 → 5.65，100 → 7.78，200 → 11.42，与 `0.8√n` 一致。达到 z = 4 至少约 25 个 token——前提仍是"均匀分布 + 0.9 偏置"。
- **FPR 0.000**：结论方向正确（理论 3.17e-5），但证据来自正态近似，而不是这 100 次抽样。

---

## 7. 动手改一改

1. **（讲义练习 1）** 在 `main` 中加上 `z ≥ 1.645` 的 FPR，并把抽样次数改成 1000，验证它接近 5%；思考为什么生产阈值选 4 而不是 1.645。
2. **长度曲线**：对 n ∈ {25, 50, 100, 200, 500, 1000} 各生成 50 段带水印文本，打印 z 的均值和 z ≥ 4 的比例，验证 `z ≈ 0.8√n`。
3. **带密钥的分区**：按测验 Q9 把 `green_set` 改为 HMAC + 打乱词表 + 可调 γ，同步修改 `detect` 的 γ；验证错误密钥下 z ≈ 0。
4. **logit 偏置版本**：给每一步构造一个非均匀分布（例如 top-1 概率 q，其余均分），改成"green logits 加 δ 后按 softmax 采样"；比较 q = 0.5 / 0.9 / 0.99 时 1000 token 的 z（测验 Q10 的表格是理论值）。
5. **（讲义练习 2）** 实现"同义词替换"：先定义一个 token → 同义 token 集合的映射（例如把 200 个 token 分成 100 对"同义词"），只在同义对内替换 30%，与随机替换对比 z 的下降。
6. **K 的取舍**：把 `K` 改成 1、2、8，分别测量 30% 改写后的 z，并思考 K 小时攻击者能否通过统计 "上下文 → green 集合" 反推水印。

---

## 8. 常见坑

- **把"没检出"当成"是人写的"**：水印是模型特定的（讲义 Limitations："no SynthID signal is not proof of authenticity"）。
- **用小样本论证极小的 FPR**：0/100 只能说明 FPR < 约 3%。
- **改了 γ 忘了改检测公式**：`detect` 中 0.5 是硬编码的。
- **以为哈希够"随机"就安全**：本代码 SHA-256 的 256 比特只用了 1 比特；没有密钥时任何人都能复现分区。
- **用均匀分布的结果推断真实 LLM**：低熵 token 几乎不带水印，真实文本需要更长才能检出。
- **全局随机状态互相干扰**：`random.seed(61)` 是全局的；如果在 `green_set` 里也调用 `random.seed(h)`，会打乱采样序列。需要局部随机数时用 `random.Random(seed)`。
- **把随机替换等同于改写攻击**：真实攻击是保义的，往往更彻底（讲义引 arXiv:2508.20228）。
