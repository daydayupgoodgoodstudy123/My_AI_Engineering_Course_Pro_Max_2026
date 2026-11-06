# 测验 · Quantization：让模型装得下（Quantization: Making Models Fit）

> **阶段 10 · 从零构建 LLM · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（另有 Rust 版 [code/main.rs](../code/main.rs)，只实现对称量化与误差统计） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 浮点格式的位分配 | 指数位决定**范围**、尾数位决定**精度**：FP32 = 1/8/23，FP16 = 1/5/10（最大 65,504），BF16 = 1/8/7（与 FP32 同范围），FP8 E4M3（推理）/ E5M2（训练梯度） |
| 2 | 显存估算 | 权重显存 = 参数量 × 每参数字节数：70B 在 FP16 = 140 GB、FP8 = 70 GB、INT4 = 35 GB（十进制 GB；按 GiB 算分别是 130.4 / 65.2 / 32.6） |
| 3 | 对称量化 | `scale = max|x| / qmax`，`q = clip(round(x/scale))`，反量化 `x̂ = q·scale`；每个值的舍入误差不超过 `scale/2` |
| 4 | 非对称量化 | 增加 zero-point，把 `[min, max]` 映射到 `[0, 2^b − 1]`，适合不以 0 为中心的分布（如 ReLU 后的激活） |
| 5 | 量化粒度 | per-tensor 一个 scale → per-channel 每通道一个 → group（如每 128 个权重一个）；粒度越细误差越小、scale 存储开销越大 |
| 6 | 敏感度层级（讲义） | 权重（最稳健）< 激活（有离群值）< KV cache（误差在长序列上累积）< attention logits（softmax 放大误差，通常保持 FP16/BF16） |
| 7 | PTQ vs QAT | PTQ：训练后直接量化，快且便宜，INT8/FP8 很好、INT4 需 GPTQ/AWQ；QAT：前向插入伪量化，用 STE 让梯度"穿过"取整，低比特质量更好但要完整训练 |
| 8 | GPTQ / AWQ / GGUF | GPTQ：逐层、用校准数据的二阶信息（Hessian）补偿舍入误差；AWQ：按激活幅度找约 1% 的显著权重，量化前放大它们；GGUF：llama.cpp 的自包含文件格式，混合精度，面向 CPU/Apple Silicon，Q4_K_M 最常用 |
| 9 | 质量度量 | 权重层面：MSE、SNR、余弦相似度；模型层面：WikiText-2 perplexity 增量（讲义：< 0.5 优秀、> 2.0 有问题）、任务基准（数学/代码更敏感）、输出对比、延迟与吞吐 |
| 10 | 比特数与误差 | 均匀量化每多 1 bit，量化噪声功率约降为 1/4，SNR 约提升 6 dB；4 bit 附近是质量"悬崖"的起点 |

### 核心技能（能动手做到）

- [ ] 手算任意小张量的对称/非对称 INT8、INT4 量化结果与反量化误差
- [ ] 读懂 FP16/BF16/FP8 的位模式，指出本节 FP8 模拟器在**进位**和**次正规数**上的错误，以及 BF16 用截断代替就近舍入的问题
- [ ] 按参数量、精度、KV cache 估算一个模型能否放进某块 GPU（注意 GB 与 GiB、GQA 的 KV 头数）
- [ ] 解释 per-channel 为什么在本节数据上效果好，以及"离群值在行还是在列"如何决定它是否有效
- [ ] 说清真实的 GPTQ、AWQ 在做什么，并指出本节"Simulated GPTQ / AWQ"与真实算法的差距
- [ ] 设计一个量化上线前的验证流程（perplexity、任务 eval、输出对比、吞吐/延迟）

---

## 二、基础自测（选择题）

**Q1.** 关于 BF16 与 FP16，下列说法正确的是：

- A. BF16 有 10 位尾数，比 FP16 更精确
- B. BF16 的最大值只有约 65,504，因此训练时需要 loss scaling
- C. FP16 与 BF16 的指数位数相同，只是尾数不同
- D. BF16 保留了 FP32 的 8 位指数（范围与 FP32 相同），尾数只有 7 位，精度低于 FP16；它不容易下溢，因此成为训练的默认格式

**Q2.** 讲义说 70B 模型 INT4 权重约 35 GB，本节 `print_memory_table` 却打印 `32.6G`。原因是：

- A. 代码额外计入了 scale factor 的存储
- B. 代码除以 `1024**3`，单位是 GiB；35 GB（十进制，10^9 字节）≈ 32.6 GiB，两者是同一个量
- C. 代码把 INT4 当成了 3.7 bit
- D. 代码漏算了 embedding 层

**Q3.** 用本节 `quantize_symmetric` 对 `[0.503, −1.27, 0.0219]` 做 8-bit 对称量化，得到的 scale 和整数是：

- A. `scale = 0.01`，`q = [50, −127, 2]`
- B. `scale = 0.00996`，`q = [51, −128, 2]`
- C. `scale = 0.01`，`q = [50, −128, 2]`
- D. `scale = 1.27`，`q = [0, −1, 0]`

**Q4.** per-channel 量化通常比 per-tensor 好得多，最根本的原因是：

- A. per-channel 使用了更多的比特
- B. per-channel 不需要校准数据
- C. 不同通道的数值范围差异很大时，per-tensor 的 scale 被最大的通道决定，小幅值通道只能用到很少的量化级别；per-channel 让每个通道按自己的范围使用全部级别
- D. per-channel 会把离群值直接丢弃

**Q5.** 用本节 `quantize_asymmetric` 对最小值 −1.0、最大值 1.55 的张量做 8-bit 非对称量化，数值 0.0 会被映射成哪个整数？

- A. 0
- B. 100
- C. 128
- D. 155

**Q6.** 按讲义的"敏感度层级"，从最能容忍量化到最敏感的顺序是：

- A. attention logits < KV cache < 激活 < 权重
- B. 激活 < 权重 < attention logits < KV cache
- C. KV cache < 权重 < 激活 < attention logits
- D. 权重 < 激活 < KV cache < attention logits

**Q7.** 关于 QAT（量化感知训练），正确的是：

- A. 在前向传播中插入"量化—反量化"的伪量化操作，反向传播时用 straight-through estimator 把取整的梯度当作 1，让模型学会容忍舍入误差
- B. 不需要训练，只需要 128 条校准样本
- C. QAT 只在推理时生效，与训练无关
- D. QAT 在 INT8 上比 PTQ 好很多，在 INT4 上没有优势

**Q8.** 关于 GPTQ、AWQ、GGUF，下列描述正确的是：

- A. 三者都是量化算法，GGUF 是其中最新的一种
- B. AWQ 会把约 1% 的显著权重保留为 FP16，其余量化为 INT4
- C. GPTQ 用校准数据估计二阶信息，逐层量化并补偿舍入误差；AWQ 根据激活幅度识别显著权重并在量化前放大它们；GGUF 是 llama.cpp 生态的自包含文件格式，支持混合精度
- D. GGUF 主要面向 H100 的 FP8 推理

---

## 三、动手 / 代码题

**Q9.** 本节的 FP8 E4M3 模拟器：

```python
    exp = int(np.floor(np.log2(abs_val)))
    exp = max(-6, min(8, exp))
    mantissa_val = abs_val / (2.0 ** exp) - 1.0
    mantissa_quant = round(mantissa_val * 8) / 8
    mantissa_quant = max(0, min(0.875, mantissa_quant))
    reconstructed = (1.0 + mantissa_quant) * (2.0 ** exp)
```

实测：`simulate_fp8_e4m3(1.97) → 1.875`、`simulate_fp8_e4m3(0.99) → 0.9375`、`simulate_fp8_e4m3(0.00073) → 0.015625`。

1. 前两个结果错在哪里？正确的 E4M3 值是多少？
2. 第三个结果错在哪里？已知 E4M3 的指数偏置为 7、最小正规数为 `2^−6 = 0.015625`、次正规数步长为 `2^−9 ≈ 0.00195`，正确结果是多少？
3. 同一张输出表里，BF16 把 0.1 存成了 0.099609。代码是怎样从 FP32 得到 BF16 的？按"就近舍入（round-to-nearest-even）"应该是多少？

**Q10.** STEP 6 的实际输出：

```text
  Method                          MSE   SNR (dB)   Cosine Sim
  Per-channel              0.00002284      17.31   0.99087935
  Simulated AWQ            0.00002284      17.31   0.99087935
```

两行完全相同（实测两者重建结果的最大差异为 `6.9e-18`）。相关源码：

```python
    scaled_weights = weight_matrix * scale_factors.reshape(-1, 1)
    quantized, scales = quantize_per_channel(scaled_weights, num_bits, axis=0)
    dequantized = dequantize_per_channel(quantized, scales, axis=0)
    result = dequantized / scale_factors.reshape(-1, 1)
```

1. 用一行公式解释为什么"先按行乘 s、再按行量化、再除以 s"与直接按行量化完全等价。
2. 实测被选中的两个显著行的 scale factor 是 `0.295` 和 `0.334`。这与讲义描述的 AWQ（"scales them up"）方向一致吗？
3. 真实 AWQ 中，scale 作用在哪个维度、量化分组在哪个维度，为什么那样才会有效果？

**Q11.** STEP 6 中 "Simulated GPTQ" 的权重 MSE 为 0.000176，比 per-channel（0.0000228）**差约 7.7 倍**。阅读核心循环：

```python
    for col in range(n_out):
        w_col = W[:, col]
        scale = np.max(np.abs(w_col)) / qmax
        q_col = np.clip(np.round(w_col / scale), qmin, qmax).astype(np.int32)
        quant_error = w_col - q_col * scale
        ...
            for next_col in range(col + 1, min(col + 4, n_out)):
                compensation = quant_error * importance_weights * 0.1
                W[:, next_col] += compensation
```

权重形状为 `(d_in, d_out) = (256, 512)`，前向为 `x @ W`，5 个离群值**行**被放大 10 倍。

1. 这个实现的 scale 是"每列一个"。为什么在本数据上它比"每行一个"差那么多？（提示：实测纯按列量化、不做补偿，MSE 为 0.000173。）
2. 误差被加到了"后面的输出列"上。为什么这种补偿在数学上无法降低 `x @ W` 的输出误差？
3. 真实 GPTQ 的误差补偿是在哪个维度上进行的？

**Q12.** STEP 5 的实际输出（INT4）：

```text
  Component                                 MSE   SNR (dB)   Cosine Sim
  Attention logits (5% noise)        0.00000000      60.05   0.99999951
  Activations only                   0.00002745      18.66   0.99325311
  KV cache only                      0.00002996      18.28   0.99272597
  Weights only                       0.00005590      15.57   0.98751272
```

讲义说敏感度层级是"权重 < 激活 < KV cache < attention logits"，而这里的排序几乎**完全相反**。

1. "Attention logits" 这一行在 INT8 和 INT4 下的数字完全相同，为什么？它测的是量化吗？
2. 实测这个玩具层的注意力权重全部落在 `[0.0586, 0.0665]`，而 `1/16 = 0.0625`。这说明了什么？为什么在这种情况下对 logits 加噪几乎不影响输出？
3. "Weights only" 为什么误差最大？
4. 你会如何修改实验，让它真正检验讲义的层级？

---

## 四、面试高频题

**Q13.**（基础必考）给你一个 70B 的 dense 模型（80 层、GQA 8 个 KV 头、head_dim 128），要在单卡 80 GB 上服务 32K 上下文。请估算不同精度下的显存，并给出你的方案。

**Q14.**（原理深挖）为什么权重容易量化、激活难量化？LLM.int8() 和 SmoothQuant 分别如何处理激活离群值？

**Q15.**（原理深挖）请说明 GPTQ 和 AWQ 的核心思想，以及它们为什么都需要校准数据。

**Q16.**（工程实践）你把一个 8B 模型量化成了 INT4。上线前你要做哪些验证？哪些信号说明"量化坏了"？

**Q17.**（追问型）"INT4 的显存是 FP16 的 1/4，所以推理速度也会快 4 倍。"这句话对吗？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："BF16 keeps the 8-bit exponent from FP32 but shrinks the mantissa to 7 bits. Same range as FP32, less precision than FP16 ... A gradient of 10^-20 that underflows to zero in FP16 survives in BF16." A 把两者的尾数说反了（FP16 是 10 位）；B 描述的是 FP16（最大 65,504，训练需要 loss scaling）；C 错，FP16 是 5 位指数，BF16 是 8 位。

### Q2 — 答案：B

`70 × 10^9 × 0.5 B = 35 × 10^9 B`，除以 `1024^3` 得 32.6，这是 GiB。同理 FP16 打印 130.4G（= 140 GB）。显存厂商标称（"80 GB"）和很多工具使用的单位不同，估算时必须统一口径。A 错：代码没有计 scale；C、D 均无依据。

### Q3 — 答案：A

`max|x| = 1.27`，`scale = 1.27/127 = 0.01`；`0.503/0.01 = 50.3 → 50`，`−127`，`0.0219/0.01 = 2.19 → 2`（已实测）。反量化误差为 `[−0.003, 0, −0.0019]`，都不超过 `scale/2 = 0.005`。

- B：scale 按 128 计算并把最小值映射到 −128，这不是代码的做法（代码 `scale = abs_max / qmax`，`qmax = 127`）；
- C：−1.27/0.01 = −127，不会落到 −128；
- D：把 scale 误解为最大值本身。

对照：同一张量做 **4-bit** 对称量化，`scale = 1.27/7 ≈ 0.181`，`0.0219` 被量化成 0，小数值的信息全部丢失。

### Q4 — 答案：C

讲义："if one column has large values and another has small values, the small values lose most of their precision." 实测 STEP 3（第 0 行 ×15、第 42 行 ×8）：4-bit per-tensor SNR 4.56 dB，per-channel 16.26 dB。A 错：比特数相同；B 错：两者都不需要校准；D 错：离群值仍被量化，只是有了自己的 scale。

### Q5 — 答案：B

`scale = (1.55 − (−1.0)) / 255 = 0.01`；`zero_point = round(0 − (−1.0)/0.01) = 100`；`q(0.0) = round(0/0.01 + 100) = 100`（实测 `[−1.0, 0, 0.37, 1.55] → [0, 100, 137, 255]`）。zero-point 正是"实数 0 对应的整数"，这保证 0 能被精确表示（对 padding、ReLU 输出很重要）。A 是对称量化里 0 的位置；C 是"把区间中点当 0"的误解；D 是把 1.55 当成整数。

### Q6 — 答案：D

讲义："Weights (most robust) ... Activations (moderate sensitivity) ... KV cache (high sensitivity) ... Attention logits (most sensitive)." 注意本节代码的 STEP 5 实验结果与这个顺序几乎相反，原因见 Q12。

### Q7 — 答案：A

讲义："Gradients flow through the fake quantization using the straight-through estimator (STE): pretend the rounding operation has gradient 1." B 描述的是 PTQ 的校准；C 错，QAT 发生在训练中；D 说反了：讲义表格中 INT8 两者都 "Excellent"，QAT 的优势在 INT4/INT2。

### Q8 — 答案：C

A 错：GGUF 是文件格式，不是算法（里面的 Q4_K_M 等是 llama.cpp 的量化方案）；B 描述的更接近 LLM.int8() 的"离群值保留高精度"思路，AWQ 的做法是缩放而不是混合精度存储；D 错：GGUF 面向 CPU 与 Apple Silicon（讲义："designed for CPU inference and Apple Silicon"）。

### Q9 — 参考答案

1. **缺少进位**。`1.97 = 1.97 × 2^0`，尾数 `0.97 × 8 = 7.76`，四舍五入为 8，即 `1 + 8/8 = 2.0`，此时应**进位到下一个指数**得到 `1.0 × 2^1 = 2.0`。代码把尾数截在 0.875，结果是 1.875，误差从 0.03 变成 0.095。同理 `0.99 = 1.98 × 2^−1` → 应为 1.0，代码给 0.9375；`3.9` → 应为 4.0，代码给 3.75（均已实测）。修正：若 `round(m × 8) == 8`，则 `exp += 1, m = 0`（并在超过 448 时饱和）。
2. **没有次正规数（subnormal）**。代码把指数下限钳在 −6，于是所有小于 `2^−6` 的数都被当作 `1.0 × 2^−6` 处理，结果反而**变大**成 0.015625（0.00073 被放大约 21 倍，1.2e−6 被放大约 1.3 万倍）。真实 E4M3 在指数位为 0 时表示 `(m/8) × 2^−6`，步长 `2^−9 ≈ 0.00195`。`0.00073 / 0.00195 ≈ 0.37`，舍入为 0，所以正确结果是 **−0.0**（误差 0.00073，而不是 0.0149）。同理 0.003 应为 `2 × 2^−9 ≈ 0.0039`。
3. 代码 `bf16_bits = (fp32_bits >> 16)` 直接丢掉低 16 位，是**截断**（向零舍入）。0.1 的 FP32 位模式为 `0x3DCCCCCD`，被丢弃部分的最高位是 1，按就近舍入应进位为 `0x3DCD`，即 **0.10009766**，误差约 0.0000977，比截断的 0.00039 小约 4 倍（已实测）。硬件和 PyTorch 的 FP32→BF16 转换默认就近舍入。

附带一点：FP32 那一行的 Error 恒为 0，是因为代码返回的是 `float(value)`（原始 Python float），而不是 `float(np.float32(value))`；0.1 存成 FP32 后的真实误差约 `1.49e−9`。

### Q10 — 参考答案

1. 按行量化时，行 i 的 scale 与该行的最大绝对值成正比：`round(s·w / (s·max|w|/qmax)) = round(w / (max|w|/qmax))`，**s 被约掉了**。量化出的整数完全相同，反量化后乘 `s·scale` 再除以 s，结果也相同。所以在"缩放维度 = 量化分组维度"时，任何缩放都是无效的。
2. 不一致。代码 `scale_factors[idx] = min(4.0, mean|W| / max|W[idx]|)`，对显著行通常小于 1（实测 0.295、0.334），是**缩小**而不是放大。另外校准输入是随机的 `randn × 0.1`，选出的显著行 `[146, 115]` 与真正的离群行 `[89, 13, 16, 83, 141]` 毫无关系。`qmin`、`qmax` 在函数里也是算了没用。
3. 真实 AWQ（以 PyTorch 的 `W` 形状 `(out, in)`，`y = W x` 为例）：
   - 缩放作用在**输入通道**上：`y = (W·diag(s)) (diag(s)^−1 x)`，把显著输入通道 j 的权重列乘以 `s_j > 1`，对应的激活除以 `s_j`；
   - 量化分组在**输出通道 / 沿输入维度的 group**上（如每行每 128 个输入一组）；
   - 因为一个量化组里同时包含显著和非显著输入通道，放大显著通道让它们相对于组内 scale 的舍入误差变小，而组内最大值通常不变（或只略增），其他权重的精度几乎不受影响；
   - `s` 通过在校准数据上网格搜索 `s = mean|x_j|^α`，最小化输出误差 `‖Q(W·diag(s))(diag(s)^−1 X) − W X‖` 来确定。
   本节代码的缩放维度（行 = 输入通道）与量化分组维度（也是行）重合，所以效果为零。

### Q11 — 参考答案

1. 离群值在**行**上：5 个离群行在每一列里都有一个 ×10 的元素，于是每一列的 `max|w|` 都由离群行决定，其余 251 个正常权重只能分到很少的量化级别——每列一个 scale 几乎等同于 per-tensor。而"每行一个 scale"恰好把 5 个离群行隔离开。纯按列量化的 MSE 0.000173 与"Simulated GPTQ"的 0.000176 几乎一样，说明 GPTQ 部分的差距主要来自分组方向，**补偿还让误差略增**。结论：per-channel 有效的前提是 scale 的分组方向与离群值的方向一致。
2. 在 `y = x @ W` 中，第 j 列只决定第 j 个输出 `y_j = x · W[:, j]`。第 col 列的舍入误差只影响 `y_col`；把这个误差加到 `W[:, col+1]` 上，只会给 `y_{col+1}` 引入**新的**误差，而不会抵消 `y_col` 的误差。所以这种"跨输出列补偿"在数学上只会增加输出误差。此外 `importance_weights` 来自随机输入的 Hessian 对角线，几乎是常数；系数 0.1、"只补后 3 列"都是任意设定。
3. 真实 GPTQ 对每个**输出通道**（PyTorch 权重的一行）独立优化 `‖w X − ŵ X‖²`：按输入维度逐个量化权重 `w_q`，然后用 Hessian `H = 2XXᵀ` 的逆，把误差 `(w_q − ŵ_q)/[H^−1]_qq · H^−1_{q,:}` 分配到**同一输出通道中尚未量化的其他输入权重**上。由于这些权重与 `w_q` 作用在同一个输出上，且输入之间相关（H 的非对角项），补偿才能真正降低输出误差。工程实现还会用 Cholesky 分解、按块（lazy batch）更新以加速，并配合 group size（如 128）使用。

### Q12 — 参考答案

1. 这一行不是量化，而是给 logits 加了**标准差为 logits 标准差 5% 的高斯噪声**，与 `num_bits` 无关；`sensitivity_experiment` 开头 `np.random.seed(42)`，所以两次的噪声完全相同，结果也完全相同（60.05 dB）。
2. 注意力几乎是**均匀分布**（16 个位置，权重都在 0.0625 附近）。输入是 `randn × 0.1`，q·k 很小，logits 的标准差只有约 0.018，softmax 处于接近线性的平坦区，加 5% 的噪声（约 0.0009）对权重几乎没有影响。真实模型的注意力往往很尖锐（少数位置权重接近 1），这时 logits 的小扰动可能改变"注意哪个位置"，误差会被 softmax 放大。实测把输入放大 30 倍后，最大注意力权重变为 0.99999。
3. "Weights only" 同时量化了 `qkv` 和 `out` 两个矩阵，误差来源最多，而其他实验只量化一个张量；这几个实验施加的扰动"量"并不可比。
4. 改进建议：
   - 让输入/权重尺度更真实，使注意力分布足够尖锐（或直接构造带离群通道的激活）；
   - 对 attention logits 做**真正的** INT8/INT4 量化（例如按行对称量化），与其他组件用同样的比特数和粒度比较；
   - 每个实验只量化一个张量，或报告"每量化 1 个参数带来的输出误差"；
   - 加入因果 mask 和多层堆叠，观察 KV cache 误差随序列长度、层数的累积；
   - 多个随机种子取平均，报告方差。

### Q13 — 参考回答要点

- **权重**：FP16 = 140 GB（放不下）；FP8 = 70 GB；INT4 = 35 GB（另加 group scale 开销，group 128 时约多 3%）。
- **KV cache**（每 token `2 × 层数 × KV头数 × head_dim × 字节`）：`2 × 80 × 8 × 128 × 2 B = 327,680 B`，32K token ≈ **10.7 GB/序列**（FP16）；FP8 KV 减半约 5.4 GB。若不用 GQA（64 个 KV 头）则是 85.9 GB。讲义写 "For a 70B model at 32K context, the KV cache alone is 40GB in FP16"，按上述配置单条序列算不出 40 GB，大约相当于 4 条并发序列，引用时要说清口径。
- **方案**：
  - FP8 权重（70 GB）+ FP8 KV：单序列约 75 GB，再加激活与框架开销，几乎没有并发余量，适合 H100（原生 FP8）低并发场景；
  - INT4 权重（AWQ/GPTQ，约 36 GB）+ FP8/FP16 KV：剩余约 40 GB 给 KV cache，可支持 3–7 条 32K 并发，吞吐更高，但要验证 INT4 质量；
  - 或者两卡张量并行 FP16/FP8，质量最好但成本翻倍。
- 加分点：统一 GB 与 GiB 的口径（见 Q2），并把框架预留、CUDA context、激活峰值也算进去。

### Q14 — 参考回答要点

- **权重**：训练后固定，大致是以 0 为中心的类高斯分布，可以离线逐通道或逐组精细选择 scale，还能用校准数据做误差补偿。
- **激活**：随输入变化，必须在线量化；动态范围大，并存在**系统性离群通道**（讲义："A single attention head might produce activation values 100x larger than the mean"），这些离群值对模型质量至关重要。per-tensor 量化时，一个离群通道就会把其他所有通道压缩到很少的量化级别。
- **LLM.int8()**：检测幅值超过阈值（论文与讲义练习 4 中为 6）的特征维，把这些维以 FP16 计算，其余维用 INT8 矩阵乘，再把两部分结果相加（混合精度分解）。
- **SmoothQuant**：利用 `Y = (X·diag(s)^−1)(diag(s)·W)` 的等价变换，把激活的离群幅度"迁移"到权重上，让激活和权重都容易量化，从而实现 W8A8。
- 其他手段：per-token 激活 scale、per-channel 权重 scale、FP8（指数位让它对离群值更宽容）。
- 加分点：本节 STEP 3 的离群行实验与 Q11 说明，scale 的分组方向必须与离群值的方向匹配。

### Q15 — 参考回答要点

- **共同目标**：不是最小化权重误差 `‖W − Ŵ‖`，而是最小化**层输出误差** `‖WX − ŴX‖`；X 来自校准数据，所以都需要几十到几百条有代表性的样本（讲义："128 examples is typical"）。
- **GPTQ**：源自 Optimal Brain Quantization。对每个输出通道，按顺序量化输入维度上的权重；每量化一个，就用逆 Hessian（`H = 2XXᵀ`）把它的舍入误差分摊到尚未量化的权重上。逐层进行，一次性完成（one-shot），无需反向传播。讲义："the first method to make INT4 quantization practical for LLMs."
- **AWQ**：观察到约 1% 的权重因为对应的激活幅值大而格外重要；不做误差补偿，而是对输入通道做缩放 `W·diag(s)`、`X·diag(s)^−1`，让显著通道在量化网格上更精确；`s` 按激活幅度和网格搜索确定。不依赖反向传播和 Hessian 求逆，讲义："1.5-2x faster to apply"，质量与 GPTQ 相当或略好。
- **工程**：两者都常与 group size 128、INT4 权重 / FP16 激活（W4A16）一起使用；原始工具 AutoGPTQ、AutoAWQ 已归档，讲义推荐 GPTQModel 和 LLM Compressor。
- 常见误区：讲义说 GPTQ 让 "important weights get quantized more carefully"，更准确的说法是所有权重用同一个网格，靠**后续权重的补偿**来抵消误差。

### Q16 — 参考回答要点

- **困惑度**：在 WikiText-2 或业务语料的保留集上比较原始与量化模型；讲义经验值：增量 < 0.5 优秀，0.5–1.0 良好，1.0–2.0 多数任务可接受，> 2.0 说明出了问题。
- **任务 eval**：MMLU 等通用基准 + 自己的业务 eval（上一节）；重点看数学（GSM8K）和代码（HumanEval），讲义："Math and code tasks are more sensitive to precision loss."
- **输出对比**：同一批 prompt，原始 vs 量化模型，用 LLM-as-judge 计算"量化版不差于原版"的比例；检查长文本生成是否出现重复、乱码。
- **性能**：tokens/s、TTFT、显存峰值、不同 batch 下的吞吐；讲义："A quantized model that is slower than the original is worse than useless."
- **"坏了"的信号**：PPL 暴涨或 NaN；生成重复/乱码；某些层（常见于 embedding、lm_head、第一/最后一层）误差异常；特定语言或长上下文质量大幅下降。
- **修复手段**：增大校准集并使其贴近业务分布；减小 group size；把敏感层（embedding、lm_head）保留在 FP16/INT8（混合精度）；换 AWQ/GPTQ；仍不行则考虑 FP8 或 QAT。

### Q17 — 参考回答要点

- **不对**，至少不总是对。
- **decode 阶段**是显存带宽受限：每生成一个 token 都要把全部权重读一遍，权重变成 1/4，读取量减少，速度可以显著提升（但通常远小于 4 倍，因为还有 KV cache 读取、反量化开销、kernel 效率等）。讲义表格中 70B FP16 → INT4 约从 38 到 72–75 tokens/s，约 2 倍。
- **prefill 阶段**是算力受限：W4A16 方案中权重要先反量化成 FP16 再做矩阵乘，算力需求不变，甚至因反量化变慢；只有 INT8/FP8 这类"激活也低精度"的方案能用到更快的低精度张量核心（讲义：A100 INT8 624 TOPS vs FP16 312 TFLOPS；H100 上 FP8 提速 30–50%）。
- **硬件与内核**：没有高效 INT4 kernel 的平台可能更慢；讲义表格中 GGUF Q4_K_M 在 CPU 上只有 28 tokens/s。
- **大 batch** 时 decode 也逐渐转向算力受限，权重量化带来的收益会变小。
- 加分点：量化真正"白送"的是**能装下**（单卡跑 70B、腾出空间给 KV cache 提高并发），速度收益要按场景实测。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：浮点表示、溢出与下溢、舍入误差。
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：参数量与 KV cache 的估算方法。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../10-evaluation/docs/zh.md)：用 perplexity 与任务 eval 衡量量化损失。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的结构与显存占用。

### 本节被哪些后续内容用到
- [阶段 10 · 12 Inference Optimization](../../12-inference-optimization/docs/zh.md)：量化与 KV cache、批处理、推测解码等推理优化的组合。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：QLoRA 在 4-bit 量化底座上做微调。
- [阶段 17 · 09 生产环境中的 Quantization](../../../17-infrastructure-and-production/09-production-quantization/docs/zh.md)：AWQ、GPTQ、GGUF K-quants、FP8、MXFP4/NVFP4 的生产实践。
- [阶段 17 · 07 针对硬件的 Inference 编译](../../../17-infrastructure-and-production/07-tensorrt-llm-blackwell/docs/zh.md)：FP8 与 NVFP4 在新硬件上的落地。
- [阶段 17 · 12 边缘 Inference](../../../17-infrastructure-and-production/12-edge-inference/docs/zh.md)：端侧设备上的低比特部署。

### 延伸关键词
`FP8 E4M3 / E5M2` · `subnormal` · `round-to-nearest-even` · `per-channel / group-wise quantization` · `zero-point` · `PTQ / QAT` · `STE` · `GPTQ` · `AWQ` · `SmoothQuant` · `LLM.int8()` · `GGUF Q4_K_M` · `W4A16 / W8A8` · `KV cache quantization` · `perplexity delta`
