# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 14 节 Show-o 与离散扩散统一模型 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

Show-o 的图像生成用的是 MaskGIT 式**掩码离散扩散**：从全 `<MASK>` 出发，每步并行预测所有被遮位置，只提交最有把握的一部分，迭代若干步填满。这份 110 行的脚本只模拟**采样循环**，模型用一个 `mock_logits` 假装：

1. **cosine mask 日程**：`cosine_schedule(T)` 给出每一步之后的 mask 比例。
2. **一次并行预测 + 按置信度提交**：`step_unmask` 对所有被遮位置取 argmax 和置信度，排序后提交前若干个。
3. **mask 逐步溶解的可视化**：`render` 把每一步的 16 个 token 打印成一行，看 `.` 一点点被数字替换。

> 一句话：**这份代码把 MaskGIT 的推理循环骨架写清楚了，但"每步提交多少"的语义写错了，而且 mock 模型不看上下文，所以演示不了"为什么要多步"**。读懂这两处，你就真正理解了掩码离散扩散。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VOCAB = 8`、`SEQ_LEN = 16`、`MASK = -1` | 常量 | 码本大小 8、16 个 image token、mask 记号 | VQ token 网格 |
| `cosine_schedule` | 函数 | 返回 T 个 mask 比例，从 0.981 降到 0 | mask 日程 |
| `mock_logits` | 函数 | 假 Transformer：噪声 + 按 prompt/位置的偏置 | 并行预测 |
| `softmax` | 函数 | 数值稳定 softmax | 置信度 |
| `step_unmask` | 函数 | 预测所有被遮位置，按置信度提交前 `keep_ratio` 比例 | 置信度提交（commitment） |
| `sample` | 函数 | 外层循环：按日程调用 `step_unmask`，兜底填满 | 迭代解码 |
| `render` | 函数 | 把 token 列表格式化成一行，mask 显示为 `.` | 可视化 |
| `main` | 函数 | 打印日程、采样 trace、四种任务说明 | — |

数据流：`random.seed(2)` → `cosine_schedule(8)` 打印 → `sample(prompt_seed=3)`：`[MASK]*16` →（每步）`mock_logits` → `softmax` → 排序 → 提交 → 记录 trace → `render` 打印。

---

## 3. 逐段精讲

### 3.1 `cosine_schedule`：mask 比例怎么递减

```python
def cosine_schedule(T: int) -> list[float]:
    """Mask ratio at step t, in [0, 1]. Goes 1.0 -> 0.0."""
    return [math.cos(math.pi * (t + 1) / (2 * T)) for t in range(T)]
```

- 第 t 步**之后**的 mask 比例为 `cos(π(t+1)/2T)`。T = 8 时为 `0.981, 0.924, 0.831, 0.707, 0.556, 0.383, 0.195, 0.000`。
- 讲义写的是 `cos(πt / 2T)`、t = 0..T（共 T+1 个值，起点 1.0）；代码用 `t + 1` 跳过了起点，只保留 T 个"步后"值——两者等价，只是下标约定不同。
- cosine 的形状：开始下降很慢（0.981、0.924），中后段下降很快。翻译成"每步揭开多少"就是**前少后多**——第一步几乎没有上下文，只敢提交极少数 token。
- ⚠️ 最后一项 `cos(π/2)` 在浮点中是 `6.12e-17` 而不是 0，这会在 3.5 节造成一个小 bug。

### 3.2 `mock_logits`：一个不看上下文的"Transformer"

```python
def mock_logits(tokens, prompt_seed=0):
    logits = []
    for i, t in enumerate(tokens):
        base = [random.gauss(0, 0.3) for _ in range(VOCAB)]
        bias = (prompt_seed + i) % VOCAB
        base[bias] += 2.5
        if t != MASK:
            base[t] += 3.0
        logits.append(base)
    return logits
```

- 每个位置得到 8 个 logits：σ = 0.3 的噪声 + 在 `(prompt_seed + i) % 8` 上加 2.5（模拟"prompt 决定了这个位置该画什么"）。
- 一次调用就给出**所有 16 个位置**的 logits——这就是"并行预测"：真实 Show-o 中也是一次前向得到每个位置的分布。
- `if t != MASK: base[t] += 3.0`：已揭开的位置偏向自己，但 `step_unmask` 不会重新预测已揭开位置，这一行实际上不起作用。
- ⚠️ **关键简化**：被 mask 位置的 logits **完全不依赖其他位置**。讲义"Use It"说它"predicts logits based on a prompt and the currently-unmasked tokens"，与代码不符。后果：
  - 2.5 的偏置远大于 0.3 的噪声，argmax 永远等于偏置 token（重复 1 万次、16 万个位置无一例外），最终序列一定是 `(seed + i) % 8`；
  - 揭开顺序只由噪声决定，"先揭哪个"对结果没有任何影响；
  - 一步揭开全部与八步揭开结果相同——**演示不了讲义练习 1"为什么不能一步完成"**。测验 Q11 给出了一个让位置依赖左邻的 mock，可以复现"一步解码会拼出不一致的序列"。

### 3.3 `softmax`

```python
def softmax(xs):
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    z = sum(e)
    return [x / z for x in e]
```

- 标准的减最大值写法，防止 `exp` 溢出。这里的概率只用于两件事：取 argmax 和给出置信度 `probs[top]`。

### 3.4 `step_unmask`：一次并行预测 + 按置信度提交

```python
    logits = mock_logits(tokens, prompt_seed)
    preds = []
    confs = []
    for i, t in enumerate(tokens):
        if t == MASK:
            probs = softmax(logits[i])
            top = max(range(VOCAB), key=lambda k: probs[k])
            preds.append((i, top, probs[top]))
        else:
            preds.append((i, t, 1.0))
        confs.append(preds[-1][2])
    masked_indices = [i for i, t in enumerate(tokens) if t == MASK]
    masked_indices.sort(key=lambda i: -preds[i][2])
    n_to_keep = max(1, int(len(masked_indices) * keep_ratio))
    new_tokens = list(tokens)
    for idx in masked_indices[:n_to_keep]:
        new_tokens[idx] = preds[idx][1]
    return new_tokens
```

- 对每个被遮位置：softmax → `max(range(VOCAB), key=...)` 取 argmax → 记下 `(位置, 预测 token, 置信度)`。
- `masked_indices.sort(key=lambda i: -preds[i][2])`：按置信度**降序**排序（取负号实现降序）。
- 提交前 `n_to_keep` 个，其余保持 `MASK`——即 MaskGIT 的"keep the top-K most confident predictions and re-mask the rest"。
- `new_tokens = list(tokens)`：复制一份再改，不修改调用方的列表，trace 才能记录每一步的快照。
- ⚠️ `confs` 列表算出来但从未使用。
- ⚠️ 用的是 argmax（贪心），不是采样。MaskGIT 实际会从分布中采样 token，并给置信度加上随步数退火的 Gumbel 噪声，以增加多样性。
- ⚠️ `n_to_keep = len(masked_indices) * keep_ratio`：提交数是"**剩余** mask 数 × 比例"。这与日程的语义不一致（见下一节）。

### 3.5 `sample`：日程语义错位与浮点 bug

```python
def sample(prompt_seed, T=8):
    tokens = [MASK] * SEQ_LEN
    traces = [list(tokens)]
    ratios = cosine_schedule(T)
    for step in range(T):
        remaining = sum(1 for t in tokens if t == MASK)
        if remaining == 0:
            break
        keep_ratio = max(0.15, 1 - ratios[step])
        tokens = step_unmask(tokens, prompt_seed, keep_ratio)
        traces.append(list(tokens))
    while any(t == MASK for t in tokens):
        tokens = step_unmask(tokens, prompt_seed, 1.0)
        traces.append(list(tokens))
    return traces
```

- `1 - ratios[step]` 是"这一步之后全图**已揭开**的比例"，但它被当成"**剩余** mask 中要提交的比例"传给 `step_unmask`。再加上 `max(0.15, …)` 的下限，结果是：

  | 步 | 剩余 | keep_ratio | 实际揭开 | MaskGIT 语义应揭开 |
  |----|------|-----------|---------|-----------------|
  | 0 | 16 | 0.15（下限） | 2 | 1 |
  | 1 | 14 | 0.15（下限） | 2 | 1 |
  | 2 | 12 | 0.169 | 2 | 1 |
  | 3 | 10 | 0.293 | 2 | 2 |
  | 4 | 8 | 0.444 | 3 | 3 |
  | 5 | 5 | 0.617 | 3 | 2 |
  | 6 | 2 | 0.805 | 1 | 3 |
  | 7 | 1 | ≈1.0 | 1 | 3 |

  代码是"前期多、后期少"，与 cosine"前少后多"的设计意图**正好相反**。正确做法是按"步后应剩 `floor(N × ratio)` 个 mask"计算提交个数（测验 Q9 给出改写，实测 masked 数为 `16 → 15 → 14 → 13 → 11 → 8 → 6 → 3 → 0`）。
- **浮点 bug**：`T = 1` 时 `ratios = [6.12e-17]`，`keep_ratio = 0.9999999999999999`，`int(16 × 0.9999…) = 15`，只揭开 15 个，剩下 1 个由 `while` 兜底，**多走一步**（实测 `16 → 1 → 0`）。T = 8 时最后一步只剩 1 个，被 `max(1, …)` 掩盖。
- `while any(...)` 兜底循环保证一定填满，但也意味着"总步数 ≤ T"不再成立；而 `if remaining == 0: break` 又会让大 T 提前结束（T = 16 实测只用了 13 步）。
- `traces` 保存每一步的快照列表，供 `main` 打印。

### 3.6 `render` 与 `main`

```python
def render(tokens):
    return " ".join(f"{t:>2}" if t != MASK else " ." for t in tokens)
```

- 每个位置占 2 个字符：数字右对齐，mask 显示为 ` .`，保证每行对齐、方便肉眼看"溶解"过程。
- `main` 打印三块：日程、trace（每行附 `masked=` 计数）、"一个 checkpoint 四种任务"说明（文本生成、VQA、T2I、inpainting）。inpainting 只需把初始 `tokens` 换成"部分已知 + 部分 MASK"，同一个 `sample` 循环即可——这就是讲义说的"comes for free"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| mock logits 代替 Transformer | 让注意力集中在采样循环 | 预测与上下文无关，无法体现多步解码的意义；真实模型在图像块内双向注意力 |
| argmax 提交 | 结果确定、易读 | 没有多样性；MaskGIT 采样 token 并在置信度上加退火 Gumbel 噪声 |
| `keep_ratio` 作用于剩余 mask | 实现简单 | 日程语义错位，揭开曲线形状反了；应按"目标剩余个数"计算 |
| `max(0.15, …)` 下限 | 防止早期一步揭不开、循环停滞 | 进一步扭曲了日程；正确的整数逻辑只需保证每步至少 1 个 |
| `while` 兜底 | 保证一定填满 | 掩盖了浮点 bug，步数不受 T 控制 |
| 16 个 token、码本 8 | 一屏打印得下 | 真实 Show-o：512×512 约 1,024 个 token（讲义），码本上万 |
| 只模拟推理 | 篇幅所限 | 训练（随机 mask 比例 + 交叉熵）与混合注意力 mask 未实现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| 列表推导式 + 数学函数 | `[math.cos(math.pi * (t + 1) / (2 * T)) for t in range(T)]` | 一行生成日程 |
| 列表乘法 | `[MASK] * SEQ_LEN` | 生成 16 个 `-1`（不可变元素才可安全这样复制） |
| `enumerate` | `for i, t in enumerate(tokens)` | 同时取下标与值 |
| `max` + `key` 实现 argmax | `max(range(VOCAB), key=lambda k: probs[k])` | 返回使 `probs[k]` 最大的 k |
| `lambda` | `lambda i: -preds[i][2]` | 匿名函数，常作排序键 |
| `list.sort(key=...)` 原地排序 | `masked_indices.sort(key=lambda i: -preds[i][2])` | 取负号实现降序；也可用 `reverse=True` |
| 元组与索引 | `preds.append((i, top, probs[top]))`、`preds[-1][2]` | 三元组；`[-1]` 取最后一个元素 |
| 切片 | `masked_indices[:n_to_keep]` | 取前 n 个 |
| `list(tokens)` 浅拷贝 | `new_tokens = list(tokens)`、`traces.append(list(tokens))` | 复制列表，避免后续修改影响快照 |
| 生成器 + `sum` 计数 | `sum(1 for t in tokens if t == MASK)` | 统计满足条件的元素个数 |
| `any` | `while any(t == MASK for t in tokens)` | 只要还有 mask 就继续 |
| `int()` 截断 | `int(len(masked_indices) * keep_ratio)` | 向零取整；浮点误差可能少 1（见 3.5） |
| 条件表达式 + f-string | `f"{t:>2}" if t != MASK else " ."` | 右对齐两位或显示占位符 |
| `str.join` | `" ".join(...)` | 用空格拼接字符串序列 |
| f-string 格式符 | `{r:.3f}`、`{t:>2}`、`{n_mask:>2}` | 小数位、右对齐宽度 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，瞬间完成）：

```text
Schedule (cosine, T=8 steps)
  step  0  mask_ratio = 0.981
  step  1  mask_ratio = 0.924
  step  2  mask_ratio = 0.831
  step  3  mask_ratio = 0.707
  step  4  mask_ratio = 0.556
  step  5  mask_ratio = 0.383
  step  6  mask_ratio = 0.195
  step  7  mask_ratio = 0.000

SAMPLING TRACE (prompt_seed=3)
  step  0  masked=16  |  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
  step  1  masked=14  |  .  .  .  .  .  .  .  .  .  .  .  .  .  0  1  .
  step  2  masked=12  |  .  .  .  6  .  .  .  .  .  4  .  .  .  0  1  .
  step  3  masked=10  |  .  .  .  6  .  .  .  2  .  4  .  .  7  0  1  .
  step  4  masked= 8  |  .  .  .  6  .  .  1  2  .  4  5  .  7  0  1  .
  step  5  masked= 5  |  3  .  .  6  .  0  1  2  3  4  5  .  7  0  1  .
  step  6  masked= 2  |  3  4  5  6  .  0  1  2  3  4  5  6  7  0  1  .
  step  7  masked= 1  |  3  4  5  6  .  0  1  2  3  4  5  6  7  0  1  2
  step  8  masked= 0  |  3  4  5  6  7  0  1  2  3  4  5  6  7  0  1  2
```

逐项解读：

- **日程**：与 `cos(π(t+1)/16)` 一致；最后一项打印为 0.000，但真实值是 6.12e-17。
- **trace 第一行**是初始状态（全 mask），之后 8 行对应 8 步，合计 9 行。
- **每步揭开数** `2, 2, 2, 2, 3, 3, 1, 1`：前期被 `max(0.15, …)` 抬高、后期反而只揭 1 个，与 cosine 的"前少后多"相反（见 3.5 的表格）。
- **揭开位置是散布的**（13、14 → 3、9 → 7、12 …），不是从左到右——这正是并行解码与自回归的直观区别，也是图像块内必须用双向注意力的原因。
- **最终序列**正好是 `(3 + i) % 8`：`3 4 5 6 7 0 1 2 3 4 5 6 7 0 1 2`。换成 `prompt_seed = 0` 或 `5` 就整体平移，说明结果只由 prompt 和位置决定，与揭开顺序无关。

---

## 7. 动手改一改

1. **（练习 3）** 写一个 `linear_schedule(T)`，返回 `1 - (t + 1) / T`，并用"步后剩余 `floor(N × ratio)`"的逻辑分别打印 cosine 和 linear 在 N = 16、N = 1,024 时每步揭开的数量（答案见测验 Q12）。
2. **修正日程语义**：把 `step_unmask` 改为接受"提交个数 k"，在 `sample` 中按目标剩余个数计算 k，最后一步强制清零；确认 T = 1 时只走 1 步（参考测验 Q9、Q10）。
3. **加入随机性**：把 argmax 改成按 `probs` 采样，并在排序用的置信度上加 `temperature × (1 − step/T) × Gumbel` 噪声，观察多次采样结果的多样性。
4. **（练习 1）让模型看上下文**：把 `mock_logits` 改成"位置 i 偏好左邻 + 1，第一个位置双峰"（测验 Q11 的 `mock_logits_dep`），比较 T = 1、8、16 时序列的不一致程度（实测平均断点数 7.47、2.19、0.21）。
5. **inpainting**：把初始 tokens 设成 `[3, 4, 5, 6, MASK, MASK, MASK, MASK, 3, 4, ...]`，只让中间 4 个位置参与采样，验证同一个循环可以完成"局部重绘"。
6. **（练习 4）** 写一个函数计算 `num_tokens × log2(K)` 与原始像素 bit 数的比值，对比 Show-o（1,024 token、K = 16,384）与 Emu3（4,096 token、K = 32,768）的压缩比。

---

## 8. 常见坑

- **把"全局 mask 比例"当成"剩余 mask 的提交比例"**：日程形状会被彻底扭曲。
- **浮点 `cos(π/2) ≠ 0`**：用比例相乘再 `int()` 截断时，最后一步可能少提交一个；最后一步应显式清零。
- **并行预测不看上下文**：这样的 mock 无法体现多步解码的价值；真实模型的每一步都以已提交的 token 为条件。
- **只用 argmax 不采样**：生成结果完全确定，没有多样性。
- **图像块用因果 mask**：揭开顺序由置信度决定而非从左到右，因果 mask 会让模型看不到已揭开的"后面"的 token。
- **以为步数越少越好**：步数太少会把不同模式的片段拼在一起（条件独立假设失效）。
- **轻信讲义的分类表**：LlamaGen 是自回归模型，不属于"掩码扩散"一类（讲义练习 5 本身就在对比二者）。
