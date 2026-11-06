# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 02 节 CLIP 与视觉语言对比 Pretraining ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需 NumPy / PyTorch / 网络

---

## 1. 这份代码在考察什么

这份代码不训练任何模型，而是在**手工构造的 embedding** 上把 CLIP / SigLIP 的几块核心数学跑一遍：

1. **相似度矩阵**：两侧向量先 L2 归一化，再两两点积、除以 temperature，得到 `S[i][j]`。
2. **对称 InfoNCE**：对 `S` 按行、按列各做一次交叉熵（log-sum-exp 保证数值稳定）。
3. **Sigmoid pairwise loss**：把每个 `(i, j)` 当作独立二分类，对角线为正例。
4. **Zero-shot 分类**：图像向量与各类"文本原型"比余弦，排序取 top-1。
5. **Prompt ensemble**：多个模板的 embedding 取平均。

四个 demo 分别对应讲义 The Concept 中的 InfoNCE、Temperature、Sigmoid、Zero-shot、Prompt templates 几个小节。

> 一句话：**用不到 200 行纯 Python 看清"对比学习的 loss 长什么样、tau 怎么影响它、zero-shot 为什么只是一个 argmax"**。同时要注意：讲义说这里"构建了训练步骤、可以看 loss 曲线"，但代码里没有任何参数更新——它只是在固定矩阵上**计算** loss。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `normalize` | 函数 | L2 归一化（零向量时除以 1 防止除零） | 单位长度 embedding |
| `cosine` | 函数 | 两个向量的点积（**假设已归一化**） | 余弦相似度 |
| `similarity_matrix` | 函数 | 归一化两侧 → `N × N` 点积 → 除以 `tau` | 相似度矩阵 `S` |
| `log_sum_exp` | 函数 | `m + log Σ exp(x − m)` | 数值稳定 softmax 分母 |
| `infonce_loss` | 函数 | 行交叉熵 + 列交叉熵，除以 `2N` | 对称 InfoNCE |
| `sigmoid` | 函数 | 分正负两支的稳定 sigmoid | 逻辑函数 |
| `sigmoid_loss` | 函数 | 每对 BCE，`bias` 可选，除以 `N²` | SigLIP loss（归一化与论文不同） |
| `zero_shot_classify` | 函数 | 对每类算余弦并降序排序 | Zero-shot 分类 |
| `make_fake_embedding` | 函数 | 按种子生成 64 维高斯向量 | 伪造 encoder 输出 |
| `demo_infonce` | 函数 | 4 对近似对齐的数据，比较 3 个 tau | Temperature 的作用 |
| `demo_shuffled` | 函数 | 6 对完全不相关 vs 完全对齐 | loss 能区分对齐与否 |
| `demo_zero_shot` | 函数 | "狗原型 + 30% 噪声"的图像做 4 类分类 | argmax 余弦 |
| `demo_prompt_ensemble` | 函数 | 3 个模板的伪 embedding 求平均 | Prompt ensemble |
| `main` | 函数 | 依次运行 4 个 demo 并打印要点 | — |

数据流：`make_fake_embedding`（伪 encoder 输出）→ `similarity_matrix`（归一化、点积、除 tau）→ `infonce_loss` / `sigmoid_loss`（打分）；或 → `zero_shot_classify`（排序取 top-1）。

---

## 3. 逐段精讲

### 3.1 归一化与"余弦"

```python
def normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
```

- `normalize` 把向量缩放到单位长度。`... or 1.0` 是一个小技巧：若范数为 0（`0.0` 在布尔上下文中为假），就用 1.0 代替，避免除零。
- ⚠️ `cosine` 的名字有误导性：它只是**点积**，只有在两个输入都已归一化时才等于余弦。所有调用处都先 `normalize` 了，所以结果正确；但如果你直接对原始向量调用 `cosine`，得到的不是余弦。
- 讲义："Both towers normalize their outputs to unit length. Similarity is `cos(f(x), g(y)) = f(x)^T g(y)`"——归一化之后余弦和点积就是同一回事，这也是真实 CLIP 实现里只写一个矩阵乘法的原因。

### 3.2 相似度矩阵

```python
def similarity_matrix(images, texts, tau):
    I = [normalize(v) for v in images]
    T = [normalize(v) for v in texts]
    N = len(I)
    S = [[0.0] * N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            S[i][j] = cosine(I[i], T[j]) / tau
    return S
```

- 输出 `S` 是 `N × N` 的嵌套列表：第 i 行是第 i 张图对所有 caption 的打分，对角线是正例。
- 双重循环等价于 NumPy 的 `I @ T.T / tau`，复杂度 `O(N² · D)`。
- `[[0.0] * N for _ in range(N)]` 用推导式创建**互不共享**的行；若写成 `[[0.0] * N] * N`，N 行会是同一个列表对象，改一行等于改全部。
- 这里 tau 是固定参数。真实 CLIP 中它是可学习的，并在 log 空间参数化（讲义 Key Terms："CLIP parametrizes `log(1/tau)`"）。

### 3.3 log-sum-exp 与对称 InfoNCE

```python
def log_sum_exp(row):
    m = max(row)
    return m + math.log(sum(math.exp(x - m) for x in row))


def infonce_loss(S):
    N = len(S)
    loss_i2t = 0.0
    for i in range(N):
        loss_i2t += -S[i][i] + log_sum_exp(S[i])
    loss_t2i = 0.0
    for j in range(N):
        col = [S[i][j] for i in range(N)]
        loss_t2i += -S[j][j] + log_sum_exp(col)
    return (loss_i2t + loss_t2i) / (2 * N)
```

- 单行交叉熵：`-log softmax(row)[i] = -row[i] + log Σ_j exp(row[j])`。先减最大值 `m` 再 `exp`，避免 tau = 0.07 时 `exp(14.3)` 这类大数溢出（tau 更小时会更严重）。
- **行**（i2t）：图 i 在所有 caption 中找自己的；**列**（t2i）：caption j 在所有图中找自己的。`col = [S[i][j] for i in range(N)]` 手工取出第 j 列。
- 除以 `2N`：先对 N 行求平均、N 列求平均，再把两个方向平均。与讲义 `(loss_i2t + loss_t2i) / 2` 一致。
- 健全性检查：若 `S` 所有元素相等，每行损失都是 `ln N`。实测 6×6 全零矩阵输出 1.7918 = ln 6。

### 3.4 稳定的 sigmoid 与 SigLIP 风格损失

```python
def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def sigmoid_loss(S, bias=0.0):
    N = len(S)
    total = 0.0
    count = 0
    for i in range(N):
        for j in range(N):
            logit = S[i][j] + bias
            y = 1.0 if i == j else 0.0
            p = sigmoid(logit)
            eps = 1e-9
            term = y * math.log(p + eps) + (1 - y) * math.log(1 - p + eps)
            total += -term
            count += 1
    return total / count
```

- `sigmoid` 分两支：x ≥ 0 时用 `exp(-x)`，x < 0 时用 `exp(x)`，两种写法数学等价，但保证 `exp` 的参数永远 ≤ 0，不会溢出。
- 每个 pair 是一个二元交叉熵：对角线 `y = 1`，其余 `y = 0`。
- ⚠️ **归一化系数与讲义不一致**：`count` 在双重循环中累加到 N²，因此返回 `Σ / N²`；讲义和 SigLIP 论文都是 `Σ / N`。代码值 = 讲义值 / N（DEMO 1 中 N = 4，tau = 0.07 时 0.9268 vs 3.7071，已实际计算）。常数因子不改变优化方向，但改变 loss 的量级，对照论文数字时要注意。
- ⚠️ `bias` 默认 0。SigLIP 论文用 `b = -10` 初始化，因为每行只有 1 个正例、N−1 个负例。bias = 0 会导致一个反直觉现象：tau 越小 SigLIP loss 越**大**（见第 6 节）。
- ⚠️ `math.log(p + eps)` 是一种"够用"的写法：当 logit 极大或极小时，单项损失会被截断在约 `-log(1e-9) ≈ 20.7`。更好的写法是 `log σ(x) = -softplus(-x)`，NumPy 里可以用 `np.logaddexp(0, -x)`。
- 讲义的 SigLIP 写法是 `S[i,j]/tau + b`，论文写法是 `t · cos + b`（`t = exp(t')`），两者只是参数化不同。

### 3.5 Zero-shot 分类

```python
def zero_shot_classify(image, class_texts):
    img = normalize(image)
    scores = []
    for name, vec in class_texts.items():
        scores.append((name, cosine(img, normalize(vec))))
    scores.sort(key=lambda p: p[1], reverse=True)
    return scores
```

- 输入：一个图像向量、一个"类名 → 文本向量"的字典。输出：按余弦降序排列的 `(类名, 分数)` 列表，`[0]` 就是 top-1。
- 这就是讲义的 "Argmax cosine similarity = predicted class"。注意这里**没有 tau**：tau 只影响 softmax 的尖锐程度，不影响 argmax 的结果。若要输出"概率"，需要乘 logit scale 后再 softmax。
- 真实场景中，`class_texts` 的向量来自文本 encoder 对 `a photo of a {class}` 的编码；这里用随机向量代替。

### 3.6 伪 embedding 与 DEMO 1（tau 的影响）

```python
def make_fake_embedding(seed, dim=64):
    rng = random.Random(seed)
    return [rng.gauss(0, 1) for _ in range(dim)]

def demo_infonce():
    images = [make_fake_embedding(i) for i in range(4)]
    texts = [[x + 0.05 * make_fake_embedding(i + 100)[k] for k, x in enumerate(v)]
             for i, v in enumerate(images)]
    for tau in (0.07, 0.1, 1.0):
        S = similarity_matrix(images, texts, tau=tau)
        ...
```

- `random.Random(seed)` 创建**独立的**随机数生成器，同一种子永远得到同一向量，不影响全局 `random` 状态，可复现。
- 文本 = 图像 + 5% 的另一个随机向量，所以对角线余弦约 0.999；不同 i 的向量相互独立，非对角线余弦接近 0（64 维独立高斯向量的余弦标准差约 `1/√64 = 0.125`）。
- ⚠️ 写法上有浪费：`make_fake_embedding(i + 100)[k]` 在内层推导式中对每个 k 都重新生成一次 64 维向量，共生成 64 次再取第 k 个。结果正确，但应当提到循环外先生成一次。`demo_zero_shot` 中 `make_fake_embedding(999)[i]` 也是同样的写法。
- 讲义说 image 特征是 "hash-based"、text 是 "char features"，实际代码两侧都是种子高斯向量，没有任何文本特征化。

### 3.7 DEMO 2：对齐与不对齐

```python
    images = [make_fake_embedding(i) for i in range(6)]
    texts = [make_fake_embedding(i + 500) for i in range(6)]
    ...
    aligned_txt = [[x + 0.02 for x in v] for v in aligned_imgs]
```

- misaligned：图和文是完全独立的随机向量，相当于"encoder 什么都没学到但 tau 已经很小"。
- aligned：文本 = 图像每一维加常数 0.02（一个整体平移，而不是噪声），余弦几乎为 1。
- 结论：两种损失都能区分"对齐"与"不对齐"，这是梯度信号存在的前提。

### 3.8 DEMO 3、DEMO 4：zero-shot 与 prompt ensemble

```python
    query_image = [c + 0.3 * make_fake_embedding(999)[i]
                   for i, c in enumerate(classes["dog"])]
```

- 查询图 = 狗的原型 + 30% 噪声。两个独立高斯向量近似正交，所以余弦约 `1 / √(1 + 0.3²) ≈ 0.958`，实测 0.9574。

```python
    for t in templates:
        prompt = t.format(**{"class": class_name})
        seed = sum(ord(c) for c in prompt)
        emb = make_fake_embedding(seed)
```

- `t.format(**{"class": class_name})`：因为 `class` 是 Python 关键字，不能写 `t.format(class=...)`，所以用字典解包传参。
- ⚠️ 用字符码之和作种子：与字符顺序无关，**字母重排必然碰撞**（实测 `"a photo of a cat"` 与 `"a photo of a act"` 都是 1401）。而且生成的向量与类名语义毫无关系。
- ⚠️ 平均前没有对每个模板 embedding 归一化；真实做法是"归一化 → 平均 → 再归一化"（测验 Q10）。
- ⚠️ 最后打印的 "+1-3 points on real benchmarks" 是写死的字符串，不是本代码测出来的；讲义正文的数字是"80 个模板 +3 点"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python、不用 NumPy | 每一步求和都写出来，零依赖 | `O(N²·D)` 的 Python 循环极慢；生产用 `I @ T.T` 的矩阵乘法，在 GPU 上算 |
| 随机高斯向量代替 encoder | 能精确控制"对齐程度" | 看不到真实 encoder 的行为；真实 CLIP 用 ViT + Transformer |
| 固定 tau、无训练循环 | 只关注 loss 的形状 | 讲义说能"看 loss 曲线"，实际没有；真实 CLIP 学习 `log(1/tau)` 并设上限 |
| `sigmoid_loss` 除以 N² | 写成"所有 pair 的平均"最直观 | 与讲义、论文的 `1/N` 不一致，数值小 N 倍 |
| bias 默认 0 | 简单 | 小 tau 时负例损失主导，出现"tau 越小 SigLIP 越大"；论文初始化 `b = -10` |
| `log(p + 1e-9)` | 防止 `log(0)` | 单项损失被截断在约 20.7；生产用 log-sigmoid / softplus |
| 种子 = 字符码之和 | 让同一 prompt 得到同一向量 | 字母重排碰撞；与语义无关 |
| zero-shot 不用 tau | argmax 不受正数缩放影响 | 若要输出概率需乘 logit scale 再 softmax |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值；在旧版 Python 上也能写 `list[float]` 这种注解 |
| 类型注解 | `def normalize(v: list[float]) -> list[float]:`、`dict[str, list[float]]`、`list[tuple[str, float]]` | 标注参数和返回值的类型，只用于阅读和静态检查，运行时不强制 |
| 生成器表达式 | `sum(x * x for x in v)` | 不建列表，边生成边求和，省内存 |
| `or` 提供默认值 | `math.sqrt(...) or 1.0` | 左边为假（0.0）时取右边 |
| `zip` | `zip(a, b)` | 按位置配对两个序列 |
| 列表推导式 | `[x / n for x in v]`、`[[0.0] * N for _ in range(N)]` | 简洁地构造列表；嵌套列表必须用推导式避免行共享 |
| `enumerate` | `for k, x in enumerate(v)` | 同时得到下标和元素 |
| 条件表达式 | `y = 1.0 if i == j else 0.0` | 一行内的 if-else |
| `lambda` + `sort(key=...)` | `scores.sort(key=lambda p: p[1], reverse=True)` | 按元组第二个元素降序原地排序 |
| `dict.items()` | `for name, vec in class_texts.items()` | 同时遍历键和值 |
| 独立随机数生成器 | `rng = random.Random(seed)`、`rng.gauss(0, 1)` | 每个种子一个生成器，结果可复现、互不干扰 |
| `str.format` + 字典解包 | `t.format(**{"class": class_name})` | `**` 把字典展开成关键字参数；绕开 `class` 是关键字的问题 |
| `ord` | `sum(ord(c) for c in prompt)` | 字符 → Unicode 码点整数 |
| `round` | `[round(x, 3) for x in ensemble_vec[:6]]` | 保留 3 位小数；`[:6]` 是切片 |
| f-string 格式符 | `{tau:4.2f}`、`{loss:.4f}`、`{name:6s}`、`{score:+.4f}` | 宽度与小数位；`s` 字符串左对齐；`+` 总是显示正负号 |
| 字符串乘法 | `"=" * 60`、`"-" * 60` | 重复字符串画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 `import` 时不执行（便于在别处复用 `infonce_loss` 等函数） |

---

## 6. 运行结果解读

实际运行（Python 3，耗时约 0.03 秒）：

```text
DEMO 1: InfoNCE on 4 aligned pairs
  tau=0.07  InfoNCE=0.0000  SigLIP=0.9268
  tau=0.10  InfoNCE=0.0003  SigLIP=0.7854
  tau=1.00  InfoNCE=0.7748  SigLIP=0.6197

DEMO 2: what happens with misaligned pairs
  misaligned: InfoNCE=2.9754  SigLIP=1.0846
  aligned   : InfoNCE=0.0000  SigLIP=0.8152
  aligned loss < misaligned loss confirms the gradient signal.

DEMO 3: zero-shot classification
  query image (close to 'dog' prototype):
    dog   : +0.9574
    cat   : +0.0824
    bird  : +0.0424
    car   : +0.0042
  top-1: dog

DEMO 4: prompt template ensemble
  ensembled 3 prompts for 'golden retriever'
  first 6 dims: [-0.215, 0.64, -0.205, 0.072, -0.665, -0.345]
  single-template: noisier; ensemble: +1-3 points on real benchmarks.
```

逐项解读：

- **DEMO 1 的 InfoNCE**：tau = 1 时 0.7748。原因是余弦被限制在 `[-1, 1]`：对角线 ≈ 0.999、非对角线 ≈ 0 ～ 0.17，行损失约 `ln(1 + 3·e^-1) ≈ 0.74`，无论 embedding 多好都降不下去。tau = 0.07 时 logit 差被放大 14 倍，loss 降到 6.2e-6（打印成 0.0000）。这就是讲义 "Low tau → sharp distribution" 的数值体现。
- **DEMO 1 的 SigLIP 反向变化**：tau 越小 SigLIP 越大（0.6197 → 0.9268）。打印 tau = 1 的矩阵可以看到非对角线余弦有 0.156、0.165 这样的值；除以 0.07 后负例 logit 达到约 +2.4，`softplus(2.4) ≈ 2.5`，远超 ln 2。bias = 0 时负例从 p = 0.5 起步，负例数量又是正例的 3 倍，于是负例损失主导。同一数据上把 bias 设为 −2 / −5 / −10，tau = 0.07 的 loss 依次为 0.2471 / 0.0162 / 0.0036（已实际运行）。这正是 SigLIP 需要 bias 的原因（讲义练习 2）。
- **DEMO 2 的 misaligned InfoNCE = 2.9754 > ln 6 = 1.792**：随机向量的余弦在 ±0.2 左右，除以 0.07 后变成 ±3，模型对错误答案"很自信"，比"完全不知道"（ln N）更差。tau 取 0.5 / 1 / 10 时同一数据的 loss 依次为 1.858 / 1.820 / 1.794，逐渐逼近 ln 6。
- **DEMO 2 的 aligned SigLIP = 0.8152**：同样是 bias = 0 导致的负例主导；N = 6 时负例占 30/36。
- **DEMO 3**：0.9574 与理论值 `1/√1.09 ≈ 0.958` 吻合；其它三类余弦接近 0，因为独立随机向量近似正交。
- **DEMO 4**：前 6 维只是三个随机向量的平均值，没有可解释的含义。

---

## 7. 动手改一改

1. **（讲义练习 1）**手工构造一个 4×4 相似度矩阵，按"softmax → 取对角线 → 交叉熵"手算，然后调用 `infonce_loss` 对拍；再把某个非对角线元素调大，观察对应行和列的损失变化。
2. 修正 `sigmoid_loss` 的归一化：把 `return total / count` 改为 `return total / N`，并给 `similarity_matrix` 增加 `bias` 参数，用 `tau = 0.1, bias = -10`（论文的初始化）重跑 DEMO 1。
3. 修正 `demo_prompt_ensemble`：种子改用 `hash` 以外的稳定方法（如 `zlib.crc32(prompt.encode())`），并改为"归一化 → 平均 → 再归一化"。再构造一个"类语义向量 + 模板噪声"的生成方式，量化 ensemble 是否让类原型更接近真实语义向量。
4. **加入真正的训练循环**：把图像和文本 embedding 各自当作可学习参数（或一个线性投影），手写 InfoNCE 对 `S` 的梯度（`softmax(S) − I`，行列各一份），用 SGD 更新 200 步并打印 loss 曲线——补齐讲义所说的"watch the loss curve"。
5. **（讲义练习 3 的玩具版）**构造 100 个"猫"和 100 个"狗"的图像向量（类原型 + 噪声），比较单模板与三模板 ensemble 的 zero-shot 准确率。
6. 用 NumPy 写出向量化版本（参考测验 Q11），在 N = 1024、D = 512 时对比纯 Python 版本的耗时。

---

## 8. 常见坑

- **忘记归一化**：没有 L2 归一化时点积会被向量长度主导，tau 的含义也会变。本节的 `cosine` 正是依赖调用方先归一化。
- **只做单向 InfoNCE**：只算 i2t 会让文本侧缺少约束；CLIP 用的是对称版本。
- **tau 设成 1**：logit 范围只有 `[-1, 1]`，loss 降不下去（N = 32768 时下界约 8.4）。
- **SigLIP 不加 bias**：负例数量远多于正例，bias = 0 时训练初期会被负例梯度淹没。
- **把 loss 数值和论文直接比较**：先确认归一化口径（本节代码除以 N²，论文除以 N）。
- **嵌套列表用 `[[0.0] * N] * N`**：所有行指向同一列表，修改一处全部改变。
- **prompt ensemble 平均前不归一化**：范数大的模板主导结果。
- **把"zero-shot 分数"当概率**：余弦值不是概率；不同 checkpoint 的分数尺度也不同（技能文件："SigLIP and CLIP score on different scales"）。
