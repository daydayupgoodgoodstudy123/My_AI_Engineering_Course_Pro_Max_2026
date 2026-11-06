# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 39 节 通过监督式 Fine-Tuning 进行指令微调 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下，CPU 约 30 秒；只要训练 loss 下降就以退出码 0 结束）；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests` ｜ **依赖**：`torch`、`numpy`（第三方）；`math`、`random`、`sys`、`dataclasses`、`typing`（标准库）。不写文件，不需要网络。

---

## 1. 这份代码在考察什么

这份代码搭了一个最小的 Alpaca 风格 SFT 流程：

1. **格式契约**：每个样本拼成 `[INST] 指令 [RESP] 回答`，用三个保留 id（256/257/258）做边界和 padding。
2. **loss mask**：`sft_collate` 把指令区、边界 token 和 pad 的 label 设为 `-100`，`shifted_loss` 用 `ignore_index=-100` 只在回答 token 上计算交叉熵。
3. **移位对齐**：位置 i 的 logits 预测位置 i+1 的 label。
4. **带因果 mask 的小 GPT**：`TinyGPT`（2 层、hidden 96、4 头、max_len 96、约 28 万参数），保留 LM head（与第 38 节"换头"相对）。
5. **生成与评估**：贪心/温度采样生成、启发式停止、归一化 exact-match、按类别统计。

> 一句话：**SFT = 同样的 next-token 交叉熵 + 一个模板 + 一个只让回答计分的 mask**。但本节代码也很好地暴露了"格式契约"缺的另一半：**没有 EOS**。模型从未学过何时停止，默认配置下 EM 全程为 0.000，延长训练到训练 loss 0.0006 时训练集 EM 也只有 0.006；加上 EOS 后训练集 EM 立刻到 0.95。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `InstructionTokenizer` | 类 | 字节级编码；`encode_pair` 返回 `(ids, resp_start)`，`encode_prefix` 用于生成，`decode_response` 丢弃特殊 token | 模板 + 特殊 token |
| `CausalSelfAttention` | `nn.Module` | 融合 qkv、因果 mask（buffer）+ 可选 key padding mask | 因果注意力 |
| `Block` / `TinyGPT` | `nn.Module` | pre-norm block；token + 位置 embedding → blocks → `ln_f` → `head`（不 tie） | decoder-only LM |
| `CAPITALS` … `DEFINITIONS` / `_arithmetic_response` / `make_dataset` | 常量 / 函数 | 6 类任务 × 3–4 个指令模板 = 200 对 | 合成指令数据 |
| `split_dataset` | 函数 | 按类别分层 80/20（160/40） | 分层划分 |
| `SFTDataset` | `Dataset` | 返回未 padding 的 `(ids, resp_start)` | 数据集 |
| `sft_collate` | 函数 | 动态 padding；构造 `input_ids`、`labels`（-100 mask）、`attn_mask` | loss mask |
| `shifted_loss` | 函数 | `logits[:, :-1]` vs `labels[:, 1:]`，`ignore_index=-100` | 移位 + 忽略 |
| `SFTConfig` / `build_model` / `SFTReport` | dataclass / 函数 | 配置、建模、训练记录 | — |
| `train_sft` | 函数 | Adam 训练循环，每 `eval_every` 个 epoch 评估一次 EM | SFT 循环 |
| `generate` | 函数 | 从 `[INST] 指令 [RESP]` 开始贪心/采样生成，含停止规则 | 解码 |
| `normalise` / `exact_match` / `exact_match_set` / `per_category_em` | 函数 | 归一化比较与汇总 | Exact-match |
| `run_demo` | 函数 | 数据 → 基线 EM → 训练 → 分类别 EM → 样例 → 退出码 | 演示 |

数据流：`make_dataset` → `split_dataset` → `SFTDataset` + `DataLoader(collate_fn=sft_collate)` → `TinyGPT(input_ids, key_pad_mask)` → `shifted_loss` → Adam；评估时 `encode_prefix` → `generate` → `exact_match`。

---

## 3. 逐段精讲

### 3.1 `InstructionTokenizer`：模板就是三个特殊 id

```python
class InstructionTokenizer:
    INST_ID = 256
    RESP_ID = 257
    PAD_ID = 258
    VOCAB = 260
    IGNORE_INDEX = -100

    def encode_pair(self, instruction: str, response: str, max_len: int) -> Tuple[List[int], int]:
        if max_len < 3:
            raise ValueError(...)
        inst_bytes = list(instruction.encode("utf-8", errors="ignore"))
        resp_bytes = list(response.encode("utf-8", errors="ignore"))
        max_inst = max_len - 3
        inst_bytes = inst_bytes[:max_inst]
        ids = [self.INST_ID] + inst_bytes + [self.RESP_ID]
        resp_start = len(ids)
        ids.extend(resp_bytes[: max_len - len(ids)])
        return ids, resp_start
```

- 序列为 `[INST] 指令字节 [RESP] 回答字节`，`resp_start` 是回答第一个字节的下标（RESP 在 `resp_start - 1`）。
- 截断策略：先保证指令最多 `max_len - 3`，从而至少留 1 个回答字节——这样任何样本都至少有 1 个有效 label，不会出现"整行全是 -100"。
- **注意**：只保证"至少 1 个"，不保证"完整"：实测 200 条中有 6 条编码后超过 96（最长 108），都是 `"One-sentence summary of: ..."`，回答被截短（如 31 字节只留 21）。其中 3 条在测试集，导致测试 EM 的理论上限只有 37/40 = 0.925。
- **注意**：**没有 EOS**：回答后面直接是 pad。词表 260 还空着 259，可以作为 EOS（测验 Q9）。
- `encode_prefix` 生成 `[INST] 指令 [RESP]`，与训练时的前缀逐 token 一致——训练/推理模板一致是 SFT 的硬性要求。
- `decode_response` 只保留 `< 256` 的 id，非法 UTF-8 用 `�` 替换。

### 3.2 `CausalSelfAttention`：因果 mask + key padding mask

```python
        mask = torch.tril(torch.ones(max_len, max_len, dtype=torch.bool))
        self.register_buffer("causal_mask", mask, persistent=False)
    ...
        causal = self.causal_mask[:T, :T].view(1, 1, T, T)
        att = att.masked_fill(~causal, float("-inf"))
        if key_pad_mask is not None:
            km = key_pad_mask.view(B, 1, 1, T).to(torch.bool)
            att = att.masked_fill(~km, float("-inf"))
        weights = F.softmax(att, dim=-1)
        weights = torch.nan_to_num(weights, nan=0.0)
```

- `tril` 得到下三角为 True 的"允许"矩阵，`~causal` 取反后把上三角（未来）填 `-inf`。与第 38 节相比，这里是真正的因果模型，next-token 训练不会泄漏。
- key padding mask `(B, 1, 1, T)` 广播到每个头、每个 query 行，屏蔽 pad 作为 key。
- **注意**：对**右侧 padding** 来说它是冗余的：pad 都在真实 token 右边，因果 mask 已经挡住了。实测加/不加 key mask，真实位置的 logits 差值为 0.0。它只影响 pad 位置自己的输出（其 label 本来就是 -100）。左侧 padding 时它才必不可少。
- `nan_to_num`：理论上某一行全部被屏蔽时 softmax 得到 NaN；在因果 + 右 padding 下，位置 0 至少能看到自己，不会发生。

### 3.3 `Block` 与 `TinyGPT`

```python
    def forward(self, x, key_pad_mask=None):
        x = x + self.attn(self.ln1(x), key_pad_mask)
        h = self.ln2(x)
        h = self.fc2(F.gelu(self.fc1(h)))
        return x + h
```

- 标准 pre-norm block，MLP 直接写在 block 里（`fc1`/`fc2`）。
- `TinyGPT.head = nn.Linear(hidden, vocab, bias=False)`，没有与 embedding tie。参数量实测 282,240：token 260×96 = 24,960，位置 96×96 = 9,216，每 block 111,456（ln 384、qkv 27,648、out 9,216、fc1 37,248、fc2 36,960），×2 = 222,912，`ln_f` 192，head 24,960。
- 讲义说 SFT 是在"预训练 body"上做的，但本节 `build_model` 直接随机初始化——这里的"SFT"实际上是从零训练一个只见过 160 条指令数据的模型，这也是测试集泛化弱的重要原因。

### 3.4 合成数据与分层划分

```python
    cap_resp_templates = [
        "the capital of {country} is {city}.",
        "{city} is the capital of {country}.",
        "{city}.",
        "the answer is {city}.",
    ]
    for country, city in CAPITALS:
        for i, t in enumerate(cap_templates):
            pairs.append({"instruction": t.format(country=country),
                          "response": cap_resp_templates[i].format(country=country, city=city)})
```

- 6 类：capitals 40、arithmetic 30、lists 30、summaries 30、code 30、definitions 40，合计 200。
- capitals 的**回答句式由指令模板决定**（第 i 个指令模板对应第 i 个回答模板），其它类别同一事实的不同问法共用同一个回答。实测测试集 40 条中有 32 条的参考回答原封不动出现在训练集里（指令句式不同）——测试的是"换一种问法还能否答出"。
- `_arithmetic_response` 的除法用 `//`；fixture 中的除法都能整除（12/4、15/5、20/4），所以不会出错，但换数据就会给出错误的"正确答案"。
- `split_dataset` 按类别分层，`cut = max(1, int(n * 0.8))`；测试集各类别为 definitions 8、capitals 8、其余各 6，测试 `test_split_is_stratified` 检查每类都在测试集里出现。
- `make_dataset` 用独立的 `random.Random(seed)`，只用于打乱顺序。

### 3.5 `sft_collate`：动态 padding + loss mask

```python
    max_t = max(len(x[0]) for x in batch)
    for ids, resp_start in batch:
        seq_len = len(ids)
        pad = [pad_id] * (max_t - seq_len)
        padded = list(ids) + pad
        lbl: List[int] = list(padded)
        for i in range(len(lbl)):
            if i < resp_start:
                lbl[i] = ignore_index
            elif i >= seq_len:
                lbl[i] = ignore_index
        am = [1] * seq_len + [0] * (max_t - seq_len)
```

以 `("ab", "cd")` 与 `("a", "bcdefghij")` 组成的 batch 为例（实测）：

| 下标 | 0 | 1 | 2 | 3 | 4 | 5 | 6–11 |
|------|---|---|---|---|---|---|------|
| `input_ids` 第 0 行 | 256 (INST) | 97 `a` | 98 `b` | 257 (RESP) | 99 `c` | 100 `d` | 258 (PAD) |
| `labels` 第 0 行 | -100 | -100 | -100 | -100 | 99 | 100 | -100 |
| `attn_mask` 第 0 行 | 1 | 1 | 1 | 1 | 1 | 1 | 0 |

- **动态 padding**：只补到本 batch 最长序列（这里 12），而不是全局 `max_len`，节省计算。
- labels 与 `input_ids` **位置对齐**（没有移位），只是把不该训练的目标换成 -100；移位交给 `shifted_loss`。讲义说 collate "Builds labels = input_ids shifted by one ... The mask is applied after the shift"，与代码写法不同，但结果等价。
- `i < resp_start` 覆盖了 INST、全部指令字节和 RESP 本身：讲义要求 "you do not train the model to predict the boundary token"。
- 训练集统计（实测）：指令区 4,882 token、回答区 3,730 token，回答只占约 43%——这就是 mask 的意义所在。

### 3.6 `shifted_loss`：移位 + `ignore_index`

```python
def shifted_loss(logits, labels, ignore_index=InstructionTokenizer.IGNORE_INDEX):
    pred = logits[:, :-1, :].contiguous()
    target = labels[:, 1:].contiguous()
    return F.cross_entropy(
        pred.view(-1, pred.size(-1)),
        target.view(-1),
        ignore_index=ignore_index,
    )
```

- `pred[i]` 对应 `target[i] = labels[i+1]`。在上表中：下标 3（RESP）的输出被训练去预测 `labels[4] = 'c'`；下标 2（`'b'`）对应 `labels[3] = -100`，不训练"预测 RESP"；下标 5（`'d'`）对应 `labels[6] = -100`——**最后一个回答字节之后没有任何训练目标**，这就是"停不下来"的根源。
- `view(-1, V)` 把 `(B, T-1, V)` 展平成 `(B·(T-1), V)`；`contiguous()` 保证切片后的张量可以 `view`。
- `reduction` 默认 `mean`：分母是本 batch **有效目标 token 数**，所以长回答的样本在 batch 内权重更大。
- 全部目标都是 -100 时返回 NaN（实测 `F.cross_entropy(torch.zeros(1,5), torch.tensor([-100]))` 为 `nan`），测试 `test_ignore_index_zeros_loss_on_masked_positions` 接受这一行为。`encode_pair` 保证每个样本至少 1 个回答 token，所以训练中不会出现。

### 3.7 `train_sft`：标准循环 + 周期性评估

```python
    torch.manual_seed(cfg.seed)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    for ep in range(1, cfg.epochs + 1):
        model.train()
        for input_ids, labels, attn_mask in train_loader:
            logits = model(input_ids, key_pad_mask=attn_mask)
            loss = shifted_loss(logits, labels)
            opt.zero_grad()
            loss.backward()
            opt.step()
            ...
        if eval_pairs is not None and tok is not None and ep % eval_every == 0:
            em = exact_match_set(model, tok, eval_pairs, cfg.max_len)
            ...
```

- Adam、lr 5e-4、20 个 epoch、无调度器（讲义 stretch goal 1 建议加 warmup + cosine）。
- 每 5 个 epoch 对测试集做一次完整生成评估；`log` 参数可注入（测试里传 `lambda s: None` 静音）。
- **注意**：评估成本远高于训练：每条测试样本最多生成 64 个 token，每生成一个 token 都对整个前缀重新前向（无 KV cache）。
- `generate` 内部调用 `model.eval()`，评估完回到下一个 epoch 时循环开头再 `model.train()`——顺序是对的（本模型没有 dropout，影响不大）。

### 3.8 `generate`：贪心/采样 + 启发式停止

```python
    ids = tok.encode_prefix(instruction, max_len=max_len)
    sentence_ends = {ord("."), ord("!"), ord("?")}
    for _ in range(max_new_tokens):
        if len(ids) >= max_len:
            break
        ...
        if temperature <= 0.0:
            next_id = int(next_logits.argmax().item())
        else:
            probs = F.softmax(next_logits / temperature, dim=-1)
            next_id = int(torch.multinomial(probs, num_samples=1, generator=rng).item())
        if next_id == tok.PAD_ID:
            break
        if next_id == tok.INST_ID or next_id == tok.RESP_ID:
            break
        ids.append(next_id)
        out_chars.append(next_id)
        if len(out_chars) >= 2 and out_chars[-1] in sentence_ends and out_chars[-2] in sentence_ends:
            break
```

- `temperature <= 0` 走 `argmax`，避免了除以 0（对比阶段 10 · 04 的实现）；采样时用独立的 `torch.Generator`，结果可复现。
- 停止条件有四个：长度到 `max_len`、生成了 PAD/INST/RESP、连续两个句末标点、`max_new_tokens`。
- **注意**：前三类特殊 token 在训练中**从来不是目标**（INST/RESP 被 mask、PAD 被 mask），模型几乎不会生成它们；而回答里很少出现 `..`、`?!` 这类连续句末标点。所以实际上生成几乎总是跑满 64 个 token 或撞到 `max_len`。实测：延长训练到 100 epoch 后，`"What is 5 * 4?"` 生成 `"5 * 4 = 20 4 5 = = 2 = a 20 = Ot 4 2. ..."`——前缀正确，后面继续乱写。
- 讲义所说的"two consecutive sentence-ending bytes"作为停止规则本身就很难触发；正确做法是 EOS。

### 3.9 指标与 `run_demo`

```python
def normalise(text: str) -> str:
    s = text.lower().strip()
    while "  " in s:
        s = s.replace("  ", " ")
    return s
```

- 小写、去首尾空白、反复把双空格替换成单空格；**不去标点**，所以 `"Paris."` ≠ `"Paris"`。
- `per_category_em` 用 `setdefault` 按类别收集 0/1，再求平均。

```python
    if (
        len(report.losses) < 2
        or not math.isfinite(report.losses[-1])
        or report.losses[-1] >= report.losses[0]
    ):
        print("ERROR: training loss did not decrease over the run", file=sys.stderr)
        return 1
    return 0
```

- **注意**：退出码只看"loss 是否下降"。模块文档却写"Exits 0 when the trained model beats the random baseline of 0.0"——本次运行 EM 0.000 = 基线 0.000，仍然退出 0。
- `collate_fn=lambda b: sft_collate(b)`：等价于直接传 `sft_collate`；lambda 不能被 pickle，若设置 `num_workers > 0` 在某些平台会出错。
- `random.seed`、`np.random.seed` 是习惯性设置，本文件中的随机性都来自独立的 `random.Random` 或 torch。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 字节级 + 3 个特殊 id | 零依赖，模板一目了然 | 序列长；生产用基座模型自带的 tokenizer 与 chat 模板 |
| 不设 EOS | 讲义只强调起始边界 | 模型无法停止，EM 失效；生产模板一定有 EOS（或回合结束 token），且 EOS 参与 loss |
| labels 不移位、loss 里移位 | mask 规则按 input 下标写，最直观 | 需要记住"label 对齐 input" 的约定，与 HF 的惯例一致 |
| 指令 + RESP 都 mask | 只训练回答，边界不作为目标 | — |
| 动态 padding | 减少无效计算 | 长度差异大时仍有浪费；生产常用 packing（多样本拼一条）配合正确的 mask |
| key padding mask | 通用写法，兼容左 padding | 右 padding 下冗余 |
| 从随机初始化开始 "SFT" | 自包含 | 没有预训练知识，测试泛化弱；真实 SFT 一定从预训练 checkpoint 开始（第 37 节） |
| 启发式停止规则 | 不改训练目标也能停 | 几乎不触发；应换成 EOS |
| 无 KV cache 的生成 | 简单 | 评估很慢；生产推理必须有 KV cache |
| exact-match | 严格、无歧义 | 不奖励改写、不去标点；补充 token F1 / judge（第 41 节） |
| 退出码只看 loss | 保证"能跑通" | 掩盖了 EM = 0 的事实；CI 应检查 EM 相对基线的提升 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类常量 | `INST_ID = 256`、`InstructionTokenizer.IGNORE_INDEX` | 作为"命名常量"，可被默认参数引用 |
| 默认参数引用类常量 | `def sft_collate(batch, pad_id: int = InstructionTokenizer.PAD_ID, ...)` | 默认值在函数定义时求值 |
| `Optional[...]` / `Callable[[str], None]` | `key_pad_mask: Optional[torch.Tensor] = None`、`log: Callable[[str], None] = print` | 可为 None；接收一个字符串、无返回值的函数 |
| 函数作为参数 | `log=print`、测试中 `log=lambda s: None` | 依赖注入，便于静音或重定向日志 |
| `lambda` | `collate_fn=lambda b: sft_collate(b)` | 匿名函数 |
| `str.format` 关键字 | `t.format(country=country)`、`cap_resp_templates[i].format(country=..., city=...)` | 按名字填充模板 |
| `enumerate` | `for i, t in enumerate(cap_templates)` | 同时拿到下标与元素 |
| `", ".join(...)` | `", ".join(items) + "."` | 用分隔符拼接字符串列表 |
| f-string 格式符 | `{ep:>3d}`、`{avg:.4f}`、`{cat:>12s}` | 右对齐宽度 3 的整数、4 位小数、右对齐宽度 12 的字符串 |
| 字典推导式 | `{c: sum(vs) / max(len(vs), 1) for c, vs in by_cat.items()}` | 生成"类别 → 平均值"的字典 |
| 集合字面量 | `{ord("."), ord("!"), ord("?")}` | O(1) 的成员判断 |
| `ord` / `bytes(...)` | `ord(".")`、`bytes(i for i in ids if i < 256)` | 字符 ↔ 码值；整数序列 → 字节串 |
| `@dataclass` + `field(default_factory=list)` | `SFTReport` | 可变默认值用工厂 |
| `while` 循环替换 | `while "  " in s: s = s.replace("  ", " ")` | 反复合并直到没有双空格 |
| `@torch.no_grad()` | `generate`、`exact_match_set` | 推理不建计算图 |
| 布尔取反 `~` | `att.masked_fill(~causal, float("-inf"))` | 张量逐元素逻辑非 |
| `torch.Generator` | `rng = torch.Generator(); rng.manual_seed(seed)` | 独立随机数流，`multinomial(..., generator=rng)` |
| `math.isfinite` | `math.isfinite(report.losses[-1])` | 检查不是 NaN/inf |
| `sys.exit(run_demo())` | 文件末尾 | 返回值作为退出码 |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU；耗时约 31 秒，退出码 0）：

```text
INSTRUCTION TUNING (SFT) DEMO
train=160 test=40 max_len=96
categories: ['arithmetic', 'capitals', 'code', 'definitions', 'lists', 'summaries']

baseline (untrained) EM = 0.000

[training]
  epoch   5: loss=3.2999  EM=0.000
  epoch  10: loss=2.7440  EM=0.000
  epoch  15: loss=2.3709  EM=0.000
  epoch  20: loss=1.9946  EM=0.000

[per-category exact-match on held-out]
    arithmetic: 0.000
      ...（6 类全部 0.000）

[sample generations]
  [MISS ] inst: What is 5 * 4?
          gold: 5 * 4 = 20
          pred:  12 / = = 3 = 3 = 4 co in i of = o i o o i o in of o 2 o ct o a
  [MISS ] inst: Explain the term string.
          gold: a sequence of characters.
          pred: a berere calital al cthe itere itores of s bate ct o an in an s
  [MISS ] inst: Tell me the capital of Brazil.
          gold: the answer is Brasilia.
          pred: the cof al a ct cof ith ithores in an ate an in cof an we it in

FINAL EXACT MATCH = 0.000  (baseline was 0.000)
```

逐项解读：

- **loss 3.30 → 1.99**：仍在快速下降，远未收敛。`e^1.99 ≈ 7.3`，相当于每个字节还有约 7 个候选，生成自然是乱码。不过已经能看到"格式"的苗头：回答首词 `a`、`the` 与参考答案的首词一致——这些高频开头最先被学会（讲义 stretch goal 2 提到"early epochs are dominated by template tokens"）。
- **EM 全程 0.000**：讲义描述的"0.0 → 约 0.85"没有出现。
- **退出码 0**：因为只检查 loss 是否下降。

额外对照实验（同一种子，在副本中运行；单次实验，只说明趋势）：

| 配置 | 最终训练 loss | 训练集 EM | 测试集 EM | 测试集"前缀正确"比例 |
|------|-------------|----------|----------|------------------|
| 原代码，100 epoch，lr 2e-3 | 0.0006 | 0.006 | 0.000 | 0.125 |
| 加 EOS（259），100 epoch，lr 2e-3 | 0.0006 | 0.95 | 0.15 | 0.15 |
| 加 EOS、**不 mask 指令**，100 epoch，lr 2e-3 | 0.106（含指令 token） | 0.95 | 0.05 | 0.05 |
| 加 EOS，默认 20 epoch，lr 5e-4 | 1.92 | 0.000 | 0.000 | 0.000 |

- 第 1 行说明：loss 已经接近 0，模型把训练集背下来了，却因为停不下来几乎拿不到 EM；"前缀正确"（生成以参考答案开头）达到 12.5%。
- 第 2 行说明：EOS 是格式契约中不可缺少的一半，加上后训练集 EM 立刻到 0.95。测试集 0.15 说明这个从零训练、只见过 160 条数据的小模型主要在记忆，例如 `"Tell me the capital of Brazil."` 生成 `"the answer is Ottawa."`（句式对、事实错）。
- 第 3 行与讲义 "Why the mask matters" 的方向一致：不 mask 时测试 EM 更低（0.05 vs 0.15），生成中出现复述指令的倾向（`"What is 5 * 4?"` 生成 `"5 * 4?"`）。

测试运行：`python3 -m pytest -q tests` → `14 passed in 2.31s`。

---

## 7. 动手改一改

1. **加 EOS**（必做）：按测验 Q9 修改 `encode_pair` 与 `generate`，重跑 demo；再把 epoch 提到 100、lr 提到 2e-3，观察训练集 / 测试集 EM。
2. **修正门禁**：把 `run_demo` 的退出条件改为"loss 下降且 `final_em > initial_em`"（测验 Q11）。
3. **讲义 stretch goal 1**：加入线性 warmup + cosine 衰减，比较相同 epoch 数下的最终 loss 和 EM。
4. **讲义 stretch goal 2**：在 `shifted_loss` 中用 `reduction="none"` 拿到逐 token loss，分别统计"回答第 1 个 token"和"其余 token"的平均 loss 随 epoch 的变化。
5. **讲义 stretch goal 3**：实现前缀匹配率与 chrF / token F1，与 exact-match 一起报告；观察无 EOS 时这些指标与 EM 的差距。
6. **讲义 stretch goal 4**：实现多轮 chat 模板（测验 Q12），构造一个"追问"fixture，只训练 assistant 回合。

---

## 8. 常见坑

- **忘了 EOS 或把 EOS 的 label 设为 -100**：模型学不会停止，表现为"答对后继续乱写"。
- **把边界 token 也算进 loss**：模型被训练去"预测 RESP"，在指令中途就可能输出边界。
- **mask 错位一位**：labels 与 input 对齐还是已移位，全流程必须约定一致；用小例子打印对照表检查。
- **训练/推理模板不一致**：推理前缀少了 RESP 或多了空格，模型就看不到熟悉的边界。
- **只看 loss**：teacher forcing 下的 loss 很低，不代表自回归生成可用；定期做生成评估。
- **截断吃掉回答**：`max_len` 太小时回答被截短，模型学到不完整答案，评估也有无法达到的上限。
- **左 padding 不传 key mask**：本节右 padding 下 key mask 冗余，换成左 padding 时就会出错。
- **`ignore_index` 用了别的负数**：只有恰好等于 `ignore_index` 的值被忽略，其它负数会触发越界错误。

---

## 9. 测试在验证什么

`tests/test_main.py`（`unittest` 风格，pytest 可收集）共 14 个测试：

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TokenizerTests` | `test_encode_pair_places_resp_marker` | 首 token 为 INST，`resp_start - 1` 处为 RESP，回答字节从 `resp_start` 开始 |
| | `test_truncates_to_max_len` | 超长指令+回答被截到 `max_len` |
| | `test_decode_response_drops_specials` | 解码时丢掉特殊 token |
| `CollateTests` | `test_collate_pads_and_masks_instruction` | 指令区 label 为 -100，回答区 label 等于 input |
| | `test_collate_pads_labels_to_ignore_index` | pad 区 label 为 -100；attention mask 真实为 1、pad 为 0 |
| `DatasetTests` | `test_make_dataset_returns_200_pairs` | 200 对、6 个类别 |
| | `test_split_is_stratified` | 每个类别都出现在测试集 |
| `LossTests` | `test_ignore_index_zeros_loss_on_masked_positions` | 全部被忽略时不报错（返回 NaN） |
| | `test_loss_decreases_when_target_distribution_is_learnable` | 在 `[3, 5, 7]` 上放大 logits 后 loss 下降——间接验证了"位置 i 预测 labels[i+1]"的移位方向 |
| `MetricTests` | `test_normalise_collapses_whitespace_and_case` | 大小写与空白归一化 |
| | `test_exact_match_is_strict` | 大小写不敏感，但标点敏感 |
| `GenerateTests` | `test_generation_respects_max_new_tokens` | 生成长度不超过 `max_new_tokens` |
| | `test_temperature_zero_is_deterministic` | 贪心解码两次结果相同 |
| `TrainingTests` | `test_train_sft_returns_loss_history_per_epoch` | 每个 epoch 一条 loss；最后的 loss 不比第一个高出 1.0 以上（很宽松） |

运行方式（在 `code/` 下）：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。实际结果：**14 passed**（约 2.3 秒）。

测试没有覆盖：模型能否在训练后**停止生成**、训练后 EM 是否高于基线、截断是否吃掉回答——恰好是本节代码最大的问题所在。可以补一个"在 8 条样本上过拟合后训练集 EM 应为 1.0"的测试，它会立刻暴露缺少 EOS 的问题。
