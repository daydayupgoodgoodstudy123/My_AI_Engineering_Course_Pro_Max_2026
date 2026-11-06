# 测验 · 生产环境中的 Quantization：AWQ、GPTQ、GGUF K-quants、FP8、MXFP4/NVFP4（Production Quantization — AWQ, GPTQ, GGUF K-quants, FP8, MXFP4/NVFP4）

> **阶段 17 · 基础设施与生产 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 格式选择是函数而非常量 | 量化格式 = f(硬件, 服务引擎, 负载)；不能照搬别人的选择 |
| 2 | GGUF Q4_K_M / Q5_K_M | 是**文件格式**，打包多种 K-quant 变体；CPU / 边缘的默认选择，走 llama.cpp / Ollama；讲义：在 vLLM 中只有约 93 tok/s（7B），"用错了引擎" |
| 3 | GPTQ | 带校准的训练后量化（4–8 bit）；Marlin kernel 比非 Marlin 快 2.6 倍，约 712 tok/s（7B）；**在 vLLM 中支持 LoRA**，是多 LoRA 场景的选择 |
| 4 | AWQ | Activation-aware：保护约 1% 最显著（salient）的权重；Marlin-AWQ 比朴素实现快 10.9 倍，约 741 tok/s（7B），INT4 中 Pass@1 最好；2026 年数据中心 GPU 的默认 |
| 5 | FP8 | 近乎无损、支持广泛（Hopper/Ada/Blackwell），质量不可妥协时（推理、医疗、代码）的安全默认 |
| 6 | MXFP4 / NVFP4 | Blackwell 的 4-bit microscaling；每 token 字节比 FP8 再减半；**尚不支持 LoRA**（2026 初），推理负载掉点明显，需逐模型验证 |
| 7 | 校准陷阱 | AWQ/GPTQ 需要校准集（常用 C4、WikiText）；领域模型用通用网页文本校准会保护错权重，HumanEval Pass@1 可掉几分；用几百条领域样本校准即可 |
| 8 | KV cache 陷阱 | 权重量化不改变 KV cache；"我的模型只有 4 GB 了"忘了生产 batch 下还有几十 GB 的 KV 和激活；HBM 要整体预算 |
| 9 | KV cache 量化是独立决策 | FP8 KV / INT8 KV 直接影响 attention 精度，"不是免费的午餐" |
| 10 | AWQ INT4 对推理有风险 | 讲义：MATH 掉约 3–5 分；推理类负载上 FP8 或 BF16，接受显存成本 |

### 核心技能（能动手做到）

- [ ] 给定参数量和格式，算出权重、KV cache（并发 × 上下文）、激活三部分显存，并判断能放进哪张 GPU
- [ ] 按讲义的 picking guide（CPU → GGUF；多 LoRA → GPTQ；推理 → FP8；常规 GPU 聊天 → AWQ；Blackwell 已验证 → NVFP4 + FP8 KV）为具体场景选格式
- [ ] 解释为什么"同样是 4 bit"，GGUF、GPTQ、AWQ 在 vLLM 里的吞吐差一个数量级（kernel 与引擎匹配）
- [ ] 计算在给定 GPU 上"权重放下之后还能并发多少条序列"
- [ ] 设计领域校准 + eval 验证 + 回滚的量化上线流程
- [ ] 指出本节代码的简化：层数启发式、吞吐只看权重位宽、`gpu_check` 不检查硬件是否支持该格式

---

## 二、基础自测（选择题）

**Q1.** 部署目标是笔记本电脑 CPU，引擎为 llama.cpp。讲义推荐的格式是：

- A. AWQ-Int4 + Marlin
- B. GGUF Q4_K_M（或 Q5_K_M）
- C. NVFP4
- D. FP8

**Q2.** 你在 vLLM 上服务一个基座模型和 30 个 LoRA 微调变体，GPU 为 H100。讲义的推荐是：

- A. NVFP4，因为每 token 字节最少
- B. GGUF Q5_K_M，因为质量最接近 BF16
- C. AWQ，因为 Pass@1 最好
- D. GPTQ-Int4 + Marlin，因为它在 vLLM 中支持 LoRA adapter

**Q3.** 一个医疗问答 + 多步推理的负载，质量不可妥协。讲义建议的默认精度是：

- A. FP8
- B. AWQ INT4
- C. GGUF Q4_K_M
- D. NVFP4 + FP8 KV

**Q4.** "AWQ 之后我的模型只有 4 GB 了"这句话的陷阱在于：

- A. AWQ 实际上并不压缩权重
- B. AWQ 和 vLLM 不兼容
- C. AWQ 只压缩权重；KV cache 和激活是独立的，生产并发下可能还有几十 GB
- D. AWQ 强制要求 INT8 KV cache

**Q5.** 一个代码模型用 C4 通用网页文本做 AWQ 校准，上线后 HumanEval 掉了几分。最可能的原因和修复是：

- A. 校准分布与部署领域不匹配，算法保护了"错误的"显著权重；改用几百条领域内样本重新校准并在 eval 上复验
- B. C4 数据太少，换成更大的通用语料即可
- C. AWQ 不支持代码模型，必须换成 GGUF
- D. Marlin kernel 有 bug，关掉 Marlin 即可

**Q6.** 讲义提到 GGUF 在 vLLM 中只有约 93 tok/s（7B），而 AWQ + Marlin 约 741 tok/s。对此最合理的解读是：

- A. GGUF 的量化精度太低，导致需要重算
- B. GGUF 文件太大，加载时间被算进了吞吐
- C. vLLM 有 bug，应该提 issue
- D. GGUF 不是为 GPU kernel 优化的格式，它的主场是 CPU / llama.cpp；在 vLLM 里用它是"用错了引擎"

**Q7.** 本节代码在"70B、并发 128、上下文 2048"场景下，只有一行被 `gpu_check` 判定为能放进 H100 80GB。这一行及其判定的问题是：

- A. AWQ-Int4 + Marlin；问题是没算激活
- B. FP8；问题是 FP8 在 H100 上没有硬件加速
- C. NVFP4 + FP8 KV（72.9 GB）；问题是 `gpu_check` 只比较容量，不检查硬件是否支持该格式，而 NVFP4 是 Blackwell 专属
- D. GGUF Q4_K_M；问题是 llama.cpp 不能用 GPU

**Q8.** 本节代码的 `relative_throughput` 对 GGUF Q4_K_M、GPTQ、AWQ、NVFP4 都给出 4.00x。下列说法正确的是：

- A. 这与讲义完全一致，四者吞吐确实相同
- B. 该函数只看 `weight_bits`（`16 / bits`），不考虑引擎/kernel 效率和 KV cache 读取，因此与讲义"GGUF 在 vLLM 约 93 tok/s、AWQ 约 741 tok/s"的差距相矛盾
- C. 该函数考虑了 KV 位宽，所以 NVFP4 + FP8 KV 应该更高
- D. 该函数计算的是显存占用比，而不是吞吐

---

## 三、动手 / 代码题

**Q9.** 讲义的"KV cache 陷阱"一节写道：

> For a 70B model with AWQ: Weights ~35 GB; KV cache at 128 concurrent × 2k context: ~20 GB; Activations ~5 GB; Total ~60 GB — fits on H100 80GB.

而代码对同一场景输出 `AWQ-Int4 + Marlin (vLLM)  35.0  68.7  3.5  107.2  H200 141GB`。

1. 代码的 KV 是如何算出 68.7 GB 的？（提示：`layers = 64 * (params_b / 70.0)**0.5`，`kv_heads = 8`，`head_dim = 128`，BF16）
2. 用 Llama 3 70B 的真实形状（80 层、8 个 KV 头、head_dim 128）重算 BF16 KV。
3. 讲义的"~20 GB、能放进 H100"结论是否成立？要让 AWQ 70B 在单张 H100 上服务 128 条 2k 序列，你会怎么做？

**Q10.** 讲义练习 1 与练习 5：

1. 给 `FORMATS` 增加一行 `Format("AWQ-Int4 + FP8 KV (vLLM)", 4, 8, "vLLM", "...")`，在 70B / 128 并发 / 2k 上下文下它的总显存是多少？`gpu_check` 给出什么？
2. 写一个函数 `max_concurrency(params_b, fmt, hbm_gb, ctx)`：放下权重和激活后，剩余 HBM 能容纳多少条序列的 KV？对 70B、2k 上下文、80 GB 的 H100，分别计算 BF16、AWQ（BF16 KV）、FP8、NVFP4 + FP8 KV 四行。
3. 什么时候值得把 AWQ 权重与 FP8 KV 组合，什么时候应该保留 BF16 KV？

**Q11.** `relative_throughput` 只看权重位宽：

```python
def relative_throughput(fmt: Format) -> float:
    return 16 / fmt.weight_bits
```

把它改成"KV 感知"的版本：一个 decode step 读一遍权重，再读一遍 batch 内所有序列的 KV（假设每条序列都是满 2k 上下文），吞吐 ∝ `并发数 / (权重字节 + KV 字节)`。以 BF16 为 1.0，计算 70B / 128 并发 / 2k 时 AWQ（BF16 KV）、FP8、NVFP4 + FP8 KV 的相对吞吐，并解释结果。

**Q12.** 按讲义的 2026 picking guide 和 `outputs/skill-quantization-picker.md` 的拒绝规则，写一个 `pick_format(hardware, engine, workload, needs_lora=False, nvfp4_validated=False, can_run_eval=True)`，并给出以下 6 个用例的输出：

1. CPU + llama.cpp + 聊天
2. H100 + vLLM + 推理
3. H100 + vLLM + 聊天 + 需要多 LoRA
4. B200 + TRT-LLM + 聊天 + NVFP4 已验证
5. B200 + TRT-LLM + 聊天 + NVFP4 未验证
6. H100 + vLLM + 普通聊天

---

## 四、面试高频题

**Q13.**（基础必考）AWQ 和 GPTQ 都是 4-bit 训练后量化，它们的核心思路有什么不同？为什么在 vLLM 中选择它们时，"kernel"比"算法"更重要？

**Q14.**（原理深挖）为什么权重量化能显著提升 decode 吞吐，却对 prefill 帮助有限？KV cache 量化为什么"不是免费的午餐"？

**Q15.**（工程实践）你有一个 7B 代码模型要上线到 GPU 集群（讲义练习 2）。你选什么格式？如果你对质量容忍度判断错了，恢复路径是什么？

**Q16.**（场景设计）公司要在 H100 集群上为 40 个企业客户各自提供 LoRA 微调的 70B 模型，同时有一个面向内部数据分析的推理型负载。请设计量化方案和上线流程。

**Q17.**（追问型）同事说："我们把 70B 量化成 INT4，只要 35 GB，一张 H100 就能扛住全部流量。"你怎么回应？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："CPU/edge serve: GGUF Q4_K_M. Done." GGUF 是 llama.cpp 的原生格式，llama.cpp"is by far the fastest CPU inference engine"。A 依赖 GPU 的 Marlin kernel；C 需要 Blackwell Tensor Core；D 在 CPU 上没有硬件加速。skill 文件还规定："If the engine is llama.cpp, refuse any format other than GGUF."

### Q2 — 答案：D

讲义："GPTQ-Int4 supports LoRA adapters in vLLM. If you are serving a base model plus 10-50 fine-tuned variants (each as a LoRA), GPTQ is your path." A 错，"NVFP4 does not support LoRA yet as of early 2026"，且 H100 不支持 NVFP4；B 是 CPU 格式；C 的 AWQ 是"无 LoRA 需求"时的默认。

### Q3 — 答案：A

讲义："FP8 is the safe 2026 default when quality is non-negotiable (reasoning, medical, code-gen)"；"AWQ INT4 loses ~3-5 points on MATH. For reasoning-heavy workloads, ship FP8 or BF16." B、C 都是 INT4 级别；D 讲义明确说推理负载上 FP4 掉点明显，必须先验证。

### Q4 — 答案：C

讲义："AWQ shrinks weights to 4 bits. KV cache is separate and stays at FP16/FP8 ... Naively 'I quantized my model to 4 GB' forgets the other 30-50 GB. Budget HBM holistically." A、B 与事实不符；D 混淆了权重量化与 KV 量化——讲义强调二者是独立决策。

### Q5 — 答案：A

讲义："For domain models (code, medical, legal), calibrating on generic web text lets the algorithm make wrong decisions about which weights to protect. Pass@1 on HumanEval can drop several points. The fix: calibrate on in-domain data. Hundreds of domain samples is usually enough." B 错，问题是分布而不是数量；C 错，AWQ 可以用于代码模型；D 错，kernel 只影响速度，不影响数值。

### Q6 — 答案：D

讲义："Throughput penalty in vLLM: ~93 tok/s on 7B — the format is not optimized for GPU kernels. Use GGUF when the deployment target is CPU/edge." 代码 KEY FINDING 5 也说："~93 tok/s in vLLM is not a bug, it is the wrong engine." A 错，Q4_K_M 质量接近 BF16，与吞吐无关；B 错，吞吐不含加载时间；C 错，格式与引擎不匹配不是 bug。

### Q7 — 答案：C

实际输出中只有 `NVFP4 + FP8 KV (TRT-LLM)  35.0  34.4  3.5  72.9  H100 80GB`。`gpu_check` 只按总容量依次与 80 / 141 / 192 比较，完全不看格式需要什么硬件；而 NVFP4 是"Blackwell aggressive"（`notes` 字段自己就写了），H100 没有 FP4 Tensor Core，也不能跑 TRT-LLM 的 NVFP4 kernel。A 错，AWQ 总量 107.2 GB 被判到 H200；B 错，H100 原生支持 FP8，FP8 行 107.9 GB 也被判到 H200；D 错，GGUF 行 107.2 GB，且讲义里 GGUF 的定位是 CPU。真正能在 H100 上做到 72.9 GB 的组合是"AWQ 权重 + FP8 KV"（见 Q10），代码里没有这一行。

### Q8 — 答案：B

`relative_throughput` 只有一行 `return 16 / fmt.weight_bits`，`engine`、`kv_bits` 都没参与。它表达的是"理想 memory-bound、只读权重、kernel 完美"的上限。讲义给出的实测数字（GGUF 在 vLLM 约 93 tok/s、GPTQ + Marlin 约 712、AWQ + Marlin 约 741）说明同为 4 bit，引擎与 kernel 能让吞吐差 8 倍。A 与讲义矛盾；C 错，`kv_bits` 不参与；D 错，函数注释明确是 decode 吞吐。

### Q9 — 参考答案

1. 代码层数 = `64 × sqrt(70/70) = 64`。每条序列 KV = `64 × 2 × 8 × 128 × 2048 × 2 B ≈ 0.537 GB`，× 128 并发 = **68.7 GB**（BF16，因为 AWQ 行 `kv_bits = 16`）。
2. 真实形状：`80 × 2 × 8 × 128 × 2 B = 327,680 B/token`，× `128 × 2048 = 262,144` token ≈ **85.9 GB**（BF16）；FP8 KV 约 42.9 GB。
3. **不成立**。讲义的"~20 GB"低估了约 3.4–4.3 倍（取决于用代码形状还是真实形状），"Total ~60 GB fits on H100"的结论也随之失效；代码本身的输出（107.2 GB → H200）就和讲义的这段说法矛盾。单张 H100 的可行方案：
   - KV 改为 FP8（代码形状下总量 72.9 GB，真实形状下约 35 + 42.9 + 3.5 ≈ 81 GB，仍偏紧）；
   - 降低并发（例如代码形状下 BF16 KV 最多约 77 条 2k 序列，见 Q10）；
   - 用 PagedAttention 按实际长度分配 KV（并非每条序列都用满 2k）；
   - 或者上 H200 / 两张 H100 做张量并行。
   这也正是讲义要传达的教训——"Budget HBM holistically"——只是讲义自己的示例数字算错了。

### Q10 — 参考答案

1. 实际运行：`weight 35.0 + kv 34.4 + act 3.5 = 72.9 GB`，`gpu_check` → `H100 80GB`。与 NVFP4 + FP8 KV 的显存完全相同，但这是 H100 真正能跑的组合。

2. 参考实现：

```python
def max_concurrency(params_b, fmt, hbm_gb, ctx):
    m1 = memory_breakdown(params_b, fmt, concurrency=1, ctx=ctx)
    free = hbm_gb - m1["weight"] - m1["act"]
    return max(0, int(free / m1["kv"]))
```

实际计算（70B、2k、80 GB）：

| 格式 | 权重 | 剩余 HBM | 每序列 KV | 最大并发 |
|------|------|---------|----------|---------|
| BF16 | 140 GB | 负数 | 0.537 GB | 0（放不下） |
| AWQ（BF16 KV） | 35 GB | 41.5 GB | 0.537 GB | 77 |
| FP8（W8 + KV8） | 70 GB | 6.5 GB | 0.268 GB | 24 |
| NVFP4 + FP8 KV | 35 GB | 41.5 GB | 0.268 GB | 154 |

有意思的是 FP8 只能并发 24 条——权重 70 GB 占掉了大部分显存。这说明"质量更安全的 FP8"在单卡 70B 上会严重限制并发，通常要配合多卡或 H200（141 GB 时 FP8 可并发约 251 条）。

3. AWQ + FP8 KV 适合：长上下文或高并发、KV 成为显存/带宽主导，且任务对 attention 精度不敏感（常规聊天、摘要），并已在 eval 上验证。保留 BF16 KV 适合：推理/长上下文检索类任务对 attention 精度敏感、或 eval 显示 FP8 KV 掉点（skill 文件："BF16 KV if attention accuracy is marginal; INT8 KV only after validation"）。

### Q11 — 参考答案

```python
def relative_throughput_kv(params_b, fmt, conc=128, ctx=2048):
    def tput(f):
        m = memory_breakdown(params_b, f, conc, ctx)
        return conc / (m["weight"] + m["kv"])   # 每 step 读一遍权重 + 全部 KV
    return tput(fmt) / tput(FORMATS[0])
```

实际计算（70B / 128 / 2k，代码的 KV 形状）：

| 格式 | 仅权重（原函数） | KV 感知 |
|------|----------------|--------|
| BF16 | 1.00x | 1.00x |
| AWQ（W4 + KV16） | 4.00x | **2.01x** |
| FP8（W8 + KV8） | 2.00x | **2.00x** |
| NVFP4 + FP8 KV | 4.00x | 3.01x |

解释：并发 128、2k 上下文时 KV 有 68.7 GB，比 AWQ 的 35 GB 权重还大，成为带宽大头。AWQ 只压了权重，KV 仍是 BF16，所以优势从 4 倍降到 2 倍，与 FP8 打平——而 FP8 质量风险更低。这就是讲义 KEY FINDING 1 "KV alone dwarfs weight savings" 的吞吐版本。（简化：假设每条序列都读满 2k 的 KV，忽略算力上限；真实情况下平均上下文更短时 AWQ 的优势会回升。）

### Q12 — 参考答案

```python
def pick_format(hardware, engine, workload, needs_lora=False, nvfp4_validated=False, can_run_eval=True):
    if not can_run_eval:
        return "REFUSE: no 1,000-sample eval -> no blind quantization"
    if engine == "llama.cpp" or hardware == "CPU":
        return "GGUF Q4_K_M (Q5_K_M if quality headroom is thin)"
    if workload in ("reasoning", "creative-marginal"):
        return "FP8 weights (+ FP8 KV after validation); refuse INT4"
    if needs_lora and engine == "vLLM":
        return "GPTQ-Int4 + Marlin"
    if hardware in ("B200", "GB200") and engine == "TRT-LLM":
        return "NVFP4 weights + FP8 KV" if nvfp4_validated else "FP8 (run per-block NVFP4 validation first)"
    return "AWQ-Int4 + Marlin"
```

实际运行输出：

```text
('CPU', 'llama.cpp', 'chat') -> GGUF Q4_K_M (Q5_K_M if quality headroom is thin)
('H100', 'vLLM', 'reasoning') -> FP8 weights (+ FP8 KV after validation); refuse INT4
('H100', 'vLLM', 'chat', True) -> GPTQ-Int4 + Marlin
('B200', 'TRT-LLM', 'chat', False, True) -> NVFP4 weights + FP8 KV
('B200', 'TRT-LLM', 'chat', False, False) -> FP8 (run per-block NVFP4 validation first)
('H100', 'vLLM', 'chat') -> AWQ-Int4 + Marlin
```

要点：**规则顺序很重要**——"不能做 eval 就拒绝"和"引擎决定格式"（llama.cpp → GGUF）放在最前；"推理负载 → FP8"要先于"多 LoRA → GPTQ"，否则推理 + LoRA 的组合会被错误地分到 INT4（若两者同时出现，应提示冲突：FP8 + LoRA 的支持情况需按引擎版本确认）。NVFP4 未验证时回退 FP8，而不是回退到 vLLM 专用的 Marlin-AWQ。真实决策还要输出显存预算、校准与回滚计划（skill 文件的 6 项产出）。

### Q13 — 参考回答要点

- **AWQ（Activation-aware Weight Quantization）**：观察激活的幅度，找出对输出影响最大的约 1% 显著权重通道，通过缩放保护它们（讲义："Protects the ~1% most-salient weights"），其余权重正常量化到 INT4。
- **GPTQ**：逐层做训练后量化，利用校准数据（近似二阶信息）在量化一部分权重后调整剩余权重以补偿误差。
- **共同点**：都需要校准数据，都是 weight-only INT4（推理时反量化后与 FP16 激活相乘）。
- **为什么 kernel 更重要**：INT4 的收益只有在 kernel 把"读 INT4 + 反量化 + 矩阵乘"融合好时才能兑现。讲义：Marlin-AWQ 比朴素实现快 10.9 倍、Marlin-GPTQ 比非 Marlin 快 2.6 倍，而同样 4 bit 的 GGUF 在 vLLM 中只有 93 tok/s。skill 文件也把"不说明 kernel 就报吞吐数字"列为 hard reject。
- **选择依据**：无 LoRA → AWQ（Pass@1 更好）；需要多 LoRA → GPTQ。
- 常见误区：认为"AWQ 和 GPTQ 显存不同"——讲义与代码都指出二者 4-bit 足迹相同，区别在 LoRA 支持和 kernel。

### Q14 — 参考回答要点

- **decode**：每步每序列只算 1 个 token，权重读取是带宽瓶颈；权重字节减半，读取时间减半，吞吐近似翻倍（本节代码的 `16 / bits`）。
- **prefill**：大量 token 并行，矩阵乘的算术强度高，是 compute-bound；weight-only 量化不减少 FLOPs，反而多了反量化开销，因此帮助有限。要加速 prefill 需要激活也量化（如 FP8 W8A8、NVFP4 激活），让 Tensor Core 用更低精度直接计算。
- **KV cache 量化的代价**：K 与 Q 的点积决定 attention 分布，V 直接加权求和进入输出；量化误差会扭曲长距离依赖，长上下文、推理、检索类任务最敏感。讲义："affects attention accuracy directly and is not a free win"；第 07 节还指出 KV 降到 FP4 会让 attention 分数崩塌。
- **收益**：KV 减半 → 同样显存并发翻倍、长上下文 decode 读取量减半（见 Q10、Q11）。
- 加分点：说明"权重量化省容量和 decode 带宽；KV 量化省并发容量和长上下文带宽；激活量化省 prefill 算力"，三者是三个独立旋钮。

### Q15 — 参考回答要点

- **初选**：代码生成属于讲义列出的质量敏感负载（"reasoning, medical, code-gen"），7B 的显存压力本来不大（BF16 也只有 14 GB），首选 **FP8**；若必须压缩到 INT4（例如要塞进更小的 GPU 或追求极致并发），用 **AWQ + Marlin**，并用**代码领域数据**校准（讲义的校准陷阱正是以 HumanEval 为例）。
- **验证**：BF16 基线 vs 量化版本在 HumanEval（及内部代码 eval）上对比，设定可接受的掉点阈值（skill 文件："Ship if drop ≤ quality tolerance"）；同时测真实 batch 下的吞吐。
- **恢复路径**：磁盘上保留 BF16/FP8 权重，通过配置开关回切（skill 文件的 rollback path）；若 INT4 掉点：先换领域校准集重做 AWQ → 仍不达标就退回 FP8 → 再不行用 BF16。
- 常见误区：只用 C4/WikiText 校准代码模型；只在 MMLU 等通用基准上验证。

### Q16 — 参考回答要点

- **LoRA 多租户层**：70B 基座 GPTQ-Int4 + Marlin（vLLM 支持 GPTQ + LoRA），40 个 adapter 动态加载；显存预算 = 35 GB 权重 + adapter + KV + 激活，按并发与上下文核算是否需要 H200 或 TP=2；KV 视 eval 结果选 FP8。
- **推理型分析负载**：单独部署 FP8 权重（或 BF16），不与 INT4 的租户层混用；讲义："For reasoning-heavy workloads, ship FP8 or BF16; accept the memory cost."
- **校准**：每类领域（法律、金融等）准备几百到两千条领域样本（skill："500-2000 for domain"），留 10% 做校准验证；基座只量化一次，但要用覆盖各租户领域的混合校准集。
- **验证**：每个租户 adapter 在自己的 eval 上比较 BF16 基座 + LoRA 与 GPTQ 基座 + LoRA；推理负载用 MATH/内部任务。
- **上线**：shadow / 金丝雀（第 20 节），以 goodput 和质量指标为闸门；保留 BF16 权重用于回滚。
- 加分点：指出 NVFP4 目前不支持 LoRA，即使未来迁移到 Blackwell，多 LoRA 层也要等支持成熟。

### Q17 — 参考回答要点

- **权重只是一部分**：KV cache 与并发 × 上下文成正比。按真实 70B 形状，128 条 2k 序列的 BF16 KV 约 86 GB，比权重本身还大；再加激活，单张 H100 放不下。
- **并发上限**：权重 35 GB 后剩约 41 GB，按代码估算 BF16 KV 只能放约 77 条 2k 序列；长上下文时更少。
- **吞吐也受 KV 影响**：高并发下 KV 读取成为带宽主导，INT4 权重的吞吐优势从 4 倍降到约 2 倍（见 Q11）。
- **质量**：INT4 在推理/代码任务上会掉点（MATH 约 3–5 分），需要领域校准与 eval 验证。
- **建议**：列出"权重 + KV + 激活"的完整预算；考虑 FP8 KV、PagedAttention、限制最大上下文或多卡；用 goodput 压测确认（第 08 节）。
- 加分点：引用讲义原话"Budget HBM holistically"。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 11 Quantization：让模型装得下](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：量化的数学基础（讲义先修写成"阶段 10 · 13"，实际在第 11 节）。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：KV cache 的分配方式决定实际并发。
- [阶段 17 · 07 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4](../../07-tensorrt-llm-blackwell/docs/zh.md)：NVFP4 + FP8 KV 的经济账。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 显存公式。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：理解多 LoRA 服务的需求来源。

### 本节被哪些后续内容用到
- [阶段 17 · 10 缓解无服务器 LLMs 的冷启动](../../10-cold-start-mitigation/docs/zh.md)：权重越小，加载越快。
- [阶段 17 · 12 边缘 Inference](../../12-edge-inference/docs/zh.md)：GGUF 与端侧格式。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：KV cache 压力的另一种解法。
- [阶段 17 · 28 自托管服务选型](../../28-self-hosted-serving-selection/docs/zh.md)：格式、引擎、硬件三者匹配。
- [阶段 17 · 08 Inference 指标](../../08-inference-metrics-goodput/docs/zh.md)：用 goodput 而不是峰值吞吐评估量化收益。

### 延伸关键词
`AWQ` · `GPTQ` · `Marlin kernel` · `GGUF / K-quants` · `Q4_K_M` · `FP8 E4M3` · `MXFP4 / NVFP4` · `calibration dataset` · `weight-only quantization` · `W8A8` · `KV cache quantization` · `multi-LoRA serving` · `HBM budget` · `llama.cpp` · `vLLM quantization`
