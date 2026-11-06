# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 09 节 序列到序列模型 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅 Python 标准库（`math`、`random`）；讲义中的 PyTorch 版 `Encoder` / `Decoder` / `train_batch` / `greedy_decode` 不在本文件里

---

## 1. 这份代码在考察什么

讲义的 Build It 部分用 PyTorch 搭了 GRU encoder-decoder，并在 Step 5 用"复制任务"展示上下文向量瓶颈。本文件**不训练任何网络**，而是用几十行纯 Python 搭一个"解析式模拟"，把瓶颈的成因拆开给你看：

1. **定长**：无论源序列多长，编码结果都是 8 个浮点数（`context_dim=8`）。
2. **遗忘**：编码器每读一个新 token，旧状态乘以 0.85 衰减——越早的 token 在上下文里权重越小。
3. **解码只能看上下文**：解码器给目标序列打分时，唯一的信息来源就是这 8 个数。
4. **指标设计**：用"真实序列得分 > 随机序列得分"的命中率来衡量还剩多少信息——它的随机水平是 50%。

> 一句话：**用一个可以手算的玩具，复现"序列越长、定长上下文向量越不够用"的趋势**，为第 10 节的 attention 做铺垫。读的时候也要练习分辨"示意性模拟"和"真实训练实验"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `simulate_copy_accuracy(seq_len, context_dim, epochs, n_train, seed)` | 函数 | 对给定长度跑 100 次试验，返回命中率 | 瓶颈实验（讲义 Step 5 的简化版） |
| `embed` | 局部变量（10×8 列表） | 每个字母一个随机向量，固定不训练 | 词嵌入表 |
| `encode(sequence)` | 嵌套函数 | 带衰减地累加 embedding，得到上下文向量 | Encoder + 最终隐状态 |
| `decode_score(context, target)` | 嵌套函数 | 用上下文与目标 token 的点积打分，按位置递减加权 | Decoder 对目标序列的"信心" |
| `main()` | 函数 | 对长度 5/10/20/40/80 打印命中率表 | 演示入口 |

数据流：`random.Random(seed)` → 生成 `embed` → 每次试验：随机源序列 `seq` → `encode(seq)` 得 `c` → `decode_score(c, seq)` 与 `decode_score(c, 随机序列)` 比较 → 统计命中率。

---

## 3. 逐段精讲

### 3.1 独立随机数发生器与固定的"词嵌入"

```python
def simulate_copy_accuracy(seq_len, context_dim=8, epochs=200, n_train=300, seed=0):
    rng = random.Random(seed)
    vocab = list("abcdefghij")
    vocab_size = len(vocab)

    embed = [[rng.gauss(0, 0.3) for _ in range(context_dim)] for _ in range(vocab_size)]
    context = [0.0] * context_dim
```

- `random.Random(seed)`：创建一个**独立的**随机数发生器实例，而不是用全局的 `random.seed()`。好处是可复现且不影响其他代码的随机状态；每次调用函数都从同一个种子开始，所以不同长度用的是**同一张 `embed` 表**，只是之后抽到的序列不同。
- `list("abcdefghij")`：字符串拆成 10 个字符的列表，作为词表。
- `rng.gauss(0, 0.3)`：均值 0、标准差 0.3 的正态分布，模拟随机初始化的 embedding。
- ⚠️ 三个"摆设"：`epochs=200`、`n_train=300` 两个参数在函数体中**从未使用**；外层 `context = [0.0] * context_dim` 也没被用到（`decode_score` 的同名参数会遮蔽它）。它们暗示了"训练"，但这段代码里没有任何参数更新。可以把它们理解为作者原本想写训练版本留下的痕迹。

### 3.2 编码器：带衰减的累加

```python
    def encode(sequence):
        c = [0.0] * context_dim
        decay = 0.85
        for token in sequence:
            idx = vocab.index(token)
            for d in range(context_dim):
                c[d] = c[d] * decay + embed[idx][d]
        return c
```

- 这是一个**线性 RNN** 的极简版：`c_t = 0.85 · c_{t-1} + embed(x_t)`，对应讲义 `h_t = f(W·x_t + U·h_{t-1})` 中把 `U` 取成 `0.85·I`、`W` 取成查表、去掉非线性。
- 展开后：`c = Σ 0.85^(L-1-t) · embed(x_t)`。最后一个 token 权重 1；第 1 个 token 权重 `0.85^(L-1)`——L=20 时约 0.046，L=40 时约 0.0018。上下文向量几乎只"记得"结尾。
- 这就是讲义所说的"Everything the encoder learned about the source must be squeezed into that one context vector"：8 个数 + 指数遗忘。
- `vocab.index(token)`：在列表里线性查找下标，O(|V|)。10 个词无所谓；真实代码用 `dict` 做 token → id 映射。
- ⚠️ 简化：没有非线性、没有门控、没有学习。真实 LSTM/GRU 的遗忘率由门控**按内容学习**，所以 `main()` 最后打印 "real LSTMs decay more gracefully but hit the same ceiling."

### 3.3 解码器打分：点积 + tanh + 位置递减

```python
    def decode_score(context, target):
        total = 0.0
        recovery = 1.0
        for token in target:
            idx = vocab.index(token)
            score = sum(context[d] * embed[idx][d] for d in range(context_dim))
            normed = math.tanh(score) * recovery
            total += max(0.0, normed)
            recovery *= 0.9
        return total / max(1, len(target))
```

- **点积 `score`**：上下文与目标 token embedding 越"同向"，说明上下文里越可能含有这个 token——这是第 10 节 attention 打分的雏形（attention 是 decoder 状态与**每个** encoder 状态做点积，这里只能与**一个**上下文向量做）。
- **`math.tanh`**：把分数压到 (-1, 1)，避免某个大分数主导总和。
- **`recovery` 每步乘 0.9**：模拟"解码越往后越难恢复信息"——第 1 个目标 token 权重 1，第 10 个只有 `0.9⁹ ≈ 0.39`。
- **`max(0.0, normed)`**：负分截为 0（类似 ReLU），只累计"支持"的证据。
- **`/ max(1, len(target))`**：按长度取平均；`max(1, …)` 防止空序列除零。
- 🔍 一个值得注意的错位：`recovery` 让**目标开头**最重要，而 `encode` 记得最清楚的是**源序列结尾**。复制任务中目标 = 源，所以解码器最看重的恰恰是编码器忘得最厉害的部分。这正是 Sutskever 等人（2014）把源句**反转**后再输入的动机（测验 Q9 有定量实验：把这里改成 `reversed(target)`，长序列命中率回升到 90% 以上）。

### 3.4 实验主体：和随机序列比

```python
    hits = 0
    trials = 100
    for _ in range(trials):
        seq = [rng.choice(vocab) for _ in range(seq_len)]
        c = encode(seq)
        target_score = decode_score(c, seq)

        noise_score = decode_score(c, [rng.choice(vocab) for _ in range(seq_len)])
        if target_score > noise_score:
            hits += 1
    return hits / trials
```

- 每次试验：随机生成源序列 → 编码 → 对"正确答案"（源序列本身）和"干扰项"（等长随机序列）分别打分 → 正确答案得分更高就算命中。
- 这是一个**二选一判别任务**，不是讲义所说的逐 token 复制准确率：
  - 上下文向量完全没用时，命中率 ≈ 50%（抛硬币），而不是 0%；
  - 试验只有 100 次，统计波动约 ±5 个百分点，所以偶尔会出现低于 50% 的数。
- `rng.choice(vocab)`：从列表中等概率抽一个元素。
- ⚠️ 与讲义的差异：讲义 Step 5 表格（5→98%、10→91%、20→62%、40→23%）描述的是训练 GRU 复制模型的结果，本模拟复现不出这些数字（下限约 50%）；两者一致的只是"随长度下降"的趋势。

### 3.5 `main()`：打印对齐的表格

```python
    print(f"{'seq_len':>8}  {'accuracy':>10}")
    for length in [5, 10, 20, 40, 80]:
        acc = simulate_copy_accuracy(length)
        print(f"{length:>8}  {acc:>9.0%}")
```

- `{'seq_len':>8}`：字符串右对齐、宽 8。
- `{acc:>9.0%}`：`%` 格式符把 0.89 显示为 `89%`（乘 100 加百分号），`.0` 表示不保留小数，`>9` 右对齐宽 9。
- 前面的几行 `print` 把模拟的假设（8 维上下文、0.85 衰减）直接打印出来——好的实验脚本应该"自带说明"，读输出的人不需要翻代码就知道条件。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不训练、用解析式模拟 | 无需 PyTorch、0.1 秒跑完，每一步可手算 | 数字不能代表真实模型；讲义 Step 5 / 练习 1 要求真正训练 GRU 复制模型 |
| 线性衰减编码器（0.85） | 一个参数就能表达"遗忘" | 真实 RNN 的遗忘是门控学习出来的，且有非线性 |
| 8 维上下文 | 让"定长"足够紧，瓶颈明显 | 真实隐状态 256–1024 维；但定长本质不变 |
| 与随机序列比较的二选一指标 | 实现简单，不需要解码出具体 token | 下限是 50% 而非 0%，比真实复制准确率宽松得多 |
| 每个长度 100 次试验 | 运行快 | 波动约 ±5%；想要稳定结论应增大 `trials` 或多种子平均 |
| 独立 `random.Random(seed)` | 可复现、不污染全局随机状态 | 无 |
| 保留未使用的 `epochs`、`n_train` 参数 | （推测）为训练版本预留 | 误导读者以为有训练；应删除或真正实现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def simulate_copy_accuracy(seq_len, context_dim=8, ...)` | 不传参时使用默认值 |
| `list(str)` | `list("abcdefghij")` | 把字符串拆成单字符列表 |
| 嵌套列表推导式 | `[[rng.gauss(0, 0.3) for _ in range(context_dim)] for _ in range(vocab_size)]` | 生成 10×8 的二维列表；`_` 表示不用的循环变量 |
| 列表乘法 | `[0.0] * context_dim` | 生成全 0 列表（元素是不可变的 float，所以安全） |
| `random.Random(seed)` | `rng = random.Random(seed)` | 独立随机数发生器实例，有 `gauss`、`choice` 等方法 |
| 嵌套函数（闭包） | `def encode(sequence):` 定义在外层函数内部 | 可以直接读取外层的 `embed`、`vocab`、`context_dim` |
| 变量遮蔽 | `decode_score(context, target)` 的参数 `context` | 内层同名参数会遮蔽外层变量，外层 `context` 因此从未被用到 |
| `list.index` | `vocab.index(token)` | 线性查找元素下标；找不到抛 `ValueError` |
| 生成器表达式 + `sum` | `sum(context[d] * embed[idx][d] for d in range(context_dim))` | 点积，不建中间列表 |
| `math.tanh` | `math.tanh(score)` | 双曲正切，输出在 (-1, 1) |
| 复合赋值 | `recovery *= 0.9`、`hits += 1` | 等价于 `x = x * 0.9` |
| f-string 对齐 | `{'seq_len':>8}`、`{length:>8}` | `>` 右对齐，数字为宽度 |
| f-string 百分比 | `{acc:>9.0%}` | 自动乘 100 并加 `%` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，仅标准库，约 0.07 秒）的完整输出：

```text
toy simulation of encoder-decoder bottleneck
context vector has fixed size = 8 floats
encoder decays state at rate 0.85 per step (simulates forgetting)

 seq_len    accuracy
       5        89%
      10        83%
      20        69%
      40        53%
      80        51%

real LSTMs decay more gracefully but hit the same ceiling.
attention (lesson 10) removes the fixed-size constraint.
```

逐行解读：

- **长度 5 → 89%**：5 个 token 时，第 1 个 token 权重仍有 `0.85⁴ ≈ 0.52`，上下文里信息较完整，真实序列大多能胜过随机序列。
- **长度 10 → 83%、20 → 69%**：开头 token 的权重分别降到约 0.23 和 0.046，而解码打分最看重的正是开头——命中率稳步下降。
- **长度 40 → 53%、80 → 51%**：几乎就是 50% 的随机水平，说明此时上下文向量对"整条序列是否正确"已经几乎没有判别力。
- 和讲义 Step 5 表格对比：讲义是 98% → 23% 的复制准确率，本模拟是 89% → 51% 的二选一命中率；**数字不可比，趋势一致**。
- 结尾两行点题：真实 LSTM 的遗忘更平缓（门控按内容决定保留什么），但定长向量的上限依然存在；attention 让解码器每一步都能直接访问所有编码器状态，从根本上去掉定长约束。

---

## 7. 动手改一改

1. **增大上下文维度**：把 `context_dim` 改成 64，观察短序列和长序列的命中率分别怎么变——维度能救短序列，救不了长序列吗？
2. **去掉遗忘**：把 `decay` 改为 1.0（纯累加，相当于词袋），再看长度 40、80 的结果；思考"不遗忘"为什么仍然不够（提示：加法丢失了顺序）。
3. **反转解码顺序**：把 `for token in target:` 改为 `for token in reversed(target):`，解释结果并联系 Sutskever 等人的"反转源句"技巧。
4. **让统计更可靠**：把 `trials` 提到 2000，并对 `seed=0..4` 取平均，画出长度-命中率曲线。
5. **清理代码**：删除未使用的 `epochs`、`n_train`、外层 `context`；把 `vocab.index` 换成预先构建的字典 `tok2id`。
6. **进阶**：实现一个"attention 版"打分——不再只保留最终 `c`，而是保存每一步的状态列表，解码第 i 个 token 时与所有状态做点积取最大值，对比长序列命中率。

---

## 8. 常见坑

- **把模拟当实验**：这里的数字不是训练出来的 GRU 准确率，不能拿去和论文或讲义的表格直接比较。
- **忽略随机基线**：二选一任务的"0 信息"水平是 50%，看到 51% 不要以为"还剩一半能力"。
- **小样本波动**：100 次试验的结果会因种子不同而上下浮动 5 个百分点左右（换 `seed=1` 时长度 80 是 43%），比较前要多次平均。
- **嵌套函数里的变量遮蔽**：内层参数与外层变量同名（`context`）时，读代码容易误以为用的是外层变量。
- **未使用的参数**：函数签名里的 `epochs`、`n_train` 不起任何作用，改它们不会改变结果。
