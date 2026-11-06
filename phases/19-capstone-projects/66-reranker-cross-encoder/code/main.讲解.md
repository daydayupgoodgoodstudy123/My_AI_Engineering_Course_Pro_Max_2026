# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 66 节 基于 Cross-Encoder 的 Reranker ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`） ｜ **依赖**：第三方 `torch`、`numpy`；其余为标准库（`math`、`re`、`time`、`dataclasses`、`typing`）。无需 GPU、无需网络、无需预训练权重。

---

## 1. 这份代码在考察什么

这份代码用一个"玩具级"的 PyTorch cross-encoder，演示 RAG 中的**两阶段检索**：

1. **cross-encoder 的输入形状**：`[CLS] query [SEP] doc [SEP]` 打包成一条序列，配合 token / type（segment）/ position 三种 embedding。
2. **cross-encoder 的模型形状**：一层多头注意力 + FFN（post-norm），对非 padding 位置做 mean-pooling，再用线性头输出**每对一个标量分数**。
3. **监督训练**：用 14 条手工标注的 (query, doc, label) 三元组，以 MSE 回归分数。
4. **两阶段 pipeline**：一个基于哈希的"假" bi-encoder 先取 top-N，cross-encoder 再把 N 个候选重排成 top-K，并分别计时。
5. **batch 推理**：`_batch_encode` 把 N 个候选拼成一个张量，一次前向打完分（讲义 "Batching matters"）。

> 一句话：**把"便宜的检索器粗排 + 昂贵的交叉编码器精排"这条生产流水线缩小到 300 行，看清每一层的形状**。同时要看清它的局限：模型太小、训练集太小、评估 query 就是训练 query——这些恰好是讲义 "Failure modes" 里警告的问题，也是面试追问的重点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VOCAB_SIZE / PAD_ID / SEP_ID / CLS_ID / SEED` | 常量 | 词表大小 8192，三个特殊 token id，固定随机种子 | 特殊 token |
| `_set_seed` | 函数 | 同时固定 torch 与 numpy 的随机种子 | 可复现 |
| `_token_to_id` | 函数 | 把单词哈希到 `[3, 8191]`，代替真正的 tokenizer | 哈希词表 |
| `tokenize_pair` | 函数 | 打包 `[CLS] q [SEP] d [SEP]`，生成 `type_ids`，截断或补 PAD | cross-encoder 输入 |
| `CrossEncoder` | `nn.Module` | 三种 embedding → 多头注意力 → FFN → mean-pool → 线性头 | cross-encoder |
| `Triple` | dataclass | (query, document, label) 训练样本 | 监督数据 |
| `_batch_encode` | 函数 | 把一组 Triple 变成 `(ids, type_ids, labels)` 三个张量 | batching |
| `train_tiny` | 函数 | 全批量 Adam + MSE，返回每轮 loss | 训练 |
| `Candidate` | dataclass | 候选文档：id、文本、第一阶段分数 | 候选池 |
| `rerank` | 函数 | 对 N 个候选一次前向打分，排序取 top-K | 第二阶段 |
| `mock_embed / cosine / BiEncoder` | 函数 / dataclass | 哈希词袋向量 + 点积检索 | 第一阶段（bi-encoder 替身） |
| `pipeline` | 函数 | 检索 top-N → 重排 top-K，分别计时 | retrieve-then-rerank |
| `CORPUS / TRAIN_TRIPLES` | 常量 | 8 篇文档、14 条训练三元组 | fixture |
| `print_list / main` | 函数 | 训练模型，对 3 个 query 打印两阶段结果与延迟 | demo |

数据流：`main` → 建 `BiEncoder` 并索引 8 篇文档 → 构造 `CrossEncoder` 并 `train_tiny` 60 轮 → 对每个 query 调 `pipeline`：`BiEncoder.search`（top-N）→ `rerank`（`_batch_encode` → `CrossEncoder.forward` → 排序取 top-K）→ 打印。

---

## 3. 逐段精讲

### 3.1 哈希"分词"与输入打包

```python
def _token_to_id(token: str) -> int:
    h = 0
    for ch in token:
        h = (h * 1315423911) ^ ord(ch)
        h &= 0xFFFFFFFF
    return 3 + (h % (VOCAB_SIZE - 3))
```

- 这是一个简单的字符串哈希：每读一个字符，`h` 乘以一个大常数再与字符码异或，`& 0xFFFFFFFF` 截成 32 位无符号整数（Python 整数不会溢出，必须手动截断）。
- `3 + h % 8189` 把结果映射到 `[3, 8191]`，**避开 0/1/2 这三个特殊 id**。
- 这是"hashing trick"：不需要预先建词表，任何单词都有 id，代价是不同单词可能**碰撞**到同一个 id，且没有子词切分。

```python
def tokenize_pair(query: str, document: str, max_len: int = 96) -> tuple[list[int], list[int]]:
    q_tokens = [_token_to_id(t) for t in _WORD.findall(query.lower())]
    d_tokens = [_token_to_id(t) for t in _WORD.findall(document.lower())]
    ids = [CLS_ID] + q_tokens + [SEP_ID] + d_tokens + [SEP_ID]
    type_ids = ([0] * (len(q_tokens) + 2)) + ([1] * (len(d_tokens) + 1))
    if len(ids) > max_len:
        ids = ids[:max_len]
        type_ids = type_ids[:max_len]
    else:
        pad = max_len - len(ids)
        ids = ids + [PAD_ID] * pad
        type_ids = type_ids + [0] * pad
    return ids, type_ids
```

- `_WORD = re.compile(r"[a-z0-9]+")` 先转小写再抽取连续字母数字串；标点、下划线都被丢掉（`check_permission` 会变成 `check`、`permission` 两个词）。
- 打包格式正是讲义的 `[CLS] query_tokens [SEP] document_tokens [SEP]`。
- `type_ids`：query 段长度 = query token 数 + 2（CLS 与第一个 SEP），文档段长度 = 文档 token 数 + 1（末尾 SEP）。这就是 BERT 的 segment id，让模型知道"哪段是 query"。
- 例：`tokenize_pair("alpha", "beta gamma", max_len=12)` 实测返回
  `ids = [2, 1875, 1, 7837, 7561, 1, 0, 0, 0, 0, 0, 0]`，`type_ids = [0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0]`。
- 固定长度 `max_len=96`：短的补 PAD，长的截断。demo 中所有对都只有 24–32 个 token，不会触发截断。
- ⚠️ 截断是"从尾部硬切"：一旦超长，**末尾的 `[SEP]` 会丢失**；如果 query 本身很长，文档部分甚至可能完全被切掉。生产中通常优先截断文档、保留 query 和两个 SEP。

### 3.2 `CrossEncoder`：模型结构

```python
class CrossEncoder(nn.Module):
    def __init__(self, d_model: int = 64, n_heads: int = 4, ff_hidden: int = 128,
                 max_len: int = 96) -> None:
        super().__init__()
        _set_seed()
        self.token_emb = nn.Embedding(VOCAB_SIZE, d_model, padding_idx=PAD_ID)
        self.type_emb = nn.Embedding(2, d_model)
        self.pos_emb = nn.Embedding(max_len, d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.ln1 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, ff_hidden),
            nn.GELU(),
            nn.Linear(ff_hidden, d_model),
        )
        self.ln2 = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, 1)
        self.max_len = max_len
```

- **三种 embedding 相加**：token（8192 × 64）、type（2 × 64）、position（96 × 64，可学习的绝对位置），与 BERT 输入层一致。
- `padding_idx=PAD_ID`：id 为 0 的行初始化为全零，且**不接收梯度**，PAD 不会学到任何东西。
- `nn.MultiheadAttention(64, 4, batch_first=True)`：4 个头，每头 16 维；`batch_first=True` 表示输入形状是 `(B, S, D)` 而非默认的 `(S, B, D)`。
- 只有**一层** Transformer block；FFN 是 `64 → 128 → 64`（2 倍扩展，而非常见的 4 倍），激活 GELU。
- `head = nn.Linear(64, 1)`：回归头，输出一个标量，没有 sigmoid。
- `_set_seed()` 写在构造函数里：每次构造都会重置全局随机种子，所以任何两个 `CrossEncoder()` 的初始权重都一样。好处是可复现；副作用是**会悄悄改变调用方的全局 RNG 状态**。
- 参数量（实测 564,097）：token embedding 就占 524,288（约 92.9%），注意力 + FFN + LayerNorm + 头加起来只有约 3.3 万。详见测验 Q12。

### 3.3 `forward`：形状追踪

```python
    def forward(self, input_ids: torch.Tensor, type_ids: torch.Tensor) -> torch.Tensor:
        batch, seq = input_ids.shape
        pos = torch.arange(seq, device=input_ids.device).unsqueeze(0).expand(batch, seq)
        x = self.token_emb(input_ids) + self.type_emb(type_ids) + self.pos_emb(pos)
        mask = (input_ids == PAD_ID)
        attn_out, _ = self.attn(x, x, x, key_padding_mask=mask)
        x = self.ln1(x + attn_out)
        x = self.ln2(x + self.ff(x))
        # mean-pool over non-pad positions
        keep = (~mask).unsqueeze(-1).float()
        pooled = (x * keep).sum(dim=1) / keep.sum(dim=1).clamp(min=1.0)
        return self.head(pooled).squeeze(-1)
```

| 步骤 | 形状（demo 中 B = 候选数，S = 96） |
|------|------|
| `input_ids`、`type_ids` | `(B, 96)` |
| `pos = arange(96).unsqueeze(0).expand(B, 96)` | `(B, 96)` |
| 三种 embedding 相加 | `(B, 96, 64)` |
| `mask = input_ids == 0` | `(B, 96)` 布尔，True 表示 PAD |
| `attn(x, x, x, key_padding_mask=mask)` | `(B, 96, 64)`，自注意力：Q、K、V 都是 `x` |
| `ln1(x + attn_out)` | `(B, 96, 64)` |
| `ln2(x + ff(x))` | `(B, 96, 64)` |
| `keep = (~mask).unsqueeze(-1).float()` | `(B, 96, 1)`，非 PAD 为 1.0 |
| `(x * keep).sum(1) / keep.sum(1)` | `(B, 64)`，只对真实 token 求平均 |
| `head(pooled).squeeze(-1)` | `(B, 1)` → `(B,)` |

- **`key_padding_mask`**：True 的位置作为 Key 被屏蔽，任何 token 都不会去注意 PAD。注意 PAD 位置作为 Query 仍然会被计算，但最终池化时被 `keep` 排除，不影响结果。
- **post-norm**：`ln1(x + attn_out)` 是"先残差、后 LayerNorm"，与原始 Transformer、BERT 一致（GPT-2 用的是 pre-norm `x + attn(ln(x))`）。
- **cross-encoder 的关键就在这一层注意力**：query 段与文档段在同一条序列里，文档 token 的表示可以直接受 query token 影响——这是 bi-encoder 做不到的"联合编码"。
- **mean-pooling**：讲义描述的标准做法是取 CLS 位置接头，代码选了"对非 PAD 位置求平均"，讲义说两者差别不大（练习 3 要求对比，见测验 Q11）。`clamp(min=1.0)` 防止全是 PAD 时除以 0（实际上 CLS 永远存在，不会发生）。
- 输出是一个**无界实数**：没有 sigmoid，所以分数可能大于 1 或小于 0（demo 中出现了 1.1841）。

### 3.4 训练：全批量 Adam + MSE

```python
@dataclass
class Triple:
    query: str
    document: str
    label: float  # 1.0 relevant, 0.0 irrelevant


def _batch_encode(pairs: list[Triple], max_len: int = 96) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    ...
    return (
        torch.tensor(id_lists, dtype=torch.long),
        torch.tensor(type_lists, dtype=torch.long),
        torch.tensor(labels, dtype=torch.float),
    )


def train_tiny(model: CrossEncoder, triples: list[Triple], epochs: int = 60, lr: float = 5e-3) -> list[float]:
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    losses: list[float] = []
    ids, tids, labels = _batch_encode(triples, max_len=model.max_len)
    for _ in range(epochs):
        opt.zero_grad()
        pred = model(ids, tids)
        loss = loss_fn(pred, labels)
        loss.backward()
        opt.step()
        losses.append(loss.item())
    return losses
```

- `_batch_encode` 把 14 条样本打成 `(14, 96)` 的 `ids`/`tids` 和 `(14,)` 的 `labels`。`torch.long` 是 embedding 查表要求的整数类型，标签用 `float` 以配合 MSE。
- 训练循环是标准五步：`zero_grad → forward → loss → backward → step`。每轮就是一次**全批量**梯度下降（14 条一起），60 轮 = 60 步。
- **pointwise 回归**：标签不只 0/1，还有 0.2、0.3、0.5 这类"部分相关"的分级标签，所以用 MSE 而不是 BCE。
- 实测 loss：第 1 轮 0.5356，第 10 轮 0.1889，第 30 轮 0.0214，第 60 轮 0.0003——几乎完美拟合训练集。但 56 万参数对 14 条样本，这是**记忆**而不是泛化（见 3.7 与 6 节）。
- ⚠️ `losses[0]` 是第一次**更新前**的 loss；`epochs=1` 时返回的就是初始 loss。
- ⚠️ 讲义说 `train_tiny` 是 "one pass of supervised training"、练习 2 说"训练十轮而不是一轮"，但代码默认 `epochs=60`、demo 也用 60——讲义描述与代码不一致。
- ⚠️ `train_tiny` 没有调用 `model.train()`；而 `rerank` 会调用 `model.eval()`。本模型没有 dropout/BatchNorm（`nn.MultiheadAttention` 默认 `dropout=0`），所以不影响结果，但这是个不好的习惯。

### 3.5 `rerank`：生产接口

```python
def rerank(model, query, candidates, top_k=5):
    if not candidates:
        return []
    model.eval()
    triples = [Triple(query, c.text, 0.0) for c in candidates]
    ids, tids, _ = _batch_encode(triples, max_len=model.max_len)
    with torch.no_grad():
        scores = model(ids, tids).tolist()
    out = sorted(zip(candidates, scores), key=lambda x: -x[1])
    return out[:top_k]
```

- 空候选直接返回 `[]`（有对应测试）。
- 复用 `Triple` 打包，标签填 0.0 占位不用。
- **一次 batch 前向**给所有候选打分：`(N, 96) → (N,)`。讲义："A real cross-encoder runs the N candidates in one batch... Skip batching and the latency multiplies by N."
- `torch.no_grad()`：推理时不构建计算图，省内存省时间。
- `sorted(zip(...), key=lambda x: -x[1])` 按分数降序；`[:top_k]` 截断，`top_k` 大于候选数时返回全部（有对应测试）。
- **query 总是放在前面**：`tokenize_pair(query, c.text)`。讲义强调 cross-encoder 不对称；实测把顺序颠倒后，同一对的分数从 0.978 变成 0.530。

### 3.6 第一阶段：哈希 bi-encoder

```python
def mock_embed(text: str, dim: int = 96) -> list[float]:
    vec = [0.0] * dim
    for tok in _WORD.findall(text.lower()):
        h = 0
        for ch in tok:
            h = (h * 1315423911) ^ ord(ch)
            h &= 0xFFFFFFFF
        vec[h % dim] += 1.0
        vec[(h >> 7) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))
```

- 每个词哈希到 96 维中的两个桶（权重 1.0 和 0.5），本质是**带哈希的词袋**，没有任何语义——"abort" 和 "cancel" 毫无相似性。
- 向量做了 L2 归一化，所以 `cosine` 直接写成点积。`or 1.0` 防止空文本时除以 0。
- **没有停用词过滤**："how do we cancel a job" 中的 how/do/we/a 都参与打分，这就是 cancel 查询的 gold d8 只排第 3、而包含 "how often ... within a window" 的 d3 排第 1 的原因。
- `BiEncoder.add` 在索引时为每篇文档算一次向量（"embed once"）；`search` 对 query 只算一次向量，与全部文档点积后排序（真实系统用 ANN 索引代替线性扫描）。
- `search` 返回**新的** `Candidate` 对象，带上 `retriever_score`，不修改索引里的原对象。

### 3.7 两阶段 pipeline 与 fixture

```python
def pipeline(query, retriever, reranker, top_n=10, top_k=5):
    t0 = time.perf_counter()
    n_candidates = retriever.search(query, top_n)
    t1 = time.perf_counter()
    reranked = rerank(reranker, query, n_candidates, top_k)
    t2 = time.perf_counter()
    return {
        "retrieve_top_n": n_candidates,
        "reranked_top_k": reranked,
        "latency_retrieve_ms": (t1 - t0) * 1000,
        "latency_rerank_ms": (t2 - t1) * 1000,
    }
```

- `time.perf_counter()` 是高精度单调时钟，适合测短时间间隔；乘 1000 转成毫秒。
- 返回值是 `dict[str, object]`，由调用方按键取值（生产中更推荐 dataclass，类型更明确）。
- fixture：8 篇文档（S3 分片上传中止、重试预算、权限检查、策略引擎、rank fusion、索引容量、任务取消……），14 条训练三元组覆盖 5 个 query。

⚠️ 几个需要看清的简化：

1. **`main` 用的 3 个 query 全部是训练 query**（`TRAIN_TRIPLES` 中的原句）。讲义 "Training data leaks into the eval" 一节恰好警告了这种做法："If the hand-labeled training pairs include the eval queries, the rerank looks magical."
2. **`top_n=8` 等于语料大小**：第一阶段没有过滤掉任何文档，rerank 结果与 bi-encoder 的排序无关。讲义说 N 至少是 K 的 3 倍，这里 N=8、K=3 虽然满足，但"N = 全库"让两阶段的意义消失了。
3. **`print_list` 只打印前 5 条**：所以 "retrieve top-N" 只显示 8 个候选中的 5 个。
4. 讲义说 demo "loads the corpus from lesson 65's pattern"，实际上本文件自带 `CORPUS`，没有读取第 65 节的任何东西。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 随机初始化的单层 Transformer | 不需要下载权重，几秒内训练完 | 没有语言知识，只能记忆；生产从预训练 encoder（MiniLM/BERT 系、bge-reranker 等）微调 |
| 哈希"分词"（8192 桶） | 无需词表文件，确定性 | 有碰撞、无子词、丢标点；生产用 WordPiece/SentencePiece |
| type embedding 区分 query/文档 | 与 BERT 句对输入一致 | 需要保证训练与推理打包方式完全一致 |
| post-norm | 与 BERT 一致 | 深层时 pre-norm 更稳定；一层无所谓 |
| mean-pooling（排除 PAD） | 浅模型上收敛更快、实现简单 | 讲义的标准写法是 CLS 头；二者差别通常不大 |
| MSE 回归分级标签、无 sigmoid | 能直接利用 0.3/0.5 等部分相关标签 | 分数无界、未校准，不适合直接当拒答阈值；生产常用 BCE 或 pairwise/listwise 损失 |
| 全批量训练 60 轮 | 14 条样本一次就能装下 | 严重过拟合；真实训练用 mini-batch、困难负例、验证集早停 |
| 构造函数里设置种子 | 每个模型实例初始化相同，测试可复现 | 改变全局 RNG 状态；生产中由调用方统一管理种子 |
| 哈希词袋 bi-encoder | 无依赖、确定性 | 无语义，连停用词都算分；生产用稠密 embedding 模型 + ANN 索引（或第 65 节的 hybrid） |
| 批量推理 `_batch_encode` | 一次前向打完 N 个候选 | 生产还要按长度分桶、限制 max_len、用 GPU/量化 |
| demo 用训练 query 做展示 | 让结果"看起来"正确 | 实际是数据泄漏；应使用独立的评估 query |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可以在旧版本 Python 中使用 `list[int]`、`X \| None` 等新写法 |
| 类型注解 | `def tokenize_pair(query: str, document: str, max_len: int = 96) -> tuple[list[int], list[int]]` | 标注参数与返回值类型，不影响运行，方便阅读与静态检查 |
| 模块级常量 | `VOCAB_SIZE = 8192`、`PAD_ID = 0` | 全大写命名表示"不要修改" |
| 前导下划线 | `_set_seed`、`_token_to_id`、`_batch_encode` | 约定为模块内部使用；`from main import *` 不会导入它们（测试里是显式按名导入的） |
| 位运算 | `h = (h * 1315423911) ^ ord(ch)`、`h &= 0xFFFFFFFF`、`h >> 7` | 异或、按位与（截断成 32 位）、右移 |
| `ord()` | `ord(ch)` | 取字符的 Unicode 码点 |
| 预编译正则 | `_WORD = re.compile(r"[a-z0-9]+")`、`_WORD.findall(...)` | 编译一次多次使用；`findall` 返回所有匹配子串 |
| 列表推导式 | `[_token_to_id(t) for t in _WORD.findall(query.lower())]` | 一行构造列表 |
| 列表拼接与重复 | `[CLS_ID] + q_tokens + [SEP_ID]`、`[0] * (len(q_tokens) + 2)` | `+` 连接，`*` 重复 |
| 切片 | `ids[:max_len]`、`items[:5]`、`out[:top_k]` | 取前若干个，越界不报错 |
| 继承 `nn.Module` | `class CrossEncoder(nn.Module)` + `super().__init__()` | PyTorch 模型的标准写法，必须先调用父类构造函数才能注册子模块 |
| `nn.Sequential` | `nn.Sequential(nn.Linear(...), nn.GELU(), nn.Linear(...))` | 把多层按顺序串起来 |
| `model(ids, tids)` | `pred = model(ids, tids)` | 调用 `__call__`，内部会执行 `forward` 及各种 hook，不要直接调 `forward` |
| 张量方法链 | `torch.arange(seq).unsqueeze(0).expand(batch, seq)` | `unsqueeze` 增加维度，`expand` 不复制内存地广播 |
| 布尔张量 | `mask = (input_ids == PAD_ID)`、`~mask` | 逐元素比较得到 bool 张量，`~` 取反 |
| `.float()` / `.squeeze(-1)` / `.clamp(min=1.0)` | `keep.sum(dim=1).clamp(min=1.0)` | 类型转换、去掉大小为 1 的维度、下限截断 |
| `.item()` / `.tolist()` | `loss.item()`、`model(ids, tids).tolist()` | 把张量转成 Python 数值 / 列表 |
| `with torch.no_grad():` | `rerank` 中 | 上下文管理器：块内不记录梯度 |
| `@dataclass` | `Triple`、`Candidate`、`BiEncoder` | 自动生成 `__init__`、`__repr__` 等 |
| 可变默认值 | `docs: list[Candidate] = field(default_factory=list)` | dataclass 中不能写 `= []`，否则所有实例共享同一个列表 |
| 带默认值字段 | `retriever_score: float = 0.0` | 构造时可省略 |
| `typing.Callable` | `from typing import Callable` | 导入了但本文件未使用 |
| `zip` + `sorted` + `lambda` | `sorted(zip(candidates, scores), key=lambda x: -x[1])` | 两两配对后按分数降序 |
| `enumerate` | `for i, item in enumerate(items[:5])` | 同时拿到下标和元素 |
| `or` 短路默认值 | `math.sqrt(...) or 1.0` | 左侧为 0（假值）时取右侧 |
| 函数作为参数 | `print_list(label, items, fmt)`，`fmt` 传入 `lambda c: f"..."` | 把"如何格式化"交给调用方决定 |
| f-string 格式符 | `{losses[0]:.4f}`、`{result['latency_rerank_ms']:.2f}ms` | 保留 4 位/2 位小数；f-string 内用单引号取字典键 |
| 多行字符串拼接 | `"AbortMultipartOnFail aborts ..." "decrements ..."` | 相邻字符串字面量自动连接 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，torch 2.14 CPU，固定种子；整个脚本耗时数秒到二十秒不等，主要花在 `import torch` 上，取决于机器负载）：

```text
trained tiny cross-encoder, loss 0.5356 -> 0.0003

query: how do we abort a multipart upload
  retrieve top-N:
    1. d1  retriever_score=0.4255
    2. d3  retriever_score=0.3660
    3. d4  retriever_score=0.2131
    4. d8  retriever_score=0.1735
    5. d2  retriever_score=0.1579
  reranked top-K:
    1. d1  cross_score=0.9780          ← 训练对 (q, d1, 1.0) 被背下来
    2. d8  cross_score=0.8024          ← d8 与 abort 无关，却排第二
    3. d6  cross_score=0.6686
  latency: retrieve 0.12ms, rerank 4.81ms

query: centralized authorization check function
  retrieve top-N:
    1. d4  retriever_score=0.5159      ← bi-encoder 已经排对了
    ...
  reranked top-K:
    1. d8  cross_score=1.1841          ← 错！"取消任务"文档排第一，且分数 > 1
    2. d4  cross_score=0.9991          ← 训练标签 1.0
    3. d2  cross_score=0.8358
  latency: retrieve 0.14ms, rerank 2.53ms

query: how do we cancel a job
  retrieve top-N:
    1. d3  retriever_score=0.4304      ← bi-encoder 被 how/a 等停用词误导
    2. d4  retriever_score=0.2916
    3. d8  retriever_score=0.2586      ← gold 在第 3
    ...
  reranked top-K:
    1. d8  cross_score=1.0152          ← rerank 把第 3 提到第 1
    2. d3  cross_score=0.9986
    3. d6  cross_score=0.7758
  latency: retrieve 0.15ms, rerank 2.35ms
```

逐项解读：

- **loss 0.5356 → 0.0003**：训练集被几乎完美拟合。所有出现在训练集里的 (query, doc) 对，分数都非常接近标签（d1 0.978、d4 0.999、d8 1.015）。
- **cancel 查询**是讲义所说的理想情形："picking the answer that the bi-encoder ranked second or third"——bi-encoder 把 gold 排第 3，rerank 把它提到第 1。
- **authorization 查询**暴露了问题：bi-encoder 本来排对了，rerank 反而排错。我们额外做了几个实验：
  - query 为空串时，cross-encoder 对 8 篇文档的打分排序是 d8（0.993）> d1 > d6 > …——**不看 query 也会给 d8 高分**，说明模型学到的主要是"文档先验"（d8 和 d6 都是训练集中某个 query 的唯一正例）；
  - 换成训练集外的说法 "stop an upload that failed"，排第一的是 d6（rank fusion），gold d1 排在倒数第二；
  - 扫描 N：N = 3 或 5 时三个 query 的 top-1 全对，N = 8 时 authorization 查询错，N ≤ 2 时 cancel 查询的 gold 进不了候选池。第一阶段在这里起到了"过滤噪声"的作用（详见测验 Q10）。
- **延迟**：bi-encoder 检索 8 篇约 0.12–0.15ms，cross-encoder 重排 8 个候选约 2.4–4.8ms，单个候选的成本比检索高一个数量级以上。第一次调用最慢（4.81ms），之后稳定在约 2.5ms，这是 PyTorch 的预热开销。讲义的观点得到印证："The cross-encoder takes longer per call but does not run on the full corpus."
- **讲义表格的 Recall@1 数字**（0.62/0.81/0.86/0.86）是"示意形状"，讲义自己说明 "not measurements from this fixture"，demo 也没有输出任何 recall 指标。

---

## 7. 动手改一改

1. **讲义练习 1（扫描 N）**：写一个循环，对 N ∈ {1, 2, 3, 5, 8} 跑 `pipeline`，统计三个 query 中 rerank 后 top-1 等于 gold（d1、d4、d8）的比例，同时打印 gold 是否在 top-N 中。验证"recall@N 封顶"并找出本 fixture 的最佳 N。
2. **讲义练习 2（训练轮数）**：把 `epochs` 设为 1、10、30、60，每次计算"正例平均分 − 负例平均分"（margin）。再准备 3 条**不在训练集**的改写 query，观察 margin 在训练集与改写集上的差别——这就是过拟合的直接证据。
3. **讲义练习 3（CLS 头）**：按测验 Q11 写 `CLSCrossEncoder`，对比两种池化的 loss 曲线和 rerank 结果。
4. **修复数据泄漏**：把 `main` 中的 3 个 query 换成训练集外的说法（如 "stop an upload that failed"、"who is allowed to access a resource"、"terminate a running worker"），重新观察 rerank 效果；再给每个训练 query 增加 2–3 个困难负例，看结果是否改善。
5. **换损失函数**：把 `MSELoss` 换成 `BCEWithLogitsLoss`（标签二值化，≥ 0.5 记为 1），推理时用 `torch.sigmoid` 得到 [0, 1] 的分数；再实现讲义"Use It"中的置信阈值：rank-1 分数低于阈值时打印 "I am not confident"。
6. **进阶（讲义练习 5）**：把 `BiEncoder` 换成第 65 节的 hybrid 检索器，比较"只用第一阶段"与"两阶段"的 top-K 差异；再给 `rerank` 加一个按 `(query, doc_id)` 的字典缓存，测量缓存命中时的延迟。

---

## 8. 常见坑

- **把 query 和文档顺序搞反**：cross-encoder 不对称，训练怎么打包，推理就必须怎么打包（实测颠倒后 0.978 → 0.530）。
- **忘记 `key_padding_mask` 或池化时没排除 PAD**：PAD 会参与注意力和平均，长短不同的文档分数会被长度"污染"。
- **以为训练 loss 低就说明 reranker 好**：本节 loss 0.0003，但换个说法就排错。必须在独立 query 上看 MRR/nDCG。
- **评估 query 与训练 query 重叠**：讲义明确警告，本节 demo 就是反例。
- **N 设成全库或等于 K**：前者让第一阶段失去意义（且真实语料跑不动），后者让 rerank 无法改变 top-K 集合。
- **把无界回归分数当概率用**：本节分数可以 >1（d8 得 1.1841），直接拿来做拒答阈值很不可靠，需要 sigmoid/校准。
- **逐个候选调用模型**：不 batch 时延迟乘以 N（讲义 "Batching matters"）。
- **截断时把 query 或 SEP 切掉**：硬截断尾部会丢掉末尾 `[SEP]`，长 query 时甚至丢掉整个文档，应优先截断文档。
- **在构造函数里设全局种子**：会影响调用方其它随机过程（例如测试中先 `_set_seed()` 再 `torch.randint`，之后构造模型又重置一次）。

---

## 9. 测试在验证什么

测试文件：`tests/test_reranker.py`（`unittest` 风格，pytest 也能直接收集）。运行方式：在 `code/` 目录下执行 `python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。文件开头把 `code/` 加入 `sys.path`，以便 `from main import ...`。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `TestTokenizePair.test_packs_with_separators` | 首位是 CLS（2）、序列中出现 SEP（1）、`ids` 与 `type_ids` 都被补齐到 `max_len=16` |
| `TestTokenizePair.test_type_ids_split_query_and_doc` | `type_ids` 以 0 开头，且存在值为 1 的文档段 |
| `TestTokenizePair.test_truncates_past_max_len` | 200 个词的长文档被截断到 `max_len=32` |
| `TestCrossEncoderForward.test_forward_returns_scalar_per_batch_row` | 输入 `(4, 48)` 时输出形状为 `(4,)`——每对一个标量 |
| `TestCrossEncoderForward.test_deterministic_init` | 两次构造的模型参数完全相同（`torch.allclose`） |
| `TestTrainTiny.test_loss_decreases` | 小模型（d_model=32）训练 40 轮，最终 loss 低于初始值且 < 0.1 |
| `TestTrainTiny.test_positive_scores_above_negative_after_training` | 训练后，abort 查询下"abort 文档的改写"排在"天空白云"无关文本之前 |
| `TestRerank.test_returns_top_k` | 5 个候选、`top_k=3` 时返回 3 个 |
| `TestRerank.test_handles_empty` | 空候选返回空列表 |
| `TestRerank.test_top_k_larger_than_input_returns_all` | `top_k` 大于候选数时返回全部 |
| `TestPipeline.test_pipeline_reports_two_latencies` | 返回字典包含两阶段结果与两个正的延迟值，top-K 长度为 3 |
| `TestPipeline.test_pipeline_reorders_bi_encoder_output` | abort 查询下 d1 在 rerank 后的 top-3 中 |

实际运行结果：

```text
............                                                             [100%]
12 passed in 4.28s
```

几点评价：

- `test_deterministic_init` 在每次构造前都调用了 `_set_seed()`，但构造函数内部本身就会设种子，所以这个测试即使去掉外部的 `_set_seed()` 也必然通过——它验证的其实是"构造函数内部设种子"这件事。
- `test_positive_scores_above_negative_after_training` 用的负例是"fluffy clouds drift across a summer afternoon sky"，与语料毫无词汇重叠，是一个很弱的检验；改用同主题的困难负例（如 d2 "Uploading large files…"）才能真正考察区分能力。
- `test_pipeline_reorders_bi_encoder_output` 名字说"重排了 bi-encoder 的输出"，但只断言 d1 在 top-3 中；而 d1 本来就是 bi-encoder 的第 1 名，这个测试并没有验证"重排"。
- 没有任何测试检查 rerank 在**训练集外 query** 上的效果，也没有检查 authorization 查询的 top-1——这正是本节 demo 出错的地方。
