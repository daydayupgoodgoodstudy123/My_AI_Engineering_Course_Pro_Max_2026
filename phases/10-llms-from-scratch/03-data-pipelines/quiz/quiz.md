# 测验 · 用于预训练的数据管道（Data Pipelines for Pre-Training）

> **阶段 10 · 从零构建 LLM · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 数据决定上限 | 各家 LLM 架构大同小异，输出质量的差距主要来自数据：规模、清洗、去重、配比 |
| 2 | Chinchilla 缩放律 | 固定算力 C 下 `N_opt ∝ C^0.5`、`D_opt ∝ C^0.5`，参数和 token 应等比例扩大；70B 模型配 1.4T token（约 20 token/参数）胜过 280B 的 Gopher |
| 3 | 推理最优的"过度训练" | Llama 3 70B 用 15T token，远超 Chinchilla 最优：多花一次训练成本，换来更小、永远更便宜的推理模型 |
| 4 | 清洗流水线 | HTML 剥离 → 语言识别 → 质量过滤 → 去重 → PII 移除；每一步去掉一类噪声 |
| 5 | 质量过滤 | 启发式（太短、全大写比例、特殊字符比例）+ 困惑度过滤（用 Wikipedia 上训练的小模型打分，困惑度高 = 不像干净文本） |
| 6 | 去重 | 精确去重靠哈希；近似重复靠 shingle（n-gram 集合）+ Jaccard。讲义称这是"影响最大的清洗步骤"，可避免浪费算力和逐字背诵 |
| 7 | MinHash + LSH | MinHash 签名的每一位"相等的概率 = Jaccard 相似度"；LSH 把签名分成 b 个 band，任一 band 完全相同才成为候选对，把 O(n²) 比较降到接近线性 |
| 8 | 序列打包（packing） | 用 EOS 把多篇文档拼成定长序列，代替逐篇 padding；正确做法还需要块对角 attention mask，防止跨文档注意 |
| 9 | DataLoader 与统计指标 | 打乱 + 分批喂给训练循环；用压缩比（英文约 3–4 字符/token）和序列利用率（低于 90% 说明 padding 浪费）检查管道健康度 |

### 核心技能（能动手做到）

- [ ] 用正则写出 `clean_text` 与启发式 `quality_filter`，并能说出每条规则会误杀/漏掉哪类文本
- [ ] 从零实现 shingling、MinHash 签名、LSH 分桶与 Jaccard 校验，完成近似去重
- [ ] 手算/估算 LSH 的候选概率 `1 − (1 − s^r)^b`（r 为每个 band 的行数、b 为 band 数），并据此调 `num_hashes` 与 `bands`
- [ ] 实现文档拼接 + 定长打包 + padding mask，并在此基础上构造块对角（按文档）的因果 mask
- [ ] 写出支持打乱、分批的 `DataLoader`，并统计实际送出的非 padding token 数
- [ ] 计算并解读数据集统计：总 token、唯一 token、字符/token 压缩比、序列利用率

---

## 二、基础自测（选择题）

**Q1.** 按 Chinchilla 缩放律，如果训练算力预算增加到原来的 100 倍，计算最优的做法是：

- A. 参数量扩大 100 倍，数据量不变
- B. 数据量扩大 100 倍，参数量不变
- C. 参数量和数据量各扩大约 10 倍
- D. 参数量扩大 50 倍，数据量扩大 2 倍

**Q2.** Llama 3 70B 用了约 15T token 训练，远超 Chinchilla 最优比例。讲义给出的理由是：

- A. Meta 不知道 Chinchilla 缩放律
- B. 额外的训练成本只付一次，而更小的模型推理成本"永远"更低（推理最优）
- C. 数据越多，模型参数量就会自动增加
- D. 这样能降低训练总算力

**Q3.** 对两个集合 A、B 用同一个随机哈希函数分别取最小哈希值，两者相等的概率等于：

- A. 两者的余弦相似度
- B. 两者的 Jaccard 相似度 `|A∩B| / |A∪B|`
- C. 两者的编辑距离
- D. `1 / num_hashes`

**Q4.** 本节代码用 128 个哈希、16 个 band（每 band 8 行）。一对文档成为 LSH 候选对的概率为 `1 − (1 − s⁸)¹⁶`（s 为 Jaccard）。这个"S 形曲线"的陡升点（阈值）大约在：

- A. 0.125
- B. 0.5
- C. 0.71
- D. 0.95

**Q5.** 关于序列打包（sequence packing），下列说法正确的是：

- A. 打包后不需要任何 mask，因为没有 padding
- B. 把每篇文档都 pad 到最大长度比打包更省算力
- C. 用 EOS 分隔多篇文档拼成定长序列；严格来说还需要块对角 attention mask，防止文档 A 的 token 注意到文档 B
- D. 打包只适用于微调，不适用于预训练

**Q6.** RefinedWeb 使用的困惑度（perplexity）过滤，正确的理解是：

- A. 用大模型给文档打分，困惑度**低**的文档被删除
- B. 用在 Wikipedia 上训练的小语言模型打分，困惑度**高**（不像 Wikipedia）的文档被视为垃圾删除
- C. 困惑度只用于评估最终模型，不能用于数据过滤
- D. 困惑度过滤等价于语言识别

**Q7.** `compute_statistics` 中压缩比定义为"字符数 / token 数"。若在英文语料上得到 1.5 字符/token，讲义认为最可能的原因是：

- A. tokenizer 学到了大量领域专用的长合并
- B. tokenizer 切分过于激进（合并太少、词表太小）
- C. 语料去重做得太彻底
- D. 序列打包的利用率太低

---

## 三、动手 / 代码题

**Q8.** 运行 `main.py`，去重阶段只输出 `Removed 1 near-duplicates`。样例语料里专门构造了两个"近似重复"：`near_dup_2` 与 `base_docs[1]` 一字不差，`near_dup_1` 是 `base_docs[0]` 的改写版。

1. 被删掉的是哪一篇？为什么另一篇"近似重复"没有被删？（提示：计算 5 词 shingle 的 Jaccard，并结合 Q4 的候选概率曲线。）
2. 如果你想让 `near_dup_1` 被识别出来，可以改哪些参数？各有什么代价？

相关代码：

```python
def get_shingles(text, k=5):
    words = text.lower().split()
    if len(words) < k:
        return set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}
```

```python
        jaccard = len(s1 & s2) / len(s1 | s2)
        if jaccard >= threshold:
            removed.add(j)
```

**Q9.** 预测下面这行的输出，并指出 `clean_text` 的至少两个问题，给出改进版本。

```python
def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()

print(repr(clean_text("<p>Hello</p><p>World</p> café 你好\tTab http://x.com/a end")))
```

**Q10.** `pack_sequences` 只生成"是否 padding"的一维 mask，没有实现讲义要求的块对角 mask：

```python
def pack_sequences(token_ids, seq_length, pad_id=0):
    sequences = []
    attention_masks = []
    for i in range(0, len(token_ids), seq_length):
        seq = token_ids[i:i + seq_length]
        mask = [1] * len(seq)
        if len(seq) < seq_length:
            pad_count = seq_length - len(seq)
            seq = seq + [pad_id] * pad_count
            mask = mask + [0] * pad_count
        sequences.append(seq)
        attention_masks.append(mask)
    return sequences, attention_masks
```

1. 本次运行共 2,660 个 token、`seq_length=128`，会得到多少条序列？最后一条有多少个 padding？据此验证输出中的 `Seq utilization: 99.0%`。
2. 写一个函数 `block_causal_mask(seq, eos_id, pad_mask)`，返回 `n×n` 的 0/1 矩阵：位置 i 只能注意同一文档内、不在它之后、且不是 padding 的位置 j。文档边界由 `eos_id` 标出（EOS 属于它前面的文档）。

---

## 四、面试高频题

**Q11.**（基础必考）请描述一条完整的 LLM 预训练数据管道：从 Common Crawl 原始网页到训练循环拿到的 batch，中间经过哪些步骤？每一步解决什么问题？

**Q12.**（原理深挖）讲一下 MinHash + LSH 做近似去重的原理。为什么 MinHash 能估计 Jaccard？`num_hashes` 和 `bands` 怎么选？

**Q13.**（工程实践）序列打包时为什么要考虑跨文档注意？不处理会怎样？工程上怎么实现"文档内注意"？

**Q14.**（追问型）Chinchilla 说 70B 模型配 1.4T token 是计算最优，那为什么 Llama 3 8B/70B 都训练了 15T token？如果你的模型要服务海量用户，你会怎么权衡？

**Q15.**（场景设计）你要训练一个"擅长代码和数学"的 7B 模型，数据配比怎么定？怎么验证配比是否合理？

**Q16.**（工程实践）训练时发现 GPU 利用率只有 40%，profiling 显示 GPU 经常在等数据。你会如何优化数据管道？

---

## 五、参考答案与解析

### Q1 — 答案：C

`N_opt ∝ C^0.5`、`D_opt ∝ C^0.5`，算力 ×100 → 参数 ×√100 = ×10，数据 ×10。讲义原话："you should scale model size and dataset size roughly equally"。（训练算力约为 `6·N·D`，N、D 各 ×10 正好是 ×100。）

### Q2 — 答案：B

讲义："The extra training cost is paid once, but the smaller model is cheaper to serve forever." 这被称为"推理最优"（inference-optimal）。D 恰好相反：多训 token 会增加训练算力，换来的是同等质量下更小的模型。

### Q3 — 答案：B

在随机哈希下，`A∪B` 中每个元素成为最小值的机会均等；最小值落在 `A∩B` 中时两边的最小哈希才相等，概率 = `|A∩B| / |A∪B|`，即 Jaccard。用 k 个独立哈希，"签名相等位数 / k"就是 Jaccard 的无偏估计。本节样例中，`base_docs[0]` 与 `near_dup_1` 的真实 Jaccard 为 0.270，128 位 MinHash 估计为 0.273（实际计算验证）。

### Q4 — 答案：C

阈值近似为 `(1/b)^(1/r) = (1/16)^(1/8) ≈ 0.707`。代入公式可以看到曲线形状（实际计算）：s=0.5 时候选概率约 6%，s=0.7 时约 61%，s=0.8 时约 95%，s=0.9 时约 99.99%。这与代码中的最终校验阈值 0.8 搭配合理：0.8 以上的真重复几乎都能成为候选，0.5 以下的几乎不会浪费比较次数。

### Q5 — 答案：C

讲义："Tokens from Document A should not attend to tokens from Document B within the same packed sequence. This requires a block-diagonal attention mask." A 错：没有 padding 也需要文档边界 mask（且最后一条通常仍有 padding）；B 错：逐篇 padding 浪费大量算力；D 错：预训练正是最常用打包的场景。注意本节代码只实现了 padding mask（见 Q10）。

### Q6 — 答案：B

先在高质量参考语料（如 Wikipedia）上训练一个小 LM，再给每篇文档算困惑度：困惑度高说明这篇文档"不像" Wikipedia，可能是垃圾、关键词堆砌或机器生成内容，超过阈值就删除。A 方向反了；D 不对，语言识别是 fastText 之类的分类器做的另一件事。

### Q7 — 答案：B

讲义："English text typically compresses to about 3-4 characters per token. If you see 1.5 characters per token, your tokenizer is splitting too aggressively. If you see 8+, it has learned very domain-specific merges." 本次运行只有 100 次合并，结果为 1.97 字符/token，正属于"切得太碎"。注意：本节的压缩比是"字符/token"（越**高**越好），与第 01 节"token/字节"（越**低**越好）方向相反，比较时别弄混。

### Q8 — 参考答案

1. **被删的是 `near_dup_2`**（它与 `base_docs[1]` 的 5 词 shingle 集合完全相同，Jaccard = 1.0，128 个 MinHash 全部相等，16 个 band 全部同桶）。`near_dup_1` 与 `base_docs[0]` 的 5 词 shingle Jaccard 只有 **0.27**（实际计算；MinHash 估计 0.273），16 个 band **一个都没有撞桶**——按 Q4 的公式，s=0.27 时成为候选的概率几乎为 0。即使成为候选，0.27 也远低于校验阈值 0.8。所以样例中名为"近似重复"的那篇其实没被抓到，本次删除的只是一篇**精确重复**。
   - 原因：`near_dup_1` 是"改写"而不是"换广告的同一篇文章"。每改动一个词，最多会破坏 5 个包含它的 5-gram，改动分散在全文时 shingle 重叠率下降得非常快。
2. **可调的参数及代价**（括号内为对这两篇实际计算的 Jaccard）：
   - 减小词 shingle 长度 k：k=3（0.44）、k=2（0.55）、k=1（0.78）。k 越小越容易判为相似，但不同文档共享常见短语的概率也越高，误删增加；k=1 就退化为"词袋"相似度。
   - 改用字符 n-gram：字符 3-gram（0.82）、字符 5-gram（0.70）。对小改动更鲁棒，但集合更大、计算更慢，短 n-gram 区分度差。
   - 降低校验阈值 `threshold`（如 0.5），同时增加 band 数降低 LSH 阈值（如 32 band × 4 行，阈值约 `(1/32)^(1/4) ≈ 0.42`）：召回提升，但候选对和误删都会增多。
   - 工程上的结论：去重阈值与 shingle 设计需要在"漏掉改写重复"和"误删不同文档"之间权衡，通常抽样人工检查被删文档来校准。

### Q9 — 参考答案

输出（已实际运行验证）：

```text
'HelloWorld caf Tab end'
```

逐步推导：删标签得到 `"HelloWorld café 你好\tTab http://x.com/a end"` → 删 URL → 删除所有非可打印 ASCII（`é`、`你好`、`\t` 全部消失）→ 合并多个空格。

问题：

1. **标签直接替换为空串**：`</p><p>` 两侧的词被粘成 `HelloWorld`，样例语料里的 HTML 文档也因此变成了 `"TitleMachine learning ..."`。应替换为空格（或换行）再压缩空白。
2. **`[^\x20-\x7E\n]` 过于激进**：删除了所有非 ASCII 字符（中文、带重音字母、emoji）和制表符。`café` 变成 `caf`，中文整段消失，代码缩进中的 tab 也被删。若目标是多语言模型，这一步会直接毁掉非英文数据；语言筛选应交给语言识别模型，而不是字符白名单。
3. 次要：`http\S+` 会误删以 `http` 开头的普通词（如讨论 `httpx` 库）；正则剥 HTML 无法处理 `<script>`/`<style>` 内的内容，生产中用 `trafilatura` 等正文抽取库。

改进版（保留多语言，仅作示意）：

```python
import re
import unicodedata

def clean_text(text):
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)  # 去掉脚本/样式块
    text = re.sub(r"<[^>]+>", " ", text)                           # 标签换成空格
    text = re.sub(r"https?://\S+", " ", text)                      # 只删真正的 URL
    text = "".join(c for c in text                                 # 只删控制字符，保留 \n \t
                   if c in "\n\t" or unicodedata.category(c)[0] != "C")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()
```

### Q10 — 参考答案

1. `range(0, 2660, 128)` 产生 `⌈2660/128⌉ = 21` 条序列；前 20 条共 2,560 个 token，最后一条只有 100 个真实 token，补 **28** 个 padding。利用率 = 2660 / (21×128) = 2660 / 2688 ≈ **98.96% → 99.0%**，与输出一致。（`compute_statistics` 用 `t != 0` 统计非 padding，因为 `pad_id=0`；这依赖于真实数据中不出现字节 0——`clean_text` 删除了控制字符，所以这里成立。）

2. 参考实现（已用小例子运行验证）：

```python
def doc_ids_from_eos(seq, eos_id):
    ids, cur = [], 0
    for t in seq:
        ids.append(cur)
        if t == eos_id:          # EOS 归属于它前面的文档，之后换下一篇
            cur += 1
    return ids

def block_causal_mask(seq, eos_id, pad_mask):
    doc = doc_ids_from_eos(seq, eos_id)
    n = len(seq)
    return [[1 if (j <= i and doc[i] == doc[j] and pad_mask[i] and pad_mask[j]) else 0
             for j in range(n)]
            for i in range(n)]
```

对 `seq=[11,12,99,21,22,23,99,31,0,0]`（`eos_id=99`，最后两个是 padding），文档编号为 `[0,0,0,1,1,1,1,2,2,2]`，得到三个下三角小块沿对角线排列，第 4 行（第二篇文档的第一个 token `21`）只能看到自己。

注意：
- 这里同时满足"因果"（`j <= i`）和"同文档"两个条件。
- padding 行全为 0，若直接用于 softmax（把 0 变成 −∞）会产生 NaN。实际实现中通常让 padding 位置至少能看到自己，并在 loss 中把这些位置屏蔽。
- 另一个配套细节：位置编码（position ids）通常也要在每篇文档开头重置为 0。
- 第二篇文档的第一个 token 在序列中间，但它看不到前文，这正是我们想要的"像独立文档一样"。

### Q11 — 参考回答要点

- **采集**：Common Crawl（约 250TB 原始数据）、Wikipedia、GitHub 代码、书籍、arXiv、StackOverflow 等。
- **抽取与清洗**：HTML → 正文（trafilatura/readability），去掉导航、广告、模板；规范化空白与编码。
- **语言识别**：fastText `lid.176.bin`，按目标语言过滤，置信度低于约 0.8 的视为不干净。
- **质量过滤**：启发式规则（长度、全大写比例、符号比例、重复行等）+ 基于困惑度或分类器的打分。
- **去重**：精确去重（哈希）+ 近似去重（MinHash + LSH，Jaccard 阈值约 0.8）。
- **PII 移除**：正则处理邮箱/电话/身份证号，NER 处理人名。
- **配比与采样**：按来源设定比例（网页、代码、数学、多语言），对高质量来源上采样。
- **分词与打包**：用 tokenizer 编码、文档间插 EOS、打包成定长序列，生成 mask。
- **存储与加载**：预先分词并分片存成二进制文件，训练时流式读取、打乱、分批，确保 GPU 不等数据。
- 加分点：强调每一步都要**可观测**——记录每一步删除的比例并抽样人工检查，因为过滤器的误杀往往不报错。

### Q12 — 参考回答要点

- **Shingling**：把文档变成 n-gram 集合（如 5 词 shingle），文档相似度用 Jaccard 衡量。
- **MinHash**：对每个哈希函数，取集合中所有元素哈希值的最小值；`P[minhash(A) = minhash(B)] = J(A,B)`。用 k 个哈希得到长度 k 的签名，签名相等的比例估计 Jaccard，误差约随 `1/√k` 缩小。签名长度固定，与文档长度无关。
- **LSH**：把签名切成 b 个 band、每 band r 行；任意一个 band 完全相同就进入同一个桶、成为候选对。候选概率 `1 − (1 − s^r)^b`，阈值约 `(1/b)^(1/r)`。只对候选对计算精确 Jaccard，把 O(n²) 两两比较变为接近线性。
- **参数选择**：先定目标 Jaccard 阈值（如 0.8），再选 b、r 让 S 曲线的陡升点略低于阈值（宁可多一些候选，再用精确 Jaccard 过滤）。b 越大召回越高、误报越多；r 越大越严格。本节 128 = 16×8，阈值约 0.71。
- **工程细节**：本节用 `sha256(f"{i}:{shingle}")` 模拟 128 个独立哈希，易懂但很慢；生产中用一次基础哈希加 `(a·x + b) mod p` 形式的多组随机线性变换生成 k 个哈希，并在分布式框架中按桶 shuffle。
- 常见误区：以为 LSH 的桶就是最终结果——桶内只是候选，仍需校验。

### Q13 — 参考回答要点

- **为什么**：打包后一条序列里有多篇无关文档。如果只用普通因果 mask，后一篇文档的 token 可以注意到前一篇的内容，模型会学到"无关上下文也能用来预测"的虚假关联，并在训练中引入噪声。
- **不处理会怎样**：一种常见的简化做法是只用 EOS 分隔、不做文档内 mask，依赖模型自己学会在 EOS 之后"不再依赖前文"；这能跑通，但会引入跨文档噪声，在文档短而杂、或做长上下文训练时影响更明显。讲义的观点是应当使用块对角 mask。
- **实现方式**：
  - 构造 `doc_ids`，mask = 因果 ∧ 同文档（见 Q10）；
  - 位置编码在每篇文档开头重置；
  - 高效实现：不显式构造 `n×n` 矩阵，而是把每篇文档的起止位置（如 FlashAttention 的变长接口中的累计序列长度 `cu_seqlens`）传给 attention kernel，只在文档内部计算。
- 另一个相关问题：长文档在序列边界被截断，后半段失去前文。讲义提到一些管道会尽量在段落/句子边界切分。

### Q14 — 参考回答要点

- **Chinchilla 回答的问题**：给定一次性训练算力，怎样分配 N 和 D 使**训练结束时的 loss 最低**。结论是 N 和 D 等比例扩大（约 20 token/参数）。
- **Llama 3 回答的问题**：模型训练好后要被调用无数次，**总成本 = 训练成本 + 推理成本**。推理成本与参数量成正比，所以宁愿用更多数据把小模型"训透"，在相同质量下得到更小的模型。
- **权衡思路**：
  - 估计生命周期内的推理 token 总量，推理量越大，越应该选小模型 + 大数据；
  - 受限于高质量数据总量时，过度训练会遇到数据重复（多 epoch）的收益递减；
  - 小模型过度训练的 loss 会持续下降，但边际收益越来越小。
- 加分点：讲义称这种推理最优思路自 2024 年起已成为行业标准；能用 `C ≈ 6·N·D` 估算训练算力。

### Q15 — 参考回答要点

- **初始配比**：参考公开技术报告中的配方（如 Llama 3 报告按"通用知识、数学推理、代码、多语言"几大类给出了配比），在通用网页语料基础上提高代码与数学比例，同时保留足量通用文本，否则语言能力下降。
- **数据来源与质量**：代码去重（GitHub 重复非常多）、过滤自动生成和死代码；数学数据从 arXiv、教材、数学网页中抽取，保留公式。
- **验证方法**：讲义强调配比"没有公式，需要实验和评估"。
  - 用小模型做消融实验：固定总 token，改变配比，在代码（如 HumanEval）、数学（如 GSM8K）、通用（如 MMLU）基准上比较；
  - 关注"跷跷板"：提高代码比例后通用能力是否下降；
  - 训练后期可对高质量数据上采样。
- 常见误区：只看总 token 数不看配比；讲义原话："Too much web data and the model becomes a Reddit parrot. Too little code and it cannot program."

### Q16 — 参考回答要点

- **定位瓶颈**：分别测"数据管道单独吞吐（token/s）"和"训练步消耗速度"，确认是 I/O、解压、分词还是 collate 慢。
- **离线预处理**：不要在训练时分词。提前用 Rust tokenizer 把语料编码成整数数组，按分片存成二进制文件（如 uint16/uint32 的 memmap），训练时只做切片读取。讲义指出纯 Python 管道比 HF/Rust 慢 10–50 倍。
- **流式与分片**：按分片流式读取，避免一次性载入内存；多卡训练时每个 rank 读不同分片。
- **并行与预取**：多进程 worker、预取下一批、pinned memory 与异步拷贝到 GPU。
- **打乱策略**：分片级打乱 + 缓冲区内打乱（shuffle buffer），兼顾随机性与顺序读取效率。
- **监控**：持续记录 dataloader 等待时间，确保训练步之间 GPU 不空转。
- 加分点：本节 `PreTrainingDataLoader` 把全部序列放在内存中、用 `random.shuffle` 打乱且未设种子，只适合教学；生产中还需要可复现的随机种子和断点续训时恢复数据位置。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 01 Tokenizers: BPE, WordPiece, SentencePiece](../../01-tokenizers/docs/zh.md)：BPE 与压缩比。
- [阶段 10 · 02 从头开始构建 Tokenizer](../../02-building-a-tokenizer/docs/zh.md)：特殊 token（EOS）与预分词。
- [阶段 00 · 09 数据管理](../../../00-setup-and-tooling/09-data-management/docs/zh.md)：大规模数据的存储与组织。
- [阶段 05 · 01 文本处理](../../../05-nlp-foundations-to-advanced/01-text-processing/docs/zh.md)：正则与文本清洗。

### 本节被哪些后续内容用到
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：直接消费打包好的 token 序列进行训练。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../05-scaling-distributed/docs/zh.md)：多卡训练下的数据分片与吞吐。
- [阶段 07 · 13 缩放定律](../../../07-transformers-deep-dive/13-scaling-laws/docs/zh.md)：Chinchilla 与计算最优的系统讲解。
- [阶段 18 · 27 数据溯源与训练治理](../../../18-ethics-safety-alignment/27-data-provenance-training-governance/docs/zh.md)：数据来源、许可与 PII 的治理。
- [阶段 19 · 42 大规模语料下载器](../../../19-capstone-projects/42-large-corpus-downloader/docs/zh.md)、[阶段 19 · 43 HDF5 分词语料](../../../19-capstone-projects/43-hdf5-tokenized-corpus/docs/zh.md)：综合项目中的语料下载与离线分词存储。

### 延伸关键词
`Common Crawl` · `RefinedWeb / FineWeb` · `trafilatura` · `fastText lid.176` · `MinHash / LSH` · `Jaccard` · `perplexity filter` · `PII scrubbing` · `sequence packing` · `cu_seqlens` · `Chinchilla` · `inference-optimal` · `data mixing`
