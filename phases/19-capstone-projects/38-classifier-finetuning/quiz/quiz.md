# 测验 · 通过替换输出头进行分类器 Fine-Tuning（Classifier Fine-Tuning by Head Swap）

> **阶段 19 · 综合项目 · 第 38 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Head swap（换头） | 模型 = body `f_θ(tokens) → hidden` + head `g_φ(hidden) → logits`；保留 θ，把"投影到词表"的 LM head 换成"投影到 2 类"的线性层 |
| 2 | 两种训练方式 | head-only：body 全部 `requires_grad=False`，只训 φ（本节 130 个参数）；full FT：全部参数都训（本节 118,402 个） |
| 3 | 一个训练循环兼容两种方式 | 优化器只接收 `[p for p in model.parameters() if p.requires_grad]`，切换方式只需调用 `freeze_body` / `unfreeze_body` |
| 4 | Pooling | 分类需要"每个序列一个向量"：mean pool（本节）、CLS pool（BERT）、last-token pool（GPT 类）；mean pool 必须按 attention mask 加权，排除 padding |
| 5 | Padding 与 mask | `ByteTokenizer` 用 256 作 PAD，`attention_mask` 1/0；mask 同时用于注意力（屏蔽 pad 作为 key）和 pooling（不计入平均） |
| 6 | P / R / F1 | `P = TP/(TP+FP)`、`R = TP/(TP+FN)`、`F1 = 2PR/(P+R)`；分母为 0 时返回 0；混淆矩阵按 `[[TN, FP], [FN, TP]]` 打印 |
| 7 | 分层划分 | `stratified_split` 对每个类别分别按 80/20 切分，测试集保持 50/50 平衡，P/R 才能直接解读 |
| 8 | 成本与收益 | head-only 快、几乎不占额外显存、小数据下不易过拟合；full FT 慢（本节实测约 5 倍耗时）、有灾难性遗忘风险，但在领域漂移大、数据多时上限更高 |
| 9 | 预训练 body 的意义 | 讲义：用 `pretrain_quick` 先做 5 个 epoch 的 LM 训练，让 body 有非平凡的起点；随后丢掉 LM head，只保留 body |
| 10 | 评估要警惕泄漏 | 本节 fixture 总共只有 73 种不同的句子，测试集 160 条中 158 条与训练集逐字重复，F1 = 1.000 并不能说明泛化能力 |

### 核心技能（能动手做到）

- [ ] 给定 hidden 维度和类别数，算出 head-only 与 full FT 的可训练参数量，并用 `trainable_params` 验证
- [ ] 写出按 mask 加权的 mean pool，并能用"扰动 pad 位置、输出不变"的方法测试它
- [ ] 从 logits 手算混淆矩阵与 P/R/F1，处理分母为 0 的边界情况
- [ ] 实现"只解冻最后一个 block"的 partial FT，以及 body / head 使用不同学习率的参数组
- [ ] 发现并修复本节 body 缺少因果 mask 导致的 LM 预训练"偷看答案"问题
- [ ] 识别数据集中训练/测试的重复泄漏，并改成按模板（分组）划分

---

## 二、基础自测（选择题）

**Q1.** 本节 `Classifier` 的 hidden = 64、类别数 = 2。冻结 body 后，`trainable_params(model)` 返回多少？

- A. 128
- B. 130
- C. 118,272
- D. 118,402

**Q2.** 对单个样本，hidden states 为 `[[1.0, 0.0], [2.0, 0.0], [99.0, 99.0]]`，mask 为 `[1, 1, 0]`，`mean_pool` 的输出是：

- A. `[34.0, 33.0]`
- B. `[1.0, 0.0]`
- C. `[51.0, 49.5]`
- D. `[1.5, 0.0]`

**Q3.** 测试集上 spam 类的计数为 TP = 45、FP = 5、FN = 15、TN = 95。precision、recall、F1 分别约为：

- A. 0.900、0.750、0.818
- B. 0.750、0.900、0.818
- C. 0.900、0.750、0.825
- D. 0.900、0.857、0.878

**Q4.** `train_classifier` 中写 `params = [p for p in model.parameters() if p.requires_grad]` 再构造 Adam，这样做的主要目的是：

- A. Adam 构造函数要求参数必须可训练，否则会报错
- B. 让冻结的参数在反向传播时也计算梯度
- C. 让 head-only 和 full FT 共用同一个训练函数：切换方式只靠 `freeze_body`/`unfreeze_body`，循环本身不变
- D. 防止 head 被意外冻结

**Q5.** 关于三种 pooling 的说法，正确的是：

- A. mean pool 不需要 mask，因为 pad 位置的 hidden state 恒为 0
- B. GPT 类模型通常用第一个 token 的输出做分类，因为它看到了整句
- C. CLS pool 不需要任何预训练就能直接用
- D. GPT 类（因果）模型常用最后一个非 pad token，因为只有它"看过"整句；BERT 用 CLS；本节用按 mask 加权的 mean pool

**Q6.** 本节用 `ByteTokenizer`（每个 UTF-8 字节一个 token），`max_len = 32`。下列说法正确的是：

- A. 一条 token 数超过 32 的消息会被截断，例如 `"URGENT call 09061701461 to claim your prize"`（43 字节）只保留到 `"URGENT call 09061701461 to claim"`
- B. 讲义说消息长度在 5–25 个 token 之间，所以不会有截断
- C. 超过 32 的部分会被自动放到下一个 batch
- D. 截断发生在字符级别，永远不会切开多字节字符

**Q7.** 实际运行 demo，head-only 和 full FT 的 F1 都是 1.000。对这个结果最恰当的解读是：

- A. 预训练非常有效，两种方式都达到了完美泛化
- B. full FT 过拟合了，所以和 head-only 一样
- C. fixture 只有 73 种不同句子，测试集 160 条中 158 条在训练集里逐字出现，这个分数基本是在测"记忆"而不是泛化
- D. 测试集划分没有分层，导致结果偏高

**Q8.** `freeze_body(model)` 在本节 demo 配置下返回 24，这个数字的含义是：

- A. 被冻结的参数元素个数
- B. body 中参数张量（`Parameter` 对象）的个数
- C. body 的层数
- D. 被冻结的 Transformer block 个数乘以 head 数

---

## 三、动手 / 代码题

**Q9.** 阅读 `MultiHeadAttention.forward` 和 `pretrain_quick`：

```python
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        # mask: B x T, 1 for real, 0 for pad. broadcast to B x 1 x 1 x T.
        m = mask.view(B, 1, 1, T).to(att.dtype)
        att = att.masked_fill(m == 0, float("-inf"))
```

```python
            logits = head(ids, mask)
            # Shift one for next-token prediction.
            target = ids[:, 1:].contiguous()
            ...
            logits = logits[:, :-1, :].contiguous()
```

1. `pretrain_quick` 做的是 next-token prediction，但 body 的注意力有什么问题？位置 t 预测 `ids[t+1]` 时能看到什么？
2. 修复它：给 `MultiHeadAttention` / `LMBody` 增加 `causal: bool` 参数，预训练时启用因果 mask，分类时可以保持双向。
3. 实测：原代码 5 个 epoch 后预训练 loss 为 0.0761，加上因果 mask 后为 0.1319。为什么加了因果 mask 之后 loss 仍然这么低（对比 `ln 256 ≈ 5.55`）？

**Q10.** 下面是 fixture 的部分模板和槽位：

```python
SPAM_TEMPLATES = ["FREE entry in {n}wkly comp to win FA Cup", "URGENT call {phone} to claim your prize", ...]
HAM_TEMPLATES  = ["are you home for dinner tonight", "see you at {time} tomorrow", ...]
SLOTS = {"n": [5 个], "phone": [3 个], "amount": [5 个], "prize": [4 个], "url": [3 个],
         "discount": [4 个], "city": [4 个], "time": [4 个], "item": [5 个]}
```

1. 根据 `main.py` 中完整的 10 个 spam 模板和 10 个 ham 模板，计算 fixture 理论上最多能生成多少种不同的句子（实测 800 条中只有 73 种不同句子）。
2. 这对 80/20 划分意味着什么？讲义"precision near 0.9 and recall near 0.85"的说法与实测的 1.000 为什么对不上？
3. 设计一个更诚实的划分：如何保证测试集里的句子（或模板）从未在训练中出现？

**Q11.** 完成讲义的 Stretch goal 1 和 2：

1. 写 `unfreeze_last_block(model)`，只解冻最后一个 block 和 `ln_f`，算出此时的可训练参数量。
2. 修改 `train_classifier`，支持"head 用较大学习率、body 用较小学习率"的两个参数组。

**Q12.** 完成讲义 Stretch goal 3 的前置：写 `last_token_pool(hidden, mask)`，取每个序列最后一个非 pad 位置的 hidden state。在 `hidden = torch.arange(12.).view(2, 3, 2)`、`mask = [[1, 1, 0], [1, 1, 1]]` 上它应输出什么？如果把它换进本节的 `Classifier`，在当前（双向）body 和"加了因果 mask 的" body 上，它的含义有什么不同？

---

## 四、面试高频题

**Q13.**（基础必考）拿到一个预训练语言模型，要做二分类，有哪些微调方案？各自的成本、风险和适用场景是什么？

**Q14.**（原理深挖）什么是灾难性遗忘（catastrophic forgetting）？为什么 full FT 时 body 通常要用比 head 更小的学习率？有哪些缓解手段？

**Q15.**（工程实践）你的分类器在测试集上 F1 = 1.0，你会怎么排查"这是真的好还是评估有问题"？

**Q16.**（场景设计）要上线一个真实的短信垃圾分类器：spam 只占约 10–15%，误拦正常短信的代价远高于漏掉垃圾短信。你如何选择训练方式、评估指标和决策阈值？

**Q17.**（追问型）decoder-only（GPT 类）模型做分类时，用 mean pool、last-token pool 还是 CLS？padding 放在左边还是右边有影响吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

head 是 `nn.Linear(64, 2)`：权重 `64 × 2 = 128` 加 bias `2`，共 130。实测输出 `trainable params = 130`。A 漏了 bias；C 是 body 的参数量（118,272）；D 是 full FT 的总可训练参数（118,272 + 130 = 118,402，实测一致）。

### Q2 — 答案：D

`m = mask.unsqueeze(-1)` 为 `[[1], [1], [0]]`，相乘后第三行变为 0；求和 `[3.0, 0.0]`，除以有效长度 2，得 `[1.5, 0.0]`。这正是测试 `test_mask_excludes_pads_from_pool` 的用例（已实测）。A 是不加 mask 的平均（被 pad 位置的 99 严重污染）；B 只取了第一个位置；C 是错误地除以 2 但没屏蔽 pad。

### Q3 — 答案：A

`P = 45/(45+5) = 0.900`；`R = 45/(45+15) = 0.750`；`F1 = 2 × 0.9 × 0.75 / 1.65 = 0.818`（用 `precision_recall_f1(45, 5, 15)` 实测为 `(0.9, 0.75, 0.8181...)`）。B 把 P/R 对调了；C 用了算术平均 0.825 而非调和平均——调和平均总是 ≤ 算术平均，更惩罚两者的不平衡；D 的 recall 错用了 `TP/(TP+FP+...)`。TN 不参与这三个指标。

### Q4 — 答案：C

讲义："the same `train_classifier` function handles both, and the toggle is one call"。优化器只会更新它持有的参数；按 `requires_grad` 过滤后，head-only 时优化器里只有 head 的 2 个张量，full FT 时是全部。A 错：Adam 并不要求这一点（把冻结参数传进去不会报错，只是它们的 `.grad` 为 None 时被跳过）；B 恰好相反；D 不是它的作用——如果 head 也被冻结，过滤后列表为空，代码会抛 `ValueError("No trainable parameters...")`。

### Q5 — 答案：D

讲义 "The Pooling Question" 列出三种方式：mean pool（本节，按 mask 加权）、CLS pool（BERT）、last-token pool（GPT 类）。A 错：body 对 pad 位置同样会产生非零的 hidden state，必须用 mask 排除（测试 `test_pad_tokens_do_not_change_pooled_output` 正是验证这一点）；B 错：因果模型中第一个 token 只能看到它自己；C 错：CLS 的表示需要在预训练或微调中学出来，讲义说 mean pool 的优点之一就是"does not require pretraining a CLS token"。

### Q6 — 答案：A

字节级 tokenizer 下 token 数 = 字节数。实测 800 条消息的字节长度在 23–54 之间，平均 34.6，**435 条（54%）超过 32 而被截断**。`"URGENT call 09061701461 to claim your prize"` 为 43 字节，编码后解码得到 `"URGENT call 09061701461 to claim"`。B 错：讲义的"5 到 25"大致是按单词数说的，与字节 token 数不是一回事；C 错：`encode` 直接 `[:max_len]` 丢弃；D 错：截断按字节进行，遇到中文等多字节字符可能切在字符中间（本 fixture 全是 ASCII，所以没暴露）。

### Q7 — 答案：C

实测：800 条数据只有 73 种不同句子；训练集 640 条中有 72 种，测试集 160 条中 158 条与训练集中的某句完全相同。分类器只要"记住"这些句子就能得满分。进一步实测：**完全不预训练、随机初始化的 body**，只训 head 20 个 epoch，测试 F1 同样是 1.0——说明这个 fixture 连"预训练是否有用"都区分不出来。A 不成立；B 无依据；D 错，代码做了分层（测试集 80/80）。

### Q8 — 答案：B

`freeze_body` 对 `model.body.parameters()` 逐个设置 `requires_grad=False` 并 `n += 1`，数的是 `Parameter` 张量个数：`tok`、`pos` 各 1 个；每个 block 有 ln1(2) + qkv(1，无 bias) + out(1，无 bias) + ln2(2) + fc1(2) + fc2(2) = 10 个，2 个 block 共 20；`ln_f` 2 个。合计 24。A 是 118,272（元素个数）。函数文档写 "Returns count frozen"，容易被误解为参数量。

### Q9 — 参考答案

1. 注意力只屏蔽了 pad 作为 key 的位置，**没有因果 mask**：每个位置都能注意到序列中所有非 pad 位置，包括它右边的位置。位置 t 的 hidden state 可以直接"看到" `ids[t+1]`，而训练目标恰好就是 `ids[t+1]`——这就是"偷看答案"。用这种方式"预训练"出来的 body，学到的一部分是"把右边那个 token 抄过来"，而不是语言建模。（对分类任务本身，双向注意力没有问题，BERT 就是双向的。）
2. 参考修改：

```python
class MultiHeadAttention(nn.Module):
    def __init__(self, hidden, heads, causal=False):
        ...
        self.causal = causal

    def forward(self, x, mask):
        ...
        att = att.masked_fill(mask.view(B, 1, 1, T) == 0, float("-inf"))
        if self.causal:
            future = torch.triu(torch.ones(T, T, dtype=torch.bool, device=x.device), diagonal=1)
            att = att.masked_fill(future, float("-inf"))
        ...
```

   `LMBody.forward(ids, mask, causal=False)` 把开关传到每个 block 更灵活：`pretrain_quick` 调用时传 `causal=True`，`Classifier` 用默认值。
3. 实测（同一种子）：双向版各 epoch loss 为 `3.83 → 2.21 → 1.11 → 0.33 → 0.076`，因果版为 `3.81 → 2.13 → 1.00 → 0.33 → 0.132`。两者都远低于均匀分布的 `ln 256 ≈ 5.55`，原因是**训练文本只有 72 种不同句子**，模型在 5 个 epoch 内就把它们背下来了：给定前缀，后续字节几乎是确定的。所以这里的低 loss 主要来自记忆，泄漏只让它再低一点；在真实的大语料上，没有因果 mask 的 LM 训练会得到一个推理时无法使用的模型（推理时右边的 token 还不存在）。

### Q10 — 参考答案

1. 逐个模板数可能的填充组合（只看模板中出现的槽位）：
   - spam：`{n}` 5 + `{phone}` 3 + `{amount}` 5 + `{prize}` 4 + `{url}×{discount}` 3×4 = 12 + `{phone}` 3 + `{city}` 4 + `{url}` 3 + `{amount}` 5 + 无槽位 1 = **45**
   - ham：无槽位 1 + `{time}` 4 + `{item}` 5 + `{time}` 4 + `{item}` 5 + 无槽位 1 + `{n}` 5 + 无槽位 1 + 1 + 1 = **28**
   - 合计 **73**，与实测的 73 种不同句子完全一致：400 × 2 次抽样已经把整个空间抽满了。
2. 80/20 划分是按"样本"而不是按"句子"进行的，同一个句子的多个副本会同时落在训练集和测试集，测试集几乎全是训练集见过的句子（158/160）。分类器只需记忆，因此实测两种方式 P = R = F1 = 1.000，而讲义描述的"P≈0.9、R≈0.85，full FT 相差一两个点"在当前代码下无法复现。讲义自己也承认"Real datasets have noise this fixture does not"。
3. 更诚实的划分：
   - **先去重再划分**：对 `set(texts)` 划分，测试集只放训练集中没出现过的句子；
   - **按模板分组划分**（group split）：例如每类拿出 2 个模板只用于测试，测的是"对新句式的泛化"；
   - 或**按槽位值划分**：测试集使用训练中没见过的电话号码、城市、物品；
   - 同时保留分层，保证测试集类别平衡。
   - 加分：这类"近重复泄漏"在真实数据（转发的短信、模板化邮件）中极常见，生产中常用 MinHash 等近重复检测在划分前做去重。

### Q11 — 参考答案

```python
def unfreeze_last_block(model: Classifier) -> int:
    freeze_body(model)
    for p in list(model.body.blocks[-1].parameters()) + list(model.body.ln_f.parameters()):
        p.requires_grad = True
    return trainable_params(model)
```

实测返回 **49,986**：最后一个 block 49,728（ln1 128 + qkv 12,288 + out 4,096 + ln2 128 + fc1 16,640 + fc2 16,448）+ `ln_f` 128 + head 130。介于 head-only（130）与 full FT（118,402）之间。注意要连 `ln_f` 一起解冻：它在最后一个 block 之后、紧挨着 pooling，冻结它会限制最后一层的可调范围。

参数组版本的训练函数：

```python
def train_classifier(model, train_loader, epochs, head_lr, body_lr, seed):
    torch.manual_seed(seed)
    groups = []
    head_params = [p for p in model.head.parameters() if p.requires_grad]
    body_params = [p for p in model.body.parameters() if p.requires_grad]
    if head_params:
        groups.append({"params": head_params, "lr": head_lr})
    if body_params:
        groups.append({"params": body_params, "lr": body_lr})
    if not groups:
        raise ValueError("No trainable parameters.")
    opt = torch.optim.Adam(groups)
    ...  # 循环不变
```

讲义建议的生产配置是"head 用 cosine 调度、body 用更小的常数学习率"；可以在此基础上给 head 的参数组配 `torch.optim.lr_scheduler.LambdaLR`，让两个组使用不同的调度函数。

### Q12 — 参考答案

```python
def last_token_pool(hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    idx = mask.sum(dim=1).clamp(min=1) - 1                 # 每行最后一个有效位置（假设右侧 padding）
    return hidden[torch.arange(hidden.size(0)), idx]       # (B, D)
```

实测输出 `[[2., 3.], [10., 11.]]`：第一行有效长度 2，取位置 1；第二行有效长度 3，取位置 2。

含义差异：
- 在**当前双向 body** 中，每个位置都已看过整句，最后一个 token 只是"众多相似表示之一"，并无特殊地位，mean pool 通常更稳定。
- 在**因果 body** 中，只有最后一个有效 token 汇总了整句信息，前面的位置只看到前缀；此时 mean pool 会把"只看到一半句子"的表示也平均进来，last-token pool 才是 GPT 类分类器的自然选择（讲义："This is what GPT-class classifiers do"）。
- 注意：`idx` 的计算假设 pad 在右侧（本节 `ByteTokenizer` 正是右侧 padding）；若用左侧 padding，最后一个有效 token 恒在位置 `T-1`。

### Q13 — 参考回答要点

- **从零训练**：讲义明确说是"wrong option"——丢掉了预训练 body 编码的词、位置、共现结构。
- **head-only（linear probing）**：冻结 body，只训分类头。可训练参数极少（本节 130），训练快、显存省（不需要 body 的梯度和优化器状态），小数据下不易过拟合；上限受限于 body 表示的好坏。
- **partial FT**：只解冻最后几层（本节最后一层 + ln_f + head = 49,986 个参数），折中。
- **full FT**：全部参数可训（本节 118,402），实测耗时约为 head-only 的 5 倍（10.8 s vs 2.2 s）；需要存全部梯度和 Adam 状态；小数据下易过拟合、有灾难性遗忘风险；领域与预训练差距大、数据多时收益最大。
- **参数高效微调（PEFT，如 LoRA）**：冻结 body，在其中插入低秩可训练矩阵，兼顾 full FT 的表达力与 head-only 的成本（加分点，见阶段 11 · 08）。
- 讲义结论："On 800 examples and a tiny body, head-only is the right call. On 80,000 examples and a bigger body, full fine-tuning starts to pay off."

### Q14 — 参考回答要点

- **定义**：在新任务上训练时，模型参数偏离预训练得到的解，导致原有的通用能力（语言知识、其他任务表现）显著下降。小数据 + 大学习率 + 多 epoch 时最严重。讲义："the body's pretraining gets washed out by overfitting noise"。
- **为什么 body 用小学习率**：body 已在一个好的区域，只需要小幅调整；head 是随机初始化的，需要大步走。同一个大学习率会让 body 前几步被随机 head 产生的大梯度"打乱"。本节配置 head-only 用 5e-3、full FT 用 1e-3，但 full FT 的 head 也只得到 1e-3——更合理的是两个参数组（Q11）。
- **缓解手段**：分层/判别式学习率（越底层越小）；先 head-only 训几轮再解冻（gradual unfreezing）；warmup；早停、weight decay；LoRA 等 PEFT 只改少量参数；混入一部分预训练数据或通用任务数据。
- 常见误区：只看下游指标，不评估原能力是否退化。

### Q15 — 参考回答要点

- **查泄漏**：训练/测试是否有完全重复或近重复样本（本节实测 158/160 重复）；是否按用户、模板、时间等分组划分；预训练语料是否包含测试集。
- **查标签**：标签是否能从某个"捷径特征"直接读出（例如本节 spam 模板含大写单词、电话号码、URL，几个字节就能判断）；试试只用简单基线（关键词规则、词袋 + 逻辑回归），若基线也接近满分说明任务太简单。
- **查评估代码**：混淆矩阵四格之和是否等于测试集大小（测试 `test_evaluate_on_trained_model_is_above_random` 就检查了这一点）；正类定义是否正确；是否误用了训练集。
- **做消融**：随机初始化的 body 是否也能满分（本节实测是），能否区分"预训练有用"与"任务太简单"。
- **换更难的测试集**：分布外样本、对抗改写、真实数据。
- 加分点：报告置信区间——准确率 160/160 的 95% 置信下限（Clopper-Pearson，`0.025^(1/160)`）约为 0.977，小测试集上的指标本身就有不小的不确定性。

### Q16 — 参考回答要点

- **数据**：真实数据，按时间或发送方分组划分避免泄漏；去重；保留真实的类别比例做测试集（训练可以重采样或加权）。
- **训练方式**：先 head-only 建基线（快、稳），数据量足够且领域偏离预训练语料（短信缩写、号码、链接）时再尝试 partial/full FT 或 LoRA，并用验证集早停。
- **指标**：类别不平衡时 accuracy 没意义（全预测 ham 也有 85%+）。误拦代价高 → 重点看 spam 类的 **precision**（被拦的里有多少真是垃圾），在 precision 达标（如 ≥ 0.99）的前提下最大化 recall；同时看 PR 曲线 / PR-AUC，而不仅是单点 F1。
- **阈值**：本节 `evaluate` 用 `argmax`（相当于阈值 0.5）。生产中应在验证集上根据业务约束选择阈值，例如 `softmax(logits)[:, 1] > 0.9` 才拦截；还可以加"疑似"中间档转人工或放入垃圾箱而不是直接删除。
- **上线后**：监控拦截率、用户申诉率，周期性用新数据重训，防止垃圾短信模式漂移。
- 加分：用 F-beta（β < 1 更重视 precision）代替 F1 作为选模型的指标。

### Q17 — 参考回答要点

- **因果模型**：位置 t 只能看到 ≤ t 的 token，只有最后一个有效 token 的表示包含整句信息，所以 GPT 类分类器通常取最后一个非 pad token（讲义）。mean pool 也能用，但平均进来的大多是"只看到前缀"的表示。
- **双向模型**（BERT 类）：每个位置都看到整句，用 CLS 或 mean pool 都可以；mean pool 不需要预训练 CLS，对长度变化更稳定。
- **本节的特殊情况**：本节 body 实际上没有因果 mask（是双向的），所以 mean pool 合理；若按 Q9 修成因果，就应该考虑换成 last-token pool。
- **padding 方向**：右侧 padding 时最后有效 token 的位置因样本而异，要用 `mask.sum(1) - 1` 去取；左侧 padding 时恒为最后一个位置，取 `hidden[:, -1]` 即可，但位置编码要相应处理（否则真实 token 的位置编号会因 pad 数量而偏移）。无论哪种，都要确保 attention mask 屏蔽了 pad。
- **CLS 的变体**：对 decoder-only 模型，可以在末尾追加一个特殊 token 作为"汇总位"，微调时学习它的表示。
- 加分：讲义 stretch goal 3 的 attention pool（一个可学习的 query 对所有位置做注意力）是 mean pool 的可学习推广，在长序列上常更好。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 34 从零实现 Transformer 模块](../../34-transformer-block/docs/zh.md)：本节 `Block` 的 pre-norm 结构。
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：body + LM head 的整体结构，本节把 LM head 换掉。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：`pretrain_quick` 的 next-token 训练循环与 loss 掩码。
- [阶段 19 · 37 加载预训练 Weights](../../37-loading-pretrained-weights/docs/zh.md)：真实场景中 body 来自加载的 checkpoint。
- [阶段 04 · 05 Transfer Learning & Fine-Tuning](../../../04-computer-vision/05-transfer-learning/docs/zh.md)：冻结 backbone、换分类头的思想最早在视觉迁移学习中普及。

### 本节被哪些后续内容用到
- [阶段 19 · 39 通过监督式 Fine-Tuning 进行指令微调](../../39-instruction-tuning-sft/docs/zh.md)：同样是在预训练 body 上微调，但保留 LM head、改变数据格式。
- [阶段 19 · 40 从零实现直接偏好优化](../../40-dpo-from-scratch/docs/zh.md)：冻结参考模型、只训策略模型的思路。
- [阶段 19 · 41 完整 Evaluation 流程](../../41-eval-pipeline/docs/zh.md)：更完整的评估方法与指标。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：介于 head-only 与 full FT 之间的参数高效微调。
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：大模型时代"微调"的主流形式。

### 延伸关键词
`linear probing` · `head swap` · `requires_grad` · `parameter groups` · `discriminative learning rate` · `gradual unfreezing` · `catastrophic forgetting` · `mean / CLS / last-token pooling` · `attention pooling` · `precision / recall / F1` · `F-beta` · `PR-AUC` · `stratified split` · `group split` · `data leakage`
