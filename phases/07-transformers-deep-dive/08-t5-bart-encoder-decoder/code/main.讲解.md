# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 08 节 T5、BART——Encoder-Decoder 模型 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`random`）

---

## 1. 这份代码在考察什么

这份代码不搭模型，只做 encoder-decoder 预训练里**最容易写错、也最值得亲手写一遍**的部分——"怎么把一段无标注文本变成 `(破坏后的输入, 目标输出)` 监督样本"：

1. **T5 span corruption**：选出若干不重叠的 span，在 source 中用唯一哨兵 `<extra_id_N>` 替换，target 里按"哨兵 + 原内容"排列，结尾再加一个收尾哨兵。
2. **可逆性检查（round trip）**：用 source + target 重建原句。讲义说"真实训练不会这么做，但这个检查很便宜，能抓住 span 下标记账里的 off-by-one 错误"。
3. **BART 的 5 种噪声函数**：token masking、token deletion、text infilling、sentence permutation、document rotation。
4. **随机性管理**：所有函数接收 `rng` 参数，便于复现和测试。

> 一句话：**encoder-decoder 预训练 = 造数据的艺术**。模型结构与第 05 节一样，区别全在"怎么破坏输入、让 decoder 输出什么"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sentinel(i)` | 函数 | 生成 `<extra_id_i>` 字符串 | T5 哨兵 token |
| `corrupt_spans(tokens, mask_rate, mean_span, rng)` | 函数 | T5 span corruption，返回 `(source, target)` | 预训练样本构造 |
| `round_trip(source, target)` | 函数 | 用 target 中的 span 填回 source 的哨兵 | 可逆性检查 |
| `token_mask` | 函数 | 每个 token 以概率 `rate` 换成 `<mask>` | BART 噪声 1 |
| `token_delete` | 函数 | 每个 token 以概率 `rate` 删除 | BART 噪声 2 |
| `text_infill` | 函数 | 把一段 span 换成**单个** `<mask>` | BART 噪声 3 |
| `sentence_permute` | 函数 | 打乱句子顺序 | BART 噪声 4 |
| `document_rotate` | 函数 | 从随机位置把文档"旋转" | BART 噪声 5 |
| `main()` | 入口 | 演示 span corruption + round trip，再逐个演示 BART 噪声 | — |

数据流：`main → corrupt_spans → round_trip`（比较是否等于原句）；BART 部分每个噪声函数各用一个独立种子的 `random.Random`，互不影响。

---

## 3. 逐段精讲

### 3.1 哨兵与参数换算

```python
def sentinel(i):
    return f"<extra_id_{i}>"


def corrupt_spans(tokens, mask_rate=0.15, mean_span=3.0, rng=None):
    if rng is None:
        rng = random.Random()
    n = len(tokens)
    n_mask = max(1, int(round(n * mask_rate)))
    n_spans = max(1, int(round(n_mask / mean_span)))
```

- 默认参数 `mask_rate=0.15, mean_span=3.0` 对应 T5 论文的设置：遮约 15% 的 token、平均 span 长 3。
- `n_mask`：总共要遮多少个 token；`n_spans`：分成几个 span。两处都用 `max(1, ...)` 保证短句至少遮 1 个。
- ⚠️ Python 3 的 `round` 是**银行家舍入**：`round(4.5) = 4`、`round(2.5) = 2`。30 个 token × 0.15 = 4.5 → `n_mask = 4`，这会让人"意外"。讲义的片段写的是 `int(n * mask_rate)`（直接向下取整），与代码略有出入。
- `rng=None` + `if rng is None: rng = random.Random()` 是"可选依赖注入"的惯用写法：不传就用一个新的随机源，传了就可复现。**不要**写成 `rng=random.Random()` 作为默认值——默认值只在函数定义时求值一次，所有调用会共享同一个对象。

### 3.2 选出不重叠的 span

```python
    positions = list(range(n))
    rng.shuffle(positions)
    starts = []
    used = [False] * n
    span_lengths = []
    remaining = n_mask
    for _ in range(n_spans):
        if remaining <= 0:
            break
        random_order = list(range(n))
        rng.shuffle(random_order)
        chosen_start = None
        for start in random_order:
            if used[start]:
                continue
            length = max(1, int(rng.gauss(mean_span, 1.0)))
            length = min(length, remaining, n - start)
            if length < 1:
                continue
            if any(used[i] for i in range(start, start + length)):
                continue
            chosen_start = start
            for i in range(start, start + length):
                used[i] = True
            starts.append(start)
            span_lengths.append(length)
            remaining -= length
            break
        if chosen_start is None:
            break
```

做了什么：外层循环最多选 `n_spans` 个 span；每选一个，就把所有位置随机打乱，依次尝试作为起点，为它采样一个长度，检查"起点没被用、整个区间都没被用"，通过就把这些位置标记为 `used`。

- `used = [False] * n` 是**占用表**，用来保证 span 之间不重叠——如果重叠，同一个 token 会出现在两个 span 里，round trip 就无法定义。
- `length = min(length, remaining, n - start)`：不超过剩余预算，也不越过句尾。
- `any(used[i] for i in range(...))`：只要区间里有一个位置被占，就换下一个起点（并重新采样长度）。
- `for ... break` + `chosen_start is None` 检查：内层 `for` 找到一个就 `break`；如果所有起点都试过仍找不到，外层也提前结束。
- ⚠️ `positions` 被创建并 `shuffle`，但之后**从未使用**——属于残留代码。它还会消耗一次随机数，所以删掉它会改变同一种子下的输出。
- ⚠️ `if length < 1: continue` 实际上不会触发：`remaining > 0` 且 `n - start ≥ 1`，`length` 至少为 1。
- ⚠️ **实际遮盖率经常低于 `mask_rate`**：span 个数固定为 `n_spans`，长度又独立随机；`int()` 向零截断使平均长度约 2.5 而不是 3。演示句（25 个 token、目标遮 5 个）这次只遮了 3 个；用 2000 个种子统计平均约遮 4.4 个。T5 的官方实现是先固定总遮盖数，再随机切分成 `n_spans` 段，并保证 span 之间至少隔一个未遮 token。本代码允许两个 span **紧挨着**（source 中会出现两个连续哨兵），仍然可逆，但和官方行为不同。

### 3.3 组装 source 与 target

```python
    ordered = sorted(zip(starts, span_lengths), key=lambda x: x[0])

    source = []
    target = []
    prev_end = 0
    for idx, (start, length) in enumerate(ordered):
        source.extend(tokens[prev_end:start])
        source.append(sentinel(idx))
        target.append(sentinel(idx))
        target.extend(tokens[start:start + length])
        prev_end = start + length
    source.extend(tokens[prev_end:])
    target.append(sentinel(len(ordered)))  # closing sentinel
    return source, target
```

- **先按起点排序**：span 是随机顺序选出来的，但哨兵编号必须按**在句子中出现的先后**分配（`<extra_id_0>` 在最左边），这样 target 读起来和原文顺序一致。
- `prev_end` 是"上一个 span 结束的位置"，`tokens[prev_end:start]` 就是两个 span 之间未被遮的部分，原样拷贝进 source。这正是讲义说的"容易出 off-by-one 的 span 记账"：切片左闭右开，`start + length` 恰好是 span 之后的第一个下标。
- source 里每个 span 只占**一个**哨兵位置，所以 source 比原句短——encoder 看到的输入变短了。
- target 末尾追加 `sentinel(len(ordered))` 作为**收尾哨兵**，与 T5 官方格式一致：它标记最后一个 span 的结束，`round_trip` 依赖它把最后一段写进字典。

### 3.4 round trip：验证可逆

```python
def round_trip(source, target):
    spans = {}
    current_key = None
    current_span = []
    for tok in target:
        if tok.startswith("<extra_id_"):
            if current_key is not None:
                spans[current_key] = current_span
            current_key = tok
            current_span = []
        else:
            current_span.append(tok)
    out = []
    for tok in source:
        if tok.startswith("<extra_id_"):
            out.extend(spans.get(tok, []))
        else:
            out.append(tok)
    return out
```

- 第一段是一个小的**状态机解析器**：`current_key` 记录当前所属哨兵，遇到下一个哨兵时把上一段"提交"到 `spans`。收尾哨兵触发最后一次提交，它自己之后没有内容，循环结束时也不会被提交——这就是为什么收尾哨兵必不可少。
- 第二段遍历 source，把哨兵展开成对应 span，其余 token 原样输出。
- `spans.get(tok, [])`：哨兵在 target 里找不到时返回空列表而不是抛 `KeyError`——宽容的写法，但也可能掩盖 bug（例如 target 被截断时会"静默"丢内容）。
- ⚠️ 用 `startswith("<extra_id_")` 判断哨兵，前提是原文里不会出现这样的字符串。真实 tokenizer 把哨兵作为特殊 token id，不会与普通文本冲突。

### 3.5 BART：token masking 与 token deletion

```python
def token_mask(tokens, rate=0.15, rng=None, mask_token="<mask>"):
    if rng is None:
        rng = random.Random()
    return [mask_token if rng.random() < rate else t for t in tokens]


def token_delete(tokens, rate=0.15, rng=None):
    if rng is None:
        rng = random.Random()
    return [t for t in tokens if rng.random() >= rate]
```

- 两者都是每个 token 独立抛一次硬币：`rng.random() < rate` 时处理。
- **masking** 留下占位符，模型知道"哪里缺了"；**deletion** 不留痕迹，模型必须自己判断"哪里缺了"，难度更高。
- 两种写法分别用了推导式里的**条件表达式**（`A if cond else B`，长度不变）和**过滤**（末尾 `if`，长度变短）——正好对应"替换"和"删除"。

### 3.6 BART：text infilling

```python
def text_infill(tokens, rate=0.15, mean_span=3.0, rng=None, mask_token="<mask>"):
    """BART text infill: mask spans with a SINGLE mask; decoder infers length."""
    # ...
    out = []
    i = 0
    n = len(tokens)
    budget = int(n * rate)
    while i < n:
        if budget > 0 and rng.random() < 0.3:
            span_len = max(1, min(int(rng.gauss(mean_span, 1.0)), budget, n - i))
            out.append(mask_token)
            budget -= span_len
            i += span_len
        else:
            out.append(tokens[i])
            i += 1
    return out
```

- 用 `while` 手动推进下标 `i`：开始一个 span 时一次跳过 `span_len` 个 token，但只输出**一个** `<mask>`——这就是 docstring 说的"decoder 要推断长度"。
- `budget` 控制总遮盖量；`rng.random() < 0.3` 决定在当前位置是否开始一个 span，所以 span 倾向于出现在句子前部（预算先被用完）。
- ⚠️ 与 BART 论文的差异：论文中 span 长度服从 Poisson(λ=3) 分布，并允许长度为 0 的 span（相当于凭空插入一个 `<mask>`）；这里用截断的高斯分布，且长度至少为 1。

### 3.7 BART：句子打乱与文档旋转

```python
def sentence_permute(sentences, rng=None):
    # ...
    sents = list(sentences)
    rng.shuffle(sents)
    return sents


def document_rotate(tokens, rng=None):
    # ...
    if len(tokens) <= 1:
        return tokens
    pivot = rng.randrange(1, len(tokens))
    return tokens[pivot:] + tokens[:pivot]
```

- `list(sentences)` 先复制再 `shuffle`：`random.shuffle` 是**原地**操作，不复制就会改坏调用者的数据。
- `document_rotate`：随机选一个位置，把文档变成"从这里开始，绕回开头"。`randrange(1, len)` 排除了 0，保证一定发生旋转。模型需要学会识别文档真正的开头。
- 讲义提到 BART 论文中 **text infilling + sentence permutation** 组合效果最好；讲义 Build It 第 3 步说"组合其中两个并展示结果"，但 `main()` 实际只是**逐个**演示，没有做组合（见第 7 部分练习 3）。

### 3.8 `main()`：演示

```python
    rng = random.Random(42)
    sentence = (
        "the quick brown fox jumps over the lazy dog a stitch in time saves nine "
        "language models learn statistical patterns subword tokenization helps rare words"
    ).split()
    # ...
    source, target = corrupt_spans(sentence, mask_rate=0.20, mean_span=3.0, rng=rng)
    # ...
    reconstructed = round_trip(source, target)
    print("reconstruction matches original:",
          "YES" if reconstructed == sentence else "NO")
```

- 括号里两个相邻字符串字面量会被 Python **自动拼接**，然后 `.split()` 按空白切成 25 个 token。
- span corruption 用 `mask_rate=0.20`（比默认 0.15 高），让演示效果更明显。
- BART 部分只用前 14 个 token，并为每个噪声函数传一个**独立种子**的 `random.Random(k)`，所以每一行的结果互不影响、可单独复现。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| token 用字符串列表表示 | 打印出来一眼能看懂 | 真实流水线在 token id 上操作，哨兵是词表末尾的特殊 id |
| 用占用表 `used` + 随机试探选 span | 实现简单，天然保证不重叠 | 最坏 O(n²)；官方实现直接随机划分遮盖/非遮盖段长度，O(n) |
| span 个数先固定、长度后采样 | 代码直观 | 实际遮盖率偏低；官方先固定总数再切分 |
| 写 `round_trip` 做自检 | 低成本抓住切片下标错误 | 训练时不需要 |
| 每个函数接收 `rng` | 可复现、可单测 | 调用方要自己管理种子 |
| 高斯分布采样 span 长度 | 不需要额外库 | 论文用 Poisson（BART）/ 固定均值（T5） |
| 噪声函数逐个演示 | 便于对比每种噪声的效果 | 讲义建议的"组合两种噪声"需要自己补 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| f-string | `f"<extra_id_{i}>"` | 在字符串中嵌入变量 |
| 默认参数 + `None` 哨兵 | `rng=None` … `if rng is None: rng = random.Random()` | 避免把可变对象作为默认值（默认值只求值一次） |
| `round` 银行家舍入 | `int(round(n * mask_rate))` | `round(4.5) == 4`、`round(5.5) == 6` |
| 列表乘法 | `used = [False] * n` | 快速创建 n 个相同元素的列表（元素是不可变对象时安全） |
| `for ... break` + 标志变量 | `chosen_start = None` … `if chosen_start is None: break` | 判断内层循环是否找到了结果 |
| `any` + 生成器 | `any(used[i] for i in range(start, start + length))` | 只要有一个为真就返回 `True`，并且会短路 |
| 切片（左闭右开） | `tokens[prev_end:start]`、`tokens[start:start + length]` | `[a:b]` 取下标 a 到 b-1 |
| `list.extend` vs `append` | `source.extend(...)`、`source.append(sentinel(idx))` | `extend` 逐个加入可迭代对象的元素，`append` 把整体当一个元素加入 |
| `sorted` + `zip` + `lambda` | `sorted(zip(starts, span_lengths), key=lambda x: x[0])` | 把两个列表配对后按第一个元素排序 |
| `enumerate` + 嵌套解包 | `for idx, (start, length) in enumerate(ordered)` | 同时得到序号和元组内容 |
| 字典 `get` 默认值 | `spans.get(tok, [])` | key 不存在时返回默认值而不是抛 `KeyError` |
| `str.startswith` | `tok.startswith("<extra_id_")` | 前缀判断 |
| 条件表达式 / 过滤推导式 | `[mask_token if ... else t for t in tokens]`、`[t for t in tokens if ...]` | 前者逐元素替换，后者筛选 |
| `while` 手动推进下标 | `while i < n: ... i += span_len` | 需要"一次跳过多个元素"时比 `for` 更方便 |
| `random.Random` 方法 | `rng.shuffle`、`rng.gauss`、`rng.random`、`rng.randrange` | 原地打乱、高斯采样、[0,1) 均匀数、整数区间采样 |
| 相邻字符串字面量拼接 | `("the quick ... " "language models ...")` | 编译期自动拼接成一个字符串 |
| 条件表达式用于打印 | `"YES" if reconstructed == sentence else "NO"` | 列表可以直接用 `==` 逐元素比较 |

---

## 6. 运行结果解读

实际运行（Python 3.13）输出：

```text
=== T5 span corruption ===
corrupted source:
  the quick <extra_id_0> fox jumps over the lazy dog a <extra_id_1> time saves nine language models learn statistical patterns subword tokenization helps rare words

decoder target:
  <extra_id_0> brown <extra_id_1> stitch in <extra_id_2>

reconstruction matches original: YES
```

- 25 个 token、`mask_rate=0.20` → `n_mask = 5`、`n_spans = 2`。实际选中 `brown`（长度 1）和 `stitch in`（长度 2），只遮了 3 个——体现了 3.2 节说的"实际遮盖率偏低"。
- source 中两个哨兵按位置先后编号 0、1；target 是 `<extra_id_0> brown <extra_id_1> stitch in`，再加收尾哨兵 `<extra_id_2>`。格式与讲义示例 `<extra_id_0> brown <extra_id_1> over the lazy` 完全一致。
- `YES`：round trip 成功，说明切片下标没有 off-by-one。

```text
=== BART noise functions ===
original: the quick brown fox jumps over the lazy dog a stitch in time saves

token mask:     <mask> quick brown fox jumps over the lazy <mask> <mask> stitch in time <mask>
token delete:   the quick jumps over the lazy dog a stitch time saves
text infill:    <mask> brown fox <mask> the lazy dog a stitch in time saves
sentence permute:
  language models learn patterns
  a stitch in time
  the quick brown fox

document rotate: stitch in time saves the quick brown fox jumps over the lazy dog a
```

- **token mask**：14 个 token 中 4 个被换成 `<mask>`，长度不变。
- **token delete**：`brown`、`fox`、`in` 被删除，长度从 14 变 11，且没有任何"这里缺东西"的提示。
- **text infill**：`budget = int(14 × 0.3) = 4`；`the quick` 和 `jumps over` 两个 2-token span 各自只留下一个 `<mask>`——模型必须推断每个 `<mask>` 背后有几个词。
- **sentence permute**：三句话顺序被完全倒过来。
- **document rotate**：`pivot = 10`，文档从 `stitch` 开始，原开头 `the quick ...` 被转到了后面。

---

## 7. 动手改一改

1. **讲义练习 1**：构造一个 30 个 token 的句子，用默认参数跑 `corrupt_spans` 并验证 round trip；思考为什么只遮了一个 span（提示：`round(4.5)`）。
2. **统计实际遮盖率**：对 1000 个随机种子统计"实际遮盖 token 数 / n"，再把 `int(rng.gauss(...))` 改成 `round(...)`，观察均值的变化。
3. **组合噪声**：实现讲义 Build It 第 3 步——先 `sentence_permute` 再对每句做 `text_infill`，打印 BART 风格的 `(noisy_input, original)` 训练对。
4. **Poisson span**：把 `text_infill` 的长度分布改成 Poisson(λ=3)（可用"指数间隔计数"或 Knuth 算法自己实现），并允许长度 0 的 span（插入一个 `<mask>`）。
5. **禁止相邻 span**：修改 `corrupt_spans`，保证任意两个 span 之间至少隔一个未遮 token（与 T5 官方行为一致），并保持 round trip 通过。
6. **teacher forcing**：写 `make_decoder_io(target)`，返回右移一位的 decoder 输入和标签（见测验 Q11），再加上 EOS。

---

## 8. 常见坑

- **哨兵编号乱序**：span 按选中顺序编号而不是按位置排序，target 读起来顺序错乱，模型更难学。本代码用 `sorted(...)` 避免。
- **忘记收尾哨兵**：最后一个 span 无法从 target 中正确解析。
- **span 重叠**：同一 token 被遮两次，round trip 失败；需要占用表或区间检查。
- **切片 off-by-one**：`tokens[start:start + length]` 写成 `start + length - 1` 会少一个 token——这正是讲义建议做 round trip 自检的原因。
- **`random.shuffle` 原地修改**：直接 shuffle 调用者传入的列表会产生副作用，应先 `list(...)` 复制。
- **默认参数写成 `rng=random.Random()`**：所有调用共享同一个随机源，复现实验时很难排查。
