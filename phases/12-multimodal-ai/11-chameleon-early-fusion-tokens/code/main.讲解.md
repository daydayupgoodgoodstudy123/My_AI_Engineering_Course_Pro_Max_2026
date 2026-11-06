# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 11 节 Chameleon：仅用 Token 的早期融合 Multimodal Models ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`collections`），无需 NumPy / PyTorch / 网络，运行时间不到 0.1 秒

---

## 1. 这份代码在考察什么

这份代码把 Chameleon 的"早期融合"流水线压缩成不到 180 行标准库 Python，端到端走一遍：

1. **图像 → 离散 token**：一个"VQ-VAE 风格"的量化器，把 8×8 灰度图切成 4 个 patch，每个 patch 按 L2 距离映射到最近的码字（codebook entry），得到 4 个整数 ID。对应讲义"VQ-VAE as image tokenizer"。
2. **共享词表（shared vocabulary）**：文本 ID `0..31`、图像 ID `32..47`、分隔符 `<image>`=48、`</image>`=49，总共 50 个 ID 放在同一个空间里。对应讲义"The shared vocabulary"。
3. **交错序列 + 单一自回归模型**：训练数据是"caption + `<image>` 图像 token `</image>`"或反过来的交错序列；模型只做一件事——给定上一个 token 预测下一个 token，不区分模态。
4. **混合模态生成**：采样循环一路生成，文本和图像 token 从同一个分布里出来。

"transformer"被换成了一个 **bigram 计数表**，讲义说明这是有意为之："The code intentionally keeps the transformer tiny (bigrams) so you can trace the signal flow end to end." 所以这份代码适合看清**数据流和词表布局**，而不是图像质量。它也有几处设计缺陷（codebook 退化、缺 BOS/EOS、图像长度不受约束），恰好暴露了真实系统必须解决的问题，本讲解会逐一指出。

> 一句话：**图像先被 tokenizer 变成词表里的"单词"，之后图文就是同一条序列、同一个模型、同一种 next-token 采样**——而图像好不好，完全取决于 tokenizer。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VOCAB_TEXT` / `VOCAB_IMG` / `IMG_OFFSET` / `SEP_OPEN` / `SEP_CLOSE` / `VOCAB_SIZE` | 模块级常量 | 定义共享词表的 ID 区间 | Shared vocabulary |
| `CODEBOOK` | 模块级常量（列表推导式） | 16 个 4 维码字（手工构造，非学习得到） | VQ codebook |
| `quantize_patch` | 函数 | 最近码字查找，返回加了偏移的 token ID | 向量量化 |
| `image_to_tokens` | 函数 | 8×8 图 → 4 个 4×4 patch → 各自 2×2 平均池化成 4 维 → 量化 | 图像 tokenizer（encoder + 量化） |
| `synthesize_caption` / `synth_image` | 函数 | 4 类（red/blue/green/gray）合成 caption 与条纹灰度图 | 训练数据 |
| `make_dataset` | 函数 | 生成 n 条交错序列，约 40% 图像在前 | 交错多模态文档 |
| `train_bigram` | 函数 | 统计相邻 token 对的出现次数 | "模型训练"（bigram 的最大似然估计） |
| `sample_next` | 函数 | 按计数比例采样下一个 token | softmax 采样的离散版 |
| `generate` | 函数 | 自回归循环，见到 `</image>` 且已有文本就停 | Mixed-modality generation |
| `render` | 函数 | 把 ID 渲染成 `w*` / `i*` / `<image>` 方便阅读 | detokenize |
| `main` | 函数 | 四段演示：tokenizer、词表布局、数据集、训练 + 采样 | — |

数据流：`synth_image` → `image_to_tokens`（`quantize_patch`）→ 与 `synthesize_caption` 拼成交错序列（`make_dataset`）→ `train_bigram` → `generate`（`sample_next`）→ `render` 打印。

---

## 3. 逐段精讲

### 3.1 共享词表的 ID 布局

```python
random.seed(42)

VOCAB_TEXT = 32
VOCAB_IMG = 16
IMG_OFFSET = VOCAB_TEXT              # 32
SEP_OPEN = VOCAB_TEXT + VOCAB_IMG    # 48  <image>
SEP_CLOSE = SEP_OPEN + 1             # 49  </image>
VOCAB_SIZE = SEP_CLOSE + 1           # 50
```

- 这就是 Chameleon "一个 ID 空间"的缩影：`[文本 | 图像 | 分隔符]` 首尾相接。真实 Chameleon 的图像 codebook 有 8192 项；讲义举例"文本 BPE 比如 32000 → 合计 40192"，论文中实际是总词表 65,536，其中包含 8192 个图像 code。
- 图像码字索引 `k` 映射为 `k + IMG_OFFSET`，这样模型的 embedding 表和输出层只需一张 `VOCAB_SIZE` 大小的表，不需要两套。
- `random.seed(42)` 写在**模块顶层**：一 `import main` 就会重置全局随机状态。这让 `python main.py` 的输出可复现，但如果别的脚本 import 它，就会被"悄悄"改种子。

### 3.2 Codebook 与最近码字量化

```python
CODEBOOK = [[(i * 7 + 3 * j) % 8 for j in range(4)] for i in range(VOCAB_IMG)]


def quantize_patch(patch: list[int]) -> int:
    """Nearest-codebook lookup by L2 distance."""
    best = 0
    best_d = float("inf")
    for k, code in enumerate(CODEBOOK):
        d = sum((p - c) ** 2 for p, c in zip(patch, code))
        if d < best_d:
            best_d = d
            best = k
    return best + IMG_OFFSET
```

- `quantize_patch` 是教科书式的 VQ 量化：对每个码字算平方 L2 距离，取 argmin。用 `d < best_d`（严格小于），平局时保留**索引较小**的码字。
- 不开方：比较大小时 `‖x−c‖²` 与 `‖x−c‖` 的 argmin 相同，省一次 `sqrt`。
- ⚠️ **codebook 是手工构造的，不是学出来的**。真正的 VQ-VAE codebook 由 codebook loss / EMA 在训练中更新（讲义："Training: VAE reconstruction loss + commitment loss + codebook loss"），这里一个 loss 都没有。
- ⚠️ **16 个码字只有 8 个不同**：`(7i + 3j) % 8` 只依赖 `i mod 8`，所以码字 8～15 与 0～7 完全重复，又因为平局取小索引，8～15 **永远不会被选中**（我们穷举了 `0..9` 范围内全部 10⁴ 个 4 维整数向量验证过，只有 0～7 会出现）。名义上 K = 16，实际 K = 8。
- ⚠️ **亮度覆盖不足**：每个码字都是 0..7 的锯齿排列，均值只有 2.5、3.5、4.5 三种：

  | 码字 | 向量 | 均值 | Σ(v − 均值)² |
  |------|------|------|-------------|
  | 0 / 6 | `[0,3,6,1]` / `[2,5,0,3]` | 2.5 | 21 / 13 |
  | 1 / 3 / 5 / 7 | `[7,2,5,0]` / `[5,0,3,6]` / `[3,6,1,4]` / `[1,4,7,2]` | 3.5 | 29 / 21 / 13 / 21 |
  | 2 / 4 | `[6,1,4,7]` / `[4,7,2,5]` | 4.5 | 21 / 13 |

  对接近常数 `c` 的 patch，距离 = `4(c − 均值)² + Σ(v − 均值)²`。只要 `c ≥ 4.5`，都会落到"均值 4.5、方差项最小"的码字 4。合成图的像素在 2～9 之间，于是比 4.5 亮的图（red、green、gray）全部挤到同一个码字上——见第 6 节的运行结果。

### 3.3 `image_to_tokens`：切 patch + 下采样 + 量化

```python
def image_to_tokens(img: list[list[int]]) -> list[int]:
    """8x8 grayscale -> 4 patches of 4 floats (downsampled). Return token IDs."""
    patches = []
    for pr in range(0, 8, 4):
        for pc in range(0, 8, 4):
            flat = []
            for r in range(2):
                for c in range(2):
                    s = 0
                    for dr in range(2):
                        for dc in range(2):
                            s += img[pr + 2 * r + dr][pc + 2 * c + dc]
                    flat.append(s // 4)
            patches.append(flat)
    return [quantize_patch(p) for p in patches]
```

六层循环拆开看：

| 循环变量 | 取值 | 含义 |
|---------|------|------|
| `pr`, `pc` | 0, 4 | 4×4 patch 的左上角，8×8 图被切成 2×2 = 4 个 patch（行优先） |
| `r`, `c` | 0, 1 | patch 内的 2×2 子块位置 |
| `dr`, `dc` | 0, 1 | 子块内的 2×2 像素 |

- 每个 4×4 patch 经 **2×2 平均池化**变成 2×2 = 4 个数，展平成 4 维向量，再量化成 1 个 token。形状变化：`(8, 8)` → 4 个 `(4, 4)` → 4 个 4 维向量 → 4 个 token ID。
- 类比 Chameleon：512×512 → 32×32 = 1024 个 token，每个 token 负责 16×16 像素；这里 8×8 → 2×2 = 4 个 token，每个 token 负责 4×4 像素。
- 这里的"平均池化"扮演了 encoder 的角色（真实系统是 CNN + ViT 把 patch 编码成 256 维 feature）。
- ⚠️ 与讲义的出入：讲义写 "maps 8x8 patches to codebook indices"，实际是把 **8×8 整图**切成 **4×4 patch**。
- ⚠️ docstring 说 "4 floats"，但 `s // 4` 是整数整除，得到的是 `int`。即使改成 `/ 4` 保留小数，也救不了上一节的 codebook 退化（我们验证过：改为 `/ 4` 后 red、green、gray 都变成 `[36, 36, 36, 36]`）。
- ⚠️ 只有 encoder 一侧，没有 decoder：token 无法还原成像素，所以看不到"重建质量"，也就无法体会讲义说的 26–28 dB 上限。

### 3.4 合成数据：caption、图像与交错序列

```python
def synthesize_caption(kind: str) -> list[int]:
    if kind == "red":
        return [1, 5, 3, 7]
    if kind == "blue":
        return [2, 5, 3, 8]
    if kind == "green":
        return [1, 5, 3, 9]
    return [1, 5, 3, 10]


def synth_image(kind: str) -> list[list[int]]:
    shade = {"red": 7, "blue": 2, "green": 4, "gray": 5}[kind]
    return [[(shade + (r + c) % 3) for c in range(8)] for r in range(8)]
```

- caption 是 4 个"词"：blue 以 `w2` 开头，其他三类都以 `w1` 开头；中间固定 `w5 w3`；**类别信息只在最后一个词**（`w7/w8/w9/w10`）。
- 图像是灰度"条纹图"：基础亮度 `shade` 加上沿对角线循环的 `0/1/2`。所谓 red/blue/green 只是不同亮度，并没有颜色通道。像素范围：red 7～9、gray 5～7、green 4～6、blue 2～4。
- `{...}[kind]`：字典字面量直接按 key 取值，相当于一个小查找表。

```python
def make_dataset(n: int = 40) -> list[list[int]]:
    kinds = ["red", "blue", "green", "gray"]
    corpus = []
    for _ in range(n):
        k = random.choice(kinds)
        tokens = synthesize_caption(k) + [SEP_OPEN] + image_to_tokens(synth_image(k)) + [SEP_CLOSE]
        if random.random() < 0.4:
            tokens = [SEP_OPEN] + image_to_tokens(synth_image(k)) + [SEP_CLOSE] + synthesize_caption(k)
        corpus.append(tokens)
    return corpus
```

- 每条序列长 10：4 个文本 + `<image>` + 4 个图像 + `</image>`。以 40% 的概率换成"先图后文"——这就是讲义说的交错多模态文档，模型要从数据中学会两种顺序。
- 写法上先构造"先文后图"、再按概率覆盖，有一次多余的计算，但不影响结果。
- ⚠️ **没有 BOS / EOS**：序列开头和结尾没有特殊标记，bigram 学不到"第一个 token 是什么分布"、也学不到"何时结束"。讲义练习 5（测量先图 / 先文比例）因此无法直接在这份代码上完成，见第 7 节。
- 实际比例：`seed(42)` 下这 40 条里图像在前的有 19 条（47.5%），与名义上的 40% 有偏差，这是小样本的正常波动。

### 3.5 `train_bigram`：用计数代替 transformer

```python
def train_bigram(corpus: list[list[int]]) -> dict:
    counts: dict = defaultdict(lambda: defaultdict(int))
    for seq in corpus:
        for a, b in zip(seq, seq[1:]):
            counts[a][b] += 1
    return counts
```

- `zip(seq, seq[1:])` 产生所有相邻对 `(a, b)`，这正是 next-token prediction 的训练样本"输入 a、目标 b"。
- 计数归一化后就是 `P(b | a)` 的**最大似然估计**——对 bigram 模型来说，"最小化交叉熵"的闭式解就是数数。所以虽然代码里没有出现 loss，它和讲义的"one loss"在数学上是一回事。我们额外算了这个 bigram 在训练集上的平均负对数似然：0.449 nats / token（困惑度约 1.57），而均匀分布是 `ln 50 ≈ 3.91`。
- 双层 `defaultdict`：第一次访问 `counts[a][b]` 时自动创建内层字典和 0 计数，不必写 `if a not in counts`。
- 学到的关键计数（`seed(42)`，40 条序列）：

  ```text
  w1 -> w5: 31          w2 -> w5: 9          w5 -> w3: 40
  w3 -> w7: 13, w8: 9, w9: 11, w10: 7
  w7/w8/w9/w10 -> <image>: 8 / 7 / 5 / 1
  <image> -> i2: 31, i6: 9
  i2 -> i4: 31          i4 -> i4: 62, </image>: 31
  i6 -> i6: 27, </image>: 9
  </image> -> w1: 17, w2: 2
  ```

  可以直接看出 bigram 的两个盲点：`w3` 之后选哪个颜色词与开头是 `w1` 还是 `w2` 无关；`<image>` 之后画哪张图与 caption 无关。

### 3.6 `sample_next`：按计数比例采样

```python
def sample_next(bigram: dict, prev: int) -> int:
    dist = bigram.get(prev, {})
    if not dist:
        return random.randrange(VOCAB_SIZE)
    total = sum(dist.values())
    r = random.random() * total
    acc = 0
    for tok, c in dist.items():
        acc += c
        if r <= acc:
            return tok
    return next(iter(dist))
```

- 这是"轮盘赌"采样：在 `[0, total)` 里取随机数 `r`，按累计计数落在哪个区间就选哪个 token，等价于按 `count / total` 的概率采样——对应真实模型里"softmax 后按概率采样"（temperature = 1）。
- `bigram.get(prev, {})` 用 `.get` 而不是 `bigram[prev]`：对 `defaultdict` 用方括号访问不存在的 key 会**插入**一个空条目，`.get` 不会。
- 没见过的上下文（例如 `w0`、`w4`）走回退分支：从全部 50 个 ID 中**均匀**随机选一个，可能选出图像 token 或 `</image>`。真实 LM 的 softmax 永远给出完整分布，不存在"空分布"；n-gram 模型则会用平滑（smoothing）或回退（backoff）。
- 最后的 `return next(iter(dist))` 实际上**不可达**：`random.random()` 在 `[0, 1)` 内，`r < total`，循环里必然返回。它只是防御浮点误差的保险。

### 3.7 `generate` 与 `render`：混合模态生成

```python
def generate(bigram: dict, prompt: list[int], max_len: int = 40) -> list[int]:
    out = list(prompt)
    while len(out) < max_len:
        nxt = sample_next(bigram, out[-1])
        out.append(nxt)
        if nxt == SEP_CLOSE and any(t < VOCAB_TEXT for t in out):
            break
    return out
```

- 标准的自回归循环：每步只看最后一个 token（bigram 的"上下文窗口"长度为 1），采样、追加、重复。`max_len` 是**含 prompt** 的总长度上限。
- 停止规则是手写的：只要出现 `</image>` 且序列里已有文本 token，就认为"一图一文"完成了。
- ⚠️ 这条规则是缺 EOS 的补丁，带来几个后果：
  - 以 `[1, 5]` 这类文本 prompt 开头时，必然在第一个 `</image>` 停下，结果总是"先文后图"；
  - 以 `[SEP_OPEN]` 开头时，图像结束时还没有文本，不会停，于是会生成"图 → 文 → 又一张图"（实测例：`<image> i2 i4 </image> w1 w5 w3 w8 <image> i2 i4 </image>`）；
  - prompt 不能为空，否则 `out[-1]` 抛 `IndexError`。
- ⚠️ 图像段长度不受约束：bigram 不知道"一张图 = 4 个 token"。真实系统在推理端用约束解码强制 `<image>` 后恰好 1024 个图像 token。
- `any(t < VOCAB_TEXT for t in out)` 每步扫描整个序列，是 O(n) 的；序列很短，无所谓。

```python
def render(tokens: list[int]) -> str:
    parts = []
    for t in tokens:
        if t == SEP_OPEN:
            parts.append("<image>")
        elif t == SEP_CLOSE:
            parts.append("</image>")
        elif t < VOCAB_TEXT:
            parts.append(f"w{t}")
        else:
            parts.append(f"i{t - IMG_OFFSET}")
    return " ".join(parts)
```

- `render` 是 detokenizer 的玩具版：按 ID 区间判断模态。真实系统里这一步是"文本 token 走 BPE 解码，`<image>…</image>` 之间的 token 送进 VQ decoder 还原像素"。
- 注意判断顺序：先判两个分隔符，再判文本，剩下的一律当图像。如果以后加了 BOS/EOS（ID ≥ 50），会被错误地显示成 `i18`、`i19`，需要补分支。

### 3.8 `main`：四段演示

`main` 依次打印：tokenizer 结果 → 词表布局 → 前 4 条训练序列 → 训练 bigram 并以 `[1, 5]`（即 `w1 w5`）为 prompt 采样 3 次 → TAKEAWAY。随机数只在 `make_dataset` 和 `generate` 里消耗，而且都在 `seed(42)` 之后按固定顺序调用，所以每次运行输出完全相同。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、无 NumPy | 零依赖，每一步都能用 print 跟踪 | 无法扩展；生产用 PyTorch，VQ 部分用卷积 encoder/decoder |
| 手工 `CODEBOOK` | 不用训练 VQ-VAE，代码短 | 只有 8 个有效码字、亮度覆盖不足，4 类中 3 类同码；生产用学习得到的 codebook（K = 8192 等），并监控码字利用率 |
| 2×2 平均池化代替 encoder | 最简单的"降维 + 下采样" | 没有学习能力；生产用 CNN + ViT encoder |
| 只有 tokenizer 的 encoder 一侧 | 演示 token 化就够了 | 看不到重建质量；生产必须有 decoder 才能输出图像 |
| bigram 计数代替 transformer | 能手算、能 trace，讲义明确的取舍 | 上下文长度为 1：图像长度、caption-图像一致性都学不到；生产用带长上下文的 transformer |
| 共享 50 个 ID 的词表 | 直观展示"一个 ID 空间" | 生产词表数万（论文为 65,536，含 8192 个图像 code），embedding 与输出层随之变大 |
| 手写停止规则代替 EOS | 少一个特殊 token | 无法学"何时结束"，也无法学首个 token 的模态分布；生产用 BOS/EOS 与约束解码 |
| 未见上下文时均匀随机回退 | 保证总能输出 | 可能在文本里冒出图像 token；n-gram 用平滑/回退，神经 LM 天然输出完整分布 |
| 模块级 `random.seed(42)` | 输出可复现 | import 时改变全局随机状态；更好的做法是 `rng = random.Random(42)` 显式传递 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值，注解只当字符串保存；在旧版本 Python 中也能写 `list[int]` |
| 类型注解 | `def quantize_patch(patch: list[int]) -> int:` | 标注参数和返回值类型，不影响运行，便于阅读和静态检查 |
| 模块级常量 | `VOCAB_TEXT = 32`、`SEP_CLOSE = SEP_OPEN + 1` | 全大写命名表示"不该被修改"；可以由前面的常量推导 |
| 嵌套列表推导式 | `[[(i * 7 + 3 * j) % 8 for j in range(4)] for i in range(VOCAB_IMG)]` | 外层生成行、内层生成列，得到 16×4 的二维列表 |
| `%` 取模 | `(i * 7 + 3 * j) % 8`、`(r + c) % 3` | 余数运算，常用来制造周期性模式 |
| `float("inf")` | `best_d = float("inf")` | 正无穷，作为"求最小值"的初始值 |
| `enumerate` | `for k, code in enumerate(CODEBOOK)` | 同时拿到下标和元素 |
| `zip` 与切片错位 | `zip(seq, seq[1:])`、`zip(patch, code)` | 并行遍历；`seq[1:]` 错开一位得到相邻对 |
| 生成器表达式 + `sum` / `any` | `sum((p - c) ** 2 for p, c in zip(...))`、`any(t < VOCAB_TEXT for t in out)` | 不建中间列表；`any` 遇到第一个 True 就停止 |
| `**` 幂运算 | `(p - c) ** 2` | 平方 |
| 整除 `//` | `s // 4` | 向下取整的除法，结果是 `int` |
| `range(start, stop, step)` | `range(0, 8, 4)` | 产生 0、4，用来按步长切 patch |
| 字典字面量直接取值 | `{"red": 7, "blue": 2, ...}[kind]` | 一行实现查找表；key 不存在会抛 `KeyError` |
| 列表拼接 | `synthesize_caption(k) + [SEP_OPEN] + ... + [SEP_CLOSE]` | `+` 连接列表，生成新列表 |
| `random.choice` / `random.random` / `random.randrange` | `random.choice(kinds)`、`random.random() < 0.4`、`random.randrange(VOCAB_SIZE)` | 随机选元素 / `[0,1)` 浮点数 / `[0, n)` 整数 |
| `defaultdict` 嵌套 | `defaultdict(lambda: defaultdict(int))` | 访问不存在的 key 时自动用工厂函数创建默认值；`lambda` 是匿名函数 |
| `dict.get(key, default)` | `bigram.get(prev, {})` | 取不到时返回默认值，且不会往 `defaultdict` 里插入新 key |
| `dict.items()` / `dict.values()` | `for tok, c in dist.items()`、`sum(dist.values())` | 遍历键值对 / 只取值 |
| `next(iter(...))` | `next(iter(dist))` | 取可迭代对象的第一个元素（字典的第一个 key） |
| `while` + `break` | `while len(out) < max_len: ... break` | 条件循环，满足条件时提前退出 |
| `list(prompt)` | `out = list(prompt)` | 复制一份，避免修改调用者传入的列表 |
| f-string 格式符 | `f"  {kind:<6} -> codes {codes}"`、`f"w{t}"` | `:<6` 左对齐占 6 格 |
| 字符串乘法 / `join` | `"=" * 60`、`" ".join(parts)` | 重复字符串画分隔线 / 用空格拼接列表 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行（但模块顶层的 `random.seed(42)` 仍会执行） |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`cd code && python3 main.py`，耗时约 0.02 秒），完整输出如下：

```text
============================================================
CHAMELEON EARLY-FUSION TOY (Phase 12, Lesson 11)
============================================================

1. VQ tokenizer — 8x8 grayscale -> 4 patches -> 4 image tokens
------------------------------------------------------------
  red    -> codes [34, 36, 36, 36]
  blue   -> codes [38, 38, 38, 38]
  green  -> codes [34, 36, 36, 36]
  gray   -> codes [34, 36, 36, 36]

2. Shared vocabulary layout
------------------------------------------------------------
  text tokens   : 0..31
  image tokens  : 32..47
  <image>       : 48
  </image>      : 49
  vocab total   : 50

3. Dataset (40 sequences of interleaved text + image tokens)
------------------------------------------------------------
  <image> i2 i4 i4 i4 </image> w1 w5 w3 w7
  <image> i2 i4 i4 i4 </image> w1 w5 w3 w9
  w2 w5 w3 w8 <image> i6 i6 i6 i6 </image>
  w1 w5 w3 w7 <image> i2 i4 i4 i4 </image>

4. Train bigram, sample mixed-modality output
------------------------------------------------------------
  w1 w5 w3 w9 <image> i2 i4 i4 i4 </image>
  w1 w5 w3 w7 <image> i2 i4 i4 i4 i4 </image>
  w1 w5 w3 w7 <image> i6 i6 </image>

TAKEAWAY
------------------------------------------------------------
  one model, one vocab, one loss -> mixed-modality output for free
  tokenizer quality caps image fidelity (lesson 12.12 on Emu3)
  at scale you need QK-Norm + careful dropout for stable training
```

逐项解读：

- **第 1 段：tokenizer 退化**。4 类图像只得到 2 种 token 序列：red、green、gray 完全相同（`[34, 36, 36, 36]`），只有 blue 不同。原因见 3.2 节：codebook 均值只覆盖 2.5～4.5，比 4.5 亮的 patch 都落到码字 4（ID 36）；第一个 patch 恰好在码字 2 与 4（以及重复的 10、12）之间平局，按索引取 2（ID 34）。这直接意味着：**图像 token 里几乎没有类别信息**——"tokenizer 是质量天花板"的极端演示。
- **第 2 段：词表布局**。与 3.1 节的常量一一对应。
- **第 3 段：训练数据**。前两条是"先图后文"，后两条是"先文后图"；`i6 i6 i6 i6` 是 blue 的图像，其余三类都是 `i2 i4 i4 i4`。
- **第 4 段：生成结果**。三条都以 prompt `w1 w5` 开头，必然"先文后图"：
  - 第 1 条：green caption（`w9`）+ `i2 i4 i4 i4`，碰巧与训练数据一致；
  - 第 2 条：图像段有 **5** 个 token——bigram 在 `i4` 之后以 2/3 的概率继续 `i4`，不知道该停；
  - 第 3 条：red caption（`w7`）配 **blue 的图像 code**（`i6`），而且只有 **2** 个 token——caption 与图像不一致。
- 我们额外做了 20,000 次采样统计（`random.seed(0)`）：
  - 图像段恰好 4 个 token 的比例只有 13.8%（理论值 `31/40 × 4/27 + 9/40 × 27/256 ≈ 0.1385`），平均长度 3.99，但 2 个 token 的占 29.7%；
  - 图像与 caption 完全对应的比例只有 9.4%（理论值约 0.094）；
  - 还有 0.04% 的样本因为 `i4` 连续太多，在 `max_len = 30` 处被截断，根本没有 `</image>`。
- **TAKEAWAY 的第三行**提到 QK-Norm 和 dropout，但代码里没有注意力，也就没有这部分实现；讲义练习 3 要求自己补（参考测验 Q12）。

---

## 7. 动手改一改

1. **修复 codebook**：把 `CODEBOOK` 改成 `[[i] * 4 for i in range(VOCAB_IMG)]`（16 个亮度级别的平坦码字），重新运行。实测结果：red → `[39, 40, 40, 40]`、blue → `[34, 35, 35, 35]`、green → `[36, 37, 37, 37]`、gray → `[37, 38, 38, 38]`，4 类可区分。进一步：对所有训练 patch 做 k-means，用聚类中心当 codebook，并统计每个码字被使用的次数（码字利用率）。
2. **讲义练习 1、2（手算）**：计算 Chameleon 的压缩比（`512 × 512 × 24 / (1024 × 13) ≈ 473`）和 4K 图像的 token 数（`240 × 135 = 32,400`），再算本玩具的压缩比：64 像素 × 4 bit 对比 4 个 token × 4 bit（名义 K = 16），即 16 倍。
3. **加 BOS / EOS（讲义练习 5）**：令 `BOS, EOS = 50, 51`，训练时用 `[BOS] + seq + [EOS]`，`generate` 从 `[BOS]` 开始、遇到 `EOS` 停止，`render` 补两个分支。用 `make_dataset(2000)` 训练后从 BOS 采样 10,000 次，统计首个 token 是 `<image>` 的比例（`seed(7)` 下实测：数据中文本在前 59.6%，采样结果文本在前 60.4%）。
4. **约束解码**：在 `generate` 中加入"图像模式"：见到 `<image>` 后只允许从图像 ID 区间采样（把 bigram 分布中非图像 ID 过滤掉），恰好 4 个后强制输出 `</image>`。统计改动前后"图像段恰好 4 个 token"的比例（13.8% → 100%）。
5. **加长上下文**：把 bigram 改成 trigram（以 `(prev2, prev1)` 为 key），或把"当前 caption 的颜色词"作为条件拼进 key，观察 caption-图像一致率能否从 9.4% 提高；体会"为什么需要能看完整上下文的 transformer"。
6. **进阶（讲义练习 3）**：写一个 64 维的 QK-Norm 演示，把 q、k 同时放大 1/4/16 倍，对比 `q·k/√d` 与 `LN(q)·LN(k)/√d`（参考测验 Q12：前者 5.6 → 89.7 → 1434.8，后者恒为 5.095）。

---

## 8. 常见坑

- **以为 K = 16 就有 16 个可用码字**：要检查码字是否重复、是否真的被用到。codebook collapse（大量码字闲置）在真实 VQ-VAE 训练中也很常见，应监控码字利用率。
- **把"共享词表"误解为"模态自动对齐"**：本代码中 caption 与图像只有 9.4% 一致。共享词表只让不同模态在同一个 softmax 里竞争，一致性要靠模型对长距离上下文的建模。
- **图像段长度不受控**：VQ decoder 需要恰好 H×W 个 token（Chameleon 为 32×32 = 1024）才能 reshape 回特征图，推理端必须约束解码，否则输出无法渲染。
- **缺 BOS/EOS**：模型学不到序列首 token 的分布和结束时机，只能靠手写规则停止；空 prompt 还会直接报错。
- **对 `defaultdict` 用方括号读取**：`bigram[prev]` 会在 key 不存在时插入空条目，悄悄改变"训练好的模型"；只读时用 `.get`。
- **整除与浮点**：`s // 4` 会截断；在需要精确平均值的场景（例如计算重建误差）应使用 `/`。
- **模块顶层设随机种子**：`import main` 就会重置全局 `random` 状态，在其他实验脚本里复用这些函数时，结果可能"莫名其妙地"固定或改变。
- **把讲义的训练稳定性细节当成论文原文**：讲义说"dropout after every residual-add"和"最后一个 block 的 skip connection 上加 LN"，而论文是 7B 在注意力和 FFN 之后加 dropout，34B 则不用 dropout，改为把 norm 放到每个子层的输出上（Swin 式重排），并都使用 z-loss。复述时请以论文为准。
