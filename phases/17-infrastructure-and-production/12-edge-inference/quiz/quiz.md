# 测验 · 边缘 Inference：Apple Neural Engine、Qualcomm Hexagon、WebGPU/WebLLM、Jetson（Edge Inference — Apple Neural Engine, Qualcomm Hexagon, WebGPU/WebLLM, Jetson）

> **阶段 17 · 基础设施与生产 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量较差（例如把 tok/s 译成"吨/秒"、把 TOPS 译成"吨"），数字和术语请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 边缘的真正瓶颈是带宽 | decode 每生成一个 token 都要把全部权重读一遍；移动 DRAM 50–90 GB/s，数据中心 HBM3 2–3 TB/s，讲义称差距 30–50 倍 |
| 2 | 带宽天花板公式 | `ceiling(tok/s) = 带宽(GB/s) / 模型大小(GB)`；讲义：7B Q4 = 3.5 GB，50 GB/s 下约 14 tok/s，90 GB/s 下约 25 tok/s |
| 3 | Apple Neural Engine | M4/A18 最高 38 TOPS，统一内存（CPU 与 ANE 共享同一内存池，无拷贝）；原生访问 ANE 只能经 Core ML，llama.cpp 的 Metal 后端走的是 MPS（GPU）而非 ANE |
| 4 | Qualcomm Hexagon | Snapdragon X Elite / 8 Gen 4 最高 45 TOPS，与 CPU/GPU 同 SoC 但内存域独立；用 QNN SDK 与 AI Hub 转换 |
| 5 | WebGPU + WebLLM | 浏览器内用 WebGPU compute shader 跑模型、免安装；M3 Max 上 Llama 3.1 8B Q4 约 41 tok/s（约原生 70–80%）；OpenAI 兼容 JS API；格式是 MLC 的 q4f16_1，不支持 GGUF |
| 6 | WebGPU 覆盖率 | 讲义：Chrome Android v121+、Safari iOS 26 GA，Firefox Android 仍在追赶，移动端总覆盖约 70–75%，因此必须设计服务端回退 |
| 7 | NVIDIA Jetson | Orin Nano Super（8GB）装得下 Llama 3.2 3B / Phi-3；AGX Orin 用 vLLM 跑 gpt-oss-20b 约 40 tok/s；Thor / T4000 约为 AGX Orin 2 倍；TensorRT Edge-LLM 支持 EAGLE-3、NVFP4、chunked prefill |
| 8 | 按目标选量化格式 | ANE：INT4 权重 + FP16 激活（Core ML）；Hexagon：QNN INT8/INT4；浏览器：MLC Q4；Orin Nano：Q4 GGUF 或 TRT-LLM INT4；AGX/Thor：NVFP4 + FP8 KV |
| 9 | 长上下文陷阱 | 8 GB 内存的手机上，权重 + 32K token 的 KV cache + 操作系统开销会 OOM，边缘部署一般把上下文控制在 4K–8K，除非接受 Q4 KV |
| 10 | 语音是杀手级应用 | 语音 Agent 要求首 token < 500 ms，本地推理彻底消除网络延迟；配合边缘版 Whisper 组成本地语音闭环 |

### 核心技能（能动手做到）

- [ ] 给定设备带宽和模型字节数，30 秒内算出 decode 速度上限，并据此判断某个 tok/s 承诺是否"违反物理"
- [ ] 用"实测 / 上限"计算运行时效率，并能解释效率 > 100% 的数据说明了什么
- [ ] 按 `2 × 层数 × KV 头数 × head_dim × 字节数 × token 数` 估算 KV cache，判断某个上下文长度在手机上是否放得下
- [ ] 为 iOS / Android / 浏览器 / Jetson 各自选出量化格式与转换工具链（Core ML、QNN/AI Hub、MLC-LLM、TensorRT Edge-LLM）
- [ ] 为 WebGPU 不可用的浏览器设计"同一 OpenAI 兼容接口"的服务端回退
- [ ] 给 `main.py` 加上内存容量检查与 KV cache 读取量，使它的结论更接近真实

---

## 二、基础自测（选择题）

**Q1.** 按讲义的带宽上限算法，一个 Q4 量化后 3.5 GB 的 7B 模型，在带宽 50 GB/s 的手机上，decode 速度的理论上限约为：

- A. 0.07 tok/s
- B. 3.5 tok/s
- C. 14 tok/s
- D. 143 tok/s

**Q2.** 讲义说"边缘的核心约束是内存带宽，而不是算力"。最准确的原因是：

- A. 单用户 decode 每生成 1 个 token 都要把全部权重从内存读一遍，而每个字节只参与极少量运算，算力大部分在等数据
- B. 手机 NPU 的 TOPS 比数据中心 GPU 高，所以算力过剩
- C. 量化以后权重变小，计算量变成 0
- D. prefill 阶段需要逐 token 处理，因此受带宽限制

**Q3.** 运行 `code/main.py`，`Jetson AGX Orin` 一行的 efficiency 是 **103%**（上限 43.6 tok/s，实测 45 tok/s）。最合理的解读是：

- A. Jetson 的统一内存可以突破带宽限制，这是正常现象
- B. 代码的 `efficiency` 函数把分子分母写反了
- C. 说明 AGX Orin 是算力瓶颈而不是带宽瓶颈
- D. 在"每 token 读一遍 4.7 GB 权重"的模型下效率不可能超过 100%，说明这条"实测值"与表头所说的"Llama 8B Q4 单流 decode"口径不一致（可能混入了别的模型、投机解码或批处理的数据）

**Q4.** 关于在 Apple 设备上使用 Neural Engine（ANE），下列说法正确的是：

- A. llama.cpp 的 Metal 后端直接调用 ANE
- B. 2026 年原生使用 ANE 需要把模型转换成 Core ML；llama.cpp 的 Metal 后端走的是 MPS（GPU），不是 ANE
- C. ANE 与 CPU 有独立显存，推理前必须把权重拷贝过去
- D. ANE 只能运行 FP32 模型

**Q5.** 讲义推荐在浏览器中通过 WebGPU + WebLLM 部署时使用哪种权重格式？

- A. MLC 的 Q4（q4f16_1），用 `mlc_llm convert_weight` 转换并配合编译好的 `.wasm`
- B. GGUF Q4_K_M
- C. NVFP4 + FP8 KV
- D. Core ML INT4 + FP16

**Q6.** Llama 3.1 8B 有 32 层、8 个 KV 头、head_dim = 128。用 FP16 存 KV cache，32K（32,768）个 token 的 KV cache 约为：

- A. 512 MiB
- B. 1 GiB
- C. 2 GiB
- D. 4 GiB

**Q7.** `main.py` 的"QUANTIZATION IMPACT"部分输出 `iPhone 16 + BF16 model= 18.8 GB ceiling= 3.2 tok/s`。下列评价最恰当的是：

- A. 结论完全正确，iPhone 16 上跑 BF16 只是慢一些
- B. 18.8 GB 是 8B 模型 BF16 的精确大小
- C. 上限与模型字节数成反比这一点正确，但 iPhone 16 只有 8 GB 内存，18.8 GB 的模型根本装不下，"3.2 tok/s"是没有意义的数字；而且 8B 的 BF16 实际约 16 GB，18.8 GB 是把 4.7 GB 直接乘 4 得到的
- D. BF16 比 Q4 快，因为不需要反量化

**Q8.** 一个基于 WebLLM 的产品需要覆盖 Firefox Android 用户。按讲义与配套 skill，正确做法是：

- A. 改用 GGUF 让 Firefox 支持
- B. 检测到 WebGPU 不可用时，回退到服务端推理，并且服务端提供与 WebLLM 相同的 OpenAI 兼容接口，前端代码几乎不用改
- C. 让用户安装 Chrome 之后才能使用，不做任何回退
- D. 在 Firefox 上用 CPU 跑 8B 模型，速度相同

---

## 三、动手 / 代码题

**Q9.**（讲义练习 1）

1. 7B 模型 Q4（3.5 GB）在 Snapdragon 8 Gen 3（约 77 GB/s）上，decode 的带宽上限是多少？讲义给出的实测是 6–8 tok/s，运行时效率大约多少？
2. `main.py` 里同一款芯片用的是 8B、4.7 GB，上限和效率分别是多少？
3. 列出至少 3 个"实测远低于带宽上限"的原因。

**Q10.** `ceiling()` 只考虑了权重：

```python
def ceiling(target: Target, model_gb: float) -> float:
    seconds_per_token = model_gb / target.bandwidth_gb_s
    return 1 / seconds_per_token
```

请改造代码：

1. 增加 KV cache 读取量：每生成一个 token，还要把已有上下文的 K/V 全部读一遍。写一个 `ceiling_with_kv(bw_gb_s, model_gb, ctx_tokens, kv_bytes_per_token)`。
2. 增加容量检查 `fits(ram_gb, model_gb, ctx_tokens, kv_bytes_per_token, os_overhead_gb=2.5)`。
3. 用 Llama 3.1 8B Q4（4.7 GB，每 token KV = 131,072 字节）在 iPhone 16（60 GB/s，8 GB 内存）上计算：4K 上下文时的上限，以及 32K 上下文是否装得下。

**Q11.** 对照讲义与代码，找出 `main.py` 中至少 4 处数据或建模上的问题（提示：看 efficiency 列、BF16 的大小、iPhone 的实测值、`notes` 列的说法）。

**Q12.**（讲义练习 3）iOS 应用需要 4K 上下文流式输出，活跃内存必须控制在 4 GB 以内（iPhone 16，带宽按 60 GB/s）。请给出模型与格式组合，并算出：权重大小、4K 上下文的 KV cache（FP16）、总内存、带宽上限。已知 Llama 3.2 3B：约 3.21B 参数、28 层、8 个 KV 头、head_dim = 128；Q4 按每参数约 4.7 bit 估算。

---

## 四、面试高频题

**Q13.**（基础必考）为什么说端侧 LLM 推理是 memory-bound？请用 roofline / 算术强度的语言解释，并给出一个"手机上能跑多快"的估算方法。

**Q14.**（原理深挖）讲义说 AGX Orin 用 vLLM 跑 gpt-oss-20b 约 40 tok/s，而 `main.py` 算出同一块板子跑 8B 稠密模型 Q4 的上限只有 43.6 tok/s。为什么一个"20B"的模型可以和 8B 稠密模型跑得差不多快？MoE 在边缘部署上有什么代价？

**Q15.**（工程实践）同一个模型要同时发布到 iOS、Android、浏览器和 Jetson 机器人上，请分别给出量化格式、转换工具链，并说明如何统一上层接口。

**Q16.**（场景设计）设计一个"离线优先、隐私默认"的语音助手，目标设备从 iPhone 16 到中端 Android 再到浏览器。请说明模型选择、上下文预算、首 token 延迟目标、回退策略和要监控的指标。

**Q17.**（追问型）"2026 年 WebLLM 已经可以用于生产"——你同意吗？请结合覆盖率、性能和 Firefox Android 的缺口论证（讲义练习 5）。

---

## 五、参考答案与解析

### Q1 — 答案：C

`3.5 GB ÷ 50 GB/s = 70 ms/token`，即约 `1000 / 70 ≈ 14.3 tok/s`（实际计算）。讲义原话："Reading 3.5 GB at 50 GB/s takes 70 ms — a theoretical ceiling of ~14 tok/s."

- A 把公式倒过来了（3.5/50 = 0.07 秒是"每 token 的时间"，不是速度）。
- B 是模型的 GB 数，与速度无关。
- D 把 50 GB/s 误当成 500 GB/s 或单位换算错。

### Q2 — 答案：A

单用户 decode 时 batch = 1，每个权重读进来只做一次乘加，算术强度（FLOPs / 字节）只有约 2 FLOPs/参数，远低于芯片的"算力 / 带宽"比值，所以算力单元大部分时间在等内存。这就是讲义"No amount of compute helps below this number"的含义。

- B 错：手机 NPU 的 38–45 TOPS 远低于数据中心 GPU，但即便如此算力也是过剩的，原因是带宽太低，而不是 NPU 算力更高。
- C 错：量化减少的是读的字节数，计算量并不为 0。
- D 错：prefill 是并行处理整个 prompt，偏算力瓶颈；带宽瓶颈的是 decode。

### Q3 — 答案：D

`ceiling = 205 / 4.7 = 43.6 tok/s`，代码把实测写成 45，`45 / 43.6 = 103%`。在代码自己的模型（每 token 读完整个 4.7 GB）下，效率 > 100% 等于"违反物理"，只能说明这条实测数据与表头的口径不一致。讲义里 AGX Orin 的 "~40 tok/s" 是 **gpt-oss-20b** 的数字（MoE，每 token 只读激活参数），很可能被挪用到了这里；也可能来自投机解码或多并发。

- A 错：统一内存省掉的是 CPU↔加速器拷贝，不会提高 DRAM 带宽本身。
- B 错：`observed / ceiling_val * 100` 写法正确。
- C 错：即使是算力瓶颈，也只会让速度更低，不可能超过带宽上限。

结论：看到效率 > 100% 时，第一反应应该是检查数据口径，而不是怀疑公式。

### Q4 — 答案：B

讲义："Llama.cpp Metal backend uses MPS, not ANE directly; native ANE requires Core ML conversion." 2026 年 iOS 最实际的路径是 Core ML + INT4 权重 + FP16 激活。

- A 正好说反了。
- C 错：Apple Silicon 是统一内存，CPU 与 ANE 共享内存池，这正是 ANE 无拷贝开销的原因。
- D 错：推荐的就是 INT4 权重 + FP16 激活。

### Q5 — 答案：A

讲义表格："WebGPU / WebLLM — Q4 MLC (q4f16_1) — Use `mlc_llm convert_weight` + compiled `.wasm`; GGUF is not supported."

- B：GGUF 是 llama.cpp 生态的格式，WebLLM 不支持。注意配套的 `outputs/skill-edge-target-picker.md` 第 3 条写着"Q4 GGUF (browser/edge CPU)"，与讲义表格矛盾，应以讲义为准。
- C：NVFP4 + FP8 KV 是 Jetson AGX / Thor 的路线。
- D：Core ML 是 ANE 的路线。

### Q6 — 答案：D

每 token：`2（K、V）× 32 层 × 8 个 KV 头 × 128 × 2 字节 = 131,072 字节 = 128 KiB`；`× 32,768 = 4 GiB`（实际计算）。

讲义写的是"4 GB model + 2 GB KV cache for 32K tokens"，对 Llama 3.1 8B 的 FP16 KV 来说偏低一半；2 GiB 对应的是 8-bit KV。不管哪种算法，结论都一样：8 GB 内存的手机上，4.7 GB 权重 + 2–4 GB KV + 操作系统必然 OOM。

- A 是 4K 上下文的量（0.5 GiB）。
- B 是 8K 上下文的量。
- C 是讲义的数字（相当于 8-bit KV）。

### Q7 — 答案：C

"上限 ∝ 1 / 模型字节数"是对的（BF16 → Q4 字节数降为 1/4，上限提高 4 倍）。但：

1. 代码没有任何容量检查。iPhone 16 只有 8 GB 内存，18.8 GB 根本装不下，INT8 的 9.4 GB 也装不下，这两行上限都没有意义。
2. 8.03B 参数 × 2 字节 ≈ 16.1 GB，18.8 GB 是把 Q4 的 4.7 GB 机械乘 4 得来的。4.7 GB 对应每参数约 4.7 bit（Q4 量化带 scale 等元数据），并不是精确的 4 bit，所以不能直接乘 4。

- A、B 见上。
- D 错：在带宽瓶颈下读的字节越多越慢，反量化的计算开销在算力过剩时几乎可以忽略。

### Q8 — 答案：B

讲义练习 2 和 skill 的 Fallback 条款都要求：WebGPU 不可用（Firefox Android、旧版浏览器）时回退到服务端，并使用与 WebLLM 相同的 OpenAI 兼容接口，这样前端只需切换 `baseURL`。

- A 错：WebLLM 不支持 GGUF，而且问题不在格式，在于浏览器没有 WebGPU。
- C 在产品层面通常不可接受；skill 的拒绝条款也只是"用户要求 Firefox 支持时要么要求 Chrome、要么提供服务端回退"。
- D 错：CPU 路径远慢于 GPU，而且手机内存往往装不下 8B。

### Q9 — 参考答案

1. `77 / 3.5 = 22.0 tok/s`。实测 6–8 tok/s，效率 `6/22 ≈ 27%` 到 `8/22 ≈ 36%`，说明运行时远没有吃满带宽。
2. 代码中 8B、4.7 GB：`77 / 4.7 = 16.4 tok/s`，实测 7 tok/s，效率 43%（运行输出 `16.4  7  43%`）。
3. 实测低于上限的常见原因：
   - **峰值带宽 ≠ 可持续带宽**：LPDDR 的标称带宽在实际访存模式下通常只能用到一部分，且被 CPU、GPU、显示等共享。
   - **NPU 不一定能从用户空间访问**：讲义强调"whether the NPU is accessible from user-space"；很多应用实际跑在 CPU 或 GPU 上。
   - **热降频**：手机持续推理几十秒后会降频，数字越跑越低。
   - **KV cache 读取、反量化、采样、调度**等额外开销，上限公式都没算。
   - 运行时实现不够成熟（算子融合差、内存布局不友好）。

### Q10 — 参考答案

```python
def ceiling_with_kv(bw_gb_s, model_gb, ctx_tokens, kv_bytes_per_token):
    kv_gb = ctx_tokens * kv_bytes_per_token / 1e9      # 每步要读的 KV 字节
    return bw_gb_s / (model_gb + kv_gb)

def fits(ram_gb, model_gb, ctx_tokens, kv_bytes_per_token, os_overhead_gb=2.5):
    kv_gb = ctx_tokens * kv_bytes_per_token / 1e9
    need = model_gb + kv_gb + os_overhead_gb
    return need <= ram_gb, round(need, 2)

KV_LLAMA31_8B = 2 * 32 * 8 * 128 * 2                  # 131,072 字节/token
print(ceiling_with_kv(60, 4.7, 4096, KV_LLAMA31_8B))  # ≈ 11.5 tok/s
print(fits(8, 4.7, 4096, KV_LLAMA31_8B))              # (True, 7.74)  勉强
print(fits(8, 4.7, 32768, KV_LLAMA31_8B))             # (False, 11.49)
```

计算结果（已实际运行）：

- 4K 上下文：KV 约 0.54 GB，上限从 12.8 降到约 **11.5 tok/s**。上下文越长，每步要读的 KV 越多，decode 越来越慢，这是原代码看不到的效应。
- 4K 时总需求约 7.7 GB（含假设的 2.5 GB 系统开销），8 GB 手机上已经非常勉强；iOS 对单个 App 的内存上限通常远低于物理内存，实际上更不可行。
- 32K 时 KV 约 4.3 GB，总需求约 11.5 GB，**装不下**，对应讲义的"long-context trap"。

要点：上限公式里的"字节"应是"每步要读的全部字节 = 权重 + 当前 KV"；容量检查要放在速度估算之前，装不下时直接拒绝（skill 的 Hard rejects 也是这个顺序）。

### Q11 — 参考答案

1. **Jetson AGX Orin 效率 103%**：实测 45 > 上限 43.6，在代码自己的模型下不可能成立，数据口径不一致（见 Q3）。讲义的 ~40 tok/s 是 gpt-oss-20b 的数字。
2. **BF16 大小 18.8 GB**：由 `4.7 × 4` 得来，实际约 16.1 GB（8.03B × 2 字节）；INT8 的 9.4 GB 也是同样乘出来的，实际约 8.5 GB 左右。
3. **没有容量检查**：iPhone 16 8 GB 内存装不下 BF16 和 INT8，代码却照样打印上限。
4. **iPhone 实测值不一致**：讲义 The Problem 说同一个 Llama 3.1 8B Q4 在 iPhone 16 Pro 上约 3 tok/s，代码里 A18 写的是 8 tok/s。
5. **`notes` 的"browser penalty ~25%"与效率列的关系**：WebGPU 41 vs 原生 55 是 `41/55 ≈ 75%`，所以"损失 25%"是相对原生而言；但若只看 efficiency 列（48% vs 65%），容易误以为浏览器只到了上限的一半，要区分"相对上限"和"相对原生"两个口径。
6. **只算权重、不算 KV cache**（见 Q10），长上下文时上限被高估。
7. `WebGPU on Pixel 9` 直接沿用了与 Snapdragon 8 Gen 3 相同的 77 GB/s，属于假设值，代码没有注明来源。

### Q12 — 参考答案

选 **Llama 3.2 3B，Core ML INT4 权重 + FP16 激活**（或其它 3B 级模型）：

| 项 | 计算 | 结果 |
|----|------|------|
| 权重 | `3.21e9 × 4.7 / 8` | 约 1.89 GB |
| KV / token | `2 × 28 × 8 × 128 × 2` | 114,688 字节 |
| 4K KV（FP16） | `114,688 × 4,096` | 约 0.47 GB |
| 活跃内存合计 | 1.89 + 0.47 | 约 2.36 GB（再加运行时缓冲，仍 < 4 GB） |
| 带宽上限（只算权重） | `60 / 1.89` | 约 31.7 tok/s |
| 带宽上限（含 4K KV） | `60 / 2.36` | 约 25.4 tok/s |

（以上数值已用 Python 计算。）8B Q4 光权重就 4.7 GB，超出 4 GB 预算，排除。若还需要更长上下文，可以接受 8-bit 或 Q4 KV（讲义提到 Q4 KV），把 KV 再压一半到四分之一。

### Q13 — 参考回答要点

- **算术强度**：batch = 1 的 decode 中，每个参数只做一次乘加（约 2 FLOPs），每个参数 Q4 下约 0.5–0.6 字节，算术强度只有约 3–4 FLOPs/字节。
- **roofline**：芯片的"转折点" = 峰值算力 / 带宽。手机上 38 TOPS / 60 GB/s ≈ 600 ops/字节，远高于 decode 的算术强度，所以完全落在带宽斜线上。
- **估算方法**：`tok/s 上限 = 带宽 / (权重字节 + 当前 KV 字节)`，再乘一个经验效率（讲义数据大约 40–80%）。例如 iPhone 16（60 GB/s）跑 8B Q4（4.7 GB）上限约 12.8 tok/s。
- **推论**：提升边缘速度的手段依次是减少字节（量化、更小的模型、MoE 只读激活专家）、提高带宽利用率（更好的 kernel）、投机解码（一次读权重验证多个 token）。增加 TOPS 几乎没用。
- 加分点：prefill 是算力瓶颈，所以长 prompt 的首 token 延迟在手机上会受 NPU 算力影响；decode 才是带宽瓶颈。

### Q14 — 参考回答要点

- **MoE 只读激活参数**：gpt-oss-20b 是 MoE，每个 token 只激活少数专家，激活参数远少于总参数，权重又是 4-bit 级格式，所以每 token 读的字节接近一个 2–4B 稠密模型，带宽上限反而比 8B 稠密模型高。
- **代价 1：容量**——全部专家都必须常驻内存，因为下一个 token 可能路由到任何专家；这就是为什么讲义说 Orin Nano（8 GB）只能装 3B 级，而 gpt-oss-20b 要 AGX Orin。
- **代价 2：访存不规则**——不同 token 读不同专家，缓存局部性差，批处理时激活的专家并集变大，单流优势会被削弱。
- **代价 3：工具链支持**——不是所有边缘运行时都支持 MoE 和对应量化格式；讲义提到的是 vLLM 与 TensorRT Edge-LLM。
- 加分点：指出 `main.py` 中 AGX Orin 的 45 tok/s（效率 103%）很可能就是把 MoE 的数字套在了稠密 8B 上。

### Q15 — 参考回答要点

| 目标 | 格式 | 工具链 |
|------|------|--------|
| iOS（ANE） | INT4 权重 + FP16 激活 | Core ML 转换（只有 Core ML 能原生用 ANE） |
| Android（Hexagon） | QNN INT8 / INT4 | Qualcomm AI Hub / QNN SDK |
| 浏览器 | MLC Q4（q4f16_1） | `mlc_llm convert_weight` + 编译 `.wasm`，WebLLM 运行 |
| Jetson Orin Nano | Q4 GGUF 或 TRT-LLM INT4 | llama.cpp 或 TensorRT-LLM |
| Jetson AGX / Thor | NVFP4 + FP8 KV | TensorRT Edge-LLM |

- **统一接口**：各端运行时都包一层 OpenAI 兼容的 chat completions 接口（WebLLM 原生提供），业务代码只认这一层；设备不支持时把 `baseURL` 指向服务端。
- **统一评测**：同一套离线评测集在每种格式上跑一遍，比较量化后的质量回退；性能看"最差设备上的 tok/s"（skill 结尾要求的单一指标）。
- 常见误区：以为一个 GGUF 文件能通吃所有端；以为 llama.cpp 在 Mac 上用的是 ANE。

### Q16 — 参考回答要点

- **模型**：1–3B 级 + INT4；只在高端设备上提供 8B 选项。用带宽公式先算最差设备的上限，保证 > 语音所需的读出速度（语音朗读约 3–5 token/s 就够，但首 token 必须快）。
- **首 token**：讲义要求 < 500 ms。首 token = ASR 尾延迟 + prefill + 一步 decode；prefill 吃算力，要控制系统提示长度，必要时缓存系统提示的 KV。
- **上下文预算**：4K–8K（讲义建议），超过则摘要压缩历史；可选 8-bit / Q4 KV。
- **ASR**：边缘版 Whisper Turbo 变体（讲义），与 LLM 共享内存预算。
- **回退**：WebGPU 不可用、内存不足、电量低或温度过高时回退到服务端，同一 OpenAI 兼容接口；隐私模式下回退需要用户同意。
- **监控**：按设备型号统计首 token 延迟 P50/P99、tok/s、OOM 和崩溃率、降频后的性能、回退比例。
- 加分点：说明 iOS 对单 App 的内存限制远低于物理内存，规划时要留余量。

### Q17 — 参考回答要点

- **支持的论据**：WebLLM 约 41 tok/s（M3 Max、8B Q4），约为原生的 70–80%；OpenAI 兼容 JS API、Apache 2.0、社区活跃（讲义 17.6k stars）；Safari iOS 26 已 GA，Chrome Android v121+ 可用。
- **反对的论据**：移动端覆盖率只有约 70–75%，Firefox Android 仍在追赶；手机浏览器里 8B 模型只有 4–8 tok/s；首次加载要下载几 GB 权重，冷启动体验差；浏览器标签页的内存限制更严格。
- **结论**：对"有服务端回退"的产品是可以上生产的——把 WebLLM 当作"有 WebGPU 时的加速/隐私路径"，而不是唯一路径。如果产品要求在所有移动浏览器上都本地运行，则还不成熟。
- 加分点：给出灰度指标（WebGPU 可用率、模型下载完成率、首 token 延迟、回退率）。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：prefill 与 decode 的区别，decode 为什么是带宽瓶颈。
- [阶段 17 · 09 生产环境中的 Quantization：AWQ、GPTQ、GGUF K-quants、FP8、MXFP4/NVFP4](../../09-production-quantization/docs/zh.md)：本节每个目标所用量化格式的原理。
- [阶段 10 · 11 Quantization：让模型装得下](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：量化如何减少字节数。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 大小的估算公式。
- [阶段 04 · 15 实时视觉——边缘部署](../../../04-computer-vision/15-real-time-edge/docs/zh.md)：边缘部署的一般约束（功耗、内存、热）。

### 本节被哪些后续内容用到
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../05-eagle3-speculative-decoding/docs/zh.md)：TensorRT Edge-LLM 把 EAGLE-3 带到了边缘。
- [阶段 17 · 07 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4](../../07-tensorrt-llm-blackwell/docs/zh.md)：Jetson Thor 使用的 NVFP4 路线。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：衡量边缘体验的首 token 延迟与 tok/s。
- [阶段 17 · 28 自托管服务选型：让引擎匹配硬件与规模](../../28-self-hosted-serving-selection/docs/zh.md)：在服务端回退路径上选择引擎。
- [阶段 14 · 22 语音 Agents：Pipecat 与 LiveKit](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：语音这一"杀手级应用"的工程实现。
- [阶段 19 · 03 综合项目 03：实时语音助手——从 ASR 到 LLM 再到 TTS](../../../19-capstone-projects/03-realtime-voice-assistant/docs/zh.md)：端到端语音闭环。

### 延伸关键词
`memory-bound` · `roofline` · `arithmetic intensity` · `unified memory` · `Core ML` · `QNN / AI Hub` · `MLC-LLM` · `WebGPU` · `q4f16_1` · `TensorRT Edge-LLM` · `NVFP4` · `KV cache quantization` · `MoE active parameters` · `thermal throttling`
