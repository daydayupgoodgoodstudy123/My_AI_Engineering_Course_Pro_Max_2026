# 测验 · 开放模型：架构详解（Open Models: Architecture Walkthroughs）

> **阶段 10 · 从零构建 LLM · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 不变的骨架 | token embedding → N 个 decoder block（norm、自注意力、残差、norm、MLP、残差）→ 最终 norm → LM head；因果 mask + next-token 交叉熵 |
| 2 | 六个"旋钮" | LayerNorm→RMSNorm；学习式位置→RoPE（+YaRN/NTK）；GELU→SwiGLU/GeGLU；MHA→GQA/MQA/MLA；Dense→MoE；pre-norm 保持不变 |
| 3 | RMSNorm | `x / sqrt(mean(x²) + eps) * γ`：不减均值、没有 β，计算更省；每层两个 norm 只有 `2h` 个参数 |
| 4 | RoPE | 按位置把 Q、K 的每对维度旋转一个确定角度，没有可学习的位置表，配合 NTK/YaRN 可外推；Llama 3 把 `rope_theta` 从 1 万调到 50 万 |
| 5 | SwiGLU | `Swish(xW1) ⊙ (xV)` 再乘 `W2`，MLP 有 3 个矩阵（gate、up、down），每层参数 `3·h·ff`；参数对齐时 `ff = 8/3·h`，而 Llama 3 实际用 `3.5·h` |
| 6 | GQA / MQA / MLA | KV cache 只与 **KV 头数**有关：GQA 32/8 缩小 4 倍，MQA 缩小 `num_heads` 倍；MLA 把 K/V 压到共享低秩潜变量里缓存 |
| 7 | MoE | router 为每个 token 选 top-k 专家；总参数大、激活参数小：Mixtral 8x7B 约 47B/13B，DeepSeek-V3 约 671B/37B；但所有专家都要放进显存 |
| 8 | 从 config 算参数 | embedding `V·h`、注意力 `2h² + 2h·kv_heads·head_dim`、SwiGLU `3·h·ff`、norm；**别忘了不共享权重的 LM head** |
| 9 | KV cache 公式 | `2 × 层数 × KV 头数 × head_dim × 序列长度 × 字节数`；Llama 3 8B 在 128k、BF16 下约 17.2 GB，比 16 GB 的权重还大 |
| 10 | 选型直觉 | 单卡 80GB：8B/7B/9B 级；单节点 8×80GB：70B 级 dense；最大开放能力：接受 MoE 复杂度；长上下文：RoPE 缩放 + GQA/MLA |

### 核心技能（能动手做到）

- [ ] 拿到任意 HuggingFace `config.json`，逐字段说出它对应 GPT-2 结构中的哪一部分
- [ ] 手算 dense 模型的总参数量（含/不含 tied LM head），并解释与官方数字的差异
- [ ] 手算 MoE 模型的总参数与激活参数，并说出 router、shared expert、前几层 dense 的影响
- [ ] 按公式计算任意模型在给定上下文、精度下的 KV cache，并据此估算单卡/单节点能服务多少并发序列
- [ ] 读懂 `main.py` 的计算器，指出它在 LM head、MLA、位置 embedding、bias、单位上的简化
- [ ] 根据部署目标（显存、上下文、延迟）从 Llama / Mistral / Qwen / Gemma / Mixtral / DeepSeek 中做出有依据的选择

---

## 二、基础自测（选择题）

**Q1.** 关于 RMSNorm，下列哪一项是正确的定义？

- A. `(x − mean(x)) / sqrt(var(x) + eps) * γ + β`
- B. `x / sqrt(mean(x²) + eps) * γ`，不减均值、没有偏置 β
- C. `x / max(|x|) * γ`
- D. `(x − mean(x)) * γ`，只减均值不缩放

**Q2.** Llama 3 8B 有 32 个 Q 头、8 个 KV 头（GQA）。在层数、head_dim、上下文长度都不变的前提下，它的 KV cache 是同结构全 MHA 版本的多少？

- A. 1/32
- B. 1/8
- C. 1/2
- D. 1/4

**Q3.** 运行本节 `main.py`，`llama3-8b` 的 `total params` 输出为 **7.5B**，而 Llama 3 8B 的官方参数量约 8.0B。差距的主要来源是：

- A. 代码没有计入不与 embedding 共享权重的 LM head（`128256 × 4096 ≈ 525M`）
- B. 代码漏算了 RMSNorm 的参数
- C. 代码把 GQA 当成了 MHA，少算了 K/V 投影
- D. 代码用错了 head_dim（应为 64 而不是 128）

**Q4.** 关于 MoE 模型的"总参数"与"激活参数"，说法正确的是：

- A. 激活参数决定了服务时需要的显存，总参数决定每个 token 的计算量
- B. Mixtral 8x7B 的总参数正好是 8 × 7B = 56B
- C. Mixtral 8x7B 总参数约 47B、每 token 激活约 13B；每 token 的计算量接近激活参数规模，但全部专家权重都必须驻留显存
- D. MoE 中每个 token 会经过全部专家，再按 router 权重加权求和

**Q5.** Llama 3 8B 的 `hidden_size = 4096`、`intermediate_size = 14336`，MLP 使用 SwiGLU、无 bias。每层 MLP 的参数量是：

- A. 117.4M（`2 · h · ff`）
- B. 134.2M（`8 · h²`，即 GPT-2 式 4 倍 dense MLP）
- C. 58.7M（`h · ff`）
- D. 176.2M（`3 · h · ff`）

**Q6.** DeepSeek-V3 每 token 从 256 个路由专家中选 8 个，Mixtral 8x7B 从 8 个中选 2 个。关于"被激活的路由专家占比"，正确的是：

- A. DeepSeek-V3 约 3.1%（8/256），Mixtral 25%（2/8）；DeepSeek-V3 是更稀疏、更细粒度的专家划分
- B. 两者都是 25%
- C. DeepSeek-V3 约 31%，Mixtral 约 3%
- D. DeepSeek-V3 是 100%，因为它还有 shared expert

**Q7.** 关于 Llama 3 8B config 中的字段，下列说法正确的是：

- A. `num_key_value_heads = 8` 表示每个 KV 头的维度是 8
- B. `max_position_embeddings = 131072` 说明模型内部有一张 131072 行的可学习位置表
- C. `rope_theta = 500000.0` 是 RoPE 的基频；讲义称 Meta 把它从默认的 1 万提高到 50 万以利于长上下文外推
- D. `rms_norm_eps` 控制 RoPE 的旋转角度

**Q8.** 讲义写 Llama 3 8B 在 128k、BF16 下的 KV cache 是 **17.2 GB**，而 `main.py` 打印 **16.0GB**。原因是：

- A. 代码用的是 FP8，所以更小
- B. 两者字节数相同（17,179,869,184 字节）；代码的 `fmt_bytes` 每次除以 1024（实际是 GiB），讲义用 10⁹ 作为 GB
- C. 代码少算了一层
- D. 代码用 MLA 公式计算了 Llama 3

---

## 三、动手 / 代码题

**Q9.** `main.py` 对 `deepseek-v3` 输出 `total=665.9B`、`active=32.4B`，而讲义（以及 DeepSeek-V3 技术报告）给出的是 671B / 37B。阅读：

```python
def attention_params_per_layer(config: dict) -> int:
    h = config["hidden_size"]
    q_heads = config["num_attention_heads"]
    kv_heads = config["num_key_value_heads"]
    head_dim = h // q_heads
    if config.get("attention") == "mla":
        lora = config.get("kv_lora_rank", 512)
        return h * h + 2 * (h * lora + lora * q_heads * head_dim) + h * h
    ...
```

```python
    if config.get("attention") == "mla":
        latent = config.get("kv_lora_rank", 512)
        kv_cache_bytes = 2 * n_layers * latent * max_seq * 2
```

1. 找出导致参数量偏低的两个原因。
2. 已知 DeepSeek-V3 config 中 `q_lora_rank = 1536`、`kv_lora_rank = 512`、`qk_nope_head_dim = 128`、`qk_rope_head_dim = 64`、`v_head_dim = 128`、`num_attention_heads = 128`、`hidden_size = 7168`、`vocab_size = 129280`，LM head 不共享。请写出更准确的 MLA 每层参数公式，并重新计算总参数与激活参数。
3. MLA 的 KV cache 公式有什么问题？给出修正后的数值（BF16、131072 token）。

**Q10.** 代码对 `gpt2-small` 输出 `123.6M`（精确值 123,570,432），而第 04 节测验中 Hugging Face GPT-2 的真实参数量是 124,439,808。请逐项说明差在哪里，并用数字凑出差值。

**Q11.** 讲义练习 3：计算 Llama 3 405B（126 层、head_dim 128）在 128k 上下文下的 KV cache（BF16 与 FP8），并估算一台 8×H100（共 640GB）能同时服务多少条满长度序列。

注意：讲义模型表中把 405B 写成 "GQA (128/16)"，但第 04 节测验已指出 Llama 3 全系列都只有 **8 个 KV 头**，请按 8 计算，并说明如果按 16 算会差多少。

**Q12.** 讲义"Activation memory budget"一节给出经验公式：

```text
activation_mem ~ batch_size * seq_len * hidden_size * num_layers * bytes_per_element
```

并称 Llama 3 8B（batch 1、seq 8192、BF16、32 层、hidden 4096）"开 gradient checkpointing 时约 8 GB"。

1. 用这个公式实际算一遍，与讲义的数字对照，你发现了什么？
2. 讲义说这个公式"See `code/main.py` for the exact formulas"，但代码里并没有激活显存的计算。请为 `Breakdown` 增加一个 `activation_bytes(batch, seq)` 函数。
3. 讲义练习 4：若一半层使用 4096 窗口的 sliding-window attention，另一半是全注意力，总上下文 8k 时 KV cache 节省多少？写出一般公式。

---

## 四、面试高频题

**Q13.**（基础必考）从 GPT-2 到 Llama 3，Transformer 结构主要改了哪些地方？每一项改动的动机是什么？

**Q14.**（原理深挖）比较 MHA、MQA、GQA、MLA：它们的 KV cache 大小、模型质量和实现复杂度分别如何？MLA 为什么还需要一个"解耦的 RoPE key"？

**Q15.**（原理深挖）RoPE 相比 GPT-2 的学习式位置 embedding 好在哪里？`rope_theta`、NTK-aware 插值、YaRN 分别在解决什么问题？

**Q16.**（场景设计）你有一张 80GB 显卡，要上线一个 32k 上下文的对话服务，希望支撑约 20 个并发长会话。你会选哪个开放模型？请用 KV cache 公式做出量化论证，并说明不够时有哪些手段。

**Q17.**（追问型）MoE 既然"同样计算、更多参数"，为什么不是所有模型都用 MoE？部署 MoE 有哪些额外难点？DeepSeek-V3 的 shared expert 与"前 3 层 dense"起什么作用？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义：`RMSNorm(x) = x / sqrt(mean(x^2) + eps) * gamma`，"No mean subtraction. No bias."。A 是 LayerNorm；C、D 不是任何常用归一化。代码里对应的体现是 `layer_norm_params_per_layer`：RMSNorm 每层 `2h`（两个 γ），LayerNorm 每层 `4h`（两组 γ、β）。

### Q2 — 答案：D

KV cache ∝ KV 头数。全 MHA 有 32 个 KV 头，GQA 只有 8 个，`8/32 = 1/4`。讲义："Llama 3 8B uses GQA with 32 Q heads and 8 KV heads (G=8), so the KV cache shrinks 4x versus full MHA." 实测：128k 上下文下，MHA 版本为 64 GiB，GQA 版本为 16 GiB。A 是 MQA（1 个 KV 头）的情形；B 把"8 个 KV 头"误当成"缩小 8 倍"。

### Q3 — 答案：A

`analyze` 计算的是 `emb + n_layers × block + final_norm`，只有一份 `vocab × h` 的 embedding。Llama 3 8B 的 LM head 不与 embedding 共享，需要再加 `128256 × 4096 = 525,336,576`。实测加上后为 **8.030B**，与官方 8.0B 吻合。同样的修正让 Mistral 7B 从 7.11B 变为 7.24B、Llama 3 70B 从 69.5B 变为 70.55B、Qwen 2.5 72B 从 71.46B 变为 72.71B、Mixtral 从 46.57B 变为 46.70B。B 错：代码计算了 RMSNorm（每层 `2h`，加最终 `h`），只是量很小；C 错：`attention_scheme` 正确识别为 `GQA (32/8)`，K/V 投影按 8 个头计算；D 错：`4096 / 32 = 128` 是对的。

### Q4 — 答案：C

讲义："Mixtral 8x7B has 47B total parameters but activates only 13B per token"，"the expert memory still has to live somewhere (so serving needs more VRAM than a dense equivalent)"。A 把两者说反了。B 错：8 个专家共享注意力、embedding 等非 MLP 部分，只有 MLP 被复制 8 份，所以总数是 47B 而不是 56B（代码实测 46.6B，加 LM head 后 46.7B）。D 描述的是"软 MoE/dense 混合"，标准 top-k MoE 每个 token 只经过 k 个专家。

### Q5 — 答案：D

SwiGLU 有 gate（`h→ff`）、up（`h→ff`）、down（`ff→h`）三个矩阵：`3 × 4096 × 14336 = 176,160,768 ≈ 176.2M`，与代码输出 `mlp / layer : 176.2M` 一致。A 漏了 gate 矩阵（是非 SwiGLU 分支 `2 · h · ff` 的结果）；B 是 GPT-2 式 `ff = 4h` dense MLP 的参数量 `8h² = 134.2M`；C 只算了一个矩阵。

补充一处讲义自相矛盾：讲义说参数对齐时 SwiGLU 取 `ff = 8/3 · h`（4096 时为 10,923），但又说 Llama 3 的 `intermediate_size` "3.5x hidden -- SwiGLU math"。实际 `14336 / 4096 = 3.5`，MLP 参数是 `10.5h²`，比 GPT-2 式 `8h²` 多 31%——Llama 3 是**有意加大**了 MLP，而不是"参数对齐"的结果。

### Q6 — 答案：A

`8/256 = 3.125%`，`2/8 = 25%`。代码打印的 `active/total` 是另一个口径（含注意力、embedding 等共享部分）：Mixtral 27.37%、DeepSeek-V3 4.86%。讲义练习 2 写"from sparse (25%) to denser sparse (3%)"，"denser"的措辞容易误导——3% 是**更稀疏**；其要点是专家更多、更细，单位 FLOP 能调用的总容量更大。D 错：shared expert 只有 1 个，路由专家中仍只激活 8 个（加上 shared 共 9/257 ≈ 3.5% 的专家参与计算）。

### Q7 — 答案：C

讲义："`rope_theta`: RoPE base frequency. Meta scaled it from the default 10k to 500k for long-context extrapolation." A 错：它是 KV 头的**个数**，head_dim 由 `hidden_size / num_attention_heads = 128` 得到。B 错：RoPE 没有可学习的位置表，`max_position_embeddings` 只是训练/支持的上下文长度。D 错：`rms_norm_eps` 是 RMSNorm 分母中防止除零的常数。

### Q8 — 答案：B

`2 × 32 × 8 × 128 × 131072 × 2 = 17,179,869,184` 字节。讲义按 10⁹ 写成 17.2 GB；代码 `fmt_bytes` 循环除以 1024，得到 16.0 但标注为 "GB"，实际是 GiB。同理 GPT-2 Small 的 "36.0MB" 是 37,748,736 字节（37.7 MB）。估算显存时要统一单位：GiB 与 GB 相差约 7.4%（`2³⁰ / 10⁹ ≈ 1.074`），混用会让容量估算出现同等量级的误差。A、C、D 均与代码不符。

### Q9 — 参考答案

1. **两个原因**：
   - **没有计入 LM head**：DeepSeek-V3 不共享权重，少了 `129280 × 7168 = 926,679,040`。
   - **MLA 参数公式过于粗略**：`head_dim = h // q_heads = 56`，但 DeepSeek-V3 的 Q/K 每头是 `128（nope）+ 64（rope）= 192` 维、V 每头 128 维；代码也没有 Q 的低秩压缩（`q_lora_rank = 1536`）和解耦 RoPE key。代码算出每层注意力 117.4M，真实约 187.1M。
2. **更准确的 MLA 每层参数**（忽略极小的 norm）：

```python
def mla_params(h=7168, n=128, q_lora=1536, kv_lora=512, d_nope=128, d_rope=64, d_v=128):
    q_a  = h * q_lora                          # 下投影 Q
    q_b  = q_lora * n * (d_nope + d_rope)      # 上投影 Q（含 rope 部分）
    kv_a = h * (kv_lora + d_rope)              # 下投影到 c_KV + 共享 rope key
    kv_b = kv_lora * n * (d_nope + d_v)        # 从 c_KV 上投影出每头 K_nope 与 V
    o    = n * d_v * h                         # 输出投影
    return q_a + q_lora + q_b + kv_a + kv_lora + kv_b + o   # 中间两个是 q/kv 的 norm
```

   每层 187,107,328，比代码多 69,666,816，61 层共多 4,249,675,776。加上 LM head 后（已用 Python 计算）：
   - 总参数：`665.85B + 0.93B + 4.25B ≈ 671.0B`
   - 激活参数：`32.38B + 0.93B + 4.25B ≈ 37.6B`
   与讲义的 671B / 37B 吻合。（这里不含 DeepSeek-V3 发布权重中额外的 MTP 模块。）
3. **KV cache 问题**：代码写 `2 * n_layers * latent * ...`，开头的 `2` 是把 K、V 当成两份分别缓存。MLA 的要点恰恰是 K 和 V **共享同一个**压缩潜变量 `c_KV`（512 维），另外再缓存一个所有头共享的 64 维 RoPE key。每 token 每层缓存 `512 + 64 = 576` 个值：`576 × 61 × 2 字节 × 131072 = 9,210,691,584 字节 ≈ 8.58 GiB`，而代码给出 15.2 GiB，高估约 1.8 倍。对比：同样 128k 下 Llama 3 8B（GQA 32/8）是 16 GiB，Llama 3 405B 是 63 GiB——这正是讲义"DeepSeek V3's KV cache is smaller than Llama 3 405B's ... that is MLA in action"的含义（注意：脚本里**并没有** 405B 的 config，讲义"Use It"中这句比较无法直接从输出中看到）。

### Q10 — 参考答案

| 差异项 | 计算 | 数量 |
|-------|------|------|
| 学习式位置 embedding（代码未计入） | `1024 × 768` | 786,432 |
| 注意力 bias（Q/K/V + 输出投影） | `12 × (3×768 + 768)` | 36,864 |
| MLP bias | `12 × (3072 + 768)` | 46,080 |
| 合计 | | **869,376** |

`123,570,432 + 869,376 = 124,439,808`，与 HF 值精确一致（已用 Python 验证）。代码的 GPT-2 计算还有一个口径问题：`analyze` 不知道 GPT-2 是 weight tying，但恰好也没加 LM head，所以"碰巧对了"；如果按上题给 Llama 补 LM head 时不区分 tied/untied，GPT-2 会被多算 38.6M（实测 162.2M）。正确做法是在 config 里加 `tie_word_embeddings` 字段并据此决定是否加 LM head。

### Q11 — 参考答案

每 token KV：`2 × 126 × 8 × 128 × 2 字节 = 516,096 字节`。

| 精度 | 128k 单序列 KV cache |
|------|---------------------|
| BF16 | `516,096 × 131,072 ≈ 67.6 GB`（63.0 GiB） |
| FP8 | 约 33.8 GB |

8×H100 共 640 GB：
- BF16 权重 `405B × 2 = 810 GB`，单节点**放不下**，必须量化或多节点。
- FP8 权重约 405 GB，剩余约 235 GB：FP8 KV 可放 `235 / 33.8 ≈ 6.9` → **6 条**满长度序列；BF16 KV 约 **3 条**。（未扣除激活与框架开销，实际更少。）

若按讲义表中的 16 个 KV 头计算，KV cache 翻倍为约 135 GB（BF16），FP8 KV 下只能服务 3 条——一个配置字段写错，容量估算就差一倍。这也是为什么讲义要求"从 config.json 读数"，而不是从二手表格读数。

### Q12 — 参考答案

1. `1 × 8192 × 4096 × 32 × 2 = 2,147,483,648 字节 ≈ 2.1 GB`，而讲义写"roughly 8 GB just for activations with checkpointing, 40 GB without"。按讲义自己的公式只有 2.1 GB，相差约 4 倍；讲义的 8 GB 可能隐含了其它系数（如每层保存多个张量），但正文没有说明。结论：这个"经验公式"只能当量级参考，具体系数取决于 checkpoint 策略与实现。
2. 参考实现：

```python
def activation_bytes(config: dict, batch: int, seq: int, bytes_per=2, factor=1.0) -> int:
    """开 gradient checkpointing 时，每层只保存一份 block 输入（factor=1）。"""
    return int(batch * seq * config["hidden_size"] * config["num_hidden_layers"] * bytes_per * factor)

# activation_bytes(CONFIGS["llama3-8b"], 1, 8192) -> 2,147,483,648
```

   把 `factor` 暴露出来，是为了诚实地表示"不同实现的系数不同"。
3. 一般公式（L 层、一半全注意力、一半窗口 W、总长 S）：

```text
KV = 2 · (L/2) · kv_heads · head_dim · bytes · (S + min(S, W))
节省比例 = (S − W) / (2S)       （当 W < S）
```

   S = 8192、W = 4096 时节省 `4096 / 16384 = 25%`。例如按 Gemma 2 9B 的公开 config（42 层、8 个 KV 头、head_dim 256）计算，BF16 下从 2.625 GiB 降到 1.97 GiB。上下文越长，节省比例越接近 50%。

### Q13 — 参考回答要点

- **RMSNorm 代替 LayerNorm**：去掉均值与 β，更省计算，效果相当（讲义引 Zhang & Sennrich 2019，约快 10%）。
- **RoPE 代替学习式位置**：没有长度上限的查找表，按旋转注入相对位置信息，可配合 NTK/YaRN 外推。
- **SwiGLU 代替 GELU MLP**：门控结构在同参数下 perplexity 更好；代价是 3 个矩阵。
- **GQA（或 MLA）代替 MHA**：缩小 KV cache，降低 decode 的显存带宽压力，是长上下文与高并发的前提。
- **MoE（顶端模型）**：同样每 token 计算量下获得更大容量。
- **pre-norm 保留**：深层训练稳定（Gemma 2 在 pre-norm 基础上又加了 post-norm）。
- 其它常见变化：去掉 bias、LM head 不再与 embedding 共享（Llama 3）、词表扩到 128K 级别。
- 加分点：说出"这些都是架构旋钮，学习率、数据配比、上下文长度属于训练配置"——讲义的区分。

### Q14 — 参考回答要点

| 方案 | KV 头 | KV cache（相对 MHA） | 质量 | 复杂度 |
|------|------|---------------------|------|-------|
| MHA | `n_heads` | 1 | 最好 | 最简单 |
| GQA | `G`（如 8） | `G / n_heads` | 接近 MHA | 低，主流 |
| MQA | 1 | `1 / n_heads` | 难任务略降 | 低 |
| MLA | 共享潜变量 + RoPE key | 更小（DeepSeek-V3 每层 576 个值，对比 GQA 8 头 × 128 × 2 = 2048） | 接近 MHA | 高 |

- **MLA 原理**：把 K、V 联合压缩成低秩潜变量 `c_KV` 缓存，计算时再上投影回每个头；上投影矩阵可以在推理时吸收进 Q 和输出投影，从而不必真正展开 K/V。
- **为什么要解耦 RoPE key**：RoPE 的旋转矩阵与位置有关，夹在 Q 与 K 之间，会让"把 K 的上投影吸收进 Q"失效。解决办法是让一小部分维度（64 维）单独承载 RoPE，这部分 key 不压缩、所有头共享并直接缓存。
- 加分点：本节代码把 MLA KV cache 当成 K、V 两份计算，高估约 1.8 倍（见 Q9）。

### Q15 — 参考回答要点

- **学习式位置的问题**：GPT-2 只有 1024 行位置表，第 1025 个位置没有向量，无法外推。
- **RoPE**：对 Q、K 的每对维度按 `位置 × 频率` 旋转，点积只依赖相对位置差；无参数，理论上任意长度可算。
- **`rope_theta`**：基频越大，低频分量转得越慢，长距离位置更不容易"转一圈"混淆，利于长上下文；Llama 3 从 1 万调到 50 万。
- **NTK-aware 插值 / YaRN**：推理时把超出训练长度的位置"压缩"回训练见过的角度范围，对不同频率分量采用不同缩放，从而在少量或无需微调的情况下把 8k 训练的模型扩到 128k，精度损失有限（讲义："a model trained on 8k context can stretch to 128k at inference with modest accuracy loss"）。
- 常见误区：以为 RoPE"天然无限外推"——不做缩放时，超长位置的注意力质量会明显下降。

### Q16 — 参考回答要点

- **候选**：Llama 3 8B / Mistral 7B 这一级（BF16 权重约 16 GB）。
- **算账**（Llama 3 8B，GQA 8 头、32 层、head_dim 128）：每 token KV `2 × 32 × 8 × 128 × 2 = 131,072 字节`（128 KiB）；32k 满长度一条约 4.3 GB。80 GB − 16 GB ≈ 64 GB → 约 **14.9 条**满长度会话，达不到 20 条。
- **手段**：
  - KV cache 量化到 FP8：约 29 条；
  - 权重 FP8/INT4 量化再腾出 8–12 GB；
  - PagedAttention：按实际长度分配，多数会话不会同时用满 32k；
  - 选择 sliding-window 或更少 KV 头的模型；前缀缓存共享 system prompt。
- **反面例子**：若选 MHA 结构的同尺寸模型，KV cache 是 4 倍，连 4 条满长度会话都放不下——讲义："For any model above ~13B parameters, GQA or MLA is effectively mandatory."
- 加分点：同时估算 decode 吞吐（显存带宽 / 每步读取的权重 + KV 字节数），说明并发数还受延迟目标约束。

### Q17 — 参考回答要点

- **为什么不都用 MoE**：
  - 显存按**总参数**计，服务成本高（Mixtral 47B 要按 47B 放显存，算力只用 13B）；
  - router 负载均衡难：专家冷热不均导致容量浪费或 token 被丢弃，需要辅助损失或 DeepSeek-V3 的无辅助损失均衡；
  - 小 batch 下每个专家分到的 token 少，矩阵乘效率低；
  - 需要 expert parallelism 与 all-to-all 通信，推理栈要支持（outputs 技能文件："MoE models on a serving stack without expert-parallel support" 是硬拒绝项）；
  - 微调与对齐时 router 的稳定性是独立的研究问题。
- **shared expert**：每个 token 都会经过的通用专家，承担共性知识，让路由专家更专门化。
- **前 3 层 dense**：浅层表示较通用，路由收益小且训练早期不稳定，用 dense MLP（`intermediate_size = 18432`）更稳；代码中的 `first_dense_layers` 正是为此而设。
- 加分点：能说出代码中 `active_moe_block = attn + expert_mlp × (top_k + shared) + router + norm` 的含义。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：GPT-2 基线结构与参数计数，本节的"diff"都以它为起点。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../05-scaling-distributed/docs/zh.md)：大模型训练的显存构成（权重、优化器、激活）。
- [阶段 10 · 12 Inference Optimization](../../12-inference-optimization/docs/zh.md)：KV cache 与 decode 瓶颈。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：RoPE 的数学。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：router 与 top-k 的基础。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的实现。

### 本节被哪些后续内容用到
- [阶段 10 · 11 Quantization](../../11-quantization/docs/zh.md)：选型时配合量化方案（outputs 技能文件要求同时给出量化选择）。
- [阶段 10 · 16 Differential Attention（V2）](../../16-differential-attention-v2/docs/zh.md)、[阶段 10 · 17 原生稀疏 Attention](../../17-native-sparse-attention/docs/zh.md)：注意力旋钮的新变体。
- [阶段 10 · 18 Multi-Token 预测（MTP）](../../18-multi-token-prediction/docs/zh.md)、[阶段 10 · 20 DeepSeek-V3 架构详解](../../20-deepseek-v3-walkthrough/docs/zh.md)：MLA、MoE、MTP 的完整拆解。
- [阶段 10 · 21 Jamba——混合 SSM-Transformer](../../21-jamba-hybrid-ssm-transformer/docs/zh.md)：讲义练习 5 所说的"第七个旋钮"候选。
- [阶段 17 · 28 自托管服务选型](../../../17-infrastructure-and-production/28-self-hosted-serving-selection/docs/zh.md)：把模型选型落到服务引擎与硬件。

### 延伸关键词
`config.json` · `RMSNorm` · `SwiGLU / GeGLU` · `RoPE` · `rope_theta` · `NTK-aware scaling` · `YaRN` · `GQA / MQA` · `MLA` · `kv_lora_rank` · `decoupled RoPE` · `MoE top-k routing` · `shared expert` · `active params` · `tie_word_embeddings` · `sliding-window attention`
