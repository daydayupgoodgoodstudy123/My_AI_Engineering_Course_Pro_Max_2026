# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 25 节 实体链接和消歧 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`；`collections.Counter` 被导入但没有使用）

---

## 1. 这份代码在考察什么

这是一个**玩具版的"先验 + 上下文"实体链接器**（Milne & Witten 思路的极简实现），用 5 个歧义别名、14 个实体、11 个测试句子，把实体链接的两步流水线完整走一遍：

1. **候选生成**：用别名索引 `ALIAS_INDEX` 把表面形式 "Jordan" 映射成 4 个候选 KB id。
2. **上下文消歧**：用上下文与实体描述的 **Jaccard 词重叠**给候选打分。
3. **先验的作用**：`PRIORS` 近似 `P(entity | mention)`，演示"上下文证据弱时由先验兜底"，以及先验权重过大时的流行度偏置。
4. **评估意识**：同一个测试集分别跑"有先验 / 无先验"两次，用准确率做消融对比。
5. **认识 baseline 的局限**：词袋 Jaccard 没有词形还原、没有停用词过滤、偏向描述短的实体，这正是讲义说"Jaccard 只是玩具，要换成 embedding"的原因。

> 一句话：**先用 100 行代码看清"候选 → 打分 → 选最大"的骨架**，再把打分函数换成 BLINK 式的 embedding，或换成受约束的 LLM，骨架完全不变。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ALIAS_INDEX` | 模块级字典 | 小写别名 → 候选实体 id 列表 | 别名索引 / 候选生成 |
| `KB_DESC` | 模块级字典 | 实体 id → 一句话描述（关键词串） | 知识库中的实体描述 |
| `PRIORS` | 模块级字典 | 实体 id → 先验概率（同一别名下的候选之和为 1） | `P(entity | mention)`，流行度先验 |
| `tokenize(text)` | 函数 | 小写 + 正则切词，返回**集合** | 词袋表示 |
| `disambiguate(mention, context, use_prior)` | 函数 | 查候选 → 算 Jaccard → 叠加先验 → 返回最高分 | 消歧 |
| `run_eval(test_cases, use_prior)` | 函数 | 逐条预测、打印 OK/MISS、汇总准确率 | top-1 准确率评估 |
| `main()` | 函数 | 定义 11 个带 gold 的测试用例，分别跑有/无先验 | 消融实验 |

数据流：`main → run_eval → disambiguate → tokenize`；三张表是全局只读数据，相当于一个"迷你 Wikidata"。

---

## 3. 逐段精讲

### 3.1 三张表：一个迷你知识库

```python
ALIAS_INDEX = {
    "jordan": ["Q41421", "Q810", "Q254110", "Q3308285"],
    "paris":  ["Q90", "Q663094", "Q55411"],
    "apple":  ["Q312", "Q89"],
    "washington": ["Q23", "Q1223", "Q61"],
    "python": ["Q28865", "Q83320"],
}

KB_DESC = {
    "Q41421":  "Michael Jordan American basketball player Chicago Bulls six championships",
    "Q810":    "Jordan country Middle East kingdom capital Amman Arabic",
    # ...
}

PRIORS = {
    "Q41421":  0.50, "Q810":    0.20, "Q254110": 0.20, "Q3308285": 0.10,
    "Q90":     0.85, "Q663094": 0.05, "Q55411":  0.10,
    # ...
}
```

- **`ALIAS_INDEX` = 候选生成器**。键统一小写，查询时也 `mention.lower()`，实现大小写不敏感匹配。真实系统的别名表来自 Wikipedia 重定向、消歧页和锚文本，约 1800 万条；结构完全一样，只是存成倒排索引或 KV 库。
- **`KB_DESC` = 实体的"文本画像"**。这里刻意写成关键词串（没有虚词），让 Jaccard 能看出效果。BLINK 一类系统用的正是实体的 Wikipedia 首段描述。
- **`PRIORS` = 先验**。仔细看会发现：同一别名下的先验加起来正好是 1（jordan：0.5+0.2+0.2+0.1；paris：0.85+0.05+0.10）。也就是说它是一个条件分布 `P(e | m)`，真实系统中由"锚文本 m 链向实体 e 的次数 / 锚文本 m 出现总次数"统计得到，也叫 commonness。
- ⚠️ 实体 id 采用 Wikidata QID 的格式，只是为了演示；`washington` 的 3 个候选在 `main()` 的测试集里没有用到。

### 3.2 `tokenize`：最朴素的词袋

```python
def tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))
```

- 先 `lower()`，再用正则 `[a-z0-9]+` 抓出所有连续的字母或数字串，标点和空格都被当作分隔符丢掉。
- 返回 **`set`**，后面直接用 `&`（交集）、`|`（并集）算 Jaccard，词频信息被丢弃。
- 几个副作用值得注意：
  - `"Jordan's"` 会被切成 `jordan` 和 `s` 两个词；
  - 没有词形还原：上下文里的 `arabia` 和描述里的 `arabic` 不算重叠；
  - 没有停用词过滤：`"capital of France"` 里的 `of` 也会算进交集；
  - 正则只认 ASCII 字母，中文等非拉丁文字会被整体丢掉，这也是讲义提到的跨语言 EL 需要另行处理的原因之一。
- ⚠️ 这些都是刻意的简化。第 01 节的分词、词形还原，第 02 节的 TF-IDF，都可以直接拿来改进这一步。

### 3.3 `disambiguate`：候选 → 打分 → 选最大

```python
def disambiguate(mention, context, use_prior=True):
    candidates = ALIAS_INDEX.get(mention.lower(), [])
    if not candidates:
        return None, 0.0
    ctx_tokens = tokenize(context)
    scored = []
    for cand in candidates:
        desc_tokens = tokenize(KB_DESC.get(cand, ""))
        if not desc_tokens:
            jac = 0.0
        else:
            overlap = len(ctx_tokens & desc_tokens)
            union = len(ctx_tokens | desc_tokens)
            jac = overlap / union if union else 0.0
        prior = PRIORS.get(cand, 0.0) if use_prior else 1.0
        score = jac + 0.1 * prior
        scored.append((cand, score, jac, prior))
    scored.sort(key=lambda x: -x[1])
    return scored[0][0], scored[0][1]
```

逐行拆解：

1. **候选生成**：`ALIAS_INDEX.get(..., [])` 查不到就返回空列表，函数返回 `(None, 0.0)`。这是唯一一种"NIL"情况。⚠️ 只要别名在表里，哪怕上下文和所有候选都不沾边，函数也一定会返回某个实体，**没有基于分数的 NIL 判定**。
2. **上下文表示**：整句话 tokenize 一次，放在循环外，避免每个候选重复计算。
3. **Jaccard 相似度**：`|A∩B| / |A∪B|`，取值范围 [0, 1]。两层防御：描述为空时直接给 0（`KB_DESC.get(cand, "")` 保证 KB 缺描述时不会抛 `KeyError`），并集为 0 时也不会除零。
4. **先验与组合方式**：`score = jac + 0.1 * prior`。
   - 讲义写的 Milne-Witten 公式是**乘法** `P(e | m) × 相似度`，代码用的是**加法 + 小权重 0.1**。加法下先验最多贡献 0.085（Paris 0.85×0.1），只在上下文证据接近时起"打破平局"的作用；乘法下先验会被放大（0.85 对 0.05 相差 17 倍），冷门实体很难翻身。我在本地用同样数据试过：改成乘法后只有 7/11 正确，纯先验只有 4/11。
   - `use_prior=False` 时 `prior = 1.0`：每个候选都加同一个常数 0.1，**排序完全由 Jaccard 决定**，但打印出来的 score 比纯 Jaccard 大 0.1。
5. **保留诊断信息**：`scored` 里存了 `(cand, score, jac, prior)` 四元组，虽然最后只返回前两项，但调试时打印 `scored` 就能看到每个候选的分数构成，这是一个好习惯。
6. **排序**：`sort(key=lambda x: -x[1])` 按分数降序。Python 的排序是**稳定**的，分数相同时保留 `ALIAS_INDEX` 中的原始顺序。这一点在下面的运行结果里有实际影响。
- ⚠️ 只需要最大值时，`max(scored, key=lambda x: x[1])` 是 O(n)，比排序的 O(n log n) 更省；不过候选只有 2–4 个，这里无所谓。用排序的好处是将来可以直接返回 top-K。

### 3.4 Jaccard 的隐藏偏置：mention 自身与描述长度

以 "Jordan scored 45 points against the Lakers last night." 为例，上下文有 9 个词，4 个候选的交集都**只有 `jordan` 这一个词**（"Lakers" 不在任何描述里）：

| 候选 | 描述词数 | 并集 | Jaccard |
|------|---------|------|---------|
| Q41421（篮球） | 9 | 17 | 0.0588 |
| Q810（约旦国） | 8 | 16 | 0.0625 |
| Q254110（演员） | 9 | 17 | 0.0588 |
| Q3308285（教授） | 8 | 16 | 0.0625 |

- 由于 mention 本身同时出现在上下文和几乎所有描述里，每个候选都"白拿"一份重叠。
- 上下文没有真正的证据时，胜负完全由**分母**决定：描述越短，Jaccard 越高。Q810 和 Q3308285 并列，稳定排序让排在前面的 Q810 胜出。
- 这就是无先验时唯一一个 MISS 的来源，也说明了先验的价值：加上 `0.1×0.5 = 0.05` 之后，篮球 Jordan 以 0.109 胜出。

### 3.5 `run_eval`：评估与打印

```python
def run_eval(test_cases, use_prior):
    correct = 0
    print(f"=== disambiguation {'with' if use_prior else 'without'} prior ===")
    for mention, context, gold in test_cases:
        pred, score = disambiguate(mention, context, use_prior=use_prior)
        ok = pred == gold
        correct += int(ok)
        tag = "  OK" if ok else "MISS"
        print(f"  [{tag}] mention={mention:<10} pred={pred:<7} gold={gold:<7} score={score:.3f}")
        print(f"         context: {context[:70]}...")
    print(f"  accuracy: {correct}/{len(test_cases)} ({100 * correct / len(test_cases):.1f}%)")
    print()
    return correct
```

- 指标是 **top-1 准确率**。因为 11 个用例的 gold 都在候选列表里（mention recall = 100%），这里测到的就是纯消歧准确率。讲义强调要和 mention recall 一起报告，这份代码只测了后者。
- `int(ok)` 把布尔值转成 0/1 累加。其实 `correct += ok` 也能工作（`bool` 是 `int` 的子类），写成 `int(ok)` 意图更清楚。
- f-string 里的 `{'with' if use_prior else 'without'}` 是嵌在花括号里的条件表达式；`:<10` 是左对齐并补齐到 10 个字符，用来排出整齐的表格。
- `context[:70]` 截断长句；短句也会加上 `...`，属于纯展示上的小瑕疵。
- ⚠️ **潜在 bug**：`pred={pred:<7}` 要求 `pred` 是字符串。如果测试集里加入一个别名表中不存在的 mention，`disambiguate` 返回 `None`，这一行会抛 `TypeError: unsupported format string passed to NoneType.__format__`。现有 11 个用例都在别名表里，所以没有触发。

### 3.6 `main`：一个"每个义项一个用例"的测试集

```python
    test_cases = [
        ("Jordan", "Jordan scored 45 points against the Lakers last night.", "Q41421"),
        ("Jordan", "Jordan borders Syria, Iraq, and Saudi Arabia in the Middle East.", "Q810"),
        # ...
        ("Python", "The python is a large nonvenomous snake found in Asia.", "Q83320"),
    ]

    run_eval(test_cases, use_prior=True)
    run_eval(test_cases, use_prior=False)
```

- 测试集按"每个别名的每个义项至少一句"来设计：Jordan 4 个义项全覆盖，Paris 3 个，Apple、Python 各 2 个。这样能同时考到热门实体和冷门实体，而不是只测最常见的义项（否则纯先验就能拿高分）。
- 同一份数据跑两次、只改一个开关，是最简单的**消融实验**：差值（11 vs 10）就是先验的贡献。
- ⚠️ 11 个用例统计意义很弱，脚本末尾的提示也承认这是玩具测试集；真实评估要用 AIDA-CoNLL（1,393 篇文章、约 3.4 万个 mention）这样的基准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字典模拟别名索引 | 一眼看清"表面形式 → 候选"的结构 | 生产中用 Wikidata / Wikipedia 别名转储，存成倒排索引或 KV 库，并配合模糊匹配和稠密检索 |
| Jaccard 词集合重叠 | 零依赖，直观展示"上下文与描述越像越好" | 偏向短描述，受 mention 自身词和停用词干扰；生产中换成 bi-encoder embedding 或 cross-encoder |
| 加法组合 `jac + 0.1·prior` | 先验只做弱先验 / 打破平局，不压制冷门实体 | 权重是拍脑袋定的；生产中在验证集上调权重，或用学习到的排序模型融合多种特征 |
| 先验同一别名下归一化 | 符合 `P(e | m)` 的概率语义 | 真实先验来自锚文本统计，存在流行度偏置，领域场景要重新估计 |
| 只在"无候选"时返回 None | 代码最短 | 没有分数阈值 NIL，KB 外实体会被硬链到某个已有实体；生产中必须加 NIL 阈值或 NIL 分类器 |
| 有 / 无先验两次评估 | 直接量化先验的贡献 | 只报了准确率，没报 mention recall、NIL 检测率 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量（全大写命名） | `ALIAS_INDEX = {...}`、`PRIORS = {...}` | 约定俗成表示"不应修改的全局数据" |
| 字典 / 列表字面量 | `{"jordan": ["Q41421", ...]}` | 嵌套的数据结构直接写在代码里 |
| `dict.get(key, default)` | `ALIAS_INDEX.get(mention.lower(), [])`、`PRIORS.get(cand, 0.0)` | 键不存在时返回默认值，而不是抛 `KeyError` |
| `re.findall` | `re.findall(r"[a-z0-9]+", text.lower())` | 返回所有匹配的子串列表；`r"..."` 是原始字符串，反斜杠不转义 |
| `set` 与集合运算 | `ctx_tokens & desc_tokens`、`ctx_tokens | desc_tokens` | `&` 交集、`|` 并集，平均 O(1) 查找，天然去重 |
| 条件表达式（三元运算） | `overlap / union if union else 0.0`、`"  OK" if ok else "MISS"` | `A if 条件 else B`，一行内完成分支 |
| 默认参数 | `def disambiguate(mention, context, use_prior=True)` | 调用时可以省略该参数 |
| 关键字参数调用 | `disambiguate(mention, context, use_prior=use_prior)` | 显式写出参数名，可读性更好 |
| 元组与元组解包 | `scored.append((cand, score, jac, prior))`；`pred, score = disambiguate(...)`；`for mention, context, gold in test_cases` | 一次返回或接收多个值 |
| `lambda` 与 `sort(key=...)` | `scored.sort(key=lambda x: -x[1])` | 按第 2 个元素取负数实现降序；等价于 `key=lambda x: x[1], reverse=True` |
| 稳定排序 | 同上 | Python 的 `sort` 是稳定的，相等元素保持原顺序 |
| 布尔转整数 | `correct += int(ok)` | `True → 1`，`False → 0` |
| 切片 | `context[:70]` | 取前 70 个字符，越界不会报错 |
| f-string 格式说明符 | `{mention:<10}`、`{score:.3f}`、`{100 * correct / len(test_cases):.1f}` | `<10` 左对齐补齐宽度，`.3f` 保留 3 位小数；花括号里可以写任意表达式 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`（Python 3.13），关键输出如下：

```text
=== disambiguation with prior ===
  [  OK] mention=Jordan     pred=Q41421  gold=Q41421  score=0.109
  [  OK] mention=Jordan     pred=Q810    gold=Q810    score=0.208
  [  OK] mention=Jordan     pred=Q254110 gold=Q254110 score=0.234
  [  OK] mention=Jordan     pred=Q3308285 gold=Q3308285 score=0.224
  [  OK] mention=Paris      pred=Q90     gold=Q90     score=0.514
  ...
  [  OK] mention=Python     pred=Q83320  gold=Q83320  score=0.405
  accuracy: 11/11 (100.0%)

=== disambiguation without prior ===
  [MISS] mention=Jordan     pred=Q810    gold=Q41421  score=0.163
         context: Jordan scored 45 points against the Lakers last night....
  [  OK] mention=Jordan     pred=Q810    gold=Q810    score=0.287
  ...
  [  OK] mention=Paris      pred=Q663094 gold=Q663094 score=0.555
  [  OK] mention=Paris      pred=Q55411  gold=Q55411  score=0.555
  ...
  accuracy: 10/11 (90.9%)

note: toy 11-case test set.
production EL uses Wikipedia alias dumps (~18M aliases) and encoder-based disambiguation.
```

逐行解读：

- **有先验 11/11**：第一句 "Jordan scored 45 points…" 的分数只有 0.109，是全场最低。它几乎全靠先验 `0.1×0.5 = 0.05` 赢下来，Jaccard 部分只有 0.0588。说明"赢"得很勉强。
- **约旦国那句 0.208**：交集是 `{jordan, middle, east}`，并集 16，Jaccard = 0.1875，加上 `0.1×0.2 = 0.02`。注意上下文中的 `arabia` 和描述中的 `arabic` 没对上，这就是没有词形还原的代价。
- **Paris / France 那句 0.514**：交集是 `{paris, capital, of, france, eiffel, tower}`，其中 `of` 是停用词"蹭"到的。
- **无先验时唯一的 MISS**：原因见 3.4 节，只剩 mention 自身一个重叠词时，Jaccard 偏向描述更短的 Q810，而 Q810 又因稳定排序赢下和 Q3308285 的平局。显示的 0.163 = 0.0625 + 0.1（常数偏移）。
- **无先验的 score 普遍比有先验大**：因为 `prior=1.0` 时每个候选都加 0.1，而有先验时加的是 `0.1×prior`（≤ 0.085）。所以两组分数**不能直接比较大小**。
- **两组准确率之差 1/11**：这就是消融实验测出的先验贡献。我在本地把权重从 0.1 换成其他值试了一下：0.05 和 0.1 都是 11/11，0.2 和 0.3 掉到 10/11，0.5 是 7/11，1.0 只剩 4/11（等于纯先验）。先验权重越大，流行度偏置越明显。

---

## 7. 动手改一改

1. **修掉打印 bug**：在测试集里加 `("Tesla", "Tesla unveiled a new electric car.", None)`，先看它崩溃，再把 `None` 统一改成字符串 `"NIL"`。
2. **加 NIL 阈值**：最佳候选的 Jaccard 低于 `tau` 时返回 `"NIL"`；再加两条 KB 外的句子（如 "Jordan Peterson released a new book on psychology."），观察阈值如何在"误判 NIL"和"硬链错误实体"之间取舍。
3. **去掉 mention 自身词和停用词**：计算 Jaccard 前执行 `ctx_tokens -= {mention.lower()}`，并去掉 `the / of / and / is` 等词，比较无先验时的准确率和分数分布。
4. **乘法 vs 加法**：把 `score` 改成讲义里的 `prior * jac`，看准确率怎么变，解释为什么冷门实体（Paris Hilton、Paris, Texas）会被热门的巴黎压住。
5. **报告 mention recall@K**：把候选按先验排序后截断成前 K 个，统计 gold 在候选中的比例；再算"recall@K × 消歧准确率"作为端到端上限。
6. **换成 embedding**（需要自行安装 sentence-transformers）：按讲义 Step 3，用 `[MENTION]…[/MENTION]` 标记 mention 后编码，与 `KB_DESC` 的向量做点积，对比 Jaccard 版本的准确率。

---

## 8. 常见坑

- **把别名索引当成精确匹配就够了**：真实文本里有 "Michael Jordan's"、"M. Jordan"、"MJ" 等写法，候选生成需要大小写和标点归一化、缩写表、模糊匹配，否则 mention recall 会先掉下来，后面的消歧再准也没用。
- **只报消歧准确率**：本代码的测试集 mention recall = 100%，所以准确率看起来很高；换成真实数据时，一定要先测候选召回。
- **Jaccard 偏向短描述**：描述越长并集越大、分数越低，"信息量更多的实体"反而吃亏；改用 TF-IDF 余弦或 embedding 可以缓解。
- **先验权重过大 → 流行度偏置**：权重调到 1.0 时退化为纯先验，冷门义项全错。领域场景（如 ML 论文里的 Michael I. Jordan）必须重新估计先验或做微调。
- **`None` 参与格式化**：`f"{None:<7}"` 会抛 `TypeError`；NIL 最好用字符串 `"NIL"` 表示。
- **跨运行比较 score**：有 / 无先验时 score 的基线不同（+0.1 常数偏移），只能比较同一次运行内部的排序，不能比较绝对值。
