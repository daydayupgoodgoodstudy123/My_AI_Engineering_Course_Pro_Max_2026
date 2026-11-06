# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 41 节 完整 Evaluation 流程 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（约 30 秒，CPU 即可；会在 `code/` 目录写出 `report.json`）；测试：`python -m pytest -q tests` 或 `python -m unittest discover -s tests` ｜ **依赖**：`torch`、`numpy`（第三方）；`json`、`math`、`dataclasses`、`typing` 等（标准库）。无需 GPU、无需网络、无需 API key

---

## 1. 这份代码在考察什么

这份代码把"评估一个语言模型"做成一条完整的流水线：先在一个极小的语料上把 `TinyGPT` 训练几轮，然后跑四种性质完全不同的 eval，再把它们归一化、加权、汇总成一份报告。它考察的是：

1. **困惑度的正确计算**：next-token 错位（`logits[:, :-1]` 对 `ids[:, 1:]`）、padding 掩码只作用于**目标**位置、先累加 NLL 再除以 token 总数。
2. **字符串类指标的定义细节**：exact-match 的归一化规则、token F1 的多重集交集与空串边界。
3. **LLM-as-judge 的接口设计**：用一个确定性的 mock judge 代替真模型，但接口 `(instruction, prediction, reference) -> JudgeVerdict` 与真 judge 一致，可以直接替换。
4. **多指标聚合**：把量纲不同的指标映射到 [0, 1]，按可配置权重加权，权重随实际出现的 eval 重新归一化。
5. **报告工程**：结构化的 `EvalResult` / `FinalReport`、稳定键的 JSON、给人看的表格、逐样本抽查。

> 一句话：**评估不是"算一个数"，而是"为每个维度设计一个函数，再用一个聚合器和一份报告把它们并排摆出来"**。同时要看清这个 demo 在数据切分、归一化和停止条件上的简化——它们恰恰是生产 eval 最容易出错的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `InstructionTokenizer` | 类 | 字节级分词，特殊 token `INST=256`、`RESP=257`、`PAD=258`，`VOCAB=260` | 指令格式 |
| `CausalSelfAttention` / `Block` / `TinyGPT` | `nn.Module` | 2 层、64 维、4 头的 decoder-only Transformer（137,984 参数） | 被评测的模型 |
| `ExampleRecord` / `EvalResult` | dataclass | 逐样本记录与单个 eval 的结果容器 | eval 统一接口 |
| `normalise` / `strip_trailing_punctuation` / `normalise_for_em` / `tokenize_text` | 函数 | 字符串归一化与切词 | EM / F1 的预处理 |
| `LM_CORPUS` / `EM_PAIRS` / `F1_PAIRS` / `JUDGE_SET` | 模块级常量 | 四组各 20 条的固定数据（fixtures） | 评测数据 |
| `LMTextDataset` | `Dataset` | 把文本编码并 pad 到 `max_len`，返回 `(ids, attn)` | 批处理 |
| `perplexity_eval` | 函数 | 带掩码的 token 级 NLL 累加 → `exp` | 困惑度 |
| `generate_greedy` | 函数 | 贪心解码，遇特殊 token 或连续两个句末标点停止 | 生成 |
| `exact_match_score` / `token_f1_score` | 函数 | 单样本打分 | EM / F1 |
| `exact_match_eval` / `token_f1_eval` / `judge_eval` | 函数 | 遍历数据集 → 生成 → 打分 → `EvalResult` | 生成式 eval |
| `JudgeVerdict` / `mock_judge` | frozen dataclass / 函数 | 1–5 分 + 一句理由 | mock LLM-as-judge |
| `DEFAULT_WEIGHTS` / `normalise_metric` / `aggregate` / `FinalReport` | 常量 / 函数 / dataclass | 归一化、权重重归一、加权平均 | 聚合器 |
| `render_report` | 函数 | 打印表格 | 人读的报告 |
| `EvalConfig` / `train_small` / `run_demo` | dataclass / 函数 | 配置、短训练、端到端演示、写 JSON、返回退出码 | 演示入口 |

数据流：`run_demo` 固定种子 → 构造 `TinyGPT` → `train_small`（`LM_CORPUS` + `EM_PAIRS`，5 轮）→ 四个 eval 各自产出 `EvalResult` → `aggregate` 生成 `FinalReport` → `render_report` 打印 → 抽查前两条样本 → 写 `report.json` → `sys.exit(返回码)`。

---

## 3. 逐段精讲

### 3.1 `InstructionTokenizer`：字节 + 三个特殊 token

```python
class InstructionTokenizer:
    INST_ID = 256
    RESP_ID = 257
    PAD_ID = 258
    VOCAB = 260
    IGNORE_INDEX = -100

    def encode_pair(self, instruction: str, response: str, max_len: int) -> Tuple[List[int], int]:
        ids = [self.INST_ID]
        ids.extend(instruction.encode("utf-8", errors="ignore"))
        ids.append(self.RESP_ID)
        resp_start = len(ids)
        ids.extend(response.encode("utf-8", errors="ignore"))
        ...
```

- 0–255 是原始字节，256/257/258 是特殊 token，259 空闲（`VOCAB = 260`）。
- 指令样本格式：`[INST] 指令字节 [RESP] 答案字节`；`encode_prefix` 只编码到 `[RESP]` 为止，作为生成的起点；`encode_text` 用于纯语言建模语料，不加任何特殊 token。
- `decode_response` 用生成器表达式 `bytes(i for i in ids if i < 256)` 丢掉特殊 token，再以 `errors="replace"` 解码（不合法的 UTF-8 显示成 `�`）。
- ⚠️ `resp_start` 和 `IGNORE_INDEX = -100` 都**没有被用到**：训练时对整条序列（包括指令部分）算 loss，没有做 SFT 常见的"只对答案算 loss"。
- ⚠️ 没有 EOS token。答案后面什么也没有，模型从未学过"什么时候停"——这直接影响 3.6 节的停止行为。

### 3.2 `TinyGPT`：与第 38–40 课相同的小模型

```python
    def forward(self, x: torch.Tensor, key_pad_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        B, T, D = x.shape
        qkv = self.qkv(x).view(B, T, 3, self.heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        causal = self.causal_mask[:T, :T].view(1, 1, T, T)
        att = att.masked_fill(~causal, float("-inf"))
        if key_pad_mask is not None:
            km = key_pad_mask.view(B, 1, 1, T).to(torch.bool)
            att = att.masked_fill(~km, float("-inf"))
        weights = F.softmax(att, dim=-1)
        weights = torch.nan_to_num(weights, nan=0.0)
```

形状追踪（默认配置 `hidden=64, heads=4`）：

| 步骤 | 形状 |
|------|------|
| `self.qkv(x)` | `(B, T, 192)` |
| `.view(B, T, 3, 4, 16)` | 拆出 Q/K/V 三份、4 个头、每头 16 维 |
| `.permute(2, 0, 3, 1, 4)` | `(3, B, 4, T, 16)`，`qkv[0]` 即 `q` |
| `q @ k.transpose(-2, -1)` | `(B, 4, T, T)` |
| `causal_mask[:T, :T].view(1,1,T,T)` | 广播到每个 batch、每个头 |
| `key_pad_mask.view(B,1,1,T)` | 屏蔽"作为 key 的 pad 位置"，广播到每个 query |
| `(weights @ v).transpose(1,2).contiguous().view(B,T,D)` | 合头回 `(B, T, 64)` |

- 因果掩码是 `torch.tril` 的布尔下三角，用 `register_buffer(..., persistent=False)` 注册：跟随 `.to(device)` 移动，但不写进 `state_dict`。
- 掩码用 `-inf`，再用 `torch.nan_to_num(weights, nan=0.0)` 兜底：若某一行全被屏蔽，softmax 会得到 `NaN`，这里把它变成 0。在本代码中，因果掩码保证每个 query 至少能看到位置 0，而位置 0 永远是真实 token，所以实际上不会出现全屏蔽行。
- `Block` 是 pre-norm：`x + attn(ln1(x))`，`x + fc2(gelu(fc1(ln2(x))))`；FFN 是 4 倍扩展、GELU 激活。
- `TinyGPT` 的输出头 `self.head` 是独立的 `nn.Linear`（**没有** weight tying）。参数量手算：token 嵌入 `260×64 = 16,640`，位置嵌入 `80×64 = 5,120`，每个 block `49,728`（LN 128 + qkv 12,288 + out 4,096 + LN 128 + fc1 16,640 + fc2 16,448），两个 block `99,456`，`ln_f` 128，head `16,640`，合计 **137,984**（已用 `numel()` 验证）。

### 3.3 结果容器：`ExampleRecord` 与 `EvalResult`

```python
@dataclass
class EvalResult:
    name: str
    metric: float
    n_examples: int
    records: List[ExampleRecord] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)
```

- 这是讲义里"Each eval is a function from `(model, dataset) -> EvalResult`"的具体落地。`name` 同时是聚合时查权重、选归一化规则的键。
- 可变默认值必须用 `field(default_factory=list)`：写成 `records: List = []` 会让所有实例共享同一个列表，dataclass 会直接报错阻止你这么写。
- `to_dict` 用 `asdict(r)` 把嵌套 dataclass 递归转成 dict，便于 `json.dump`。
- ⚠️ 讲义说 `perplexity_eval` 返回"per-token loss histogram"，代码的 `extras` 里只有 `total_tokens` 和 `mean_nll`，没有直方图。

### 3.4 字符串归一化

```python
_TERMINAL_PUNCT = ".!?"

def normalise(text: str) -> str:
    s = text.lower().strip()
    while "  " in s:
        s = s.replace("  ", " ")
    return s

def strip_trailing_punctuation(text: str) -> str:
    s = text
    while s and s[-1] in _TERMINAL_PUNCT:
        s = s[:-1]
    return s

def normalise_for_em(text: str) -> str:
    return strip_trailing_punctuation(normalise(text))

def tokenize_text(text: str) -> List[str]:
    return [t for t in normalise(text).split() if t]
```

- `normalise`：小写、去首尾空白、反复把"两个空格"替换成一个，直到没有连续空格。
- `strip_trailing_punctuation` 用 `while` 去掉**所有**结尾的 `.!?`，所以 `"Paris?!"`、`"paris..."` 都变成 `"paris"`。
- EM 用 `normalise_for_em`（去结尾标点）；F1 用 `tokenize_text`（**不**去标点）。
- ⚠️ 与讲义的出入：
  - 讲义说"Collapse internal whitespace runs"，但 `normalise` 只折叠**空格**，`\t`、`\n` 原样保留。实测 `exact_match_score("carbon\ndioxide", "carbon dioxide") == 0`。用 `" ".join(s.split())` 可以一并处理所有空白。
  - 讲义说"Drop trailing terminal punctuation **if both sides differ only by punctuation**"，代码是**无条件**去掉。
  - 讲义说 token F1 "matches the SQuAD evaluation reference"，但 SQuAD 的 `normalize_answer` 还会去掉**所有**标点和冠词 `a/an/the`。本实现中 `"paris."` 与 `"paris"` 是两个不同的词元（见测验 Q11）。
- 边界：`normalise_for_em("...") == ""`，所以 `exact_match_score("?", "")` 会返回 1。

### 3.5 Fixtures 与 `LMTextDataset`

- 四组数据各 20 条，全部硬编码为模块常量，保证确定性：`LM_CORPUS` 是英文谚语式句子（最长 70 字节），`EM_PAIRS` 是首都/算术/定义/Python 短答案，`F1_PAIRS` 是"Summarise: ..."与改写后的参考答案，`JUDGE_SET` 是完整句子形式的参考答案。

```python
    def __getitem__(self, idx: int):
        ids = self.tok.encode_text(self.texts[idx], self.max_len)
        attn = [1] * len(ids)
        pad = self.max_len - len(ids)
        ids = ids + [InstructionTokenizer.PAD_ID] * pad
        attn = attn + [0] * pad
        return torch.tensor(ids, dtype=torch.long), torch.tensor(attn, dtype=torch.long)
```

- 每条文本右侧 pad 到 `max_len = 80`，`attn` 中真实 token 为 1、pad 为 0。`DataLoader` 自动把多个样本堆叠成 `(B, 80)`。

### 3.6 `perplexity_eval`：本节最核心的函数

```python
    for ids, attn in dl:
        logits = model(ids, key_pad_mask=attn)
        pred = logits[:, :-1, :].contiguous()
        target = ids[:, 1:].contiguous()
        target_mask = attn[:, 1:].contiguous()  # exclude pad targets
        loss_per_pos = F.cross_entropy(
            pred.view(-1, pred.size(-1)),
            target.view(-1),
            reduction="none",
        ).view(target.shape)
        loss_per_pos = loss_per_pos * target_mask
        per_seq_sum = loss_per_pos.sum(dim=-1)
        per_seq_tok = target_mask.sum(dim=-1).clamp(min=1.0)
        per_example_nll.extend((per_seq_sum / per_seq_tok).tolist())
        total_nll += float(loss_per_pos.sum().item())
        total_tokens += int(target_mask.sum().item())
```

逐行看三个"陷阱"是怎么避开的：

1. **错位**：`logits` 形状 `(B, 80, 260)`；位置 `i` 的输出预测位置 `i+1` 的 token，所以取 `logits[:, :-1]`（`(B, 79, 260)`）对 `ids[:, 1:]`（`(B, 79)`）。
2. **掩码对齐目标**：`target_mask = attn[:, 1:]`，与 `target` 同形状。若误用 `attn[:, :-1]`，"最后一个真实 token 预测第一个 pad"的位置会被计入。
3. **先求和再相除**：`reduction="none"` 拿到每个位置的 NLL，乘掩码清零 pad 位置，累加到 `total_nll`；`total_tokens` 只数掩码为 1 的目标。循环结束后才 `exp(total_nll / total_tokens)`。

- `F.cross_entropy` 要求 logits 是二维 `(N, C)`，所以先 `view(-1, 260)` 展平，算完再 `view(target.shape)` 还原成 `(B, 79)`。`.contiguous()` 是因为切片后的张量可能不连续，`view` 需要连续内存。
- `per_example_nll` 是每条序列自己的平均 NLL，只用于逐样本记录（`score = exp(mean_nll)`，mean_nll ≥ 50 时记 `inf` 防止溢出）。
- 首 token 无法被预测（没有 BOS），所以 20 条语料共 1,149 字节，实际计分 **1,129** 个位置（与输出 `total_tokens: 1129` 一致）。
- `@torch.no_grad()` 装饰器关闭梯度追踪，省显存、提速；`model.eval()` 切换到评估模式（本模型没有 dropout，影响不大，但这是好习惯）。
- ⚠️ 本函数用 `LM_CORPUS` 评测，而 `LM_CORPUS` 也是训练数据，所以这不是真正的 held-out 困惑度（见 3.10 与测验 Q10）。

### 3.7 `generate_greedy`：贪心解码与停止条件

```python
    ids = tok.encode_prefix(instruction, max_len=model.max_len)
    sentence_ends = {ord("."), ord("!"), ord("?")}
    out_chars: List[int] = []
    for _ in range(max_new_tokens):
        if len(ids) >= model.max_len:
            break
        x = torch.tensor([ids], dtype=torch.long)
        attn = torch.ones_like(x)
        logits = model(x, key_pad_mask=attn)
        next_id = int(logits[0, -1, :].argmax().item())
        if next_id == tok.PAD_ID or next_id == tok.INST_ID or next_id == tok.RESP_ID:
            break
        ids.append(next_id)
        out_chars.append(next_id)
        if (
            len(out_chars) >= 2
            and out_chars[-1] in sentence_ends
            and out_chars[-2] in sentence_ends
        ):
            break
```

- 每步都对整个前缀做一次完整前向，只取最后一个位置的 logits 做 `argmax`。没有 KV cache，所以 60 个样本的生成占了 demo 的大部分时间。
- 四种停止条件：上下文用满、生成特殊 token、**连续两个**句末标点、跑满 48 步。
- ⚠️ 实测发现：大量输出在一个句号后就停了，例如 `Compute 2 + 3.` → `"5."`。调试表明停止原因是模型在 `.` 之后预测了 **`RESP_ID = 257`**。原因：训练数据里所有指令都以 `.` 或 `?` 结尾、紧接着 `[RESP]`，模型学会了"句末标点之后是 RESP"。这是一个**偶然生效**的停止信号，并不是设计出来的 EOS。
- `ord(".")` 得到字符的码点 46，与字节 ID 一致（ASCII 范围内）。

### 3.8 EM、token F1 与三个生成式 eval

```python
def token_f1_score(pred: str, ref: str) -> float:
    p_tokens = tokenize_text(pred)
    r_tokens = tokenize_text(ref)
    if not p_tokens and not r_tokens:
        return 1.0
    if not p_tokens or not r_tokens:
        return 0.0
    p_counts: Dict[str, int] = {}
    for tok in p_tokens:
        p_counts[tok] = p_counts.get(tok, 0) + 1
    ...
    intersection = 0
    for tok, n in p_counts.items():
        intersection += min(n, r_counts.get(tok, 0))
```

- **多重集交集**：每个词取两边计数的较小值。例如 pred `"the the the"`、ref `"the cat sat"`，交集只算 1 个 `the`，`P = R = 1/3`，F1 = 0.333（已运行验证）。如果用 `set` 求交集就会错。
- 空串约定：两边都空 → 1.0（"空对空"视为匹配），只有一边空 → 0.0。与讲义一致。
- 用 `dict.get(k, 0) + 1` 手写计数，等价于 `collections.Counter`；`Counter(p) & Counter(r)` 就是多重集交集。
- 注意循环变量名 `tok` 与外层惯用的 tokenizer 变量同名，在这个函数里只是字符串，不影响逻辑，但读代码时容易混淆。
- `exact_match_eval` / `token_f1_eval` / `judge_eval` 结构完全相同：遍历 `(inst, ref)` → `generate_greedy` → 打分 → 累加 → `ExampleRecord`。`metric = total / max(len(pairs), 1)` 中的 `max(..., 1)` 防止空数据集除以零。
- 三个 eval 各自重新生成一遍：同一模型的生成结果不会在 eval 之间共享（`JUDGE_SET` 与 `EM_PAIRS` 中的 `Define variable.` 等指令会被重复生成）。

### 3.9 mock judge

```python
@dataclass(frozen=True)
class JudgeVerdict:
    score: int
    rationale: str

def mock_judge(instruction: str, prediction: str, reference: str) -> JudgeVerdict:
    norm_pred = normalise_for_em(prediction)
    norm_ref = normalise_for_em(reference)
    if norm_pred == norm_ref:
        return JudgeVerdict(score=5, rationale="exact match after normalisation")
    f1 = token_f1_score(prediction, reference)
    if f1 >= 0.8:
        return JudgeVerdict(score=4, rationale=f"high token overlap (F1={f1:.2f})")
    ...
```

- 规则与讲义完全一致：EM → 5；F1 ≥ 0.8 → 4；[0.5, 0.8) → 3；[0.2, 0.5) → 2；否则 1。用一连串 `if ... return` 实现区间判断，依赖"前面的分支已经排除了更高区间"。
- `frozen=True` 让 verdict 不可修改（赋值会抛 `FrozenInstanceError`），符合"判决结果是值"的语义。
- `judge_eval(..., judge_fn=mock_judge)`：judge 作为**参数注入**。换成真实模型时只要写一个同签名函数传进去，pipeline 其余部分不变——这就是讲义说的"Swap in a real model later by changing one function"。
- `instruction` 参数在 mock judge 里没有用到，但保留在签名里，因为真 judge 需要看到问题才能评判。
- ⚠️ 局限：mock judge 只看词重叠。实测 `mock_judge("...", "Paris", "the capital of france is paris.")` 得 **1 分**（`"paris."` 带句点，F1 = 0），一个正确的简短答案被判为最差。

### 3.10 聚合器

```python
def normalise_metric(name: str, value: float) -> float:
    if name == "perplexity":
        if value <= 0 or math.isinf(value) or math.isnan(value):
            return 0.0
        return 1.0 / (1.0 + math.log(max(value, 1.0)))
    if name == "exact_match":
        return max(0.0, min(1.0, float(value)))
    ...
    if name == "judge":
        return max(0.0, min(1.0, float(value) / 5.0))
    raise ValueError(f"unknown metric name: {name}")

def aggregate(results, weights=None) -> FinalReport:
    weights = dict(weights or DEFAULT_WEIGHTS)
    total_w = sum(weights.get(r.name, 0.0) for r in results)
    if total_w <= 0:
        raise ValueError("no positive weights match the eval names")
    norm_weights = {r.name: weights.get(r.name, 0.0) / total_w for r in results}
    ...
    agg = sum(normalised[name] * norm_weights[name] for name in normalised)
```

- perplexity 的映射 `1/(1+ln ppl)`：ppl = 1 → 1，ppl = e → 0.5，ppl = 11.315 → 0.292，ppl = 260（均匀猜测）→ 0.152。`max(value, 1.0)` 防止 ppl < 1（理论上不会出现）时 `ln` 为负、结果大于 1。
- `max(0.0, min(1.0, x))` 是"截断到 [0, 1]"（clamp）的惯用写法。
- `dict(weights or DEFAULT_WEIGHTS)`：传入 `None` 或空字典时用默认值，并**复制**一份，避免修改调用者的字典。
- 权重只在**实际出现**的结果上重新归一化：只有 EM 和 F1 时，0.3 / 0.3 变为 0.5 / 0.5。
- 名字不在已知四类中时 `normalise_metric` 抛 `ValueError`（实测传 `"bleu"` 会报错），不会静默忽略——这是好的防御。
- ⚠️ 设计上的"地板"：
  - judge 最低 1 分，`÷5` 后最低 0.2，白送 `0.2 × 0.2 = 0.04`；
  - 随机模型的 ppl 是几百，归一化后仍有约 0.15。
  - 实测未训练模型的 aggregate = **0.0696**，训练后 = **0.149**。若改为 judge `(s−1)/4`、perplexity `max(0, 1 − ln ppl / ln V)`，两者分别为 0.0 和 0.164（测验 Q12）。
- ⚠️ 测试 `normalise_metric("judge", 0.0) == 0.0` 测的是一个 judge 永远不会给出的分数。

### 3.11 `render_report` 与 `run_demo`

```python
        if name == "perplexity":
            raw_repr = f"{raw:>9.3f}"
        else:
            raw_repr = f"{raw:>9.3f}"
```

- ⚠️ 两个分支完全相同，是一段无效的条件判断（原意可能是给 ppl 用不同格式）。
- `sorted(report.per_eval.keys())` 按字母序输出，所以表格顺序是 exact_match、judge、perplexity、token_f1，而不是 eval 的执行顺序。
- `log: Callable[[str], None] = print`：把输出函数作为参数，测试或日志系统可以传入别的函数捕获输出。

```python
def run_demo(cfg: Optional[EvalConfig] = None, write_json: bool = True) -> int:
    cfg = cfg or EvalConfig()
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    random.seed(cfg.seed)
    ...
    if write_json:
        here = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(here, "report.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2, default=str)
    ...
    if report.aggregate <= 0.0 or math.isnan(report.aggregate):
        print("ERROR: aggregate score is not positive", file=sys.stderr)
        return 1
    return 0
```

- 三个随机源（torch、numpy、random）都固定种子；两次运行输出完全一致（已验证）。
- `report.json` 写在 `main.py` 同目录（`.gitignore` 已忽略它）。`default=str` 让无法序列化的对象转成字符串；但 `float('inf')` 会被写成非标准 JSON 的 `Infinity`，严格的 JSON 解析器会拒绝。
- ⚠️ 返回 1 的条件 `aggregate <= 0` 实际上不可能成立（judge 地板至少贡献 0.04），所以"exits zero on success"的检查形同虚设。
- `train_small`：`LM_CORPUS` 20 条 + `EM_PAIRS` 20 条，batch size 1，Adam（lr = 3e-3），5 个 epoch，对整条序列算 loss。
- ⚠️ **训练集即评测集**：`LM_CORPUS` 与 `EM_PAIRS` 既用于训练又用于评测。用两句新句子测得的 ppl 是 26.60，而在训练语料上是 11.315。讲义中的"held-out"在代码里并不成立。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一个 eval 一个函数，统一返回 `EvalResult` | 每个 eval 可以独立开发、测试、替换 | 生产中会用注册表/插件机制（如 lm-evaluation-harness 的 task 配置） |
| judge 作为 `judge_fn` 参数注入 | 换真模型只改一个函数 | 真 judge 需要处理随机性、偏差、成本、解析失败 |
| 确定性 mock judge（基于 EM + F1） | 离线、可复现、可测试 | 只看词重叠，正确的短答案会被判低分；不能代表真实 judge |
| 困惑度"先求和再相除" + 目标掩码 | 符合教科书定义，避免长度偏差与 pad 污染 | 跨 tokenizer 比较应改用 bits-per-byte |
| 归一化只折叠空格、不去标点 | 实现简单 | 与讲义所说的"SQuAD 参考"不一致；生产用 SQuAD 的 `normalize_answer` 或更完整的规则，并对规则做版本化 |
| `1/(1+ln ppl)` 与 judge `÷5` | 简单、单调、落在 [0, 1] | 存在"地板"，随机模型也有约 0.07 分；可改为相对均匀基线归一化、judge `(s−1)/4` |
| 权重随出现的 eval 重新归一化 | 允许只跑部分 eval | 不同 eval 子集的 aggregate 不可直接比较，报告中应注明 |
| 训练数据与评测数据重叠 | demo 只需"让指标非平凡" | 指标偏乐观；生产必须严格切分并做去污染 |
| 每项只有 20 条 fixtures | 运行快 | EM 0.15 的 95% 置信区间约 ±0.16，无法区分小幅回归；生产需要数百到上千条 |
| 无 EOS、无 KV cache 的贪心生成 | 代码最短 | 停止行为依赖偶然学到的模式；生成慢；生产需要 EOS、KV cache、批量生成 |
| JSON + 表格双输出 | 机器读与人读兼顾 | 需要处理 `inf`/`nan` 的序列化，并记录模型/数据/规则版本 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值（存为字符串），可以在注解中引用尚未定义的类 |
| 类型注解 | `def encode_pair(self, instruction: str, ...) -> Tuple[List[int], int]` | 标注参数与返回值类型，运行时不强制检查，便于阅读与 IDE 提示 |
| `Optional` / `Callable` / `Sequence` | `key_pad_mask: Optional[torch.Tensor] = None`、`judge_fn: Callable[[str, str, str], JudgeVerdict]` | `Optional[X]` 即"X 或 None"；`Callable[[参数类型...], 返回类型]` 描述函数签名 |
| 类属性 | `INST_ID = 256`（写在 class 体内） | 所有实例共享，可用 `InstructionTokenizer.PAD_ID` 直接访问 |
| `@dataclass` | `class EvalResult:` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=...)` | `records: List[ExampleRecord] = field(default_factory=list)` | 每个实例得到独立的新列表，避免共享可变默认值 |
| `@dataclass(frozen=True)` | `JudgeVerdict`、`EvalConfig` | 实例不可修改，可哈希 |
| `asdict` | `[asdict(r) for r in self.records]` | 把 dataclass（含嵌套）递归转成 dict |
| 装饰器 | `@torch.no_grad()` | 在函数执行期间关闭梯度计算 |
| 生成器表达式 | `bytes(i for i in ids if i < 256)` | 不建中间列表，边产生边消费 |
| 列表推导式带条件 | `[t for t in normalise(text).split() if t]` | 过滤空字符串 |
| 字典推导式 | `{r.name: weights.get(r.name, 0.0) / total_w for r in results}` | 一行构造字典 |
| `sum(...)` + 生成器 | `sum(normalised[name] * norm_weights[name] for name in normalised)` | 加权求和 |
| `dict.get(k, 默认值)` | `p_counts.get(tok, 0) + 1` | 键不存在时返回默认值，常用于计数 |
| `while` 条件循环 | `while "  " in s:`、`while s and s[-1] in _TERMINAL_PUNCT:` | 条件为真时反复执行；`s and ...` 先判断非空，避免 `s[-1]` 越界 |
| 字符串切片 | `s[:-1]`、`rec.instruction[:35]` | 去掉最后一个字符；取前 35 个字符 |
| `or` 提供默认值 | `cfg = cfg or EvalConfig()`、`dict(weights or DEFAULT_WEIGHTS)` | 左侧为假值（None、空）时取右侧 |
| 默认参数是函数 | `log: Callable[[str], None] = print` | 函数是一等对象，可以当参数传递 |
| f-string 格式符 | `{raw:>9.3f}`、`{name:<12}`、`{res.name:>11s}`、`{f1:.2f}` | 右对齐宽 9 保留 3 位小数；左对齐宽 12；右对齐字符串 |
| `print(..., file=sys.stderr)` | 错误信息 | 输出到标准错误流 |
| `with open(...) as fh` | 写 `report.json` | 自动关闭文件 |
| `json.dump(..., indent=2, default=str)` | 写报告 | 缩进美化；`default` 处理无法序列化的对象 |
| `os.path` | `os.path.dirname(os.path.abspath(__file__))` | 得到当前脚本所在目录 |
| `raise ValueError(...)` | `normalise_metric` 未知名字 | 主动抛出异常 |
| `if __name__ == "__main__":` + `sys.exit(...)` | `sys.exit(run_demo())` | 只在直接运行时执行；把返回值作为进程退出码 |
| `nn.Module` / `nn.ModuleList` | `self.blocks = nn.ModuleList([...])` | 用 ModuleList 而不是普通 list，参数才会被注册、被优化器看到 |
| `register_buffer` | `self.register_buffer("causal_mask", mask, persistent=False)` | 非参数张量，随模型移动设备，`persistent=False` 不存入 state_dict |
| 张量变形 | `.view(...)`、`.permute(2, 0, 3, 1, 4)`、`.transpose(-2, -1)`、`.contiguous()` | 改变形状/维度顺序；`view` 需要连续内存 |
| 布尔掩码 | `att.masked_fill(~causal, float("-inf"))` | `~` 对布尔张量取反；把为 True 的位置填成指定值 |
| `.item()` / `.tolist()` | `float(loss.item())`、`(...).tolist()` | 张量转 Python 标量 / 列表 |
| `Dataset` / `DataLoader` | `LMTextDataset`、`DataLoader(ds, batch_size=8, shuffle=False)` | 实现 `__len__`、`__getitem__` 后即可批量迭代 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，CPU，约 31 秒，两次运行结果完全一致）：

```text
EVAL PIPELINE DEMO
fixtures: lm=20 em=20 f1=20 judge=20

[training] 5 epochs over the LM + EM combined corpus...
           final epoch loss = 2.1057          ← 5 轮平均 loss：3.977 → 3.088 → 2.712 → 2.387 → 2.106

[evaluating]
  perplexity   = 11.315                      ← exp(2.4261)，在训练语料上测得
  exact_match  = 0.150                       ← 20 题对 3 题
  token_f1     = 0.020                       ← 只有 2 条拿到 0.2
  judge (1-5)  = 1.000                       ← 全部 1 分

EVAL REPORT
  eval          raw        normalised   weight
  ------------  ---------  -----------  ------
  exact_match       0.150        0.150    0.30
  judge             1.000        0.200    0.20   ← 最低分也有 0.2 的"地板"
  perplexity       11.315        0.292    0.20   ← 1/(1+ln 11.315)
  token_f1          0.020        0.020    0.30
  ------------  ---------  -----------  ------
  AGGREGATE                            0.149

[per-task spot checks]
  exact_match  inst='What is the capital of France?' pred='pr it 5 4e ite cal ithe 3atithe ' score=0.00
  exact_match  inst='What is the capital of Japan?' pred='me is 3 ome ite 3e the it be 2.' score=0.00
     token_f1  inst='Summarise: the sun rises in the eas' pred='4eris be atere ble a' score=0.00
     token_f1  inst='Summarise: water boils at one hundr' pred='ate plite b' score=0.00
        judge  inst='Name the capital of France.' pred='ame athe 2e e ' score=1.00
        judge  inst='Name the capital of Japan.' pred='me ' score=1.00

wrote .../code/report.json
```

逐项解读：

- **perplexity 11.315**：`report.json` 中 `extras = {total_tokens: 1129, mean_nll: 2.4261}`，`exp(2.4261) = 11.315`。逐条 ppl 在 7.42（`to be or not to be...`）到 15.79（`an apple a day...`）之间。逐条 ppl 的算术平均是 11.416，高于按 token 计算的 11.315——这就是 Q1 讲的平均方式差异。对照：未训练模型 ppl = 318.15；训练后在两句**新**句子上 ppl = 26.60，说明 11.315 带有明显的训练集乐观偏差。
- **exact_match 0.150**：命中的是 `Compute 2 + 3.` → `"5."`、`Compute 9 - 4.` → `"5."`、`Compute 20 / 5.` → `"4."`。其余算术题也输出 `"5."` 或 `"4."`，说明模型只是学会了"算术题答一个数字加句点"，命中是巧合。归一化去掉了句点，所以 `"5."` 等于 `"5"`。
- **token_f1 0.020**：只有两条拿到 0.2：`dna stores ...` 的预测 `'pit be the '` 与参考答案共享一个 `the`（`P = 1/3`、`R = 1/7`，F1 = 0.2）；`tectonic plates ...` 的预测 `'pete pl the '` 同理。`F1_PAIRS` 完全没参与训练，模型输出的基本是"像英文的乱码"。
- **judge 1.000**：20 条全部 1 分。`JUDGE_SET` 也没参与训练；即便答得对，带句点的参考答案也会让 F1 打折。
- **AGGREGATE 0.149** = `0.3·0.150 + 0.2·0.200 + 0.2·0.292 + 0.3·0.020`。其中 0.04 来自 judge 地板。未训练模型的 aggregate 是 0.0696。
- **为什么很多输出在一个句号后就停**：调试发现停止原因是模型预测了 `RESP_ID`（见 3.7）。
- 运行后会产生 `report.json`（本次约 23 KB）与 `__pycache__`；本讲解的结果是在临时副本中运行得到的。

---

## 7. 动手改一改

1. **修正归一化**：把 `normalise` 改成 `" ".join(text.lower().split())`，处理所有空白；再写一个 SQuAD 风格的 `squad_normalise`（去所有标点、去 `a/an/the`），让 `tokenize_text` 使用它，重新运行，比较 judge 分数的变化（参考测验 Q11）。
2. **真正的 held-out**：把 `LM_CORPUS`、`EM_PAIRS` 按 75/25 用固定种子切分，给 `train_small` 增加数据参数，只用训练部分训练、只用评测部分评测；比较 perplexity 与 EM 的变化（参考测验 Q10）。
3. **加入 EOS**：用空闲 ID 259 作为 `EOS_ID`，训练时在每个答案和每条语料末尾追加 EOS，`generate_greedy` 遇 EOS 停止；同时用 `resp_start` 和 `IGNORE_INDEX` 实现"只对答案算 loss"，把 `train_epochs` 调到 30，观察 EM 是否提升。
4. **去掉评分地板**：judge 改为 `(score − 1) / 4`，perplexity 改为 `max(0, 1 − ln(ppl)/ln(V))`，验证未训练模型 aggregate ≈ 0（参考测验 Q12）；顺便删掉 `render_report` 中的重复分支。
5. **讲义延伸目标 1——校准 eval**：在 EM 集上记录生成第一个 token 时的最大 softmax 概率作为置信度，按 [0, 0.2)、[0.2, 0.4)… 分桶，报告每桶的实际准确率与 ECE（期望校准误差），作为第五个 `EvalResult` 加入 `aggregate`（需要在 `normalise_metric` 中加一条规则）。
6. **讲义延伸目标 3——真实 judge**：写一个 `http_judge(instruction, prediction, reference) -> JudgeVerdict`，调用任意 LLM API，要求返回 JSON `{score, rationale}`，解析失败时重试；加缓存；传入 `judge_eval(..., judge_fn=http_judge)`。对同一批样本与 mock judge 的分数计算 Spearman 相关。

---

## 8. 常见坑

- **掩码对齐输入而不是目标**：`attn[:, :-1]` 与 `attn[:, 1:]` 只差一位，代码都能跑，数字却不同。
- **平均每批 ppl**：不同 batch 长度不同时结果偏差；`exp` 的凸性让它系统性偏高。
- **以为 `cross_entropy` 会自动忽略 PAD**：它只忽略 `ignore_index`（默认 -100），不认识 `PAD_ID = 258`。
- **在训练集上报告"held-out"指标**：本 demo 正是如此，ppl 与 EM 都偏乐观。
- **用 `set` 求 F1 交集**：丢掉了重复词的计数，`"the the the"` vs `"the cat sat"` 会算错。
- **归一化规则悄悄改动**：去不去标点、去不去冠词会显著改变 F1 和 judge 分数；规则要版本化，否则历史分数不可比。
- **只看 aggregate**：一项上涨可能掩盖另一项崩溃；而且 aggregate 有地板，随机模型也不是 0。
- **样本太少**：每项 20 条时，EM 的 95% 置信区间约 ±0.16，单次的小幅变化没有统计意义。
- **把 `inf` 写进 JSON**：Python 默认写出 `Infinity`，下游严格解析器会报错。
- **测试用例注释与实际不符**：见第 9 节 `test_high_overlap_scores_four`，注释算出的 F1 是错的。

---

## 9. 测试在验证什么

测试文件 `tests/test_main.py`（`unittest` 风格，pytest 也能运行）。运行方式：

```bash
cd code
python -m pytest -q tests                     # 20 passed in 3.12s
python -m unittest discover -s tests          # Ran 20 tests in 0.257s, OK
```

测试开头 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 目录加入导入路径，这样在任意位置运行都能 `from main import ...`。辅助函数 `_build_model(cfg)` 固定种子后构造一个**未训练**的小模型（`hidden=32, heads=2, depth=1`）。

| 测试类 / 用例 | 验证的性质 |
|--------------|-----------|
| `NormaliseTests.test_em_strips_trailing_punctuation` | `"Paris."` 与 `"paris"` 归一化后都是 `"paris"` |
| `NormaliseTests.test_em_collapses_internal_whitespace` | `"  the   sky  "` → `"the sky"`（只测了空格，没有测 `\t`/`\n`） |
| `ExactMatchTests.test_match_after_normalisation` | 大小写、结尾标点（包括 `"Paris!"` vs `"paris."`）不影响 EM |
| `ExactMatchTests.test_no_match_on_different_content` | 内容不同时 EM = 0 |
| `TokenF1Tests.test_identical_strings_score_one` | 完全相同 → 1.0 |
| `TokenF1Tests.test_empty_both_score_one` | 两边都空 → 1.0（空匹配约定） |
| `TokenF1Tests.test_empty_one_side_scores_zero` | 只有一边空 → 0.0 |
| `TokenF1Tests.test_partial_overlap_is_between_zero_and_one` | 精确数值：`P = 2/3`、`R = 1/2` → F1 = 0.5714 |
| `JudgeTests.test_exact_match_scores_five` | 归一化后相等 → 5 分 |
| `JudgeTests.test_high_overlap_scores_four` | 断言分数在 (3, 4) 中 |
| `JudgeTests.test_zero_overlap_scores_one` | 无重叠 → 1 分 |
| `AggregateTests.test_normalise_perplexity_decreasing` | ppl 1 > 10 > 100 的归一化值严格递减 |
| `AggregateTests.test_normalise_judge_divides_by_five` | 5 → 1.0，2.5 → 0.5，0 → 0 |
| `AggregateTests.test_aggregate_uses_weights` | 全部满分时 aggregate = 1，权重和为 1 |
| `AggregateTests.test_aggregate_handles_subset_of_evals` | 只有两项时权重重新归一化，aggregate = 0.5 |
| `PerplexityEvalTests.test_perplexity_is_finite_on_short_corpus` | 未训练模型的 ppl 有限、非 NaN、为正（`max_len=32` 会截断较长句子） |
| `PerplexityEvalTests.test_perplexity_records_count_examples` | `n_examples` 与 `records` 数量与输入一致 |
| `GenerativeEvalTests.test_em_eval_returns_score_in_unit_interval` | EM ∈ [0, 1]，`n_examples` 正确 |
| `GenerativeEvalTests.test_f1_eval_runs_and_returns_in_unit_interval` | F1 ∈ [0, 1] |
| `GenerativeEvalTests.test_judge_eval_returns_in_one_to_five` | judge 均值 ∈ [1, 5] |

需要注意的地方：

- **`test_high_overlap_scores_four` 的注释算错了**。注释说两句共享 4 个词、F1 = 0.667 → 3 分；实际 `"the sky was very blue today"` 与 `"the sky was blue today bright"` 共享 `the, sky, was, blue, today` **5** 个词，`P = R = 5/6`，F1 = 0.833 → **4 分**（已运行验证）。断言写成 `assertIn(v.score, (3, 4))` 恰好掩盖了这个错误，这也让测试无法区分 3 分与 4 分两种实现。更好的写法是 `assertEqual(v.score, 4)`。
- `test_normalise_judge_divides_by_five` 测了 `judge = 0.0`，但 judge 实际最低是 1——这条测试没有覆盖到"地板"问题。
- 测试只验证"性质"（区间、单调性、空串约定），**没有**验证困惑度的掩码与错位是否正确。可以补一个测试：构造一条已知分布的序列（或把模型输出固定成均匀分布，此时 ppl 应恰好等于 `VOCAB = 260`），并检查加 pad 前后 ppl 不变。
- 生成式 eval 的测试在未训练模型上运行，只验证"能跑、范围对"，不验证打分是否与 rubric 一致。
