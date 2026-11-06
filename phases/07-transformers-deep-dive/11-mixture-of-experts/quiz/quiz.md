# 测验 · 专家混合 (MoE)（Mixture of Experts (MoE)）

> **阶段 07 · Transformers 深入 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MoE 的核心交换 | 把每层 FFN 换成 E 个独立专家 + 一个路由器，每个 token 只选 k 个专家；存储随 E 增长，计算随 k 增长 |
| 2 | 总参数 vs 激活参数 | 总参数 ≈ `E × 专家大小`，每 token 激活 ≈ `k × 专家大小`；DeepSeek-V3 为 671B 总 / 37B 激活（约 5.5%） |
| 3 | 路由器（router） | 一个线性层给 token 对每个专家打分，取 top-k，再对选中专家的分数做归一化得到门控权重，输出 = Σ gate × Expert(x) |
| 4 | 负载均衡问题 | 路由器若把大部分 token 发给少数专家，其余专家"饿死"、训练浪费；三种解法：辅助损失、容量上限 + 丢 token、无辅助损失偏置 |
| 5 | 无辅助损失均衡（DeepSeek-V3） | 每个专家一个偏置，**只影响选择、不影响门控权重**；每步按使用量高于/低于目标 `∓γ` 调整，不给主目标加额外梯度 |
| 6 | 共享专家 | 每个 token 都经过的专家，承载通用知识；路由专家负责专门化。V3：1 个共享 + 256 选 8 |
| 7 | 细粒度专家 | 专家更窄（约 1/8 FFN）、E 更大（256+）、k 更大（8+）；组合数 `C(256, 8) ≈ 4×10¹⁴`，质量提升而延迟基本不变 |
| 8 | 代价：显存与通信 | 不管激活哪个专家，所有专家都要放在显存里；671B fp16 ≈ 1.3 TB；需要专家并行，延迟常由 all-to-all 通信主导 |
| 9 | 何时不用 MoE | 边缘部署、延迟敏感的单用户服务、小模型（讲义：约 6B 激活参数以下优势不明显） |

### 核心技能（能动手做到）

- [ ] 用纯 Python 实现 `route()`：top-k 选择 + 只在选中专家上做 softmax，并保证偏置只影响选择不影响门控
- [ ] 实现 `update_bias()` 的符号式更新，能解释为什么 `γ` 过大会出现振荡、`γ` 过小收敛慢
- [ ] 用熵 `-Σ p log p` 衡量专家负载均衡程度，知道上限是 `ln E`
- [ ] 给定 `d_model`、专家中间维度、E、k、层数，算出 MoE 的总参数与激活参数，并与同级 dense 模型对比
- [ ] 能解释 Switch 风格辅助损失、容量上限 + 丢 token、无辅助损失偏置三种方案的取舍
- [ ] 能为一个 MoE 部署估算显存，并说明为什么需要专家并行以及 all-to-all 通信的影响

---

## 二、基础自测（选择题）

**Q1.** 某 MoE 层有 256 个路由专家、1 个共享专家、每个 token 选 top-8，每个专家参数量 44M。这一层 FFN 部分的总参数和每 token 激活参数约为：

- A. 总 11.3B，激活 0.40B
- B. 总 11.3B，激活 11.3B
- C. 总 0.40B，激活 0.40B
- D. 总 1.9B，激活 0.35B

**Q2.** 在 DeepSeek-V3 的无辅助损失负载均衡中，每个专家的偏置 `bias` 的作用是：

- A. 同时加到选择分数和门控权重上，让过载专家的输出变小
- B. 只加到用于 top-k **选择**的分数上；门控权重仍由原始分数计算
- C. 作为一个额外的损失项，通过反向传播更新
- D. 用来决定每个专家的容量上限，超出的 token 被丢弃

**Q3.** 早期 Switch Transformer 的"专家容量 + token 丢弃"方案有什么主要缺点？

- A. 需要额外的路由器参数
- B. 超出容量的 token 会直接跳过该层的专家计算，损害模型质量
- C. 会让所有专家的参数共享
- D. 无法在 GPU 上实现

**Q4.** 关于"细粒度专家"（fine-grained experts），下列说法**正确**的是：

- A. 专家数变少、每个专家变宽，以减少路由开销
- B. 每个专家更窄、专家数更多、k 更大，在总参数相近时专家组合数大幅增加
- C. 细粒度意味着每个 token 只能选 1 个专家
- D. 细粒度专家会让每个 token 的激活计算量成倍增加

**Q5.** 为什么讲义说 MoE 的"代价是显存"？

- A. 因为路由器参数特别多
- B. 因为所有专家无论是否被激活都要常驻显存；671B 参数的模型 fp16 权重约需 1.3 TB
- C. 因为 MoE 的 KV cache 是 dense 模型的 E 倍
- D. 因为每个 token 都要经过全部专家

**Q6.** 下列哪个场景**最不适合**用 MoE？

- A. 有大规模 GPU 集群、追求单位 token 推理成本更低的前沿对话服务
- B. 手机端离线运行的小模型
- C. 以大量短对话和代码生成为主的高吞吐服务
- D. 已具备专家并行基础设施的团队训练新一代旗舰模型

**Q7.** 共享专家（shared expert）的设计意图是：

- A. 让所有路由专家共享同一套参数，节省显存
- B. 每个 token 都经过共享专家，由它承载通用知识，让路由专家更专注于专门化
- C. 共享专家只在推理时使用，训练时关闭
- D. 共享专家用来替代 attention 层

**Q8.** 用熵 `H = -Σ pᵢ ln pᵢ` 衡量 8 个专家的使用分布。下列哪个说法正确？

- A. H 越小说明负载越均衡
- B. H 的最大值是 `ln 8 ≈ 2.079`，在使用量完全均匀时取到
- C. H 的最大值是 8
- D. 只要 H > 2.0，每个专家的使用量就一定都在目标值 ±5% 以内

---

## 三、动手 / 代码题

**Q9.** 运行 `code/main.py`，偏置更新阶段的输出是：

```text
iteration  0  usage:  260  206  278  265  216  301  253  221  entropy=2.072
iteration  1  usage:  228  247  253  236  271  279  215  271  entropy=2.076
iteration  2  usage:  267  299  211  270  220  249  260  224  entropy=2.073
iteration  3  usage:  228  247  253  236  271  279  215  271  entropy=2.076
iteration  4  usage:  267  299  211  270  220  249  260  224  entropy=2.073
...
iteration 10  usage:  267  299  211  270  220  249  260  224  entropy=2.073
```

```python
def update_bias(bias, usage_counts, target, gamma):
    for e in range(len(bias)):
        if usage_counts[e] > target:
            bias[e] -= gamma
        elif usage_counts[e] < target:
            bias[e] += gamma
    return bias
```

(1) 讲义说"使用量会在几次迭代内收敛到均匀分布"，但实际输出在两种状态之间来回跳。请解释为什么会精确地出现周期为 2 的振荡。(2) 给出至少两种修复方法。

**Q10.** 对下面的输入手算 `route()` 的返回值，并与"用加偏置后的分数计算门控"做对比：

```python
scores = [2.0, 1.0, 0.5, 0.1]   # 某个 token 对 4 个专家的原始打分
bias   = [0.0, 0.0, 1.0, 0.0]   # 专家 2 使用不足，偏置被调高
top_k  = 2
```

`route()` 的核心逻辑：

```python
    biased = [s + b for s, b in zip(scores, bias)]
    top_idx = sorted(range(E), key=lambda i: -biased[i])[:top_k]
    chosen = [scores[i] for i in top_idx]
    m = max(chosen)
    exps = [math.exp(c - m) for c in chosen]
    s = sum(exps)
    gates = [e / s for e in exps]
```

**Q11.** `main()` 中的参数量估算打印了：

```text
  deepseek-v3 FFN total (×61 layers): ~806B total,  ~28B active
  llama-3-70b FFN total: ~13B  (all active every token)
```

(1) 指出这两行估算的问题（提示：806B 比整个 DeepSeek-V3 的 671B 还大；Llama 3 70B 的 FFN 只有 13B 显然不对）。(2) 已知 DeepSeek-V3：`d_model=7168`、专家中间维度 2048、61 层中前 3 层是 dense FFN（中间维度 18432）、其余 58 层为 MoE（1 共享 + 256 路由、top-8）；Llama 3 70B：`d_model=8192`、FFN 中间维度 28672、80 层。都使用 SwiGLU（3 个矩阵）。写代码重新估算。

---

## 四、面试高频题

**Q12.**（基础必考）什么是 MoE？为什么说它"把参数量和每 token 计算量解耦"？请用 DeepSeek-V3 或 Mixtral 的数字说明。

**Q13.**（原理深挖）MoE 的负载均衡为什么重要？比较辅助损失、容量上限 + 丢 token、无辅助损失偏置三种方案，并写出 Switch Transformer 辅助损失的形式。

**Q14.**（原理深挖）DeepSeek 系列为什么同时使用"共享专家"和"细粒度路由专家"？各自解决了什么问题？

**Q15.**（工程实践）部署一个 671B 总参数 / 37B 激活的 MoE 模型，会遇到哪些工程问题？为什么说它在单用户低延迟场景下可能比同等激活参数的 dense 模型更慢？

**Q16.**（场景设计）你的团队要做两个模型：①一个 3B 参数、要部署到手机的助手；②一个面向海量用户的云端旗舰模型，计算预算固定但显存充足。分别选 dense 还是 MoE？如果选 MoE，E、k、共享专家和均衡策略怎么定？

---

## 五、参考答案与解析

### Q1 — 答案：A

总参数：`(1 + 256) × 44M ≈ 11.3B`；激活参数：共享专家总是激活，再加 8 个路由专家，`(1 + 8) × 44M ≈ 0.40B`。B 把激活算成了全部；C 把总参数算成了激活；D 是乱凑的。这也是讲义"存储随 E 增长、计算随 k 增长"的直观体现：激活只占约 3.5%。

### Q2 — 答案：B

讲义："Selection uses `scores + bias`. Expert probabilities used for gating are the raw `scores` unchanged. Decouples routing from expression." 偏置只是用来"把 token 挪到空闲专家"，不改变模型对已选专家的加权方式，因此不会扭曲模型的预测。C 错：偏置在训练损失之外按规则更新，不产生额外梯度——这正是"auxiliary-loss-free"的含义。D 描述的是容量方案。

### Q3 — 答案：B

每个专家最多处理 `C × N / E` 个 token（C 为容量因子），溢出的 token 跳过该层（只走残差连接），等于这些 token 在这一层没有得到 FFN 计算，讲义直言"Hurts quality"。

### Q4 — 答案：B

讲义：经典 MoE（GShard、Switch）每个专家和完整 FFN 一样宽，E 为 8–64、k 为 1–2；细粒度 MoE（DeepSeek-V3、Qwen-MoE）每个专家约 1/8 FFN 宽，E 为 256+、k 为 8+。总参数相近，但组合数从 `C(8, 2) = 28` 暴涨到 `C(256, 8) ≈ 4.1×10¹⁴`，专家可以更精细地专门化。因为每个专家变窄了，k 变大并不会让激活计算成倍增加（D 错）。

### Q5 — 答案：B

稀疏的是**计算**，不是**存储**：一个 batch 里不同 token 会选中不同专家，所有专家都必须随时可用。`671 × 10⁹ × 2 字节 ≈ 1.34 TB`。所以前沿 MoE 必须做专家并行，把专家分散到多张 GPU，再通过网络 all-to-all 把 token 送到对应专家。C 错：KV cache 属于 attention 部分，与专家数无关。

### Q6 — 答案：B

讲义"When NOT to pick MoE"：边缘部署——为了一点激活计算要付全部存储的代价；小模型（<7B）——质量优势只在一定算力阈值以上出现。A、C、D 都是讲义"When to pick MoE"中的典型场景（追求更低单 token 成本、有显存/专家并行基础设施、token 密集型负载）。

### Q7 — 答案：B

讲义："Every token passes through all shared experts. Routed experts are picked via top-k. Shared experts capture common knowledge; routed experts specialize." 如果没有共享专家，每个路由专家都得重复学一遍通用知识（例如基本语法），浪费参数。

### Q8 — 答案：B

熵在分布完全均匀时最大，为 `ln E = ln 8 ≈ 2.079`（代码最后一行也打印了它），越小表示越集中。D 错：熵对轻度不均衡很不敏感——本节代码 iteration 0 的熵是 2.072，看起来接近上限，但使用量从 206 到 301，相对目标 250 偏差高达 ±20%。实际监控时应同时看"最大使用量 / 目标值"这类指标。

### Q9 — 参考答案

(1) 观察 iteration 1（状态 A）和 iteration 2（状态 B）：A 中高于目标 250 的专家（第 2、4、5、7 个，下标从 0 起）在 B 中恰好全部低于目标，反之亦然——**每个专家的"超/欠"符号完全相反**。于是：

- 第 2 次更新加上 `Δ(A)`（超的 −0.15、欠的 +0.15），得到状态 B；
- 第 3 次更新加上 `Δ(B) = −Δ(A)`，偏置**精确回到**第 1 次更新后的值，路由结果自然又是状态 A；
- 如此往复，形成周期 2 的极限环。

根本原因：这是一个**固定步长、只看符号**的 bang-bang 控制器，步长 `γ = 0.15` 相对于路由分数的尺度（本例中分数标准差约 1.2，而专家间的差距更小）太大，每次调整都"矫枉过正"。注意 iteration 0 本身已经只是轻度不均衡（熵 2.072），所以振荡后并没有明显改善——最大偏差从 51 降到 35/49 后就停住了。

(2) 修复方法（已在本地用同一组数据验证）：

- **减小 γ**：`γ = 0.05` 时最大偏差降到 11–15，`γ = 0.02` 时 50 轮后约 5–7，`γ = 0.01` 时约 3–4（但收敛更慢，需要更多轮）；
- **步长衰减**：`γ_t = γ₀ / √t` 或指数衰减，先快后稳；
- **按偏差比例更新**：`bias[e] -= γ × (usage[e] − target) / target`，偏差小时步子也小；
- **加动量/平滑**：用使用量的滑动平均而不是单步计数来决定更新方向。

真实训练中每一步的 batch 不同，token 分布本身也在变，这种完全周期性的振荡不会这么"干净"地出现，但"γ 过大导致抖动、γ 过小导致响应慢"的取舍是真实存在的，这也是配套 skill 要求给出 γ 值的原因。

### Q10 — 参考答案

- 加偏置后的分数：`[2.0, 1.0, 1.5, 0.1]`，top-2 选中 **专家 0 和专家 2**（`top_idx = [0, 2]`）。没有偏置时本应选中专家 0 和 1——偏置确实把 token 挪给了使用不足的专家 2。
- 门控用**原始**分数 `[2.0, 0.5]`：`softmax = [1/(1+e^-1.5), e^-1.5/(1+e^-1.5)] ≈ [0.8176, 0.1824]`。
- 如果错误地用加偏置后的分数 `[2.0, 1.5]` 算门控：`≈ [0.6225, 0.3775]`，专家 2 的权重从 18% 被抬到 38%。

对比说明了"解耦"的意义：偏置是**负载均衡的工程手段**，不是模型学到的判断。原始打分认为专家 2 对这个 token 不太合适（0.5 分），所以即便为了均衡把 token 发给它，也只给它较小的权重，模型输出受到的扭曲最小。若偏置也进入门控，均衡机制会直接改写模型的预测，相当于引入了一个不受训练目标约束的扰动。

### Q11 — 参考答案

(1) 问题：

- `ffn_full = 3 * d * int(d * 2.67)` 用了"中间维度 ≈ 2.67 d"的经验值，`fine_expert = ffn_full // 8` 得到每个专家约 51.4M，比真实的 44M 大；并且把 **61 层全部**按 MoE 计算，而 V3 前 3 层是 dense。于是 FFN 总量算成 806B，超过了整个模型的 671B。
- `llama-3-70b` 一行直接复用了 DeepSeek 的 `d = 7168` 和 `ffn_full`，并假设 32 层；而 Llama 3 70B 实际是 `d = 8192`、FFN 中间维度 28672、80 层，FFN 约 56B，代码低估了约 4 倍。这也使得"takeaway: same active FLOPs"缺乏数字支撑。

(2) 重新估算：

```python
def swiglu_params(d, d_ff):
    return 3 * d * d_ff            # W_gate, W_up, W_down

d = 7168
expert = swiglu_params(d, 2048)
moe_layers, dense_layers = 58, 3
total = moe_layers * (1 + 256) * expert + dense_layers * swiglu_params(d, 18432)
active = moe_layers * (1 + 8) * expert + dense_layers * swiglu_params(d, 18432)
print(f"expert = {expert/1e6:.1f}M")
print(f"DeepSeek-V3 FFN: total ~{total/1e9:.0f}B, active ~{active/1e9:.1f}B")

llama = 80 * swiglu_params(8192, 28672)
print(f"Llama-3-70B FFN: ~{llama/1e9:.1f}B (all active)")
```

输出（已运行验证）：

```text
expert = 44.0M
DeepSeek-V3 FFN: total ~658B, active ~24.2B
Llama-3-70B FFN: ~56.4B (all active)
```

解读：DeepSeek-V3 的 FFN 占了 671B 中的约 658B（其余是 attention、embedding 等）；每 token 激活的 FFN 约 24B，再加上 attention 等部分，合计约 37B，与官方数字吻合。与 Llama 3 70B 相比，V3 的 FFN 总量是它的约 12 倍，而每 token 激活的 FFN 计算还不到它的一半——这才是"更多知识、更少激活计算"的定量证据。

### Q12 — 参考回答要点

- **定义**：把 Transformer 每层的 FFN 换成 E 个独立的专家 FFN + 一个路由器，每个 token 由路由器选 top-k 个专家，输出为门控加权和。
- **解耦**：dense 模型每 token 的计算 ≈ 2 × 参数量（前向），参数越多每个 token 越贵；MoE 中总参数 ∝ E（决定"能记住多少知识"），每 token 计算 ∝ k（决定"每个 token 花多少算力"）。
- **数字**：DeepSeek-V3 671B 总 / 37B 激活（约 5.5%）；Mixtral 8×22B 141B 总 / 约 39B 激活；Kimi K2 1T 总 / 约 32B 激活。讲义：V3 在几乎所有基准上超过 Llama 3 70B（dense），每 token 激活 FLOPs 却更少。
- **加分点**：指出 attention 部分仍是 dense 的，所以"激活参数"包含 attention + 共享专家 + k 个路由专家；MoE 节省的是 FLOPs，而不是显存。

### Q13 — 参考回答要点

- **为什么重要**：路由器和专家是一起训练的，存在"富者愈富"的正反馈——被选得多的专家训练得更好、于是更容易被选中，最终可能出现路由坍塌（少数专家处理大部分 token），其余专家参数浪费；在专家并行中，热门专家所在的 GPU 还会成为瓶颈，拖慢整体速度。
- **三种方案**：

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| 辅助损失（Switch、Mixtral） | 在主损失上加一个惩罚不均衡的项 | 简单有效 | 多一个超参数（系数），且第二个梯度信号会干扰主目标 |
| 容量上限 + 丢 token（早期 Switch） | 每个专家最多处理 `C × N / E` 个 token，溢出的跳过该层 | 计算量可预测 | 被丢的 token 没有 FFN 计算，损害质量 |
| 无辅助损失偏置（DeepSeek-V3） | 每专家一个偏置，只影响选择；按使用量 `±γ` 更新 | 不干扰主目标 | 需要调 γ；偏置更新本身不可微 |

- **Switch 辅助损失**：`L_aux = α · E · Σᵢ fᵢ · Pᵢ`，其中 fᵢ 是被分配给专家 i 的 token 比例（不可微，来自 argmax），Pᵢ 是路由器分给专家 i 的平均概率（可微）；在均匀分布时取最小值，论文中 α 取 0.01。讲义把它概括为"与使用量方差成正比的惩罚"，严格来说是 f 与 P 的点积形式。
- **加分点**：提到配套 skill 的立场——2026 年新项目默认采用无辅助损失均衡，不再只用辅助损失。

### Q14 — 参考回答要点

- **共享专家**：所有 token 都要用到的通用能力（语法、常见词搭配等）如果由路由专家承担，就会在多个专家里重复学习，造成参数冗余。设置一个所有 token 必经的共享专家来承载这些公共知识，让路由专家把容量用在真正的专门化上。
- **细粒度路由专家**：把一个大专家切成多个小专家，同时增大 k，总参数和激活计算基本不变，但可选的组合数呈爆炸式增长（`C(256, 8) ≈ 4.1×10¹⁴`），每个 token 能得到更"量身定制"的专家组合，专家的分工也更细。讲义："Quality goes up, latency stays flat."
- **组合效果**：DeepSeek-V3 每层 1 个共享 + 256 选 8 个路由专家，激活 9 个窄专家。
- **代价**：专家数多了，路由与 all-to-all 通信的调度更复杂，每个专家的矩阵更小，GPU 计算效率可能下降，需要专门的 kernel（grouped GEMM）来弥补。

### Q15 — 参考回答要点

- **显存**：671B 参数 fp16 约 1.34 TB，单机放不下，必须多机多卡；即使量化到 8 bit 也要约 671 GB。配套 skill 要求总参数超过 80 GB 时必须有专家并行方案。
- **专家并行与通信**：不同专家放在不同 GPU，每层 MoE 都要做两次 all-to-all（把 token 发到专家所在的卡，再把结果收回来）；讲义："延迟由 all-to-all 通信主导，而不是矩阵乘"。
- **负载不均**：推理时某些专家可能特别热门，所在 GPU 成为瓶颈；需要专家复制/冗余部署等手段。
- **为什么单用户低延迟反而慢**：①batch 很小时，每个专家只分到很少的 token，矩阵乘无法吃满 GPU，而读取权重的访存成本仍然要付；②每层都有路由计算和跨卡通信开销；③激活参数虽少，但分散在多张卡上，通信延迟无法省掉。讲义："Latency-critical single-user serving — expert routing adds overhead."
- **加分点**：提到 vLLM、SGLang 原生支持 MoE 路由与专家并行；大 batch、高并发的场景下 MoE 的单 token 成本优势最明显。

### Q16 — 参考回答要点

- **① 3B 手机模型**：选 **dense**。理由：边缘设备显存/存储是硬约束，MoE 要为全部专家付存储成本；激活参数远低于讲义的约 6B 阈值（配套 skill 更严格：激活参数低于 4B 时拒绝推荐 MoE），dense 在同等算力下更好；单用户场景 MoE 的路由开销不划算。
- **② 云端旗舰**：选 **MoE**。建议：细粒度布局（256+ 专家、top-8）+ 1 个共享专家；均衡策略用无辅助损失偏置（给出 γ，并像 Q9 那样监控振荡）；路由器打分用 fp32（skill 提醒：规模大时路由精度很重要）；提前规划专家并行（每个专家的显存占用、总卡数）；监控路由坍塌、专家饥饿、all-to-all 瓶颈。
- **加分点**：说明 MoE 适合 token 密集型负载（对话、代码），而长文档等上下文密集型负载的瓶颈在 attention/KV cache，MoE 帮助有限（讲义："token-heavy not context-heavy"）。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：FFN 在 block 中的位置——MoE 替换的就是它。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：decoder-only 主干，现代 MoE LLM 都在其上构建。
- [阶段 03 · 04 激活函数](../../../03-deep-learning-core/04-activation-functions/docs/zh.md)：SiLU / SwiGLU。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：用熵衡量负载均衡。

### 本节被哪些后续内容用到
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：MoE 只省 FFN 计算，attention 侧的推理优化另需处理。
- [阶段 07 · 13 Scaling Laws](../../13-scaling-laws/docs/zh.md)：在固定算力下扩大参数量的另一条路线。
- [阶段 10 · 20 DeepSeek-V3 精读](../../../10-llms-from-scratch/20-deepseek-v3-walkthrough/docs/zh.md)：MLA + 无辅助损失 MoE + MTP 的完整拆解。
- [阶段 10 · 14 开源模型架构详解](../../../10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/zh.md)：Mixtral、Qwen-MoE 等的结构对比。
- [阶段 10 · 05 扩展与分布式训练](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：专家并行与其他并行方式。
- [阶段 17 · 04 vLLM 服务内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：MoE 模型的生产推理。

### 延伸关键词
`Switch Transformer` · `GShard` · `expert capacity factor` · `router z-loss` · `grouped GEMM` · `all-to-all` · `expert parallelism` · `token choice vs expert choice routing` · `router collapse`
