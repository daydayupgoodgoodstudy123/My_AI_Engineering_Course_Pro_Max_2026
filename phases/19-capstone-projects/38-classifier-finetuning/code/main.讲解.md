# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 38 节 通过替换输出头进行分类器 Fine-Tuning ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下，CPU 约 13 秒；成功退出码 0，任一方式 F1 ≤ 0.5 时退出码 1）；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests` ｜ **依赖**：`torch`、`numpy`（第三方）；`math`、`random`、`sys`、`dataclasses`、`typing`（标准库）。不写任何文件，不需要网络。

---

## 1. 这份代码在考察什么

这份代码用一个极小的 Transformer 演示"换头微调"（head swap）的完整流程：

1. **body 与 head 分离**：`LMBody` 只输出 hidden states；预训练时接 `LMHead`（投影到词表），微调时换成 `Classifier.head`（投影到 2 类）。
2. **两种训练方式共用一个循环**：`freeze_body` / `unfreeze_body` 切换 `requires_grad`，`train_classifier` 只把可训练参数交给优化器。
3. **padding 与 mask 的正确处理**：注意力屏蔽 pad 作为 key，mean pool 按 mask 加权。
4. **从 logits 到 P/R/F1 与混淆矩阵**：`evaluate` 手工计数 TP/FP/FN/TN。
5. **成本对比**：head-only 只有 130 个可训练参数，full FT 有 118,402 个。

> 一句话：**body 是昂贵的、可复用的；head 是便宜的、按任务替换的；"训不训 body"是一个 `requires_grad` 开关**。同时也要看清本节的两个"坑"：body 没有因果 mask（LM 预训练会偷看答案），以及 fixture 只有 73 种句子、测试集几乎全在训练集里——所以两种方式都拿到 F1 = 1.000。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ByteTokenizer` | 类 | 字节 → id（0–255），PAD = 256，VOCAB = 260；`encode` 返回 `(ids, attention_mask)` | 分词 + padding |
| `MultiHeadAttention` | `nn.Module` | 融合 qkv（无 bias）、按 pad mask 屏蔽 key、softmax、`nan_to_num` | 注意力（**双向**） |
| `FeedForward` / `Block` | `nn.Module` | `d → 4d → d` + GELU；pre-norm 残差块 | Transformer block |
| `LMBody` | `nn.Module` | token + 位置 embedding → N 个 block → `ln_f`，返回 `(B, T, D)` | body `f_θ` |
| `mean_pool` | 函数 | 按 mask 加权平均，`(B, T, D) → (B, D)` | Pooling |
| `Classifier` | `nn.Module` | body + mean pool + `Linear(D, 2)` | head `g_φ` |
| `LMHead` | `nn.Module` | body + `Linear(D, vocab)`，只在预训练中使用 | 被换掉的旧头 |
| `freeze_body` / `unfreeze_body` / `trainable_params` | 函数 | 切换并统计可训练参数 | 冻结 |
| `SPAM_TEMPLATES` / `HAM_TEMPLATES` / `SLOTS` / `fill` / `make_dataset` | 常量 / 函数 | 模板 + 槽位生成 400 + 400 条短信并打乱 | 合成 fixture |
| `stratified_split` | 函数 | 每类各按 80/20 切分 | 分层划分 |
| `ClassificationDataset` / `LMDataset` | `Dataset` | 返回张量化的 `(ids, mask, y)` 或 `(ids, mask)` | 数据管道 |
| `pretrain_quick` | 函数 | 5 个 epoch 的 next-token 训练，loss 只算非 pad 目标 | 预训练（简化） |
| `TrainReport` / `train_classifier` | dataclass / 函数 | 共享训练循环，记录每 epoch 平均 loss 和可训练参数量 | 微调 |
| `Metrics` / `precision_recall_f1` / `evaluate` | dataclass / 函数 | 计数 + 指标 + 混淆矩阵字符串 | 评估 |
| `Config` / `build_model` / `DemoReport` / `run_demo` / `_clone_body` | — | 配置、组装、演示、复制 body | 演示 |

数据流：`make_dataset` → `stratified_split`（640 / 160）→ `pretrain_quick(LMBody + LMHead, 训练文本)` → `_clone_body` 复制两份 body → ① `freeze_body` + `train_classifier`（lr 5e-3）→ `evaluate`；② `unfreeze_body` + `train_classifier`（lr 1e-3）→ `evaluate` → `SUMMARY`，`passed()` 决定退出码。

---

## 3. 逐段精讲

### 3.1 `ByteTokenizer`：最简单的分词 + padding

```python
class ByteTokenizer:
    PAD_ID = 256
    VOCAB = 260  # leave headroom for future specials

    def encode(self, text: str, max_len: int) -> Tuple[List[int], List[int]]:
        raw = list(text.encode("utf-8", errors="ignore"))[:max_len]
        attn = [1] * len(raw)
        while len(raw) < max_len:
            raw.append(self.PAD_ID)
            attn.append(0)
        return raw, attn
```

- 每个 UTF-8 字节就是一个 token（0–255），PAD 用 256，词表留到 260 给将来的特殊 token。
- 返回两个等长列表：`ids` 与 `attention_mask`（真实 token 为 1、pad 为 0），右侧 padding。
- **注意**：截断按**字节**进行：实测 800 条消息字节长度 23–54（平均 34.6），**435 条超过 32 被截断**，例如 `"URGENT call 09061701461 to claim your prize"` 只剩 `"URGENT call 09061701461 to claim"`。讲义说消息"between 5 and 25 tokens long"，那是按单词算的。多字节字符（如中文）还可能被切成半个字符。
- `errors="ignore"` 在 `str.encode("utf-8")` 中几乎不会触发（只有孤立代理字符才会编码失败），这里主要是防御性写法。
- `decode` 过滤掉 ≥ 256 的 id（PAD），测试 `test_decode_skips_pad` 验证。

### 3.2 注意力：只有 pad mask，没有因果 mask

```python
    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        B, T, D = x.shape
        qkv = self.qkv(x).view(B, T, 3, self.heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        m = mask.view(B, 1, 1, T).to(att.dtype)
        att = att.masked_fill(m == 0, float("-inf"))
        weights = F.softmax(att, dim=-1)
        weights = torch.nan_to_num(weights, nan=0.0)
        ctx = (weights @ v).transpose(1, 2).contiguous().view(B, T, D)
        return self.out(ctx)
```

形状追踪（demo：B = 32，T = 32，D = 64，4 头，head_dim = 16）：

| 步骤 | 形状 |
|------|------|
| `self.qkv(x)` | `(B, T, 192)` |
| `.view(B, T, 3, 4, 16)` | 把 192 拆成"3 份 × 4 头 × 16 维" |
| `.permute(2, 0, 3, 1, 4)` | `(3, B, 4, T, 16)`，于是 `qkv[0]` 就是 Q |
| `q @ kᵀ / √16` | `(B, 4, T, T)` |
| `mask.view(B, 1, 1, T)` | 广播到每个头、每个 query 行：屏蔽"作为 key 的 pad 列" |
| `weights @ v` → `transpose` → `view` | `(B, T, 64)` |

- mask 只屏蔽**列**（key 维度）：pad 位置作为 query 时仍然会算出 hidden state，但这些行之后在 pooling 中被排除。
- `nan_to_num`：如果一整行都是 `-inf`（整条序列都是 pad），softmax 得到 NaN，替换为 0。正常输入不会发生。
- **注意**：**没有因果 mask**：每个位置都能看到右边的 token。做分类没问题（BERT 也是双向的），但 `pretrain_quick` 用同一个 body 做 next-token prediction，位置 t 能直接看到目标 `ids[t+1]`。实测：原代码 5 个 epoch 预训练 loss 为 `3.83 → 2.21 → 1.11 → 0.33 → 0.076`；加上因果 mask 后为 `3.81 → 2.13 → 1.00 → 0.33 → 0.132`。两者都很低，是因为训练文本只有 72 种不同句子、被背下来了（详见测验 Q9）。
- qkv、out 都 `bias=False`；FFN 带 bias。

### 3.3 `LMBody`、`mean_pool` 与 `Classifier`

```python
    def forward(self, ids: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        B, T = ids.shape
        positions = torch.arange(T, device=ids.device).unsqueeze(0).expand(B, T)
        x = self.tok(ids) + self.pos(positions)
        for block in self.blocks:
            x = block(x, mask)
        return self.ln_f(x)
```

- `arange(T).unsqueeze(0).expand(B, T)`：生成 `(B, T)` 的位置下标，`expand` 不复制内存。
- body 只返回 hidden states，不含任何"任务头"——这是 head swap 的前提。

```python
def mean_pool(hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    m = mask.unsqueeze(-1).to(hidden.dtype)
    summed = (hidden * m).sum(dim=1)
    counts = m.sum(dim=1).clamp(min=1.0)
    return summed / counts
```

- `mask.unsqueeze(-1)`：`(B, T) → (B, T, 1)`，可与 `(B, T, D)` 广播相乘，把 pad 行清零。
- `counts` 是每条序列的有效长度 `(B, 1)`；`clamp(min=1.0)` 防止全 pad 时除以 0（测试 `test_empty_mask_does_not_divide_by_zero`）。
- 例：hidden `[[1,0],[2,0],[99,99]]`、mask `[1,1,0]` → `[1.5, 0.0]`。不加 mask 会得到 `[34, 33]`。

```python
class Classifier(nn.Module):
    def __init__(self, body: LMBody, num_classes: int = 2):
        super().__init__()
        self.body = body
        hidden = body.ln_f.normalized_shape[0]
        self.head = nn.Linear(hidden, num_classes)
```

- 从 `ln_f.normalized_shape[0]` 反推 hidden 维度，不必另传参数。
- head 是 `Linear(64, 2)`：128 + 2 = **130** 个参数，即讲义的 "`hidden_dim * num_classes` weights plus a bias"。
- `LMHead` 结构类似，`Linear(64, 260, bias=False)`；预训练结束后它被直接丢弃——这就是"换头"。

### 3.4 冻结开关

```python
def freeze_body(model: Classifier) -> int:
    n = 0
    for p in model.body.parameters():
        p.requires_grad = False
        n += 1
    return n
```

- 把 body 每个参数的 `requires_grad` 设为 False：反向传播不会为它们计算梯度（输入 ids 本身也不需要梯度，所以 autograd 甚至不会往 body 里回传），自然也不会被更新。
- 返回值是**参数张量个数**（demo 中为 24），不是元素个数——文档写 "Returns count frozen" 容易误解。
- `trainable_params` 统计 `requires_grad=True` 的元素总数，是区分两种方式最直接的"审计记录"。
- 注意：冻结的 body 在 `train_classifier` 中仍处于 `model.train()` 模式。本模型没有 dropout / BatchNorm，所以无影响；若 body 含 dropout，head-only 时通常要把 body 设为 `eval()`，否则冻结的特征本身是随机的。

### 3.5 合成 fixture 与分层划分

```python
def make_dataset(n_per_class: int = 400, seed: int = 0) -> Tuple[List[str], List[int]]:
    rng = random.Random(seed)
    ...
    for _ in range(n_per_class):
        texts.append(fill(rng.choice(SPAM_TEMPLATES), rng))
        labels.append(1)
        texts.append(fill(rng.choice(HAM_TEMPLATES), rng))
        labels.append(0)
    order = list(range(len(texts)))
    rng.shuffle(order)
```

- 使用独立的 `random.Random(seed)`，不受全局随机状态影响，可复现。
- `fill` 按 `SLOTS` 的键顺序替换模板中的 `{key}`，每个出现的槽位随机选一个值。
- **注意**：**样本空间极小**：10 个 spam 模板最多 45 种填充、10 个 ham 模板最多 28 种，合计 73 种，实测 800 条中恰好有 73 种不同句子。spam 模板普遍含大写词、电话号码、URL，ham 全小写——前几个字节就足以区分。

```python
    for y, idxs in by_label.items():
        idxs_copy = list(idxs)
        rng.shuffle(idxs_copy)
        cut = int(len(idxs_copy) * (1.0 - test_frac))
        train_idx.extend(idxs_copy[:cut])
        test_idx.extend(idxs_copy[cut:])
```

- 每个类别单独打乱再切分，测试集 80 spam + 80 ham，保持平衡（测试 `test_stratified_split_preserves_balance`）。
- **注意**：划分单位是"样本"而不是"句子"或"模板"：实测测试集 160 条中 **158 条在训练集中逐字出现**。这是 F1 = 1.000 的根本原因。

### 3.6 `pretrain_quick`：带 mask 的 next-token loss

```python
            logits = head(ids, mask)
            target = ids[:, 1:].contiguous()
            tgt_mask = mask[:, 1:].contiguous()
            logits = logits[:, :-1, :].contiguous()
            loss_full = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                target.view(-1),
                reduction="none",
            )
            loss_full = loss_full.view(target.shape) * tgt_mask
            denom = tgt_mask.sum().clamp(min=1.0)
            loss = loss_full.sum() / denom
```

- 输入/目标错开一位：位置 0..T-2 的 logits 预测 1..T-1 的 token。
- `reduction="none"` 得到每个位置的 loss，再乘 `tgt_mask` 把"目标是 pad"的位置清零，最后除以有效目标个数——这样 pad 不会稀释 loss，也不会让模型学"预测 pad"。
- 只用训练集文本 `tr_t` 预训练，没有把测试文本喂给 body（但由于重复，测试句子基本都已见过）。
- **注意**：因 3.2 节所述缺少因果 mask，这一步并不是真正的语言模型预训练。实测还发现：**随机初始化、完全不预训练**的 body，head-only 训练 20 个 epoch 后测试 F1 同样为 1.0，说明在这个 fixture 上预训练的作用无法体现。

### 3.7 `train_classifier`：一个循环、两种方式

```python
    torch.manual_seed(seed)
    params = [p for p in model.parameters() if p.requires_grad]
    if not params:
        raise ValueError("No trainable parameters. Did you freeze the head as well?")
    opt = torch.optim.Adam(params, lr=lr)
    ...
        for ids, mask, y in train_loader:
            logits = model(ids, mask)
            loss = F.cross_entropy(logits, y)
            opt.zero_grad()
            loss.backward()
            opt.step()
```

- 过滤 `requires_grad` 是讲义强调的"同一 API"：head-only 时优化器里只有 head 的 2 个张量。
- `torch.manual_seed(seed)` 放在开头，让 DataLoader 的 `shuffle` 顺序可复现（它使用全局 torch 随机数）。
- `F.cross_entropy(logits, y)`：logits `(B, 2)`、y `(B,)` 的整数标签，内部做 log-softmax + NLL。
- 返回 `TrainReport(losses, final_loss, trainable)`；每个 epoch 记录的是该 epoch 各 batch loss 的平均值（训练过程中边更新边记录）。
- **注意**：full FT 时 head 和 body 用同一个学习率（1e-3）；讲义 stretch goal 2 和 quiz.json 都提到 body 应用更小的学习率、head 用更大的，需要两个参数组（测验 Q11）。

### 3.8 `evaluate` 与 `Metrics`

```python
@torch.no_grad()
def evaluate(model: Classifier, loader: DataLoader, positive: int = 1) -> Metrics:
    model.eval()
    tp = fp = fn = tn = 0
    for ids, mask, y in loader:
        logits = model(ids, mask)
        pred = logits.argmax(dim=-1)
        for p_i, y_i in zip(pred.tolist(), y.tolist()):
            if p_i == positive and y_i == positive:
                tp += 1
            ...
```

- `argmax` 相当于"spam 概率 > 0.5 就判 spam"，没有可调阈值。
- 用 Python 循环逐个计数，便于读懂；生产中会用向量化写法（`((pred == 1) & (y == 1)).sum()`）。
- `precision_recall_f1` 对每个分母为 0 的情况返回 0.0（测试 `test_all_false_positive`）。
- `Metrics.confusion()` 打印 2×2 表：行是真实标签、列是预测，`[[TN, FP], [FN, TP]]`。

### 3.9 `run_demo` 与 `_clone_body`

```python
    head_only_model = Classifier(_clone_body(body_for_pretrain), num_classes=2)
    full_ft_model = Classifier(_clone_body(body_for_pretrain), num_classes=2)
```

- 两种方式各拿一份**独立复制**的预训练 body（`load_state_dict(body.state_dict())`），保证起点相同、互不影响。讲义 "What you will build" 第 5 条说 "The body is the same instance across regimes"，与代码不符——如果真用同一个实例，full FT 会改动 head-only 模型的 body。
- 两个 `Classifier` 的 head 都在此时随机初始化（各自消耗全局随机数，所以两个 head 的初始值不同）。
- `build_model` 在 demo 中没被用到，只在测试里使用；`np.random.seed` 也只是习惯性设置（本文件不使用 NumPy 随机数）。
- `DemoReport.passed()` 只要求两种方式 F1 > 0.5，阈值很宽松；`sys.exit(run_demo())` 把返回值作为进程退出码，方便 CI 判断。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 字节级 tokenizer | 零依赖、无 OOV | 序列长，`max_len=32` 截掉过半样本；生产用子词 tokenizer，且与预训练 tokenizer 一致 |
| 双向注意力 body | 分类时每个位置看全句，适合 mean pool | 拿它做 next-token 预训练会泄漏目标；预训练需因果 mask |
| mask 加权 mean pool | 简单、对长度稳定、不需要 CLS | 因果 body 下应换 last-token pool；长序列可试 attention pool |
| `requires_grad` 开关 + 过滤优化器参数 | 一个训练函数服务所有方式 | 不支持分组学习率；生产中用参数组 + 不同调度 |
| head-only lr 5e-3、full FT lr 1e-3 | 粗略地让 full FT 更保守 | full FT 下 head 也只有 1e-3；应分组 |
| 模板 + 槽位合成数据 | 可复现、秒级生成 | 只有 73 种句子，测试几乎全泄漏，指标失去区分度；应去重或按模板分组划分 |
| 分层 80/20 划分 | 测试集平衡，P/R 可直接解读 | 未按句子/模板去重 |
| `argmax` 评估 | 简单 | 无法按业务调阈值；生产中看 PR 曲线选阈值 |
| `_clone_body` 复制 body | 两种方式起点一致、互不干扰 | 显存翻倍（小模型无所谓） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类属性 | `PAD_ID = 256`、`VOCAB = 260`；`ByteTokenizer.VOCAB` | 定义在类体中，所有实例共享，可通过类名访问 |
| 类型注解（`typing`） | `Tuple[List[int], List[int]]`、`Sequence[str]` | 旧式写法；与 `dict[int, List[int]]` 新式写法混用 |
| `X | None` 联合类型 | `def run_demo(cfg: Config | None = None)` | 依赖 `from __future__ import annotations` 才能在旧版本 Python 中写 |
| `or` 默认值 | `cfg = cfg or Config()` | `cfg` 为 None 时使用默认配置 |
| `@dataclass(frozen=True)` | `class Config` | 字段不可修改，可安全地作为"配置常量" |
| `@dataclass` 方法 | `Metrics.confusion()`、`DemoReport.passed()` | dataclass 里照样可以写方法 |
| 多重赋值 | `tp = fp = fn = tn = 0` | 同时初始化多个变量 |
| 链式比较之外的条件表达式 | `p = tp / (tp + fp) if (tp + fp) else 0.0` | 三元表达式，处理分母为 0 |
| `dict.setdefault` | `by_label.setdefault(y, []).append(idx)` | 键不存在时先放一个空列表 |
| `random.Random(seed)` | `rng = random.Random(seed)`、`rng.choice`、`rng.shuffle` | 独立的随机数生成器，可复现 |
| 列表推导式 | `[texts[i] for i in order]`、`[p for p in model.parameters() if p.requires_grad]` | 带过滤条件的推导式 |
| 生成器表达式 | `bytes(i for i in ids if i < 256)`、`sum(p.numel() for p in ...)` | 不建中间列表 |
| `zip` | `for p_i, y_i in zip(pred.tolist(), y.tolist())` | 并行遍历两个序列 |
| `Dataset` 协议 | `__len__`、`__getitem__` | 实现这两个方法即可被 `DataLoader` 使用 |
| f-string 格式符 | `{self.tn:>8d}`、`{pre_losses[-1]:.4f}`、`{report.head_only_trainable:>6d}` | 右对齐宽度 8/6 的整数；4 位小数 |
| `print(..., file=sys.stderr)` | 失败信息 | 打印到标准错误 |
| `sys.exit(code)` | `sys.exit(run_demo())` | 以返回值作为进程退出码 |
| 装饰器 | `@torch.no_grad()` | 评估时不建计算图 |
| 张量变形 | `.view`、`.permute(2, 0, 3, 1, 4)`、`.unsqueeze(-1)`、`.expand(B, T)` | 改形状、重排维度、加维度、广播扩展 |
| `masked_fill` | `att.masked_fill(m == 0, float("-inf"))` | 按布尔条件填值 |
| `clamp` | `m.sum(dim=1).clamp(min=1.0)` | 下限截断，防止除零 |
| `if __name__ == "__main__":` | 文件末尾 | 只在直接运行时执行 demo |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU；总耗时约 12.7 秒，退出码 0）：

```text
CLASSIFIER FINE-TUNING DEMO
train=640 test=160 max_len=32

[1/3] pretraining body briefly on the corpus text...
      pretrain final loss = 0.0761          ← 远低于 ln256≈5.55：双向注意力泄漏 + 只有 72 种句子被背下

[2/3] training head-only (body frozen)...
      trainable params = 130                ← 64×2 + 2
      final train loss = 0.0904
      P=1.000 R=1.000 F1=1.000
                pred ham   pred spam
  actual ham          80          0
  actual spam          0         80

[3/3] training full fine-tuning (body unfrozen)...
      trainable params = 118402             ← body 118,272 + head 130
      final train loss = 0.0001
      P=1.000 R=1.000 F1=1.000
  ...（混淆矩阵同上）

SUMMARY
  head-only:  trainable=   130 F1=1.000
  full-FT:    trainable=118402 F1=1.000
```

逐项解读：

- **参数量**：body = token 260×64（16,640）+ 位置 32×64（2,048）+ 2 × 每 block 49,728（ln1 128、qkv 12,288、out 4,096、ln2 128、fc1 16,640、fc2 16,448）+ `ln_f` 128 = 118,272。可训练参数相差约 900 倍。
- **训练 loss**：额外实测每个 epoch 的平均 loss——head-only 为 `0.625, 0.482, 0.405, …, 0.090`，下降平缓（只能调一个线性层）；full FT 为 `0.350, 0.012, 0.0015, …, 0.0002`，第二个 epoch 就几乎为 0（全模型迅速记住了训练集）。
- **耗时**：单独计时，head-only 20 个 epoch 约 2.2 秒，full FT 约 10.8 秒，约 **5 倍**（讲义说"about three times longer"，量级相近）。head-only 快在不需要对 body 反向传播。
- **F1 = 1.000**：讲义说"typically see precision near 0.9 and recall near 0.85"，但实测两种方式都满分。原因见 3.5 节：测试集 158/160 与训练集重复；且随机初始化 body 的 head-only 也是 1.0。这个 demo 能证明"流程跑通"，但不能用来比较两种方式的优劣。

测试运行：`python3 -m pytest -q tests` → `16 passed in 2.48s`。

---

## 7. 动手改一改

1. **修因果 mask**：给注意力加 `causal` 开关，预训练时打开（测验 Q9），比较预训练 loss 曲线。
2. **让评估有意义**：按模板做分组划分（每类留 2 个模板只放测试集），重新跑两种方式，观察 F1 是否开始出现差异；再试试"随机 body + head-only"作为对照。
3. **讲义 stretch goal 1**：实现 `unfreeze_last_block`，可训练参数应为 49,986；三种方式放在一起比较 F1 与耗时。
4. **讲义 stretch goal 2**：改 `train_classifier` 为参数组（head 5e-3 + cosine 调度，body 1e-4 常数），观察 full FT 的 loss 曲线是否更平稳。
5. **讲义 stretch goal 3**：实现 attention pool（一个可学习的 query 向量对所有非 pad 位置做注意力），与 mean pool、last-token pool（测验 Q12）对比。
6. **阈值与 PR 曲线**：在 `evaluate` 中返回 spam 概率，扫描阈值 0.1–0.9 画出 precision / recall 的变化；把 spam 比例降到 15% 重新生成数据，观察 accuracy 与 F1 的差别。

---

## 8. 常见坑

- **pooling 不加 mask**：pad 位置的 hidden state 不是 0，平均进来会把短句的表示拉偏。
- **用双向 body 做 next-token 预训练**：目标 token 对模型可见，loss 虚低，得到的 body 在自回归推理时无法使用。
- **冻结后仍把全部参数传给优化器**：PyTorch 的 Adam 会跳过 `grad=None` 的参数，所以眼下不会出错；但同一个优化器若在之后被复用、而参数又被解冻，它们就会悄悄开始更新（还带着同一个学习率）。按 `requires_grad` 过滤、意图写在代码里最清晰。
- **head 也被冻结**：过滤后参数列表为空，本代码会抛 `ValueError` 提醒。
- **冻结 body 却忘了 `eval()`**：含 dropout 的 body 在 head-only 时会给出随机特征。
- **只看 F1 = 1.0 就下结论**：先查训练/测试重复与"捷径特征"，再做随机 body 的对照实验。
- **字节级截断**：`max_len` 太小会把关键内容（如 "your prize"）截掉；多字节字符会被切开。
- **混淆矩阵的行列约定**：本代码是"行 = 真实、列 = 预测"，与 sklearn 一致，但别和"行 = 预测"的写法混用。

---

## 9. 测试在验证什么

`tests/test_main.py`（`unittest` 风格，pytest 可收集）共 16 个测试：

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TokenizerTests` | `test_pads_to_max_len` | 短文本补齐到 `max_len`，mask 前 1 后 0，pad id 为 256 |
| | `test_truncates_long_input` | 长文本截断到 `max_len`，mask 全 1 |
| | `test_decode_skips_pad` | 解码时丢弃 PAD |
| `DatasetTests` | `test_make_dataset_balanced` | 每类数量正确 |
| | `test_stratified_split_preserves_balance` | 200 条 20% 测试集中两类各 20 条 |
| `MetricsTests` | `test_perfect_classifier` / `test_all_false_positive` / `test_f1_is_harmonic_mean` | 指标公式与分母为 0 的边界 |
| `FreezeTests` | `test_freeze_zeros_grad_flags_on_body_only` | 冻结后 body 全部不可训、head 仍可训、可训练参数减少 |
| | `test_unfreeze_restores` | 解冻后全部可训 |
| `PoolingTests` | `test_mask_excludes_pads_from_pool` | pad 位置不进入平均（`[1.5, 0.0]`） |
| | `test_empty_mask_does_not_divide_by_zero` | 全 pad 不产生 NaN |
| `ForwardTests` | `test_forward_shape_is_batch_by_num_classes` | 输出形状 `(B, 2)` |
| | `test_pad_tokens_do_not_change_pooled_output` | 只改 pad 位置的 token id，输出完全不变——同时验证了注意力 mask 与 pooling mask |
| `TrainingTests` | `test_head_only_reduces_loss` | head-only 训练 loss 下降，`TrainReport.trainable` 与实际一致 |
| `EvaluateTests` | `test_evaluate_on_trained_model_is_above_random` | 小配置下 F1 > 0.5，四格计数之和等于测试集大小 |

运行方式（在 `code/` 下）：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。实际结果：**16 passed**（约 2.5 秒）。

测试没有覆盖：因果性（也就验证不出 3.2 节的泄漏）、训练/测试去重、full FT 路径、`run_demo` 本身（虽然被导入但没有调用）。
