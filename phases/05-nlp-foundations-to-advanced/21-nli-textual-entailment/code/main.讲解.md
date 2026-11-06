# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 21 节 自然语言 Inference — 文本蕴涵 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`、`collections.Counter`），不需要 transformers 或 GPU

---

## 1. 这份代码在考察什么

讲义 Step 4 说得很直白：这是一个"不具竞争力"的玩具分类器，目的是让你看清 **NLI 任务的形状**——两段文本进，三分类标签出。具体来说：

1. **任务接口**：`predict_nli(premise, hypothesis) -> (label, score)`，与 DeBERTa-MNLI 等真实模型的输入输出形状一致。
2. **两个浅层特征**：内容词重叠率（假设有多少被前提覆盖）+ 否定词是否一致。
3. **规则决策**：用阈值和 if 分支把两个特征映射到 entailment / contradiction / neutral。
4. **评估方式**：逐例打印、计算准确率、输出 (gold, pred) 混淆矩阵。
5. **反面教材**：这两个特征恰恰是讲义 Pitfalls 中的"词汇重叠启发式"和"否定词捷径"，真实模型在 HANS/ANLI 上失败也是因为偷偷学了它们。

> 一句话：**看懂这个玩具为什么能拿 83%、又为什么不可靠，就理解了 NLI 评估中"捷径学习"的全部要害。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NEGATIONS` | 常量集合 | 9 个否定词 | 否定检测 / hypothesis-only 捷径 |
| `STOP` | 常量集合 | 冠词、介词、代词、助动词等停用词 | 只保留内容词 |
| `tokenize(text)` | 函数 | 小写化 + 正则取字母数字串 | 分词 |
| `content_words(tokens)` | 函数 | 去掉停用词和否定词 | 内容词抽取 |
| `has_negation(tokens)` | 函数 | 是否包含否定词 | 否定特征 |
| `lexical_overlap(p, h)` | 函数 | 假设内容词中被前提覆盖的比例 | 词汇重叠特征 |
| `predict_nli(premise, hypothesis)` | 函数 | 两个特征 → 三分类标签 + 重叠分数 | NLI 分类器 |
| `evaluate(examples)` | 函数 | 逐例预测、打印、统计准确率和混淆矩阵 | 评估 |
| `main()` | 演示入口 | 12 个手写样本（每组前提配多个假设） | — |

数据流：`(premise, hypothesis) → tokenize → content_words / has_negation → lexical_overlap → if 规则 → label`，再由 `evaluate` 汇总。

---

## 3. 逐段精讲

### 3.1 两张词表

```python
NEGATIONS = {"not", "no", "never", "nobody", "nothing", "neither", "nor", "none", "without"}
STOP = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "of", "in", "on", "at", "to", "for", "with", "by", "as", "and", "or", "but",
        "there", "this", "that", "these", "those", "it", "its", "i", "he", "she", "we", "they",
        "do", "does", "did", "has", "have", "had", "will", "would", "could", "should"}
```

- 都用 `set`（花括号、无冒号），成员判断是 O(1)。
- `NEGATIONS` 正是讲义 Pitfalls 点名的 "not, nobody, never" 一类词——它们在 SNLI 中与 contradiction 强相关。
- `STOP` 里有 `has`、`have`、`did` 等助动词，所以 "John **has** a dog" 的内容词只剩 `john, dog`。
- ⚠️ 注意 `his` 不在 `STOP` 中，而 `he`、`she` 在；这种手写词表的不一致在规则系统里非常常见，会悄悄影响分数。
- ⚠️ `"n't"` 没有被处理：`tokenize("didn't")` 会得到 `["didn", "t"]`，否定检测完全漏掉。

### 3.2 分词与内容词

```python
def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def content_words(tokens):
    return [t for t in tokens if t not in STOP and t not in NEGATIONS]


def has_negation(tokens):
    return any(t in NEGATIONS for t in tokens)
```

- `tokenize` 先小写，再抽取连续的字母/数字，标点自然被丢弃。
- `content_words` 去掉否定词，是为了让"有没有否定"与"内容是否重叠"成为**两个独立特征**：`"There is no cat in the room"` 的内容词仍是 `cat, room`，与无否定版本相同。
- `any(... for ...)` 遇到第一个 True 就停止（短路），比先建列表再判断更高效。
- ⚠️ 没有词形还原：`stocks` 与 `stock`、`ran` 与 `run` 被视为不同的词。这直接导致了输出中的一个错例（见第 6 节）。

### 3.3 词汇重叠率

```python
def lexical_overlap(prem_tokens, hyp_tokens):
    p_content = content_words(prem_tokens)
    h_content = content_words(hyp_tokens)
    if not h_content:
        return 0.0
    p_set = set(p_content)
    covered = sum(1 for t in h_content if t in p_set)
    return covered / len(h_content)
```

- 计算的是"**假设**的内容词中，有多少比例出现在前提里"，分母是假设长度。这个方向是有意设计的：蕴涵要求"假设说的东西前提都说过"，前提里多出来的信息无所谓。所以它是**不对称**的，与 NLI 本身的不对称性一致。
- 前提转成 `set` 后查找是 O(1)；假设保留为 list，重复词会被重复计数。
- `if not h_content: return 0.0`：假设全是停用词时避免除以 0。
- ⚠️ 这是**词袋**比较：完全不看语序。`"The doctor saw the lawyer"` 与 `"The lawyer saw the doctor"` 的重叠率是 1.0——这就是讲义提到的 HANS 陷阱。

### 3.4 决策规则

```python
def predict_nli(premise, hypothesis):
    p_tokens = tokenize(premise)
    h_tokens = tokenize(hypothesis)

    overlap = lexical_overlap(p_tokens, h_tokens)
    p_neg = has_negation(p_tokens)
    h_neg = has_negation(h_tokens)

    if overlap >= 0.5 and p_neg != h_neg:
        return "contradiction", overlap
    if overlap >= 0.5:
        return "entailment", overlap
    if overlap > 0 and p_neg != h_neg:
        return "contradiction", overlap
    return "neutral", overlap
```

四条规则可以画成一张表：

| overlap | 否定是否一致 | 预测 |
|---|---|---|
| ≥ 0.5 | 不一致 | contradiction |
| ≥ 0.5 | 一致 | entailment |
| (0, 0.5) | 不一致 | contradiction |
| 其他 | — | neutral |

- **直觉**："说的是同一件事 + 一边否定一边肯定" → 矛盾；"说的是同一件事 + 极性一致" → 蕴涵；"没怎么谈同一件事" → 中立。
- 规则顺序很重要：先判断矛盾再判断蕴涵，否则高重叠的矛盾句会被第二条规则提前截走。
- 第三条规则允许**低重叠**时也判矛盾，只要有一点点话题关联且否定不一致。这让 `"Stocks did not move today"` 仅凭 `today` 一个词的重叠就被判为 contradiction——标签对了，理由却很牵强。
- `p_neg != h_neg` 用"不等"表示异或：恰好一边有否定。两边都有否定（双重否定、都否定）时视为极性一致。
- 返回的第二个值是 overlap，打印时标为 `conf`，但它**不是**校准过的概率，只是特征值。
- ⚠️ 与真实模型的根本差异：DeBERTa 读入 `[CLS] premise [SEP] hypothesis [SEP]`，通过 attention 建模两段文本中词与词的对齐关系，再用交叉熵训练三分类；这里没有任何训练和损失函数，阈值 0.5 是手定的。

### 3.5 评估函数

```python
def evaluate(examples):
    correct = 0
    confusion = Counter()
    for premise, hypothesis, gold in examples:
        pred, conf = predict_nli(premise, hypothesis)
        ok = pred == gold
        correct += int(ok)
        confusion[(gold, pred)] += 1
        tag = "  OK" if ok else "MISS"
        print(f"  [{tag}] gold={gold:<13} pred={pred:<13} conf={conf:.2f}")
        # ...
    return correct, len(examples), confusion
```

- 用 `Counter` 以 `(gold, pred)` 元组为 key 计数，就是一个稀疏的**混淆矩阵**；对角线（gold == pred）是答对的。
- 返回三元组，由调用方决定怎么展示，打印和统计各司其职。
- `main()` 里用 `sorted(confusion.items())` 让输出按字母序排列，结果稳定可比。

### 3.6 样本设计

```python
    examples = [
        ("A cat is sleeping on the couch.", "There is a cat in the room.", "entailment"),
        ("A cat is sleeping on the couch.", "There is no cat in the room.", "contradiction"),
        ("A cat is sleeping on the couch.", "The dog chased the ball.", "neutral"),
        # ...
    ]
```

- 每个前提配 2–3 个假设，覆盖三个标签——这与 SNLI/MNLI 的标注方式一致（标注者看一个前提，分别写一个蕴涵、矛盾、中立的假设）。
- 但也继承了 SNLI 的问题：4 个矛盾假设**全部**含否定词，5 个蕴涵假设全都不含。只看假设"有没有否定词"就能答对 9/12（见测验 Q9），这就是讲义说的 hypothesis-only 捷径。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库、手写规则 | 零依赖，几秒看懂"NLI 的输入输出形状" | 生产用 DeBERTa-v3-MNLI 等 cross-encoder |
| 重叠率以假设为分母 | 与"假设被前提覆盖"的蕴涵直觉一致，体现不对称性 | 忽略语序和句法角色，HANS 类样本必错 |
| 否定词单独作特征 | 抓住最强的单一信号 | 双重否定、`n't`、反义词全部漏掉 |
| 阈值 0.5 手定 | 简单 | 真实模型输出校准概率，阈值在验证集上调 |
| 无词形还原 | 代码短 | `stocks/stock` 不匹配；生产模型通过子词与上下文表示天然处理 |
| `(gold, pred)` 计数的混淆矩阵 | 一眼看出错在哪一类 | 生产中还要按错误类型（否定、数字、语序）做切片分析 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 集合字面量 | `NEGATIONS = {"not", "no", ...}` | 花括号无冒号是 `set`；成员判断 O(1) |
| 多行括号续行 | `STOP = {"a", "an", ...` 跨多行 | 括号内换行无需反斜杠 |
| 正则 `re.findall` | `re.findall(r"[a-z0-9]+", text.lower())` | 返回所有匹配子串；`[a-z0-9]+` 匹配连续字母数字 |
| 列表推导式 + 多条件 | `[t for t in tokens if t not in STOP and t not in NEGATIONS]` | 过滤式推导 |
| `any` + 生成器 | `any(t in NEGATIONS for t in tokens)` | 有一个为真即返回 True，短路求值 |
| `sum` 计数技巧 | `sum(1 for t in h_content if t in p_set)` | 满足条件的元素个数 |
| 早返回 | `if not h_content: return 0.0` | 空列表为假值，提前处理边界 |
| 返回元组 / 解包 | `return "contradiction", overlap`；`pred, conf = predict_nli(...)` | 一次返回多个值 |
| `!=` 作异或 | `p_neg != h_neg` | 两个布尔值不同即"恰好一个为真" |
| 循环中解包三元组 | `for premise, hypothesis, gold in examples` | 每个元素是 `(前提, 假设, 标签)` |
| `Counter` 以元组为 key | `confusion[(gold, pred)] += 1` | 元组可哈希，适合做多维计数 |
| `sorted(dict.items())` | `sorted(confusion.items())` | 按 key 排序后遍历，输出稳定 |
| f-string 对齐与精度 | `f"{gold:<13}"`、`f"{conf:.2f}"`、`f"{100 * correct / total:.1f}%"` | `<13` 左对齐占 13 格；`.2f` 两位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出（节选）：

```text
=== toy NLI classifier (lexical overlap + negation) ===

  [  OK] gold=entailment    pred=entailment    conf=0.50
         p: A cat is sleeping on the couch.
         h: There is a cat in the room.
  [  OK] gold=contradiction pred=contradiction conf=0.50
         p: A cat is sleeping on the couch.
         h: There is no cat in the room.
  ...
  [MISS] gold=entailment    pred=neutral       conf=0.25
         p: The stock market rallied today.
         h: Stocks went up today.
  [  OK] gold=contradiction pred=contradiction conf=0.33
         p: The stock market rallied today.
         h: Stocks did not move today.
  [MISS] gold=entailment    pred=neutral       conf=0.33
         p: The chef served a tasty meal.
         h: The chef prepared food.
  ...

accuracy: 10/12 (83.3%)

confusion (gold -> pred):
  contradiction  -> contradiction   4
  entailment     -> entailment      3
  entailment     -> neutral         2
  neutral        -> neutral         3

note: this classifier exploits two shallow features.
production NLI uses DeBERTa-v3-MNLI at ~91% on MNLI-matched.
the shape of the task — (premise, hypothesis) -> label — stays identical.
```

逐项解读：

- **第一组**：假设 `There is a cat in the room.` 的内容词是 `cat, room`，`cat` 被覆盖 → 0.50，恰好压线判为 entailment。加上 `no` 后内容词不变、否定不一致 → contradiction。两个"正确"都踩在 0.5 的阈值上，非常脆弱。
- **`Stocks did not move today.` 判对了，但理由牵强**：只有 `today` 重叠（1/3 = 0.33），靠第三条规则"低重叠 + 否定不一致"判为矛盾。
- **两个错例都是 entailment → neutral**：
  - `stocks` ≠ `stock`（缺词形还原），`went up` 与 `rallied` 是同义改写 → 1/4 = 0.25。
  - `prepared food` 与 `served a tasty meal` 只有 `chef` 重叠 → 1/3。
  - 这两类（词形变化、同义改写）正是需要语义表示的地方。
- **混淆矩阵**：contradiction 4/4 全对，与"矛盾假设都含否定词"的数据特点吻合；错误全部集中在"蕴涵被判为中立"，说明词汇重叠对改写极不鲁棒。
- **最后三行**：提醒你真实 NLI 用 DeBERTa-v3 在 MNLI-matched 上约 91%，任务形状不变。

---

## 7. 动手改一改

1. 加一个 hypothesis-only baseline：只看假设是否含否定词，统计它在这 12 个例子上的准确率（应为 9/12），与 10/12 对比（参考测验 Q9）。
2. 加入 HANS 风格的对抗样本：`("The doctor saw the lawyer.", "The lawyer saw the doctor.", "neutral")`、`("The doctor near the actor danced.", "The actor danced.", "neutral")`，观察准确率变化。
3. 在 `content_words` 之后加极简词形归一化（去掉长度大于 3 的词尾 `s`），验证准确率升到 11/12（参考测验 Q10）。
4. 处理缩写否定：在 `tokenize` 前把 `n't` 替换为 ` not`，验证 `"John didn't walk his dog."` 能被识别为否定。
5. 把 `predict_nli` 包装成 `faithfulness(answer, context)`：按句拆论断、逐条判定、返回蕴涵比例；构造一个把 1889 改成 1989 的答案，看它能否被识别（参考测验 Q11）。
6. 进阶：如果环境中有 `transformers`，用 `pipeline("text-classification", model="facebook/bart-large-mnli", top_k=None)` 跑同样 12 个例子 + 对抗样本，对比两者的错误类型。

---

## 8. 常见坑

- **把重叠当蕴涵**：词袋重叠完全不看语序和句法角色，"医生看律师"与"律师看医生"被判为蕴涵。
- **否定检测过于简单**：双重否定、`n't` 缩写、`fail to`、反义词（bad/good）都会漏掉。
- **把特征值当置信度**：输出里的 `conf` 只是 overlap，不是概率，不能直接拿来设阈值做业务决策。
- **评估集太小、太"干净"**：12 个手写样本里否定词与矛盾完全对应，准确率被捷径抬高；评估一定要加对抗子集。
- **停用词表与归一化顺序**：若先做词形归一化再过滤停用词，`does → doe`、`this → thi` 会逃过停用词过滤。
