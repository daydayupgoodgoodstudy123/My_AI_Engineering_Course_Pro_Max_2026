# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到高级 · 第 02 节 词袋、TF-IDF 和文本表示 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`re`），不需要 scikit-learn / NumPy

---

## 1. 这份代码在考察什么

这份脚本用不到 100 行纯 Python，把"字符串 → 定长数值向量 → 文档相似度"的经典链路完整走了一遍：

1. **词表构建**：如何给每个词分配一个固定下标，让不同长度的文档都能映射到同一维度的向量。
2. **词袋（BoW）**：只数次数、丢掉顺序，理解"稀疏 + 每一维可解释"的表示长什么样。
3. **TF-IDF 加权**：亲手实现 TF、DF、平滑 IDF，看清"处处出现的词被压低、稀有词被抬高"的机制——以及平滑带来的副作用。
4. **L2 归一化与余弦相似度**：为什么归一化之后余弦相似度就等于点积。
5. **与 scikit-learn 对齐**：这份实现的输出与 `TfidfVectorizer()` 默认配置在数值上一致（对齐列顺序后误差约 1e-16），学完你就知道那个"三行搞定"的 API 内部到底在算什么。

> 一句话：**TF-IDF 只是"计数 × 稀有度 → 归一化"三步，自己写一遍，就能读懂 scikit-learn 的每一个参数。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TOKEN_RE` / `tokenize(text)` | 正则常量 + 函数 | 抽取单词和数字并转小写，**丢弃标点** | Tokenization（第 01 节的简化版） |
| `build_vocab(docs)` | 函数 | 按首次出现顺序给每个词编号，返回 `{词: 下标}` | 词表 |
| `bag_of_words(docs, vocab)` | 函数 | 生成"文档 × 词表"的计数矩阵 | BoW |
| `document_frequency(bow_matrix)` | 函数 | 统计每个词出现在多少篇文档中 | DF |
| `inverse_document_frequency(df, n_docs)` | 函数 | 平滑 IDF：`ln((N+1)/(df+1)) + 1` | IDF |
| `tfidf(bow_matrix)` | 函数 | TF（计数 / 文档长度）× IDF | TF-IDF |
| `l2_normalize(matrix)` | 函数 | 每行除以自己的 L2 范数 | 长度归一化 |
| `cosine_similarity(a, b)` | 函数 | 两个向量的点积（**假设已归一化**） | 余弦相似度 |
| `main()` | 函数 | 3 篇示例文档 → 打印词表、TF-IDF 向量、相似度矩阵 | 演示入口 |

数据流：`raw 字符串 → tokenize → docs（词列表的列表）→ build_vocab → bag_of_words → tfidf → l2_normalize → 两两 cosine_similarity`。

---

## 3. 逐段精讲

### 3.1 Tokenizer：比第 01 节更"狠"

```python
TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[0-9]+")


def tokenize(text):
    return [t.lower() for t in TOKEN_RE.findall(text)]
```

- 与第 01 节的 `WORD_RE` 相比，**去掉了第三个分支** `[^\sA-Za-z0-9]`，所以标点（如句号）根本不会被匹配，直接消失。对词袋来说，标点基本没有区分度，丢掉可以缩小词表。
- 统一 `lower()`：`The` 和 `the` 合并为一个词。这是讲义提到的 "simplified lowercase variant"。
- ⚠️ 代价：`!`、`?` 在情感分析中可能有信号；小写化会把 `US`（美国）和 `us`（我们）合并。预处理选择永远是任务相关的。

### 3.2 `build_vocab`：插入顺序即下标

```python
def build_vocab(docs):
    vocab = {}
    for doc in docs:
        for token in doc:
            if token not in vocab:
                vocab[token] = len(vocab)
    return vocab
```

- `vocab[token] = len(vocab)` 是个很巧的写法：字典当前有几个元素，新词的下标就是几，自动得到 `0, 1, 2, ...` 的连续编号。
- 下标顺序 = 词在语料中**首次出现**的顺序，所以 `the` 是 0、`cat` 是 1。scikit-learn 则按**字母序**排序（讲义："Convention varies; scikit-learn sorts alphabetically"）。列顺序不同不影响任何数学结果，但对比两份实现时要先按词名对齐。
- `token not in vocab` 对字典是 O(1)，整体 O(语料总 token 数)。

### 3.3 `bag_of_words`：计数矩阵

```python
def bag_of_words(docs, vocab):
    matrix = [[0] * len(vocab) for _ in docs]
    for i, doc in enumerate(docs):
        for token in doc:
            if token in vocab:
                matrix[i][vocab[token]] += 1
    return matrix
```

- `[[0] * len(vocab) for _ in docs]`：每篇文档一行、每个词一列的全零矩阵。**必须用列表推导**，不能写成 `[[0] * V] * n`——后者会让 n 行指向同一个列表对象，改一行就改了所有行（经典坑）。
- `_` 表示"这个循环变量我用不到"，是 Python 社区约定。
- `if token in vocab`：推理时遇到训练词表之外的词（OOV）会被**静默跳过**。这就是讲义说的第二种失败："A BoW model ... has no idea what to do with `Zoomer-approved`"。
- ⚠️ 用稠密的 Python 列表存矩阵，教学上直观；但真实词表有 1 万～10 万维，绝大多数格子是 0。scikit-learn 返回的是**稀疏矩阵**，讲义提醒："stay sparse until the classifier demands dense"。

### 3.4 DF 与平滑 IDF

```python
def document_frequency(bow_matrix):
    df = [0] * len(bow_matrix[0])
    for row in bow_matrix:
        for j, count in enumerate(row):
            if count > 0:
                df[j] += 1
    return df


def inverse_document_frequency(df, n_docs):
    return [math.log((n_docs + 1) / (d + 1)) + 1 for d in df]
```

- DF 只关心"出没出现"（`count > 0`），不关心出现了几次——一篇文档里 `the` 出现 100 次，对 DF 的贡献也只是 1。
- IDF 公式中的两个平滑技巧：

| 技巧 | 作用 |
|------|------|
| `(N+1)/(df+1)` | 避免 `df = 0` 时除零（例如对新语料 transform 时） |
| 末尾 `+ 1` | 让出现在**所有**文档中的词 IDF = 1 而不是 0，与 scikit-learn 默认 `smooth_idf=True` 一致 |

- 本例 N = 3：`the`（df=3）→ `ln(4/4)+1 = 1.000`；`cat/sat/on/mat`（df=2）→ `ln(4/3)+1 ≈ 1.288`；`dog/ran/across/room`（df=1）→ `ln(4/2)+1 ≈ 1.693`。
- `math.log` 是**自然对数**（以 e 为底），与 scikit-learn 一致。对原始 `log(N/df)` 而言，换底数只是整体乘一个常数，L2 归一化后不影响结果；但平滑版末尾有 `+ 1`，换底数会改变"log 部分"与常数 1 的相对比例，结果会略有不同——所以要和 scikit-learn 对齐，必须用自然对数。
- ⚠️ `bow_matrix[0]` 假设矩阵非空；传入空列表会抛 `IndexError`。

### 3.5 `tfidf`：TF × IDF

```python
def tfidf(bow_matrix):
    n_docs = len(bow_matrix)
    df = document_frequency(bow_matrix)
    idf = inverse_document_frequency(df, n_docs)
    out = []
    for row in bow_matrix:
        length = sum(row)
        tf = [c / length if length else 0 for c in row]
        out.append([t * i for t, i in zip(tf, idf)])
    return out
```

- TF = 计数 / 文档长度（这里的"长度"是词表内 token 的总数 `sum(row)`）。`if length else 0` 防止空文档除零。
- `zip(tf, idf)` 把两条等长列表按位置配对，逐元素相乘。
- 一个值得记住的结论：**TF 是否除以文档长度，在 L2 归一化之后没有影响**。因为同一行的每个元素都乘了同一个 `1/length`，归一化时被抵消。所以本实现虽然 TF 定义与 scikit-learn（直接用原始计数）不同，最终输出却一致。
- ⚠️ IDF 是在**传入的同一批文档**上算出来的，相当于"在全量数据上 fit"。生产中应只在训练集上计算 DF/IDF，再对新文档复用——否则会造成数据泄露，也无法处理单篇新文档。

### 3.6 L2 归一化与"余弦相似度"

```python
def l2_normalize(matrix):
    out = []
    for row in matrix:
        norm = math.sqrt(sum(x * x for x in row))
        out.append([x / norm if norm else 0 for x in row])
    return out


def cosine_similarity(a, b):
    return sum(x * y for x, y in zip(a, b))
```

- `l2_normalize` 把每行缩放到模长 1，`if norm else 0` 处理全零行（空文档或全是 OOV 的文档）。
- 归一化后，`cos(a, b) = a·b / (|a||b|) = a·b`，所以 `cosine_similarity` 只算点积。
- ⚠️ 这个函数**只有在输入已归一化时才名副其实**。如果有人直接传 `tfidf(bow)` 的结果，得到的只是原始点积（测验 Q10 实测：两篇相同文档只得到约 0.553）。更稳妥的做法是在函数里自己除以两个模长，或者把函数改名为 `dot`。

### 3.7 `main`：打印词表、向量与相似度矩阵

```python
def main():
    raw = [
        "The cat sat on the mat.",
        "The dog sat on the mat.",
        "The cat ran across the room.",
    ]
    docs = [tokenize(r) for r in raw]
    vocab = build_vocab(docs)
    bow = bag_of_words(docs, vocab)
    tfidf_vectors = l2_normalize(tfidf(bow))

    words = sorted(vocab, key=lambda w: vocab[w])
    print(f"vocab: {words}")
    # ...
    for i, (r, v) in enumerate(zip(raw, tfidf_vectors)):
        pretty = [f"{x:.2f}" for x in v]
        # ...
    print("cosine similarity matrix:")
    for i in range(len(tfidf_vectors)):
        row = [f"{cosine_similarity(tfidf_vectors[i], tfidf_vectors[j]):.2f}" for j in range(len(tfidf_vectors))]
        print(f"  d{i}: {row}")
```

- 三篇文档设计得很有讲究：d0 和 d1 只差一个词（cat ↔ dog），d0 和 d2 共享 `cat`，d1 和 d2 除了 `the` 什么都不共享。
- `sorted(vocab, key=lambda w: vocab[w])`：对字典迭代得到的是**键**；按值（下标）排序，就得到"下标 → 词"的顺序列表，方便和向量各维对齐打印。（Python 3.7+ 字典本身保持插入顺序，所以这里 `list(vocab)` 也能得到同样结果，但显式排序更稳健。）
- `enumerate(zip(raw, tfidf_vectors))` 同时拿到下标、原文和向量，`(r, v)` 是**嵌套解包**。
- 相似度矩阵用 O(n²) 两两计算，n = 3 无所谓；真实检索要靠矩阵乘法或 ANN 索引。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表实现矩阵 | 每一步都看得见，便于对照公式 | 稠密存储、慢；生产用 scikit-learn 的稀疏矩阵 |
| 按首次出现顺序编号词表 | 实现最简单（`len(vocab)`） | 与 scikit-learn 字母序不同，对比前需按词名对齐列 |
| 平滑 IDF（与 sklearn 默认一致） | 防除零、处处出现的词不被清零 | 高频虚词保留权重，小语料上 `the` 甚至权重最高；常配合 `max_df` / 停用词 / `sublinear_tf` |
| TF 除以文档长度 | 贴近教科书定义 | 在 L2 归一化后其实是多余的一步 |
| 在同一批文档上算 IDF 并变换 | 演示简洁 | 生产中必须 `fit` 于训练集、`transform` 新数据，并与模型一起版本化 |
| `cosine_similarity` 只算点积 | 输入已归一化时最快 | 函数名有误导性；通用版本需自己归一化并处理零向量 |
| tokenizer 丢弃标点、统一小写 | 缩小词表 | 丢失 `!`、大小写等可能有用的信号 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import` 标准库 | `import math`、`import re` | `math.log` 是自然对数，`math.sqrt` 开平方 |
| 预编译正则 + `findall` | `TOKEN_RE.findall(text)` | 返回所有匹配的字符串列表 |
| 列表推导式 | `[t.lower() for t in ...]` | 一行生成新列表 |
| 带条件表达式的推导式 | `[c / length if length else 0 for c in row]` | `A if cond else B` 写在推导式的表达式位置，对每个元素做"带保护的计算" |
| 嵌套列表初始化 | `[[0] * len(vocab) for _ in docs]` | 每行都是独立的新列表；`_` 表示不使用的循环变量 |
| 字典作为映射 | `vocab[token] = len(vocab)`、`token in vocab` | O(1) 插入与查找；Python 3.7+ 保持插入顺序 |
| `enumerate` | `for j, count in enumerate(row)` | 同时拿到下标和元素 |
| `zip` | `zip(tf, idf)` | 按位置配对多个序列 |
| 嵌套元组解包 | `for i, (r, v) in enumerate(zip(raw, tfidf_vectors))` | 一次解开"下标 + (原文, 向量)" |
| 生成器表达式 | `sum(x * x for x in row)` | 不建中间列表，直接求和 |
| `sorted` + `key` + `lambda` | `sorted(vocab, key=lambda w: vocab[w])` | 按自定义规则排序；`lambda` 是匿名函数 |
| f-string 格式符 | `f"{x:.2f}"` | 保留 2 位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，纯标准库）的完整输出：

```text
vocab: ['the', 'cat', 'sat', 'on', 'mat', 'dog', 'ran', 'across', 'room']

d0: The cat sat on the mat.
    tfidf: ['0.61', '0.39', '0.39', '0.39', '0.39', '0.00', '0.00', '0.00', '0.00']

d1: The dog sat on the mat.
    tfidf: ['0.58', '0.00', '0.37', '0.37', '0.37', '0.49', '0.00', '0.00', '0.00']

d2: The cat ran across the room.
    tfidf: ['0.53', '0.34', '0.00', '0.00', '0.00', '0.00', '0.45', '0.45', '0.45']

cosine similarity matrix:
  d0: ['1.00', '0.80', '0.46']
  d1: ['0.80', '1.00', '0.31']
  d2: ['0.46', '0.31', '1.00']
```

逐项解读：

- **vocab**：9 个词，按首次出现顺序排列；句号已被 tokenizer 丢弃，`The` 已小写。
- **d0 中 `the` = 0.61，反而最大**：`the` 在每篇都出现两次（TF = 2/6），平滑 IDF 又让它保留了 1.0 的权重；而 `cat` 等词 TF 只有 1/6，IDF 也只有 1.288。计算：`0.333 / 0.544 ≈ 0.61`、`0.215 / 0.544 ≈ 0.39`。这是平滑 IDF 在小语料上的副作用。
- **d1 中 `dog` = 0.49 > `sat/on/mat` = 0.37**：`dog` 只出现在 1 篇文档中（IDF ≈ 1.693），比出现在 2 篇中的词（IDF ≈ 1.288）权重更高——这就是 IDF "抬高稀有词"的效果。
- **d2 中 `ran/across/room` = 0.45 > `cat` = 0.34**：同理，d2 独有的三个词权重最高。
- **相似度矩阵**：
  - 对角线全是 1.00：每篇文档与自己完全相同；
  - d0–d1 = 0.80 最高：只差 cat/dog 一个词；
  - d0–d2 = 0.46：共享 `the` 和 `cat`；
  - d1–d2 = 0.31：**只**共享 `the`，却仍有 0.31 的相似度——这完全是虚词 `the` 贡献的"虚假相似度"。

对照实验（测验 Q9）：换成不带平滑的 `ln(N/df)` 后，`the` 的权重变成 0，相似度变为 d0–d1 = 0.47、d0–d2 = 0.10、d1–d2 = 0.00，更"诚实"地反映了内容词的重叠。另外，用 scikit-learn `TfidfVectorizer()` 跑同样三句话，按词名对齐列后与本脚本的结果最大误差约 `1.1e-16`。

---

## 7. 动手改一改

1. **（易）通用余弦相似度**：改写 `cosine_similarity`，让它自己除以两个模长，并处理零向量；验证相同文档得 1.0（用 `math.isclose`）、词表不相交的文档得 0.0。
2. **（易）停用词实验**：在 `tokenize` 之后去掉 `the`、`on`，观察相似度矩阵的变化，并和 `max_df` 的思路对比。
3. **（中）`sublinear_tf`**：把 TF 改成 `1 + log(count)`（count > 0 时），观察 `the` 的权重变化。
4. **（中）n-gram 支持**（讲义练习 2）：实现 `ngrams(doc, n)`，用 bigram 重跑，观察词表大小和稀疏程度的变化。
5. **（中）拆分 fit / transform**：把 `tfidf` 拆成 `fit(train_bow) → idf` 和 `transform(bow, idf)` 两个函数，对一篇包含新词的文档做 transform，观察 OOV 被丢弃的现象。
6. **（难）TF-IDF 加权 embedding**：实现讲义中的 `tfidf_weighted_embedding`，用一张手工构造的小词向量表（如 4 维）验证加权平均的结果，再思考它和简单平均相比强调了什么。

---

## 8. 常见坑

- **`[[0] * V] * n` 共享引用**：所有行是同一个列表，`matrix[0][j] += 1` 会让每一行都变。必须用列表推导逐行创建。
- **把点积当余弦**：输入未归一化时，`cosine_similarity` 的结果没有 [-1, 1] 的意义，长文档会占便宜。
- **在全量数据（含测试集）上算 IDF**：信息泄露，离线指标虚高；线上也无法对单篇新文档计算。
- **以为 IDF 平滑后虚词就没影响**：平滑版的 "+1" 让处处出现的词权重为 1，小语料上虚词可能主导相似度——需要 `max_df`、停用词或 `sublinear_tf` 配合。
- **情感任务删停用词**：英文停用词表包含 `not`，删掉后 "not good" 只剩 "good"。
- **用浮点 `==` 判断相似度为 1**：相同文档实测可能得到 `1.0000000000000002`，测试中要用 `math.isclose`。
