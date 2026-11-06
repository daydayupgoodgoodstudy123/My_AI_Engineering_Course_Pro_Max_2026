# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 63 节 多模态 Evaluation ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`cd code && python3 main.py`；测试 `python3 -m unittest test_main.py` ｜ **依赖**：`torch`、`numpy`（第三方）；标准库 `importlib`、`math`、`sys`、`dataclasses`、`pathlib`。运行时还会加载 `62-vision-language-pretraining/code/main.py`（以及它依赖的 59/60/61 节代码）

---

## 1. 这份代码在考察什么

上一节训练了"对比 + captioning"的多模态模型，这一节给它装上"尺子"。代码从零实现三个评估面：

1. **检索**：由图文余弦相似度矩阵计算图→文、文→图两个方向的 Recall@1/5/10。
2. **VQA**：把 (图像, 问题) 送进 decoder，取最后一个问题 token 处的 argmax 作为答案，与参考答案做 exact match。
3. **Captioning**：从 token 0 开始贪心生成 8 个 token，对多条参考计算带平滑和 brevity penalty 的句子级 BLEU-4，再取平均。
4. **评估集构造**：`build_eval_suite` 生成 50 个样本的检索对、VQA 三元组、多参考 caption。
5. **before/after 对比**：未训练模型评估一次 → 训练 50 步 → 再评估一次。

> 一句话：**把三种多模态指标写成几个"薄函数"，算式完全透明**。但这个 demo 的评估集与训练集 caption 完全重叠、VQA 任务不可学、BLEU 平滑会给随机输出约 0.13 分——这些问题恰恰是学习"如何正确评估"的最好素材。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_load_module` + `_pretrain` | 函数 / 模块 | 按路径加载第 62 节，取出 `MultimodalModel`、`PretrainConfig`、`make_mock_corpus`、`sample_batch`、`PAD_ID` | 代码复用 |
| `RetrievalPair` / `VQATriple` / `CaptionSample` / `EvalSuite` | dataclass | 评估数据的结构化容器 | 评估集 |
| `recall_at_k` | 函数 | `(N,N)` 相似度 → `(i2t, t2i)` 召回率 | R@K |
| `vqa_exact_match` | 函数 | 预测与参考逐个比较，返回命中比例 | VQA EM |
| `_ngrams` / `_count` | 辅助函数 | 生成 n-gram 列表；手写计数字典 | n-gram 统计 |
| `bleu4` | 函数 | clipped 精确率 × 几何平均 × brevity penalty，多参考、可平滑 | BLEU-4 |
| `build_eval_suite` | 函数 | 生成 50 条检索对 / VQA 三元组 / 多参考 caption | 评估集构造 |
| `_stack_images` | 辅助函数 | `torch.cat` 拼图像 | 批处理 |
| `evaluate` | 函数 | 依次计算 6 个检索指标、VQA EM、平均 BLEU-4 | 评估执行 |
| `_print_metrics` / `main` | 函数 | 构建模型与评估集、训练前后评估、打印差值 | 演示 |

数据流：

```text
build_eval_suite(seed=7777) ─► EvalSuite
                                  │
MultimodalModel(cfg) ─► evaluate ─┼─ retrieval: encode_image + text_encoder ─► sim (50,50) ─► recall_at_k ×3
                                  ├─ vqa: decoder(question, memory) ─► 最后非 PAD 位置 argmax ─► vqa_exact_match
                                  └─ caps: 从 [0] 贪心生成 8 token ─► bleu4(gen, refs) ─► 平均
训练 50 步（与第 62 节相同的循环）─► 再 evaluate ─► 打印 before / after / delta
```

---

## 3. 逐段精讲

### 3.1 加载第 62 节与数据结构

```python
LESSON_62 = THIS_DIR.parent.parent / "62-vision-language-pretraining" / "code"
_pretrain = _load_module("pretrain_lesson62", LESSON_62 / "main.py")
MultimodalModel = _pretrain.MultimodalModel
...

@dataclass
class VQATriple:
    image: torch.Tensor
    question_ids: torch.Tensor
    answer_id: int

@dataclass
class EvalSuite:
    retrieval: list[RetrievalPair]
    vqa: list[VQATriple]
    caps: list[CaptionSample]
```

- `_load_module` 与第 62 节同一个写法（详见 62 节讲解 3.1）。加载 62 节时，62 节自己又会加载 59/60/61 节，形成一条依赖链。
- 这里的 dataclass **没有** `frozen=True`，只是带类型注解的数据容器，让 `suite.vqa[i].answer_id` 这样的访问比元组下标更清晰。
- `CaptionSample.references: list[list[int]]`：每张图可以有多条参考 caption。

### 3.2 `recall_at_k`

```python
def recall_at_k(sim, k):
    if sim.dim() != 2 or sim.shape[0] != sim.shape[1]:
        raise ValueError(...)
    n = sim.shape[0]
    if k < 1 or k > n:
        raise ValueError(...)

    targets = torch.arange(n, device=sim.device)

    topk_i2t = sim.topk(k, dim=1).indices
    hits_i2t = (topk_i2t == targets.unsqueeze(1)).any(dim=1).float().mean().item()

    sim_t = sim.T
    topk_t2i = sim_t.topk(k, dim=1).indices
    hits_t2i = (topk_t2i == targets.unsqueeze(1)).any(dim=1).float().mean().item()
    return hits_i2t, hits_t2i
```

| 步骤 | 形状 / 含义 |
|------|-----------|
| `sim` | `(N, N)`，行 = 图像，列 = caption |
| `sim.topk(k, dim=1).indices` | `(N, k)`：每张图相似度最高的 k 个 caption 的下标 |
| `targets.unsqueeze(1)` | `(N, 1)`：每行的正确下标（对角线） |
| `==` 广播 | `(N, k)` 布尔：top-k 中哪一个是正确答案 |
| `.any(dim=1)` | `(N,)`：这一行是否命中 |
| `.float().mean()` | 命中比例，即 R@K |

- 文→图方向直接对 `sim.T` 重复一遍。两个方向的结果可以不同（测验 Q2）。
- `k` 必须在 `[1, N]`：`topk` 在 k > N 时会报错，这里提前给出清晰的 `ValueError`。
- 假设"第 i 张图只与第 i 条 caption 匹配"。真实 COCO 每张图有 5 条 caption，图→文时任一条命中就算对，需要改写成"正确集合"而不是单个对角线下标。
- 并列分数时 `topk` 的顺序不保证，会影响 R@K（测验 Q12）。

### 3.3 `vqa_exact_match`

```python
def vqa_exact_match(predictions, references):
    if len(predictions) != len(references):
        raise ValueError(...)
    if not predictions:
        return 0.0
    hits = sum(1 for p, r in zip(predictions, references) if int(p) == int(r))
    return hits / len(predictions)
```

- 每个样本 0/1，再取平均。`int(p)` 让 Python int 和 numpy/torch 整数都能比较。
- 空列表返回 0.0 而不是除以 0。
- 讲义提到 VQA v2 的 soft accuracy（`min(人数/3, 1)`），这里为了清晰只做单答案 EM（练习 2 让你补上）。

### 3.4 n-gram 辅助函数与 `bleu4`

```python
def _ngrams(seq, n):
    if len(seq) < n:
        return []
    return [tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)]

def _count(ngrams):
    out = {}
    for g in ngrams:
        out[g] = out.get(g, 0) + 1
    return out
```

- n-gram 用 `tuple` 表示，因为 tuple 可哈希、能做字典的键（list 不行）。
- `_count` 等价于 `collections.Counter(ngrams)`，手写是为了展示原理。

```python
    for n in range(1, 5):
        gen_counts = _count(_ngrams(generated, n))
        ref_max_counts = {}
        for ref in references:
            for g, c in _count(_ngrams(ref, n)).items():
                if c > ref_max_counts.get(g, 0):
                    ref_max_counts[g] = c

        clipped = 0
        for g, c in gen_counts.items():
            clipped += min(c, ref_max_counts.get(g, 0))
        total = sum(gen_counts.values())

        if total == 0:
            return 0.0
        if clipped == 0:
            if smoothing:
                clipped = 1
                total = total + 1
            else:
                return 0.0
        log_p_sum += weights[n - 1] * math.log(clipped / total)
```

- **多参考 clipping**：对每个 n-gram，取它在各条参考中出现次数的**最大值**作为上限；生成中出现再多次也只按上限计。这是 BLEU 防"重复刷分"的关键（测验 Q3）。
- `log_p_sum` 累加 `¼ · log p_n`，最后 `exp` 得到四阶精确率的**几何平均**。用对数相加而不是连乘，数值更稳定。
- ⚠️ `total == 0`（生成长度 < n）时**直接返回 0**，即使开启平滑。生成 3 个 token、全部正确也得 0（测验 Q9）。
- ⚠️ **平滑方式**：只对 clipped = 0 的阶"分子分母各加 1"。docstring 称其为 Chen & Cherry method 1，但 NLTK 的 method1 是给 0 计数加 epsilon = 0.1，method2 才是 add-one（且作用于所有 n ≥ 2 的阶）。我们用 NLTK 3.10 对照：不需要平滑的样例两者完全一致；需要平滑的样例本实现 0.2937、method1 0.1729、method2 0.3493。
- ⚠️ 平滑的副作用：完全不相关的 8 token 生成也能得约 0.13；重复 token `[7,7,7,7]` 对 `[7,3,5,9]` 能得 0.32。

```python
    gen_len = len(generated)
    closest_ref_len = min(references, key=lambda r: (abs(len(r) - gen_len), len(r)))
    ref_len = len(closest_ref_len)
    if gen_len > ref_len:
        bp = 1.0
    else:
        bp = math.exp(1.0 - ref_len / max(1, gen_len))
    return bp * math.exp(log_p_sum)
```

- **最接近的参考长度**：`key` 返回元组 `(长度差, 长度)`，长度差相同时选更短的参考——与 BLEU 标准实现一致。
- `gen_len > ref_len` 时 BP = 1；否则 `exp(1 − r/g)`。相等时 `exp(0) = 1`，两种写法结果相同。
- `max(1, gen_len)` 防除零（实际前面已经对空生成返回 0）。
- ⚠️ 标准 BLEU 是 **corpus 级**的：先把全部句子的 clipped 计数、总数、长度累加，再算一个 BLEU。本节 `evaluate` 对每句算 BLEU 再平均，是"平均句子级 BLEU"，数值通常不同。

### 3.5 `build_eval_suite`

```python
    base_pairs = make_mock_corpus(seed=seed, n_pairs=n_samples,
                                  vocab_size=vocab_size, max_len=max_len)

    for i, (img, ids) in enumerate(base_pairs):
        retrieval.append(RetrievalPair(image=img, caption_ids=ids))

        q_seed = seed + 7919 + i
        q_rng = np.random.default_rng(q_seed)
        q_len = min(int(q_rng.integers(3, max(4, max_len // 2))), max_len)
        question_ids = np.zeros((max_len,), dtype=np.int64)
        question_ids[:q_len] = q_rng.integers(1, vocab_size, size=q_len)
        answer_id = int(ids[0, 0].item())
        vqa.append(VQATriple(...))

        cap_refs = [[int(t) for t in ids[0].tolist() if int(t) != PAD_ID]]
        for k in range(2):
            shift = (i + k + 1) % 5
            variant = [(t + shift) % vocab_size if t != 0 else 0 for t in cap_refs[0]]
            variant = [t for t in variant if t != PAD_ID]
            if variant:
                cap_refs.append(variant)
        caps.append(CaptionSample(image=img, references=cap_refs))
```

- **检索对**：直接复用 62 节的 `make_mock_corpus`，只是换了 seed。
- ⚠️ **泄漏**：`make_mock_corpus` 里 caption 只由下标 i 决定，seed 只影响图像噪声。我们实测 `build_eval_suite(7777, 50, 128, 10)` 的 50 条 caption 与训练语料 `make_mock_corpus(1, 200, 128, 10)` 前 50 条**全部相同**，图像亮度档也相同。讲义"held out from the training corpus"不成立（测验 Q7、Q10）。
- **VQA 三元组**：问题是 3–4 个随机 token（7919 是一个质数，用来错开随机种子）；答案是 caption 的第一个 token。问题与答案、图像都无关，答案只能由下标 i 决定，**任务不可学**（测验 Q11）。
- **多参考 caption**：第 0 条是原 caption（去掉 PAD），另外两条是把每个 token 整体平移 `shift` 的版本。例如第 0 个样本：`[1,4,7,10,13,16]`、`[2,5,8,11,14,17]`、`[3,6,9,12,15,18]`。它们仍然是公差 3 的等差数列。
- ⚠️ 若 shift 后某个 token 恰好变成 0（`(t + shift) % vocab_size == 0`），它会被当作 PAD 删掉，参考 caption 中间会"少一个词"。

### 3.6 `evaluate`：检索部分

```python
    model.eval()
    with torch.no_grad():
        images = _stack_images([p.image for p in suite.retrieval])
        captions = torch.cat([p.caption_ids for p in suite.retrieval], dim=0)

        memory, img_emb = model.encode_image(images)
        txt_emb = model.text_encoder(captions)
        img_n = F.normalize(img_emb, dim=-1)
        txt_n = F.normalize(txt_emb, dim=-1)
        sim = img_n @ txt_n.T

        r1_i, r1_t = recall_at_k(sim, 1)
        r5_i, r5_t = recall_at_k(sim, min(5, sim.shape[0]))
        r10_i, r10_t = recall_at_k(sim, min(10, sim.shape[0]))
```

- `model.eval()` + `torch.no_grad()`：推理模式、不记录梯度。注意函数结束后模型仍处于 eval 模式，`main` 在训练前手动调用了 `model.train()`。
- 相似度不乘 logit scale：排序只看相对大小，乘正数不改变 R@K。
- `min(5, N)`：评估集小于 5 时自动降级，避免 `recall_at_k` 抛错。

### 3.7 `evaluate`：VQA 部分

```python
        vqa_logits = model.decoder(vqa_q, vqa_memory)
        last_non_pad = (vqa_q != PAD_ID).sum(dim=1).clamp(min=1) - 1
        batch_idx = torch.arange(vqa_logits.size(0), device=vqa_logits.device)
        last_step = vqa_logits[batch_idx, last_non_pad, :]
        preds = last_step.argmax(dim=-1).tolist()
```

- `(vqa_q != PAD_ID).sum(dim=1) - 1`：每个问题最后一个非 PAD token 的位置（假设 PAD 都在末尾）。`clamp(min=1)` 防止全 PAD 时得到 −1。
- `vqa_logits[batch_idx, last_non_pad, :]`：两组整数数组的**花式索引**，一次取出每个样本各自位置的 logits，形状 `(50, 128)`。
- 本质上是"让 caption decoder 在问题末尾续写一个 token"，然后拿它当答案。模型从未在 VQA 上训练，我们实测 32% 的预测等于"最后一个问题 token + 3"——它在续写等差数列。

### 3.8 `evaluate`：captioning 部分

```python
        cap_len = min(8, model.cfg.max_text_len - 1)
        prompts = torch.zeros(cap_memory.shape[0], 1, dtype=torch.long)
        generated_ids = [[] for _ in range(cap_memory.shape[0])]
        for step in range(cap_len):
            logits = model.decoder(prompts, cap_memory)
            next_tok = logits[:, -1, :].argmax(dim=-1)
            for b, t in enumerate(next_tok.tolist()):
                generated_ids[b].append(int(t))
            prompts = torch.cat([prompts, next_tok.unsqueeze(1)], dim=1)
```

- **贪心解码**：每步对整个前缀重新前向一次（没有 KV cache），取最后一个位置的 argmax，拼到前缀后面。
- `cap_len = min(8, max_text_len − 1)`：前缀长度最多是 `1 + 8 = 9`，不超过 decoder 的位置上限 10。
- ⚠️ 起始 token 是 **0 = PAD**。训练时没有 BOS，PAD 只出现在 caption 结尾之后（且对应目标被忽略），模型从未学过"PAD 之后该说什么"，所以第一个词基本靠运气。
- ⚠️ 没有停止条件：总是生成 8 个 token，即使生成了 PAD 也不停，PAD 会留在 `generated_ids` 中参与 BLEU。
- 训练后我们打印生成结果：50 张图只产生了 **4 种**不同的 caption（如 `[80, 83, 86, 89, 24, 27, 30, 33]`），说明 decoder 学到了"+3"规律但没有利用图像。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 指标写成纯函数、与数据加载分离 | 讲义："swap `build_eval_suite` for a real loader and keep the function bodies" | 无，这是好的工程实践 |
| 手写 BLEU，不用库 | 让算式透明 | 平滑方式与命名不符；生产用 `sacrebleu` / COCO caption 官方脚本保证可比性 |
| 句子级 BLEU 求平均 | 简单 | 与标准 corpus BLEU 不等价；短句方差大 |
| 只对 0 计数 add-one 平滑 | 避免整句为 0 | 随机输出约 0.13 分，掩盖真实差异；应报告随机基线 |
| 单答案 exact match | 讲义："for clarity" | VQA v2 需要 soft accuracy 与答案归一化 |
| 单 token 答案 = decoder 续写一个 token | 复用 caption decoder，无需额外头 | 模型没在 VQA 上训练，测的是续写而不是回答 |
| 复用 62 节 `make_mock_corpus` 并换 seed | 省代码 | caption 只依赖下标，评估集与训练集重叠 |
| 50 个样本 | 几秒跑完 | 1 个样本 = 0.02，统计噪声大；应报告置信区间 |
| 贪心解码、从 PAD 开始、固定 8 token | 简单 | 应有 BOS/EOS、beam search 或采样策略 |
| 检索只认对角线 | 一图一 caption 的合成数据 | COCO 一图 5 caption，需支持多正样本 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass`（非 frozen） | `class VQATriple` | 自动生成 `__init__`/`__repr__`，字段可修改 |
| 嵌套泛型注解 | `references: list[list[int]]`、`dict[tuple[int, ...], int]` | `tuple[int, ...]` 表示任意长度的整数元组 |
| 返回元组 | `def recall_at_k(...) -> tuple[float, float]`；`r1_i, r1_t = recall_at_k(sim, 1)` | 一次返回两个方向的结果并解包 |
| `topk` | `sim.topk(k, dim=1).indices` | 返回 values 与 indices 两个字段的命名元组 |
| 广播比较 + `any` | `(topk_i2t == targets.unsqueeze(1)).any(dim=1)` | `(N,k)` 与 `(N,1)` 比较，再按行判断是否有 True |
| 生成器表达式 + `sum` | `sum(1 for p, r in zip(...) if int(p) == int(r))` | 带条件计数 |
| 切片生成 n-gram | `[tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)]` | 滑动窗口；`tuple` 可哈希 |
| `dict.get(key, default)` | `out.get(g, 0) + 1`、`ref_max_counts.get(g, 0)` | 键不存在时返回默认值 |
| `min` + `key=lambda` 返回元组 | `min(references, key=lambda r: (abs(len(r) - gen_len), len(r)))` | 先比第一项，平局再比第二项 |
| `math.log` / `math.exp` | `log_p_sum += ... * math.log(clipped / total)` | 对数域累加实现几何平均 |
| 列表推导式带条件 | `[int(t) for t in ids[0].tolist() if int(t) != PAD_ID]` | 过滤 PAD |
| 条件表达式在推导式里 | `[(t + shift) % vocab_size if t != 0 else 0 for t in ...]` | 每个元素二选一 |
| `enumerate` | `for i, (img, ids) in enumerate(base_pairs)`、`for b, t in enumerate(next_tok.tolist())` | 同时拿下标和元素，可嵌套解包 |
| 花式索引 | `vqa_logits[batch_idx, last_non_pad, :]` | 每个样本取不同位置 |
| `[[] for _ in range(n)]` | `generated_ids` | 创建 n 个**独立**空列表（不能写 `[[]] * n`，那是同一个列表的 n 个引用） |
| `torch.cat` 增长序列 | `prompts = torch.cat([prompts, next_tok.unsqueeze(1)], dim=1)` | 自回归时把新 token 拼到前缀 |
| f-string 格式符 | `{k:12s}`、`{v:.4f}`、`{marker}{abs(d):.4f}` | 宽 12 左对齐字符串；4 位小数 |
| `for k in before:` | 遍历字典的键 | 字典保持插入顺序 |

---

## 6. 运行结果解读

实际运行（PyTorch CPU，约 3.4 秒）：

```text
  text vocab : 128
  embed dim  : 64
  steps      : 50

building eval suite (50 samples, held-out seed)...
  retrieval pairs : 50
  vqa triples     : 50
  caption samples : 50

metrics BEFORE training (50-step random init):
  R@1_i2t      : 0.0200       ← 随机基线 0.02
  R@1_t2i      : 0.0400
  R@5_i2t      : 0.1000       ← 随机基线 0.10
  R@5_t2i      : 0.0800
  R@10_i2t     : 0.1600       ← 随机基线 0.20
  R@10_t2i     : 0.2000
  vqa_em       : 0.0200       ← 50 个中对 1 个
  bleu4        : 0.1220       ← 随机输出在此实现下约 0.13

training for 50 steps on the mock corpus...
  step   0  total 8.3900
  ...
  step  49  total 6.0834

metrics AFTER training:
  R@1_i2t      : 0.0000
  R@1_t2i      : 0.0600
  R@5_i2t      : 0.1800
  R@5_t2i      : 0.2000
  R@10_i2t     : 0.2600
  R@10_t2i     : 0.3800
  vqa_em       : 0.0000
  bleu4        : 0.1730

metric deltas (after - before):
  R@1_i2t      : 0.0000  (-0.0200)
  ...
  R@10_t2i     : 0.3800  (+0.1800)
  vqa_em       : 0.0000  (-0.0200)
  bleu4        : 0.1730  (+0.0510)
```

逐项解读：

- **训练前**：所有检索指标都在随机基线附近；BLEU 0.122 与"随机 8 个 token"的 0.130 相当——平滑带来的保底分。打印标签 "(50-step random init)" 有些误导，此时还没有训练。
- **检索**：R@5/R@10 上升，文→图 R@10 = 0.38 比随机高约 3 个标准误（`sqrt(0.2×0.8/50) ≈ 0.057`），有一定信号；R@1 图→文反而从 0.02 降到 0（就是 1 个样本的差别）。注意评估 caption 与训练 caption 完全相同，文本 embedding 在训练中见过它们。我们补算了 MRR（图→文）≈ 0.107，随机期望 `H₅₀/50 ≈ 0.090`，正确项中位排名 18。
- **VQA**：0.02 → 0.00，都在噪声内（随机 `1/128 ≈ 0.008`）。讲义说"VQA improving above random"与实际输出不符；任务本身不可学，模型也没在 VQA 上训练。
- **BLEU-4**：0.122 → 0.173。训练后 50 张图只生成 4 种 caption，都是"+3 等差"片段，与参考的等差数列有部分 n-gram 重合，于是 BLEU 上升——这是语言先验，不是看图。

我们另外做的验证：

| 实验 | 结果 |
|------|------|
| 评估 caption 与训练前 50 条 caption 比较 | 50/50 完全相同 |
| 随机 8 token 生成的平均 BLEU | 0.130；全 PAD 生成 0.119 |
| 训练后生成 caption 的去重数量 | 50 张图只有 4 种 |
| VQA 预测 = 最后问题 token + 3 的比例 | 32% |
| 本实现 vs NLTK（无需平滑的样例） | 完全一致（0.6804、0.3457、0.3679） |
| 本实现 vs NLTK（需要平滑的样例） | 0.2937 vs method1 0.1729 / method2 0.3493 |

---

## 7. 动手改一改

1. **修复泄漏**：一次生成 250 条语料，前 200 条训练、后 50 条评估；再写一个断言检查两者 caption 无重叠。比较修复前后的检索指标。
2. **讲义练习 4（MRR）**：实现 `mean_reciprocal_rank`，与 R@K 一起打印，并打印随机基线 `H_N/N`（测验 Q12）。
3. **讲义练习 3 + 平滑修正**：让 `bleu4` 在生成长度 < 4 时不直接返回 0（跳过该阶并重新归一化权重，或 epsilon 平滑）；同时把平滑改成真正的 method1（epsilon = 0.1），对比随机基线的变化。
4. **讲义练习 1（CIDEr）**：对每个 n-gram 计算 TF-IDF（文档 = 每张图的参考集合），用生成与参考 TF-IDF 向量的余弦相似度打分，比较 CIDEr 与 BLEU 对"+3 等差但起点错误"的 caption 的打分差异。
5. **讲义练习 2（soft accuracy）**：给每个 VQA 样本造 10 个"人工答案"（例如 6 个正确答案 + 4 个噪声），实现 `min(n/3, 1)` 的 soft accuracy。
6. **讲义练习 5 + 置信区间**：在训练第 0/10/20/30/40/50 步分别评估，画学习曲线；对每个指标做 1000 次 bootstrap，给出 95% 置信区间，判断哪些变化是显著的。

---

## 8. 常见坑

- **不报随机基线**：R@10 = 0.2 在 N = 50 时就是随机；BLEU 0.12 在这个平滑下就是随机。
- **评估集泄漏**：只换 seed 不等于 held-out，必须检查内容重叠。
- **只看一个方向的检索**：图→文和文→图可以差很多。
- **句子级 BLEU 当 corpus BLEU 报**：两者数值不同，与论文对比时必须用相同的实现（如 sacrebleu / COCO 官方脚本）。
- **平滑掩盖退化**：重复 token、无关输出都能拿到不低的分数。
- **把续写当回答**：未在 VQA 上训练的 LM 在问题末尾预测的是"下一个词"，不是答案。
- **小样本下结论**：50 个样本中 1 个样本 = 0.02。
- **`[[]] * n`**：创建的是同一个列表的 n 个引用，往一个里 append 会出现在所有里；代码用的 `[[] for _ in range(n)]` 才是对的。
- **评估后忘了 `model.train()`**：`evaluate` 会把模型切到 eval 模式，继续训练前要切回来（`main` 做了）。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m unittest -v test_main.py`。

| 测试 | 验证的性质 |
|------|-----------|
| `TestRecallAtK.test_perfect_identity_matrix` | `eye(10) × 10` 时两个方向 R@1 都是 1.0 |
| `TestRecallAtK.test_flipped_matrix_below_top` | 对角线 0、其余 10 时 R@1（图→文）为 0 |
| `TestRecallAtK.test_rejects_invalid_k` | k = 0 和 k = N + 1 都抛 `ValueError` |
| `TestVQAExactMatch.test_all_correct` | 全对 → 1.0 |
| `TestVQAExactMatch.test_half_correct` | 4 个对 2 个 → 0.5 |
| `TestVQAExactMatch.test_length_mismatch_raises` | 长度不同抛 `ValueError` |
| `TestBLEU.test_exact_match_returns_one` | 生成等于参考（9 个 token）→ > 0.99 |
| `TestBLEU.test_disjoint_vocab_returns_zero_without_smoothing` | 关闭平滑、词表不相交 → 0.0 |
| `TestBLEU.test_disjoint_vocab_smoothed_is_below_match` | 开启平滑、不相交 → 低于完美匹配（实际值约 0.135，测试没有检查它有多高） |
| `TestBLEU.test_brevity_penalty_applies_when_generated_short` | 生成 4 个、参考 8 个 → < 1.0（实际 0.368） |
| `TestEvalSuite.test_build_shapes` | 三个列表各 8 条，caption 形状 `(1, 8)` |

实际运行结果：

```text
Ran 11 tests in 0.009s

OK
```

与讲义 Tests 一节的差异：讲义说 "bleu4 returns 0.0 on disjoint vocabulary"，实际只有关闭平滑时才是 0（默认开启平滑时约 0.135）。测试也没有覆盖：评估集与训练集是否重叠、`evaluate` 端到端、生成长度 < 4 时的 BLEU 行为。
