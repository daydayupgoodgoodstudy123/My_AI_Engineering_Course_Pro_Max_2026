# 测验 · Multi-Token 预测（Multi-Token Prediction (MTP)）

> **阶段 10 · 从零构建 LLM · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MTP 的动机 | 普通 next-token prediction 每个位置只有 1 个监督信号；MTP 让每个隐藏状态额外预测更远的 token，训练信号更"密" |
| 2 | 并行 MTP（Gloeckle 等，2024） | D 个独立输出头都接在同一个 `h_i^(0)` 上，各自预测不同偏移；简单，但预测之间没有因果链，不能直接拿来做 speculative decoding 的 draft |
| 3 | 顺序 MTP（DeepSeek-V3，2024.12） | 第 k 个模块把上一深度的隐藏状态与"真实下一个 token 的 embedding"拼接、投影，再过一个 Transformer block，保持因果链 |
| 4 | 模块组成 | 每个模块 = 投影 `M_k`（`h × 2h`）+ 一个 Transformer block `T_k`；embedding 表 `E` 与输出头 `Out` 与主模型**共享**，不新增参数 |
| 5 | 联合损失 | `L_MTP = (λ / D) · Σ_k L_k`，总损失 `L_main + L_MTP`；讲义：λ 前期 0.3、后期 0.1 |
| 6 | 参数账 | 讲义按"投影 2h² + block 约 12h²"估算每模块约 `14h²`；h = 7168 时约 719M；DeepSeek-V3 实际 MTP 部分 14B，因为模块里的 FFN 也是 MoE |
| 7 | 推理红利 | 训练好的 MTP 模块可直接当 speculative decoding 的 draft；讲义：首个模块接受率 80%+、约 1.8× 吞吐 |
| 8 | 与 EAGLE 的区别 | EAGLE 在预训练**之后**单独训练 draft；MTP 在预训练**之中**一起训练，不能给已有 checkpoint 补装 |
| 9 | 适用边界 | 讲义：需要掌控完整预训练、隐藏维度 ≥ 4096 才划算；对已有稠密模型做 fine-tuning 时不适用 |
| 10 | 本节玩具代码的局限 | 用"相加"代替拼接、注意力退化为线性映射、没有训练；且其深度索引让 `L_1` 实际是主模型损失、最后一个模块从未参与计算 |

### 核心技能（能动手做到）

- [ ] 写出顺序 MTP 的递推式与每个深度的预测目标，说清"模块 k 看到了什么、预测什么"
- [ ] 给定隐藏维度 h、FFN 维度、D，手算 MTP 额外参数量与相对主模型的开销比例
- [ ] 解释并行 MTP 与顺序 MTP 的结构差异，以及为何只有后者天然适合做 speculative decoding 的 draft
- [ ] 读懂 `mtp_loss` 的双重循环，指出它的索引与 DeepSeek-V3 论文的差异，并能改写成"模块 k 预测 `t_{i+k+1}`"的版本
- [ ] 用"接受率 α、draft 长度 k"估算 speculative decoding 每步期望产出的 token 数，解释 1.8× 的由来
- [ ] 判断一个具体项目（从零预训练 / 继续预训练 / SFT）是否应该加入 MTP

---

## 二、基础自测（选择题）

**Q1.** DeepSeek-V3 的顺序 MTP 与 Gloeckle 等人的并行 MTP 最本质的区别是：

- A. 顺序 MTP 的第 k 个模块以前一深度的隐藏状态和"真实 token 的 embedding"为输入，保持了因果链；并行 MTP 的各个头都只看同一个 `h_i^(0)`
- B. 顺序 MTP 使用独立的 embedding 表，并行 MTP 共享 embedding 表
- C. 并行 MTP 只能预测 1 个额外 token，顺序 MTP 可以预测任意多个
- D. 顺序 MTP 在推理时必须关闭，并行 MTP 可以用于推理加速

**Q2.** 一个 MTP 模块中，哪些部分是**新增参数**？

- A. 只有共享输出头
- B. embedding 表、投影 `M_k` 和 Transformer block
- C. 投影 `M_k` 和 Transformer block `T_k`
- D. 只有投影 `M_k`

**Q3.** 按讲义的估算方法（投影 `2h²` + 注意力 `4h²` + SwiGLU MLP `8h²`），h = 7168、D = 1 时 MTP 额外参数约为：

- A. 51M
- B. 205M
- C. 14B
- D. 719M

**Q4.** 设 D = 1、λ = 0.3，某一步主损失 `L_main = 2.1`，MTP 第 1 深度损失 `L_1 = 2.0`。总训练损失是：

- A. 4.10
- B. 2.70
- C. 2.40
- D. 1.23

**Q5.** 讲义说 DeepSeek-V3 的 MTP 部分是 14B，而按稠密 block 估算每模块只有约 720M。差距的主要原因是：

- A. MTP 模块额外复制了一份 embedding 表
- B. MTP 模块额外复制了一份输出头
- C. D = 20，有 20 个模块
- D. MTP 模块里的 Transformer block 也继承了 MoE 结构，专家参数把模块参数量撑大

**Q6.** 若把 D = 1 的 MTP 模块当作 draft，每步只起草 1 个 token、接受率为 α，且忽略 draft 本身的开销，每次主模型前向期望产出的 token 数是：

- A. `1 + α`
- B. `α`
- C. `1 / (1 − α)`
- D. `2α`

**Q7.** 下列哪种场景**最不适合**引入 MTP？

- A. 从零预训练一个 hidden = 7168 的 MoE 模型，并计划大规模在线服务
- B. 从零预训练一个 hidden = 4096 的稠密模型，希望训练信号更密
- C. 在一个已经预训练好的稠密 checkpoint 上做 SFT，希望顺便获得 MTP draft
- D. 预训练时同时需要更密的训练信号和推理时的 speculative decoding

**Q8.** 运行本节 `code/main.py`，Step 1 打印 `L_1=3.672, L_2=3.272`，而均匀随机猜测的参考值是 `3.466`。关于这组数字，正确的是：

- A. `L_1 < ln 32`，说明模型已经学到了下一个 token
- B. `L_1` 高于 `ln 32`，因为玩具 backbone 隐藏状态是用"当前 token"的 embedding 加噪声构造的，共享输出头更倾向于预测当前 token 而不是下一个
- C. `L_2 < L_1` 证明了"越远的 token 越容易预测"
- D. 这些损失是训练 100 步后的结果

---

## 三、动手 / 代码题

**Q9.** 阅读 `mtp_loss` 的核心循环：

```python
    for i in range(len(backbone_hidden) - D):
        h_prev = backbone_hidden[i]
        for k in range(1, D + 1):
            logits = shared_head_logits(h_prev, E)
            tgt = tokens[i + k]
            per_depth[k - 1] += cross_entropy(logits, tgt)
            next_embed = E[tokens[i + k]]
            h_prev = mtp_forward(h_prev, next_embed, modules[k - 1])
        n_valid += 1
```

1. 当 k = 1 时，`logits` 由哪个隐藏状态算出？`L_1` 实际上是谁的损失？
2. D = 2 时，`modules[1]`（第 2 个模块）的输出被用到了吗？如何用实验验证？
3. DeepSeek-V3 论文中模块 k 的输出 `h_i^(k)` 用于预测 `t_{i+k+1}`。请把循环改写成与论文一致的版本，并说明外层 `range` 需要怎样调整。

**Q10.** `attention_single` 的实现如下：

```python
    q = matvec(Wq, v_in)
    k = matvec(Wk, v_in)
    v = matvec(Wv, v_in)
    score = sum(q[i] * k[i] for i in range(len(q))) / math.sqrt(len(q))
    weight = 1.0
    attended = [weight * vi for vi in v]
    return matvec(Wo, attended)
```

1. `score` 对输出有没有影响？`Wq`、`Wk` 的取值会改变结果吗？
2. 这个"注意力"在数学上等价于什么？
3. 为什么"单 token 的自注意力"权重必然是 1？真实的 MTP 模块里，`T_k` 的注意力在看什么？

**Q11.** 用 `count_parameters` 的公式（`per_mtp = h² + 4h² + 3·h·ff`）与讲义公式（`14h²`）分别计算 Llama 风格稠密 70B（h = 8192，ff = 28672，80 层，D = 1）的 MTP 额外参数，并解释两者差在哪里；再算它相对代码给出的主模型 78.9B 的开销比例（对应讲义练习 2）。

**Q12.** Step 3 打印了"噪声越小，L_1 和 L_2 都下降"的表格，并声称在"模拟训练"。请评估这个结论：它真的模拟了训练吗？换随机种子还成立吗？如果要真正完成讲义练习 1（"用固定模式验证 depth-1 和 depth-2 损失都收敛"），合成数据应该怎么构造？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 Multi-Token Prediction？DeepSeek-V3 的 MTP 是怎么做的，训练和推理时分别起什么作用？

**Q14.**（原理深挖）为什么说并行 MTP 头"不能直接用来做 speculative decoding"，而顺序 MTP 可以？顺序结构在训练时为什么要喂入"真实 token"的 embedding 而不是模型自己预测的 token？

**Q15.**（工程实践）你负责一个 70B 级 MoE 模型的预训练，老板问"要不要加 MTP、加几层、λ 怎么设、要付出多少代价"。请给出你的方案和评估指标。

**Q16.**（追问型）MTP 和 EAGLE-3 都能做 draft，它们的接受率差不多，为什么还要在预训练里加 MTP？反过来，什么情况下 EAGLE 更合适？

**Q17.**（场景设计）推理时用 D = 1 的 MTP 模块做 speculative decoding，请描述一次 decode step 的完整流程（包括验证、接受/拒绝、KV cache 的处理），并估算接受率 0.85 时的理论加速上限。

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："DeepSeek-V3's sequential design builds `h_i^(k)` from `h_i^(k-1)` plus the actual next-token embedding `E(t_{i+k})`. That preserves the causal chain"。并行 MTP 的 D 个头都直接作用在 `h_i^(0)` 上，彼此不条件依赖。

- B 反了：顺序 MTP 恰恰**共享** embedding 表和输出头。
- C 错：两者都可以有 D 个深度。
- D 错：顺序 MTP 正是推理时可复用为 draft 的那一个。

### Q2 — 答案：C

讲义 Parameter accounting：共享输出头"No extra params"，共享 embedding"No extra params"；新增的是投影 `M_k`（`2h²`）和 Transformer block `T_k`（约 `12h²`）。代码中 `MTPModule` 也只含 `M_k` 和 block 的 7 个矩阵，`E` 作为参数单独传入。A、B 把共享部分当成新增；D 漏了 block。

### Q3 — 答案：D

`14 × 7168² = 719,323,136 ≈ 719M`（已用 Python 计算）。讲义写作"~720M"。A（51M）是 `h²`；B（205M）约是 `4h²`（仅注意力）；C 是 DeepSeek-V3 实际报告的 MTP 参数量（包含 MoE 专家）。

### Q4 — 答案：B

`L_MTP = (λ / D) · L_1 = 0.3 / 1 × 2.0 = 0.6`；总损失 `L_main + L_MTP = 2.1 + 0.6 = 2.70`。

- A（4.10）忘了乘 λ，把 MTP 损失与主损失等权相加。
- C（2.40）把 λ 本身当成了要加的量（2.1 + 0.3）。
- D（1.23）把 λ 同时乘到了主损失上（0.3 × 4.1）——λ 只作用于 MTP 部分，主损失权重恒为 1。

延伸：若 D = 2、`L_1 = 2.0`、`L_2 = 2.4`，则 `L_MTP = 0.3 / 2 × 4.4 = 0.66`。"除以 D"让 MTP 部分的总权重不随深度数增加而膨胀。

### Q5 — 答案：D

讲义："DeepSeek reports 14B — the difference is mostly expert layers being MoE in the MTP module too." 讲义练习 2 也要求解释这一点。A、B 错：embedding 和输出头是共享的。C 错：DeepSeek-V3 用的是 D = 1（模型卡写作 671B 主模型 + 14B MTP 模块 = 685B）。

### Q6 — 答案：A

每步主模型一次前向至少产出 1 个 token（即使 draft 被拒，也会用主模型自己的分布补一个）；draft 被接受时额外多得 1 个，因此期望为 `1 + α`。一般地，起草 k 个、逐个以 α 独立接受时，期望产出 `(1 − α^(k+1)) / (1 − α)`；k = 1 时化简为 `1 + α`。α = 0.8 时恰好是 1.8（已计算），与讲义"80%+ 接受、约 1.8×"吻合（忽略 draft 开销的理想值）。C 是 k → ∞ 的极限；B、D 不对。

### Q7 — 答案：C

讲义 "When not to"："Fine-tuning an existing pre-trained dense model. The MTP module is not trained." MTP 模块需要和主模型一起预训练，SFT 阶段才临时加上，它没有经过大规模训练，既得不到"更密的训练信号"的好处，作为 draft 也不会有高接受率。A、B、D 都是讲义 "When to use" 列出的典型场景（hidden ≥ 4096、掌控完整预训练、计划规模化服务）。

### Q8 — 答案：B

实际验证：`backbone_hidden[i] = rms_norm(E[tokens[i]] + noise)`，用共享头 `logits[v] = E_v · h` 打分时，argmax 有 **9/12** 个位置等于**当前 token** `t_i`，等于下一个 token `t_{i+1}` 的次数为 **0**。目标却是 `t_{i+1}`，于是正确 token 的概率比均匀分布还低，`L_1 = 3.672 > ln 32 = 3.466`。

- A 方向说反了。
- C 错：`L_2` 恰好低于 `L_1` 只是随机初始化下的偶然数值，没有任何训练，不能说明"远处更好预测"。
- D 错：整份代码**没有任何训练步骤**，所有权重都是随机初始化。

### Q9 — 参考答案

1. k = 1 时 `h_prev = backbone_hidden[i]`，即 `h_i^(0)`，`logits = Out(h_i^(0))`，目标 `t_{i+1}`——这就是**主模型自己的 next-token 损失**，不是 MTP 损失。已验证：对同样 10 个位置单独计算主模型交叉熵，结果正好是 3.6723，与 `L_1` 完全相同。
2. 没有被用到。循环在 k = D 时先算 logits，再调用 `mtp_forward(..., modules[D-1])` 更新 `h_prev`，但之后循环结束，这个 `h_prev` 被丢弃。验证方法：把 `modules[1]` 换成另一个随机模块，`(total, per_depth)` 完全不变（实测仍为 `1.04166..., [3.6723, 3.2721]`）；而替换 `modules[0]` 后 `L_2` 从 3.272 变为 3.340。所以 D = 2 时实际上只有 1 个 MTP 模块在起作用，且 `L_MTP` 把主损失也算了进去（再乘 λ/D）。
3. 与论文一致的写法（模块 k 的输出预测 `t_{i+k+1}`）：

```python
    for i in range(len(backbone_hidden) - D - 1):     # 需要 t_{i+D+1} 存在
        h_prev = backbone_hidden[i]                    # h_i^(0)，主模型负责预测 t_{i+1}
        for k in range(1, D + 1):
            next_embed = E[tokens[i + k]]              # 真实 t_{i+k} 的 embedding
            h_prev = mtp_forward(h_prev, next_embed, modules[k - 1])   # h_i^(k)
            logits = shared_head_logits(h_prev, E)
            per_depth[k - 1] += cross_entropy(logits, tokens[i + k + 1])
        n_valid += 1
```

要点：先更新隐藏状态再算 logits；目标从 `t_{i+2}` 开始；外层少一个位置；主损失 `L_main` 单独计算，不进入 `L_MTP`。这样 D 个模块都参与，`L_MTP = (λ/D)·Σ L_k` 里的每一项都是真正的 MTP 损失。

### Q10 — 参考答案

1. 没有影响。`score` 算完后从未被使用，`weight` 被硬编码为 1.0，因此 `Wq`、`Wk` 取任何值输出都不变——它们是"死参数"，却仍被 `count_parameters` 计入 `4h²`。
2. 等价于一个线性映射：`attention_single(x) = Wo · Wv · x`。整个 block 因此是"残差 + 线性层 + 残差 + SwiGLU"。
3. 只有一个 key 时，softmax 只对一个分数归一化，结果恒为 1，所以注释说"degenerate"。真实 MTP 模块里 `T_k` 是完整的因果自注意力：在深度 k，对所有位置 `i` 的组合表示 `M_k[RMSNorm(h_i^(k-1)); RMSNorm(E(t_{i+k}))]` 构成一条序列，位置 i 会注意它之前的所有位置，因此也需要自己的 KV cache。另外代码在注意力前没有做 RMSNorm（只有 MLP 前做了），与标准 pre-norm block 也不一致。

### Q11 — 参考答案

已用 Python 计算：

| 口径 | 公式 | 结果 |
|------|------|------|
| 代码 `count_parameters` | `h² + 4h² + 3·h·ff = 67.1M + 268.4M + 704.6M` | **1,040,187,392 ≈ 1.04B**（约 15.5h²） |
| 讲义 | `14h²` | **939,524,096 ≈ 0.94B** |

差异来源：

- **投影**：讲义按真实 DeepSeek 的拼接 `[2h] → h` 算 `2h²`；代码用"相加"代替拼接，`M_k` 只有 `h × h`，少 `h²`。
- **MLP**：讲义按 SwiGLU 隐层 `8h/3` 估成 `8h²`；代码用的是 Llama 风格 ff = 28672 = 3.5h，三块矩阵是 `10.5h²`，多出 `2.5h²`。
- 二者都按 MHA 算注意力 `4h²`；真实的 70B（如 Llama 3 70B）用 GQA，K/V 投影更小，注意力实际约 `2.25h²`（若 8 个 KV 头）。

开销比例：`1.04B / 78.9B ≈ 1.3%`（代码打印 `1.3% overhead`）；讲义口径 `0.94B / 70B ≈ 1.34%`。与 DeepSeek-V3 的 `14B / 671B ≈ 2.1%` 相比，稠密模型开销更低——因为 DeepSeek 的 MTP block 也是 MoE。

### Q12 — 参考答案

- **没有模拟训练**：Step 3 只是把构造 backbone 隐藏状态时的高斯噪声从 0.5 调到 0.05，所有模块参数和 `E` 都不变。噪声变小只意味着 `h_i^(0)` 更接近 `E[t_i]`（当前 token）——这与"预测下一个 token"没有因果关系。
- **结论不稳健**：已实测，固定 `E`/tokens/模块、只换噪声种子时，`L_1` 单调下降的情况为 28/50；连同 `E`、tokens、模块一起换随机种子时只有 14/50。种子 23 + 42 恰好给出了单调下降的表格。
- **正确构造**：让序列有可学习的规律，并真正做梯度更新。例如：
  - 固定模式：`tokens = [i % 5 for i in range(seq)]`（或 `t_{i+1} = (t_i + 3) % V`），使 `t_{i+1}`、`t_{i+2}` 都是 `t_i` 的确定函数；
  - 构造 `h_i^(0)` 时让它编码"下一个 token"（如 `E[t_{i+1}]` 加噪声），或者加一个可训练的 backbone；
  - 对 `M_k`、block 权重做数值梯度（或换 NumPy/PyTorch 用自动微分）迭代若干步，观察 `L_1`、`L_2` 同时下降到接近 0。

### Q13 — 参考回答要点

- **定义**：在标准 next-token 损失之外，让模型在每个位置额外预测更远的 token（`t_{i+2}`、`t_{i+3}`…），提供更密的监督信号。
- **DeepSeek-V3 的做法**：主模型之上串联 D 个 MTP 模块（DeepSeek-V3 用 D = 1）。模块 k：`h_i^(k) = T_k(M_k [RMSNorm(h_i^(k-1)); RMSNorm(E(t_{i+k}))])`，再用共享输出头预测 `t_{i+k+1}`；embedding 与输出头共享。
- **损失**：`L = L_main + (λ/D)·Σ L_k`。讲义：λ 前期 0.3、后期 0.1（DeepSeek-V3 技术报告原文是前 10T token 用 0.3、余下 4.8T token 用 0.1，并非"前 10% 训练"）。
- **训练作用**：更密的信号；讲义称在 MMLU、GSM8K、MATH、HumanEval 上有几个百分点的一致提升；讲义估计训练变慢约 10%。
- **推理作用**：可以直接丢弃 MTP 模块，主模型照常推理；也可以把它当 speculative decoding 的 draft，讲义：接受率 80%+、约 1.8× 吞吐。
- 加分点：说清"共享 embedding / head 让参数开销只有约 2%（14B/671B）"。

### Q14 — 参考回答要点

- **并行头的问题**：各头都只看 `h_i^(0)`，第 2 个头预测 `t_{i+2}` 时并不知道第 1 个头给出了什么 `t_{i+1}`。推理时如果第 1 个 token 被替换（例如采样到了别的 token），第 2 个头的预测并不会随之改变，起草出的多个 token 之间可能互相矛盾，接受率低。
- **顺序结构的好处**：模块 k 的输入里显式包含 `E(t_{i+k})`。推理时把"刚起草出的 token"的 embedding 喂进去，就得到以它为条件的下一个预测——这和自回归解码完全同构，讲义说它"structurally identical to how an autoregressive decoder consumes its own output"。
- **训练时喂真实 token**：这就是 teacher forcing。用真实 token 训练稳定、可并行（所有位置一次算完），不需要在训练中采样；代价是训练/推理存在暴露偏差（推理时喂的是 draft token，可能错）。但因为错误的 draft 会被主模型验证拒绝，不影响最终输出正确性，只影响接受率。
- 加分点：指出 speculative decoding 的"无损"由验证步骤保证，与 draft 好坏无关；draft 只决定速度。

### Q15 — 参考回答要点

- **深度 D**：起步用 D = 1（DeepSeek-V3 的选择；讲义附带的 skill 文件也把"首次集成 D > 2"列为 hard reject）。每增加一层深度，训练每步多一个 block 的前向/反向。
- **λ 调度**：沿用 0.3 → 0.1 的两段式；监控 MTP 损失占比，若它主导了总损失就下调。
- **参数与显存**：每模块 = 投影 `2h²` + 一个 MoE block；embedding/head 共享。还要算激活显存（D 个模块的激活要保存用于反向）和 pipeline 并行时 MTP 模块放在哪个 stage（DeepSeek-V3 把 embedding、输出头和 MTP 模块放在同一个 PP rank 上以共享参数）。
- **代价**：讲义估计训练慢约 10%。
- **评估指标**：
  - 下游基准（MMLU、GSM8K、HumanEval 等）与无 MTP 基线对比（需要等算力的消融实验）；
  - MTP 模块作为 draft 的 depth-1 接受率（skill 文件建议 50B token 后应高于 70%）；
  - 线上 speculative decoding 的实际 tokens/s 提升。
- 常见误区：在已有 checkpoint 上继续预训练时临时加 MTP，期望马上获得高接受率。

### Q16 — 参考回答要点

- **MTP 的额外价值**：不仅是 draft，还提供"更密的训练信号"，对主模型质量有直接提升；draft 在预训练中与主模型共同训练，不需要额外的蒸馏流水线；部署时 draft 与主模型共享 embedding/head，权重一体发布。
- **EAGLE 更合适的情形**：
  - 模型已经训练好（无法重训），EAGLE 可以后补，"Backward-compatible with existing weights: Yes"；
  - 想针对特定业务流量重新训练 draft，迭代成本低；
  - 讲义表格中 EAGLE-3 接受率 0.88–0.92，略高于 MTP depth-1 的 0.80+。
- 对比表要点：训练时机（预训练后 vs 预训练中）、能否兼容旧权重、draft 规模（1–2 层 vs 1 block + 投影）、收益（仅加速 vs 质量 + 加速）。
- 加分点：二者不互斥——可以先用 MTP 模块作 draft，后续再针对线上分布微调 draft。

### Q17 — 参考回答要点

1. 主模型对当前前缀做一次前向，得到最后位置的隐藏状态 `h^(0)` 与下一个 token `t₁`（由主模型分布采样/贪心得到，必然正确）。
2. MTP 模块输入 `h^(0)` 与 `E(t₁)`，输出 `h^(1)`，经共享输出头得到 draft token `t₂'`。
3. 下一步主模型一次前向同时处理 `[t₁, t₂']` 两个位置：位置 `t₁` 的输出用于验证 `t₂'`（贪心时比较是否相等；采样时用 Leviathan 的接受概率 `min(1, p/q)`），位置 `t₂'` 的输出给出再下一个 token。
4. 接受：本步一次前向产出 2 个 token；拒绝：用主模型分布重采样替换 `t₂'`，并把 `t₂'` 位置写入的 KV cache 回滚（截断）。MTP 模块自身的 KV cache 也要同步回滚。
5. 加速上限：每次主模型前向期望产出 `1 + α = 1.85` 个 token（α = 0.85），理论上限约 1.85×；扣除 MTP 模块前向与验证的额外开销，实际略低。DeepSeek-V3 技术报告给出的第二个 token 接受率在 85%–90% 之间、TPS 约提升 1.8 倍，讲义概括为"80%+、1.8×"。
- 加分点：D = 1 时理论上限就是 2×；想更高需要更多深度或树状 draft，但接受率逐层递减。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：next-token 目标、交叉熵、weight tying（共享输出头的来源）。
- [阶段 10 · 15 Speculative Decoding 与 EAGLE-3](../../15-speculative-decoding-eagle3/docs/zh.md)：MTP 在推理时就是作为这里的 draft 网络使用。
- [阶段 07 · 16 Speculative Decoding — 草稿、验证、重复](../../../07-transformers-deep-dive/16-speculative-decoding/docs/zh.md)：草稿-验证框架与接受率。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：理解为何 DeepSeek-V3 的 MTP 模块参数达到 14B。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：因果链与 teacher forcing。

### 本节被哪些后续内容用到
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../20-deepseek-v3-walkthrough/docs/zh.md)：MTP 作为 V3 四大组件之一被整体装配。
- [阶段 10 · 19 DualPipe 并行](../../19-dualpipe-parallelism/docs/zh.md)：MTP 模块与主模型一起被切分到流水线中训练。
- [阶段 10 · 25 Speculative Decoding 与 EAGLE](../../25-speculative-decoding/docs/zh.md)：草稿模型的更多变体。
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../../17-infrastructure-and-production/05-eagle3-speculative-decoding/docs/zh.md)：生产推理栈里如何接 draft。
- [阶段 19 · 14 综合项目 14：推测解码 Inference 服务端](../../../19-capstone-projects/14-speculative-decoding-server/docs/zh.md)：把 draft-verify 做成服务。

### 延伸关键词
`multi-token prediction` · `sequential MTP` · `parallel MTP heads` · `teacher forcing` · `shared embedding / output head` · `speculative decoding` · `acceptance rate` · `Medusa heads` · `EAGLE-3` · `MoE` · `DeepSeek-V3`
