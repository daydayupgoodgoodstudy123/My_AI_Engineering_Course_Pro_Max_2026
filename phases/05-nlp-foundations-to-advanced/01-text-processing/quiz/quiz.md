# 测验 · 文本处理 — Tokenization、词干提取、词形还原（Text Processing — Tokenization, Stemming, Lemmatization）

> **阶段 05 · NLP 基础到高级 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要预处理 | 模型读的是离散的整数 ID，不是字符串；预处理是"连续语言 → 离散 token"的桥梁 |
| 2 | Tokenization 粒度 | token 是"模型消费的单位"：传统 NLP 用词级，Transformer 用 subword，无空格语言可用字符级 |
| 3 | 正则 tokenizer 与优先级 | 正则多分支 `A|B|C` 在同一位置从左到右尝试；`3pm` 被切成 `3` + `pm`，URL、邮箱、hashtag 都会被切碎 |
| 4 | Stemming（词干提取） | 基于规则砍后缀：快、激进、"笨"；结果不一定是真实单词，`organization → organ` 是典型的过度合并 |
| 5 | Porter step 1a 与规则顺序 | `sses→ss`、`ies→i`、`ss→ss`、`s→''`；规则相互竞争、先匹配者胜，顺序比单条规则更重要 |
| 6 | Lemmatization（词形还原） | 还原为词典形式，需要形态学知识（查表 / 形态分析器）：`ran→run`、`better→good` |
| 7 | 词性（POS）是 lemma 的前提 | 同一个词在不同词性下 lemma 不同；NLTK 的 Penn Treebank 标签要翻译成 WordNet 的 `v/a/r/n` |
| 8 | 选型经验 | 追求速度、能容忍噪声（搜索索引、粗分类）→ stem；在意含义（QA、语义检索、用户可见文本）→ lemmatize；Transformer 流水线 → 直接用模型自带 tokenizer |
| 9 | 两个生产级失败模式 | **可复现性漂移**（库升级改变切分结果）与**训练/推理不一致**（训练做了预处理、上线没做）——前者靠锁版本 + 回归测试，后者靠"把预处理函数打包进模型" |

### 核心技能（能动手做到）

- [ ] 能写出讲义中的正则 tokenizer，并**不运行代码**准确预测它对 `"Don't stop at 3pm!"`、`"naïve café"` 的切分结果
- [ ] 能从零实现 Porter step 1a，并用 `caresses / ponies / caress / cats` 验证；能解释为什么 `sses` 规则必须排在 `s` 规则之前
- [ ] 能实现"查表 + 后缀回退"的 lemmatizer，并指出 `watched`、`sing`、`class` 等输入暴露出的缺陷
- [ ] 能用 NLTK 写出 `word_tokenize` + `PorterStemmer` + `WordNetLemmatizer` 的完整流程，**包括** Penn Treebank → WordNet 的词性映射函数
- [ ] 能用 spaCy 的 `nlp(text)` 取出每个 token 的 `text / lemma_ / pos_`
- [ ] 能扩展 tokenizer，让 URL 作为一个整体 token 保留，且不吞掉句末标点
- [ ] 能为预处理函数写一个"冻结 20 条样例句子切分结果"的回归测试，用来防御库升级带来的漂移

---

## 二、基础自测（选择题）

**Q1.** 关于 stemming 与 lemmatization，下列说法**正确**的是：

- A. stemming 的输出一定是词典中存在的真实单词
- B. 把 `better` 还原为 `good`，需要知道它是形容词的比较级，这属于 lemmatization 的工作
- C. lemmatization 通常比 stemming 更快，因为查表是 O(1)
- D. 两者都不需要词性信息

**Q2.** 本节的正则 tokenizer `[A-Za-z]+(?:'[A-Za-z]+)?|[0-9]+|[^\sA-Za-z0-9]` 对 `"Don't stop at 3pm!"` 一共切出多少个 token？

- A. 4
- B. 5
- C. 6
- D. 7

**Q3.** 如果把 `stem_step_1a` 里的 `if word.endswith("s")` 规则**挪到最前面**（先于 `sses` 规则判断），`"caresses"` 的输出会变成：

- A. `caress`
- B. `caresse`
- C. `cares`
- D. `caresses`

**Q4.** 句子 "I saw a bird" 中 `saw` 的 lemma 是 `see`，而 "Hand me the saw" 中 `saw` 的 lemma 是 `saw`。这个例子最能说明：

- A. lemmatization 必须结合词性 / 上下文才能做对
- B. stemming 在这里比 lemmatization 更准确
- C. tokenizer 把 `saw` 切错了
- D. 词表不够大，需要加更多词条

**Q5.** 用 NLTK 做词形还原时，`pos_tag` 给出的 Penn Treebank 标签 `JJR`（形容词比较级）应该翻译成 WordNet 的哪个词性代码？

- A. `"j"`
- B. `"a"`
- C. `"n"`
- D. `"r"`

**Q6.** 某团队训练时对文本做了小写化、去停用词、stemming，上线后直接把用户原始输入喂给模型，准确率明显下滑。最根本的修复方式是：

- A. 换一个更大的模型，让它对输入噪声更鲁棒
- B. 把预处理写成函数并随模型一起打包，训练和推理调用**同一份**实现
- C. 推理时关闭模型，改用规则系统
- D. 让服务端团队参照训练 notebook 自己重写一遍预处理

**Q7.** 你要微调一个 BERT 类模型做文本分类，以下哪种做法最合理？

- A. 先用 PorterStemmer 把所有词转成词干，再交给 BERT 的 tokenizer
- B. 先做 lemmatization，减少词表大小，再交给 BERT 的 tokenizer
- C. 直接使用该模型配套的 tokenizer，跳过传统的 stemming / lemmatization
- D. 用本节的正则 tokenizer 替换 BERT 的 tokenizer，速度更快

---

## 三、动手 / 代码题

**Q8.** 不运行代码，写出下面两行的输出，并解释 `naïve` 为什么会被切成那个样子。

```python
print(tokenize("naïve café, O'Neil's"))
print([stem_step_1a(w) for w in ["is", "this", "glass", "ponies"]])
```

（`tokenize` 与 `stem_step_1a` 均为本节 `code/main.py` 中的实现。）

**Q9.** 下面是本节代码中的 `lemmatize`。请找出**至少 3 个**会产生错误或不一致结果的输入，说明原因，并写一个改进版。

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

**Q10.** （讲义练习 1 的加强版）扩展 `WORD_RE`，让 URL 作为一个完整 token 保留，同时满足：

- `"Visit https://example.com today."` → `['Visit', 'https://example.com', 'today', '.']`
- `"Go to http://x.org/p, then stop"` → URL 后面的逗号要单独成 token
- 原有行为（如 `3pm → ['3', 'pm']`）不变

写出正则，并解释你把 URL 分支放在什么位置、为什么。

---

## 四、面试高频题

**Q11.**（基础必考）Stemming 和 lemmatization 有什么区别？分别在什么场景下用？各举一个失败案例。

**Q12.**（原理深挖）为什么在 BERT / GPT 这类 Transformer 流水线里，一般不再做 stemming 和 lemmatization？如果硬要做，会有什么后果？

**Q13.**（工程实践）讲义说"训练/推理预处理不一致是最常见的生产 NLP 故障"。你会如何从工程上**系统性地**避免它，以及避免 NLTK / spaCy 升级导致的切分漂移？

**Q14.**（场景设计）为一个英文电商站点设计商品搜索的文本预处理方案（索引端 + 查询端）。用户会搜 "running shoes"、"iphone 15 pro"、"3pm delivery" 这类查询。你会怎么做 tokenization、是否做 stemming / lemmatization？

**Q15.**（追问型）面试官追问："你说的这些都是英文。如果是中文、日文这种没有空格的语言，tokenization 怎么做？stemming 还有意义吗？"

---

## 五、参考答案与解析

### Q1 — 答案：B

- B 正确：`better → good` 不是任何"砍后缀"规则能做到的，必须知道它是 `good` 的比较级，这正是 lemmatization 所需的形态学知识。
- A 错：stemming 的输出常常不是真词，如 `ponies → poni`、`organization → organ`（后者还撞上了另一个真词，造成语义混淆）。
- C 错：讲义明确说 lemmatization "Slower"——它需要查表或形态分析器，还常常依赖 POS 标注这一额外步骤；stemming 只是几条字符串规则。
- D 错：stemming 不需要词性，但 lemmatization 需要（见 Q4）。

### Q2 — 答案：C

切分结果为 `["Don't", 'stop', 'at', '3', 'pm', '!']`，共 6 个：
- `Don't` 被第一分支 `[A-Za-z]+(?:'[A-Za-z]+)?` 整体吃下（内部撇号是可选组）；
- `3pm` 中字母和数字分属不同分支，于是被切成 `3` 和 `pm`——讲义专门指出了这个失败模式；
- `!` 由第三分支"任意非空白、非字母数字的单个字符"匹配。

### Q3 — 答案：B

`"caresses"` 以 `s` 结尾，`s` 规则先命中，直接去掉最后一个字母得到 `caresse`，后面的 `sses` 规则永远没机会执行。这正是讲义强调的 "Rules compete. Earlier rules win. The order matters more than any single rule." 原代码把**更长、更具体**的后缀（`sses`、`ies`、`ss`）放在**更短、更泛化**的 `s` 之前，是"最长匹配优先"的经典写法。

### Q4 — 答案：A

`saw` 作动词时是 `see` 的过去式，作名词时是"锯子"本身。只看字符串无法区分，必须先确定词性（POS），才能在词典里查到正确的 lemma。这也是讲义 Ship It 部分要求"拒绝在没有 POS 标签的情况下推荐 lemmatization"的原因。B 错在 stemming 根本不会把 `saw` 变成 `see`；C、D 与问题无关。

### Q5 — 答案：B

讲义中的映射函数：
```python
def nltk_pos_to_wordnet(tag):
    if tag.startswith("V"):
        return "v"
    if tag.startswith("J"):
        return "a"
    if tag.startswith("R"):
        return "r"
    return "n"
```
Penn Treebank 的形容词标签以 `J` 开头（`JJ / JJR / JJS`），WordNet 用 `"a"` 表示形容词。注意 WordNet 没有 `"j"` 这个代码；兜底返回 `"n"`。这个映射是"大多数教程都跳过的那一步"——不传 POS 时 `WordNetLemmatizer` 默认按名词处理，动词形式往往还原不了。

### Q6 — 答案：B

这是讲义所说的 **training / inference mismatch**：模型在"预处理后的分布"上训练，推理时却看到原始分布。正确做法是 "Ship preprocessing as a function inside the model package, not as a notebook cell the serving team rewrites"。D 恰恰是讲义点名批评的反模式：两份实现迟早会出现细微差异（比如一个先小写再分词、另一个先分词再小写）。A、C 都没有解决分布不一致的根因。

### Q7 — 答案：C

讲义的选型表写得很清楚：Transformer 流水线"you'll tokenize with the model's tokenizer anyway"，应直接使用 `tokenizers` / `transformers`，跳过传统预处理。模型在预训练时见到的是原始文本经其 subword tokenizer 切分后的分布；先 stem/lemmatize 会制造出预训练中罕见的形式（如 `poni`），反而破坏分布（详见 Q12）。D 更不行：模型的词表 ID 与 tokenizer 一一绑定，换 tokenizer 等于输入全错。

### Q8 — 参考答案

输出：
```
['na', 'ï', 've', 'caf', 'é', ',', "O'Neil", "'", 's']
['i', 'thi', 'glass', 'poni']
```

解释：
- `[A-Za-z]` 只覆盖 ASCII 字母，`ï`、`é` 不在其中，于是落入第三分支 `[^\sA-Za-z0-9]`，被当作"标点"单独成 token，`naïve` 被拆成 3 段。这说明本节正则**只适用于纯 ASCII 英文**；处理 Unicode 文本需要改用 `\w` 或 `[^\W\d_]` 之类的 Unicode 感知写法，或直接用 NLTK / spaCy。
- `O'Neil's`：撇号可选组 `(?:'[A-Za-z]+)?` 最多匹配**一次**，所以只吃到 `O'Neil`，剩下的 `'`、`s` 各自成 token。
- `is → i`、`this → thi`：step 1a 的 `s` 规则没有任何长度或"词干中必须含元音"的条件（真实 Porter 后续步骤对很多规则加了 measure 条件），短词会被误砍。`glass` 命中 `ss` 规则保持不变；`ponies` 命中 `ies → i` 得到 `poni`。

### Q9 — 参考答案

问题输入（均已实测）：

| 输入 | 输出 | 问题 |
|------|------|------|
| `lemmatize("sing", "VERB")` | `'s'` | 只要以 `ing` 结尾就砍，不检查剩余词干是否合理 |
| `lemmatize("Jumping", "VERB")` | `'Jump'` | 回退分支用的是原始 `word`，没有小写；而查表分支和最后一个分支都返回小写，**大小写不一致** |
| `lemmatize("class", "NOUN")` | `'clas'` | 名词回退只看 `s` 结尾，没排除 `ss` |
| `lemmatize("watched", "VERB")` | `'watched'` | 不处理 `ed`（讲义刻意保留的"教学时刻"） |
| `lemmatize("hopping", "VERB")` | `'hopp'` | 不处理双写辅音 |

改进版：

```python
VOWELS = set("aeiou")

def lemmatize_v2(word, pos):
    w = word.lower()                      # 1. 先统一小写，所有分支都基于 w
    if (w, pos) in LEMMA_TABLE:
        return LEMMA_TABLE[(w, pos)]
    if pos == "VERB":
        for suf in ("ing", "ed"):
            stem = w[: -len(suf)]
            # 2. 去掉后缀后必须还剩一个含元音的词干（sing / red 不动）
            if w.endswith(suf) and any(c in VOWELS for c in stem):
                # 3. 双写辅音还原：hopping -> hopp -> hop（ll/ss/zz 例外）
                if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeioulsz":
                    stem = stem[:-1]
                return stem
    if pos == "NOUN" and w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]                     # 4. class / glass / bus 不动
    return w
```

实测：`sing→sing`、`Jumping→jump`、`watched→watch`、`hopping→hop`、`falling→fall`、`class→class`、`Dogs→dog`、`bus→bus`。

仍然存在的局限：`loved → lov`（需要"补回 e"规则）、`children → children`（不规则复数）。这正是讲义的结论——规则永远补不完，生产中应使用 WordNet、spaCy morphologizer 等形态分析器。

### Q10 — 参考答案

```python
import re

WORD_RE = re.compile(
    r"https?://\S+?(?=[.,!?;:]?(?:\s|$))"   # 新增：URL 分支，放在最前面
    r"|[A-Za-z]+(?:'[A-Za-z]+)?"
    r"|[0-9]+"
    r"|[^\sA-Za-z0-9]"
)

def tokenize(text):
    return WORD_RE.findall(text)
```

实测：
```
'Visit https://example.com today.'  -> ['Visit', 'https://example.com', 'today', '.']
'Go to http://x.org/p, then stop'   -> ['Go', 'to', 'http://x.org/p', ',', 'then', 'stop']
'See https://a.b/c?x=1.'            -> ['See', 'https://a.b/c?x=1', '.']
'no url here: 3pm.'                 -> ['no', 'url', 'here', ':', '3', 'pm', '.']
```

要点：
1. **必须放在最前面**：正则在同一位置按分支从左到右尝试，若通用的 `[A-Za-z]+` 在前，`https` 会先被当作普通单词吃掉，URL 分支永远没机会。讲义原话："For production, add patterns before the general ones."
2. `\S+?` 是**非贪婪**匹配，配合前瞻 `(?=[.,!?;:]?(?:\s|$))`：URL 在"可选的一个句末标点 + 空白或字符串结尾"之前停下，从而把句号/逗号留给后面的标点分支。
3. 已知局限：URL 本身以标点结尾且后面紧跟空格的情况（如 `.../p. ` 里的点到底属于谁）在纯正则里是歧义的，生产中通常用专门的 URL 识别库。

### Q11 — 参考回答要点

- **定义**：stemming 是基于规则的后缀剥离（如 Porter 算法的多阶段规则）；lemmatization 是借助词典 + 形态学（通常还要 POS）把词还原到词典形式。
- **对比**：

| 维度 | Stemming | Lemmatization |
|------|----------|---------------|
| 依据 | 字符串规则 | 词典 + 形态分析 + 词性 |
| 速度 | 快 | 慢 |
| 输出 | 不一定是真词（`poni`） | 是词典形式（`run`、`good`） |
| 不规则形式 | 处理不了（`ran`、`better`） | 能处理 |

- **场景**：速度优先、能容忍噪声（搜索索引、粗粒度分类）→ stemming；含义重要（问答、语义检索、任何用户会看到的文本）→ lemmatization。
- **失败案例**：stemming 过度合并 `organization → organ`，让主题模型把"组织"和"器官"混成一类；lemmatization 不传 POS 时，`running` 被当名词处理，无法还原为 `run`。
- **加分点**：提到"过度合并（over-stemming）与合并不足（under-stemming）"两类错误；指出 stemming 结果绝不能直接展示给用户。

### Q12 — 参考回答要点

- **原因 1：模型自带 tokenizer**。Transformer 的词表与其 subword tokenizer 绑定，`running` 会被切成已知的 subword 片段，形态变化由模型从数据中学习，不需要人工合并。
- **原因 2：信息不该丢**。时态、单复数、比较级本身就是语义信号（"ran" vs "will run"）；stemming/lemmatization 是有损变换，丢掉的信息模型再也拿不回来。
- **原因 3：分布一致性**。模型预训练时看到的是原始文本；推理时输入 stem 过的 `poni`、`thi` 这类"非自然"字符串，会切出罕见的 subword 组合，相当于制造了分布偏移。
- **后果**：效果通常变差而不是变好，且多了一个需要在训练和推理两端保持一致的组件（呼应 Q13 的故障模式）。
- **仍然有用的场景**：BM25 等稀疏检索的 analyzer、经典的 TF-IDF/朴素贝叶斯基线、关键词统计与可视化等。
- **常见误区**：以为"预处理越多越干净越好"——对深度模型来说，预处理越少往往越好。

### Q13 — 参考回答要点

- **训练/推理一致性**：
  1. 预处理写成**纯函数**放在模型包里（与模型版本同发布），训练脚本和推理服务都 `import` 同一个函数，绝不允许"参照 notebook 重写"；
  2. 能把预处理并入模型本身就并入（例如把 tokenizer 文件和模型权重一起保存、一起加载）；
  3. 线上采样记录"原始输入 → 预处理后 token"，与训练数据的 token 分布做对比监控（OOV 率、平均长度等）。
- **可复现性漂移**：
  1. 在 `requirements.txt` 中**锁定** NLTK / spaCy 及模型数据的版本；
  2. 写一个预处理**回归测试**：冻结 20 条有代表性句子（缩写、数字、URL、Unicode、标点）的期望切分结果，每次升级都跑；
  3. 升级时把回归测试的 diff 作为评审材料，必要时重新训练。
- **加分点**：把它类比为 "feature store / training-serving skew" 问题；提到 CI 中同时跑"训练侧预处理"和"服务侧预处理"并比较输出。

### Q14 — 参考回答要点

- **核心原则**：索引端与查询端必须使用**同一个 analyzer**（同样的 tokenization、小写化、stemming），否则会出现"索引存的是 `run`、查询却是 `running`"的不匹配——这本质上也是训练/推理一致性问题。
- **Tokenization**：
  - 在通用规则之前加入领域规则：型号（`iphone 15 pro`）、SKU、带单位的数字（`3pm`、`64gb`）——像讲义的正则一样把 `3pm` 拆开可能是好事（便于匹配 `3 pm`），也可能是坏事（丢失整体），需要用真实查询日志评估；
  - 保留 URL、邮箱等不该被切碎的模式。
- **Stemming vs lemmatization**：搜索场景以召回为主、速度敏感，**对检索字段用 stemming** 合理（讲义："Stem when speed matters... search indexing"）；但要额外保留一个**不做 stemming 的原文字段**，用于精确匹配加权和高亮展示（stem 结果不能给用户看）。
- **评估**：用查询日志构造评测集，对比"不处理 / stemming / lemmatization"在召回率与精确率上的差异；关注过度合并带来的误召回（`organ` 类问题）。
- **加分点**：提到同义词表、拼写纠错、多字段加权；后续可以引入稠密向量检索做混合检索。

### Q15 — 参考回答要点

- **没有空格就没有天然词边界**。讲义给出的方向是 "Character for languages without whitespace"：可以按字符切分；也可以用专门的分词器（基于词典 + 统计/序列标注的中文分词工具），或者像现代 LLM 那样使用在多语言语料上训练的 subword / byte 级 tokenizer，让模型自己学"词"的边界。
- **stemming 基本不适用**：中文几乎没有屈折形态（没有 `-s / -ed / -ing` 这类后缀变化），英文意义上的 stemming 无从谈起；真正的难点在**分词歧义**（同一串字有多种切法）和新词识别。日文有动词活用等形态变化，需要形态分析器。
- **工程建议**：讲义 Ship It 中明确要求"Flag non-English input as needing a different pipeline"——不要把英文正则或 PorterStemmer 直接套到其他语言上；spaCy 等工具提供按语言区分的模型。
- **加分点**：指出字符级/字节级方案对未登录词更鲁棒，但序列更长、计算更贵；而词级分词的错误会传导到下游任务。

---

## 六、关联知识点

### 前置知识
- [阶段 02 · 14 朴素贝叶斯](../../../02-ml-fundamentals/14-naive-bayes/docs/zh.md)：本节的官方前置课；朴素贝叶斯文本分类的第一步就是把文本切成 token 并计数。
- Python 正则表达式基础：字符类、分支 `|`、非捕获组 `(?:...)`、`re.findall`。

### 本节被哪些后续内容用到
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：把本节得到的 token 变成计数向量；stemming 直接影响词表大小。
- [阶段 05 · 05 情绪分析](../../05-sentiment-analysis/docs/zh.md)：tokenization 与否定词处理直接决定分类基线的效果。
- [阶段 05 · 07 词性标注和句法分析](../../07-pos-tagging-parsing/docs/zh.md)：补上本节缺失的 POS tagger，让 lemmatizer 真正可用。
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：BM25 等稀疏检索中的 analyzer 就是本节的 tokenize + stem 流程。
- [阶段 05 · 18 多语言自然语言处理](../../18-multilingual-nlp/docs/zh.md)：非英文语言的切分与形态问题。
- [阶段 05 · 19 子词 Tokenization](../../19-subword-tokenization/docs/zh.md)：BPE、WordPiece、Unigram——Transformer 时代取代传统预处理的方案。
- [阶段 10 · 01 Tokenizers](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md) 与 [阶段 10 · 02 构建 Tokenizer](../../../10-llms-from-scratch/02-building-a-tokenizer/docs/zh.md)：从零为 LLM 构建 tokenizer。

### 延伸关键词
`Porter / Snowball / Lancaster Stemmer` · `WordNet` · `spaCy morphologizer` · `Penn Treebank 标签集` · `Universal POS tags` · `Unicode 规范化 (NFC/NFKC)` · `over-stemming / under-stemming` · `training-serving skew` · `Elasticsearch analyzer`
