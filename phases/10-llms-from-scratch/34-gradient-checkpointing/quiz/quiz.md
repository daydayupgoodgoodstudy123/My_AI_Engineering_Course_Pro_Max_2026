# 测验 · Gradient Checkpointing 与激活重计算（Gradient Checkpointing and Activation Recomputation）

> **阶段 10 · 从零构建 LLM · 第 34 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机翻，部分句子已失真（如开头把 "3 TB" 译成"肺结核"），有疑义处以英文版为准。另外讲义里 `L` 时而表示**序列长度**（`12 * B * L * d`、`L^2`），时而表示**层数**（`sqrt(L)` 规则），阅读时要注意区分；本测验统一用 S 表示序列长度、L 表示层数。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 反向传播需要什么 | 线性层求 `grad_W = inputᵀ @ grad_output` 需要输入；ReLU/GELU/softmax 的导数需要激活值本身。autograd 默认把这些全部存下来 |
| 2 | 激活显存的量级 | 讲义估算每层约 `12·B·S·d` 个值；d = S = 8192、B = 1、BF16 时每层约 1.61 GB，64 层约 103 GB，远超权重 + 优化器之外剩下的显存 |
| 3 | Gradient checkpointing | 把网络分成若干段，forward 时只存每段的**输入**，backward 时重跑该段 forward 恢复中间结果再求导：用算力换显存 |
| 4 | 全量重计算的代价 | backward ≈ 2 倍 forward；多做一次完整 forward 后一步从 3 个单位变为 4 个，总 FLOPs 多约 33%（forward 部分多 100%） |
| 5 | √L 规则 | Chen 等（2016）：L 层均匀成本时每 √L 层设一个 checkpoint，存储与重算都按 √L 增长；L = 64 时为 8 |
| 6 | 激活的结构差异 | attention softmax 输出 `B·heads·S²`，随序列长度**平方**增长；FFN 隐层 `B·S·4d` 线性增长；长序列时 softmax 主导 |
| 7 | Selective checkpointing | Korthikanti 等（2022）：只重算"存起来贵、算起来便宜"的 attention 部分，其余保留；讲义：约 5% FLOP 开销换约 5 倍显存节省 |
| 8 | Offload | 不重算，而是把激活搬到 CPU 内存、backward 时搬回；当传输时间（可与计算重叠）小于重算时间时更划算 |
| 9 | 何时不必 checkpoint | 已用 FlashAttention 时它本身不存 S×S 矩阵、backward 时重算 softmax，selective 的收益变小；流水线中正在进行中的层 |
| 10 | 与并行/低精度的交互 | TP 下重算要重新 gather 输入；PP 下每个 stage 的 forward 常整体 checkpoint；FP8 重算时 amax 历史必须与原 forward 一致，否则 scale 漂移 |

### 核心技能（能动手做到）

- [ ] 用 NumPy 写出分段 checkpoint 的 forward/backward，并验证梯度与不做 checkpoint 时逐位一致
- [ ] 给定 L、k，算出重算 FLOP 开销与激活显存，并能指出"成本模型"与"实现"之间的不一致
- [ ] 推导 √L 规则，并说明当"段内中间激活"远大于"段输入"时最优段长如何变化
- [ ] 估算一层 transformer 的激活显存（含/不含 S² 项），判断何时 attention 主导
- [ ] 比较 recompute 与 offload 的时间，算出 PCIe 带宽的盈亏平衡点
- [ ] 在 PyTorch 中正确使用 `torch.utils.checkpoint.checkpoint`，并知道 dropout/RNG、FP8 scale 等重算一致性问题

---

## 二、基础自测（选择题）

**Q1.** 对一个 L 层、每层成本相同的网络做"每层都 checkpoint、backward 时每层重算一次 forward"。设 backward 的 FLOPs 约为 forward 的 2 倍，则每步训练的**总** FLOPs 大约增加：

- A. 100%
- B. 50%
- C. 33%
- D. 5%

**Q2.** 按讲义的估算"每层激活约 `12·B·S·d` 个值"，取 d = 8192、S = 8192、B = 1、BF16（2 字节/值），每层激活与 64 层总激活分别约为：

- A. 每层约 1.61 GB，64 层约 103 GB
- B. 每层约 800 MB，64 层约 51 GB
- C. 每层约 134 MB，64 层约 8.6 GB
- D. 每层约 1.61 GB，64 层约 51 GB

**Q3.** 下列哪一类激活随序列长度 S **平方**增长，因此在长上下文训练中最先成为显存大头？

- A. FFN 隐层激活 `B·S·4d`
- B. 残差流 `B·S·d`
- C. Q/K/V 投影输出 `3·B·S·d`
- D. attention softmax 输出 `B·heads·S·S`

**Q4.** 按 Chen 等（2016）的 √L 规则，一个 64 层、各层成本相同的网络应每隔多少层放一个 checkpoint？

- A. 4
- B. 8
- C. 16
- D. 32

**Q5.** 本节 `checkpoint_cost(64, selective=True)` 假设 attention 占单层 forward 的 15%，只重算 attention。它报告的 FLOP 开销是：

- A. 15%
- B. 5%
- C. 0.15%
- D. 33%

**Q6.** 关于 FlashAttention 与 selective checkpointing 的关系，正确的是：

- A. FlashAttention 会把完整的 S×S softmax 存下来，所以更需要 selective checkpointing
- B. 两者互斥，开了 FlashAttention 就不能再用任何 checkpoint
- C. 用了 FlashAttention 后任何层都不再需要 checkpoint
- D. FlashAttention 本身不物化完整的 S×S 注意力矩阵、backward 时重算 softmax，所以在它之上再做 attention 的 selective 重算收益有限

**Q7.** 何时选择 activation offload（搬到 CPU）比重算更合适？

- A. 该层激活经 PCIe 传输的时间（可与计算重叠）小于其重算时间，且 CPU 内存充足
- B. 任何时候都应优先 offload，因为它不增加 FLOPs
- C. 只有当 GPU 算力闲置、显存充足时
- D. 当使用 FP8 训练时必须用 offload 代替重算

**Q8.** 运行 `main.py` 打印 `equivalence: {'output_match': True, 'max_grad_diff': 0.0}`，梯度差**恰好为 0**。最主要的原因是：

- A. 代码内部全部使用 float64，误差小到打印成 0
- B. 随机初始化恰好让梯度都是 0
- C. 重算时以完全相同的输入、按完全相同的顺序执行完全相同的 NumPy 运算，CPU 上结果逐位一致
- D. `model_backward_checkpointed` 实际没有计算梯度，而是复制了 `model_backward` 的结果

---

## 三、动手 / 代码题

**Q9.** 运行 `main.py` 得到：

```text
k=  1  overhead=0.0%
...
k= 64  overhead=32.8%
activation memory (no ckpt), L=64, d=8192, seq=8192, batch=1: 103079.2 MB
  checkpoint k=  1: 8724.2 MB
  checkpoint k=  8: 2147.5 MB
```

相关代码：

```python
        recompute = n_layers * flops_per_layer * (
            (segment_size - 1) / max(segment_size, 1)
        )
...
    per_layer = 12 * batch * seq * hidden * bytes_per_value      # activation_memory_mb
...
    saved = (n_seg + segment_size) * batch * seq * hidden * bytes_per_value   # memory_after_checkpoint
```

"k = 1 时零 FLOP 开销、显存却从 103 GB 降到 8.7 GB"——这是免费的午餐吗？

1. 请指出成本模型与显存模型各自隐含的假设，说明二者为什么互相矛盾。
2. 讲义说"32 层分成 32 段、每段 1 层"的开销是多少？与代码 k = 1 的输出是否一致？
3. 请给出一个自洽的模型：每层内部激活 12 个单位、层输入 1 个单位（1 单位 = `B·S·d·2` 字节 ≈ 134.2 MB），算出 k = 1、2、8 时的峰值激活显存，以及该模型下的最优 k。

**Q10.** 统计 `model_backward_checkpointed` 实际调用了多少次 `layer_forward`：

```python
    for seg_idx in range(n_seg - 1, -1, -1):
        start = seg_idx * k
        end = min(start + k, len(params))
        x_in = saved_inputs[seg_idx]
        _, seg_acts = model_forward(x_in, params[start:end])
        g, seg_grads = model_backward(g, seg_acts, params[start:end])
```

1. 6 层、k = 2 时，backward 中重算了几次 `layer_forward`？`checkpoint_cost` 的公式 `L·(k−1)/k` 预测的是几次？
2. 为什么每段的最后一层其实不需要重算？改一行代码让实际重算次数与公式一致，并说明如何验证改动正确。
3. 再看 `layer_backward` 的开头 `h_pre = linear_forward(x_in, w1, b1)`。这说明"不做 checkpoint 的基线"实际上存了什么、没存什么？

**Q11.** 估算 recompute 与 offload 的盈亏平衡。假设：一层激活 1.61 GB（BF16、`12·S·d`，d = S = 8192）；一层 forward 约 `1.54 × 10¹³` FLOPs（含 attention 矩阵乘）；GPU 有效算力 400 TFLOPS；PCIe 有效带宽 25 GB/s；offload 的传输可与计算完全重叠。

1. 重算一层需要多少毫秒？把一层激活单向搬到 CPU 需要多少毫秒？
2. 按配套 skill 的规则（传输时间 > 重算时间则拒绝 offload），这层该选哪种？
3. PCIe 有效带宽至少达到多少，offload 才不慢于重算？

**Q12.** 阅读 `should_recompute`：

```python
def should_recompute(layer_type, activation_bytes_mb, recompute_flops_ratio):
    if layer_type == "attention" and activation_bytes_mb > 100:
        return True
    if layer_type == "ffn" and activation_bytes_mb > 500:
        return recompute_flops_ratio < 0.1
    return False
```

1. 写出以下调用的返回值：`("attention", 150, 0.5)`、`("ffn", 600, 0.2)`、`("ffn", 600, 0.05)`、`("ffn", 400, 0.01)`、`("norm", 10000, 0.0)`。
2. 讲义 Step 7 的同名函数参数是 `activation_bytes`、阈值写作 `100 * 1e6`；代码改成了 `activation_bytes_mb` 和 `100`。这种改动最容易引发什么 bug？
3. 这个决策函数缺少哪些生产中必须考虑的输入？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 gradient checkpointing？它解决什么问题、代价是什么？`torch.utils.checkpoint` 大致是怎么工作的？

**Q14.**（原理深挖）请推导：①全量重计算为什么是约 33% 的额外开销；②为什么最优 checkpoint 间隔是 √L；③如果段内中间激活远大于段输入（例如 12 : 1），最优间隔会怎样变化？

**Q15.**（工程实践）训练一个 64 层、d = 8192、S = 8192 的模型时单卡 OOM。你会按什么顺序尝试哪些手段？selective、full、offload 分别在什么条件下选？

**Q16.**（追问型）重算时"第二次 forward"必须与第一次完全一致。哪些因素可能让两次不一致？分别怎么处理？

**Q17.**（场景设计）为长上下文（S = 32K）训练设计一套逐层的激活策略，并说明你如何验证它既放得下、又没有浪费算力。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的成本模型：不 checkpoint 时一步 = forward 1 + backward 2 = 3 个单位；全量重算多一次 forward，变为 1 + 1 + 2 = 4，`4/3 − 1 ≈ 33%`。A 是"forward 部分"的增幅（forward 从 1 变 2，+100%），不是整步；讲义开头写"33% more forward-pass FLOPs"的措辞不严谨，准确说是整步 FLOPs 多 33%。B 没有依据；D 是 selective 的开销。

### Q2 — 答案：A

`12 × 1 × 8192 × 8192 = 805,306,368` 个值，× 2 字节 = 1.61 GB/层；× 64 = 103.08 GB，与代码输出 `103079.2 MB` 一致。B 是**讲义正文**的数字（"800 MB/layer in BF16 … 51 GB"）——它其实是"值的个数"（805M 个值、64 层 51.5G 个值），相当于按 1 字节/值算，BF16 下少算了一半。C 是 1 个"单位"（`B·S·d·2` 字节 = 134.2 MB），漏了系数 12。D 混用了两种口径。

### Q3 — 答案：D

softmax 输出（以及 attention dropout mask 等）是每个头一个 S×S 矩阵，体积 `B·heads·S²`，S 翻倍它变 4 倍。其余三项都与 S 成正比。讲义："The attention softmax output is `B*L*L*heads` and grows quadratically"。这正是 selective checkpointing 只重算 attention 的原因。

### Q4 — 答案：B

`√64 = 8`，代码 `optimal_segment(64)` 也返回 8。直觉：存 L/k 个段输入 + 重算时一段内 k 层的中间结果，`L/k + k` 在 `k = √L` 时最小。A、C 都比最优多存约 25%（按代码模型：k = 4 或 16 时 20 个单位，k = 8 时 16 个单位）；D 偏离更大。

### Q5 — 答案：B

`fwd = 64`、`recompute = 64 × 0.15 = 9.6`、`bwd = 128`，`(64 + 9.6 + 128) / (64 + 128) − 1 = 0.05`，即讲义 `(3 + 0.15)/3 − 1 = 5%`。A 把"重算 15% 的 forward"误当成整步开销；C、D 不对。注意 15% 是讲义给的假设值，真实比例随 S 增长而变大（attention 的 FLOPs 也有 S² 项）。

### Q6 — 答案：D

FlashAttention 分块计算注意力，只存 softmax 的归一化统计量（每行的 max 与 sum），backward 时重新计算注意力分数，所以 S² 的激活本来就不存在。讲义 When Not to Checkpoint："Flash already recomputes the softmax fast, so additional layer-level checkpointing adds little on top"；配套 skill 也要求"若 kernel 已重算 softmax，就把 attention 的 selective 降级为 none"。A 说反了；B、C 过度推断——FFN、残差等线性项仍可能需要 checkpoint。

### Q7 — 答案：A

讲义："beneficial when idle bandwidth exceeds the cost of rematerialization"；skill："Refuse offload when the layer's measured activation transfer time … exceeds its measured recompute time"。B 忽略了 PCIe 带宽限制（见 Q11，常常是传输更慢）；C 正好相反——显存充足就不需要 offload；D 是混淆，FP8 的问题是重算时 amax/scale 一致性，不是必须 offload。

### Q8 — 答案：C

`model_backward_checkpointed` 从保存的段输入出发，调用同一个 `model_forward` 重算，得到与第一次 forward **完全相同**的中间张量，再调用同一个 `model_backward`。运算、顺序、dtype（float32，A 错）都一样，CPU 上的 NumPy 结果是确定性的，所以差值严格为 0。我们另外测试了 7 层 k=3、6 层 k=4、5 层 k=1、5 层 k=10，差值都是 0.0。在 GPU 上若使用非确定性 kernel（如某些 atomic add 的归约）或 TF32/不同的算法选择，差值可能是 1e-7 量级而非 0，此时应改用 `allclose` 判断。B、D 不成立：输出也逐一比较过。

### Q9 — 参考答案

1. **两个模型的隐含假设不同**：
   - **FLOP 模型**（`(k−1)/k`）把"层"当作原子：backward 只需要每层的**输入**，所以 k = 1（存下每层输入）时不需要任何重算；段长为 k 时，每段只需重算前 k−1 层。
   - **基线显存模型**（`12·B·S·d`/层）假设每层内部有 12 个单位的中间激活必须保存。
   - **checkpoint 后的显存模型**（`n_seg + k`）又假设"正在重算的段"中每层只占 1 个单位。
   - 三者放在一起就得出"k = 1 不重算、显存却省 12 倍"的结论。真实情况是：要把每层内部 12 个单位的激活丢掉，backward 时就必须重算层内部，至少付出约 33% 的代价。
2. 讲义："32-layer transformer split into 32 segments of 1 layer each … ~33% more"；代码 k = 1 却打印 `overhead=0.0%`，二者**不一致**。代码的 k = 64 才是 32.8%。
3. **自洽模型**（层内激活 12 单位必须靠重算恢复，所以重算 FLOPs 恒为一次完整 forward，约 33%）：峰值显存 ≈ `⌈L/k⌉`（段输入）+ `12·k`（当前段的层内激活）。

   | k | 单位数 | 峰值显存 |
   |---|-------|---------|
   | 1 | 64 + 12 = 76 | ≈ 10.2 GB |
   | 2 | 32 + 24 = 56 | ≈ 7.5 GB |
   | 8 | 8 + 96 = 104 | ≈ 14.0 GB |
   | 不 checkpoint | 768 | ≈ 103 GB |

   最小化 `L/k + 12k` 得 `k* = √(L/12) ≈ 2.3`，取 k = 2。结论：**√L 只在"段输入"和"段内每层激活"体积相同时才是最优**；层内激活越大，段应越短。（以上数字已用脚本计算。）

### Q10 — 参考答案

1. 实测：6 层、k = 2 时 forward 调用 6 次 `layer_forward`，backward 中又调用了 **6 次**，即每层都重算了一遍；`checkpoint_cost` 的公式预测 `6 × (2−1)/2 = 3` 次。成本模型描述的是一个比实现更优的版本。
2. `model_backward` 只用到 `activations[i]`，即每层的**输入**；段内最后一层的输出（也就是下一段的输入，或最终输出）在 backward 中不会被用到。改为：

```python
        _, seg_acts = model_forward(x_in, params[start:end - 1])   # 只重算前 k-1 层
        g, seg_grads = model_backward(g, seg_acts, params[start:end])
```

   `model_forward(x_in, params[start:end-1])` 返回 `[x_in, out_start, …, out_{end-2}]`，长度恰为 k，正好是本段 k 层的输入。验证（已运行）：(6 层, k=2)、(7, 3)、(8, 4)、(5, 1) 四种配置下重算次数分别为 3、4、6、0，等于 `L − ⌈L/k⌉`，与不 checkpoint 的梯度最大差均为 0.0。
3. 基线 `model_forward` 只存了每层的**输出**（即下一层输入），`layer_backward` 每次都重新计算第一个线性层 `h_pre` 和 ReLU。也就是说本节的"不 checkpoint 基线"本身就在层内做了重算（第一个线性层约占该层 forward 的一半 FLOPs，因为 `w1`、`w2` 形状对称）。这进一步说明玩具代码的"层"是原子单位，与讲义"每层 12 单位中间激活"的设定不同。

### Q11 — 参考答案

1. 重算：`1.54e13 / 4e14 ≈ 38.5 ms`。单向搬运：`1.61e9 / 25e9 ≈ 64.4 ms`（backward 时还要再搬回来，往返约 129 ms）。
2. 传输时间（64.4 ms）> 重算时间（38.5 ms），按 skill 规则**拒绝 offload，选择重算**。即使传输能与计算重叠，该层 forward 本身只需约 38.5 ms，搬运无法被完全掩盖，会拖慢整步。
3. 盈亏平衡带宽 ≈ `1.61 GB / 38.5 ms ≈ 41.9 GB/s`。低于此值重算更快；高于此值且 CPU 内存充足时 offload 可以"零 FLOP"地省显存。（以上数字已计算验证；FLOPs 估算采用每层 `2 × 12d² × S` 的矩阵乘加上 `4S²d` 的注意力矩阵乘。）

要点：显存问题本质上是"把字节放哪儿"——存在 HBM、存在 CPU 内存（受 PCIe 限制），或者干脆不存（受算力限制）。不同层可以有不同选择（讲义："checkpoint some layers, offload others"）。

### Q12 — 参考答案

1. 实际运行结果：`True`、`False`、`True`、`False`、`False`。
   - attention 超过 100 MB 一律重算；
   - FFN 超过 500 MB 时，只有重算比例 < 0.1 才重算；
   - FFN 400 MB 不满足阈值；
   - 其他类型（如 norm）无论多大都不重算。
2. **单位 bug**：讲义版本接收字节数并与 `100 * 1e6` 比较，代码版本接收 MB 并与 `100` 比较。如果调用者按讲义习惯传入字节数（如 `150e6`），代码会认为它是 1.5 亿 MB，所有 attention 都判为重算；反过来，若把 MB 传给讲义版本，几乎永远不会重算。参数名带单位后缀（`_mb`）是好习惯，但调用方与实现必须一致。
3. 缺少的输入：显存预算（是否已经放得下——放得下就不该重算）；attention kernel 类型（FlashAttention 已经不存 S² 项）；offload 选项与 PCIe 实测带宽；TP/PP 下重算的通信成本；FP8 下 amax 是否被快照。阈值也是写死的绝对值，与模型规模、序列长度无关。配套 skill 的"按预算 + 10% 余量做整体规划、拒绝不必要的 full"更接近生产做法。

### Q13 — 参考回答要点

- **问题**：训练时激活显存与层数、batch、序列长度成正比（attention 部分与 S² 成正比），大模型、长上下文下激活常常比权重 + 优化器状态还大。
- **做法**：只保存部分张量（段输入），backward 时重算 forward 得到中间结果，再求导。本质是"用 FLOPs 换显存"。
- **代价**：全量重算约 +33% 步时间；selective 约 +5%（讲义数字）。
- **`torch.utils.checkpoint.checkpoint(fn, *inputs)`**：forward 时在不记录计算图的模式下执行 `fn`，只保存输入；backward 到这里时用保存的输入重新执行 `fn`（这次记录计算图），再对其做反向。新代码通常显式传 `use_reentrant=False`。
- 加分点：Megatron-Core 提供 `selective`、`full`、`block` 三种模式（讲义）；HF Transformers 里一般用 `model.gradient_checkpointing_enable()` 开启。
- 常见误区：以为 checkpointing 会改变训练结果——数学上完全等价（本节代码验证梯度差为 0），只改变时间与显存。

### Q14 — 参考回答要点

- **33%**：forward 记 1 个单位，backward 要对激活和权重各求一次梯度，约为 2 个单位，合计 3。全量重算多 1 个单位，`4/3 − 1 ≈ 33%`。
- **√L**：段长 k，需要常驻的段输入有 L/k 个；backward 处理某一段时要临时持有该段 k 层的中间结果。若每层的"输入"和"中间结果"体积都记为 1，峰值 ∝ `L/k + k`，对 k 求导得 `k* = √L`，此时峰值 ∝ `2√L`，显存从 O(L) 降为 O(√L)，重算量仍约为一次 forward。
- **12 : 1 的情形**：峰值 ∝ `L/k + 12k`，`k* = √(L/12)`；L = 64 时约 2.3（见 Q9）。层内激活越"胖"，段越短；极端情况下每层一段（即 Megatron 的 full 模式按层重算）。
- 加分点：可以递归地对段内再做 checkpoint，得到 O(log L) 显存、O(L log L) 计算的方案（Chen 等论文中也讨论了这种多层级的折中）；selective 的思路是"按张量而不是按层"做取舍。

### Q15 — 参考回答要点

按"先不花算力，再少花算力，最后多花算力"的顺序：

1. **算账**：先按讲义公式估算激活；本例无 FlashAttention 时 S² 项巨大。
2. **FlashAttention**：直接消除 S² 的 softmax 存储，几乎不增加开销，应第一个开。
3. **减小 micro-batch + 梯度累积**：激活与 micro-batch 成正比，有效 batch 不变。
4. **并行切分**：TP / sequence parallel 把激活在卡间切分；PP 减少每卡层数（见第 05 节）。
5. **Selective checkpointing**：只重算 attention 部分，约 5% 开销（讲义）。
6. **Full checkpointing**：放不下时再对部分层或全部层做全量重算，约 33%；段长按 Q14 选择。
7. **Offload**：当实测 PCIe 传输时间 < 重算时间（见 Q11）且 CPU 内存足够时，对部分层改用 offload。

- 选择依据：selective 适合 S 大、attention 主导且未用 Flash 的情况；full 适合激活主要来自 FFN/线性层、selective 不够时；offload 适合 GPU 算力已是瓶颈、PCIe 有余量时。
- 配套 skill 强调：能用 selective 解决就不要 full；任何方案都要在 HBM 预算内留 10% 余量。

### Q16 — 参考回答要点

- **随机性**：dropout 等随机操作在重算时必须生成相同的 mask。PyTorch `checkpoint` 默认 `preserve_rng_state=True`，会保存并恢复 RNG 状态；自己写重算时也要这样做。
- **FP8 scaling**：讲义："amax histories updated during recompute must match the original forward's, or the FP8 scale drifts"。框架通常对 scale 做快照，重算时不更新 amax。
- **BatchNorm 等有状态层**：重算时不能再次更新 running statistics（Transformer 一般用 LayerNorm/RMSNorm，问题较少）。
- **张量并行**：重算前需要重新 all-gather 被切分的输入，带来额外通信；序列并行下尤其要注意。
- **非确定性 kernel**：重算结果可能有极小数值差异，一般可接受，但做逐位比对的测试会失败（见 Q8）。
- **原地修改**：forward 中对输入做 in-place 操作会让保存的"段输入"被改写，重算时得到错误结果。

### Q17 — 参考回答要点

- **先量化**：按层估算激活。可以引用 Korthikanti 等论文中的估算：每层激活约 `S·B·h·(34 + 5·a·S/h)` 字节（16 位、无 TP，a 为头数、h 为隐藏维度）。S = 32K 时括号中 `5aS/h` 项远大于 34，S² 部分占绝对主导（加分点）。
- **逐层策略**（参考配套 skill）：
  - attention：使用 FlashAttention（消除 S² 存储）；未用 Flash 时用 selective；
  - 残差流、norm：不重算（体积小、重算不划算）；
  - FFN：显存不够时 full 或 offload，二者用实测的传输/重算时间决定；
  - embedding / 输出头：输出头 logits `B·S·V` 在长序列下也很大，可考虑分块计算 loss；
  - 结合 TP/sequence parallel 切分激活，PP 下每个 stage 的 forward 整体 checkpoint。
- **验证"放得下"**：用 `torch.cuda.max_memory_allocated` 实测峰值，与预算 + 10% 余量对比；逐步拉长序列，观察显存曲线是否按预期增长。
- **验证"不浪费"**：测步时间与 MFU，对比不重算时（可在短序列下对比）的 FLOP 开销；检查是否有"已经放得下却仍在 full 重算"的层。
- **验证"正确性"**：小模型上对比 checkpoint 开关前后的梯度（应在数值误差内一致）与 loss 曲线。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 03 Backpropagation 从头开始](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：理解 backward 为什么需要 forward 的中间结果。
- [阶段 01 · 05 Chain Rule & 自动微分](../../../01-math-foundations/05-chain-rule-and-autodiff/docs/zh.md)：autograd 图保存了哪些张量。
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：Transformer block 的结构与各子层的激活。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../05-scaling-distributed/docs/zh.md)：TP/PP/FSDP 与本节的交互。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：FlashAttention 如何在 backward 中重算 softmax。

### 本节被哪些后续内容用到
- [阶段 10 · 19 DualPipe 并行](../../19-dualpipe-parallelism/docs/zh.md)：流水线并行中的激活管理。
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../20-deepseek-v3-walkthrough/docs/zh.md)：大规模 MoE 训练中的重算与显存优化。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：单卡微调时常开 gradient checkpointing。
- [阶段 19 · 36 训练循环与评估](../../../19-capstone-projects/36-training-loop-eval/docs/zh.md)：在综合项目的训练循环中实践。

### 延伸关键词
`torch.utils.checkpoint` · `use_reentrant` · `preserve_rng_state` · `selective activation recomputation` · `sequence parallelism` · `activation offload` · `ZeRO-Offload` · `FSDP2` · `FlashAttention backward` · `MFU` · `sublinear memory`
