# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 11 节 Quantization：让模型装得下 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：第三方 `numpy`（无需 GPU、无需模型、无需网络）。同目录的 `main.rs` 是一个只实现对称量化与误差统计的 Rust 小版本，本文不展开。

---

## 1. 这份代码在考察什么

这份代码用 NumPy 把"量化"从比特层面一路演示到矩阵层面，共 7 个步骤：

1. **数字格式的位模式**：FP32、FP16、BF16 的 sign / exponent / mantissa，以及手写的 FP8 E4M3 模拟。
2. **显存估算**：不同参数量 × 不同精度的权重大小。
3. **量化的三种基本做法**：per-tensor 对称、per-channel 对称、per-tensor 非对称，以及 MSE / SNR / 余弦相似度三个误差指标。
4. **比特数扫描**：2/3/4/8/16 bit 的误差变化，找出质量"悬崖"。
5. **敏感度实验**：在一个单头注意力层里分别量化权重、激活、KV，并给 attention logits 加噪声。
6. **GPTQ / AWQ 的"模拟版"**：与朴素 per-tensor、per-channel 比较。
7. **权重分布**：模拟一组 std = 0.02 的权重并画直方图。

> 一句话：**量化 = 选 scale、取整、存整数 + scale；所有技巧都在回答"scale 怎么分组、误差怎么摊"。** 这份代码的 STEP 1–4 是可靠的教学实现；STEP 5、6 的"模拟实验"有明显的设计缺陷，结论与讲义不一致，读的时候要带着批判眼光（这也是本节最值得学的地方）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `float_to_fp32_bits` / `float_to_fp16_bits` / `float_to_bf16_bits` | 函数 | 用 `view` 取出位模式，拆出符号、指数、尾数 | 浮点格式 |
| `simulate_fp8_e4m3` | 函数 | 手算 E4M3 的指数与 3 位尾数 | FP8 |
| `display_format_comparison` | 函数 | 打印同一个数在 4 种格式下的存储值与误差 | 精度 vs 范围 |
| `quantize_symmetric` / `dequantize_symmetric` | 函数 | 整个张量一个 scale | per-tensor 对称量化 |
| `quantize_per_channel` / `dequantize_per_channel` | 函数 | 每行（axis=0）或每列一个 scale | per-channel 量化 |
| `quantize_asymmetric` / `dequantize_asymmetric` | 函数 | scale + zero-point，映射到 `[0, 2^b−1]` | 非对称量化 |
| `quantization_error` | 函数 | MSE、RMSE、最大误差、SNR(dB)、余弦相似度 | 误差度量 |
| `compare_quantization_methods` | 函数 | 三种量化方式并排比较 | 粒度与对称性 |
| `bit_width_sweep` | 函数 | 同一张量在不同比特下的误差 | 比特-质量曲线 |
| `simulate_transformer_layer` | 函数 | 单头注意力 + 输出投影（无 mask） | 注意力层 |
| `sensitivity_experiment` | 函数 | 分别扰动权重/激活/KV/logits | 敏感度层级 |
| `simulated_gptq` / `dequantize_gptq` | 函数 | 按输出列量化 + "误差补偿" | GPTQ（简化，见 3.8） |
| `simulated_awq` | 函数 | 按激活幅度选显著行并缩放 | AWQ（简化，见 3.9） |
| `full_quantization_comparison` | 函数 | 带离群行的矩阵上比较 4 种方法 + 端到端 matmul 误差 | 方法对比 |
| `memory_calculator` / `print_memory_table` | 函数 | 参数量 × 比特 / 8 / 1024³ | 显存估算（GiB） |

数据流：`__main__` 设种子 → STEP 1 格式表 → STEP 2 显存表 → STEP 3 构造 128×256 权重（第 0 行 ×15、第 42 行 ×8）做 8/4-bit 比较 → STEP 4 64×128 张量比特扫描 → STEP 5 INT8/INT4 敏感度 → STEP 6 256×512 矩阵（5 个离群行 ×10）四方法比较 → STEP 7 分布直方图。

---

## 3. 逐段精讲

### 3.1 读出浮点数的位模式

```python
def float_to_fp32_bits(value):
    bits = np.float32(value).view(np.uint32)
    sign = (bits >> 31) & 1
    exponent = (bits >> 23) & 0xFF
    mantissa = bits & 0x7FFFFF
    return {..., "value": float(value), "actual_exponent": int(exponent) - 127}
```

- `np.float32(value).view(np.uint32)`：**不改变内存中的 32 个比特**，只换一种类型去解读，于是得到 IEEE 754 的原始位模式。
- 右移 + 按位与取字段：符号是第 31 位；指数是 23–30 位（`0xFF` 是 8 个 1）；尾数是低 23 位（`0x7FFFFF`）。
- 指数有偏置：FP32 偏置 127、FP16 偏置 15，所以 `actual_exponent = exponent − bias`。正规数的值为 `(−1)^s × 1.mantissa × 2^actual_exponent`。
- `format(x, '08b')`：格式化为 8 位二进制字符串，不足补 0。
- ⚠️ FP32 返回的 `"value"` 是原始的 Python float（64 位），不是存进 FP32 之后的值，所以输出表里 FP32 的 Error 永远是 0。0.1 存入 FP32 的真实误差约 `1.49e−9`。应写成 `float(np.float32(value))`。

```python
def float_to_bf16_bits(value):
    fp32_bits = np.float32(value).view(np.uint32)
    bf16_bits = (fp32_bits >> 16).astype(np.uint16)
    ...
    reconstructed = np.uint32(bf16_bits.astype(np.uint32) << 16).view(np.float32)
```

- BF16 就是 FP32 的**高 16 位**：1 位符号 + 8 位指数 + 7 位尾数，所以范围与 FP32 相同。
- ⚠️ `>> 16` 直接丢掉低 16 位，是**截断**而不是就近舍入。0.1（`0x3DCCCCCD`）截断得 `0x3DCC` = 0.099609；按 round-to-nearest-even 应得 `0x3DCD` = 0.100098，误差小约 4 倍。PyTorch 与硬件转换默认就近舍入。一个常见的位运算实现是 `(bits + 0x7FFF + ((bits >> 16) & 1)) >> 16`。

### 3.2 FP8 E4M3 模拟

```python
def simulate_fp8_e4m3(value):
    sign = 1 if value < 0 else 0
    abs_val = min(abs(value), 448.0)
    ...
    exp = int(np.floor(np.log2(abs_val)))
    exp = max(-6, min(8, exp))
    mantissa_val = abs_val / (2.0 ** exp) - 1.0
    mantissa_quant = round(mantissa_val * 8) / 8
    mantissa_quant = max(0, min(0.875, mantissa_quant))
    reconstructed = (1.0 + mantissa_quant) * (2.0 ** exp)
```

- E4M3：4 位指数（偏置 7）、3 位尾数，最大值 448（`1.75 × 2^8`；全 1 的编码保留给 NaN）。先饱和到 448，再求指数 `floor(log2|x|)`，把 `|x|/2^exp ∈ [1, 2)` 的小数部分量化到 1/8 的网格。
- 正常范围内结果正确：0.1 → 0.1015625、3.14159 → 3.25、42.5 → 44（42.5 离 44 比离 40 更近）。
- ⚠️ **缺少进位**：尾数舍入到 8/8 时应进位到下一个指数，代码却截在 0.875。实测 1.97 → 1.875（应为 2.0）、0.99 → 0.9375（应为 1.0）、3.9 → 3.75（应为 4.0）。
- ⚠️ **缺少次正规数**：指数被钳在 −6，所有小于 `2^−6 = 0.015625` 的数都会被**抬高**到 `±0.015625`。输出表中 −0.00073 变成 −0.015625、1.2e−6 变成 0.015625。真实 E4M3 在指数字段为 0 时表示 `(m/8)·2^−6`，最小正数是 `2^−9 ≈ 0.00195`，−0.00073 应舍入为 −0。
- 结论：讲义说 FP8 适合权重和激活推理，前提是**先用 scale 把数值放进 FP8 的有效范围**。真实 FP8 推理（per-tensor 或 per-channel scale）也需要 scale，而不是像这里那样直接把原始数值塞进 FP8。

### 3.3 对称、per-channel、非对称量化

```python
def quantize_symmetric(tensor, num_bits=8):
    qmin = -(2 ** (num_bits - 1))
    qmax = 2 ** (num_bits - 1) - 1
    abs_max = np.max(np.abs(tensor))
    if abs_max == 0:
        return np.zeros_like(tensor, dtype=np.int32), 1.0
    scale = abs_max / qmax
    quantized = np.clip(np.round(tensor / scale), qmin, qmax).astype(np.int32)
    return quantized, float(scale)
```

- 8 bit 时 `qmin = −128, qmax = 127`；`scale = max|x| / 127`，所以 −128 实际不会被用到（这正是讲义写 "symmetric range (−127 to 127)" 的原因）。
- `np.round` 是**银行家舍入**（.5 舍入到偶数），这与讲义公式中的 round 一致即可。
- 全零张量返回 scale = 1.0，避免除以 0。
- 存储时整数用 `int32` 只是为了演示方便，真实系统会打包成 int8 或两个 int4 拼一个字节。

```python
def quantize_per_channel(tensor, num_bits=8, axis=0):
    if axis == 0:
        abs_max = np.max(np.abs(tensor), axis=1, keepdims=True)   # 每行一个
    else:
        abs_max = np.max(np.abs(tensor), axis=0, keepdims=True)   # 每列一个
    abs_max = np.where(abs_max == 0, 1.0, abs_max)
    scales = abs_max / qmax
    quantized = np.clip(np.round(tensor / scales), qmin, qmax).astype(np.int32)
    return quantized, scales.squeeze()
```

- `axis=0` 表示"沿第 0 维的每个位置一个 scale"，也就是**每行**一个。`keepdims=True` 让 `abs_max` 形状为 `(rows, 1)`，与 `(rows, cols)` 广播相除。
- `np.where(abs_max == 0, 1.0, abs_max)`：把全零行的最大值替换为 1，防止除零。
- ⚠️ 本文件中权重的形状是 `(d_in, d_out)`、前向为 `x @ W`，所以"每行"实际是**每输入通道**一个 scale，不是讲义所说的 "per output channel"。在重建误差的演示中这没有问题，但真实的整数矩阵乘法里，每输出通道的 scale 可以在乘完之后统一乘回去，而每输入通道的 scale 必须先作用在激活上（这正是 SmoothQuant/AWQ 那类"等价变换"做的事）。
- 本文件构造的离群值恰好都在**行**上（STEP 3 的第 0、42 行，STEP 6 的 5 个随机行），所以"每行一个 scale"能把它们完美隔离。实测在 STEP 6 的矩阵上改成"每列一个 scale"，MSE 从 0.0000228 升到 0.000173（约 7.6 倍）。per-channel 有效的前提是**分组方向与离群值方向一致**。

```python
def quantize_asymmetric(tensor, num_bits=8):
    qmin, qmax = 0, 2 ** num_bits - 1
    t_min, t_max = np.min(tensor), np.max(tensor)
    scale = (t_max - t_min) / (qmax - qmin)
    zero_point = int(np.round(qmin - t_min / scale))
    zero_point = max(qmin, min(qmax, zero_point))
    quantized = np.clip(np.round(tensor / scale + zero_point), qmin, qmax).astype(np.int32)
    return quantized, float(scale), int(zero_point)
```

- 把 `[t_min, t_max]` 线性映射到 `[0, 255]`。zero-point 是"实数 0 对应的整数"，例如 `[−1.0, 1.55]` 时 `scale = 0.01`、`zero_point = 100`。
- 反量化 `(q − zero_point) × scale`。
- 本函数是 **per-tensor** 的非对称量化。权重近似对称分布，所以它只比 per-tensor 对称略好（STEP 3：4-bit SNR 4.74 vs 4.56 dB），远不如 per-channel。非对称量化真正有优势的是 ReLU 输出这类单边分布。

### 3.4 误差度量

```python
def quantization_error(original, reconstructed):
    diff = original - reconstructed
    mse = float(np.mean(diff ** 2))
    signal_power = float(np.mean(original ** 2))
    snr_db = 10 * np.log10(signal_power / max(mse, 1e-20))
    ...
    cosine_sim = float(np.dot(orig_flat, recon_flat) / (norm_orig * norm_recon))
```

- **SNR（信噪比，分贝）**：`10·log10(信号功率 / 噪声功率)`。每提升 10 dB，误差功率降为 1/10。均匀量化的经验法则是**每多 1 bit 约提升 6.02 dB**（量化步长减半，噪声功率降为 1/4，`10·log10 4 ≈ 6.02`）。
- **余弦相似度**：只看方向，对整体缩放不敏感；0.99 听起来很高，但对应的 SNR 只有约 17 dB。
- `max(mse, 1e-20)`：防止 MSE 为 0 时 `log10` 得到无穷大。
- 这些都是**权重层面**的指标。讲义强调最终要看模型层面的 perplexity 和任务 eval。

### 3.5 比特数扫描

```python
    for bits in [2, 3, 4, 8, 16]:
        q, s = quantize_per_channel(tensor, bits, axis=0)
        ...
        compression = 32.0 / bits
```

- 统一用 per-channel 对称量化。注意 2 bit 对称时整数只有 `{−2, −1, 0, 1}`，正侧只有 1 个级别，非常粗糙。
- ⚠️ `compression = 32 / bits` 是**相对 FP32** 的压缩比，所以 4 bit 显示 8.0x、16 bit 显示 2.0x；讲义里"INT4 4x compression"是相对 FP16 的。另外它没有计入 scale 的存储（每行一个 float）。
- "16 bit" 一行是 16 位**整数**量化，不是 FP16。

### 3.6 显存表

```python
def memory_calculator(num_params_billions, bits_per_param):
    total_bytes = num_params_billions * 1e9 * bits_per_param / 8
    return total_bytes / (1024 ** 3)
```

- 单位是 **GiB**（2^30 字节），而讲义的"70B FP16 = 140GB"是十进制 GB（10^9 字节），所以表里显示 130.4G。两者差约 7%，估算时一定要统一口径。
- 只算了权重，没有 KV cache、激活、优化器状态。

### 3.7 敏感度实验

```python
def simulate_transformer_layer(input_data, weights, kv_scale=1.0):
    hidden = input_data @ weights["qkv"]
    seq_len = hidden.shape[1]
    d_model = weights["qkv"].shape[1] // 3
    q, k, v = hidden[:, :, :d_model], hidden[:, :, d_model:2*d_model], hidden[:, :, 2*d_model:]
    attn_scores = (q @ k.transpose(0, 2, 1)) / np.sqrt(d_model) * kv_scale
    ...
    attn_output = attn_weights @ v
    output = attn_output @ weights["out"]
```

- 一个**单头、无因果 mask** 的注意力层：`qkv` 是合并的 `(64, 192)` 投影，切片拆成 Q、K、V；`seq_len`、`kv_scale` 实际未被使用。
- 形状：输入 `(2, 16, 64)` → `hidden (2, 16, 192)` → 分数 `(2, 16, 16)` → 输出 `(2, 16, 64)`。

`sensitivity_experiment` 做了四个实验：

| 实验 | 做法 |
|------|------|
| Weights only | `qkv` 和 `out` 都按行量化后重新前向 |
| Activations only | 只量化 `attn_output`（按 token 行），再乘 `out` |
| KV cache only | 只量化 K、V（按 token 行），重算注意力 |
| Attention logits (5% noise) | **不是量化**：给分数加标准差为"分数标准差 × 5%"的高斯噪声 |

- ⚠️ 实测结果的排序（INT8：logits < KV < 激活 < 权重）几乎与讲义的层级相反，原因有三：
  1. 输入 `randn × 0.1` 让 q·k 极小，分数标准差只有约 0.018，注意力权重全部在 `[0.0586, 0.0665]`，几乎是均匀的 1/16。softmax 处于平坦区，logits 上的小扰动几乎不改变输出。真实模型的注意力往往很尖锐，此时 logits 误差会被放大。
  2. logits 实验加的是噪声，强度与 `num_bits` 无关，所以 INT8 与 INT4 下数字完全相同（60.05 dB）。
  3. 权重实验同时量化了两个矩阵，扰动的"量"与其他实验不可比。
- `baseline_internals` 与 `fresh_internals` 是同一次计算的重复，前者没有被使用。
- 结论：这个实验只能说明"代码能跑"，不能支持讲义的敏感度结论。改进方法见测验 Q12。

### 3.8 "Simulated GPTQ"

```python
    H = np.zeros((n_in, n_in))
    for x in calibration_inputs:
        for row in range(x.shape[0]):
            xi = x[row].reshape(-1, 1)
            H += xi @ xi.T
    H /= len(calibration_inputs)
    H += np.eye(n_in) * 1e-4
    weight_importance = np.diag(H)
    ...
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

- `H = Σ x xᵀ` 是 GPTQ 中 Hessian（`2XXᵀ`）的雏形，加 `1e-4·I` 做阻尼，保证可逆——这两点是对的。但之后只用了**对角线**，而且校准输入是独立随机数，对角线近似常数，"重要性"几乎没有信息。逐行累加外积也可以写成一次矩阵乘 `X.T @ X`。
- 每个**输出列**一个 scale：本数据的离群值在行上，每列的最大值都由离群行决定，效果接近 per-tensor（见 3.3）。
- ⚠️ **补偿方向错误**：把第 col 列的误差加到后面的输出列上。在 `y = x @ W` 中，每一列只决定一个输出，跨列"补偿"只会给别的输出引入新误差。实测：不做补偿、纯按列量化的 MSE 为 0.000173，加上补偿后是 0.000176——补偿让结果变差。
- 真实 GPTQ：对每个输出通道，按**输入维度**逐个量化，把误差用 `H^−1` 分配到**同一输出通道中尚未量化的输入权重**上，目标是最小化输出误差 `‖wX − ŵX‖²`。详见测验 Q11、Q15。
- `dequantize_gptq` 用 Python 循环逐列相乘，等价于向量化写法 `quantized * scales[None, :]`。

### 3.9 "Simulated AWQ"

```python
    activation_magnitudes = mean over calibration of |x|      # 每个输入通道的平均激活幅度
    n_salient = max(1, int(n_in * salient_fraction))         # 256 × 1% → 2
    salient_indices = np.argsort(activation_magnitudes)[-n_salient:]
    for idx in salient_indices:
        scale_factors[idx] = min(4.0, 1.0 / (col_max + 1e-8) * np.mean(np.abs(weight_matrix)))
    scaled_weights = weight_matrix * scale_factors.reshape(-1, 1)
    quantized, scales = quantize_per_channel(scaled_weights, num_bits, axis=0)
    result = dequantize_per_channel(quantized, scales, axis=0) / scale_factors.reshape(-1, 1)
```

- 思路方向是对的：按激活幅度找显著的**输入通道**（权重的行），缩放后量化，再除回去（等价于把激活除以 s）。
- ⚠️ **缩放维度与量化分组维度重合**：缩放按行，量化也按行（每行一个 scale），`round(s·w / (s·max/qmax)) = round(w / (max/qmax))`，s 被约掉，结果与 per-channel 完全相同。STEP 6 中 AWQ 与 Per-channel 两行一模一样，实测最大差异 `6.9e−18`。
- ⚠️ **缩放方向相反**：`mean|W| / max|W_row|` 通常小于 1（实测 0.295、0.334），是缩小而不是讲义所说的 "scales them up"。
- ⚠️ 校准数据是随机的，选出的显著行 `[146, 115]` 与真正的离群行 `[89, 13, 16, 83, 141]` 无关；`qmin`、`qmax` 计算了但没用。
- 真实 AWQ：量化按输出通道（沿输入维度分 group）进行，缩放作用在输入通道上，一个 group 内显著通道被放大后获得更细的有效分辨率；s 通过网格搜索最小化输出误差得到。详见测验 Q10。

### 3.10 端到端比较与分布分析

- `full_quantization_comparison` 先比较权重误差，再用随机输入 `test_input @ W` 比较输出误差。输出层面的排序与权重层面一致：per-channel = "AWQ" < "GPTQ" < naive。
- STEP 7 生成 1000 个 std = 0.02 的高斯权重，统计落在 ±0.1、±0.05、±0.01 内的比例。这是模拟数据，不是在测 Llama 3 70B；讲义里"95% of them fall between −0.1 and +0.1"不能由这段代码验证。高斯分布下 ±0.01 只覆盖 40.7%（≈ ±0.5σ 理论值 38.3% 附近），说明"多数权重接近 0"不等于"都很小"。
- 直方图用 `np.histogram(..., bins=20)` 分 20 个等宽区间，按最大频数缩放成 40 个 `#`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `view` 读位模式 | 直观展示 IEEE 754 | BF16 用截断代替就近舍入；FP32 误差显示恒为 0 |
| 手写 FP8 模拟 | NumPy 没有原生 FP8 | 缺进位与次正规数；生产用硬件/框架的 FP8 类型（如 `torch.float8_e4m3fn`）并配 scale |
| 量化结果存 `int32` | 演示简单 | 真实存储会打包为 int8 / int4，并记录 group scale |
| per-channel = 每行 | 与构造的离群行匹配 | 与讲义"每输出通道"不一致；分组方向要匹配离群值方向 |
| 非对称量化只做 per-tensor | 代码短 | 优势不明显；ReLU 激活等单边分布才明显受益 |
| SNR / 余弦作为指标 | 便宜、可比 | 只反映权重误差；最终要看 PPL 与任务 eval |
| 显存除以 1024³ | 常见习惯 | 与讲义十进制 GB 不一致，需标注单位 |
| 敏感度实验用小尺度随机层 | 能快速运行 | 注意力近似均匀，logits 用噪声代替量化，结论与讲义相反 |
| 简化 GPTQ（对角 Hessian + 跨列补偿） | 不必求逆 Hessian | 补偿方向错误，反而增大误差；真实 GPTQ 用逆 Hessian 在输入维补偿 |
| 简化 AWQ（按行缩放 + 按行量化） | 代码短 | 缩放被约掉、等同 per-channel；方向也反了 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| NumPy 标量类型 | `np.float32(value)`、`np.float16(value)` | 按指定精度存储一个数 |
| `.view(dtype)` | `np.float32(v).view(np.uint32)` | 不改比特，换类型解读（位级"重新解释"） |
| 位运算 | `bits >> 31`、`& 0xFF`、`<< 16` | 右移、按位与、左移，用于取出位字段 |
| 十六进制字面量 | `0xFF`、`0x7FFFFF`、`0x3FF` | 位掩码 |
| `format(x, '08b')` | `format(int(exponent), '08b')` | 转二进制字符串，宽 8 位、补 0 |
| `.astype(...)` | `.astype(np.int32)`、`.astype(np.float64)` | 数组类型转换 |
| 幂与负号优先级 | `-(2 ** (num_bits - 1))` | `**` 优先级高于一元负号，加括号更清晰 |
| `np.clip` / `np.round` | `np.clip(np.round(t / s), qmin, qmax)` | 截断到区间；`np.round` 对 .5 取偶 |
| `np.where` | `np.where(abs_max == 0, 1.0, abs_max)` | 按条件逐元素选择 |
| `axis` / `keepdims` | `np.max(np.abs(t), axis=1, keepdims=True)` | 沿某一维规约并保留维度，便于广播 |
| `reshape(-1, 1)` | `scales.reshape(-1, 1)` | `-1` 让 NumPy 自动推断该维长度 |
| `.squeeze()` | `scales.squeeze()` | 去掉长度为 1 的维度 |
| 切片拆分 | `hidden[:, :, :d_model]` | 沿最后一维切出 Q、K、V |
| `transpose(0, 2, 1)` | `k.transpose(0, 2, 1)` | 交换后两维，用于 `Q @ Kᵀ` |
| 解包参数 `*` | `np.random.randn(*shape)` | 把元组展开成多个位置参数 |
| `np.argsort` | `np.argsort(mag)[-n:]` | 排序后的下标；取最后 n 个即最大的 n 个 |
| `np.random.choice(..., replace=False)` | 选 5 个不重复的离群行 | 无放回抽样 |
| 列表推导式 | `[np.random.randn(8, d_in) * 0.1 for _ in range(n)]` | 生成校准批次 |
| `sorted(dict.items(), key=lambda ...)` | `sorted(experiments.items(), key=lambda x: x[1]["mse"])` | 按嵌套字典中的值排序 |
| 元组列表迭代 | `for name, output in [("Naive", ...), ...]` | 成对遍历 |
| `np.histogram` | `np.histogram(w, bins=20)` | 返回 (计数, 边界) 两个数组 |
| f-string 格式符 | `{x:>14.6f}`、`{x:>12.8f}`、`{x:>7.1f}G`、`{c:>11.1f}x`、`{'-'*76}` | 右对齐宽度与小数位；字符串乘法画线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 7 个步骤 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy 2.5，耗时约 1 秒），节选：

```text
STEP 1:
  Value: 0.1
  FP32           0.100000   0.00000000   ← 显示的是原始值，见 3.1
  FP16           0.099976   0.00002441
  BF16           0.099609   0.00039063   ← 截断；就近舍入应为 0.100098
  FP8e4m3        0.101562   0.00156250
  Value: -0.00073
  FP16          -0.000730   0.00000004
  BF16          -0.000729   0.00000139
  FP8e4m3       -0.015625   0.01489500   ← 没有次正规数，被抬高到最小正规数
  Value: 1.2e-06
  FP16           0.000001   0.00000001   ← 指数位 00000：FP16 的次正规数
  FP8e4m3        0.015625   0.01562380

STEP 2:  70B  FP32 260.8G  FP16 130.4G  FP8 65.2G  INT8 65.2G  INT4 32.6G  INT2 16.3G   ← GiB

STEP 3 (8-bit):  Per-tensor SNR 22.52 | Per-channel 41.80 | Asymmetric 24.07
STEP 3 (4-bit):  Per-tensor SNR  4.56 | Per-channel 16.26 | Asymmetric  4.74
                 Max Error: per-tensor 0.0821 = per-channel 0.0821

STEP 4:  2 bit 2.25 dB | 3 bit 11.31 | 4 bit 18.66 | 8 bit 43.84 | 16 bit 92.05

STEP 5 (INT4):  logits(噪声) 60.05 | Activations 18.66 | KV 18.28 | Weights 15.57

STEP 6:  Naive 4.84 dB | Per-channel 17.31 | Simulated GPTQ 8.45 | Simulated AWQ 17.31
         Output cosine: Naive 0.816 | Per-channel 0.991 | GPTQ 0.927 | AWQ 0.991

STEP 7:  [-0.1, 0.1] 100.0% | [-0.05, 0.05] 98.8% | [-0.01, 0.01] 40.7% | max 0.0609
```

逐项解读：

- **STEP 1**：FP16 有 10 位尾数，在 0.1 附近误差约 2.4e−5；BF16 只有 7 位尾数，误差大一个数量级。3.14159 在 FP16 和 BF16 下恰好都存成 3.140625。FP16 对 1.2e−6 用到了次正规数（指数位全 0），所以还能表示；BF16 因为 8 位指数，用正规数就能表示。FP8 的误差大得多，而且模拟器对小数值的处理是错的。
- **STEP 2**：每降一档精度，显存减半；FP8 与 INT8 同为 1 字节。数字是 GiB。
- **STEP 3**：构造的第 0 行 ×15、第 42 行 ×8 是离群行。per-tensor 时 scale 由第 0 行决定，其余行只用到很少的级别；per-channel 让每行有自己的 scale，8-bit 下 SNR 从 22.5 提升到 41.8 dB。4-bit 时两者的 **Max Error 相同**（0.0821）：最大误差出现在第 0 行内部，而第 0 行在两种方式下的 scale 相同（它本身就是全局最大值所在行）。非对称量化在近似对称的权重上只略有改善。
- **STEP 4**：每多 1 bit 约多 6 dB——4→8 bit 提升 25.2 dB（约 6.3 dB/bit），8→16 bit 提升 48.2 dB（约 6.0 dB/bit）。2→3→4 bit 分别是 2.25、11.31、18.66 dB，低比特区间每少 1 bit 损失越来越大，这就是"质量悬崖"。
- **STEP 5**：排序与讲义层级相反，原因见 3.7。不要把这个结果当作结论引用。
- **STEP 6**：per-channel 最好；"Simulated AWQ" 与 per-channel 完全相同（缩放被约掉）；"Simulated GPTQ" 比 per-channel 差约 7.7 倍，只比 naive 好（按列分 scale 不能隔离离群行，补偿方向错误）。讲义说 "AWQ typically matches or slightly beats GPTQ quality"——在这份代码里看到的差异来自实现缺陷，不代表真实算法的对比。
- **STEP 7**：std = 0.02 的高斯分布里没有任何值超出 ±0.1（最大 0.0609），平均绝对值 0.0157（理论值 `0.02·√(2/π) ≈ 0.016`）。

---

## 7. 动手改一改

1. **修复格式模拟**：给 `simulate_fp8_e4m3` 加上尾数进位与次正规数处理；给 BF16 改成就近舍入；FP32 显示真实存储值。用 `[1.97, 0.99, 0.00073, 0.003, 447, 500]` 验证。
2. **讲义练习 1（group 量化）**：把每行切成 32/64/128/256 个元素一组、每组一个 scale，比较 SNR 与"每个权重平均多出的 scale 比特数"（FP16 scale、group 128 时约 0.125 bit/权重）。
3. **验证分组方向**：把 STEP 6 的离群值从"行"改成"列"（`weight[:, cols] *= 10`），重新比较按行与按列的 per-channel 量化，体会"分组方向必须与离群方向一致"。
4. **写一个真正的 AWQ 玩具版**：量化改为"每列（输出通道）一个 scale"，校准输入中人为放大 2 个输入通道的幅度，对这些通道的权重行乘以 `s = mean|x_j|^α`（α 在 0–1 网格搜索），以**输出误差** `‖X W − X Ŵ‖` 选最优 α，与不缩放的结果对比。
5. **写一个真正的 GPTQ 玩具版**：对每个输出列，按输入维度逐个量化，用 `H^−1 = (XᵀX + λI)^−1` 把误差分配给同列中尚未量化的权重；比较输出误差与 per-column RTN（直接舍入）。
6. **讲义练习 4（离群值感知）**：在 STEP 5 的层中人为制造几个激活离群通道，用 3x/6x/10x 阈值把它们保留在 FP16、其余量化为 INT8，测端到端误差；同时把输入尺度调大，让注意力变尖锐，重新做 logits 的真实 INT8 量化。

---

## 8. 常见坑

- **GB 与 GiB 混用**：同一个 70B FP16 模型，140 GB = 130.4 GiB。
- **以为 BF16 就是 FP32 截断**：截断只是最简单的近似，标准转换是就近舍入。
- **低精度浮点不处理次正规数和进位**：手写模拟时最容易出错的两个地方。
- **per-channel 的"channel"指哪一维**：对 `x @ W`（W 为 `(in, out)`），输出通道是列；PyTorch 的 `nn.Linear.weight` 形状是 `(out, in)`，输出通道是行。搞错方向，量化的效果和可实现性都会变。
- **在缩放维度上做量化分组**：缩放会被约掉，AWQ 式的等价变换失去作用。
- **"误差补偿"补到了别的输出上**：只有作用于同一输出的权重之间才能互相补偿。
- **只看权重 MSE**：真正关心的是层输出误差与模型级指标（PPL、任务准确率）；GPTQ/AWQ 都以输出误差为目标。
- **用噪声代替量化做敏感度实验**：噪声强度与比特数无关，结论不能迁移到量化。
- **在注意力近似均匀的玩具层上下结论**：真实模型的注意力很尖锐，softmax 对 logits 误差的放大才会显现。
- **只看压缩比不看 scale 开销**：group 越小，scale 越多，实际每权重比特数会超过 4。
- **中文讲义的机翻错误**：`docs/zh.md` 把 "GPTQ" 译成了"通用计算机"（如"步骤6:模拟通用计算机"），阅读时以英文版为准。
