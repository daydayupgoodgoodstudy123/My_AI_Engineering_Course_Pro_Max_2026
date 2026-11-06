# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到高级 · 第 06 节 命名实体识别 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，瞬间完成） ｜ **依赖**：仅 Python 标准库（连 `import` 都没有），不需要 spaCy / sklearn-crfsuite / transformers

---

## 1. 这份代码在考察什么

NER 的模型可以越来越复杂（CRF、BiLSTM-CRF、BERT、LLM），但所有方法都绕不开几块"地基"。这份脚本把这些地基单独拿出来：

1. **BIO 标注与片段的互相转换**：`spans_to_bio` 把"实体在哪、是什么类型"变成逐 token 标签（训练数据怎么准备），`bio_to_spans` 把模型输出的逐 token 标签还原成实体（预测结果怎么用、怎么评估）。
2. **规则 + 词典基线**：`rule_based_ner` 展示词典方法"认识的都对、不认识的全漏、同名不同义分不清"的特点。
3. **手工特征**：`word_shape` 和 `token_features` 就是讲义中 CRF 所用特征的原型——大小写模式是识别专有名词的强信号。
4. **往返一致性测试**：`main` 的最后一段验证"片段 → BIO → 片段"能够完整还原，这是检验标注转换代码的标准手段。

> 一句话：**不管上层用什么模型，"片段 ↔ BIO"的转换与"实体级"的解码都必须先写对，否则训练数据和评估结果都是错的。**

⚠️ 讲义中的 CRF（sklearn-crfsuite）、BiLSTM-CRF（PyTorch）以及 spaCy / Hugging Face 的用法都没有放进本脚本。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ORG_GAZETTEER` / `GPE_GAZETTEER` / `PRODUCT_GAZETTEER` | 集合常量 | 三类实体的小词典 | gazetteer |
| `word_shape(word)` | 函数 | 大写 → `X`、小写 → `x`、数字 → `d`、其他字符原样保留 | 词形特征 |
| `rule_based_ner(tokens)` | 函数 | 逐 token 查词典，命中则标 `B-类型`，否则 `O` | 规则基线 |
| `spans_to_bio(tokens, spans)` | 函数 | `(start, end, label)` 片段列表 → BIO 标签列表 | 标注编码 |
| `bio_to_spans(tokens, labels)` | 函数 | BIO 标签列表 → 片段列表（严格解码） | 标注解码 |
| `token_features(token, prev_token, next_token)` | 函数 | 返回一个 token 的特征字典（CRF 风格） | 手工特征 |
| `main()` | 函数 | 规则 NER 演示 + 词形示例 + 往返一致性测试 | 演示入口 |

调用关系：`main → rule_based_ner → bio_to_spans`（预测路径）；`main → spans_to_bio → bio_to_spans`（往返测试）；`main → word_shape`。`token_features` 定义了但 `main` **没有调用**，它是为讲义中 CRF 步骤准备的。

---

## 3. 逐段精讲

### 3.1 词典与 `rule_based_ner`

```python
ORG_GAZETTEER = {"Apple", "Google", "Microsoft", "OpenAI", "Meta", "Amazon", "Netflix", "Anthropic"}
GPE_GAZETTEER = {"US", "USA", "UK", "India", "Germany", "France", "Japan"}
PRODUCT_GAZETTEER = {"iPhone", "Android", "Windows", "ChatGPT", "Claude", "Gemini"}


def rule_based_ner(tokens):
    labels = []
    for token in tokens:
        if token in ORG_GAZETTEER:
            labels.append("B-ORG")
        elif token in GPE_GAZETTEER:
            labels.append("B-GPE")
        elif token in PRODUCT_GAZETTEER:
            labels.append("B-PRODUCT")
        else:
            labels.append("O")
    return labels
```

- GPE = Geo-Political Entity（国家、城市等地缘政治实体），是 OntoNotes / spaCy 标签体系中的类型。
- 用**集合**存词典，`in` 判断平均 O(1)；真实词典有数百万条（讲义："scraped from Wikipedia and DBpedia"）。
- `if / elif` 的顺序就是**类型优先级**：一个词若同时出现在两个词典里，先匹配到的类型胜出。
- **大小写敏感**：`apple` 不会被识别，`Apple` 一定被识别为 ORG——无论句子说的是公司还是水果。讲义："Coverage is good. Disambiguation ... is terrible. That is why statistical models won."
- ⚠️ 只做**单 token** 匹配，所以只会输出 `B-` 而从不输出 `I-`；`New York` 这样的多 token 实体完全识别不了（测验 Q11 给出了最长匹配的多 token 版本）。

### 3.2 `word_shape`：把单词变成"形状"

```python
def word_shape(word):
    out = []
    for c in word:
        if c.isupper():
            out.append("X")
        elif c.islower():
            out.append("x")
        elif c.isdigit():
            out.append("d")
        else:
            out.append(c)
    return "".join(out)
```

- 例：`Apple → Xxxxx`、`iPhone → xXxxxx`、`IBM → XXX`、`USA-2024 → XXX-dddd`、`apple → xxxxx`。
- **为什么有用**：词形把无数个具体的词归并成少数几种"模式"。模型在训练集中学到"`Xxxxx` 形状的词常常是专有名词"，就能把这个规律推广到训练中没见过的新名字上——这正是词典做不到的泛化。
- 先 `append` 到列表、最后 `"".join(out)` 一次拼接，是 Python 中构造字符串的高效惯用法（避免在循环中反复 `+=` 创建新字符串）。
- `str.isupper()` / `islower()` 支持 Unicode，`Ünïcode` 也能得到 `Xxxxxxx`。
- 常见扩展（本代码未做）："短形状"会把连续相同的字符压缩成一个，如 `Xxxxx → Xx`，进一步降低特征稀疏度。

### 3.3 `spans_to_bio`：片段 → BIO

```python
def spans_to_bio(tokens, spans):
    labels = ["O"] * len(tokens)
    for start, end, label in spans:
        labels[start] = f"B-{label}"
        for i in range(start + 1, end):
            labels[i] = f"I-{label}"
    return labels
```

- 片段用 `(start, end, label)` 表示，**左闭右开**：`(1, 4, "GPE")` 覆盖下标 1、2、3。这与 Python 切片 `tokens[1:4]` 一致，所以 `main` 中可以直接 `" ".join(sentence[start:end])` 取出实体文本。
- 先全部初始化为 `O`，再为每个片段写入一个 `B-` 和若干 `I-`。
- `["O"] * len(tokens)` 用列表乘法初始化：元素是不可变的字符串，所以这里**没有**共享引用的问题（与第 02 节 `[[0] * V] * n` 的坑不同）。
- ⚠️ **没有任何校验**：
  - 两个片段重叠时，后写的覆盖先写的，可能产生 `B-ORG I-ORG I-ORG I-FAC` 这样的非法序列，且结果依赖片段顺序（嵌套实体问题，测验 Q10）；
  - 越界下标会抛 `IndexError` 或被负索引"悄悄"写到末尾。
- `tokens` 参数只用来取长度，片段内容由调用方保证正确。

### 3.4 `bio_to_spans`：BIO → 片段（严格解码）

```python
def bio_to_spans(tokens, labels):
    spans = []
    current = None
    for i, label in enumerate(labels):
        if label.startswith("B-"):
            if current:
                spans.append(current)
            current = (i, i + 1, label[2:])
        elif label.startswith("I-") and current and current[2] == label[2:]:
            current = (current[0], i + 1, current[2])
        else:
            if current:
                spans.append(current)
                current = None
    if current:
        spans.append(current)
    return spans
```

这是一个以 `current`（当前正在构建的实体，或 `None`）为状态的扫描器：

| 当前标签 | 条件 | 动作 |
|---------|------|------|
| `B-X` | — | 若有未完成实体先收尾；开启新实体 `(i, i+1, X)` |
| `I-X` | 当前实体存在且类型同为 X | 把当前实体的右边界延长到 `i+1` |
| `O`，或不匹配的 `I-Y` | — | 若有未完成实体则收尾，`current = None` |
| 循环结束 | 仍有未完成实体 | 收尾 |

- `label[2:]` 去掉 `B-` / `I-` 前缀，得到类型名。
- 元组不可变，所以"延长实体"是**创建一个新元组**替换 `current`。
- 最后的 `if current: spans.append(current)` 不可省略：句子以实体结尾时（如 `... visited OpenAI`），最后一个实体只有在这里才会被加入。
- ⚠️ **严格策略**：前面没有同类型 `B-` / `I-` 的"孤儿 `I-`"会被**直接丢弃**，例如 `["O", "I-ORG", "I-ORG"] → []`。而 conlleval / seqeval 的默认宽松模式会把孤儿 `I-X` 当作新实体的开始。两种策略都合理，但训练、解码与评估必须统一（测验 Q9 给出宽松版实现）。
- `tokens` 参数在函数体中**没有被使用**，保留它只是为了与 `spans_to_bio` 的签名对称。

### 3.5 `token_features`：CRF 风格的特征字典

```python
def token_features(token, prev_token, next_token):
    return {
        "lower": token.lower(),
        "is_upper": token.isupper(),
        "is_title": token.istitle(),
        "has_digit": any(c.isdigit() for c in token),
        "suffix_3": token[-3:].lower(),
        "shape": word_shape(token),
        "prev_lower": prev_token.lower() if prev_token else "<BOS>",
        "next_lower": next_token.lower() if next_token else "<EOS>",
    }
```

| 特征 | 例：`token_features("iPhone", "over", "sales")` | 作用 |
|------|-----------------------------------------------|------|
| `lower` | `'iphone'` | 词本身（大小写归一） |
| `is_upper` | `False` | 全大写缩写（IBM、USA） |
| `is_title` | `False` | 首字母大写（Apple 是 `True`；注意 `iPhone` 不是 title case） |
| `has_digit` | `False` | 型号、年份 |
| `suffix_3` | `'one'` | 后缀（-son、-ing、-ese 等提示类型或词性） |
| `shape` | `'xXxxxx'` | 大小写模式 |
| `prev_lower` / `next_lower` | `'over'` / `'sales'` | 上下文窗口（"Mr. X"、"X Inc."） |

- 句首 / 句尾没有前后词时，用 `<BOS>` / `<EOS>` 占位，让模型知道"这是句首"（句首大写不一定是专有名词，这个特征很重要）。
- `any(c.isdigit() for c in token)`：只要有一个字符是数字就为 `True`，遇到第一个数字立即停止（短路）。
- 返回的是**字典**，正是 sklearn-crfsuite 要求的输入格式：每个句子是"特征字典的列表"。讲义 Step 4 的 `to_features` 在此基础上增加了 `BOS` / `EOS` 布尔特征。
- `main()` 中没有调用这个函数，它是给你接到 CRF 上用的。

### 3.6 `main`：三段演示

```python
def main():
    sentence = "Apple sued Google over iPhone sales in the US .".split()
    labels = rule_based_ner(sentence)
    spans = bio_to_spans(sentence, labels)
    # ...
    for start, end, kind in spans:
        entity = " ".join(sentence[start:end])
        print(f"  [{start}:{end}] {kind:8s} {entity!r}")
    # ...
    tokens = "The New York City mayor visited OpenAI .".split()
    gold_spans = [(1, 4, "GPE"), (6, 7, "ORG")]
    bio = spans_to_bio(tokens, gold_spans)
    recovered = bio_to_spans(tokens, bio)
    # ...
    print(f"  match    : {gold_spans == recovered}")
```

- `.split()` 按空白切分作为 tokenizer——所以句号前特意留了空格（`US .`），让 `.` 成为独立 token。真实系统中 tokenization 会直接影响实体边界。
- 第一段：规则 NER → 片段，展示"预测路径"。
- 第二段：5 个词的形状，对比 `Apple` 与 `apple` 的形状差异。
- 第三段：**往返测试**。`gold_spans == recovered` 比较两个列表（逐元素比较元组），`True` 说明编码与解码互为逆运算——这正是讲义练习 1 要求的"round-trip consistency"。
- `{kind:8s}`：类型名左对齐占 8 格；`{entity!r}`：用 `repr` 打印，带引号，便于看清实体边界上有没有多余空格。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用集合做单 token 词典匹配 | 实现最简单，O(1) 查找 | 无法处理多 token 实体与消歧；生产中用 Trie / Aho-Corasick 做多模式匹配，并把词典命中作为统计模型的特征 |
| 片段用左闭右开区间 | 与 Python 切片一致，长度 = `end - start` | 需要和其他工具（如字符级偏移）约定清楚 |
| `bio_to_spans` 严格解码 | 只承认合法实体，精确率高 | 孤儿 `I-` 被丢弃；与 seqeval 默认的宽松模式不同，评估时要统一 |
| `spans_to_bio` 不做校验 | 代码短 | 嵌套 / 重叠片段被静默覆盖；准备训练数据时应加校验 |
| 手工特征返回字典 | 直接对接 sklearn-crfsuite | 特征工程依赖经验；BiLSTM-CRF / BERT 用学习到的特征替代 |
| 只用标准库 | 零依赖、随处可跑 | CRF、神经网络与 spaCy 部分需按讲义另行安装依赖 |
| 往返一致性测试 | 用最小成本验证编码 / 解码正确 | 只覆盖了合法、不重叠的输入；边界情况需额外测试 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 集合字面量 | `{"Apple", "Google", ...}` | 无序、去重，成员判断快 |
| `str.split()` | `"Apple sued ... US .".split()` | 按任意空白切分成列表 |
| 字符串判断方法 | `c.isupper()`、`c.islower()`、`c.isdigit()`、`token.istitle()` | 字符 / 字符串属性判断，支持 Unicode |
| `"".join(list)` | `"".join(out)`、`" ".join(sentence[start:end])` | 把字符串列表拼成一个字符串 |
| 列表乘法初始化 | `["O"] * len(tokens)` | 元素不可变时安全 |
| 元组解包遍历 | `for start, end, label in spans` | 一次拆出三个字段 |
| `str.startswith` | `label.startswith("B-")` | 前缀判断 |
| 字符串切片 | `label[2:]`、`token[-3:]` | 去掉前两个字符 / 取最后三个字符 |
| `None` 作为"无"状态 | `current = None`；`if current:` | 元组非空即为真，`None` 为假 |
| 元组重建 | `current = (current[0], i + 1, current[2])` | 元组不可变，只能新建 |
| `any` + 生成器 | `any(c.isdigit() for c in token)` | 有一个满足即 `True`，短路求值 |
| 条件表达式 | `prev_token.lower() if prev_token else "<BOS>"` | 处理句首 / 句尾 |
| 字典字面量返回 | `return {"lower": ..., ...}` | 返回特征字典 |
| 列表相等比较 | `gold_spans == recovered` | 逐元素比较，元组也逐元素比较 |
| f-string 宽度与 `!r` | `f"{kind:8s} {entity!r}"`、`f"{tok:12s}"` | 对齐输出；`!r` 输出带引号的 `repr` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，纯标准库）的完整输出：

```text
tokens  : ['Apple', 'sued', 'Google', 'over', 'iPhone', 'sales', 'in', 'the', 'US', '.']
labels  : ['B-ORG', 'O', 'B-ORG', 'O', 'B-PRODUCT', 'O', 'O', 'O', 'B-GPE', 'O']
spans   :
  [0:1] ORG      'Apple'
  [2:3] ORG      'Google'
  [4:5] PRODUCT  'iPhone'
  [8:9] GPE      'US'

word shapes (useful CRF features):
  Apple        -> shape Xxxxx
  iPhone       -> shape xXxxxx
  IBM          -> shape XXX
  USA-2024     -> shape XXX-dddd
  apple        -> shape xxxxx

round-trip (spans -> BIO -> spans):
  tokens   : ['The', 'New', 'York', 'City', 'mayor', 'visited', 'OpenAI', '.']
  bio      : ['O', 'B-GPE', 'I-GPE', 'I-GPE', 'O', 'O', 'B-ORG', 'O']
  gold     : [(1, 4, 'GPE'), (6, 7, 'ORG')]
  recovered: [(1, 4, 'GPE'), (6, 7, 'ORG')]
  match    : True
```

逐段解读：

- **规则 NER**：示例句中的 4 个实体全部命中，而且类型正确——包括 spaCy 小模型在讲义中标错的 `iPhone`（讲义显示 `en_core_web_sm` 把它标成了 ORG）。这恰恰说明了词典方法的特点：**认识的实体精度很高**。但换一句 `"I ate an Apple pie in New York"`，它会把 `Apple` 标成 ORG、完全漏掉 `New York`（测验 Q7）。
- **片段输出**：`[0:1]` 等是左闭右开区间，所有实体都是单 token，所以每个区间长度为 1——规则方法从来不产生 `I-` 标签。
- **词形**：`Apple`（`Xxxxx`）与 `apple`（`xxxxx`）只差首字母大小写，形状就完全不同——这是区分"公司 Apple"和"水果 apple"的一个线索（虽然句首的 `Apple` 也会是 `Xxxxx`，所以还需要 `prev_lower = <BOS>` 这样的特征配合）。`USA-2024` 中的连字符原样保留在形状里。
- **往返测试**：`New York City` 被编码为 `B-GPE I-GPE I-GPE`，解码后恢复出完全相同的片段，`match: True`，说明在**合法、不重叠**的输入上，编码与解码互为逆运算。

---

## 7. 动手改一改

1. **（易）BILOU 版本**：写 `spans_to_bilou` 和 `bilou_to_spans`，在 `main` 的例子上验证往返一致（`New York City → B-GPE I-GPE L-GPE`，`OpenAI → U-ORG`）。
2. **（易）宽松解码**：实现把孤儿 `I-X` 当作新实体开头的 `bio_to_spans_lenient`，对比两种策略在 `["O", "I-ORG", "I-ORG"]` 上的输出（测验 Q9）。
3. **（中）多 token 词典匹配**：把词典改为"token 元组 → 类型"，用最长匹配实现 `gazetteer_ner`，让 `New York City` 被完整识别（测验 Q11）。
4. **（中）实体级评估**：写 `entity_prf(gold_labels, pred_labels)`，先解码成片段集合再算 P / R / F1；用 `["O","B-GPE","I-GPE","I-GPE","O","O","B-ORG","O"]` 作真实值、把 `City` 预测成 `O` 作预测值，验证实体级 F1 为 0.5 而 token 准确率为 0.875。
5. **（中）短形状特征**：给 `word_shape` 加一个参数，把连续相同的形状字符压缩为一个（`Xxxxx → Xx`），并加入 `token_features`。
6. **（难）接入 CRF**：如果环境中能安装 sklearn-crfsuite，用 `token_features` 为每个 token 生成特征，按讲义 Step 4 训练一个 CRF，并用 seqeval 报告实体级 F1。

---

## 8. 常见坑

- **用 token 级准确率评估 NER**：绝大多数 token 是 `O`，"全部预测 O"也能得到很高的 token 准确率；必须报告实体级 F1。
- **忘记在循环结束后收尾**：`bio_to_spans` 若省掉最后的 `if current: spans.append(current)`，句末实体会丢失——这是手写解码器最常见的 bug。
- **区间约定不一致**：一处用左闭右开、另一处用闭区间，实体会多一个或少一个 token。
- **嵌套片段被静默覆盖**：`spans_to_bio` 不报错，后写的片段覆盖先写的，训练数据里悄悄出现非法序列。
- **解码策略与评估工具不一致**：自己的严格解码 + seqeval 的宽松评估，或者反过来，会让 F1 对不上。
- **大小写处理**：`rule_based_ner` 区分大小写；如果预处理阶段把文本全部小写化，大小写这个最强的特征就没了。
