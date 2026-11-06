# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 28 节 长上下文 Evaluation — NIAH、RULER、LongBench、MRCR ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`random`、`re`），不调用任何真实模型，无需 API key

---

## 1. 这份代码在考察什么

这份代码不调用真实 LLM，而是用一个**"有硬性容量上限的假模型"**，把长上下文评测的**测试框架**完整搭起来：

1. **构造 haystack**：用随机词生成任意长度的填充文本，在指定深度插入针（needle）。
2. **深度 × 长度网格**：讲义 Step 1 的核心，扫描 5 个深度 × 5 个长度，打印成热力图表格。
3. **单针 vs 多针**：讲义 Step 2 的多针变体，要求一次找回 3 个事实。
4. **"有效容量"的概念**：mock 模型只能"看到"前 `effective_capacity` 个词，模拟"标称窗口 ≠ 可用窗口"。
5. **认识 mock 的边界**：硬截断只能产生单调的阶梯形热力图，无法模拟 lost in the middle 和渐进退化。看清这一点，就知道真实评测时要观察什么。

> 一句话：**评测 harness 和被测模型是解耦的**。把 `mock_retrieval_model` 换成真实的 `model.complete(...)`，网格、打分、报表全部可以原样复用。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `FILLER_WORDS` | 模块级列表 | 55 个词（去重后 45 个）的词表，用于生成填充文本 | haystack 的"干草" |
| `make_filler(n_tokens, seed)` | 函数 | 用固定种子随机抽词，生成 n 个词的填充文本 | 可复现的 haystack |
| `insert_needle(filler, needle, depth_ratio)` | 函数 | 在 `depth_ratio` 对应位置插入针 | 深度控制 |
| `mock_retrieval_model(context, question, effective_capacity)` | 函数 | 正则找针，只有针前词数 ≤ 容量时才"看得到" | 被测模型的替身 |
| `score_single_needle(...)` | 函数 | 调用 mock，答案包含期望词得 1 分 | 单针打分 |
| `score_multi_needle(...)` | 函数 | 统计容量内找到的针，返回命中比例 | 多针打分 |
| `run_niah_grid(lengths, depths, seed)` | 函数 | 扫网格并打印热力图表格 | NIAH 卡片 |
| `run_multi_needle(length, n_needles, seed)` | 函数 | 在 0.2 / 0.5 / 0.8 深度插 3 根针并打分 | 多针变体 |
| `main()` | 函数 | 跑网格 + 多针，打印说明 | 演示入口 |

调用关系：`main → run_niah_grid → make_filler / insert_needle / score_single_needle → mock_retrieval_model`；`main → run_multi_needle → make_filler / score_multi_needle`。

---

## 3. 逐段精讲

### 3.1 填充文本：`FILLER_WORDS` 与 `make_filler`

```python
FILLER_WORDS = (
    "the quick brown fox jumps over the lazy dog and then runs across the field "
    "where birds sing and flowers bloom while the river flows gently toward the sea "
    "and clouds drift slowly across a sky painted in hues of orange and pink "
    "as evening approaches and the day begins to fade into quiet darkness "
).split()


def make_filler(n_tokens, seed):
    rng = random.Random(seed)
    return " ".join(rng.choice(FILLER_WORDS) for _ in range(n_tokens))
```

- 括号里相邻的字符串字面量会被 Python 自动拼成一个长字符串，再用 `.split()` 切成词表。词表里 "the"、"and" 出现多次，`rng.choice` 抽到它们的概率也更高，这让填充文本的词频更接近自然文本。
- `random.Random(seed)` 创建一个**独立的随机数生成器**，不影响全局 `random` 状态；相同的 seed 生成相同的文本，保证评测**可复现**。
- 这里"token"其实是**词**。真实评测中长度应该按目标模型的 tokenizer 计数，英文 1 个词大约对应 1.3 个 token 左右，中文差别更大。
- 讲义提醒的 "lexical overlap with filler" 陷阱在这里被避开了：词表中没有 magic、word、is，填充文本不可能偶然拼出 "the magic word is"。
- ⚠️ 词表与针的主题毫不相干（自然风景 vs "magic word"），针在语义上非常显眼，比真实场景容易。讲义建议用领域文本做 haystack。

### 3.2 插针：`insert_needle`

```python
def insert_needle(filler, needle, depth_ratio):
    words = filler.split()
    pos = int(len(words) * depth_ratio)
    return " ".join(words[:pos] + [needle] + words[pos:])
```

- `depth_ratio=0` 插在最前面，`1.0` 插在最后，`0.5` 插在正中间。`int()` 向下取整。
- 针作为**一个列表元素**整体插入（虽然它本身有 5 个词），`join` 之后与普通词无异。
- 讲义 Step 1 的 `build_haystack` 版本更完整：会校验 `depth_ratio ∈ [0, 1]`、`total_tokens > 0`，并在填充不够长时重复填充。这里为了简短省略了校验。⚠️ 传入 `depth_ratio=1.5` 不会报错，针会被追加到末尾。

### 3.3 假模型：`mock_retrieval_model`

```python
def mock_retrieval_model(context, question, effective_capacity):
    needle_pattern = re.compile(r"(?:the magic word is|the secret code is|the pass phrase is|x1\s*=|x2\s*=|x3\s*=) [A-Z0-9a-z_]+", re.IGNORECASE)
    matches = list(needle_pattern.finditer(context))
    if not matches:
        return "no answer"
    total_len = len(context.split())
    for m in matches:
        before = len(context[:m.start()].split())
        if before <= effective_capacity:
            return m.group(0).split()[-1].strip(",.")
    return "no answer"
```

这是整份代码的"被测对象"，行为非常简单：

1. 用正则找出所有形如 "the magic word is XXX" 的句子（也预留了 "secret code"、"pass phrase" 和 `x1 = …` 这类变量赋值的模式，对应讲义 Step 3 的变量追踪，但 `main` 中没有用到）。
2. 对每个匹配，数一数它**前面有多少个词**（`context[:m.start()].split()`）。
3. 只要前面的词数 ≤ `effective_capacity`，就返回针的最后一个词（`split()[-1]`），并去掉可能粘在后面的逗号和句号。

设计含义：

- `effective_capacity` 模拟"模型实际能用的上下文"，超过这个位置的内容就像被截断了一样。这对应讲义开头的例子：合同的终止条款在 120k token 深处，模型根本"没看到"。
- ⚠️ **硬截断 + 单调**：能否找到只取决于针的绝对位置，所以热力图只会是"浅处全 1、深处出现 0"的阶梯形。真实 LLM 的退化是渐进的、概率性的，还有 lost in the middle 这种两端好、中间差的非单调形状。脚本的 notes 也承认了这一点。
- ⚠️ **完全不读 `question`**：遇到多根针时总是返回容量内的**第一根**。放一个干扰针 "the magic word is banana" 在真针前面，它就会答错（测验 Q9）。
- ⚠️ 纯字面匹配：换成 NoLiMa 风格的非字面针，它一根也找不到。
- 小瑕疵：`total_len` 计算了但没有使用。另外每个匹配都对前缀重新 `split()`，复杂度是 O(匹配数 × 文本长度)，对玩具数据无所谓。

### 3.4 打分：`score_single_needle` 与 `score_multi_needle`

```python
def score_single_needle(context, expected, effective_capacity):
    question = "What is the magic word?"
    answer = mock_retrieval_model(context, question, effective_capacity)
    return 1 if expected.lower() in answer.lower() else 0


def score_multi_needle(context, expected_list, effective_capacity):
    total_len = len(context.split())
    needle_pattern = re.compile(r"the magic word is ([A-Za-z0-9_]+)", re.IGNORECASE)
    found = []
    for m in needle_pattern.finditer(context):
        before = len(context[:m.start()].split())
        if before <= effective_capacity:
            found.append(m.group(1).lower())
    hits = sum(1 for e in expected_list if e.lower() in found)
    return hits / len(expected_list)
```

- 单针打分用**包含判断**（`expected in answer`）而不是完全相等。这与讲义 `score_niah` 一致：真实模型的回答往往是 "The magic word is pineapple." 这样的完整句子，包含判断更宽容。代价是可能误判，比如期望 "pine" 时 "pineapple" 也算对。
- 两边都 `.lower()`，大小写不敏感。
- 多针打分没有复用 mock，而是自己扫一遍：用捕获组 `([A-Za-z0-9_]+)` 直接取出针的值，统计容量内找到了哪些，再算期望列表的命中比例。返回值在 0–1 之间，是"部分得分"，讲义的多针问题 "What are the three magic words?" 也可以按这种方式给部分分。
- `e.lower() in found` 是对**列表**做成员判断，O(n)；针只有 3 根，无所谓。

### 3.5 网格：`run_niah_grid`

```python
def run_niah_grid(lengths, depths, seed=0):
    needle = "the magic word is pineapple"
    expected = "pineapple"
    capacity = 20000
    corner = "depth\\len"
    print(f"  {corner:<12}  " + "  ".join(f"{n:>6}" for n in lengths))
    for d in depths:
        row = []
        for n in lengths:
            filler = make_filler(n, seed=seed + n)
            haystack = insert_needle(filler, needle, d)
            row.append(score_single_needle(haystack, expected, capacity))
        tag = "  PASS" if all(row) else f"{sum(row)}/{len(row)}"
        print(f"  depth={d:<5}    " + "  ".join(f"{x:>6}" for x in row) + "    " + tag)
```

- 外层是深度（行），内层是长度（列），打印出来就是讲义说的 "NIAH card"。
- `seed=seed + n`：每个长度用不同的填充文本，但同一长度的不同深度共用同一份填充，只有针的位置不同，**控制变量**更干净。
- `corner = "depth\\len"` 单独放在变量里，是因为 Python 3.12 之前 **f-string 的花括号表达式里不能出现反斜杠**；`"\\"` 是转义后的一个反斜杠，打印出来是 `depth\len`。
- `all(row)` 判断整行是否全部通过；否则打印 "通过数/总数"。
- ⚠️ `capacity = 20000` 写死在函数里，不能从外部调整；讲义建议的深度是 0、0.25、0.5、0.75、1.0，这里用的是 0.1–0.9，两端各少测了一点。

### 3.6 多针：`run_multi_needle`

```python
def run_multi_needle(length, n_needles=3, seed=42):
    needles = ["the magic word is pineapple",
               "the magic word is compass",
               "the magic word is whisper"][:n_needles]
    expected = ["pineapple", "compass", "whisper"][:n_needles]
    filler = make_filler(length, seed=seed)
    depths = [0.2, 0.5, 0.8][:n_needles]
    words = filler.split()
    for d, n in sorted(zip(depths, needles), reverse=True):
        pos = int(len(words) * d)
        words = words[:pos] + [n] + words[pos:]
    haystack = " ".join(words)
    return score_multi_needle(haystack, expected, effective_capacity=length)
```

- `[:n_needles]` 切片让函数支持 1–3 根针。
- `sorted(zip(depths, needles), reverse=True)`：按深度**从深到浅**插入。先插深处的针，后插浅处的针时，浅处位置之前的内容没有被改动过，位置计算不受影响（反过来插也只会偏移一个元素，影响很小，但从深到浅更严谨）。
- ⚠️ `effective_capacity=length` 等于整个长度，所以 3 根针一定全部找到。这一段只演示了多针的**构造和打分形状**，没有体现"单针能过、多针过不了"的现象。要看到差异，可以把容量调小（比如 `length * 0.6`），浅处的针会找到，深处的会丢。
- ⚠️ `main` 中打印 `found {score * 3:.0f} / 3 needles`，把 3 写死了，与 `n_needles` 参数不联动。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 mock 模型代替真实 LLM | 无需 API key、0.3 秒跑完，专注于 harness 结构 | 无法体现渐进退化和 lost in the middle；生产中接真实模型，每格多次采样 |
| 硬容量截断 `before <= capacity` | 最直观地表达"标称 ≠ 可用" | 结果单调、边界敏感（`<=` 与 `<` 会改变格子结果） |
| 固定种子的随机填充 | 可复现，且同一长度不同深度共享填充，控制变量 | 填充与针主题差异大，针太显眼；生产中用领域文本做 haystack |
| 以"词"计长度 | 不依赖 tokenizer | 与模型真实 token 数有偏差；生产中按目标模型的 tokenizer 计数 |
| 包含判断打分 | 容忍完整句回答 | 可能误判；生产中可加规范化或用 judge |
| 多针按深度倒序插入 | 位置计算更严谨 | 容量设为全长，演示不出多针退化 |
| 深度 0.1–0.9 | 避开首尾两个极端 | 讲义建议包括 0 和 1.0，否则 lost in the middle 曲线的两端缺失 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 相邻字符串字面量自动拼接 | `("the quick ... " "where birds ...")` | 括号内多行字符串会拼成一个 |
| `str.split()` / `" ".join()` | `.split()`、`" ".join(words)` | 按空白切分 / 用空格拼接 |
| `random.Random(seed)` | `rng = random.Random(seed)` | 独立、可复现的随机数生成器 |
| `rng.choice` + 生成器表达式 | `" ".join(rng.choice(FILLER_WORDS) for _ in range(n_tokens))` | `_` 表示不使用的循环变量 |
| 列表切片与拼接 | `words[:pos] + [needle] + words[pos:]` | 在 pos 处插入一个元素（返回新列表） |
| `re.compile` + 标志位 | `re.compile(r"...", re.IGNORECASE)` | 预编译正则，忽略大小写 |
| 正则非捕获组 / 捕获组 | `(?:the magic word is|...)`、`([A-Za-z0-9_]+)` | 前者只分组，后者可用 `m.group(1)` 取出 |
| `\s*` | `x1\s*=` | 匹配零个或多个空白 |
| `finditer` 与 `list()` | `list(needle_pattern.finditer(context))` | 把迭代器一次性转成列表 |
| Match 对象 | `m.start()`、`m.group(0)`、`m.group(1)` | 匹配起点、整段匹配、第 1 个捕获组 |
| 链式字符串方法 | `m.group(0).split()[-1].strip(",.")` | 取最后一个词，再去掉首尾的逗号和句号 |
| 条件表达式 | `1 if expected.lower() in answer.lower() else 0` | 一行完成分支 |
| `all()` / `sum()` | `all(row)`、`sum(row)` | 全为真才为真；0/1 列表求和即通过数 |
| `zip` + `sorted(..., reverse=True)` | `sorted(zip(depths, needles), reverse=True)` | 配对后按第一个元素（深度）降序 |
| 默认参数 | `def run_multi_needle(length, n_needles=3, seed=42)` | 可选参数 |
| f-string 格式说明符 | `{n:>6}`、`{corner:<12}`、`{d:<5}`、`{score * 3:.0f}` | 右对齐 / 左对齐补宽；`.0f` 四舍五入为整数 |
| 字符串中的反斜杠转义 | `"depth\\len"` | `\\` 表示一个反斜杠；Python 3.12 前 f-string 表达式内不能写反斜杠，所以先放进变量 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`（约 0.3 秒），完整输出如下：

```text
=== toy NIAH grid (mock model with effective capacity = 20k) ===
marker: 1 = needle found in-context,  0 = needle missed

  depth\len        500    2000    8000   20000   40000
  depth=0.1           1       1       1       1       1      PASS
  depth=0.3           1       1       1       1       1      PASS
  depth=0.5           1       1       1       1       1      PASS
  depth=0.7           1       1       1       1       0    4/5
  depth=0.9           1       1       1       1       0    4/5

=== multi-needle at length=10000, n=3 ===
  found 3 / 3 needles

notes:
  mock model has hard effective-capacity cutoff; real LLMs degrade gradually.
  real NIAH: sweep 5 depths × 6 lengths, produce heatmap per model.
  always pair with one multi-hop / aggregation task (RULER) — single-needle is saturable.
```

逐行解读：

- **前 4 列全是 1**：长度 ≤ 20000 时，针前面的词数最多 0.9 × 20000 = 18000，都在容量内。
- **40000 这一列**：深度 0.1 / 0.3 / 0.5 对应针前 4000 / 12000 / 20000 词，都 ≤ 20000，所以通过；0.7 / 0.9 对应 28000 / 36000 词，超出容量，失败。
- **depth=0.5, len=40000 恰好踩在边界上**：针前正好 20000 词，因为判断条件是 `<=` 才通过。把容量改成 19999，这一格就变成 0（已实际验证）。评测代码中的边界条件会直接改变结论，必须写清楚。
- **热力图的形状**：失败只出现在右下角，呈阶梯形。这是硬截断的特征。真实模型的热力图往往在中间深度、长长度处先出现"浅色"格子（lost in the middle），而且是逐渐变浅的。
- **用本节方法计算有效检索长度（90%）**：20000 这一列 5/5 通过，40000 这一列只有 3/5 = 60%，所以有效检索长度是 20000，正好等于设定的容量。真实模型的这个数字需要实测得出。
- **多针 3/3**：容量等于全长，所以全部找到。它只验证了多针构造和打分是对的，还没有体现讲义说的"单针成功不预示多针成功"。

---

## 7. 动手改一改

1. **补齐深度**：把 `depths` 改成 `[0, 0.25, 0.5, 0.75, 1.0]`，并把 `capacity` 改成函数参数，分别用 20000 和 19999 跑一次，观察边界格子的变化。
2. **模拟 lost in the middle**：给 mock 增加规则，长度大于某个值时，相对深度在 0.3–0.7 之间的针以一定概率（固定种子）找不到，画出 U 形曲线。
3. **干扰针**：在真针之前插入 "the magic word is banana"，观察单针得分变成 0；再把 mock 改成"按问题中的 key 匹配"，让它通过。
4. **多针退化**：把 `run_multi_needle` 的容量改成 `int(length * 0.6)`，打印找到了哪几根针，对比同长度下的单针结果。
5. **变量追踪（RULER 风格）**：在填充文本的 0.2 / 0.5 / 0.8 处分别插入 `X1 = 42.`、`X2 = X1 + 10.`、`X3 = X2 * 2.`，写一个只解析容量内赋值并逐步计算的 mock，期望答案 `X3 = 104`。
6. **接入真实模型**（需要 API key）：按讲义 `score_niah` 的写法，把 mock 换成真实调用，在 1k / 4k / 16k 长度上跑 3 × 3 网格，同时记录每次调用的首 token 延迟。

---

## 8. 常见坑

- **只测一个深度或避开两端**：lost in the middle 需要完整的深度曲线才能看出来；讲义要求 0 到 1.0 共 5 个深度。
- **用词数冒充 token 数**：同样 "20000 长度"，不同 tokenizer 下的 token 数可能差 30% 以上，跨模型比较时必须统一口径。
- **边界条件**：`<=` 与 `<` 能改变网格里的格子；阈值和边界要在报告中写明。
- **针太显眼**：填充文本与针主题差异太大，或者针与问题有字面重叠，测出来的是"关键词搜索能力"。用领域文本、非字面针和干扰针来加难。
- **把 mock 的结论当真**：这里的 20000 是人为设定的容量，热力图只是展示 harness 的形状；真实模型的有效长度必须实测，而且不能直接采信厂商自报的分数。
- **只看单针**：单针饱和不代表多针、多跳也行；至少再配一个推理类任务。
