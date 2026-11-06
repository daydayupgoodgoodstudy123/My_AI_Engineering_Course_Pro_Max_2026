# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 13 节 Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

Transfusion 的三个关键工程部件是：**混合注意力 mask**、**两损失训练步**、**文本自回归 + 图像去噪的推理循环**。代码的 docstring 自己说："The transformer is a shared linear map; the point is the two-loss plumbing and the block-triangular attention mask."

实际上这份 160 行的脚本只真正实现了其中一项：

1. `build_mask`：按"文本因果、图内双向、图看前文、后文看图"构造 0/1 mask——**这是本文件最有价值的部分，但它有两个 bug**（标签行、多图）。
2. `two_loss_step`：演示 flow matching 的加噪公式 `x_t = (1 − t)x0 + tε` 和速度目标 `ε − x0`、文本交叉熵、加权求和——但**没有模型、没有梯度**，loss 的下降是硬编码出来的。
3. 讲义"Use It"里说的"shared-weight linear projections""alternates the two losses""Generation produces a text caption and a 4x4 image"在代码中**都不存在**。

> 一句话：**把这份代码当成"mask 构造 + 损失公式"的示意图来读，而不是一个训练器**；读懂它错在哪里，比读懂它做了什么更能帮你理解 Transfusion。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 常量 `VOCAB / IMG_PATCH_DIM / HIDDEN / SEP_OPEN / SEP_CLOSE` | 模块级常量 | 词表 8、图像 4×4、隐藏维 8、`<image>` 用 −1、`</image>` 用 −2 | 序列格式 |
| `Pair` | `@dataclass` | 一条样本：caption（4 个整数）+ 4×4 图像 | 图文对 |
| `make_dataset` | 函数 | 生成 24 条按类别着色的玩具图文对 | 数据 |
| `patch_to_vec` | 函数 | 把 patch 补零到 `HIDDEN` 维（**未被调用**） | patch 线性嵌入的占位 |
| `build_mask` | 函数 | 构造混合注意力 mask | block-triangular mask |
| `mse` / `cross_entropy_toy` | 函数 | 均方误差 / `−log p` | 两种损失 |
| `two_loss_step` | 函数 | 计算"文本 loss + 图像 flow loss"并加权 | 两损失训练 |
| `train` | 函数 | 10 步循环，每步把两个 scale 加 1 | "训练"循环 |
| `demo_mask` | 函数 | 打印 10 个位置的 mask | mask 可视化 |
| `main` | 函数 | 打印 mask、训练日志和四种架构对比 | — |

数据流：`random.seed(1)` → `demo_mask()`（`build_mask` → 打印）→ `make_dataset(24)` → `train()`（循环调用 `two_loss_step`，打印偶数步的 loss）→ 打印 Chameleon / Transfusion / MMDiT / Show-o 对比。

---

## 3. 逐段精讲

### 3.1 常量与数据：`Pair`、`make_dataset`

```python
VOCAB = 8
IMG_PATCH_DIM = 4
HIDDEN = 8
SEP_OPEN = -1
SEP_CLOSE = -2

def make_dataset(n: int = 24) -> list[Pair]:
    pairs = []
    for _ in range(n):
        cls = random.randint(0, VOCAB - 2)
        cap = [1, 2, cls, 3]
        shade = (cls + 1) / VOCAB
        img = [[shade * ((r * 4 + c) % 3 + 1) for c in range(IMG_PATCH_DIM)]
               for r in range(IMG_PATCH_DIM)]
        pairs.append(Pair(caption=cap, image=img))
    return pairs
```

- 每条 caption 是 `[1, 2, cls, 3]`，中间的 `cls ∈ [0, 6]` 是"类别词"，前后是固定模板 token。
- 图像是 4×4 的浮点网格：亮度 `shade = (cls + 1) / 8` 乘以一个 `(r*4 + c) % 3 + 1 ∈ {1, 2, 3}` 的条纹图案。所以**类别决定亮度**，"文生图"在概念上就是"读出 cls，画出对应亮度的条纹"。实际运行时第一条样本为 `caption=[1, 2, 1, 3]`、首行 `[0.25, 0.5, 0.75, 0.25]`。
- 用 −1、−2 表示标签是为了和非负的文本 id 区分，但这只在玩具里成立；真实词表中 `<image>`、`</image>` 是普通的特殊 token id。
- ⚠️ 讲义说"Images are 4x4 grids of bytes"，代码里是 0.125–2.625 之间的浮点数，不是字节。
- ⚠️ caption 在训练中**只用到了长度**（`for _ in pair.caption`），内容从未参与计算——没有真正的"条件"。

### 3.2 `patch_to_vec`：没被用上的"线性嵌入"

```python
def patch_to_vec(patch: list[float]) -> list[float]:
    return patch[:HIDDEN] + [0.0] * max(0, HIDDEN - len(patch))
```

- 意图是模拟讲义"16x16 pixel blocks projected into hidden dim via linear embedding"：把一个 patch 映射到隐藏维。这里只是截断/补零，不是线性投影。
- 全文件没有任何地方调用它，`HIDDEN` 也因此是死常量。

### 3.3 `build_mask`：本文件的核心

```python
    img_ranges = []
    i = 0
    while i < n:
        if tokens[i] == SEP_OPEN:
            start = i + 1
            while i < n and tokens[i] != SEP_CLOSE:
                i += 1
            img_ranges.append((start, i))
        i += 1
```

- 第一步扫描序列，找到每对 `<image> ... </image>` 之间的**半开区间** `[start, end)`。对 demo 序列 `[10, 11, -1, p0, p1, p2, p3, -2, 12, 13]`，得到 `[(3, 7)]`：位置 3–6 是 patch。
- 若缺少 `</image>`，内层 `while` 会走到 `n`，区间延伸到序列末尾——不会崩溃。

```python
    def same_img(a, b):  ...   # a、b 是否落在同一个图像区间
    def in_text(idx):
        return not any(s <= idx < e for s, e in img_ranges) and tokens[idx] not in (SEP_OPEN, SEP_CLOSE)

    for i in range(n):
        for j in range(n):
            if in_text(i) and in_text(j) and j <= i:          # 文本→文本：因果
                mask[i][j] = 1
            elif not in_text(i) and not in_text(j) and same_img(i, j):   # 同图双向
                mask[i][j] = 1
            elif in_text(i) and not in_text(j) and j <= i:    # 文本→前面的图像
                mask[i][j] = 1
            elif not in_text(i) and in_text(j) and j <= i:    # 图像→前面的文本
                mask[i][j] = 1
```

- 四个分支一一对应讲义给出的 mask 定义；`same_img`、`in_text` 是**闭包**，直接读取外层的 `img_ranges` 和 `tokens`。
- 双重循环是 O(n²)，对玩具足够；真实实现用张量运算或 FlexAttention 的 block mask。
- ⚠️ **Bug 1：标签行**。`in_text` 把标签排除在文本外，而图像区间又从 `<image>` 的**下一个**位置开始，于是标签"既不是文本也不是图像"：
  - 标签只能命中第 4 个分支（看前面的文本），看不到自己（对角线为 0），`</image>` 也看不到刚结束的图像；
  - 序列以 `<image>` 开头时（实测 `[<image>, P, P, </image>, T]`），第 0 行和第 3 行**全为 0**。真实注意力中整行 −∞ 经 softmax 变成 NaN。
- ⚠️ **Bug 2：多图**。第 2 个分支只允许同一张图内互看，第 4 个分支只放行文本，所以第二张图的 patch 看不到第一张图（实测 `[T, <image>, P, P, </image>, <image>, Q, Q, </image>, T]` 中 `Q` 行只有 `T`、`Q`、`Q` 为 1）。讲义的 mask 定义同样漏了这一项。
- **正确且更简单的写法**：Transfusion 的定义是"整条序列因果，再在每张图内部打开双向"：

  ```python
  mask[i][j] = 1 if (j <= i or same_img(i, j)) else 0
  ```

  标签作为普通 token 参与因果注意力即可，不会出现全 0 行。

### 3.4 两个损失函数

```python
def mse(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / max(1, len(a))

def cross_entropy_toy(prob):
    prob = max(prob, 1e-6)
    return -math.log(prob)
```

- `mse` 用生成器表达式求和，`max(1, len(a))` 防止空列表除零。
- `cross_entropy_toy` 接收的是"正确 token 的概率"而不是 logits；`max(prob, 1e-6)` 防止 `log(0)`。
- ⚠️ 只有下界保护，没有上界：概率 > 1 时会返回负数（见 3.6）。

### 3.5 `two_loss_step`：公式是对的，模型是假的

```python
    text_probs = [0.3 + 0.05 * weights["text_scale"] for _ in pair.caption]
    text_loss = sum(cross_entropy_toy(p) for p in text_probs) / len(text_probs)

    noise = [[random.gauss(0, 1) for _ in range(IMG_PATCH_DIM)] for _ in range(IMG_PATCH_DIM)]
    t = random.random()
    xt = [[(1 - t) * x + t * n for x, n in zip(row_x, row_n)]
          for row_x, row_n in zip(pair.image, noise)]
    predicted_vel = [[(n - x) * (0.8 + 0.02 * weights["img_scale"]) ...]]
    target_vel = [[n - x for x, n in zip(row_x, row_n)] ...]
    pred_flat = sum(predicted_vel, [])
    tgt_flat = sum(target_vel, [])
    img_loss = mse(pred_flat, tgt_flat)

    total = weights["text_w"] * text_loss + weights["img_w"] * img_loss
```

值得学的部分：

- **flow matching 的三行公式**：`t ~ U(0,1)`、`ε ~ N(0,1)`，`x_t = (1 − t)·x0 + t·ε`，目标速度 `ε − x0`（即 `dx_t/dt`），与讲义第 2–3 步完全一致。
- **加权求和**：`total = text_w · L_text + img_w · L_img`，默认 `text_w = 1.0`、`img_w = 0.1`，对应讲义练习 1 的"图像损失量级约为文本 10 倍"。
- `sum(predicted_vel, [])`：用 `sum` 把二维列表拼成一维（起始值为空列表），这是展平的小技巧，但时间复杂度是 O(n²)，大数据请用 `itertools.chain`。

问题部分：

- ⚠️ `text_probs` 是 `0.3 + 0.05·text_scale` 的常数，与 caption 内容无关——没有模型。
- ⚠️ `xt` 和 `t` **算了但从未使用**，"模型"不看带噪输入。
- ⚠️ `predicted_vel` 直接用真噪声 `n` 与干净图 `x` 计算，等于把答案交给模型，只乘了一个缩放系数；于是 `img_loss = (0.2 − 0.02·s)² · mean((ε − x0)²)`。

### 3.6 `train`：loss 的下降是写死的

```python
    weights = {"text_scale": 0, "img_scale": 0, "text_w": 1.0, "img_w": 0.1}
    for step in range(steps):
        pair = random.choice(pairs)
        losses = two_loss_step(pair, weights)
        weights["text_scale"] += 1
        weights["img_scale"] += 1
```

- 每步把两个 scale 无条件 +1，跟 loss 无关——没有梯度、没有优化器。
- 默认 10 步时恰好落在"看起来在收敛"的区间。实测把 `steps` 改成 22：
  - step 14：`text_prob = 1.0`，`text_loss = 0`；
  - step 16 起 `text_loss` 为负（−0.095、−0.182、−0.262），总 loss 也变负；
  - `img_loss` 在 step 10 降到 0 后反弹到 0.161。
- ⚠️ 讲义说"Training loop alternates the two losses"，实际是每步同时算两个损失并加权（这才是 Transfusion 的做法，讲义描述反而不准）。

### 3.7 `demo_mask` 与 `main`

```python
    tokens = [10, 11, SEP_OPEN, "p0", "p1", "p2", "p3", SEP_CLOSE, 12, 13]
    ...
        print(f"    {i:>2} | " + " ".join("1" if v else "." for v in row))
```

- 序列里混合了整数和字符串（`"p0"`…），因为 `build_mask` 只关心是否等于 `SEP_OPEN/SEP_CLOSE`，元素类型无所谓——这是 Python 动态类型的便利，也是类型注解 `tokens: list` 写得很宽的原因。
- `" ".join(生成器)` 把一行 0/1 转成 `1`/`.` 字符串。
- `main` 最后的四行对比表是本节最好的速记：Chameleon（离散 + NTP）、Transfusion（连续 + NTP + flow）、MMDiT（Transfusion 的兄弟，模态专属权重）、Show-o（NTP + 离散掩码扩散）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 0/1 二维列表表示 mask | 可直接打印、肉眼检查 | 生产中用布尔张量或 `−inf` 加性 mask，配合 FlexAttention/块稀疏 kernel |
| 四个分支逐条翻译讲义定义 | 与讲义一一对应 | 漏掉标签与多图情况；`j <= i or same_img(i, j)` 更简单且正确 |
| 用 −1/−2 表示标签 | 与非负文本 id 天然区分 | 真实词表中标签是普通特殊 token |
| "模型"用硬编码的 scale | 不写模型也能展示损失公式 | loss 下降毫无意义，步数一多就出现负 loss；真实实现需 Transformer + autograd |
| flow matching 而非 DDPM | 公式简单（线性插值、速度目标） | 讲义与技能文件都推荐；生产中还要时间步 embedding、t 的采样分布（如 logit-normal）等细节 |
| `img_w = 0.1` 固定权重 | 对应"图像损失约 10 倍"的练习 | 技能文件要求按梯度范数比校准，不能只用固定权重 |
| 没有推理循环 | 篇幅所限 | 真实推理：文本 NTP → `<image>` → 对全部 patch 做 10–30 步去噪 → `</image>` → 继续文本 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可写 `list[int]` 等新式类型 |
| `@dataclass` | `class Pair: caption: list[int]; image: list[list[float]]` | 自动生成构造函数与 `__repr__`（打印 `Pair(caption=..., image=...)`） |
| 关键字参数构造 | `Pair(caption=cap, image=img)` | 比位置参数更清晰 |
| 模块级常量（全大写） | `VOCAB = 8`、`SEP_OPEN = -1` | Python 没有真正的常量，全大写是约定 |
| 嵌套列表推导式 | `[[shade * ((r*4 + c) % 3 + 1) for c in range(4)] for r in range(4)]` | 外层是行、内层是列 |
| 列表拼接与乘法 | `patch[:HIDDEN] + [0.0] * max(0, HIDDEN - len(patch))` | 切片 + 重复列表实现补零 |
| `while` 循环与手动下标 | `while i < n: ... i += 1` | 需要"跳过一段"时比 `for` 更灵活 |
| 闭包（嵌套函数） | `def same_img(a, b):` 读取外层 `img_ranges` | 内部函数可以读取外层函数的局部变量 |
| 链式比较 | `s <= a < e` | 等价于 `s <= a and a < e` |
| `any` + 生成器 | `any(s <= idx < e for s, e in img_ranges)` | 只要有一个为真就返回 True，且会短路 |
| `in` 判断元组成员 | `tokens[idx] not in (SEP_OPEN, SEP_CLOSE)` | 成员测试 |
| `if / elif` 链 | `build_mask` 的四个分支 | 命中第一个为真的分支后不再判断后面的 |
| `sum` 展平列表 | `sum(predicted_vel, [])` | 以 `[]` 为初值把子列表依次相加 |
| 生成器表达式求和 | `sum((x - y) ** 2 for x, y in zip(a, b))` | 不建中间列表 |
| `dict` 作为可变状态 | `weights["text_scale"] += 1` | 函数间共享并原地修改同一个字典 |
| `random.choice` / `random.randint` | `random.choice(pairs)`、`random.randint(0, VOCAB - 2)` | 随机取元素 / 闭区间随机整数 |
| 条件表达式 | `"1" if v else "."` | 三元运算 |
| f-string 跨行拼接 | `f"  step {step:>2}  text_loss={...:.3f}" f"  img_loss=..."` | 相邻字符串字面量自动拼接 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，瞬间完成）：

```text
BLOCK-TRIANGULAR MASK for sequence:
  tokens: [10, 11, -1, 'p0', 'p1', 'p2', 'p3', -2, 12, 13]

  attention (1=attend, .=mask):
     0 | 1 . . . . . . . . .      ← 文本因果
     1 | 1 1 . . . . . . . .
     2 | 1 1 . . . . . . . .      ← <image>：看不到自己（bug）
     3 | 1 1 . 1 1 1 1 . . .      ← patch：看前文 + 整张图双向，但看不到 <image>
     4 | 1 1 . 1 1 1 1 . . .
     5 | 1 1 . 1 1 1 1 . . .
     6 | 1 1 . 1 1 1 1 . . .
     7 | 1 1 . . . . . . . .      ← </image>：看不到图像，也看不到自己（bug）
     8 | 1 1 1 1 1 1 1 1 1 .      ← 后文看到全部前文和整张图
     9 | 1 1 1 1 1 1 1 1 1 1

TWO-LOSS TRAINING (NTP on text + flow-matching on images)
  step  0  text_loss=1.204  img_loss=0.075  total=1.212   ← −ln(0.3)
  step  2  text_loss=0.916  img_loss=0.046  total=0.921   ← −ln(0.4)
  step  4  text_loss=0.693  img_loss=0.025  total=0.696   ← −ln(0.5)
  step  6  text_loss=0.511  img_loss=0.011  total=0.512
  step  8  text_loss=0.357  img_loss=0.005  total=0.357   ← −ln(0.7)

TRANSFUSION vs MMDiT vs CHAMELEON
  Chameleon  : discrete image tokens + NTP only
  Transfusion: continuous image patches + NTP (text) + flow (image)
  MMDiT (SD3): Transfusion siblings, modality-specific block weights
  Show-o     : NTP (text) + masked discrete diffusion (image)
```

逐项解读：

- **mask 的正确部分**：patch 区块（第 3–6 行 × 第 3–6 列）是全 1 的方块——图内双向；第 8、9 行看到整张图——后文以图为条件；左上角是因果三角——文本自回归。
- **mask 的错误部分**：第 2、7 行（标签）与第 2 列（patch 看不到 `<image>`）。这在 demo 里不致命，但换成以图开头的序列就会出现全 0 行。
- **文本 loss** 每步精确等于 `−ln(0.3 + 0.05·step)`，与数据无关；**图像 loss** 等于 `(0.2 − 0.02·step)² × mean((ε − x0)²)`，随机部分只来自每步新采的噪声。这组数字只证明公式能跑通，不能说明任何"训练效果"。
- **total ≈ text_loss**：因为 `img_w = 0.1` 且 img_loss 本身很小，总损失几乎全由文本决定——这也恰好说明为什么要按梯度范数而不是拍一个固定权重。

---

## 7. 动手改一改

1. **修 mask（练习 2）**：把四个分支替换成 `j <= i or same_img(i, j)`，在练习 2 的序列、以 `<image>` 开头的序列和两张图的序列上打印对比，确认不再有全 0 行。
2. **加一个断言**：在 `build_mask` 末尾加 `assert all(any(row) for row in mask)`，保证每行至少能看一个位置（否则 softmax 会 NaN）。
3. **修 loss 下界/上界**：把 `text_probs` 改成真正的 softmax 输出（例如一个 `VOCAB × VOCAB` 的二元转移表 + softmax），让概率不可能超过 1。
4. **让 `xt` 真正被用到**：写一个极简"模型" `v_θ(x_t, t) = a·x_t + b`（标量 a、b），用解析梯度做 SGD，最小化 `MSE(v_θ, ε − x0)`，观察 loss 能否下降，以及为什么一个线性模型学不好（提示：最优速度依赖 x0，需要条件信息）。
5. **补一个推理循环（练习 4）**：文本部分随机生成 3 个 token，遇到 `SEP_OPEN` 后从 `x_1 = ε` 出发用 Euler 法走 N 步（速度先用"oracle" `ε − x0` 代替），统计前向次数 = 文本 token 数 + N，再加上 CFG 后的次数。
6. **进阶（练习 3）**：写一个 `param_count(d, L, mmdit: bool)`，比较共享与 MMDiT 式模态专属权重的参数量（共享 `12d²·L`，MMDiT 约 `24d²·L`）。

---

## 8. 常见坑

- **把 "loss 在下降" 当成 "在训练"**：本代码的 loss 是按步数写死的；任何训练代码都要确认存在参数、梯度和更新。
- **标签 token 不归任何一类**：mask 中出现全 0 行，softmax 直接 NaN。特殊 token 必须明确归属。
- **多图序列只允许图内互看**：后面的图看不到前面的图，图像编辑、多轮生成会失去上下文。
- **算了 `x_t` 却不喂给模型**：flow matching 的输入必须是带噪样本和时间步 t，目标才是 `ε − x0`。
- **速度方向写反**：`x_t = (1 − t)x0 + tε` 下速度是 `ε − x0`，采样是 `x ← x − Δt·v`；换一种约定时两处要一起改。
- **固定损失权重不监控**：两个损失量级与梯度范数都可能随训练漂移，需要分别监控两条曲线。
- **相信讲义的"Use It"描述**：代码里没有线性投影、没有交替训练、也没有生成步骤，以代码为准。
