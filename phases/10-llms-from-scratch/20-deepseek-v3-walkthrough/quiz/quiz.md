# 测验 · DeepSeek-V3 架构详解（DeepSeek-V3 Architecture Walkthrough）

> **阶段 10 · 从零构建 LLM · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 不变的骨架 | V3 仍是自回归、pre-norm 的 decoder 堆叠：RMSNorm、SwiGLU、RoPE |
| 2 | 四项 DeepSeek 特有设计 | MLA（注意力/KV cache）、auxiliary-loss-free 负载均衡（MoE 路由）、MTP（训练目标 + draft）、DualPipe（训练调度） |
| 3 | MLA | K、V 先压到共享低秩潜向量 `c^{KV}`（`kv_lora_rank = 512`）再按头解压；KV cache 只存潜向量（外加 64 维解耦 RoPE key） |
| 4 | KV cache 对比 | 讲义：61 层 × 512 × 131072 × 2 字节 ≈ 7.6 GB；同层数 GQA（8 个 KV 头 × 128 维）≈ 30.5 GB，约 4× |
| 5 | MoE 结构 | 61 层中前 3 层为稠密 MLP（ff = 18432），其余 58 层为 MoE：256 个路由专家（ff = 2048）选 top-8，外加 1 个共享专家 |
| 6 | 无辅助损失的负载均衡 | 给每个专家一个 bias 加到路由分数上（只影响选谁、不影响门控权重）；过载就减 bias，欠载就加 bias，不引入额外 loss |
| 7 | 参数规模 | 总参数 671B（另有 14B MTP 模块），每 token 激活 37B，激活比约 5.5%（约 18×稀疏） |
| 8 | 稀疏度横向比较 | Mixtral 约 28%，Llama 4 Maverick 约 4.25%，V3 约 5.5%；稠密模型 100% |
| 9 | 谱系 | R1 = V3 架构 + 新的后训练配方（大规模 RL）；讲义预计 V4 保留 MLA + MoE + MTP 并加入 DSA |
| 10 | 读 config 推参数 | 只有把 MLA 的真实头维度（q/k 192 = 128 nope + 64 rope，v 128）与不共享的输出头算进去，才能复现 671B / 37B |

### 核心技能（能动手做到）

- [ ] 拿到 DeepSeek-V3 的 config，逐字段说出它对应哪个组件
- [ ] 手算单个专家（`3 × 7168 × 2048 ≈ 44M`）、一个 MoE 层（约 11.4B）、一个 MLA 注意力层的参数量
- [ ] 从 config 推出总参数约 671B、激活参数约 37B，并能解释本节计算器只得到 664.5B / 30.4B 的原因
- [ ] 计算 MLA、GQA、MHA 在 128K 上下文下的 KV cache，并正确处理解耦 RoPE key 的 64 维
- [ ] 解释 MLA 推理时"吸收（absorb）"上投影矩阵的原理，以及为什么 RoPE 需要解耦
- [ ] 用 what-if 变体（MLA rank、专家数、top-k）分析总参数、激活参数、KV cache 的变化方向

---

## 二、基础自测（选择题）

**Q1.** DeepSeek-V3 的 MLA 在推理时，每层每个 token 的 KV cache 存的是：

- A. 128 个头各自完整的 K 和 V
- B. 一个共享的低秩潜向量 `c^{KV}`（512 维），外加一个 64 维的解耦 RoPE key
- C. 8 个 KV 头的 K 和 V（GQA）
- D. 只存 Q，不存 K 和 V

**Q2.** 按讲义公式（只计 512 维潜向量，BF16），61 层、131,072 token 的 MLA KV cache 约为：

- A. 30.5 GB
- B. 488 GB
- C. 3.8 GB
- D. 7.6 GB

**Q3.** 关于 DeepSeek-V3 的 auxiliary-loss-free 负载均衡，正确的是：

- A. 给每个专家维护一个 bias，加到路由打分上用于 top-k 选择；训练中按负载调整——过载减小、欠载增大，不新增 loss 项
- B. 它完全取消了路由器，所有 token 随机分配到专家
- C. 它把负载不均衡的惩罚项加到总 loss 里，权重随训练衰减
- D. 它让每个专家处理的 token 数严格相等，不允许任何波动

**Q4.** 按讲义"Where DeepSeek-V3 sits"表格中的总参数/激活参数，**激活比例最低**的模型是：

- A. DeepSeek V3（37B / 671B）
- B. Mixtral 8x22B（39B / 141B）
- C. Llama 4 Maverick（17B / 400B）
- D. Qwen 2.5 72B（72B / 72B）

**Q5.** 关于 DeepSeek-V3 的 MLP 层结构，正确的是：

- A. 61 层全部是 MoE，每 token 激活 8 个专家
- B. 前 3 层是 MoE，后 58 层是稠密 MLP
- C. 前 3 层是稠密 MLP，后 58 层是 MoE；MoE 层中每个 token 经过 8 个路由专家 + 1 个共享专家
- D. 每层有 256 个共享专家和 1 个路由专家

**Q6.** DeepSeek-R1 与 DeepSeek-V3 的关系是：

- A. R1 使用与 V3 相同的架构，改变的是后训练配方（在可验证任务上做大规模 RL）
- B. R1 去掉了 MoE，改成稠密模型
- C. R1 把 MLA 换回了 GQA
- D. R1 是从零重新预训练的更大模型，参数量是 V3 的两倍

**Q7.** 把 `kv_lora_rank` 从 512 改成 256（其余不变），128K 上下文下 MLA KV cache（按代码口径）相对原来减少了多少？

- A. 25%
- B. 75%
- C. 88%
- D. 50%

**Q8.** 运行计算器的 "512 experts, top-8" 变体，总参数和激活参数分别如何变化？

- A. 总参数不变，激活参数翻倍
- B. 总参数约翻倍（664.5B → 1318.6B），激活参数几乎不变（30.4B → 30.5B）
- C. 两者都翻倍
- D. 两者都不变，只有 KV cache 变大

---

## 三、动手 / 代码题

**Q9.** 计算器的 MLA 注意力参数函数如下，`compute_components` 中 `head_dim = h // n_heads`：

```python
def mla_attention_params(hidden, n_heads, head_dim, kv_lora, q_lora):
    q_down = hidden * q_lora
    q_up = q_lora * (n_heads * head_dim)
    kv_down = hidden * kv_lora
    k_up = kv_lora * (n_heads * head_dim)
    v_up = kv_lora * (n_heads * head_dim)
    o_proj = (n_heads * head_dim) * hidden
    return q_down + q_up + kv_down + k_up + v_up + o_proj
```

DeepSeek-V3 的真实注意力维度是：每头 query/key = 128（不带位置的部分，nope）+ 64（RoPE 部分），每头 value = 128；`kv_a` 投影输出 `512 + 64`（潜向量 + 共享的 RoPE key）。

1. 代码中的 `head_dim` 等于多少？每层注意力算出多少参数？
2. 按真实维度重写这个函数，每层注意力是多少参数？（可忽略两个小的 RMSNorm，也可以计入）
3. 只修正注意力，总参数和激活参数各增加多少？还差的约 0.93B 来自哪里？

**Q10.** 讲义 "Parameter accounting" 一节写道：

> 58 MoE blocks: attention with MLA (~144M) + 256 experts each (30M apiece) + 1 shared expert (30M) + norm. Total ~7.95B per block ... 461B total for the 58 MoE blocks.
>
> Total active: roughly 26B core + 14B MTP (trained but not always run at inference) ≈ 37B.

代码最后又打印 "HEADLINE: total 671B published, this calculator hits ~476B-490B"。请指出这段文字中的至少三处错误，并用正确的数字重新给出"58 个 MoE 层的总参数"与"37B 激活参数"的构成。

**Q11.** 关于 KV cache：

1. 讲义说 MLA 存 "512 floats per token per layer, not 8 x 128 = 1024 floats"，而它下面的 GQA 公式是 `2 * 61 * 8 * 128 * 131072 * 2`。这两处是否一致？GQA 每层每 token 实际存多少个值？
2. 把解耦 RoPE key 的 64 维算进去，MLA 在 128K 上下文下的 KV cache 是多少？与 GQA(8×128) 相比是几倍？
3. 如果 V3 不用 MLA，而是 128 个头的标准 MHA（K 每头 192 维、V 每头 128 维），KV cache 是多少？
4. rank-256 变体的输出里写着 "MLA savings 88%"，这个 88% 是相对谁的？

**Q12.** 讲义练习 5：DeepSeek-V3 用 FP8 训练。

1. 671B 权重用 BF16 与 FP8 存储分别需要多少显存（按 1 GB = 10⁹ 字节）？
2. "FP8 训练 = 所有东西都用 FP8 存"这个理解对吗？训练时还需要存哪些高精度的状态？
3. 推理部署时，671B（FP8）权重放在 8 张 H200（每张 141 GB）上是否够？放在 8 张 H100 80GB 上呢？还要为什么预留显存？

---

## 四、面试高频题

**Q13.**（基础必考）请从输入到输出完整描述 DeepSeek-V3 的架构，并说出它相对 Llama 系列新增的四项设计各自解决什么问题。

**Q14.**（原理深挖）MLA 是怎么做到"KV cache 很小、但每个头仍然有独立的 K、V"的？推理时的"矩阵吸收"是什么意思？为什么 RoPE 不能直接加在压缩后的 K 上，而要单独解耦出一个 64 维的 RoPE key？

**Q15.**（原理深挖）MoE 为什么需要负载均衡？传统的辅助损失有什么问题？DeepSeek-V3 的无辅助损失方案具体怎么做，有没有完全不用辅助损失？

**Q16.**（工程实践）你要在自己的集群上部署 DeepSeek-V3 做 128K 长上下文服务，请估算权重显存、每 token 的 KV cache、单机能支撑的并发，并说明 MoE 推理与稠密模型推理在部署上的主要差异。

**Q17.**（追问型）为什么 DeepSeek 选择"671B 总参数、37B 激活"这么稀疏的配置？如果把专家数从 256 增加到 512（top-8 不变），理论上得到什么、付出什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

MLA 把 K、V 压缩到共享的低秩潜向量 `c^{KV}`（512 维），推理时只缓存它；为了兼容 RoPE，V3 额外缓存一个 64 维、所有头共享的 RoPE key，所以每层每 token 实际缓存 576 个值。讲义只提到了 512，漏了这 64 维（见 Q11）。A 是标准 MHA；C 是 GQA（讲义对比的基线）；D 不可能，注意力需要历史 K、V。

### Q2 — 答案：D

`61 × 512 × 131072 × 2 = 8,187,281,408 字节 ≈ 7.6 GiB`（代码用 1024 进制显示为 7.6GB）。A 是 GQA 基线；B 是 128 头 × 128 维的 MHA（同口径）；C 是 rank 256 的变体。

### Q3 — 答案：A

讲义："Per-expert bias terms are added to the router logits, adjusted during training by a simple rule: if expert `e` is overloaded, decrease `bias_e`; if underloaded, increase it. No extra loss term." 技术报告中这个 bias 只用于决定 top-k 选谁，门控权重仍由原始亲和度分数计算。B、D 错；C 描述的是传统辅助损失。补充：V3 并非完全没有辅助损失——它还保留了一个权重极小的序列级平衡损失，用来防止单条序列内的极端不均衡（见 Q15）。

### Q4 — 答案：C

计算（已用 Python）：Maverick `17/400 = 4.25%`；V3 `37/671 = 5.5%`；Mixtral 8x22B `39/141 = 27.7%`；Qwen 2.5 72B `100%`。注意讲义一边说 "DeepSeek-V3 is the sparsest frontier MoE model that has shipped open weights"，一边又列出了比例更低的 Llama 4 Maverick——两句话自相矛盾。更准确的说法是：在 V3 发布时（2024 年 12 月），它是最稀疏的开放权重前沿 MoE 之一。

### Q5 — 答案：C

config：`first_k_dense_layers: 3`、`num_hidden_layers: 61`，所以 3 个稠密层 + 58 个 MoE 层；MoE 层有 256 个路由专家选 top-8，另有 1 个共享专家对所有 token 生效。每 token 每个 MoE 层实际经过 9 个专家。A 忽略了前 3 个稠密层；B 颠倒；D 把共享专家与路由专家的数量搞反了。

### Q6 — 答案：A

讲义："R1 uses the same architecture. What changed is the post-training recipe (large-scale RL on verifiable tasks), not the pretraining architecture." B、C、D 都是捏造的变化。

### Q7 — 答案：D

KV cache 与 `kv_lora_rank` 成正比：7.6 GB → 3.8 GB，减少 50%（代码输出两次运行的 `KV cache BF16` 一栏可直接对比）。C（88%）是代码打印的 "MLA savings"，但那是 rank-256 MLA 相对 **GQA 基线**的节省，不是相对 rank-512 的节省；B（75%）是 rank-512 相对 GQA 的节省。代价是潜向量容量减半，每个头能从中解压出的信息更少（讲义练习 2）。

### Q8 — 答案：B

实测：`total params 1318.6B`、`active params 30.5B`。专家数翻倍让每个 MoE 层的专家参数从 `256 × 44M` 变成 `512 × 44M`，总参数几乎翻倍；但每个 token 仍只走 top-8 + 1 共享，激活参数只因路由器矩阵变大（`7168 × 512`）略增。A、C、D 都与输出不符。

### Q9 — 参考答案

1. `head_dim = 7168 // 128 = 56`。代入后每层注意力 `84,410,368 ≈ 84.4M`（代码输出 "attention / layer: 84.4M"）。56 是把 hidden 平均分给 128 个头的"标准 MHA 习惯"，但 MLA 的头维度与 hidden 无关。
2. 按真实维度（已用 Python 计算）：

```python
def mla_attention_params_v3(h=7168, H=128, q_lora=1536, kv_lora=512,
                            nope=128, rope=64, v_dim=128):
    q_a = h * q_lora                         # 7168 -> 1536
    q_b = q_lora * H * (nope + rope)         # 1536 -> 128 x 192
    kv_a = h * (kv_lora + rope)              # 7168 -> 512 + 64（潜向量 + 共享 RoPE key）
    kv_b = kv_lora * H * (nope + v_dim)      # 512 -> 128 x (128 + 128)，K_nope 与 V 的上投影
    o = H * v_dim * h                        # 128 x 128 -> 7168
    norms = q_lora + kv_lora                 # q_a / kv_a 后的两个 RMSNorm
    return q_a + q_b + kv_a + kv_b + o + norms
```

   结果为 **187,107,328 ≈ 187.1M**，是代码值的 2.2 倍（讲义写的 "~144M" 也不对）。
3. 61 层 × (187.1M − 84.4M) ≈ **+6.27B**，总参数和激活参数都增加这么多（注意力每层都激活）。剩下约 0.93B 来自**输出头**：V3 的 embedding 和 LM head 不共享权重（讲义"Weight-tied embeddings"的说法对 V3 不成立），而代码只算了一份 `vocab × h`。两项都修正后（另把 RMSNorm 改为每个 h 参数、加上路由 bias），实测得到：**总参数 671.03B、激活参数 37.55B**，与官方 671B / 37B 吻合。也就是说"671B 无法精确复现、差额来自各种结构性小参数"的说法并不成立——差额几乎全部来自头维度和不共享的输出头。

### Q10 — 参考答案

错误：

1. **单个专家不是 30M**：`3 × 7168 × 2048 = 44,040,192 ≈ 44M`（SwiGLU 三块矩阵）。
2. **每个 MoE 层不是 7.95B**：`256 × 44M = 11.27B`，加共享专家、注意力、路由器后约 11.5B（真实注意力）；代码输出 "moe block / layer: 11.4B"。58 层合计约 **667B**（代码口径 661B），而不是 461B。
3. **MLA 注意力不是 ~144M**：真实约 187M（Q9）。
4. **激活参数的加法逻辑错误**：37B 是主模型每个 token 的激活量，**不包含** MTP 模块；"26B + 14B MTP ≈ 37B"既算术不对（26 + 14 = 40），也概念不对。讲义中"每层激活 MLP ~260M"也偏低：9 个专家 × 44M = 396M。
5. **HEADLINE 过时**：代码实际输出 664.5B，不是"476–490B"；"差额来自 expert-specific biases、shared expert scaling"也不对（路由 bias 每层只有 256 个参数）。

正确构成（真实维度，已计算）：

| 组成 | 总参数 | 激活参数 |
|------|-------|---------|
| embedding + LM head | 2 × 0.927B = 1.85B | 1.85B |
| 61 层 MLA 注意力 | 61 × 187.1M = 11.41B | 11.41B |
| 3 个稠密 MLP | 3 × 396.4M = 1.19B | 1.19B |
| 58 层专家（256 路由 + 1 共享） | 58 × 257 × 44.04M = 656.5B | 58 × 9 × 44.04M = 22.99B |
| 路由器 + 各层 RMSNorm | ≈ 0.1B | ≈ 0.1B |
| **合计** | **≈ 671.0B** | **≈ 37.6B** |

可以看到激活参数中专家约占 23B、注意力约占 11.4B，而总参数几乎全是专家。MTP 模块（14B）另计。

### Q11 — 参考答案

1. **不一致**。GQA 每层每 token 要存 K 和 V：`2 × 8 × 128 = 2,048` 个值，不是 1,024；讲义下方的公式带了因子 2 是对的，上方的文字漏了 V。
2. 每层每 token 576 个值：`61 × 576 × 131072 × 2 字节 ≈ 8.58 GiB`。与 GQA(8×128) 的 30.5 GiB 相比约 **3.56×**（`2048 / 576`），而不是讲义说的 4×。
3. MHA（K 每头 192、V 每头 128）：`61 × 128 × (192 + 128) × 131072 × 2 ≈ 610 GiB`，单条 128K 序列就超过一个 8 卡节点的显存。这才是 MLA 真正的对比对象——MLA 把它压到约 1/71。
4. 88% 是 rank-256 MLA 相对**同一个 GQA(8/128) 基线**的节省（`1 − 3.8/30.5`），不是相对 rank-512 MLA 的节省（那是 50%）。代码的 `gqa_kv_cache_bytes_ref` 在所有变体中都是同一个基线。

### Q12 — 参考答案

1. BF16：`671e9 × 2 = 1,342 GB`；FP8：`671 GB`，节省一半（671 GB）。
2. 不对。FP8 训练指的是大部分 GEMM（矩阵乘）在 FP8 下计算、相应的激活以 FP8 缓存；但主权重（master weights）、权重梯度、优化器状态仍需较高精度（BF16/FP32），一些对精度敏感的模块（embedding、输出头、MoE 门控、归一化、注意力算子）也保留原精度。所以 FP8 训练的显存节省远小于"权重减半"这么简单；它的主要收益是 GEMM 吞吐与通信量。
3. 8 × 141 = 1,128 GB，能放下约 671 GB 的 FP8 权重（加上 MTP 模块约 685 GB），剩余约 440 GB 给 KV cache 和激活；8 × 80 = 640 GB，连权重都放不下，至少需要 2 个 H100 节点（或更激进的量化）。还要为 KV cache（每 token 约 68.6 KiB，见 Q16）、激活、通信缓冲与 CUDA graph 等预留显存。

### Q13 — 参考回答要点

- **骨架**：token embedding（129,280 × 7168）→ 61 个 pre-norm block → 最终 RMSNorm → LM head（不与 embedding 共享）。每个 block：RMSNorm → MLA → 残差；RMSNorm → MLP（前 3 层稠密 SwiGLU，其余 58 层 MoE）→ 残差。RoPE 位置编码。
- **四项新增**：
  - **MLA**（注意力层）：压缩 KV 为低秩潜向量，大幅降低 KV cache，解决长上下文推理的显存/带宽瓶颈。
  - **无辅助损失负载均衡**（MoE 路由）：用可调 bias 平衡专家负载，避免辅助损失对主任务的干扰。
  - **MTP**（训练目标）：额外预测更远的 token，训练信号更密；推理时可当 draft。
  - **DualPipe**（训练系统）：双向流水线 + 计算通信重叠，遮盖跨节点 all-to-all。
- **规模**：671B 总参数，37B 激活，14.8T token 预训练。
- 加分点：说出 256 路由专家 + 1 共享专家、top-8，以及 FP8 混合精度训练。

### Q14 — 参考回答要点

- **低秩压缩**：`c^{KV} = W^{DKV} h`（7168 → 512），各头的 K、V 由上投影得到：`k_i = W_i^{UK} c^{KV}`、`v_i = W_i^{UV} c^{KV}`。缓存只存 `c^{KV}`，各头仍有不同的 K、V。
- **矩阵吸收**：注意力分数 `q_iᵀ k_i = q_iᵀ W_i^{UK} c^{KV} = (W_i^{UKᵀ} q_i)ᵀ c^{KV}`，可以把 `W^{UK}` 合并进 Q 的投影，直接让 query 与潜向量做点积，无需显式解压 K；同理 `Σ a_j v_j = W^{UV} Σ a_j c_j`，`W^{UV}` 可合并进输出投影 `W^O`。这就是讲义练习 4 的答案。
- **为什么要解耦 RoPE**：RoPE 是与位置相关的旋转矩阵 `R_m`。若直接对解压后的 K 加 RoPE，分数变成 `q_iᵀ R_nᵀ R_m W^{UK} c`，`R` 夹在 `W^{UK}` 与 query 之间且随位置变化，无法预先合并，吸收失效。因此 V3 把每个头的 q/k 分成两部分：128 维不带位置的部分走压缩路径并可吸收；64 维 RoPE 部分单独计算，其中 RoPE key 由 hidden 直接投影得到、所有头共享，并且也要缓存（所以每 token 每层缓存 512 + 64）。
- **代价**：解压/吸收带来额外计算；但 decode 阶段是显存带宽瓶颈，少读 KV 换来的收益更大。
- 加分点：MLA 由 DeepSeek-V2 提出；query 也做了低秩压缩（`q_lora_rank = 1536`），主要为减少训练时的激活显存。

### Q15 — 参考回答要点

- **为什么要均衡**：路由坍缩会让少数专家过载（计算瓶颈、EP 下成为 straggler），其余专家训练不足、参数浪费。
- **传统辅助损失**：把负载不均衡度加入 loss。权重太小压不住，太大会干扰主任务梯度、损伤模型质量；还多一个敏感超参。
- **V3 的做法**：每个专家一个 bias `b_e`，选 top-k 时用 `s_e + b_e`，但门控权重仍用原始 `s_e`；每步结束后按负载调整 `b_e`（过载减 γ、欠载加 γ）。bias 不参与梯度，主 loss 不受干扰。
- **并非完全没有辅助损失**：V3 还保留一个权重极小的**序列级**平衡损失，防止单条序列内的极端不均衡；并采用节点受限路由（每个 token 最多发往 4 个节点）控制通信。讲义"Effect on the main loss: none measurable"是简化说法，技术报告的消融显示无辅助损失方案在多数基准上优于纯辅助损失方案。
- 加分点：V3 不做 token dropping（训练和推理都不丢 token）。

### Q16 — 参考回答要点

- **权重**：FP8 约 671 GB（含 MTP 约 685 GB）；BF16 约 1.34 TB。8 × H200（1,128 GB）单节点 FP8 可放下；8 × H100 80GB 不够，需要两节点或更低比特量化。
- **KV cache**：每层每 token 576 个 BF16 值 × 61 层 = **70,272 字节 ≈ 68.6 KiB/token**；单条 128K 序列约 8.6 GiB；若留 100 GB 给 KV cache，32K 上下文约可并发 43 条（已计算）。对比 GQA(8×128) 同层数每 token 约 244 KiB。
- **MoE 推理差异**：
  - 全部专家权重都要常驻显存，但每 token 只算 37B，计算量小、显存占用大；
  - 需要专家并行（EP），每层有 dispatch/combine 两次 all-to-all，延迟敏感；
  - 负载不均（热门专家）会造成 straggler，需要冗余专家/动态放置；
  - 大 batch 才能把每个专家的矩阵乘"喂饱"；常把 prefill 与 decode 分离部署，用不同的并行配置。
- **可选加速**：用 MTP 模块做 speculative decoding（讲义 80%+ 接受率）。

### Q17 — 参考回答要点

- **稀疏的理由**：训练与推理的计算量由激活参数决定（约 37B 的 FLOPs），而模型"知识容量"随总参数增长；在固定算力下，用更多专家 + 更低激活比例换取更好的"每激活 FLOP 质量"——讲义称这是 DeepSeek 的核心押注。细粒度专家（每个只有 2048 的中间维度）+ 共享专家让专家更专精、减少冗余。
- **512 专家、top-8 的 what-if**（计算器输出）：总参数 664.5B → 1318.6B，激活 30.4B → 30.5B。
  - 得到：更大的总容量与更细的专业分工，理论上同样的激活 FLOPs 可学到更多知识；
  - 付出：权重显存翻倍（FP8 约 1.3 TB），需要更大的 EP 组；每个专家分到的 token 减半，小 batch 下矩阵乘效率更低；路由更难均衡、all-to-all 更分散；训练时每个专家看到的数据也减半，可能训练不足。
- 加分点：对比 top-16 变体（激活 30.4B → 50.8B，计算与延迟显著上升），说明"总参数"与"激活参数"是两个独立旋钮。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 14 开放模型：架构详解](../../14-open-models-architecture-walkthroughs/docs/zh.md)：六个架构旋钮与读 config 算参数的方法。
- [阶段 10 · 17 原生稀疏 Attention（DeepSeek NSA）](../../17-native-sparse-attention/docs/zh.md)：DeepSeek 系注意力的下一步。
- [阶段 10 · 18 Multi-Token 预测（MTP）](../../18-multi-token-prediction/docs/zh.md)：V3 的 MTP 模块。
- [阶段 10 · 19 DualPipe 并行](../../19-dualpipe-parallelism/docs/zh.md)：V3 的训练调度。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：路由、top-k、负载均衡基础。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：理解 MLA 为何要解耦 RoPE。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 计算方法。

### 本节被哪些后续内容用到
- [阶段 10 · 21 Jamba——混合 SSM-Transformer](../../21-jamba-hybrid-ssm-transformer/docs/zh.md)：另一条压缩 KV cache 的路线（用 SSM 替换大部分注意力层）。
- [阶段 10 · 11 Quantization：让模型装得下](../../11-quantization/docs/zh.md)、[阶段 17 · 09 生产环境中的 Quantization](../../../17-infrastructure-and-production/09-production-quantization/docs/zh.md)：FP8 等低精度部署。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：部署 MoE/MLA 模型的服务引擎。
- [阶段 17 · 07 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4](../../../17-infrastructure-and-production/07-tensorrt-llm-blackwell/docs/zh.md)：低精度推理硬件。

### 延伸关键词
`MLA` · `kv_lora_rank / q_lora_rank` · `decoupled RoPE` · `weight absorption` · `fine-grained experts` · `shared experts` · `auxiliary-loss-free load balancing` · `node-limited routing` · `FP8 mixed precision` · `expert parallelism` · `DeepSeek-R1` · `DSA`
