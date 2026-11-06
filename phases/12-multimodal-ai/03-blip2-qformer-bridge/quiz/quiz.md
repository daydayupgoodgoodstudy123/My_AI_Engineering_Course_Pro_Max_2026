# 测验 · 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former（From CLIP to BLIP-2 — Q-Former as Modality Bridge）

> **阶段 12 · 多模态 AI · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要"桥" | CLIP 只能对齐、打分，不能生成；要让冻结的 LLM "看图说话"，需要把视觉特征变成 LLM 能吃的 token |
| 2 | Token 预算问题 | 讲义：ViT-g/14 每图 256 个 1408 维 patch token，直接喂给 LLM 每图多 256 个 token，32 张图就是 8192 个 |
| 3 | Learnable queries | 32 个可学习向量作为 cross-attention 的 Q，图像 patch 作为 K/V；同一组 query 用于所有图像，输出固定 32 个视觉 token |
| 4 | Cross-attention | Q 来自一处、K/V 来自另一处；权重矩阵 `(32, 256)`，每行 softmax 后和为 1；输出长度由 query 数决定，与 patch 数无关 |
| 5 | Q-Former 两条路径 | query 路径：self-attn → cross-attn（看图）→ FFN；text 路径：类 BERT 文本 encoder，与 query 路径共享 self-attn 和 FFN，不做 cross-attn |
| 6 | 两阶段训练 | Stage 1 无 LLM：ITC（对比）+ ITM（匹配二分类，hard negative）+ ITG（以图为条件生成文本）；Stage 2 接冻结 LLM，用 LM loss 训练 Q-Former + 线性投影 |
| 7 | 参数经济学 | 讲义：ViT-g（1.1B，冻结）+ OPT-6.7B（冻结）+ Q-Former（188M，训练）≈ 8B，只训 2.4% |
| 8 | 变体 | InstructBLIP：把指令也输入 Q-Former，query 随指令而变；MiniGPT-4：沿用 BLIP-2 的 Q-Former，只训输出投影 |
| 9 | 与 LLaVA、Flamingo 的对比 | LLaVA：2 层 MLP 把全部 576 个 patch 送进 LLM（质量优先）；Flamingo：在 LLM 每层插 gated cross-attention；BLIP-2：只在输入端压缩一次 |
| 10 | 选型原则 | 讲义："The deciding question is whether you are constrained on token budget or on quality-per-token." 长视频/多图 → Q-Former 类；单图高质量 → MLP |

### 核心技能（能动手做到）

- [ ] 写出 learnable-query cross-attention 的前向计算，并说清每一步的形状（`(32, D)` × `(256, D)` → `(32, 256)` → `(32, D)` → `(32, D_llm)`）
- [ ] 用注意力熵判断注意力是"弥散"还是"集中"，并能解释为什么本节代码未训练的注意力就已经接近 one-hot
- [ ] 按"self-attn → cross-attn → FFN + 残差"把本节的单个 cross-attention 扩展成一个 Q-Former 层
- [ ] 说清 BLIP-2 Stage 1 三个损失各自的输入、输出和作用，以及 Stage 2 训练哪些参数
- [ ] 给定视觉 token 数、每 prompt 图片数、上下文窗口，计算 Q-Former 与 MLP projector 的 token 成本和参数量
- [ ] 读本节代码时能指出讲义与代码在规模、行为描述上的不一致

---

## 二、基础自测（选择题）

**Q1.** 关于 Q-Former 中的 learnable queries，下列说法正确的是：

- A. 每张图像都会生成一组新的 query，由图像内容计算得到
- B. 它们是模型参数，训练中学习，推理时所有图像共用同一组 32 个 query，作为 cross-attention 的 Q 去"读取"图像 patch
- C. 它们就是 LLM 的文本 token embedding
- D. 它们是 ViT 输出的 CLS token 的 32 份复制

**Q2.** 关于 BLIP-2 的两阶段训练，下列说法正确的是：

- A. Stage 1 就把冻结 LLM 接上，用 LM loss 训练 Q-Former
- B. Stage 1 和 Stage 2 都要解冻 ViT
- C. Stage 2 只训练 LLM，Q-Former 冻结
- D. Stage 1 不涉及 LLM，只训练 Q-Former（ITC + ITM + ITG）；Stage 2 接上冻结 LLM，用 LM loss 训练 Q-Former 和线性投影

**Q3.** 32 个 query、256 个 patch 做单头 cross-attention，注意力权重矩阵的形状和性质是：

- A. `(32, 256)`，每一行 softmax 后和为 1
- B. `(256, 32)`，每一列和为 1
- C. `(32, 32)`，对称矩阵
- D. `(256, 256)`，因果下三角

**Q4.** 按讲义的配置（ViT-g/14 1.1B 冻结 + OPT-6.7B 冻结 + Q-Former 188M 训练），可训练参数约占全部参数的：

- A. 0.2%
- B. 12%
- C. 2.4%
- D. 24%

**Q5.** 讲义练习 5：一段 10 分钟视频采样成 60 帧，Q-Former 每帧 32 token，MLP projector 每帧 576 token，LLM 上下文 128k（131,072）token。下列说法正确的是：

- A. 两者分别需要 1,920 和 34,560 个 token，都放得下；但若按 1 FPS 取满 600 帧，MLP 需要 345,600 个 token，放不下，Q-Former 只需 19,200
- B. 两者都放不下 128k
- C. Q-Former 需要 34,560 个 token，MLP 需要 1,920 个
- D. 两者 token 数相同，因为 patch 数一样

**Q6.** 运行本节代码，未训练的 DEMO 输出 `mean entropy: 0.199 (uniform baseline: 4.159)`，大多数 query 的 top-1 权重接近 1.000。最主要的原因是：

- A. 这说明随机初始化的 query 已经学会了关注重要 patch
- B. softmax 实现有 bug，没有减去最大值
- C. `W_q`、`W_k` 按标准正态 `N(0, 1)` 初始化、没有按 `1/√fan_in` 缩放，Q、K 的数值很大，缩放后的 logit 标准差仍约 13，softmax 严重饱和
- D. patch 数（64）太少

**Q7.** 关于 BLIP-2、Flamingo、LLaVA 三种连接方式，说法正确的是：

- A. 三者都在 LLM 的每一层插入 cross-attention
- B. LLaVA 用 Q-Former 把图像压缩到 32 个 token
- C. BLIP-2 必须解冻 LLM 才能工作
- D. Flamingo 在冻结 LLM 的多层插入 gated cross-attention；BLIP-2 只在输入端用 Q-Former 压缩一次；LLaVA 用 MLP 把全部 patch token 投影后送入 LLM

**Q8.** InstructBLIP 相比 BLIP-2 的关键改动是：

- A. 用 MLP 替换 Q-Former
- B. 把指令文本也送入 Q-Former，使 query 在 cross-attention 时能"按指令"提取视觉信息，而不是对所有问题都给出同一个固定摘要
- C. 把 query 数从 32 增加到 576
- D. 解冻 ViT 一起训练

---

## 三、动手 / 代码题

**Q9.** 讲义 Use It 部分说代码"模拟 256 个 patch token（dim 128）、32 个 learnable query（dim 128）、投影到 LLM 维度 512"。

1. 实际代码的常量是什么？docstring 和最后的 TAKEAWAYS 又是怎么写的？列出所有不一致之处。
2. 按代码实际常量，`cross_attention` 输出的 `attended`、`attn` 和 `projected` 的形状各是什么？
3. 一次 `cross_attention` 中，计算注意力 logit（`dot(q, k)`）一共做了多少次长度为 16 的点积？如果换成讲义规模（32 × 256），是多少次？

**Q10.** 阅读 `demo_biased` 的 docstring：

```python
def demo_biased() -> None:
    """Show that if queries learn to align with specific patches, attention
    concentrates (lower entropy). Here we simulate by re-using a few patch
    vectors as the queries themselves."""
```

运行结果中，8 个 query 的 top-1 权重是 0.199、0.155、0.259、0.603、0.365、0.482、0.857、0.309。

1. 这个 DEMO 的平均注意力熵与未训练 DEMO（0.199）相比是更高还是更低？docstring 的说法成立吗？
2. 为什么 `demo_biased` 几乎必然"YES"，而权重却不高？（提示：W 都是单位矩阵，16 维独立高斯向量的自身点积与互相点积各是什么量级？）
3. 应当怎样修改实验，才能真正演示"训练前弥散、对齐后集中"？

**Q11.** 讲义说 Q-Former 的 query 路径是"self-attention（query 之间）→ cross-attention（看 ViT patch）→ FFN"。本节代码只实现了中间那一步。请用 NumPy 写一个 `QFormerLayer`：

1. 包含三个子层和残差连接，权重按 `N(0, 1/fan_in)` 初始化；
2. 输入 32 × 128 的 query、256 × 128 的 patch，输出 query 新状态与 cross-attention 权重；
3. 再接一个 128 → 512 的线性投影得到"LLM 输入 token"，打印各形状并检查注意力行和。

**Q12.** 参数与 token 预算计算：

1. 一个 2 层 MLP projector：1408 → 4096 → 4096（含 bias），参数量是多少？只用一层 1408 → 4096 线性层呢？与 188M 的 Q-Former 相比如何？
2. 技能文件写道："'Use MLP' with 576 tokens per image fails at 10 images in a 4k context." 请用数字验证，并算出换成 Q-Former 后 10 张图占 4k 上下文的比例。

---

## 四、面试高频题

**Q13.**（基础必考）请介绍 BLIP-2 的整体架构和两阶段训练流程。哪些参数冻结、哪些参数训练？推理时数据怎么流动？

**Q14.**（原理深挖）BLIP-2 Stage 1 的 ITC、ITM、ITG 三个损失分别在做什么？为什么需要三个而不是只用其中一个？如果跳过 Stage 1 直接做 Stage 2，会有什么问题？

**Q15.**（原理深挖）Q-Former 的 query 路径和 text 路径共享 self-attention。在三种损失下，query 与 text 之间应该如何设置注意力可见性（mask）？为什么？

**Q16.**（场景设计）你要做一个"监控视频问答"产品：每个问题需要看 10 分钟视频，LLM 上下文 32k，训练算力有限。你会选 Q-Former、Perceiver resampler 还是 MLP projector？给出 token 计算和理由。

**Q17.**（追问型）既然 Q-Former 压缩率高、训练便宜，为什么 2023 年后 LLaVA 式 MLP projector 反而成为主流？Q-Former 的固定 32 token 瓶颈会在哪类任务上吃亏？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The queries are parameters of the model — they are learned during training and the same 32 queries are used for every image." 不同图像得到不同输出，是因为 K/V 来自不同的 patch，而不是 query 本身变了。A 描述的是"输入相关的 query"（InstructBLIP 部分做到了，但也是通过把指令加入 self-attention，而不是重新生成 query）。C、D 都与 Q-Former 无关。讲义 Key Terms 把它比作"视觉的 soft prompt"。

### Q2 — 答案：D

讲义："Only the Q-Former trains. The ViT is frozen. No LLM involved."（Stage 1）；"Train only the linear projection and the Q-Former on LM loss"（Stage 2）。A 把 Stage 2 的内容放进了 Stage 1；B 错，ViT 全程冻结；C 说反了，LLM 全程冻结。

### Q3 — 答案：A

每个 query 对全部 256 个 patch 打分，`Q @ Kᵀ` 是 `(32, D) @ (D, 256) = (32, 256)`，softmax 沿最后一维（patch 维）做，所以每**行**和为 1。随后 `weights @ V = (32, 256) @ (256, D) = (32, D)`。输出长度由 query 数决定——这就是"压缩"的来源。讲义练习 1 要求验证的正是这两个性质。

### Q4 — 答案：C

`0.188 / (1.1 + 6.7 + 0.188) = 0.188 / 7.988 ≈ 2.35%`（已用 Python 计算），讲义："The Q-Former alone is ~2.4% of the full stack's parameters." A 少了一个数量级；B、D 都远高于实际。

### Q5 — 答案：A

`60 × 32 = 1,920`，`60 × 576 = 34,560`，都小于 131,072。注意讲义写的是"at 1 FPS sampled to 60 frames"：10 分钟按 1 FPS 本应是 600 帧，此时 `600 × 576 = 345,600` 放不下，`600 × 32 = 19,200` 仍然轻松放下。这正是讲义"Q-Former survives where token budget matters (long video, many images)"的数值依据。C 把两者说反；D 忽略了 Q-Former 的输出长度只取决于 query 数。

### Q6 — 答案：C

代码 `vec(n)` 用 `rng.gauss(0, 1)` 生成所有矩阵。`Q = W_q · q` 的每个分量是 16 个 `N(0,1)·N(0,1)` 之和，方差约 16；Q·K 再求 16 项乘积和，方差约 `16 × 16 × 16 = 4096`，标准差约 64；乘以 `1/√16 = 0.25` 后约 16。实测 8 × 64 个 logit 的标准差为 13.2。softmax 输入差几十，结果就是 one-hot。真实网络用 `N(0, 1/fan_in)` 一类的初始化，让 logit 标准差保持在 1 左右；我们用这种缩放重跑（不同随机种子），平均熵约 3.47、最大权重约 0.70，明显更弥散。A 错：根本没有训练。B 错：`softmax` 已经减去 `max(xs)`。D 错：patch 少只会让 uniform 熵变小（ln 64 = 4.159），不会让注意力饱和。

### Q7 — 答案：D

讲义："Flamingo ... used the same cross-attention idea but at every frozen LLM layer, not as a single bridge. BLIP-2 showed you can compress to the input layer only and still work."；LLaVA "replaced the Q-Former with a plain 2-layer MLP that projects every ViT patch token into LLM space — 576 tokens per image"。A、B 张冠李戴；C 错：BLIP-2 的 LLM 全程冻结。

### Q8 — 答案：B

讲义："At cross-attention time, the queries now have access to both the image patches and the instruction. The queries can specialize per-instruction ('count the cars', 'describe the mood') rather than learning a single fixed summary." A 是 LLaVA 的做法；C 不对，query 数仍很小；D 不对，ViT 仍冻结。

### Q9 — 参考答案

1. 实际常量：`NUM_PATCH = 64`、`PATCH_DIM = 16`、`NUM_QUERY = 8`、`QUERY_DIM = 16`、`LLM_DIM = 24`。不一致之处：
   - 讲义 Use It：256 个 128 维 patch、32 个 128 维 query、投影到 512；
   - `make_queries` 的 docstring 写 "32 learnable query vectors, dim 16"，实际生成 8 个；
   - `make_patches` 的 docstring 写 64 个 16 维，与代码一致，但与讲义不一致；
   - TAKEAWAYS 打印 "cross-attention maps (32 queries, 256 patches) -> 32 summaries"，而本次运行实际是 8 × 64；
   - 模块 docstring 写 "256 'patch tokens'"、"32 learnable query vectors"。

   缩小规模是为了让纯 Python 循环跑得快，这是合理的；但文字说明应同步修改。
2. `attended`：8 个长度 16 的列表，即 `(8, 16)`；`attn`：`(8, 64)`，每行和为 1；`projected`：`W_out` 是 `mat(24, 16)`，`matmul_vec(W, x)` 计算 `W · x`，得到 `(8, 24)`。程序打印 "output: 8 tokens of dim 24"。
3. 代码规模：`8 × 64 = 512` 次点积；讲义规模：`32 × 256 = 8,192` 次（每次长度 128）。cross-attention 的代价是 `O(N_query × N_patch × D)`，与 patch 数线性相关；作为对比，在 LLM 内对 576 个视觉 token 做 self-attention 需要 `576 × 576 = 331,776` 个注意力分数（每层），这也是压缩视觉 token 能省算力的原因。

### Q10 — 参考答案

1. 用相同的随机数序列重现后计算：`demo_biased` 的 8 个熵为 3.423、3.604、3.283、2.197、2.931、2.607、0.908、3.112，平均约 **2.758**，远**高于**未训练 DEMO 的 0.199。docstring 的"concentrates (lower entropy)"在这次运行中不成立：所谓"对齐后"的注意力反而比"未训练"更弥散。两个 DEMO 的对比完全被初始化尺度（Q6）主导，而不是被"是否对齐"主导。
2. `W_q = W_k = I`，所以 logit = `p_i · p_j / 4`。自身点积 `‖p‖²` 期望为 16（实测这 8 个 patch 为 11.2～26.4），互相点积均值为 0、标准差约 4。缩放后自身 logit 约 4，其余 63 个 logit 标准差约 1。自身得分通常是最高的，所以"YES"几乎必然；但 63 个对手中总有几个能达到 2～3，softmax 后自身权重只有 0.15～0.86。范数大的 patch（如 26.4 的 patch 11）权重最高（0.857），这与"学到了什么"无关。
3. 改进方式：
   - 两个 DEMO 使用**相同的、合理缩放的**投影矩阵（如 `N(0, 1/16)`），只改变 query；
   - "未训练"用随机 query，"对齐后"用 `α · patch[favored]`，扫描 α（如 1、2、4），观察熵随 α 下降；
   - 或者真正写一个训练循环：设定一个目标（如让 query i 重建 patch `favored[i]` 的 value），对 query 做梯度下降，打印每步的平均熵。

### Q11 — 参考答案

```python
import numpy as np
rng = np.random.default_rng(0)

def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)

def layernorm(x, eps=1e-5):
    return (x - x.mean(-1, keepdims=True)) / np.sqrt(x.var(-1, keepdims=True) + eps)

def attn(xq, xkv, Wq, Wk, Wv, Wo):
    Q, K, V = xq @ Wq, xkv @ Wk, xkv @ Wv
    A = softmax(Q @ K.T / np.sqrt(Q.shape[-1]))      # (Nq, Nkv)
    return (A @ V) @ Wo, A

def init(din, dout):
    return rng.normal(0, 1 / np.sqrt(din), (din, dout))

class QFormerLayer:
    def __init__(self, d, d_img, d_ff):
        self.sa = [init(d, d) for _ in range(4)]
        self.ca = [init(d, d), init(d_img, d), init(d_img, d), init(d, d)]
        self.W1, self.W2 = init(d, d_ff), init(d_ff, d)
    def __call__(self, q, img):
        h, _ = attn(layernorm(q), layernorm(q), *self.sa); q = q + h   # query 之间 self-attention
        h, A = attn(layernorm(q), img, *self.ca);       q = q + h   # query -> patch cross-attention
        q = q + np.maximum(0, layernorm(q) @ self.W1) @ self.W2      # FFN
        return q, A

queries = rng.normal(0, 1, (32, 128))
patches = rng.normal(0, 1, (256, 128))
out, A = QFormerLayer(128, 128, 512)(queries, patches)
llm_tokens = out @ init(128, 512)
print(out.shape, A.shape, np.allclose(A.sum(1), 1), llm_tokens.shape)
```

实际运行输出：`(32, 128) (32, 256) True (32, 512)`；cross-attention 平均熵 5.04（均匀分布为 ln 256 = 5.545），合理缩放后初始注意力是弥散的，与本节代码的饱和状态形成对比。

要点：
- cross-attention 的 K/V 投影输入维度是 `d_img`（ViT 维度，BLIP-2 中为 1408），Q 的维度是 Q-Former 自身维度（768），两者可以不同，K/V 投影负责对齐维度；
- 为简洁这里用了 pre-norm 和单头；BERT 风格的 Q-Former 实际是 post-norm、多头；
- 文本路径复用 `self.sa` 和 FFN，但跳过 cross-attention 这一步。

### Q12 — 参考答案

1. 2 层 MLP：`1408 × 4096 + 4096 + 4096 × 4096 + 4096 = 22,552,576 ≈ 22.6M`；单层线性：`1408 × 4096 + 4096 = 5,771,264 ≈ 5.8M`（已用 Python 计算）。技能文件给 MLP projector 的量级是"~20M"，与此一致。Q-Former 188M 约是 2 层 MLP 的 8 倍。参数多并不代表 Q-Former 更贵——它让 LLM 每张图只处理 32 个 token，LLM 侧的计算更省；MLP 参数少，但让 LLM 多处理 576 个 token。
2. MLP：`10 × 576 = 5,760 > 4,096`，确实放不下，连提示词都没地方放。Q-Former：`10 × 32 = 320`，只占 4k 上下文的 `320 / 4096 ≈ 7.8%`。

### Q13 — 参考回答要点

- **组成**：冻结的图像 encoder（ViT-g/14）→ Q-Former（32 个 learnable query + 12 层类 BERT Transformer）→ 线性投影 → 冻结的 LLM（OPT 或 Flan-T5）。
- **Stage 1（表示学习）**：不接 LLM，只训练 Q-Former，用 ITC + ITM + ITG，让 32 个 query 学会提取"与文本相关"的视觉信息。
- **Stage 2（生成学习）**：把 query 输出经线性层投影到 LLM 的 embedding 维度，作为"软视觉 prompt"拼到文本前面，用 LM loss 训练 Q-Former 和投影层，LLM 冻结。
- **推理**：图像 → ViT → Q-Former（只走 query 路径）→ 线性投影 → 32 个视觉 token + 文本 prompt → 冻结 LLM 生成。
- **参数**：讲义："8B total, 188M trained"，约 2.4%；训练时间"days on a handful of A100s vs weeks for end-to-end"。
- 加分点：讲义："BLIP-2 matches or beats Flamingo-80B on zero-shot VQA while being 50x smaller." 注意，按总参数算 8B 对 80B 只差 10 倍，"50 倍"这个说法只有按**可训练参数**比较才说得通，面试时要讲清口径。

### Q14 — 参考回答要点

- **ITC（对比）**：query 输出与文本 CLS embedding 做 CLIP 式对比，拉近匹配对、推远不匹配对，学习全局对齐。讲义写作"pooled query tokens"；据 BLIP-2 论文，具体做法是分别计算 32 个 query 输出与文本的相似度，取最大值作为图文相似度。
- **ITM（匹配）**：二分类"这对图文是否匹配"，负例用 hard negative mining 挑选（例如 ITC 认为相似但实际不匹配的对），迫使 query 区分细粒度差异。
- **ITG（生成）**：以 query 为条件，让文本路径做因果语言建模，迫使 query 编码"能被文字说出来"的内容——这是最贴近 Stage 2 的目标。
- **为什么三个**：ITC 学粗粒度对齐、ITM 学细粒度判别、ITG 学可生成性，三者互补；讲义 Further Reading 指出这套组合来自 BLIP 和 ALBEF。
- **跳过 Stage 1**：query 一开始是随机的，冻结的 LLM 只能看到无意义的软 prompt，Stage 2 的 LM loss 既要学"看什么"又要学"怎么对齐 LLM"，训练更难、效果更差。BLIP-2 论文的消融实验报告了跳过表示学习会显著降低 zero-shot VQA 表现（可作为加分点引用，具体数字以论文为准）。

### Q15 — 参考回答要点

- **ITC**：单模态 mask——query 只看 query，text 只看 text，二者互不可见。否则 query 可以直接"抄"文本信息，对比任务就变得平凡。
- **ITM**：双向 mask——query 与 text 互相可见，query 输出已经融合了文本，再接一个二分类头判断是否匹配。
- **ITG**：多模态因果 mask——query 之间互相可见但看不到 text（否则会泄露答案）；text token 可以看到全部 query 和自己之前的 text token，做自回归生成。
- 核心思想：用不同的注意力 mask 在**同一套共享权重**上实现三种任务，这正是讲义所说的"queries and text interact through shared self-attention, which means the queries can condition on text for tasks that need it (ITM, ITG)"。
- 常见误区：以为三种任务需要三套模型。

### Q16 — 参考回答要点

- **token 计算**：10 分钟视频，即使 1 FPS 也有 600 帧。
  - MLP（576 token/帧）：345,600 token，远超 32k；就算降到 0.1 FPS（60 帧）也要 34,560，仍超过 32k。
  - Q-Former（32 token/帧）：600 帧 19,200（占 32k 的 60%），60 帧只要 1,920。
  - Perceiver resampler：同样输出固定数量 latent（如每帧 64），token 量级与 Q-Former 相当。
- **推荐**：Q-Former 或 Perceiver resampler 类的固定长度压缩器；先降采样到合理帧率（如 0.2～0.5 FPS，必要时按场景变化做关键帧选取），每帧 32 token。训练算力有限，可沿用开源的预训练 Q-Former，只训投影层或少量层（MiniGPT-4 思路）。
- **风险**：监控画面中的小目标、车牌文字等细节可能在 32 token 中丢失；对这类需求可加"放大裁剪"二次查询。
- 技能文件的拒绝规则："If the caller asks for a bridge that can handle video without specifying how many frames and at what frame rate, refuse"——实际工作中也要先把帧率和帧数定下来再选型。

### Q17 — 参考回答要点

- **LLaVA 胜出的原因**（讲义）：MLP 让 LLM 直接看到全部原始 patch，"lets the LLM attend over raw patches"；视觉指令数据（LLaVA-Instruct-150k）证明 MLP 足以保留信号；结构简单，天然扩展到多图和视频。
- **Q-Former 的瓶颈**：
  - 固定 32 个 token 是**与问题无关**的压缩（InstructBLIP 部分缓解），对 OCR、图表、文档、小物体计数等需要细粒度空间信息的任务容易丢信息；
  - 两阶段预训练流程复杂，Stage 1 需要三种损失和多种 mask；
  - query 的表示是 Stage 1 训练出来的，换 LLM 时适配性差（讲义对 MiniGPT-4 的评价："the queries were BLIP-2's, not yours"）。
- **结论**：讲义："Q-Former survives where token budget matters (long video, many images); MLP projector dominates where raw quality per token is the priority." 技能文件也强调不能说"Q-Former strictly dominates MLP"。
- 加分点：后续的 any-resolution 方案（第 06 节）让 MLP 路线的 token 数进一步增加，于是又出现了 pixel shuffle、token 合并等折中压缩方法。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：ITC 就是 CLIP 式对比损失，BLIP-2 的视觉塔也是对比预训练得来的。
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../01-vision-transformer-patch-tokens/docs/zh.md)：patch token 的数量与维度从哪里来。
- [阶段 07 · 05 完整的 Transformer — Encoder + Decoder](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：encoder-decoder 中的 cross-attention 原型。
- [阶段 07 · 06 BERT——掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：Q-Former 从 BERT-base 初始化。
- [阶段 07 · 03 多头 Attention](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：缩放点积注意力与 `1/√d` 缩放。

### 本节被哪些后续内容用到
- [阶段 12 · 04 Flamingo：面向 Few-Shot VLM 的门控 Cross-Attention](../../04-flamingo-gated-cross-attention/docs/zh.md)：Perceiver resampler 与"每层 cross-attention"的另一条路线。
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：用 MLP projector 替代 Q-Former。
- [阶段 12 · 07 开放 Weight VLM 的构建方案：真正重要的因素](../../07-open-weight-vlm-recipes/docs/zh.md)：连接器结构与数据的消融对比。
- [阶段 12 · 17 视频语言模型：时间 Tokens 与 Grounding](../../17-video-language-temporal-grounding/docs/zh.md)：视频场景下的 token 预算。
- [阶段 19 · 60 用于 Modality Alignment 的投影层](../../../19-capstone-projects/60-projection-layer-modality-align/docs/zh.md)、[阶段 19 · 61 Cross-Attention 融合](../../../19-capstone-projects/61-cross-attention-fusion/docs/zh.md)：综合项目中亲手实现投影层与 cross-attention 融合。

### 延伸关键词
`Q-Former` · `learnable queries` · `cross-attention` · `ITC / ITM / ITG` · `hard negative mining` · `attention mask` · `InstructBLIP` · `MiniGPT-4` · `Perceiver resampler` · `MLP projector` · `token budget` · `frozen backbone` · `ALBEF`
