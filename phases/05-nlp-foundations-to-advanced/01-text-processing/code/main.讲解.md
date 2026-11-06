# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到高级 · 第 01 节 文本处理 — Tokenization、词干提取、词形还原 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`），不需要 NLTK / spaCy

---

## 1. 这份代码在考察什么

这份不到 100 行的脚本，把一个经典 NLP 预处理流水线的三个环节各写了一个"最小可用版"，目的是让你**亲手看到每一步的规则和它的失败模式**：

1. **Tokenization**：用一条正则把字符串切成 token，理解"分支顺序 = 优先级"，以及为什么 `3pm`、URL、非 ASCII 字母会被切碎。
2. **Stemming**：只实现 Porter 算法的 step 1a，体会"规则相互竞争、先匹配者胜"。
3. **Lemmatization**：用"查表 + 后缀回退"模拟词形还原，理解它为什么**必须依赖词性（POS）**。
4. **流水线组装**：`preprocess` 把三步串起来，并把 POS tagger 设计成可注入的参数——这是后面阶段 05 · 07 要补上的那一块。
5. **工程意识**：每一步都是"够用但不完美"，读完你应能说清 NLTK / spaCy 帮你多做了哪些事。

> 一句话：**先用 50 行规则把预处理拆开看清楚，再理解为什么生产中要交给成熟库（或者在 Transformer 时代干脆不做）。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `WORD_RE` | 模块级常量（预编译正则） | 定义 token 的三种形态：带可选撇号的单词、数字串、单个标点 | Tokenization |
| `tokenize(text)` | 函数 | `WORD_RE.findall(text)`，返回 token 列表 | Tokenization |
| `stem_step_1a(word)` | 函数 | Porter step 1a 的四条后缀规则 | Stemming |
| `LEMMA_TABLE` | 字典，键为 `(词, 词性)` 元组 | 小型 lemma 查找表 | Lemmatization 的词典部分 |
| `lemmatize(word, pos)` | 函数 | 先查表，查不到再按词性做后缀回退 | Lemmatization |
| `preprocess(text, pos_tagger=None)` | 函数 | 串起 tokenize → stem → (POS) → lemmatize，返回字典 | 预处理流水线 |
| `demo_pos_tagger(tokens)` | 函数 | 用硬编码集合给 token 打 VERB/ADJ/NOUN 标签 | POS tagging（玩具版） |
| `main()` | 函数 | 对一句示例文本跑完整流水线并打印 | 演示入口 |

数据流：`text → tokenize → tokens`；`tokens → (小写) → stem_step_1a → stems`；`tokens → pos_tagger → (token, tag) → lemmatize → lemmas`。注意 **stems 与 lemmas 是两条并行分支**，都从 tokens 出发，而不是串联的。

---

## 3. 逐段精讲

### 3.1 正则 tokenizer：三个分支，顺序即优先级

```python
import re


WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[0-9]+|[^\sA-Za-z0-9]")


def tokenize(text):
    return WORD_RE.findall(text)
```

正则由 `|` 分成三个分支：

| 分支 | 匹配什么 | 例子 |
|------|---------|------|
| `[A-Za-z]+(?:'[A-Za-z]+)?` | 一串 ASCII 字母，后面**可选**跟一个"撇号 + 字母串" | `cats`、`weren't`、`don't` |
| `[0-9]+` | 一串数字 | `3`、`2024` |
| `[^\sA-Za-z0-9]` | 任意**一个**既不是空白、也不是字母数字的字符 | `.`、`!`、`$` |

- `re.compile` 把正则预编译成对象放在模块级，`tokenize` 每次调用时不必重新解析模式字符串。（`re` 模块内部其实也会缓存，但显式预编译让意图更清晰。）
- `findall` 从左到右扫描，在每个位置按分支顺序尝试，返回所有不重叠的匹配；空白字符没有任何分支能匹配，于是被自然跳过——**这条正则同时完成了"切分"和"丢弃空白"**。
- `(?:...)` 是**非捕获组**。如果写成普通括号 `('[A-Za-z]+)?`，`findall` 会改为返回"组的内容"而不是整个匹配，结果就全乱了。这是一个很常见的坑。
- `3pm` 会被切成 `['3', 'pm']`：字母分支遇到数字停下，数字分支遇到字母停下。讲义认为"对多数任务够用"。
- ⚠️ 刻意的简化：
  - 只认 ASCII 字母，`naïve` 会被切成 `['na', 'ï', 've']`（`ï` 落入"标点"分支）；
  - 撇号组最多出现一次，`O'Neil's` 会变成 `["O'Neil", "'", 's']`；
  - URL、邮箱、hashtag 全部被切碎。讲义给的修法是"在通用分支**之前**加入更具体的模式"。

### 3.2 Porter step 1a：最长后缀优先

```python
def stem_step_1a(word):
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("ies"):
        return word[:-2]
    if word.endswith("ss"):
        return word
    if word.endswith("s") and len(word) > 1:
        return word[:-1]
    return word
```

| 规则 | 写法 | 例子 |
|------|------|------|
| `sses → ss` | 去掉末尾 2 个字符 | `caresses → caress` |
| `ies → i` | 去掉末尾 2 个字符 | `ponies → poni` |
| `ss → ss` | 原样返回 | `caress → caress` |
| `s → ''` | 去掉末尾 1 个字符 | `cats → cat` |

- 四个 `if` 都是"命中就 `return`"，所以**第一个命中的规则决定结果**。更长、更具体的后缀排在前面，最泛化的 `s` 排在最后——如果把 `s` 规则提到最前，`caresses` 会变成 `caresse`，`caress` 会变成 `cares`。这就是讲义说的 "The order matters more than any single rule"。
- `ies → i` 的写法很巧：不是"删掉 `ies` 再补 `i`"，而是直接删掉末尾两个字母 `es`，留下的 `i` 正好就是目标。`sses → ss` 同理。
- `len(word) > 1` 防止单个字母 `"s"` 被砍成空串。
- ⚠️ 没有真实 Porter 算法中的 measure（m 值，大致是"元音-辅音序列"的个数）等条件，因此 `is → i`、`this → thi`、`bus → bu` 这类短词会被误砍。
- ⚠️ `ponies → poni` 不是 bug，而是 step 1a 的设计结果；stemming 本来就不保证输出是真词。

### 3.3 Lemma 查找表：用 `(词, 词性)` 作键

```python
LEMMA_TABLE = {
    ("running", "VERB"): "run",
    ("ran", "VERB"): "run",
    ("runs", "VERB"): "run",
    ("better", "ADJ"): "good",
    ("best", "ADJ"): "good",
    ("cats", "NOUN"): "cat",
    ("cat", "NOUN"): "cat",
    ("were", "VERB"): "be",
    ("was", "VERB"): "be",
    ("is", "VERB"): "be",
}
```

- 键是一个**元组** `(word, pos)`。元组不可变、可哈希，所以能当字典键；列表不行。
- 把词性放进键里，正是"lemma 依赖词性"这一概念的直接编码：`("better", "ADJ") → "good"`，但 `("better", "VERB")`（"改善"）就查不到，不会被错误地还原成 `good`。
- 表里收录的恰好是**规则无法处理的不规则形式**：`ran`、`better/best`、`were/was/is`。这暗示了真实系统的结构：**例外词典 + 规则**。

### 3.4 `lemmatize`：查表优先，后缀回退兜底

```python
def lemmatize(word, pos):
    key = (word.lower(), pos)
    if key in LEMMA_TABLE:
        return LEMMA_TABLE[key]
    if pos == "VERB" and word.endswith("ing"):
        return word[:-3]
    if pos == "NOUN" and word.endswith("s"):
        return word[:-1]
    return word.lower()
```

- 三层优先级：①查表（精确、处理不规则形式）→ ②按词性的后缀规则（覆盖规则形式）→ ③原样返回小写。
- `key in LEMMA_TABLE` 是字典的 O(1) 成员测试。
- 讲义的"教学时刻"：`lemmatize("watched", "VERB")` 返回 `'watched'`——表里没有，回退规则又只认 `ing`。真实的 lemmatizer 要覆盖 `ed`、不规则动词、比较级、带音变的复数（`children → child`），所以生产中用 WordNet 或 spaCy。
- ⚠️ 回退规则非常粗糙（详见测验 Q9）：
  - `sing` → `s`（不检查剩余词干）；
  - `class`（NOUN）→ `clas`（没排除 `ss`）；
  - 若 `running` 不在表里，会得到 `runn`（不处理双写辅音）。
- ⚠️ 大小写不一致：查表分支和最后一个分支返回小写，而两条回退分支对**原始** `word` 切片，`lemmatize("Jumping", "VERB")` 返回 `'Jump'`。在流水线里，句首大写词就会出现这种不一致。改法是开头先 `w = word.lower()`，后面所有分支都用 `w`。

### 3.5 `preprocess`：可注入的 POS tagger

```python
def preprocess(text, pos_tagger=None):
    tokens = tokenize(text)
    stems = [stem_step_1a(t.lower()) for t in tokens]
    tags = pos_tagger(tokens) if pos_tagger else [(t, "NOUN") for t in tokens]
    lemmas = [lemmatize(word, pos) for word, pos in tags]
    return {"tokens": tokens, "stems": stems, "lemmas": lemmas}
```

- `pos_tagger=None` 是**依赖注入**的轻量写法：调用方可以传入任何"接受 token 列表、返回 `(token, tag)` 列表"的函数。没传就退化为"全部当名词"——讲义明确说这是"acknowledge the limitation"。
- `A if cond else B` 是**条件表达式**；这里用 `if pos_tagger`（真值判断）而非 `is not None`，效果相同。
- stemming 前先 `t.lower()`，因为 `stem_step_1a` 只做大小写敏感的 `endswith`；而 lemmatize 则把原始 token 交给 `lemmatize` 内部去小写——两条分支的大小写处理位置不同，这也是 3.4 中大小写不一致问题的来源。
- 返回字典而不是元组，调用方用 `result['tokens']` 按名字取值，可读性更好，也方便以后增加字段（比如 `tags`）。
- 后果演示：不传 tagger 时，`preprocess("The cats were running.")` 的 lemmas 是 `['the', 'cat', 'were', 'running', '.']`——`were`、`running` 被当名词，**完全没有还原**。这正是"lemmatization 没有 POS 就不可靠"的直观证据。

### 3.6 `demo_pos_tagger`：一个"作弊"的玩具 tagger

```python
def demo_pos_tagger(tokens):
    verbs = {"running", "ran", "runs", "were", "was", "is", "watched"}
    adjs = {"better", "best"}
    out = []
    for t in tokens:
        low = t.lower()
        if low in verbs:
            out.append((t, "VERB"))
        elif low in adjs:
            out.append((t, "ADJ"))
        else:
            out.append((t, "NOUN"))
    return out
```

- 用两个**集合**（set）做成员判断，平均 O(1)。
- 输出元组中保留的是原始 token `t`（不是 `low`），把小写化的责任留给 `lemmatize`。
- ⚠️ 它不看上下文，只查词表——同一个词永远得到同一个标签，无法区分 "I saw" 与 "the saw"。真正的 POS tagger（HMM、感知机、神经网络）在阶段 05 · 07 构建。

### 3.7 `main` 与入口保护

```python
def main():
    text = "The cats were running at 3pm."
    result = preprocess(text, pos_tagger=demo_pos_tagger)
    print(f"input:  {text}")
    print(f"tokens: {result['tokens']}")
    print(f"stems:  {result['stems']}")
    print(f"lemmas: {result['lemmas']}")


if __name__ == "__main__":
    main()
```

- 示例句刻意包含了：复数名词（`cats`）、不规则动词（`were`）、进行时（`running`）、数字粘字母（`3pm`）、句末标点——一句话覆盖了三步的主要行为。
- f-string 里用 `result['tokens']`（单引号）是因为外层 f-string 用了双引号；Python 3.12 之前，f-string 内部不能复用同一种引号。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一条正则完成切分 | 一行可读，三个分支直观对应三类 token | 不处理 Unicode、URL、缩写变体；生产用 NLTK `word_tokenize` 或 spaCy |
| 只实现 Porter step 1a | 覆盖最常见的英文后缀，足以展示"规则顺序" | 无 measure 条件，短词误砍；生产用完整 `PorterStemmer`（五个阶段） |
| `(词, 词性)` 元组作为字典键 | 把"lemma 依赖词性"写进数据结构 | 词表极小；生产用 WordNet / spaCy 形态分析器 |
| 查表 + 后缀回退 | 体现"例外词典 + 规则"的真实结构 | 回退规则粗糙（`sing→s`、`class→clas`） |
| POS tagger 作为可选参数注入 | 先把流水线接口定好，后面课程替换实现即可 | 默认全当 NOUN，lemmatize 基本失效 |
| stems 与 lemmas 并行输出 | 方便同屏对比两种方法的结果 | 实际系统通常二选一 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 原始字符串 `r"..."` | `r"[A-Za-z]+(?:'[A-Za-z]+)?..."` | 反斜杠不转义，写正则时必备（`\s` 原样传给 `re`） |
| `re.compile` / `findall` | `WORD_RE.findall(text)` | 预编译正则；`findall` 返回所有不重叠匹配组成的列表 |
| 正则：字符类、分支、非捕获组 | `[^\sA-Za-z0-9]`、`|`、`(?:...)` | `[^...]` 取反；`|` 从左到右尝试；`(?:...)` 分组但不捕获，避免改变 `findall` 的返回值 |
| 字符串方法 | `word.endswith("sses")`、`t.lower()` | 后缀判断、转小写 |
| 负索引切片 | `word[:-2]`、`word[:-3]` | 去掉末尾 2 / 3 个字符 |
| 元组作为字典键 | `("running", "VERB"): "run"` | 元组可哈希，可作键；`key in dict` 是 O(1) 查找 |
| 集合字面量 | `{"better", "best"}` | 无序、去重、成员判断快 |
| 默认参数 `None` | `def preprocess(text, pos_tagger=None)` | 可选参数；函数也可以作为参数传入（一等公民） |
| 条件表达式 | `pos_tagger(tokens) if pos_tagger else [...]` | 一行版 if/else |
| 列表推导式 + 元组解包 | `[lemmatize(word, pos) for word, pos in tags]` | 遍历 `(词, 词性)` 对并同时拆包 |
| `if / elif / else` | `demo_pos_tagger` 中的分类 | 多分支判断 |
| f-string | `f"tokens: {result['tokens']}"` | 字符串插值；内部引号要与外层不同（3.12 之前） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被导入时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，纯标准库）的完整输出：

```text
input:  The cats were running at 3pm.
tokens: ['The', 'cats', 'were', 'running', 'at', '3', 'pm', '.']
stems:  ['the', 'cat', 'were', 'running', 'at', '3', 'pm', '.']
lemmas: ['the', 'cat', 'be', 'run', 'at', '3', 'pm', '.']
```

逐行解读：

- **tokens**：8 个 token。`3pm` 被拆成 `'3'` 和 `'pm'`（讲义指出的失败模式）；句号单独成 token；`The` 保留原始大小写——tokenizer 不负责小写化。
- **stems**：先小写再 stem。只有 `cats → cat` 发生了变化（命中 `s` 规则）。`were` 和 `running` **原样保留**——step 1a 只处理 `s` 结尾的复数形式，`-ing` 归 step 1b 管，而不规则动词 `were` 任何 stemmer 都无能为力。
- **lemmas**：在 `demo_pos_tagger` 的帮助下，`were → be`、`running → run`（都是查表命中），`cats → cat`。对比 stems 一行，一眼就能看出 lemmatization 在不规则形式上的优势。`the`、`at`、`pm` 被 tagger 当成 NOUN，但它们不以 `s` 结尾，于是走最后一个分支原样小写返回。

再补充一个对照实验（不传 `pos_tagger`）：

```text
>>> preprocess("The cats were running.")
{'tokens': ['The', 'cats', 'were', 'running', '.'],
 'stems':  ['the', 'cat', 'were', 'running', '.'],
 'lemmas': ['the', 'cat', 'were', 'running', '.']}
```

所有词都被当成名词，`were`、`running` 都没被还原——POS 信息缺失时，lemmatizer 的效果退化到和 step 1a stemmer 差不多。

---

## 7. 动手改一改

1. **（易）URL 保留**：在 `WORD_RE` 的最前面加一个 URL 分支，让 `tokenize("Visit https://example.com today.")` 产出一个完整的 URL token，同时句号仍单独成 token。（参考答案见测验 Q10。）
2. **（易）Unicode 友好**：把字母分支改成 Unicode 感知的写法（如 `[^\W\d_]+`），验证 `naïve café` 能被正确切成两个词。思考：标点分支要同步怎么改？
3. **（中）修复 lemmatize 的大小写与回退问题**：开头统一小写；`ing` 回退要求剩余词干含元音；名词回退排除 `ss`。用 `sing / Jumping / class / Dogs` 验证。
4. **（中）实现 Porter step 1b**（讲义练习 2）：含元音且以 `ed` / `ing` 结尾时去掉后缀，并处理双写辅音（`hopping → hop`）。
5. **（中）回归测试**：写 `test_preprocess.py`，冻结 20 条句子（缩写、数字、URL、Unicode、标点）的期望 tokens，用 `pytest` 运行。改动 `WORD_RE` 时看看哪些用例会挂。
6. **（难）对比实验**：如果环境中装有 NLTK，把 `stem_step_1a` 换成 `PorterStemmer().stem`、把 `lemmatize` 换成带 POS 映射的 `WordNetLemmatizer`，在同一批句子上对比三列输出的差异。

---

## 8. 常见坑

- **正则里用了捕获组**：把 `(?:'[A-Za-z]+)?` 写成 `('[A-Za-z]+)?`，`findall` 就会只返回撇号组的内容（大多是空串），整个 tokenizer 立刻"坏掉"。
- **分支顺序写反**：在 tokenizer 里把通用分支放在具体分支（如 URL）之前，在 stemmer 里把 `s` 规则放在 `sses` 之前，都会让更具体的规则永远不触发。
- **以为 stem 是真词**：`poni`、`thi` 不能展示给用户；讲义的 Ship It 明确要求"拒绝对用户可见文本推荐 stemming"。
- **lemmatize 不传词性**：所有词都按名词处理，动词、形容词基本不会被还原；用 NLTK 时还要记得把 Penn Treebank 标签翻译成 WordNet 的 `v/a/r/n`。
- **大小写处理位置不统一**：一条分支先小写、另一条在函数内部小写、还有分支忘了小写，最终输出出现 `Jump` 和 `jump` 两种形式，词表被无声地撑大。
- **训练与推理用了不同的预处理**：哪怕只是这份脚本的一个小改动（比如加了 URL 分支）没同步到线上，模型看到的 token 分布就变了。预处理函数要和模型一起版本化。
