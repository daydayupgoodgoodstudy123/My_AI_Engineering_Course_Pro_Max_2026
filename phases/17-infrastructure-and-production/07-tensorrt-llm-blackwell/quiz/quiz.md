# 测验 · 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4（Hardware-Specialized Inference Compilation — FP8 and NVFP4 on Blackwell）

> **阶段 17 · 基础设施与生产 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义是质量很差的机器翻译（例如把 Hopper 译成"霍伯号"、把 Dynamo 译成"迪纳摩"），阅读时请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | "每美元多少 token"由四层选择叠加决定 | 硬件代际（Hopper H100/H200 vs Blackwell B200/GB200）× 精度（BF16 → FP8 → NVFP4）× 服务引擎（vLLM / SGLang / TRT-LLM）× 编排（普通 / disaggregated / Dynamo） |
| 2 | 讲义的头条数字 | 讲义："$0.012 per million tokens on a 120B model"（GB200 NVL72 + Dynamo）对比 H100 + vLLM 约 $0.09/M，约 **7 倍**经济差距；HGX B200 + TRT-LLM 约 $0.02/M |
| 3 | 为什么 KV cache 守在 FP8 | K/V 数值动态范围很宽，量化到 FP4 会让分布尾部丢失、attention 分数崩塌；FP8 的指数位提供所需的范围 |
| 4 | 典型 Blackwell 精度配置 | 权重 NVFP4、激活 NVFP4、KV cache FP8、attention 累加器 FP32（保证 softmax 稳定） |
| 5 | NVFP4 = 4-bit microscaling | 每个小 block 有自己的 scale factor，不同 block 能覆盖不同的动态范围，避免单一 per-tensor scale 的精度损失 |
| 6 | TRT-LLM 利用的 Blackwell 特性 | Day-0 FP4 权重（免 AWQ/GPTQ 转换）、MTP（集成的 speculative decoding 草稿）、disaggregated serving、NVLink 5 all-to-all（MoE 专家通信延迟降 3 倍）、硬件加速的 NVFP4/MXFP8 scale 处理 |
| 7 | decode 是 memory-bound | 单流 decode 每个 token 要把（激活的）权重从 HBM 读一遍：`tok/s ≈ HBM 带宽 / 每 token 读取字节数`；所以降低精度 = 直接提速 |
| 8 | FP4 的质量代价 | 推理/数学/长上下文代码生成会明显退化；常见折中是 FP8 权重 + FP4 激活，或在 H200 上全程 FP8；**上线前必须在自己的 eval set 上验证** |
| 9 | NVIDIA 锁定是核心取舍 | TRT-LLM 只能跑在 NVIDIA GPU 上、需针对具体 SKU 编译；多供应商战略下这一层不可用，只能用 vLLM 覆盖混合硬件 |
| 10 | 2026 实操配方 | 年推理账单巨大时把成本主导的负载迁到 Blackwell + TRT-LLM + Dynamo；实验层留在 H100 + vLLM 保持迭代速度 |

### 核心技能（能动手做到）

- [ ] 给定参数量和精度，算出权重显存（`params × bits / 8`）与 KV cache 显存（`层数 × 2 × KV 头数 × head_dim × 序列长度 × 字节数`）
- [ ] 用 memory-bound 模型估算单流 decode 的 tok/s，并换算成 $/M tokens
- [ ] 把"7 倍差距"拆成带宽、精度、MTP、disaggregation、GPU 单价几个因子，并能指出本节代码里 14x → 7x 实际是怎么来的
- [ ] 指出本节代码的建模简化（batch = 1、KV 不计入带宽、层数启发式公式）及其对结论的影响
- [ ] 为一个工作负载判断"是否值得为 7 倍差距接受 NVIDIA 锁定"，并给出质量验证与退出策略
- [ ] 说清 FP8 / NVFP4 / MXFP8 各自适用于权重、激活、KV cache 中的哪一部分以及原因

---

## 二、基础自测（选择题）

**Q1.** 讲义认为在 Blackwell 上即使权重已经是 NVFP4，KV cache 仍应保持 FP8，主要原因是：

- A. K/V 的数值动态范围很宽，FP4 会丢掉分布尾部、导致 attention 分数崩塌，FP8 的指数位能覆盖这个范围
- B. FP8 比 FP4 占用更少的显存
- C. NVLink 5 只能传输 FP8 数据
- D. 目前没有任何引擎支持 FP4 的矩阵乘

**Q2.** 本节代码 `decode_throughput(active_b, stack)` 计算单 GPU 的 tok/s。下面哪个 `Stack` 字段的取值**完全不会**影响它的结果？

- A. `hbm_bw_tbs`
- B. `weight_bits`
- C. `mtp_factor`
- D. `kv_bits`

**Q3.** 按本节代码的 memory-bound 模型，GPT-OSS-120B（激活 36B 参数）在 "H100 + FP8 + vLLM"（3.35 TB/s，权重 8 bit，无 MTP、无 disaggregation）上的单流 decode 速度约为：

- A. 47 tok/s
- B. 93 tok/s
- C. 186 tok/s
- D. 1,280 tok/s

**Q4.** 在本节代码的输出里，B200 + NVFP4 + TRT-LLM 相比 H100 + FP8 + vLLM，tok/s 高约 13.8 倍，而 $/M tokens 只便宜约 7.2 倍。这个"折半"在代码里**实际**来自：

- A. 真实流量下的调度开销（"real-traffic alpha"）
- B. KV cache 仍是 FP8，抵消了一半收益
- C. B200 每 GPU 小时价格（$4.80）约是 H100（$2.50）的 1.92 倍
- D. MoE 的 all-to-all 通信开销

**Q5.** 讲义给出的"典型 Blackwell 配置"是：

- A. 权重 FP8、激活 FP8、KV cache FP4、累加器 BF16
- B. 全部 BF16，靠 TRT-LLM 的 kernel 优化取胜
- C. 权重 INT4（AWQ）、激活 FP16、KV cache INT8
- D. 权重 NVFP4、激活 NVFP4、KV cache FP8、attention 累加器 FP32

**Q6.** "Day-0 FP4 weights" 指的是：

- A. 模型提供方直接发布 FP4 权重，TRT-LLM 直接加载，不需要再做 AWQ / GPTQ 之类的训练后转换
- B. 模型在训练第 0 天就用 FP4 从头训练
- C. TRT-LLM 在启动当天自动把 BF16 权重量化成 FP4
- D. 只在 GPU 第一次上电时有效的一种缓存格式

**Q7.** 讲义中 NVLink 5 的 all-to-all 通信原语"cut ... latency by 3x vs Hopper"，它主要加速的是：

- A. prefill 阶段的 attention 计算
- B. 模型权重从磁盘加载到 HBM
- C. MoE 模型把 token 路由到不同专家 GPU 的通信
- D. KV cache 的 FP8 量化

**Q8.** 某团队把推理型模型的权重转成 NVFP4 后，MATH 基准掉了 3 分。最符合讲义建议的做法是：

- A. 照常上线，7 倍的成本优势足以抵消质量损失
- B. 质量优先时退回 FP8 权重（可保留 FP4 激活）或在 H200 上全程 FP8；成本优先时用领域内数据做 per-block 校准，并在 eval set 上复验
- C. 关闭 MTP，因为 speculative decoding 会降低准确率
- D. 把 KV cache 也降到 FP4，以换回带宽重新平衡

---

## 三、动手 / 代码题

**Q9.** 本节代码对 GPT-OSS-120B（36B 激活）给出 "H100 + FP8 + vLLM" 为 **$7.4627/M tokens**，而讲义说 H100 + vLLM 约 **$0.09/M**，相差约 83 倍；GB200 行 $0.8611/M 对讲义的 $0.012/M 也差约 72 倍。

```python
def decode_throughput(active_b: float, stack: Stack) -> float:
    bytes_per_token = active_b * 1e9 * stack.weight_bits / 8
    raw_tokens_per_s = stack.hbm_bw_tbs * 1e12 / bytes_per_token
    return raw_tokens_per_s * stack.mtp_factor * stack.disagg_factor
```

1. 这个公式隐含了什么服务场景？为什么绝对数值和讲义差两个数量级？
2. 改写一个 `decode_throughput_batched(active_b, stack, batch, kv_gb_per_seq)`：一次 decode step 读一遍权重，再为 batch 内每条序列各读一遍它的 KV cache。
3. 用你的函数计算 batch = 64、8K 上下文时 H100 FP8 与 B200 两行的 $/M，两者的差距还是 7 倍左右吗？为什么？

**Q10.** 代码最后打印的 KEY FINDING：

```text
    1. HBM bandwidth (H100 3.35 TB/s vs B200 8.0 TB/s) ~2.4x
    2. NVFP4 weights (half the bytes per token)       ~2.0x
    3. MTP draft (~1.8x on accepted tokens)           ~1.8x
    4. Disaggregation (Dynamo: ~1.6-2.5x)             ~2.0x
  Product ~14x raw, closer to 7x after overhead and real-traffic alpha.
```

1. 按打印出来的四个因子相乘得多少？"~14x" 实际对应哪种取值？
2. 代码里"从 14x 到 7x"真正发生在哪一步？这与打印的解释是否一致？
3. 第 2 项 "half the bytes" 是相对哪个基线说的？如果相对 H100 + BF16，这一项应是多少？

**Q11.** 讲义练习 5："计算 405B 模型在 NVFP4 权重 + FP8 KV cache、128k 上下文下所需的 HBM，能否放进一个 GB200 NVL72 节点？"

```python
    weight_gb = params_b * stack.weight_bits / 8
    layers = 64 * (active_b / 35.0)**0.5
    kv_heads = 8
    head_dim = 128
    kv_gb = layers * 2 * kv_heads * head_dim * seq_len * (stack.kv_bits / 8) / 1e9
```

1. 用代码的公式算出权重和单条序列的 KV cache。
2. 代码对 405B 推出的层数是多少？Llama 3.1 405B 实际是 126 层（KV 头 8、head_dim 128），用真实形状重算 KV cache。
3. 单张 B200（代码中 192 GB）放得下吗？一个 NVL72（72 张）呢？代码里的 `fits` 判断还忽略了什么？

**Q12.** 讲义练习 2：某客户每年在 H100 + vLLM 上花 $2M。假设迁移到 Blackwell + TRT-LLM 后单位成本降为 1/7。

1. 年节省多少？
2. 若一次性迁移的工程成本为 E、每张 B200 的采购价为 P（均为未知参数），写出"12 个月内回本"时最多能买多少张 GPU 的不等式；再代入一组**假设值** E = $300K、P = $40K 算一下。
3. 按 `outputs/skill-trtllm-blackwell-advisor.md` 的规则，年支出低于多少时应直接拒绝迁移？

---

## 四、面试高频题

**Q13.**（基础必考）为什么说 LLM 的 decode 阶段是 memory-bound？降低权重精度为什么能近似线性地提升 decode 速度？这个结论在什么情况下不成立？

**Q14.**（原理深挖）FP8、NVFP4、MXFP8 有什么区别？为什么权重和激活可以用 4-bit microscaling，而 KV cache 和 attention 累加器不能？

**Q15.**（工程实践）你的公司年推理账单约 $5M，全部跑在 H100 + vLLM 上。CTO 问"要不要上 Blackwell + TRT-LLM"，你会如何评估并给出建议？

**Q16.**（场景设计）设计一个"两层"推理基础设施：既要享受 Blackwell 的成本优势，又要保留模型迭代速度和多供应商的退路。

**Q17.**（追问型）面试官问："你说 Blackwell + TRT-LLM 便宜 7 倍，这个 7 倍是怎么来的？在我们的负载上能复现吗？"

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："KV cache needs FP8 ... because it stores attention keys and values that span a wide dynamic range. Quantizing KV to FP4 causes catastrophic accuracy loss — the tail of the distribution drops off and attention scores collapse."

- B 错：FP4 只有 FP8 一半的位宽，显存更小，不是保留 FP8 的理由。
- C 错：NVLink 传的是字节，与数据格式无关。
- D 错：Blackwell Tensor Core 恰恰原生支持 NVFP4 矩阵乘，权重和激活都用它。

### Q2 — 答案：D

`decode_throughput` 只用了 `active_b`、`weight_bits`、`hbm_bw_tbs`、`mtp_factor`、`disagg_factor`。`kv_bits` 只在 `hbm_footprint_gb` 中决定 KV 的**容量**，从不进入吞吐公式。也就是说，代码假设"每个 token 只读权重、不读 KV"——在 batch = 1、短上下文时近似成立，但长上下文或大 batch 时 KV 读取会成为带宽的大头（见 Q9）。A、B、C 都直接出现在公式里。

### Q3 — 答案：B

`bytes_per_token = 36e9 × 8 / 8 = 36 GB`，`3.35e12 / 36e9 ≈ 93.1 tok/s`（实际运行输出 93）。A（47）是 BF16 的结果（每 token 72 GB）；C 是把带宽或精度算错一倍；D（1,280）是 B200 行的结果（`8e12 / 18e9 × 1.8 × 1.6`）。

### Q4 — 答案：C

实际计算：tok/s 比 = `(8.0/3.35) × (8/4) × 1.8 × 1.6 = 2.388 × 2 × 2.88 ≈ 13.76`；GPU 单价比 = `4.80 / 2.50 = 1.92`；成本比 = `13.76 / 1.92 ≈ 7.16`，与输出 `7.4627 / 1.0417 = 7.16` 一致。代码中没有任何"调度开销"或"真实流量"系数，A 是打印文案里的说法，但不是代码的计算；B 错，`kv_bits` 不影响吞吐；D 代码完全没有建模通信。

### Q5 — 答案：D

讲义原文："Weights: NVFP4. Activations: NVFP4. KV cache: FP8. Attention accumulator: FP32 (softmax stability)." A 把 KV cache 降到 FP4，正是讲义说的"常见错误"；B、C 都不是讲义描述的 Blackwell 配置（C 是 Hopper 时代 AWQ 部署的常见形态）。

### Q6 — 答案：A

讲义："model providers ship FP4 weights directly; TRT-LLM loads without post-training conversion. No AWQ / GPTQ step for FP4." B 混淆了"发布格式"与"训练精度"；C 描述的是在线量化，恰好是 Day-0 想省掉的步骤；D 无此概念。

### Q7 — 答案：C

All-to-all 是 MoE 把 token 分发到各专家 GPU、再把结果收回的通信模式。讲义："NVLink 5 cut MoE expert communication latency by 3x vs Hopper. TRT-LLM's MoE kernels are tuned for this." A 是单卡计算；B 与 NVLink 无关（是冷启动问题，见第 10 节）；D 是数值格式问题。

### Q8 — 答案：B

讲义："Teams shipping reasoning models often use FP8 weights + FP4 activations as a compromise, or stick to H200 with FP8 throughout ... always validate task quality on your eval set before committing to NVFP4 weights." 练习 3 也要求给出"质量优先（保留 FP8 权重）"和"成本优先（用领域内数据校准）"两条路径。A 违背了 skill 文件的 hard reject；C 无依据，speculative decoding 在验证正确时不改变输出分布；D 是讲义明确反对的做法。

### Q9 — 参考答案

1. **隐含场景是 batch = 1 的单流 decode**：每生成一个 token，整份激活权重都被读一遍且只服务这一个请求。真实服务会用 continuous batching 同时服务几十上百个请求，一次读权重摊给整个 batch，吞吐提高一到两个数量级，所以讲义的 $0.09/M、$0.012/M 是"批量服务"的数字，而代码是"单请求"的数字。代码只适合看**相对**比例，不能看绝对 $/M。

2. 参考实现：

```python
def decode_throughput_batched(active_b, stack, batch, kv_gb_per_seq):
    weight_bytes = active_b * 1e9 * stack.weight_bits / 8     # 每个 step 读一次
    kv_bytes = batch * kv_gb_per_seq * 1e9                    # 每条序列各读自己的 KV
    steps_per_s = stack.hbm_bw_tbs * 1e12 / (weight_bytes + kv_bytes)
    return batch * steps_per_s * stack.mtp_factor * stack.disagg_factor
```

`kv_gb_per_seq` 取 `hbm_footprint_gb(120, 36, 8192, stack)[1]`（FP8 时约 1.09 GB，BF16 时约 2.18 GB）。

3. 实际计算结果（8K 上下文，`$/M = 价格 / (tok/s × 3600) × 1e6`）：

| 栈 | batch=1 | batch=16 | batch=64 |
|----|---------|----------|----------|
| H100 + FP8 + vLLM | 90 tok/s，$7.69/M | 1,003 tok/s，$0.69/M | 2,028 tok/s，$0.34/M |
| B200 + NVFP4 + FP8 + TRT-LLM | 1,207 tok/s，$1.10/M | 10,407 tok/s，$0.13/M | 16,815 tok/s，$0.079/M |

batch = 64 时差距从约 7 倍缩小到约 **4.3 倍**（0.3423 / 0.0793）。原因：权重读取被 batch 摊薄后，KV 读取成为主要带宽开销，而两边的 KV 都是 FP8，NVFP4 对这部分毫无帮助。这正说明"7 倍"依赖负载形态（batch、上下文长度），也解释了为什么生产里还要做 KV cache 压缩、前缀复用等优化。（注：这仍是玩具模型——忽略了算力上限、显存容量是否放得下 64 条序列，以及 MoE 在大 batch 下会触达更多专家。）

### Q10 — 参考答案

1. `2.4 × 2.0 × 1.8 × 2.0 = 17.28`，并不是 14。"~14x" 对应 disaggregation 取 1.6（B200 行的 `disagg_factor`）：`2.4 × 2.0 × 1.8 × 1.6 = 13.82`（精确值 `8/3.35 × 2 × 1.8 × 1.6 = 13.76`）。打印的第 4 项写 "~2.0x" 与乘积 "~14x" 自相矛盾。
2. 代码中 14x → 7x **完全来自 GPU 小时价格**：`cost_per_million_tokens` 用的是 `price_per_gpu_hour / tokens_per_hour`，B200 的 $4.80 是 H100 $2.50 的 1.92 倍，`13.76 / 1.92 = 7.16`。打印出来的 "after overhead and real-traffic alpha" 在代码中不存在对应计算，属于文案与实现不一致。
3. 第 2 项是相对 **H100 + FP8** 基线（8 bit → 4 bit）。若相对 H100 + BF16，权重字节数减为 1/4，这一项是 4 倍；所以 GB200 相对 H100 BF16 的成本比是 `14.9254 / 0.8611 ≈ 17.3` 倍，相对 H100 FP8 是 `7.4627 / 0.8611 ≈ 8.7` 倍。说"7 倍"时必须说明基线。

### Q11 — 参考答案

1. 权重：`405 × 4 / 8 = 202.5 GB`。KV（代码公式，128k = 131,072 token，FP8）：约 **58.4 GB**（已实际调用 `hbm_footprint_gb(405, 405, 131072, B200)` 验证）。
2. 代码层数 = `64 × sqrt(405 / 35) ≈ 217.7` 层，远超真实的 126 层——这个"按 70B 形状、用激活参数开平方缩放"的启发式在大 dense 模型上明显失真（对 70B 也给出 90.5 层，而 Llama 70B 实际为 80 层）。用真实形状：`126 × 2 × 8 × 128 × 131,072 × 1 B ≈ 33.8 GB`。
3. 单张 B200：仅权重 202.5 GB 已超过 192 GB，放不下，至少需要 2 张（还要给 KV、激活和运行时留余量）。一个 NVL72 有 `72 × 192 ≈ 13.8 TB`，轻松放下，甚至能容纳数百条 128k 序列的 KV。代码的 `fits` 判断 `(w + kv) <= s.hbm_gb` 只比较"权重 + 单条序列 KV"与单卡 HBM，忽略了激活、CUDA graph / 运行时开销、并发序列数和张量并行切分后的分布。

### Q12 — 参考答案

1. 新成本 `2M / 7 ≈ $286K`，年节省 `2M − 286K ≈ $1.714M`。
2. 12 个月回本条件：`N × P + E ≤ 1.714M`，即 `N ≤ (1.714M − E) / P`。代入假设值：`(1,714K − 300K) / 40K ≈ 35.4`，最多约 35 张。（P、E 是为计算举例而设的假设值，讲义未给出 GPU 价格；若改为租用，应把 P 换成 12 个月的租金。）还要注意：节省额本身是以"迁移后跑在这些 GPU 上"为前提的，若 7 倍差距需要 GB200 + Dynamo 全栈才能达到，GPU 数量和单价都要按实际方案重算。
3. skill 文件："If annual inference spend < $500K, refuse migration. The engineering cost does not amortize."；并要求回本期 > 18 个月时标记为 marginal，迁移工程量估计 10–30 engineer-weeks。

### Q13 — 参考回答要点

- **原因**：decode 每步只为每条序列生成 1 个 token，矩阵乘退化为矩阵-向量乘，算术强度（FLOPs / 字节）很低；GPU 大部分时间在等 HBM 把权重和 KV cache 送进来。
- **公式**：单流 `tok/s ≈ HBM 带宽 / 每 token 读取的字节`，每 token 读取约等于 `激活参数 × 每参数字节数`。BF16 → FP8 → NVFP4 让字节数减半再减半，tok/s 近似翻倍再翻倍（本节代码：120B MoE 在 H100 上 BF16 47 tok/s → FP8 93 tok/s）。
- **不成立的情况**：
  - 大 batch / 长上下文时 KV 读取占主导，只量化权重收益递减（见 Q9）；
  - batch 足够大进入 compute-bound 区间，此时需要硬件 FP4/FP8 Tensor Core 提供更高 FLOPs 才能继续提速；
  - 反量化开销没有被 kernel 融合掉（例如在不支持该格式的老 GPU 上"软件反量化"），反而可能更慢。
- 加分点：MoE 在 batch = 1 时只读激活专家，但大 batch 下不同 token 路由到不同专家，读取量向"总参数"靠拢。

### Q14 — 参考回答要点

- **FP8**：8-bit 浮点，有指数位，动态范围大，适合数值跨度大的张量——KV cache、attention 相关计算。
- **NVFP4**：NVIDIA 的 4-bit microscaling 浮点格式；每个小 block 自带 scale factor，让不同 block 覆盖不同的数值范围，弥补 4 bit 本身动态范围太小的问题。讲义：用于权重与激活。
- **MXFP8**：microscaling 版的 FP8，Blackwell Tensor Core 硬件加速其 scale 处理。
- **为什么权重/激活能用 FP4**：讲义："activations are small-range within a layer"；权重分布相对集中，再配合 per-block scale 可以控制误差。
- **为什么 KV / 累加器不能**：KV 数值跨度大，FP4 丢尾部会让 attention 分数崩塌；累加器需要 FP32 来保证 softmax 的数值稳定（大量小数相加时低精度会严重舍入）。
- 加分点（讲义未展开、属公开规格）：NVFP4 用 16 个元素为一个 block、FP8（E4M3）scale，另有一个 per-tensor FP32 scale；OCP 的 MXFP4 用 32 元素 block 和 2 的幂次（E8M0）scale——block 越小、scale 越精细，量化误差越小。
- 常见误区：以为"能 FP4 的地方都 FP4"就是最优；讲义把这称为"2026 年的常见错误"。

### Q15 — 参考回答要点

- **量化当前基线**：$/M tokens、年 token 量、GPU 利用率、负载类型（routine vs reasoning-heavy）、模型是 dense 还是 MoE。
- **估算收益**：按讲义的成本形态（H100 + vLLM ~$0.09/M → B200 + TRT-LLM ~$0.02/M → GB200 NVL72 + Dynamo ~$0.012/M）投影年节省；同时说明这个比例依赖 batch、上下文长度、MTP 接受率，要在**自己的流量回放**上压测确认。
- **估算成本**：10–30 engineer-weeks 的首次迁移、质量验证、GPU CapEx 或长期租约；算回本期，> 18 个月视为 marginal。
- **质量闸门**：每个转成 NVFP4 的模型都在 eval set 上对比；推理类负载先用 FP8 权重。
- **锁定风险**：是否已有 AMD/Intel GPU？有的话多供应商那一层继续 vLLM。退出策略：保留 H100 + vLLM 双栈、权重保持 HF/GGUF 可导出格式。
- **结论模板**：$5M/年远高于 $500K 门槛，若回本期 < 12 个月且质量验证通过，先迁移成本占比最高的 1–2 个模型，其余保留。
- 常见误区：只看"7 倍"头条数字，不说明假设的 token 量和基线（skill 文件的 hard reject 之一）。

### Q16 — 参考回答要点

- **成本层（生产主力）**：Blackwell（B200 / GB200 NVL72）+ TRT-LLM + Dynamo，权重 NVFP4（推理模型先 FP8）、KV FP8；承载流量最大、模型最稳定的负载。
- **迭代层（实验 + 长尾）**：H100/H200 + vLLM，新模型先上这里，快速评测、A/B，稳定后再编译进 TRT-LLM。讲义："Keep experimentation tier on H100 + vLLM for model iteration speed."
- **统一入口**：网关按模型/租户路由到不同层（见第 19 节 AI 网关），对上层隐藏引擎差异。
- **质量流水线**：每次 NVFP4 转换或 TRT-LLM 引擎重建都跑 eval set，设定回退阈值；用 shadow 流量验证（见第 20 节）。
- **退路**：权重保留标准格式，vLLM 层可随时扩容接管；新采购的非 NVIDIA 硬件只进入 vLLM 层。
- **观测**：两层统一的 TTFT/TPOT/goodput 指标（见第 08 节），用 $/M good tokens 比较两层。

### Q17 — 参考回答要点

- **来源拆解**（讲义 + 代码）：HBM 带宽 8.0 / 3.35 ≈ 2.4 倍；NVFP4 相对 FP8 每 token 字节减半 2 倍；MTP 约 1.8 倍；disaggregation 1.6–2.5 倍；吞吐合计约 14–17 倍，再除以 Blackwell 更高的 GPU 单价（代码中 1.92 倍）≈ 7–9 倍。
- **前提**：讲义说"The 7x number assumes this full stack"——FP4 权重 × MTP × disaggregated placement × cache-aware routing 缺一不可；还要求 NVFP4 质量可接受。
- **复现方法**：用自己的模型、真实流量分布（输入/输出长度、并发）做压测，比较 goodput 而非峰值吞吐；分别测 MTP 接受率、不同 batch 下的 $/M。
- **可能复现不了的原因**：负载以长上下文、大 batch 为主，KV 读取占比高（NVFP4 帮不上，见 Q9）；推理类任务 NVFP4 质量不过关只能用 FP8；MTP 接受率低；没有用 Dynamo / disaggregation。
- 加分点：指出头条数字来自特定基准（讲义提到 SemiAnalysis InferenceX、GPT-OSS-120B），而 benchmark 数字与生产数字之间总有差距。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：理解 vLLM 的批处理与 KV 管理，才能理解 TRT-LLM 在其之上多拿了什么。
- [阶段 10 · 11 Quantization：让模型装得下](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：量化的基本原理（讲义先修写成"阶段 10 · 13"，实际量化在第 11 节）。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：prefill/decode、memory-bound 的基础。
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../05-eagle3-speculative-decoding/docs/zh.md)、[阶段 10 · 18 Multi-Token 预测（MTP）](../../../10-llms-from-scratch/18-multi-token-prediction/docs/zh.md)：MTP 草稿加速的来源。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的形状与显存公式。

### 本节被哪些后续内容用到
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：用 goodput 而不是峰值吞吐来衡量"7 倍"。
- [阶段 17 · 09 生产环境中的 Quantization](../../09-production-quantization/docs/zh.md)：AWQ/GPTQ/GGUF/FP8/MXFP4/NVFP4 的选型。
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../17-disaggregated-prefill-decode/docs/zh.md)：本节"disaggregation bonus"的完整展开（讲义误写成第 20 节）。
- [阶段 17 · 28 自托管服务选型](../../28-self-hosted-serving-selection/docs/zh.md)：引擎与硬件的匹配。
- [阶段 17 · 02 Inference 平台经济性](../../02-inference-platform-economics/docs/zh.md)、[阶段 17 · 27 LLMs 的 FinOps](../../27-finops-llms/docs/zh.md)：把 $/M tokens 放进单位经济和成本归因。

### 延伸关键词
`TensorRT-LLM` · `NVFP4` · `MXFP8 / MXFP4` · `microscaling` · `FP8 KV cache` · `memory-bound decode` · `arithmetic intensity` · `MTP` · `NVIDIA Dynamo` · `disaggregated serving` · `NVLink 5 all-to-all` · `GB200 NVL72` · `InferenceX` · `MLPerf Inference` · `vendor lock-in`
