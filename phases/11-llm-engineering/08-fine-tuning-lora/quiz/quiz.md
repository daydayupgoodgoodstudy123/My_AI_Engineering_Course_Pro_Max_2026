# 测验 · Fine-Tuning 与 LoRA & QLoRA（Fine-Tuning with LoRA & QLoRA）

> **阶段 11 · LLM 工程 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/lora.py](../code/lora.py) ｜ 代码讲解：[code/lora.讲解.md](../code/lora.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **说明**：本节代码依赖 PyTorch，编写本测验的环境未安装 torch，代码**未实际运行**。题目中的参数量、内存字节数可由张量形状精确算出（已用 Python 计算）；随机数相关的数值（loss、量化误差）只给出推断或 NumPy 模拟结果，并逐一注明。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 全参数微调的显存账 | 权重 + 梯度 + Adam 两份状态 + 激活；讲义估计 8B 模型约 56GB，单卡很难装下 |
| 2 | LoRA 核心假设 | 微调时的权重更新是低秩的：冻结 W，只训练 `ΔW = BA`，`y = Wx + (α/r)·BAx` |
| 3 | 参数量 | 一个 `d_out × d_in` 层加 LoRA 后只训练 `r·(d_in + d_out)` 个参数；4096×4096、r = 16 时为 131,072，占 0.78% |
| 4 | 初始化 | A 随机高斯、B 全零，所以训练开始时 `BA = 0`，模型行为与原模型完全一致 |
| 5 | α 缩放 | 实际缩放系数是 `α/r`；社区常用 `α = 2r`（缩放 2 倍），原论文多数实验用 `α = r` |
| 6 | 目标模块与 rank | 讲义推荐 `q_proj + v_proj` 起步；r = 8/16 最常用，超过 64 很少有收益 |
| 7 | QLoRA | 基座量化成 4-bit NF4 并冻结，LoRA 适配器用 16-bit 训练；三项技术：NF4、double quantization、paged optimizers |
| 8 | 合并与多适配器 | `W' = W + (α/r)·BA` 合并后无推理开销；多任务服务时保持分离、按请求切换适配器 |
| 9 | 适配器合并进阶 | TIES-Merging（裁剪 + 解决符号冲突）、DARE（随机丢弃 + 重缩放）、task arithmetic（权重加减） |
| 10 | 何时不该微调 | 先 prompt engineering，再 RAG，最后才 fine-tune；要"知识"用 RAG，要"风格/格式/推理模式"才微调 |

### 核心技能（能动手做到）

- [ ] 用 PyTorch 写出 `LoRALayer`、`LinearWithLoRA`、`inject_lora`，并解释为什么 B 必须初始化为 0
- [ ] 手算任意模型加 LoRA 后的可训练参数量与占比（含 bias、含不含 LoRA 本身的口径）
- [ ] 推导 `merge_lora_weights` 中为什么要 `+= merged.T`，并能写出对应的 unmerge
- [ ] 说清本节"模拟 NF4"与真正 NF4 的三点差异，并写出按正态分位数取 16 个量化级的版本
- [ ] 为一个具体任务选择 rank、α、target modules、学习率，并估算 LoRA / QLoRA 的显存
- [ ] 设计"一个基座 + 多个适配器"的服务方案，并指出加载第三方适配器的安全风险

---

## 二、基础自测（选择题）

**Q1.** 在一个 4096 × 4096 的线性层上加 r = 16 的 LoRA，需要训练多少参数？占原层参数的比例约为多少？

- A. 65,536，0.39%
- B. 262,144，1.56%
- C. 131,072，0.78%
- D. 16,777,216，100%

**Q2.** 本节代码 Step 2 使用 `rank=8, alpha=16`。LoRA 分支输出被乘上的缩放系数是：

- A. 2.0
- B. 16
- C. 0.5
- D. 8

**Q3.** LoRA 把 B 初始化为全零、A 初始化为随机值。这样做的主要目的是：

- A. 让 A 和 B 的梯度都为 0，节省显存
- B. 让训练只更新 A，不更新 B
- C. 减少合并时的数值误差
- D. 让 `BA = 0`，训练开始时模型输出与原模型完全相同，从原有行为出发逐步学习适配

**Q4.** 下列哪一项**不是** QLoRA 论文提出的技术？

- A. NF4（Normal Float 4-bit）数据类型
- B. 把 LoRA 适配器本身量化到 4-bit 再训练
- C. Double quantization（对量化常数再量化）
- D. Paged optimizers（显存不足时把优化器状态换页到 CPU 内存）

**Q5.** 本节 `LoRALayer` 中 A 的形状是 `(in_features, rank)`、B 是 `(rank, out_features)`，前向为 `x @ A @ B`。`nn.Linear.weight` 的形状是 `(out_features, in_features)`。因此合并时写成 `module.linear.weight.data += merged.T`，其中 `merged = (A @ B) * scaling`。之所以要转置，是因为：

- A. `A @ B` 的形状是 `(in, out)`，而 `nn.Linear` 计算 `x @ Wᵀ`，权重按 `(out, in)` 存储，必须转置后形状才一致、数学上才等价
- B. 转置是为了让合并后的权重正交
- C. 不转置也可以，只是数值精度略差
- D. 转置是为了抵消 scaling 的影响

**Q6.** 本节 demo 模型为 `Linear(256→512) → ReLU → Linear(512→512) → ReLU → Linear(512→10)`，在第 0、2 层注入 r = 8 的 LoRA。按代码的 `count_parameters` 口径（分母包含 LoRA 参数），可训练参数占比约为：

- A. 0.78%
- B. 约 1%（与讲义 Step 8 说明一致）
- C. 7.2%
- D. 3.47%

**Q7.** 讲义说"每 64 个权重一个 fp32 缩放因子，7B 模型额外需要约 0.4GB"。这相当于每个参数额外多少比特？

- A. 0.125 bit
- B. 0.5 bit
- C. 4 bit
- D. 32 bit

**Q8.** 某团队想让 8B 模型"知道公司上个月新发布的 200 份产品文档的内容"。按讲义的决策顺序，最合适的第一选择是：

- A. 用全部文档做全参数微调
- B. 用 QLoRA 在文档上做 r = 64 的微调
- C. 先尝试 prompt engineering；不够再用 RAG 提供外部知识，而不是把知识"烤进"权重
- D. 换一个更大的模型直接问

---

## 三、动手 / 代码题

**Q9.** （手算 Step 2、Step 3 的打印结果）

```python
def create_demo_model(d_model=256, hidden=512, n_classes=10):
    return nn.Sequential(
        nn.Linear(d_model, hidden), nn.ReLU(),
        nn.Linear(hidden, hidden), nn.ReLU(),
        nn.Linear(hidden, n_classes),
    )

lora_layers = inject_lora(model, target_modules=["0", "2"], rank=8, alpha=16)
# Step 3:
for rank in [2, 4, 8, 16, 32]:
    m = create_demo_model()
    inject_lora(m, target_modules=["0", "2"], rank=rank, alpha=rank * 2)
```

1. 写出 Step 1 的总参数量，Step 2 的 Total / Trainable / Frozen 及百分比。
2. 写出 Step 3 五个 rank 的可训练参数量和百分比。
3. 讲义 Step 8 说 demo 的可训练参数是"~1%"，为什么实际高得多？
4. `inject_lora` 用 `any(t in name for t in target_modules)` 判断目标层。在一个有 12 个以上 block、模块名形如 `layers.10.self_attn.q_proj` 的真实模型上传入 `["0", "2"]` 会发生什么？应该怎么写？

**Q10.** 阅读模拟量化代码：

```python
def quantize_to_nf4(tensor, block_size=64):
    # ...（补零到 block_size 的整数倍）
    blocks = flat.reshape(-1, block_size)
    scales = blocks.abs().max(dim=1, keepdim=True).values / 7.0
    scales = torch.clamp(scales, min=1e-8)
    quantized = torch.round(blocks / scales).clamp(-8, 7).to(torch.int8)
    return quantized, scales, original_shape, pad_size
```

1. 这个函数名叫 `nf4`，但它与真正的 NF4 有哪些不同？（至少说出三点）
2. Step 4 中被量化的是哪几个张量？`Quantized layers`、`Full model (fp32)`、`Quantized base`、`LoRA adapters`、`QLoRA total` 五个数分别是多少 KB？这里的"量化基座"真的是 4-bit 吗？
3. 写一个按标准正态分位数取 16 个量化级、并把两个 4-bit 索引打包进一个字节的版本。

**Q11.** 关于合并：

```python
def merge_lora_weights(model):
    for name, module in list(model.named_modules()):
        if isinstance(module, LinearWithLoRA):
            with torch.no_grad():
                merged = (module.lora.A @ module.lora.B) * module.lora.scaling
                module.linear.weight.data += merged.T
            # ... 用 setattr 把 LinearWithLoRA 替换回 module.linear
```

1. 证明合并前后输出相等：`linear(x) + s·(x A B) == x (W + s·(AB)ᵀ)ᵀ + b`。
2. Step 6 打印 `Max output difference (should be ~0)`，这个值为什么通常不是精确的 0？大概是什么量级？
3. 写一个 `unmerge_lora_weights`，把已合并的适配器"拆出来"恢复原权重；它在什么前提下才能精确恢复？
4. Step 6 里 `model_q` 的基座权重已经被替换成"量化再反量化"后的值。在真实 QLoRA 中，训练完想得到一个 fp16 的合并模型，应注意什么？

**Q12.** 关于保存、加载与多适配器服务：

```python
def save_lora_adapter(model, path):
    adapter_state = {}
    for name, module in model.named_modules():
        if isinstance(module, LoRALayer):
            adapter_state[f"{name}.A"] = module.A.data.clone()
            adapter_state[f"{name}.B"] = module.B.data.clone()
            adapter_state[f"{name}.rank"] = module.rank
            adapter_state[f"{name}.alpha"] = module.alpha
    torch.save(adapter_state, path)
    return len(adapter_state) // 4

def load_lora_adapter(model, path):
    adapter_state = torch.load(path, weights_only=False)
    for name, module in model.named_modules():
        if isinstance(module, LoRALayer):
            a_key = f"{name}.A"
            b_key = f"{name}.B"
            if a_key in adapter_state:
                module.A.data = adapter_state[a_key]
                module.B.data = adapter_state[b_key]
```

1. `load_lora_adapter` 存在哪些健壮性问题？（提示：rank/alpha、缺失的键、`weights_only=False`）
2. 讲义练习 4 要求"基座只加载一次，切换适配器"。Step 8 的实现（`model_even`、`model_odd` 两个完整模型）满足这个要求吗？请写一个在**同一个模型**上切换两个适配器的函数。

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 LoRA 的原理：它冻结了什么、训练了什么、参数量是多少、A/B 怎么初始化、α 的作用是什么？

**Q14.**（原理深挖）QLoRA 是如何把 7B 模型的训练显存压到 6GB 左右的？NF4 为什么比均匀的 INT4 更适合神经网络权重？请顺便估算全参数微调、LoRA、QLoRA 的显存构成。

**Q15.**（工程实践）你要用 LoRA 微调一个 8B 模型做客服回复风格适配，请给出 rank、α、target modules、学习率、epoch 等配置，以及训练中你会监控哪些信号。

**Q16.**（场景设计）公司有 50 个企业客户，每个客户都要一个定制版的 8B 模型。你会怎么训练、存储和部署这些模型？

**Q17.**（追问型）LoRA 一定能避免灾难性遗忘吗？什么情况下 LoRA 会明显不如全参数微调？多个适配器能直接相加吗？

---

## 五、参考答案与解析

### Q1 — 答案：C

`A: 16 × 4096 = 65,536`，`B: 4096 × 16 = 65,536`，合计 131,072；`131,072 / 16,777,216 = 0.78%`。A 只算了一个矩阵；B 是 r = 32 的数；D 是原层参数量。讲义："You're training 0.78% of the parameters and getting 95-100% of the quality."

### Q2 — 答案：A

`self.scaling = alpha / rank = 16 / 8 = 2.0`。B、D 把 α 或 r 本身当成了缩放系数；C 是 `r/α`，方向反了。Step 3 用 `alpha=rank * 2`，所以 5 个 rank 的缩放系数都是 2，这让不同 rank 的对比少了一个变量。

### Q3 — 答案：D

讲义："The product BA starts at zero, so the model begins with its original behavior." B = 0 时 LoRA 分支输出为 0，但 B 的梯度 `∂L/∂B` 取决于 `xA`，并不为 0，所以训练一开始 B 就会被更新，随后 A 也开始获得梯度。A 错（梯度不为 0）；B 错（两者都会更新）；C 与初始化无关。反过来，如果 A、B 都为 0，两者梯度都恒为 0，永远学不动；如果都随机，模型一开始就被扰动了。

### Q4 — 答案：B

QLoRA 的三项贡献是 NF4、double quantization、paged optimizers（讲义原文）。适配器本身保持 16-bit（讲义："attach LoRA adapters in fp16 on top"），被量化的是**冻结的基座**。量化可训练参数会让梯度更新失去精度，正是 QLoRA 刻意避免的。

### Q5 — 答案：A

`A @ B` 是 `(in, r) @ (r, out) = (in, out)`；`nn.Linear` 的 `weight` 是 `(out, in)`，前向计算 `x @ weight.T + bias`。LoRA 分支 `x @ (A@B)` 等价于 `x @ ((A@B).T).T`，所以要把 `(A@B).T` 加到 `weight` 上，形状才对上（256→512 层中两者分别是 `(256, 512)` 和 `(512, 256)`）。对于方阵（512→512 层），不转置不会报错，但结果是错的——这是本题的陷阱。注意本代码的 A、B 是论文中 A、B 的**转置**：论文中 `A ∈ R^{r×d_in}`、`B ∈ R^{d_out×r}`、`ΔW = BA`；代码按"行向量 x 右乘矩阵"的习惯写成 `ΔWᵀ = A @ B`。两者角色一致——A 在输入侧、随机初始化，B 在输出侧、零初始化。

### Q6 — 答案：D

基座 399,370 个参数；LoRA：第 0 层 `8 × (256 + 512) = 6,144`，第 2 层 `8 × (512 + 512) = 8,192`，合计 14,336。`14,336 / (399,370 + 14,336) = 3.47%`（已用 Python 计算）。A 是 4096 维、r = 16 时的比例；B 是讲义 Step 8 的说法，与实际不符（见 Q9）；C 是 r = 16 时相对**基座**的比例（28,672 / 399,370 = 7.18%）。

### Q7 — 答案：B

每 64 个权重共享一个 32-bit 缩放因子：`32 / 64 = 0.5 bit/参数`。7B × 0.5 bit = 3.5Gbit ≈ 0.44GB，与讲义"约 0.4GB"一致。double quantization 把缩放因子量化为 8-bit 后约为 `8/64 = 0.125 bit/参数`，即约 0.11GB（讲义"0.1GB"），A 就是这个值。C 是 4-bit 权重本身；D 是一个 fp32 数。

### Q8 — 答案：C

讲义："If the model needs to know about your specific data (documents, knowledge base, product catalog), retrieval is cheaper and more maintainable than baking it into weights." 文档每月更新，微调要反复训练，且无法追溯答案来源；RAG 只需重建索引。A、B 都是把"知识"烤进权重，成本高、易过时、易幻觉；D 换大模型也不知道私有文档内容。只有当需要特定**风格、格式、推理模式**，或需要蒸馏、降低 few-shot token 开销时，才轮到微调。

### Q9 — 参考答案

（以下数值由张量形状精确算出，已用 Python 验证；代码本身因缺少 torch 未运行。）

1. 基座：`256×512+512 = 131,584`；`512×512+512 = 262,656`；`512×10+10 = 5,130`；合计 **399,370**，Step 1 打印 `Trainable: 399,370 (100.0%)`。
   Step 2：LoRA 14,336；`Total: 413,706`；`Trainable (LoRA only): 14,336 (3.47%)`；`Frozen (base model): 399,370`。`LoRA injected into: ['0', '2']`。
2. 每个 rank 的可训练参数 = `r × (768 + 1024) = 1,792r`：

| rank | trainable | 百分比（分母含 LoRA） |
|------|-----------|--------------------|
| 2 | 3,584 | 0.89% |
| 4 | 7,168 | 1.76% |
| 8 | 14,336 | 3.47% |
| 16 | 28,672 | 6.70% |
| 32 | 57,344 | 12.56% |

3. LoRA 的占比 ≈ `r·(d_in + d_out) / (d_in·d_out)`。层越窄，占比越高：4096 维时 r = 16 只占 0.78%，而这里最宽才 512 维，r = 8 时第 2 层就占 `8192 / 262,144 = 3.1%`。讲义"~1%"是把大模型的经验直接套到了小 demo 上。另外分母是否包含 LoRA 参数、是否包含未注入的层，也会改变这个数。
4. `"0" in name` 是**子串匹配**：`layers.10.…`、`layers.20.…`、`layers.0.…` 中的所有线性层都会被命中，`"2"` 还会命中 `layers.2x`、`layers.12` 等，完全不是想要的结果。应该按名字的最后一段精确匹配，例如 `name.split(".")[-1] in target_modules`，或用正则 `re.fullmatch`。PEFT 的 `target_modules=["q_proj", "v_proj"]` 就是按模块名后缀匹配的。

### Q10 — 参考答案

1. 与真正 NF4 的差异：
   - **量化级不同**：这里是均匀间隔（`round(x/scale)`，相邻级间距相同），属于对称 absmax INT4；NF4 的 16 个级放在**标准正态分布的分位数**上，在 0 附近更密、两端更疏。讲义："NF4 places its 16 quantization levels at the quantiles of a standard normal distribution."
   - **实际只用到 15 个级**：`scale = absmax / 7`，`|x/scale| ≤ 7`，`-8` 永远取不到（NumPy 模拟中 `np.unique` 只有 15 个值）。
   - **存储不是 4-bit**：结果 `.to(torch.int8)`，每个权重占 1 字节，没有把两个 4-bit 值打包进一个字节。
   - 缩放因子用 fp32，没有 double quantization；`quantize_model` 又立即反量化并写回 fp32 的 `param.data`，所以训练时内存里存的仍是 fp32 权重——它只模拟了量化**误差**，没有模拟量化**存储**。
2. `quantize_model` 只量化 `requires_grad=False` 且 `dim() >= 2` 的参数：三个 Linear 的 `weight`（131,072、262,144、5,120 个元素）。bias 是一维、LoRA 的 A/B 可训练，都不量化。于是：
   - `Quantized layers: 3`
   - `Full model (fp32)`: `413,706 × 4 B = 1,616.0 KB`（含 LoRA）
   - `Quantized base`: 元素 398,336 B + 缩放因子 `(2,048 + 4,096 + 80) × 4 = 24,896 B` = **413.3 KB**
   - `LoRA adapters (fp32)`: `14,336 × 4 = 56.0 KB`
   - `QLoRA total`: **469.3 KB**
   这是**按每权重 1 字节**计算的，真 4-bit 打包后元素部分只需约 194.5 KB。另外 1,034 个 bias（4,136 B）在 `QLoRA total` 里被漏算了。
3. 参考实现（NumPy 版，已运行验证；换成 torch 的 API 逻辑相同）：

```python
import numpy as np
from statistics import NormalDist

def nf4_levels():
    nd = NormalDist()
    lv = np.array([nd.inv_cdf((i + 0.5) / 16) for i in range(16)])
    return lv / np.abs(lv).max()                       # 归一化到 [-1, 1]

LEVELS = nf4_levels()

def quantize_nf4_like(w, block_size=64):
    blocks = w.reshape(-1, block_size)
    absmax = np.abs(blocks).max(axis=1, keepdims=True)
    x = blocks / absmax                                 # 每块缩放到 [-1, 1]
    idx = np.abs(x[..., None] - LEVELS).argmin(-1).astype(np.uint8)   # 最近的级 0..15
    packed = (idx[:, 0::2] << 4) | idx[:, 1::2]         # 两个 4-bit 打包成 1 字节
    return packed, absmax.astype(np.float32)

def dequantize_nf4_like(packed, absmax, shape):
    idx = np.empty((packed.shape[0], packed.shape[1] * 2), dtype=np.uint8)
    idx[:, 0::2], idx[:, 1::2] = packed >> 4, packed & 0x0F
    return (LEVELS[idx] * absmax).reshape(shape)
```

   在 `512 × 256`、标准差 0.02 的正态权重上：打包后 65,536 字节（每权重 0.5 字节），缩放因子 8,192 字节；重建 MSE 约 3.4e-6，而本节的均匀量化约 4.7e-6——正态分位数的量化级确实更适合正态分布的权重。注意：这个简化版的 16 个级关于 0 对称、**不含精确的 0**；真正的 NF4 用非对称构造保证 0 能被精确表示（神经网络里大量接近 0 的权重和 padding 都需要它）。

### Q11 — 参考答案

1. 设 `W` 为 `(out, in)`，前向 `linear(x) = x Wᵀ + b`。LoRA 分支 `s·x A B`。合并后 `W' = W + s·(AB)ᵀ`，则 `x W'ᵀ + b = x Wᵀ + s·x ((AB)ᵀ)ᵀ + b = x Wᵀ + s·x A B + b`，二者严格相等。NumPy 随机矩阵验证两种算法的最大差约 4.5e-13（float64）。
2. 数学上相等，但浮点运算顺序不同：合并前是 `x@W.T` 和 `x@A@B` 分别算完再相加，合并后是先把权重相加再乘。float32 的相对精度约 1e-7，所以差值通常在 1e-7 ~ 1e-6 量级（未实际运行，按 float32 精度推断）。讲义练习 5 用 1e-5 作为容差是合理的。
3. 参考实现：

```python
def unmerge_lora_weights(model, lora_modules):
    # lora_modules: {name: LinearWithLoRA}，合并前保存的引用（例如 inject_lora 的返回值）
    for name, wrapper in lora_modules.items():
        with torch.no_grad():
            delta = (wrapper.lora.A @ wrapper.lora.B) * wrapper.lora.scaling
            wrapper.linear.weight.data -= delta.T
        parent_name, _, child_name = name.rpartition(".")
        parent = model.get_submodule(parent_name) if parent_name else model
        setattr(parent, child_name, wrapper)            # 换回带 LoRA 的包装层
```

   前提：保留了 A、B、scaling（本代码合并后会把 `LinearWithLoRA` 丢掉，所以必须事先保存引用）；且只能在浮点误差范围内恢复，不是逐位相等。若合并后权重又被量化、或被继续训练，就无法恢复。
4. 真实 QLoRA 中基座以 NF4 存储，不能直接把 fp16 的 `ΔW` 加到 4-bit 权重上（加完还得重新量化，适配器的细微更新会被量化误差吞掉）。通常做法是：用 fp16/bf16 重新加载**原始**基座（或把 NF4 反量化成 bf16），再合并适配器、保存 16-bit 模型；如果之后还要量化部署，应在合并**之后**再做量化，并评测量化前后的效果差异。

### Q12 — 参考答案

1. 健壮性问题：
   - 保存了 `rank`、`alpha`，但加载时**完全不用**：适配器的 rank 与目标模型不一致时，`module.A.data = ...` 直接替换张量，不会报形状错，前向时才可能报错；alpha 不同则 `scaling` 不一致，输出悄悄变化。
   - `if a_key in adapter_state` 不满足时静默跳过：层名对不上（比如目标模块换了）时，模型会带着随机 A、零 B 运行，看起来"加载成功"但适配器根本没生效。应统计并报告缺失/多余的键。
   - `torch.load(..., weights_only=False)` 会执行 pickle 反序列化，加载不可信来源的适配器文件可能执行任意代码。适配器只需要张量和少量整数，应使用 `weights_only=True` 或 safetensors 格式（PEFT 默认保存为 `adapter_model.safetensors`）。
   - 直接替换 `.data` 而不是 `copy_`，会绕开 dtype/device 检查。
2. 不满足。Step 8 创建了两个完整模型，各自注入、各自训练，基座在内存里有两份；它只证明了"两个适配器输出不同"，没有演示切换。在同一模型上切换的参考写法：

```python
def snapshot_adapter(model):
    return {name: (m.A.detach().clone(), m.B.detach().clone())
            for name, m in model.named_modules() if isinstance(m, LoRALayer)}

def use_adapter(model, adapter):
    for name, m in model.named_modules():
        if isinstance(m, LoRALayer):
            A, B = adapter[name]                 # 缺键时直接 KeyError，而不是静默跳过
            assert A.shape == m.A.shape and B.shape == m.B.shape
            with torch.no_grad():
                m.A.copy_(A)
                m.B.copy_(B)

# 用法：训练完 even 后 adapter_even = snapshot_adapter(model)，
# 重置 A/B 后训练 odd 得 adapter_odd；推理时 use_adapter(model, adapter_even) / (model, adapter_odd)
```

   这样基座只在内存中存一份，切换只拷贝 14,336 个参数。生产中多适配器服务还会把同一批请求按适配器分组，或用专门的多 LoRA 推理内核（加分点）。

### Q13 — 参考回答要点

- **冻结**：预训练权重 W（以及模型中所有非 LoRA 参数）。
- **训练**：每个目标线性层旁加两个小矩阵，`y = Wx + (α/r)·BAx`，`B ∈ R^{d_out×r}`、`A ∈ R^{r×d_in}`。
- **参数量**：`r·(d_in + d_out)`；4096 维、r = 16 时每层 131,072，占 0.78%。
- **理论依据**：讲义引 Hu 等 2021 年论文——微调时的权重更新具有很低的"内在秩"（intrinsic rank）。
- **初始化**：A 随机、B 为 0，训练从原模型行为开始。
- **α**：实际缩放是 `α/r`；调 r 时如果保持 `α/r` 不变，可以少调一次学习率。社区惯例 `α = 2r`，原论文多数实验 `α = r`。
- **加分点**：显存节省主要来自"不需要为冻结参数存梯度和优化器状态"，前向激活仍然要存；合并后推理零开销；同一基座可以挂多个适配器。

### Q14 — 参考回答要点

- **三项技术**：
  - **NF4**：权重近似正态分布，把 16 个量化级放在正态分位数上，使每个级被使用的概率接近相等，信息损失比均匀 INT4 小（Q10 的 NumPy 模拟中 MSE 约 3.4e-6 vs 4.7e-6）。
  - **Double quantization**：每 64 个权重一个 fp32 缩放因子是 0.5 bit/参数（7B 约 0.4GB），再把缩放因子量化到 8-bit，降到约 0.1GB。
  - **Paged optimizers**：利用 NVIDIA 统一内存，在显存不够时把 Adam 状态换页到 CPU 内存，避免长序列时 OOM，代价是吞吐下降。
- **显存构成（讲义表格，7B）**：全参数 fp16 权重 14GB，训练约 56GB；LoRA（fp16 基座）权重 14GB，训练约 18GB；QLoRA（4-bit 基座）权重 3.5GB，训练约 6GB。
- **追问点（讲义的算术）**：讲义"问题"一节对 8B 全参数微调的拆解是"权重 16GB + 梯度 16GB + Adam 32GB + 激活"，单是前三项就有 64GB，与它给出的"约 56GB"自相矛盾。若按常见的混合精度 Adam（fp16 权重与梯度 + fp32 主权重和两份 fp32 状态，约 16 字节/参数）估算，8B 需要约 128GB，还不含激活——全参数微调实际上通常要多卡并配合 ZeRO/FSDP 分片。面试中能说出"每参数多少字节"的口径比背结论更有说服力。
- **QLoRA 的计算**：前向时把 NF4 权重按块反量化成 bf16 再做矩阵乘（`bnb_4bit_compute_dtype=torch.bfloat16`），梯度只流向 LoRA 参数。
- 常见误区：以为 QLoRA 训练用 4-bit 计算，或以为适配器也是 4-bit。

### Q15 — 参考回答要点

- **方法**：先确认 prompt + few-shot 的基线；风格适配符合"该微调"的条件。按显存选 LoRA 或 QLoRA（24GB 卡用 QLoRA）。
- **配置起点**（讲义与 outputs 中的 advisor/skill 一致）：`r = 16`、`α = 32`、`target_modules = ["q_proj", "v_proj"]`、`lora_dropout = 0.05`；QLoRA 学习率约 2e-4（LoRA 比全参数微调用更高的学习率）；有效 batch 16–64（如 `per_device_batch_size=4` × `gradient_accumulation_steps=4`）；1–3 个 epoch。
- **数据**：几千条高质量的"工单 → 理想回复"对，格式与推理时的 chat template 一致，留 10–20% 做验证集。
- **监控**：训练 / 验证 loss 曲线（验证 loss 回升即过拟合）；梯度范数；固定一组样例定期生成，人工或 LLM-as-judge 打分；同时在通用能力评测集上抽查，确认没有明显退化。
- **迭代**：效果不够时依次尝试加入 `k_proj`、`o_proj`、MLP 层，或把 r 提到 32；每次只改一个变量做消融。
- 常见误区：用全参数微调的学习率（1e-5 级）训练 LoRA，loss 几乎不动；忘了设置 pad token（outputs 中提到 Llama 会因此出现 NaN loss）。

### Q16 — 参考回答要点

- **训练**：同一个 8B 基座 + 每个客户一个 LoRA 适配器（各自数据、各自验证集）；用 Axolotl 等配置化工具保证可复现。
- **存储**：基座一份（16GB 级），每个适配器 10–100MB（讲义），50 个适配器合计也就几 GB；版本化存放，记录训练数据与超参。
- **部署**：保持适配器**分离**，一个基座常驻显存，按请求的客户 ID 动态加载适配器；同一批次里不同客户的请求可以共享基座计算，只在 LoRA 分支上各算各的。只有某个客户流量特别大、需要极致延迟时，才为它单独部署合并后的模型。
- **隔离与安全**：适配器只从受信任的存储加载（safetensors），按客户做访问控制，避免串用。
- **加分点**：提到 vLLM 等推理引擎原生支持多 LoRA 服务；冷门客户的适配器可以按需从 CPU/磁盘换入。
- 常见误区：为每个客户合并并部署一份完整模型，50 份 16GB 的副本在成本上不可接受。

### Q17 — 参考回答要点

- **遗忘**：LoRA 只改了一个低秩子空间、基座权重不变，**卸下适配器**就能完全恢复原模型，这是它最大的安全网；但**挂着适配器**时，模型在其他任务上仍可能退化（尤其 r 大、学习率高、epoch 多时）。所以要同时评测目标任务和通用能力。
- **不如全参数微调的情况**：任务与预训练分布差距很大（新语言、新领域的大量知识注入）、需要的更新不是低秩的、数据量非常大时，低秩约束会限制效果；讲义表格显示 r = 16 时 HumanEval 14.0 vs 全参数 14.6，代码类任务差距相对明显，r = 64 可以缩小差距。
- **适配器相加**：直接相加（task arithmetic）有时可行，但不同适配器的更新可能互相干扰（同一参数符号相反）。TIES-Merging 先裁剪小幅值参数、解决符号冲突再合并；DARE 随机丢弃部分参数并重缩放。讲义："Adding a 'code' adapter and a 'math' adapter often produces a model good at both." 但务必在两类任务上都评测。
- 加分点：说出 DoRA 等 LoRA 变体（PEFT 库支持 LoRA/QLoRA/DoRA/IA3，讲义 "2026 PEFT stack" 表）。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：LoRA 是 SFT 的参数高效版本，讲义把它列为先修。
- [阶段 10 · 11 Quantization：让模型装得下](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：理解 4-bit 量化、分块缩放与量化误差。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：全参数微调为什么需要多卡与状态分片。
- [阶段 11 · 06 RAG（检索增强生成）](../../06-rag/docs/zh.md)：讲义决策树中"先 RAG 再微调"的另一条路。

### 本节被哪些后续内容用到
- [阶段 10 · 08 DPO：直接偏好优化](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：SFT 之后的偏好对齐，同样常与 LoRA 搭配（TRL 的 DPOTrainer）。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../10-evaluation/docs/zh.md)：如何评测微调前后的效果与回归。
- [阶段 17 · 09 生产环境中的 Quantization](../../../17-infrastructure-and-production/09-production-quantization/docs/zh.md)：合并后的模型如何再量化部署。
- [阶段 17 · 04 服务引擎内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：推理引擎如何高效服务（包括多适配器场景）。
- [阶段 19 · 07 端到端 Fine-Tuning 流程](../../../19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/zh.md)、[阶段 19 · 39 通过监督式 Fine-Tuning 进行指令微调](../../../19-capstone-projects/39-instruction-tuning-sft/docs/zh.md)：综合项目中完整走一遍微调流程。

### 延伸关键词
`PEFT` · `LoraConfig` · `target_modules` · `lora_dropout` · `DoRA` · `IA3` · `NF4` · `bitsandbytes` · `double quantization` · `paged AdamW` · `merge_and_unload` · `multi-LoRA serving` · `TIES-Merging` · `DARE` · `task arithmetic` · `catastrophic forgetting` · `safetensors`
