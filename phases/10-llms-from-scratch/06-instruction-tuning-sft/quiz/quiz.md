# 测验 · 指令微调（SFT）（Instruction Tuning (SFT)）

> **阶段 10 · 从零构建 LLM · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | base 模型 vs chat 模型 | base 模型只会"续写"，问它问题可能续写出更多问题；SFT 教的是"回答"这一**行为**，而不是新知识（讲义："Pre-training gives the model knowledge. SFT gives the model manners."） |
| 2 | SFT 的训练循环 | 与预训练完全相同（前向 → loss → 反向 → 更新），只换了数据：结构化的（指令, 回复）对 |
| 3 | 三种数据格式 | Alpaca（instruction/input/output，单轮）、ShareGPT（conversations 列表，多轮，human/gpt）、ChatML（`<|im_start|>` / `<|im_end|>` 特殊 token） |
| 4 | Chat template | 用角色标记把对话拼成一条 token 序列；训练和推理必须用**同一个**模板 |
| 5 | Loss masking | 只在回复 token 上算 loss，指令 token 只提供上下文；分母是回复 token 数而不是序列长度 |
| 6 | 标签错位对齐 | 输入 `tokens[:-1]`、目标 `tokens[1:]`，掩码也要取 `mask[1:]` 与目标对齐 |
| 7 | SFT 超参数 | 讲义（Llama 2）：预训练峰值 lr 3e-4，SFT lr 2e-5（低 15 倍）、2 个 epoch、batch 64 个样本 |
| 8 | 灾难性遗忘 | 学习率太高 / 训练太久会冲掉预训练能力；缓解：低 lr、1–3 epoch、混入少量预训练数据 |
| 9 | 质量 > 数量 | Alpaca 52K（约 $600）、Llama 2 Chat 约 27K、LIMA 仅 1,000 条精选样本 |
| 10 | 结束符 | 回复末尾必须有 EOS / `<|im_end|>` 并计入 loss，否则模型学不会"何时停止" |

### 核心技能（能动手做到）

- [ ] 把（指令, 回复）对用 chat template 拼成 token 序列，并写出正确对齐的 loss mask
- [ ] 实现 masked cross-entropy，说清"除以回复 token 数"与"除以序列长度"、"按 token 平均"与"按样本平均"的区别
- [ ] 读懂本节 `sft_train`，指出它**根本没有用梯度更新参数**，并说明打印结果为什么因此毫无意义
- [ ] 给模板加上 EOS 与多轮对话支持，并打印 token–mask 对齐表自检
- [ ] 用第 05 节的显存账本判断"单卡 A100 全参数微调 7B"是否可行
- [ ] 设计一个能真正检测灾难性遗忘的评估方案（基座必须是预训练好的模型）

---

## 二、基础自测（选择题）

**Q1.** 关于 SFT 的作用，最准确的说法是：

- A. 主要教会模型一种新的行为模式（看到指令就给出回复），知识主要来自预训练
- B. 主要向模型灌输大量新的事实知识
- C. 改变模型架构，增加专门的"对话头"
- D. 让模型的下一个 token 预测更准，因此需要比预训练更多的数据

**Q2.** 本节代码的序列是 `[INST_START] 指令字节 [INST_END] [RESP_START] 回复字节`，`create_loss_mask` 对 `RESP_START` 之后的 token 置 1，训练时使用 `loss_mask = mask[1:]`。下列哪一个"预测"会被计入 loss？

- A. 在 `INST_END` 位置预测下一个 token `RESP_START`
- B. 在指令最后一个字节的位置预测 `INST_END`
- C. 在 `RESP_START` 位置预测回复的第一个字节
- D. 在 `INST_START` 位置预测指令的第一个字节

**Q3.** `masked_cross_entropy_loss` 的分母是 `num_response_tokens` 而不是序列长度，主要是为了：

- A. 避免除以 0
- B. 让 loss 的大小不受指令长短影响：每个回复 token 的权重相同，长指令不会"稀释"梯度
- C. 让指令 token 也能贡献梯度
- D. 让 loss 恒等于 `ln(V)`

**Q4.** 讲义中 Llama 2 的 SFT 学习率（2e-5）比预训练峰值学习率（3e-4）低约 15 倍。主要原因是：

- A. SFT 数据更多，需要更小的步长
- B. SFT 用的是 SGD，而预训练用的是 Adam
- C. SFT 的 batch 更大
- D. 模型已经有了有用的预训练特征，大学习率会破坏它们，导致灾难性遗忘和过拟合

**Q5.** 用本节 `tokenize_instruction_pair` 处理 `("What is 15 multiplied by 7?", "15 multiplied by 7 is 105.")`（两段文本都是纯 ASCII，长度分别为 27 和 26 字节），得到的 token 总数和 `create_loss_mask` 中为 1 的个数分别是：

- A. 56 与 26
- B. 55 与 27
- C. 53 与 26
- D. 56 与 27

**Q6.** 关于三种 SFT 数据格式，**错误**的说法是：

- A. Alpaca 格式的 `input` 字段是可选的
- B. ShareGPT 格式天然支持多轮对话，按惯例用 "human" / "gpt" 标记说话人
- C. ChatML 用 `<|im_start|>` / `<|im_end|>` 这样的特殊 token 界定角色
- D. 三种格式在训练时可以混用不同的模板，推理时随便选一个模板即可

**Q7.** 本节把字节值 253、254、255 直接复用为 `INST_START`、`INST_END`、`RESP_START`，同时对普通文本做了 `min(t, 252)`。为什么这种复用在处理合法 UTF-8 文本时不会与真实字符冲突？

- A. 因为英文文本中没有字节值超过 127 的字符，中文会出错
- B. 因为合法 UTF-8 编码中根本不会出现 0xF5–0xFF 这些字节值
- C. 因为 `min(t, 252)` 会把冲突的字节映射成合法字符
- D. 因为特殊 token 在 embedding 中有独立的参数

**Q8.** 运行本节代码，3 个 epoch 的平均 loss 全部是 5.6570，SFT 前后原始文本 loss 都是 5.6048（"Change: -0.0%，Minimal forgetting"）。最准确的解释是：

- A. 学习率 2e-5 太小，再多训练几个 epoch 就会下降
- B. 只有 8 条数据，模型已经完美拟合
- C. `sft_train` 算出了 `dlogits` 却从未使用，参数"更新"是随机噪声；而且所谓 base 模型是随机初始化的，"遗忘"指标没有意义
- D. loss mask 写反了，所有回复 token 都被屏蔽了

---

## 三、动手 / 代码题

**Q9.** 阅读 `sft_train` 的核心部分：

```python
            logits = model.forward(input_ids)
            loss = masked_cross_entropy_loss(logits, target_ids, loss_mask)

            batch_size, s_len, v_size = logits.shape
            probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
            probs = probs / probs.sum(axis=-1, keepdims=True)
            dlogits = probs.copy()
            dlogits[np.arange(batch_size)[:, None], np.arange(s_len), target_ids] -= 1.0

            mask_expanded = loss_mask[:, :, np.newaxis]
            num_resp = loss_mask.sum()
            if num_resp > 0:
                dlogits = dlogits * mask_expanded / num_resp

            for block in model.blocks:
                block.ffn.W1 -= lr * np.random.randn(*block.ffn.W1.shape) * 0.01
                block.ffn.W2 -= lr * np.random.randn(*block.ffn.W2.shape) * 0.01
                block.ffn.b1 -= lr * np.random.randn(*block.ffn.b1.shape) * 0.01
                block.ffn.b2 -= lr * np.random.randn(*block.ffn.b2.shape) * 0.01
```

1. `dlogits` 计算得对吗？它后来被用到了吗？参数每步实际被改变了多少？
2. 讲义写 "The gradient is masked: instruction tokens produce zero gradient. Only response tokens push the weights." 这句话对本代码成立吗？
3. `__main__` 把随机初始化的 `MiniGPT` 当作"base model"来测遗忘。即使修好了更新步骤，这个实验设计还有什么问题？
4. 给出最小的修复方案。

**Q10.** 本节的模板没有结束符：

```python
    tokens = (
        [SPECIAL_TOKENS["INST_START"]]
        + inst_tokens
        + [SPECIAL_TOKENS["INST_END"]]
        + [SPECIAL_TOKENS["RESP_START"]]
        + resp_tokens
    )
```

1. 这会导致训练好的模型在推理时出现什么问题？`evaluate_instruction_following` 为什么"看不出"这个问题？
2. 增加 `EOS = 252`（并把普通字节截到 251），修改 `tokenize_instruction_pair` 与 `create_loss_mask`，使 EOS 计入 loss。
3. 完成讲义练习 4 的核心：写一个支持多轮对话的 `create_multiturn_mask(tokens)`，序列格式为 `[USER] ... [ASST] ... [EOS] [USER] ... [ASST] ... [EOS] ...`，只有每个 `[ASST]` 之后到（含）`[EOS]` 的 token 为 1。

**Q11.** 关于 loss 的归一化方式：一个 batch 里有两条样本，A 有 2 个回复 token、每个 token 的交叉熵都是 4.0；B 有 8 个回复 token、每个都是 1.0。

1. 按"全 batch 回复 token 求平均"（per-token）和"先每条样本内平均、再对样本平均"（per-sample）分别算出 batch loss。
2. 两种方式分别更偏向哪类样本？本节代码 batch size 为 1，属于哪一种？
3. 讲义的掩码示意图如下。按"每个位置的标签"来理解，它与正文"只有 `[ASST]` 之后的 token 计入 loss"是否一致？

```
Tokens:    [SYS] You are helpful [USER] What is the capital? [ASST] Paris is the capital [EOS]
Loss mask:   0    0    0     0      0     0   0  0     0       1     1    1   1     1      1
```

**Q12.** 讲义"Real Numbers"一节说：在单张 A100 80GB 上全量微调 7B 模型、1 万条样本、2 个 epoch，约 57 分钟，吞吐约 3,000 tokens/s。

1. 用第 05 节的显存账本（12 或 16 字节/参数）判断"单卡全参数微调 7B"能否放下。
2. 用 `6ND` 检查 3,000 tokens/s 在算力上是否合理（A100 BF16 峰值按 312 TFLOPS）。
3. 如果确实只有一张 A100，实际可行的方案有哪些？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 SFT？它和预训练在数据、目标、超参数上有什么异同？为什么只要几万条样本就能把 base 模型变成助手？

**Q14.**（原理深挖）SFT 中的 loss masking 具体怎么实现？多轮对话、batch padding、sequence packing 时分别要注意什么？

**Q15.**（工程实践）你要为一个垂直领域（如法律问答）做 SFT，请设计数据构建与质量控制流程，并说明如何评估 SFT 是否成功。

**Q16.**（场景设计）SFT 之后，模型在领域问答上变好了，但写代码、做数学的能力明显下降。你如何诊断和缓解？

**Q17.**（追问型）既然 SFT 已经能让模型听指令，为什么还需要 RLHF / DPO？SFT 有哪些固有局限？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："SFT doesn't teach the model new facts. It teaches the model a new *behavior*." B 错：知识主要来自预训练（讲义举例：模型早已从维基百科等语料中知道巴黎是法国首都）；C 错：架构完全不变，只是继续训练；D 错：SFT 数据量比预训练小几个数量级（27K 样本 vs 2T token）。

### Q2 — 答案：C

目标序列是 `tokens[1:]`，掩码是 `mask[1:]`，第 i 个位置的输入是 `tokens[i]`、标签是 `tokens[i+1]`、权重是 `mask[i+1]`。`RESP_START` 本身 mask 为 0，所以"预测 `RESP_START`"（A）不计 loss；回复第一个字节的 mask 为 1，所以"在 `RESP_START` 位置预测回复第一个字节"（C）计入 loss。实际验证："What is the capital of France?" 一例中，第一个 mask=1 的目标位于下标 32，输入 token 是 255（`RESP_START`），目标是 84（`'T'`）。B、D 都属于指令部分，不计 loss。

### Q3 — 答案：B

讲义："If you divide by the total sequence length, longer instructions dilute the gradient signal." 除以序列长度时，同样的回复配上一条长指令，loss 和梯度都会变小。A 只是代码里 `if num_response_tokens == 0` 的边界处理，不是设计目的；C 恰好相反；D 只是随机初始化时的近似值。

### Q4 — 答案：D

讲义："A high learning rate during fine-tuning destroys the pre-trained knowledge... This is catastrophic forgetting." A 错，SFT 数据远少于预训练；B 错，两者都用 AdamW（顺带一提：2e-5 是 **Adam** 的学习率，在本节这种朴素 SGD 下几乎等于不动，见 Q9）；C 错，SFT 的 batch（64 个样本）比预训练（4M token）小得多。

### Q5 — 答案：A

`1（INST_START）+ 27 + 1（INST_END）+ 1（RESP_START）+ 26 = 56`；mask 中 `RESP_START` 之后的 26 个回复字节为 1。（已用 Python 实际验证。）B 把 `RESP_START` 算进了回复；C 漏了特殊 token；D 把 `RESP_START` 的 mask 当成了 1。代码打印的第一个例子同理：30 + 31 + 3 = 64 个 token、31 个回复 token（48%）。

### Q6 — 答案：D

训练与推理的 chat template 必须**完全一致**（包括特殊 token、换行、system 段位置），否则模型在推理时看到的是训练分布之外的格式，指令遵循能力会明显下降。A、B、C 都是讲义原文描述。

### Q7 — 答案：B

UTF-8 的首字节只可能是 0x00–0x7F、0xC2–0xF4，续字节是 0x80–0xBF；0xC0、0xC1 和 0xF5–0xFF 在合法 UTF-8 中永远不会出现。所以 253–255（0xFD–0xFF）可以安全地挪作特殊 token，`min(t, 252)` 对合法 UTF-8 实际上是空操作。A 错，中文字节（如"中"为 228, 184, 173）都小于 245，同样不冲突；C 错，`min` 是截断而不是映射；D 错，本节特殊 token 与字节共用同一张 256 行的 embedding 表。生产中的做法是把特殊 token 加到词表末尾、分配新的 ID，并保证它们永远不会被 BPE 拆开或从普通文本中"拼"出来。

### Q8 — 答案：C

已实际验证：一次完整训练后 `W1` 的最大变化只有约 4.6e-6（`2e-5 × 0.01 × randn`），且方向随机；`dlogits` 算完就被丢弃。loss 曲线是 8 条样本在一个几乎不变的随机模型上的 loss，epoch 平均值因此完全相同。A 错，问题不在步长而在根本没有梯度；B 错，5.657 ≈ `ln 256 = 5.545` 附近，是随机猜测的水平；D 错，mask 是对的（见 Q2）。

### Q9 — 参考答案

1. `dlogits` 的公式本身正确：softmax + 交叉熵的梯度 = `probs − one_hot`，乘以 mask 并除以回复 token 数，与 loss 的定义一致。但它**之后再也没有被使用**。参数"更新"是 `lr × 0.01 × N(0,1)` 的随机扰动，量级约 2e-7，3 个 epoch 后 `W1` 最大变化约 4.6e-6。这不是梯度下降，而是对 FFN 加了极小的噪声；注意力、LayerNorm、embedding 完全没动。
2. 不成立。代码里没有任何 token 的梯度被传回参数，"只有回复 token 推动权重"只停留在 `dlogits` 这个从未使用的变量上。讲义 Build It 中的代码与此完全相同。
3. 实验设计问题：
   - "base model" 是随机初始化的，原始文本 loss 5.6048 ≈ 随机水平，它没有任何"能力"可以被遗忘。灾难性遗忘必须在**预训练好的**模型上测量（例如先跑第 04 节的预训练、保存权重，再加载做 SFT）。
   - 只有 4 个 64 字节的窗口（`test_text` 共 287 字节），统计噪声大。
   - 判断阈值用的是 `abs(...)`，loss 下降 15% 也会被判为"遗忘"。
4. 最小修复：至少把输出头的梯度用起来（与第 04 节相同的写法）：

   ```python
   x_normed = ...  # 需要让 forward 返回 ln_f 之后的隐藏状态
   grad_token_embed = dlogits[0].T @ x_normed[0]          # (V, D)
   model.embedding.token_embed -= lr * grad_token_embed
   ```

   我们用这种"只训练输出头"的写法实测：学习率 2e-5 跑 30 个 epoch，平均 loss 只从 5.53 降到 5.51；学习率 0.1 时从 4.52 降到 2.85。这说明 2e-5 只适用于 Adam（Adam 的更新量约等于 lr，与梯度尺度无关），朴素 SGD 下需要大得多的学习率。真正的修复是用 PyTorch 的 autograd + AdamW，对全部参数反向传播。

### Q10 — 参考答案

1. 没有 EOS，模型从未见过"回复到此结束"的信号，推理时会一直生成到 `max_new_tokens` 上限，或者续写出新的指令、重复内容。`evaluate_instruction_following` 固定生成 30 个 token，又只保留 `< 128` 的字节，再截取前 80 个字符，所以完全暴露不出"停不下来"的问题。讲义的掩码示意图里其实有 `[EOS]`，代码却没有实现。

2. 参考实现：

   ```python
   SPECIAL_TOKENS = {"EOS": 252, "INST_START": 253, "INST_END": 254, "RESP_START": 255}

   def tokenize_instruction_pair(instruction, response):
       clip = lambda s: [min(t, 251) for t in s.encode("utf-8")]
       return ([SPECIAL_TOKENS["INST_START"]] + clip(instruction)
               + [SPECIAL_TOKENS["INST_END"], SPECIAL_TOKENS["RESP_START"]]
               + clip(response) + [SPECIAL_TOKENS["EOS"]])
   ```

   `create_loss_mask` 不需要改：`RESP_START` 之后的所有 token（包括 EOS）都会被置 1，模型因此学会在回复结束后输出 EOS。生成时遇到 EOS 就停止。

3. 多轮掩码：

   ```python
   def create_multiturn_mask(tokens, asst=255, eos=252, user=253):
       mask = np.zeros(len(tokens), dtype=np.float32)
       in_resp = False
       for i, t in enumerate(tokens):
           if t == asst:
               in_resp = True
               continue              # 角色标记本身不计 loss
           if t == user:
               in_resp = False
           if in_resp:
               mask[i] = 1.0
               if t == eos:
                   in_resp = False   # EOS 计入，之后关闭
       return mask
   ```

   自检方法：把 `tokens` 和 `mask` 逐行打印对齐，确认三段回复（含各自 EOS）为 1，三段用户输入与角色标记为 0。

### Q11 — 参考答案

1. per-token：`(2×4.0 + 8×1.0) / (2+8) = 16/10 = 1.6`；per-sample：`(4.0 + 1.0) / 2 = 2.5`。
2. per-token 让长回复的样本占更大权重（B 占 80% 的权重）；per-sample 让每条样本权重相同，短回复中的每个 token 权重更大。两者都有使用：多数训练框架默认按 batch 内有效 token 求平均；需要注意梯度累积时，若每个 micro-batch 各自先平均再累加，结果会悄悄变成"按 micro-batch 平均"，与一次性大 batch 不等价。本节 batch size 为 1，两种方式此时相同，都等于"本条样本回复 token 的平均"。
3. 不一致。示意图有 15 个 token、9 个 0 和 6 个 1：下标 9 是 `[ASST]`，却被标为 1；`[EOS]` 也是 1。若把它理解为"每个位置作为**输入**、预测下一个 token 是否计 loss"，那么 `[ASST]` 位置预测 "Paris" 应计入，而 `[EOS]` 位置后面已无 token，不应计入——仍然对不上。按"每个 token 作为**标签**"理解（与本节代码一致），正确的掩码应是 `[ASST]` 为 0、`Paris … [EOS]` 为 1，共 10 个 0、5 个 1。读掩码图时一定要先弄清它是按输入还是按标签对齐的。

### Q12 — 参考答案

1. 放不下。按讲义口径 12 字节/参数，7B 需要 84 GB；按含 FP32 master 权重的 16 字节/参数，需要 112 GB——都超过 80 GB，还没算激活。
2. 算力上合理：`6 × 7e9 × 3,000 ≈ 1.26e17 FLOP/s ≈ 126 TFLOPS`，约为 A100 BF16 峰值 312 TFLOPS 的 40%，是常见的 MFU 水平。所以"57 分钟"在算力上说得通，问题出在显存。
3. 单卡可行方案：
   - LoRA / QLoRA：冻结基座，只训练低秩适配器，优化器状态只针对少量参数；QLoRA 再把基座量化为 4-bit（见阶段 11 · 08）；
   - 8-bit 优化器、梯度检查点、CPU offload（ZeRO-Offload）组合起来勉强可做全参数微调，但会明显变慢；
   - 或者使用多卡 + FSDP（第 05 节）。

### Q13 — 参考回答要点

- **定义**：在预训练模型上，用（指令, 回复）对继续做 next-token prediction，只对回复部分计算 loss。
- **相同点**：模型结构、前向、交叉熵、反向传播都不变。
- **不同点**：
  - 数据：原始文本 → 结构化对话（chat template + 角色标记）；
  - 目标：所有 token → 只有回复 token（loss mask）；
  - 超参数（讲义 Llama 2）：lr 3e-4 → 2e-5，1 个 epoch → 2 个 epoch，4M token/batch → 64 个样本/batch，2T token → 约 27K 样本。
- **为什么几万条就够**：知识和语言能力已在预训练中获得，SFT 只需激活"看到助手标记就回答"这一行为模式（讲义："SFT concentrates this latent ability"）。LIMA 用 1,000 条精选样本就取得了很好的效果，说明质量远比数量重要。
- 加分点：说出 Alpaca（52K，约 $600）、Vicuna（70K ShareGPT 对话）、Llama 2 Chat（约 27K）等例子。

### Q14 — 参考回答要点

- **实现**：构造与输入等长的 label 序列，非回复位置填一个"忽略值"（PyTorch `CrossEntropyLoss` 默认 `ignore_index=-100`），或者像本节一样乘以 0/1 掩码；注意 label 要与输入错开一位。
- **多轮对话**：每一轮助手回复（含结束符）都计 loss，所有用户轮、system prompt、角色标记都不计；有的做法只对最后一轮计 loss，二者各有取舍。
- **padding**：pad 位置既不能计 loss（label 置为 -100），也要用 attention mask 屏蔽；右填充对训练更方便，批量生成时常用左填充。
- **packing**：把多条短样本拼进一个长序列以提高 GPU 利用率时，要么使用块对角注意力掩码 / 按样本重置位置编码，要么接受跨样本"串味"；每条样本仍需各自的 loss mask，并在边界处用 EOS 分隔。
- **归一化**：per-token 还是 per-sample（见 Q11），以及梯度累积时的一致性。
- 常见误区：直接对整个序列算 loss（模型会学着"生成用户提问"）；mask 与 label 差一位；模板里的结束符没有计入 loss。

### Q15 — 参考回答要点

- **定义能力边界**：列出目标任务类型和比例（参考 `outputs/` 中的多样性清单），明确要拒答或转人工的范围。
- **数据来源**：专家撰写 + 真实用户问题改写 + 强模型合成后人工审核；注意数据许可。
- **质量控制**：
  - 事实正确性（法律条文、引用必须可查）；
  - 格式一致：统一 chat template、统一回复风格；
  - 去重（精确 + 近似去重），避免单一模板占比过高；
  - 与评测集去污染（decontamination）；
  - 过滤过短 / 过长、与指令无关、自相矛盾的回复（讲义练习 3 的质量打分器）。
- **训练配置**：lr 1e-5–5e-5、1–3 epoch、混入少量通用数据防遗忘、监控验证集 loss。
- **评估**：
  - 领域 held-out 集上的准确率 / 人工评分；
  - 通用能力回归测试（代码、数学、常识），对比 SFT 前后；
  - 格式遵循率、拒答率（过度拒答也是问题）；
  - LLM-as-judge 的 pairwise 对比（如 MT-Bench、AlpacaEval 一类）。
- 加分点：小规模先试（几百条）看趋势，再扩大数据；保留每个数据版本，便于回溯。

### Q16 — 参考回答要点

- **诊断**：
  - 在 SFT 前后用同一套通用评测（代码、数学、通用文本困惑度）对比，确认是遗忘而不是评测或模板问题；
  - 检查 chat template 是否和评测时一致；
  - 看训练曲线：验证 loss 是否在第 1 个 epoch 后上升（过拟合信号）。
- **缓解**：
  - 降低学习率（1e-5 左右）、减少 epoch、提前停止；
  - 数据混合 / 回放：在 SFT 数据中加入通用指令数据和代码、数学数据（讲义提到混入 2–5% 预训练数据）；
  - 参数高效微调（LoRA）：只更新少量参数，天然减轻遗忘，还能按任务切换适配器；
  - 必要时做模型合并（把 SFT 模型与基座或通用 chat 模型做权重插值）。
- 讲义："If the raw text loss increases by more than 10-15%, your SFT is too aggressive."
- 常见误区：只看领域指标；用随机初始化或错误的"基座"做对照（正是本节代码的问题）。

### Q17 — 参考回答要点

- **SFT 只是模仿**：它最大化示范回复的似然，学到的上限是标注者的水平；它不知道"多个合理回复里哪个更好"。
- **只有正例**：SFT 没有"不要这样回答"的负反馈，很难压制啰嗦、谄媚、编造等倾向。
- **暴露偏差**：训练时总是以标准答案为前缀，推理时却以自己生成的内容为前缀，错误会累积。
- **可能鼓励幻觉**：让模型模仿它本身并不掌握的知识的回答，会教它"自信地编"（这是近年研究讨论较多的现象）。
- **RLHF / DPO 补什么**：用偏好数据（选中 vs 拒绝）提供相对比较信号，直接优化"人更喜欢的回复"，并能惩罚不良行为。
- 实践中是 SFT → 偏好优化 的流水线：SFT 先把模型放到"会对话"的区域，偏好优化在此基础上精调；没有 SFT 直接做 RLHF 通常很难收敛。
- 衔接：下两节分别讲 RLHF（第 07 节）和 DPO（第 08 节）。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：本节直接导入那里的 `MiniGPT`，训练循环与交叉熵也一脉相承。
- [阶段 10 · 01 Tokenizers](../../01-tokenizers/docs/zh.md)、[阶段 10 · 02 从头开始构建 Tokenizer](../../02-building-a-tokenizer/docs/zh.md)：特殊 token、字节级词表与 chat template 的实现基础。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../05-scaling-distributed/docs/zh.md)：判断全参数 SFT 需要多少显存。
- [阶段 03 · 05 Loss Functions](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵与 masked loss。

### 本节被哪些后续内容用到
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../07-rlhf/docs/zh.md)：SFT 模型是奖励模型和 PPO 策略的起点。
- [阶段 10 · 08 DPO：直接偏好优化](../../08-dpo/docs/zh.md)：在 SFT 模型上直接用偏好数据优化，SFT 模型同时充当参考模型。
- [阶段 10 · 09 Constitutional AI 与自我改进](../../09-constitutional-ai-self-improvement/docs/zh.md)：用模型自己生成的数据继续做 SFT。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：单卡也能做的参数高效 SFT。
- [阶段 18 · 01 将指令遵循作为 Alignment 信号](../../../18-ethics-safety-alignment/01-instruction-following-alignment-signal/docs/zh.md)：从对齐角度看指令遵循。
- [阶段 19 · 39 通过监督式 Fine-Tuning 进行指令微调](../../../19-capstone-projects/39-instruction-tuning-sft/docs/zh.md)、[阶段 19 · 07 端到端 Fine-Tuning 流程](../../../19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/zh.md)：综合项目中完整实现 SFT。

### 延伸关键词
`chat template` · `ChatML` · `ignore_index=-100` · `loss masking` · `sequence packing` · `EOS token` · `catastrophic forgetting` · `replay / data mixing` · `LIMA` · `Alpaca` · `ShareGPT` · `decontamination` · `exposure bias` · `LoRA / QLoRA`
