# 测验 · 通过监督式 Fine-Tuning 进行指令微调（Instruction Tuning by Supervised Fine-Tuning）

> **阶段 19 · 综合项目 · 第 39 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | SFT 解决的是"格式契约" | base model 会续写但不会"应答"；SFT 用成对的 (instruction, response) 继续做 next-token 训练，让模型学会"看到指令 → 输出回答" |
| 2 | 模板与特殊 token | 每个样本拼成 `[INST] 指令字节 [RESP] 回答字节 [PAD]*`；本节 `INST=256`、`RESP=257`、`PAD=258`，词表 260 |
| 3 | Loss mask | labels 是 input_ids 的副本，指令区（含 INST 与 RESP 本身）和 pad 区改成 `-100`；只有回答 token 计入 loss |
| 4 | `ignore_index=-100` | `F.cross_entropy` 对等于 `ignore_index` 的目标贡献 0 loss、0 梯度，`mean` 只在未被忽略的位置上平均；全部被忽略时结果为 NaN |
| 5 | 移位对齐 | `shifted_loss` 用 `logits[:, :-1]` 对 `labels[:, 1:]`：位置 i 预测 i+1；RESP 所在位置负责预测回答的第一个字节 |
| 6 | 动态 padding | `sft_collate` 把一个 batch 补齐到本 batch 最长的序列，同时返回 attention mask |
| 7 | 为什么必须 mask | 讲义：不 mask 会把容量浪费在复述指令上，且指令 token 稀释了回答 token 在梯度中的占比（本节训练集中回答 token 只占约 43%） |
| 8 | 生成与停止 | 输入 `[INST] 指令 [RESP]`，贪心逐 token 生成，遇到特殊 token、连续两个句末标点、`max_new_tokens` 或 `max_len` 时停止 |
| 9 | Exact-match | 归一化（小写、去首尾空白、合并连续空格）后逐字比较，每题 0 或 1，再取平均；严格、无歧义，但不奖励同义改写 |
| 10 | 结束符（EOS）是格式契约的一部分 | 本节代码没有 EOS：模型从未学过"回答到此结束"，所以即使训练集 loss 降到 0.0006，生成仍会在正确答案后继续输出，EM 几乎为 0 |

### 核心技能（能动手做到）

- [ ] 手写 `sft_collate`：给定两个不等长样本，写出 padding 后的 `input_ids`、`labels`、`attention_mask`
- [ ] 解释 `shifted_loss` 中"移位 + `ignore_index`"如何让 RESP 位置预测回答首字节、而最后一个指令字节不预测 RESP
- [ ] 为模板加入 EOS token 并修改生成的停止条件，验证 exact-match 从接近 0 显著上升
- [ ] 统计一个 SFT 数据集中指令 token 与回答 token 的比例，判断 mask 对梯度的影响
- [ ] 把单轮模板扩展为多轮 chat 模板，并写出"只训练 assistant 回合"的 labels
- [ ] 设计比 exact-match 更宽容的评估（前缀匹配、token F1、chrF），并解释各自偏差

---

## 二、基础自测（选择题）

**Q1.** 用 `encode_pair("ab", "cd", max_len=32)` 和 `encode_pair("a", "bcdefghij", max_len=32)` 组成一个 batch 调用 `sft_collate`。第 0 行的 `labels` 是：

- A. `[256, 97, 98, 257, 99, 100, 258, 258, 258, 258, 258, 258]`
- B. `[-100, -100, -100, 257, 99, 100, -100, -100, -100, -100, -100, -100]`
- C. `[-100, -100, -100, -100, 99, 100, -100, -100, -100, -100, -100, -100]`
- D. `[-100, 97, 98, -100, 99, 100, -100, -100, -100, -100, -100, -100]`

**Q2.** 承接 Q1，`shifted_loss` 把 `logits[:, :-1]` 与 `labels[:, 1:]` 对齐。回答的第一个字节 `99`（`'c'`）是由哪个输入位置的 logits 来预测的？

- A. RESP token（第 3 个位置，下标 3）
- B. 第一个回答字节自身（下标 4）
- C. INST token（下标 0）
- D. 最后一个指令字节 `'b'`（下标 2）

**Q3.** 关于 `F.cross_entropy(..., ignore_index=-100)`，下列说法正确的是：

- A. 等于 `-100` 的位置会被当作类别 0 计算 loss
- B. 被忽略的位置 loss 为 0，但 `mean` 仍按全部位置数做分母
- C. 只要 labels 中出现负数，PyTorch 都会自动忽略
- D. 被忽略的位置贡献 0 loss、0 梯度，`mean` 只在有效位置上平均；若一个 batch 的目标全部被忽略，结果为 NaN

**Q4.** 默认配置跑完 20 个 epoch，测试集 exact-match 始终是 0.000。额外实验：把训练延长到 100 个 epoch（lr 2e-3），训练 loss 降到 0.0006，但**训练集**的 EM 也只有 0.006。最根本的原因是：

- A. 学习率太低
- B. 模板里没有结束符：回答后面的位置都是 pad（label 为 -100），模型从未学过"何时停止"，生成会在正确答案后继续输出
- C. exact-match 的归一化太严格
- D. 测试集中出现了训练集没有的类别

**Q5.** 本节训练时把 `attn_mask` 作为 `key_pad_mask` 传入注意力。对于本节的**右侧 padding**，这个 key padding mask 对真实 token 位置的输出有什么影响？

- A. 没有影响：因果 mask 已经保证真实 token 看不到它右边的 pad，实测加不加 key mask，真实位置的 logits 差值为 0
- B. 影响很大：不加它，真实 token 会注意到 pad
- C. 它让 pad 位置的 loss 变成 0
- D. 它替代了 labels 中的 `-100`

**Q6.** `max_len = 96`。fixture 中最长的样本编码后有 108 个 token；测试集 40 条里有 3 条 summary 的回答在编码时被截断（例如保留 21 / 31 字节）。在不修改代码的前提下，测试集 exact-match 的理论上限是：

- A. 1.000
- B. 0.975
- C. 0.950
- D. 0.925

**Q7.** 统计本节训练集（160 条）：指令区（含 INST、RESP 两个特殊 token）共多少 token、回答区共多少 token？

- A. 指令 3,730，回答 4,882
- B. 指令 4,882，回答 3,730（回答约占 43%）
- C. 两者大致相等，各约 4,300
- D. 指令 1,600，回答 7,000

**Q8.** 根据 `normalise` 与 `exact_match` 的实现，下列哪一对会得到 **0**？

- A. `exact_match("Paris", "paris")`
- B. `exact_match("  the  Answer is Rome. ", "the answer is rome.")`
- C. `exact_match("Paris.", "Paris")`
- D. `exact_match("5 * 4 = 20", "5 * 4 = 20")`

---

## 三、动手 / 代码题

**Q9.** 给本节加上 EOS：

1. 词表是 260，已用 256–258，用 `EOS_ID = 259`。修改 `encode_pair`（回答后追加 EOS，并为它预留长度）和 `generate`（遇到 EOS 停止），说明 EOS 在 labels 中应该是 `-100` 还是保留。
2. 额外实验（同一种子，100 epoch，lr 2e-3）：不加 EOS 时训练集 EM 0.006、测试集 EM 0.000；加 EOS 后训练集 EM 0.95、测试集 EM 0.15。解释"训练集几乎全对、测试集只有 0.15"说明了什么。

**Q10.** 讲义说 collate 函数"Builds `labels` = `input_ids` shifted by one ... The mask is applied after the shift"，并声称"Watching exact-match go from 0.0 at epoch one to something like 0.85 at epoch fifteen"。

1. 对照代码，collate 里真的做了移位吗？移位在哪里？两种写法结果是否等价？
2. 本节默认配置下实测的 loss 与 EM 轨迹是什么？讲义的 0.85 为什么无法复现？
3. 讲义还说"The model is small enough (hidden 96, 2 blocks, max length 64)"、"trains on 200 instruction-response pairs"，与代码有哪些出入？

**Q11.** `run_demo` 的模块文档写"Exits 0 when the trained model beats the random baseline of 0.0 on the held-out set"，而结尾代码是：

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

1. 本次运行最终 EM = 0.000，进程退出码是多少？这与文档是否一致？
2. 如果把这个 demo 当作 CI 门禁，应当检查什么？请给出改进后的判断条件，并说明为什么"loss 下降"不足以说明 SFT 成功。

**Q12.** 完成讲义 stretch goal 4：写 `encode_chat(turns)`，turns 是 `[("user", "hi"), ("assistant", "yo"), ("user", "ok?"), ("assistant", "k")]` 这样的列表；用 `USER=256`、`ASSIST=257`、`EOS=259`，返回 `(ids, labels)`，labels 与 ids 位置对齐（沿用本节"labels 不移位，交给 `shifted_loss` 移位"的约定），只训练 assistant 回合的内容和 EOS。写出上述输入的输出。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 SFT？它和预训练在目标函数、数据、loss 计算上有什么异同？

**Q14.**（原理深挖）为什么 SFT 要对 prompt/指令部分做 loss mask？不 mask 会怎样？有没有"不 mask 反而更好"的情况？

**Q15.**（工程实践）SFT 训练出来的模型"答对了却停不下来"或者"训练时好好的、上线后格式乱掉"，你会从哪些方面排查？

**Q16.**（场景设计）要为一个客服场景做 SFT：你会如何准备数据、设计模板、划分训练/验证集、选择评估指标？

**Q17.**（追问型）SFT 之后为什么常常还要做 RLHF/DPO？SFT 有哪些固有局限（如 exposure bias、只学模仿）？

---

## 五、参考答案与解析

### Q1 — 答案：C

`encode_pair("ab", "cd")` 得到 `[256, 97, 98, 257, 99, 100]`，`resp_start = 4`。batch 最长为 `1 + 1 + 1 + 9 = 12`，第 0 行补 6 个 PAD（258）。labels 先复制 padded，再把 `i < 4`（INST、`a`、`b`、RESP）和 `i >= 6`（pad）改为 -100，得到 `[-100, -100, -100, -100, 99, 100, -100 × 6]`（已实际运行验证）。A 是 `input_ids`；B 保留了 RESP，但讲义明确要求"The RESP_ID boundary position itself replaced by -100"；D 反而训练了指令字节。

### Q2 — 答案：A

对齐后 `pred[i]` 对应 `labels[i+1]`。`labels[4] = 99` 对应 `pred[3]`，即 RESP 所在位置（下标 3）的输出。这正是 SFT 的含义：看到 `[INST] ab [RESP]` 之后输出回答的第一个字节。D 位置（下标 2）对应 `labels[3]`，而 `labels[3]` 是 -100——所以模型**不**被训练去预测 RESP 这个边界 token。B、C 不符合"位置 i 预测 i+1"的约定。

### Q3 — 答案：D

`ignore_index` 是 `F.cross_entropy` 的文档化参数，默认就是 -100。被忽略的位置既不贡献 loss 也不产生梯度；`reduction="mean"` 时分母是**有效目标个数**（所以 B 错）。全部被忽略时是 0/0 = NaN，测试 `test_ignore_index_zeros_loss_on_masked_positions` 就接受 NaN 这一结果。A 错；C 错：只有恰好等于 `ignore_index` 的值被忽略，其他负数会报越界错误。

### Q4 — 答案：B

`sft_collate` 把 `i >= seq_len` 的位置全设为 -100，回答最后一个字节之后的位置从没有被监督过；PAD 也从来不是训练目标，所以模型几乎不可能主动输出 PAD/INST/RESP 来停止。唯一的启发式停止条件"连续两个句末标点"在答案中几乎不会出现。于是生成会在答案后继续"续写"：实测 100 epoch 后 `"What is 5 * 4?"` 生成 `"5 * 4 = 20 4 5 = = 2 = a 20 = ..."`——前缀完全正确，但 EM 判 0。A 只解释了默认 20 epoch 时 loss 还在 1.99（确实欠训练），却解释不了"训练集 loss 0.0006 时 EM 仍为 0.006"；C 不是主因（前缀已对）；D 错，`split_dataset` 分层保证测试集覆盖全部 6 类。

### Q5 — 答案：A

右侧 padding 时，pad 都在真实 token 的右边，而因果 mask 本来就禁止位置 i 看 j > i 的位置，所以真实 token 永远看不到 pad。实测同一 batch 加/不加 `key_pad_mask`，第 0 行真实位置的 logits 最大差值为 0.0。key mask 只改变 pad 位置自身作为 query 时的输出，而这些位置的 label 都是 -100。它在**左侧 padding**（pad 在真实 token 之前）时才真正必要。C、D 混淆了"注意力 mask"和"loss mask"。

### Q6 — 答案：D

`generate` 在 `len(ids) >= max_len` 时停止，`encode_prefix` 的前缀长度是"指令 + 2"。对被截断的 3 条 summary（如 `"One-sentence summary of: plants make food ..."`，前缀 75，最多只能生成 21 字节，而参考答案有 31 字节），即使模型完美也拼不出完整答案。上限是 `37/40 = 0.925`。训练集里另有 3 条同样被截断，模型还会学到"被截断的回答"。修法：增大 `max_len`、或优先截断指令而保证回答完整（本节已截指令，但这几条指令本身就太长）。

### Q7 — 答案：B

实测：训练集 160 条，指令区 4,882 token（指令字节 + INST + RESP），回答区 3,730 token，回答约占 43.3%。这印证讲义的说法"instruction tokens outnumber response tokens in most batches"：不加 mask 时，超过一半的梯度信号花在预测用户本来就会提供的内容上。

### Q8 — 答案：C

`normalise` 只做 `lower()`、`strip()` 和合并连续空格，不去标点。所以 `"Paris."` 与 `"Paris"` 不相等（测试 `test_exact_match_is_strict` 正是此例）。A 大小写被归一化；B 首尾空白被去掉、`"the  Answer"` 中的双空格被合并、大小写统一，结果相等；D 完全相同。讲义说 EM 意味着"character for character"，严格来说是"归一化之后"逐字符。

### Q9 — 参考答案

1. 修改要点：

```python
EOS_ID = 259

def encode_pair(self, instruction, response, max_len):
    ids, resp_start = <原逻辑>(instruction, response, max_len - 1)   # 预留 1 个位置
    return ids + [EOS_ID], resp_start

# generate 中：
        if next_id in (tok.PAD_ID, tok.INST_ID, tok.RESP_ID, EOS_ID):
            break
```

   EOS 在 labels 中**必须保留**（不能设为 -100）：它位于 `resp_start` 之后，`sft_collate` 自然会把它当作回答的一部分；这样"最后一个回答字节"所在位置被训练去预测 EOS，模型才学会停止。这正是"格式契约"中缺失的一半——讲义只强调了 RESP 边界，没有结束边界。
2. 训练集 EM 0.95 说明格式（何时开始、何时结束）已经完全学会；测试集只有 0.15，说明这个 2 层、hidden 96、字节级的小模型主要是在**记忆**"指令句式 → 回答"的映射，换一种问法就容易出错。例如 `"Tell me the capital of Brazil."` 生成了 `"the answer is Ottawa."`——回答模板（由指令模板决定）对了，事实错了。注意测试集 40 条中有 32 条的参考回答原封不动地出现在训练集中（只是指令句式不同），这本是对模型最友好的情况，0.15 依然很低。这些数字来自单次种子实验，仅说明趋势。

### Q10 — 参考答案

1. collate **没有**移位：它产出与 `input_ids` 对齐的 labels（只做 mask），移位发生在 `shifted_loss` 中（`logits[:, :-1]` 对 `labels[:, 1:]`）。"先 mask 再移位"与"先移位再 mask"只要 mask 的是同一组**目标 token** 就完全等价；本节代码的写法更不容易出错，因为 mask 规则可以直接按 `input_ids` 的下标写（`i < resp_start`）。
2. 实测默认配置：`epoch 5: loss=3.2999 EM=0.000`、`epoch 10: 2.7440 / 0.000`、`epoch 15: 2.3709 / 0.000`、`epoch 20: 1.9946 / 0.000`，最终 `FINAL EXACT MATCH = 0.000`。原因有二：①20 个 epoch、lr 5e-4 远未收敛（字节级 loss 1.99 ≈ 每字节约 7 选 1 的不确定性，生成仍是乱码）；②没有 EOS（Q4、Q9），即便收敛也停不下来。讲义的 0.85 在当前代码下无法复现。
3. 出入：代码 `max_len = 96`（讲义 64；若真用 64，200 条中有 58 条会被截断）；训练只用 160 条（讲义开头说"trains on 200"，后文才说 160/40 划分）；讲义说 eval 用 "token-level F1 (lesson 41)" 作补充，代码没有。

### Q11 — 参考答案

1. 退出码是 **0**：判断条件只看 `losses[-1] < losses[0]`（实测 1.9946 < 首个 epoch 的 loss）。文档说的"beats the random baseline of 0.0"根本没有被检查——EM 0.000 并没有超过 0.000，却照样"成功"。
2. 改进：

```python
    ok_loss = len(report.losses) >= 2 and math.isfinite(report.losses[-1]) \
              and report.losses[-1] < report.losses[0]
    ok_em = report.final_em > initial_em          # 至少要超过未训练基线
    if not (ok_loss and ok_em):
        return 1
```

   更严格的门禁可以设绝对阈值（如训练集 EM ≥ 0.9 证明格式学会、测试集 EM ≥ 某个历史值防回退）。"loss 下降"不足以说明成功：本节就是反例——loss 一路下降，但模型连训练集都答不出来（停止条件缺失）；loss 衡量的是 teacher forcing 下单步预测的好坏，而用户看到的是**自回归生成**的结果，两者之间还隔着解码策略、停止条件、exposure bias。

### Q12 — 参考答案

```python
USER, ASSIST, EOS = 256, 257, 259

def encode_chat(turns):
    ids, labels = [], []
    for role, text in turns:
        b = list(text.encode("utf-8"))
        if role == "user":
            seg = [USER] + b
            ids += seg
            labels += [-100] * len(seg)
        else:
            seg = [ASSIST] + b + [EOS]
            ids += seg
            labels += [-100] + b + [EOS]     # 角色标记本身不训练，内容与 EOS 训练
    return ids, labels
```

实际运行输出：

```text
ids    = [256, 104, 105, 257, 121, 111, 259, 256, 111, 107, 63, 257, 107, 259]
labels = [-100, -100, -100, -100, 121, 111, 259, -100, -100, -100, -100, -100, 107, 259]
```

要点：所有 user 回合（以及每个 ASSIST 标记）都是 -100；**每一个** assistant 回合都参与训练，而不只是最后一个（这样一条多轮对话提供多个训练信号）；EOS 被训练，模型才知道每轮何时把话轮交还给用户。推理时以 `... [ASSIST]` 结尾作为前缀，遇到 EOS 停止。

### Q13 — 参考回答要点

- **定义**：在预训练模型上，用人工整理的 (指令, 回答) 对继续做 next-token prediction，使模型学会按指令应答（讲义："Supervised fine-tuning is the smallest change that fixes this"）。
- **相同点**：目标函数仍是交叉熵 next-token 预测，模型结构不变（保留 LM head，这一点与第 38 节换头不同）。
- **不同点**：
  - 数据：海量无结构文本 → 数量少得多、按模板组织的成对数据；
  - loss：预训练对所有 token 计算；SFT 只对回答 token 计算（`ignore_index=-100` mask）；
  - 特殊 token：引入边界 token（INST/RESP，或 chat 模板的角色标记）以及 EOS；
  - 超参：学习率更小、epoch 少，讲义："SFT is more sensitive to LR than pretraining"。
- 加分点：说明 mask 后 loss 的分母是"回答 token 数"，不同长度回答的样本在 batch 内按 token 加权；有的实现会改为按样本平均，避免长回答主导梯度。

### Q14 — 参考回答要点

- **为什么 mask**：指令是用户给定的输入，不需要模型生成；对它计算 loss 会①浪费容量复述输入；②稀释回答 token 的梯度占比（本节训练集回答 token 只占约 43%），使"你真正关心的部分"的有效学习率变低（讲义 "Why the mask matters"）。
- **不 mask 的后果**：模型同时学"像用户那样说话"，可能在回答中续写出新的问题或复述指令；本节加 EOS 后的单次对照实验（100 epoch）中，不 mask 时测试集 EM 0.05，mask 时 0.15（单种子，仅供参考）。
- **例外/争议**：指令很短、回答很长时，影响很小；数据非常少时，对指令也计算 loss 相当于额外的语言建模正则，有研究和实践报告过小幅收益——这类结论依赖数据，需要在自己的验证集上确认。
- **常见误区**：把 RESP/角色标记本身也纳入 loss（模型会被训练去"预测边界"）；忘了 EOS 应当被训练。

### Q15 — 参考回答要点

- **停不下来**：检查模板中是否有 EOS、EOS 的 label 是否被错误地设成 -100、tokenizer 在推理时是否会把 EOS 当普通文本切开；生成配置里是否设置了正确的 `eos_token_id` / stop 条件。本节就是"无 EOS"导致的典型案例。
- **训练/推理模板不一致**：推理时的 prompt 必须与训练模板逐 token 一致（本节 `encode_prefix` 刻意与 `encode_pair` 共用 `[INST] ... [RESP]`），多一个空格、换行或少一个角色标记都可能让格式崩坏。
- **截断**：`max_len` 太小导致回答在训练中被截断（本节 6 条），模型学到"不完整的回答"。
- **mask 错位**：用可视化把 labels 和 input_ids 对齐打印出来（本节 Q1 的方式），检查第一个被训练的位置是不是回答首 token。
- **padding 方向**：批量推理时常用左侧 padding，此时必须传 key padding mask，位置编码也要正确（本节右侧 padding 下 key mask 是冗余的）。
- **评估方法**：只看 teacher-forcing loss 不看生成结果；应定期在固定的 prompt 集上生成并打分。

### Q16 — 参考回答要点

- **数据**：从真实工单/对话中抽取高质量回答，清洗隐私信息；覆盖主要意图并控制长尾比例；加入"拒答/转人工"样本；同一问题多种问法（本节每个事实配 3–4 个指令模板就是这个思路）。
- **模板**：使用基座模型约定的 chat 模板（system / user / assistant + EOS），多轮对话只训练 assistant 回合（Q12）；system prompt 固定写入，推理时保持一致。
- **划分**：按对话/客户/时间分组划分，避免同一工单的不同轮次跨训练和验证；保留一个从未用于调参的测试集。
- **指标**：结构化字段（订单号、退款金额）用 exact-match；自由文本用 token F1 / chrF / 嵌入相似度，加上 LLM-as-judge 或人工评审（第 41 节）；同时监控安全指标（是否泄露信息、是否越权承诺）和格式合规率。
- **训练**：小学习率 + warmup + cosine（讲义 stretch goal 1），早停看验证集生成质量而非只看 loss；必要时用 LoRA 降低成本。
- 加分：上线后收集用户反馈和"被人工改写的回答"，作为下一轮 SFT 或 DPO 的数据。

### Q17 — 参考回答要点

- **SFT 学的是模仿**：最大化参考回答的似然，只告诉模型"这个回答好"，不告诉它"哪个更好、哪个不好"；对开放式任务存在多个合理回答，SFT 无法表达偏好。
- **Exposure bias**：训练时用 teacher forcing（总是以正确前缀为条件），推理时以自己生成的前缀为条件，一旦早期出错就会偏离训练分布并累积误差——本节"前缀对了但后面乱写"的现象与之相关。
- **数据上限**：模型最多学到标注数据的水平，标注成本高。
- **RLHF/DPO 的作用**：利用成对偏好数据（chosen vs rejected）直接优化"更受偏好"的方向，可以压低有害、冗长、谄媚等不良回答的概率；DPO 不需要单独训练奖励模型（第 40 节）。
- **为什么先 SFT**：偏好优化需要一个已经会按格式回答的起点（DPO 的参考模型通常就是 SFT 模型），否则采样出的回答质量太差、偏好信号噪声大。
- 加分点：SFT 后的模型也可以用拒绝采样（best-of-n + 打分）生成新数据再 SFT，作为 RLHF 的简化替代。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：`TinyGPT` 的 decoder-only 结构与因果 mask。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：next-token 训练循环；本节只是换了数据与 loss mask。
- [阶段 19 · 38 通过替换输出头进行分类器 Fine-Tuning](../../38-classifier-finetuning/docs/zh.md)：另一种微调方式（换头），对比本节"保留 LM head"。
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：SFT 的概念、数据集与模板。
- [阶段 10 · 01 Tokenizers](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md)：字节级 tokenizer 与特殊 token。

### 本节被哪些后续内容用到
- [阶段 19 · 40 从零实现直接偏好优化](../../40-dpo-from-scratch/docs/zh.md)：在 SFT 模型基础上做偏好优化，参考模型就是 SFT 模型的冻结副本。
- [阶段 19 · 41 完整 Evaluation 流程](../../41-eval-pipeline/docs/zh.md)：token F1、judge 模型等比 exact-match 更宽容的指标（讲义提到 "that pipeline is lesson 41"）。
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)：讲义 stretch goal 1 所需的学习率调度。
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)、[阶段 10 · 08 DPO：直接偏好优化](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：SFT 之后的对齐步骤。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：用参数高效方法做 SFT。
- [阶段 18 · 01 将指令遵循作为 Alignment 信号](../../../18-ethics-safety-alignment/01-instruction-following-alignment-signal/docs/zh.md)：指令遵循与对齐的关系。

### 延伸关键词
`SFT` · `instruction tuning` · `chat template` · `ignore_index=-100` · `loss masking` · `EOS token` · `dynamic padding` · `teacher forcing` · `exposure bias` · `exact-match` · `token F1` · `chrF` · `Alpaca` · `packing` · `left vs right padding`
