# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 06 节 BERT——掩码语言建模 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`random`、`collections.Counter`）

---

## 1. 这份代码在考察什么

BERT 的模型结构就是第 05 节的 encoder，真正让它与众不同的是**训练数据怎么构造**。这份代码不建模型，只把 MLM（Masked Language Modeling，掩码语言建模）的"出题规则"讲透：

1. **15% 选择 + 80/10/10 替换**：哪些位置要预测、输入里把它们变成什么。
2. **`labels` 与 `-100`**：只有被选中的位置有标签，其余位置用 PyTorch 的 `ignore_index` 约定忽略。
3. **特殊 token 保护**：`[CLS]`、`[SEP]`、`[MASK]` 本身永远不会被选中。
4. **Whole-word masking**：一个词的多个 subword 要么一起遮、要么都不遮。
5. **统计验证**：用 10 万个 token 检查实际比例是否接近 15% / 80% / 10% / 10%——写数据管道时必须养成的习惯。

> 一句话：**模型学到什么，取决于你出什么题。这份代码就是 BERT 的"出题器"，并附带一个检查出题比例的单元测试。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MASK_ID / CLS_ID / SEP_ID / SPECIAL_IDS / IGNORE_INDEX` | 模块级常量 | 特殊 token 的 id、忽略标签 -100 | 词表约定、`ignore_index` |
| `create_mlm_batch(tokens, vocab_size, mask_prob=0.15, rng=None)` | 函数 | 逐 token 选择并按 80/10/10 替换，返回 `(input_ids, labels)` | MLM 掩码 |
| `whole_word_mlm(tokens, word_spans, vocab_size, ...)` | 函数 | 以"词"为单位选择与替换 | Whole-word masking |
| `distribution_check(n_tokens, vocab_size, ...)` | 函数 | 对随机 token 序列掩码，统计各类比例 | 数据管道的统计校验 |
| `toy_predict(masked_inputs, vocab)` | 函数 | 返回均匀分布的"假 MLM 头"（本文件中未被调用） | MLM 预测头的占位 |
| `main()` | 函数 | 三个演示：单句掩码、10 万 token 统计、整词掩码 | 演示入口 |

数据流：词 → `id_of` 映射成 id → `create_mlm_batch` / `whole_word_mlm` → `(input_ids, labels)` → 打印；`distribution_check` 内部自行生成随机 token 并统计。

---

## 3. 逐段精讲

### 3.1 常量：特殊 token 与忽略标签

```python
MASK_ID = 0  # reserve id 0 for [MASK] in this toy vocab
CLS_ID = 1
SEP_ID = 2
SPECIAL_IDS = {MASK_ID, CLS_ID, SEP_ID}
IGNORE_INDEX = -100
```

- 玩具词表中 id 0/1/2 留给特殊 token（与 `main()` 里 `vocab_words` 的前三项对应）。真实 BERT 的 `[MASK]`、`[CLS]`、`[SEP]` 有各自的 id（如 bert-base-uncased 中分别为 103、101、102），这里只是约定不同。
- `SPECIAL_IDS` 用**集合**存储，`t in SPECIAL_IDS` 是 O(1) 查找。
- `IGNORE_INDEX = -100`：PyTorch `nn.CrossEntropyLoss` 的 `ignore_index` 默认就是 -100。label 为 -100 的位置既不贡献 loss，也不计入平均的分母。HuggingFace 的数据整理器沿用了这个约定。
- 全大写的模块级变量是 Python 约定俗成的"常量"写法（语言本身不强制只读）。

### 3.2 `create_mlm_batch`：15% 选择 + 80/10/10

```python
def create_mlm_batch(tokens, vocab_size, mask_prob=0.15, rng=None):
    if rng is None:
        rng = random.Random()
    input_ids = list(tokens)
    labels = [IGNORE_INDEX] * len(tokens)
    for i, t in enumerate(tokens):
        if t in SPECIAL_IDS:
            continue
        if rng.random() >= mask_prob:
            continue
        labels[i] = t
        r = rng.random()
        if r < 0.8:
            input_ids[i] = MASK_ID
        elif r < 0.9:
            rand_id = t
            while rand_id in SPECIAL_IDS or rand_id == t:
                rand_id = rng.randrange(vocab_size)
            input_ids[i] = rand_id
    return input_ids, labels
```

逐步拆解：

1. **`rng=None` 默认值**：不传随机数生成器就新建一个（每次结果不同）；传入 `random.Random(42)` 则可复现。用 `None` 做哨兵而不是 `rng=random.Random()`，是为了避免**可变默认参数陷阱**——默认值只在函数定义时求值一次，会被所有调用共享。
2. **`input_ids = list(tokens)`**：复制输入，后续修改不影响调用方的原列表。
3. **`labels` 初始化为全 -100**：默认所有位置都不参与 loss。
4. **跳过特殊 token**：`[CLS]`、`[SEP]` 是结构标记，让模型预测它们没有意义。
5. **两次 `continue` 的"卫语句"写法**：先排除不需要处理的情况，主逻辑不必层层缩进。
6. **先写 label、后替换**：只要被选中，`labels[i] = t` 就记下原 token——所以 80% / 10% / 10% 三种情况**都**有 label，包括"保持不变"的那 10%。
7. **80/10/10 用一个随机数分段**：`r < 0.8` → `[MASK]`；`0.8 ≤ r < 0.9` → 随机 token；`r ≥ 0.9` → 什么都不做（保持原样）。用一个均匀随机数加分段阈值实现离散分布，是很常见的写法。
8. **随机替换的 `while` 循环**：
   - `rand_id = t` 让初始值必然满足循环条件，相当于 Python 中的 "do-while"；
   - 循环保证随机 token **既不是特殊 token，也不等于原 token**；
   - 与原始 BERT 的差别：原始实现从整个词表均匀抽取，可能恰好抽到原 token。这里的写法让"随机"这一类更"纯"，统计比例严格对应 80/10/10。

为什么要 80/10/10 而不是全部 `[MASK]`：`[MASK]` 在微调和推理时不会出现。如果训练时只要求模型在 `[MASK]` 处输出原词，模型就可以只在 `[MASK]` 位置"认真工作"；10% 不变和 10% 随机迫使它对**每个**位置都维持好的上下文表示（讲义："keeps the model honest"）。

⚠️ **边界 bug**：如果词表中除特殊 token 外**只有一个**普通 token（如 `vocab_size = 4`），走到随机分支时找不到合法的替代值，`while` 永远不会结束（已用 5 秒超时验证）。真实词表不会触发，但在单元测试中用小词表时要小心。修复方法见测验 Q8(c)。

⚠️ **简化**：真实实现（如 HuggingFace `DataCollatorForLanguageModeling`）是在整个 batch 张量上**向量化**地做伯努利采样，而不是逐 token 循环；并且会额外跳过 padding 位置。

### 3.3 `whole_word_mlm`：以词为单位

```python
def whole_word_mlm(tokens, word_spans, vocab_size, mask_prob=0.15, rng=None):
    # ...
    for start, end in word_spans:
        if any(tokens[i] in SPECIAL_IDS for i in range(start, end)):
            continue
        if rng.random() >= mask_prob:
            continue
        r = rng.random()
        if r < 0.8:
            for i in range(start, end):
                labels[i] = tokens[i]
                input_ids[i] = MASK_ID
        elif r < 0.9:
            for i in range(start, end):
                labels[i] = tokens[i]
                rand_id = tokens[i]
                while rand_id in SPECIAL_IDS or rand_id == tokens[i]:
                    rand_id = rng.randrange(vocab_size)
                input_ids[i] = rand_id
        else:
            for i in range(start, end):
                labels[i] = tokens[i]
    return input_ids, labels
```

- **`word_spans`**：一组左闭右开区间 `(start, end)`，每个区间是一个"词"包含的 subword 位置。例如 `(2, 4)` 表示位置 2、3（"quick"、"brown"）属于同一个词。
- **为什么要整词遮**：如果 "playing" 被切成 `play` + `##ing`，只遮 `##ing` 时模型看到 `play` 就能轻松猜出答案，学不到真正的上下文推理。整词遮盖迫使模型依靠句子其他部分来预测。
- **决策粒度**：每个词只抽一次随机数，决定"选不选"和"怎么替换"，然后作用到该词的所有 subword 上——同一个词要么全变 `[MASK]`、要么全部随机、要么全部保持（但都有 label）。
- `any(...)` 跳过包含特殊 token 的区间（这里就是 `[CLS]`、`[SEP]` 两个单 token 区间）。
- ⚠️ `mask_prob` 是**按词**的概率，不是按 token 的：长词（subword 多）被选中时会一次贡献多个预测位置，因此被选中的 token 比例与 15% 并不严格一致。真实实现（如 HF 的整词掩码整理器）通常按"token 预算"挑选词，直到达到约 15% 的 token。
- ⚠️ 随机分支中每个 subword 独立抽随机 token，并沿用了与 3.2 相同的 `while` 循环（同样的边界 bug）。

### 3.4 `distribution_check`：给数据管道写单元测试

```python
def distribution_check(n_tokens, vocab_size, mask_prob=0.15, seed=42):
    rng = random.Random(seed)
    tokens = [rng.randrange(3, vocab_size) for _ in range(n_tokens)]
    input_ids, labels = create_mlm_batch(tokens, vocab_size, mask_prob, rng)

    selected = sum(1 for l in labels if l != IGNORE_INDEX)
    masked = sum(1 for t, l in zip(input_ids, labels) if l != IGNORE_INDEX and t == MASK_ID)
    randomized = sum(1 for t, l in zip(input_ids, labels) if l != IGNORE_INDEX and t != MASK_ID and t != l)
    unchanged = sum(1 for t, l in zip(input_ids, labels) if l != IGNORE_INDEX and t == l)

    return {
        "tokens": n_tokens,
        "selected": selected,
        "selected_pct": 100 * selected / n_tokens,
        "masked_of_selected_pct": 100 * masked / selected if selected else 0.0,
        # ...
    }
```

- `rng.randrange(3, vocab_size)` 只生成普通 token（3–19），避开特殊 id。
- **用 `(input_ids, labels)` 反推每个位置属于哪一类**：
  - `l != -100` → 被选中；
  - 被选中且输入是 `MASK_ID` → `[MASK]` 类；
  - 被选中、输入不是 `MASK_ID` 且与原 token 不同 → 随机类（成立的前提是随机替换不会等于原 token，见 3.2）；
  - 被选中且输入等于原 token → 不变类。
- `sum(1 for ... if ...)` 是"计数满足条件的元素"的惯用写法。
- `100 * masked / selected if selected else 0.0`：条件表达式防止 `selected == 0` 时除零。注意运算优先级：整个 `100 * masked / selected` 是条件表达式的"真"分支。
- 返回 `dict`，调用方用 `stats['selected_pct']` 按名字取值，比返回元组更不容易取错位置。
- **为什么用 10 万个 token**：比例估计的标准误差约为 `√(p(1−p)/n)`。n = 10 万、p = 0.15 时约 0.11 个百分点，足以让 15.03% 这样的结果"可信地接近 15%"。

### 3.5 `toy_predict`：占位的 MLM 头

```python
def toy_predict(masked_inputs, vocab):
    """Pretend MLM head: returns a uniform distribution over vocab.
    Real BERT uses the encoder output at each position, projected to vocab.
    """
    V = len(vocab)
    return [[1.0 / V for _ in range(V)] for _ in masked_inputs]
```

- 对每个位置返回一个长度为 V 的均匀分布。真实 BERT 的 MLM 头是：encoder 输出 → 变换层 → 投影到词表维度（通常与输入 embedding 共享权重）→ softmax。
- 均匀分布下的交叉熵是 `ln V`（本例 `ln 20 ≈ 2.996`），这是"什么都没学到"的 loss 基线，用来检查训练初期的 loss 是否合理（测验 Q10）。
- ⚠️ 这个函数在 `main()` 中**没有被调用**。讲义 Build It 的 Step 2–4（训练 2 层 encoder + MLM 头、比较不同掩码类型下的预测、换成分类头微调）在代码中都没有实现，代码只覆盖了 Step 1 的掩码逻辑以及整词掩码和统计校验。
- ⚠️ 文件导入了 `Counter` 但没有使用。

### 3.6 `main()`：三个演示

```python
    vocab_size = len(vocab_words)
    id_of = {w: i for i, w in enumerate(vocab_words)}

    sentence = ["[CLS]", "the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog", "[SEP]"]
    tokens = [id_of[w] for w in sentence]
    rng = random.Random(42)
    inp, labels = create_mlm_batch(tokens, vocab_size, mask_prob=0.5, rng=rng)
```

- **字典推导式** `{w: i for i, w in enumerate(vocab_words)}` 建立"词 → id"映射；反向查找直接用列表下标 `vocab_words[id]`。
- 演示 1 用 `mask_prob=0.5`（而不是 0.15），只是为了在一个短句里看到足够多的遮盖。
- 演示 3 把 `"quick brown"`、`"lazy dog"` 假装成"由两个 subword 组成的词"，用 `spans` 描述。
- 打印时用 `zip(inp, tokens, labels)` 三路并行遍历，配合 `enumerate` 得到下标。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 逐 token 循环 | 规则一目了然 | 生产中在 batch 张量上向量化采样（`torch.bernoulli` 等） |
| 随机替换排除原 token 与特殊 token | "随机"类别更纯，统计可以精确对上 10% | 与原始 BERT 略有差异；极小词表会死循环 |
| 先写 label 再决定替换方式 | 三种情况都有 label，符合 BERT 定义 | — |
| `IGNORE_INDEX = -100` | 与 PyTorch / HF 约定一致，可直接接 `CrossEntropyLoss` | — |
| 整词掩码按"词"抽概率 | 实现最简单 | token 级比例不再严格是 15%；生产中按 token 预算选词 |
| 用 10 万 token 做统计检查 | 让抽样误差足够小 | 真实管道还应检查 padding、截断、特殊 token 是否被误遮 |
| 不实现模型和训练 | 本节聚焦"数据构造"；讲义："Full training needs PyTorch" | 讲义的 Step 2–4 需要自行补充 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `MASK_ID = 0`、`IGNORE_INDEX = -100` | 全大写命名表示"不应修改" |
| 集合字面量与成员判断 | `SPECIAL_IDS = {MASK_ID, CLS_ID, SEP_ID}`；`t in SPECIAL_IDS` | 集合查找为 O(1) |
| `from ... import ...` | `from collections import Counter` | 导入模块中的名字（本文件导入后未使用） |
| `None` 默认值哨兵 | `rng=None` … `if rng is None: rng = random.Random()` | 避免可变默认参数陷阱 |
| 列表复制与乘法 | `list(tokens)`、`[IGNORE_INDEX] * len(tokens)` | 复制列表；创建重复元素列表 |
| `enumerate` | `for i, t in enumerate(tokens)` | 同时拿下标和值 |
| `continue` 卫语句 | `if t in SPECIAL_IDS: continue` | 提前跳过，减少嵌套 |
| `if / elif` 分段 | `if r < 0.8: ... elif r < 0.9: ...` | 用阈值把 [0,1) 分成三段 |
| 模拟 do-while | `rand_id = t` + `while rand_id in SPECIAL_IDS or rand_id == t:` | 先让条件为真，保证至少执行一次 |
| `random.Random` 方法 | `rng.random()`、`rng.randrange(vocab_size)`、`rng.randrange(3, vocab_size)` | [0,1) 浮点；`[0, n)` 或 `[a, b)` 的整数 |
| 元组解包遍历 | `for start, end in word_spans` | 区间的两端直接拆开 |
| `any` + 生成器 | `any(tokens[i] in SPECIAL_IDS for i in range(start, end))` | 有一个为真就返回 True，并短路 |
| 条件计数 | `sum(1 for l in labels if l != IGNORE_INDEX)` | 统计满足条件的元素个数 |
| 三路 `zip` | `zip(inp, tokens, labels)` | 同时遍历三个列表 |
| 条件表达式 | `100 * masked / selected if selected else 0.0` | 防止除零 |
| 字典字面量与取值 | `return {"tokens": ..., ...}`；`stats['selected_pct']` | 按名字组织返回结果 |
| 字典推导式 | `{w: i for i, w in enumerate(vocab_words)}` | 构造词到 id 的映射 |
| 列表推导式（双层） | `[[1.0 / V for _ in range(V)] for _ in masked_inputs]` | 生成二维列表 |
| 数字分隔符 | `n_tokens=100_000` | 仅为可读 |
| f-string 格式符 | `f"{i:>4}"`、`f"{stats['selected_pct']:.2f}%"`、`f"[{s}:{e}]"` | 对齐、保留两位小数、拼接 |
| 条件表达式生成字符 | `("P" if l != IGNORE_INDEX else ".")` | 把标签状态变成可视化字符 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py` 的完整输出：

```text
=== MLM masking demo (prob=0.5 so you can see it) ===
 idx       word   input_id   input_word   label
   0      [CLS]          1        [CLS]    -100
   1        the          3          the    -100
   2      quick          0       [MASK]       4
   3      brown          0       [MASK]       5
   4        fox          6          fox    -100
   5      jumps          7        jumps    -100
   6       over          0       [MASK]       8
   7        the          0       [MASK]       3
   8       lazy          9         lazy    -100
   9        dog          0       [MASK]      10
  10      [SEP]          2        [SEP]    -100
```

- `[CLS]`（idx 0）和 `[SEP]`（idx 10）label 为 -100：特殊 token 被跳过。
- 5 个位置被选中（idx 2、3、6、7、9），label 是原 token 的 id；这 5 个恰好都落在 80% 的 `[MASK]` 分支。
- 未被选中的位置输入不变、label 为 -100，不参与 loss。
- 9 个普通 token 选中 5 个，与 `mask_prob = 0.5` 的期望 4.5 吻合。注意 idx 7 的 "the" 被遮了但 idx 1 的 "the" 没有——选择是逐位置独立进行的。

```text
=== 80/10/10 distribution over 100k random tokens ===
selected:                   15.03%   (target 15.0%)
  -> replaced with [MASK]:  79.80%   (target 80.0%)
  -> replaced with random:  10.15%   (target 10.0%)
  -> left unchanged:        10.04%   (target 10.0%)
```

- 选中比例 15.03%，偏差约 0.3 个标准误差（标准误差约 0.11 个百分点），完全正常。
- 被选中的约 15,000 个位置中，三类比例都在目标值附近，偏差在抽样误差范围内。这正是讲义练习 1 要求验证的内容。

```text
=== whole-word masking demo ===
spans:        [0:1] [1:2] [2:4] [4:5] [5:6] [6:7] [7:8] [8:10] [10:11]
input words:  [CLS] [MASK] quick brown [MASK] [MASK] over [MASK] [MASK] [MASK] [SEP]
label mask:   . P . . P P . P P P .
P = position has a label, . = ignored
```

- `[2:4]`（quick brown）没被选中：两个 subword 都保持原样、都没有 label——"要么都不"。
- `[8:10]`（lazy dog）被选中且走 `[MASK]` 分支：两个位置**同时**变成 `[MASK]`、同时有 label——"要么一起"。
- 单 token 的词（the、fox、jumps、the）各自独立决定。
- 首尾的 `[CLS]`、`[SEP]` 区间被 `any(...)` 跳过。

---

## 7. 动手改一改

1. **讲义练习 1**：把 `distribution_check` 的 `n_tokens` 改成 10,000，运行多次（换不同 `seed`），观察比例的波动幅度，并与 `√(p(1−p)/n)` 的估计对比。
2. **修复死循环**：把随机替换改为"从候选列表中 `rng.choice`"，当候选为空时退化为保持不变；写一个 `vocab_size = 4` 的测试确认能正常返回。
3. **复现原始 BERT 的随机替换**：允许随机 token 等于原 token，重新统计，验证"random"降到约 9.4%、"unchanged"升到约 10.6%（测验 Q9(c)）。
4. **写 MLM loss**：实现 `mlm_cross_entropy(probs, labels)`，配合 `toy_predict` 验证均匀分布下 loss 等于 `ln 20 ≈ 2.996`。
5. **按 token 预算的整词掩码**：改写 `whole_word_mlm`，先打乱词的顺序，依次选词直到被选中的 token 数达到 `round(0.15 × 总 token 数)`，再按 80/10/10 处理每个选中的词。
6. **进阶**：加入 padding（例如 id 3 表示 `[PAD]`），确保它既不会被选中、也不会被当成随机替换的目标。

---

## 8. 常见坑

- **忘记跳过特殊 token / padding**：模型会浪费容量去预测 `[CLS]`、`[PAD]`。
- **"保持不变"的位置没写 label**：那 10% 就失去了意义，模型又回到"只在 `[MASK]` 处工作"。
- **用 0 代替 -100 作为忽略标签**：0 可能是合法的 token id（本例中就是 `[MASK]`），会被当成真实目标计算 loss。
- **loss 平均时分母算错**：应只除以有效位置数；把 -100 位置也算进分母会让 loss 偏小。
- **可变默认参数**：写成 `rng=random.Random()` 会让所有调用共享同一个生成器对象，且行为难以复现。
- **极小词表下的随机替换死循环**：单元测试中常见，真实词表不会触发。
