# 测验 · 视频生成（Video Generation）

> **阶段 08 · 生成式 AI · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 视频 = 多了时间轴的图像 | 理论与图像扩散相同，算力难 10–100 倍；10 秒 1080p 24fps 的原始像素约 1.5 GB，像素空间扩散不可行 |
| 2 | 四个核心难题 | 时空压缩、时间一致性（运动建模）、算力预算、多种条件（文本、首帧图、音频、另一段视频） |
| 3 | 3D VAE + 时空 patch | 用视频 VAE 把 `(T,H,W,C)` 压成时空潜变量，再切成 `[t_p, h_p, w_p]` 的 3D patch 作为 token；`t_p` 常取 1 或 2 |
| 4 | 时空 DiT | transformer 处理展平的 patch 序列，每个 patch 带 3D 位置编码（时间 + y + x）；损失与第 06 节相同（ε 或 v 预测） |
| 5 | 分解注意力 | 帧内做空间注意力 + 同一空间位置跨帧做时间注意力；完整 3D 注意力贵 16–100 倍，只在低分辨率或研究中用 |
| 6 | 闪烁（flicker） | 逐帧独立用图像模型生成，各帧噪声相互独立 → 闪烁；视频扩散通过注意力或共享噪声把帧耦合起来联合去噪 |
| 7 | 数据与描述 | 讲义强调"描述质量比数据量更重要"：用 LLM 给训练片段重新生成详细描述（re-captioning） |
| 8 | 条件与长视频 | 图生视频（I2V）以首帧为条件，训练时就包含这种变体；超过 10 秒容易物理漂移，用滑动窗口 + 关键帧锚定缓解 |
| 9 | 生产部署 | 10B 以上模型常用 TP=4；I2V 的首帧条件可以像 LLM 的 prompt prefill 一样只算一次、多次复用 |

### 核心技能（能动手做到）

- [ ] 运行 `code/main.py`，解释 joint 与 independent 两组帧间差（delta）的含义，并指出 5 个 clip 的统计量为什么不可靠
- [ ] 给定分辨率、帧率、时长、VAE 压缩倍数，估算原始数据量、潜变量大小和 patch 数
- [ ] 给定帧数 F 和每帧 patch 数 N，计算完整 3D 注意力与分解注意力的复杂度之比
- [ ] 在玩具代码上实现首帧条件（固定第 0 帧、生成其余帧），并量化固定值如何向后传播
- [ ] 能设计一个"公平"的逐帧独立基线，说明代码自带基线的问题
- [ ] 能按需求（最高质量托管、开源微调、I2V、对口型）选模型，并说出长视频和闪烁的工程对策

---

## 二、基础自测（选择题）

**Q1.** 一段 10 秒、1080p（1920×1080）、24fps 的 RGB 视频（每像素每通道 1 字节），原始数据量约为：

- A. 50 MB
- B. 150 MB
- C. 1.5 GB
- D. 15 GB

**Q2.** 视频 DiT 中常用的"分解注意力"指的是：

- A. 把多头注意力的各个头分到不同 GPU 上计算
- B. 帧内的 patch 之间做空间注意力，再在同一空间位置的不同帧之间做时间注意力
- C. 只对关键帧做注意力，其他帧用插值
- D. 把 Q、K、V 矩阵做低秩分解

**Q3.** 某视频潜变量有 F = 16 帧，每帧 N = 1024 个 patch。只看注意力分数矩阵的规模（token 对数），完整 3D 注意力的开销大约是"空间 + 时间"分解注意力的多少倍？

- A. 约 2 倍
- B. 约 16 倍
- C. 约 256 倍
- D. 约 1024 倍

**Q4.** 用一个优秀的文生图模型逐帧生成视频，结果闪烁严重，根本原因是：

- A. 图像模型分辨率不够
- B. 每帧的初始噪声和采样过程相互独立，没有任何机制让相邻帧共享内容
- C. 帧率太低
- D. 没有使用 CFG

**Q5.** 时空 patch 大小设为 `[t_p, h_p, w_p] = [2, 2, 2]`，与 `[1, 2, 2]` 相比：

- A. token 数增加一倍
- B. 每个 token 覆盖两个连续的潜变量帧，时间方向的 token 数减半
- C. 只影响空间分辨率
- D. 两者没有区别

**Q6.** 关于图生视频（I2V），下列说法正确的是：

- A. 只能在推理时临时固定首帧，模型训练时不需要考虑
- B. 模型以图像 + 文本为输入，输出从这张图开始的视频；训练时就包含这种变体
- C. I2V 不能同时使用文本提示词
- D. I2V 必须使用完整 3D 注意力

**Q7.** 生成 30 秒的长视频时，后半段逐渐出现物体变形、物理不合理，讲义建议的缓解方法是：

- A. 一次性生成 30 秒，加大 CFG
- B. 滑动窗口生成 + 关键帧锚定
- C. 降低帧率到 8fps
- D. 换成逐帧独立的图像模型

**Q8.** 讲义的 Pitfalls 中关于训练数据的观点是：

- A. 数据量是唯一重要的因素
- B. 描述（caption）的质量比数据规模更重要，Sora 用 LLM 给训练片段重新生成了详细描述
- C. 视频模型不需要文本描述，只用无标注视频即可
- D. 只用合成数据训练效果最好

---

## 三、动手 / 代码题

**Q9.** 阅读下面两段代码：

```python
T_FRAMES = 6
POS_DIM = 4

def patchify_with_pos(video):
    """Each 'patch' here is one frame value + its time position embedding."""
    out = []
    for t in range(T_FRAMES):
        pe = sin_embed(t, POS_DIM)
        out.append([video[t]] + pe)
    return out

# main() 中
net = init_net(T_FRAMES * (1 + POS_DIM) + t_dim, hidden, T_FRAMES, rng)
```

(a) 网络输入维度是多少（`t_dim = 8`）？
(b) 在这个 **MLP** 里，每帧附带的位置编码对预测有没有贡献？为什么？
(c) 讲义说真实系统中"每个 patch 都带 3D 位置编码"。为什么在 transformer 里它必不可少？

**Q10.**（讲义练习 2）仿照第 09 节的 inpainting，给 `main.py` 加一个首帧条件采样函数 `sample_i2v(net, alphas, alpha_bars, T, t_dim, first, rng)`：每个反向步把第 0 帧替换成 `first` 的加噪版本，其余帧正常生成。

按训练数据的生成方式（`slope ~ N(0, 0.3)`），如果第 0 帧固定为 `+2.0`，理想情况下后面各帧的均值应该是多少？实际跑出来会怎样？为什么？

**Q11.**（评审代码）`main.py` 用下面的函数作为"逐帧独立"的闪烁基线：

```python
def independent_per_frame(T_frames, rng):
    """Baseline: sample each frame independently from a random walk."""
    return [rng.gauss(0, 1) + 0.3 * t for t in range(T_frames)]
```

(a) 这个基线与训练数据 `make_video` 的分布一致吗？有什么问题？docstring 里的 "random walk" 准确吗？
(b) 设计一个更公平的独立基线。
(c) `main.py` 只用 5 个 clip（25 个 delta）就下结论，合适吗？

---

## 四、面试高频题

**Q12.**（基础必考）视频生成相比图像生成难在哪里？主流的 Sora 式架构是怎样解决的？

**Q13.**（原理深挖）为什么视频 DiT 普遍使用"空间 + 时间"的分解注意力？代价是什么？什么时候值得用完整 3D 注意力？

**Q14.**（原理深挖）视频生成中的"闪烁"是怎么产生的？从模型结构、噪声、采样三个层面说说怎么抑制。

**Q15.**（场景设计）要为广告片生成一段 30 秒、1080p、主角在多个镜头中保持一致、需要对口型的视频。请给出模型选择、镜头拆分和质检方案。

**Q16.**（工程实践）你要自建一个开源视频生成服务（如 WAN 2.2 / HunyuanVideo 级别，10B+ 参数）。说说推理侧的并行、缓存与批处理思路，以及显存/延迟的主要瓶颈。

**Q17.**（追问型）Sora 为什么被称为"世界模拟器"？这种说法有什么局限？

---

## 五、参考答案与解析

### Q1 — 答案：C

`240 帧 × 1920 × 1080 × 3 ≈ 1.49 × 10⁹` 字节 ≈ 1.5 GB，与讲义一致。这也说明为什么必须先用 3D VAE 压缩到潜空间。

### Q2 — 答案：B

讲义：Spatial attention within each frame's patches + Temporal attention across frames at the same spatial location。A 是张量并行；D 是低秩注意力近似，都不是这里的"分解"。

### Q3 — 答案：B

- 完整 3D：所有 `F·N = 16384` 个 token 两两相关，`(F·N)² ≈ 2.68 × 10⁸`；
- 分解：空间 `F·N² = 16 × 1024² ≈ 1.68 × 10⁷`，时间 `N·F² = 1024 × 256 ≈ 2.6 × 10⁵`，合计 `≈ 1.70 × 10⁷`；
- 比值 `≈ 15.8`，约 16 倍。一般地，比值 `= F·N / (N + F)`，在 N ≫ F 时约等于 F。帧数越多，完整 3D 越不划算，这与讲义"贵 16–100 倍"的量级一致。

### Q4 — 答案：B

讲义 Pitfalls："If you run image diffusion on each frame separately, the output flickers because each frame's noise is independent."每帧单独看都合理，但颜色、纹理、细节在帧间随机跳变。视频扩散通过注意力或共享噪声把帧耦合起来。

### Q5 — 答案：B

`t_p = 2` 表示每个 patch 跨越两个连续的潜变量帧，时间方向的 token 数减半，序列更短、计算更省，代价是时间分辨率更粗。讲义提到 Sora 式模型取 `t_p = 1`（逐帧）或 `t_p = 2`（每两帧）。

### Q6 — 答案：B

讲义："Most production models also accept an image as the first frame. This is 'image-to-video' mode; training includes this variant."I2V 仍然可以加文本描述运动（C 错）。A 的"只在推理时临时固定"是 Q10 的做法，效果明显不如训练时就加入首帧条件。

### Q7 — 答案：B

讲义：Long clips (>10s) accumulate subtle inconsistencies. Sliding-window generation + keyframe anchoring helps. 配套 skill 也提到：超过 10 秒的连续运动通常要分镜头拼接。

### Q8 — 答案：B

讲义 Pitfalls 的标题就是 "Data captioning matters more than size"，并在 Concept 中提到 Sora 的训练集使用了 GPT 生成的密集重描述。另外"合成文本描述"也被列为训练数据的组成部分，但并不意味着只用合成数据（D 错）。

### Q9 — 参考答案

(a) 每帧 `1 + POS_DIM = 5` 维，6 帧共 30 维，再加 `t_dim = 8` 维的扩散时间步编码，共 **38** 维。`W1` 是 48×38。

(b) **基本没有贡献**。`sin_embed(t, POS_DIM)` 只依赖帧序号 `t`，对每个训练样本都是**同一组常数**（第 0 帧永远是 `[0, 1, 0, 1]`……），而且每帧的值在展平向量中的**位置是固定的**（第 0 帧的值永远在第 0 个输入槽）。对全连接层来说，常数输入只相当于多了一点偏置；"第几帧"这个信息已经由"在哪个输入槽"隐式给出。这里 `POS_DIM = 4` 时第二个频率是 1e-4，对应的两维在 6 帧内几乎恒为 `[0, 1]`，就更没有信息量了。

(c) Transformer 的自注意力对输入顺序是**置换等变**的：把 token 顺序打乱，输出也只是跟着打乱，模型本身不知道哪个 token 在前、在哪个空间位置。视频 DiT 把时空 patch 展平成一个序列，必须给每个 patch 加上 (时间, y, x) 三维位置编码，模型才能区分"同一帧的相邻 patch"和"相邻帧的同一位置"，分解注意力也需要依靠这些坐标来分组。另外，transformer 可以处理变长序列（不同时长、分辨率），位置编码是唯一的位置来源，而 MLP 的输入长度是写死的。

### Q10 — 参考答案

```python
def sample_i2v(net, alphas, alpha_bars, T, t_dim, first, rng):
    x = [rng.gauss(0, 1) for _ in range(T_FRAMES)]
    for t in range(T - 1, -1, -1):
        a_bar = alpha_bars[t]
        x[0] = math.sqrt(a_bar) * first + math.sqrt(1 - a_bar) * rng.gauss(0, 1)
        eps_hat, _ = forward(flatten(patchify_with_pos(x)), sin_embed(t, t_dim), net)
        beta_t = 1 - alphas[t]
        mean = [(x[i] - beta_t / math.sqrt(1 - a_bar) * eps_hat[i]) / math.sqrt(alphas[t])
                for i in range(T_FRAMES)]
        x = [m + math.sqrt(beta_t) * rng.gauss(0, 1) for m in mean] if t > 0 else mean
    x[0] = first
    return x
```

**理想情况**：训练数据是 `base + slope·t + 小噪声`，`slope` 均值为 0，已知第 0 帧 ≈ `base`，所以后面各帧的**条件均值都应约等于 `first`**（各帧围绕 `+2.0` 展开成一个扇形，越往后方差越大）。

**实际**（同一种子训练后，每个 `first` 采样 200 次）：

```text
first=-2.0: per-frame mean -2.00 -0.89 -0.43 -0.51 -0.13 +0.04 | mean |x1-x0| 1.12
first=+0.0: per-frame mean +0.00 +0.02 +0.19 -0.04 +0.05 -0.05 | mean |x1-x0| 0.42
first=+2.0: per-frame mean +2.00 +0.94 +0.88 +0.57 +0.39 +0.12 | mean |x1-x0| 1.08
```

固定值的方向能传递下去（符号正确），但**强度随帧距离衰减**，第 0→1 帧的跳变（约 1.1）远大于真实数据的帧间差（约 0.25）。原因：
1. 推理时临时固定首帧属于"朴素 mask 重注入"，模型在高噪声阶段只能看到严重加噪的首帧，信息很弱（第 09 节已经分析过）；
2. `|base| = 2` 处于先验 `N(0,1)` 的尾部，小网络在这里拟合得差；
3. `T = 40` 的调度终端 SNR 不为 0，采样起点与训练分布不一致。

这正是讲义说"training includes this variant"的原因：生产 I2V 模型把首帧作为**训练时的条件输入**（类似第 09 节的 9 通道 inpaint 模型），而不是只在推理时固定。

### Q11 — 参考答案

(a) **不一致，偏向"有利于 joint"**：
- 训练数据的帧间相关来自共享的 `base` 和 `slope`，`slope ~ N(0, 0.3)`，均值为 0；而基线写死了 `+0.3·t` 的趋势，并且每帧加入**独立**的 `N(0,1)` 噪声，它根本不是从数据分布中采样的；
- docstring 说 "random walk"，但随机游走是噪声**累加**（`x_{t+1} = x_t + ε`），这里每帧噪声相互独立、不累加，不是随机游走；
- 它也没有用到任何模型，只是"手写的独立噪声"，与"逐帧跑图像扩散模型"不完全对等。

(b) 更公平的基线：让每一帧都服从**真实的单帧边缘分布**，但帧与帧之间相互独立——例如第 t 帧取自一段新的、独立生成的 `make_video` 的第 t 帧：

```python
def independent_from_marginals(rng):
    return [make_video(rng)[t] for t in range(T_FRAMES)]
```

这对应"每帧都是一张好图片，但帧间不共享内容"的逐帧图像生成。我们在临时副本中统计了大样本的平均帧间差：

| 来源 | 平均 delta |
|------|-----------|
| 真实数据 `make_video`（2000 段） | 0.245 |
| joint 模型采样（300 段） | 0.359 |
| 代码自带基线（2000 段） | 1.163 |
| 公平基线：真实边缘分布、帧间独立（2000 段） | 1.484 |

结论没有改变（joint 远比独立采样平滑），但也能看出 joint 模型离真实数据（0.245）还有差距。

(c) 不合适。25 个 delta 的统计波动很大：`main.py` 输出的 joint 平均 delta 是 0.61，而 300 段的统计约为 0.36。评估生成模型时应该用足够多的样本，并报告均值和方差（讲义练习 1 也要求报告方差）。

### Q12 — 参考回答要点

- **难点**（讲义四点）：
  1. 数据量巨大，10 秒 1080p 原始像素约 1.5 GB；
  2. 时间一致性：内容、光照、物体身份要跨越几秒保持一致，要建模运动；
  3. 同等模型规模下训练成本是图像的 10–100 倍；
  4. 条件多样：文本、首帧图、音频、另一段视频。
- **方案**：
  - 3D VAE 做时空压缩 → 切成时空 patch（`t_p` 取 1 或 2）→ 展平成序列，加 3D 位置编码；
  - 时空 DiT（常用分解注意力）去噪，损失与图像扩散相同（ε 或 v 预测）；
  - 大型文本编码器 + cross-attention 注入文本；训练数据使用 LLM 重新生成的密集描述；
  - 最后用 3D VAE 解码。
- **加分点**：一个 10 秒 1080p 视频压缩后约有 2 万到 10 万个 patch，这决定了注意力设计和并行策略。

### Q13 — 参考回答要点

- **复杂度**：完整 3D 注意力是 `O((F·N)²)`；分解后是 `O(F·N² + N·F²)`，比值约为 `F·N/(F+N)`（见 Q3）。讲义说完整 3D 贵 16–100 倍，并且在 10 秒 1080p 上会 OOM。
- **代价**：分解注意力中，一个 token 不能在一层内直接关注"另一帧的另一个位置"，必须经过两层（先空间、再时间）间接传递信息；对大幅度运动、镜头切换、跨帧遮挡的建模能力较弱。
- **何时用完整 3D**：低分辨率、短片段，或者研究中追求最佳时空一致性；也可以结合窗口化、稀疏或分块注意力等折中方案。
- **加分点**：时间注意力在同一空间位置做，相当于假设"同一位置在时间上相关"，而运动会让物体离开原位置，所以需要多层堆叠来补偿。

### Q14 — 参考回答要点

- **成因**：帧与帧之间的高频细节没有耦合，每帧单独采样时这些细节随机变化。
- **模型结构**：联合去噪整段潜变量，用时间注意力 / 3D 注意力让帧间交换信息；用 3D VAE 在时间维上一起压缩（相邻帧共享潜变量）。
- **噪声**：讲义提到"共享噪声"——让各帧的初始噪声相关（例如共享一部分噪声分量），从源头减少独立性。
- **采样与长视频**：滑动窗口生成时让窗口重叠，以前一窗口的末帧作为锚点；关键帧锚定；首帧条件（I2V）。
- **评估**：统计帧间差、光流一致性，并逐帧人工质检（配套 skill 中的 QA 清单包括 flicker、身份一致性、物理违例）。
- **常见误区**：以为提高帧率就能消除闪烁——闪烁的根源是帧间不一致，与帧率无关。

### Q15 — 参考回答要点

- **模型**（讲义 Use It）：最高质量托管选 Veo 3 或 Sora；跨镜头的角色一致性选 Pika 2.0 或 Kling 2.1；对口型选 Veo 3（原生音频）或专用的口型同步模型。
- **镜头拆分**：30 秒远超单段 10 秒左右的稳定范围，应拆成 4–6 个镜头。为每个镜头写好镜头语言（推、拉、跟拍、手持）、主体、动作、光照风格；用同一张角色参考图做 I2V 的首帧锚点，保证主角一致。
- **可复现**：每个镜头固定 seed、锁定模型版本，记录全部参数。
- **音频**：Veo 3 原生音频；否则后期接 TTS/音乐，再做一遍口型同步。
- **质检**：逐帧检查闪烁、身份一致性、物理违例、水印合规；真人肖像需要授权（skill 中明确要求拒绝无授权的真人肖像）。

### Q16 — 参考回答要点

讲义 Production note 给出的思路：
- **张量并行**：10B+ 的视频 DiT 常用 TP=4（4 张 H100），在 all-reduce 通信成为瓶颈之前，单步延迟随 TP 近似线性下降。
- **首帧 prefill 缓存**：I2V 的首帧条件类似 LLM 的 prompt prefill，算一次、在后续去噪中复用，"相当于视频的 KV-cache"。
- **帧级批处理**：如果架构支持滑动窗口生成，可以借鉴连续批处理的思路，在返回前一段的同时开始渲染下一段。
- **瓶颈分析**：讲义认为视频潜变量的内存带宽是瓶颈。回答时最好补充自己的判断：每次前向有上万 token，矩阵乘法的计算密度很高，单请求的去噪步通常更接近算力瓶颈；带宽和显存压力主要来自长序列的激活和注意力中间结果。实际以 profiling 为准（讲义练习 3 就要求 profile 时空注意力）。
- **加分点**：3D VAE 解码本身也很吃显存，常需要按时间分块解码；可以用步数蒸馏减少去噪步数；结合第 07 节的 CPU offload / 量化在小显存上运行。

### Q17 — 参考回答要点

- **由来**：Sora 技术报告的标题就是 "Video generation models as world simulators"。讲义表格称它"First model to show world simulator properties at scale"：在大规模训练下，模型生成的视频表现出一定的 3D 一致性、物体恒存和简单的物理交互。
- **局限**：
  - 它学到的是视觉统计规律，不是显式的物理定律；讲义 Pitfalls 提到长视频会出现"physics drift"；
  - 没有可控的状态变量和动作接口，很难像游戏引擎或仿真器那样精确地做干预、回放；
  - 评估以视觉质量为主，缺少物理正确性的量化指标。
- **加分点**：可以联系视觉方向的"世界模型与视频扩散"小节，讨论动作条件的视频模型在机器人和自动驾驶中的应用。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 06 从头开始的 DDPM](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：本节代码的训练与采样流程。
- [阶段 08 · 07 潜空间扩散与 Stable Diffusion](../../07-latent-diffusion-stable-diffusion/docs/zh.md)：2D VAE → 3D VAE、U-Net → DiT、文本 cross-attention。
- [阶段 07 · 09 Vision Transformers](../../../07-transformers-deep-dive/09-vision-transformers/docs/zh.md)：patchify 与位置编码。
- [阶段 07 · 04 位置编码](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：理解为什么 transformer 需要显式的位置信息。

### 本节被哪些后续内容用到 / 相关小节
- [阶段 08 · 09 局部重绘、扩图与图像编辑](../../09-inpainting-outpainting-editing/docs/zh.md)：首帧/关键帧锚定与 mask 重注入是同一个思路。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../13-flow-matching-rectified-flows/docs/zh.md)：新一代视频模型常用的训练目标。
- [阶段 04 · 12 视频理解](../../../04-computer-vision/12-video-understanding/docs/zh.md)：视频的时空表示与分解卷积/注意力。
- [阶段 04 · 28 世界模型与视频扩散](../../../04-computer-vision/28-world-models-video-diffusion/docs/zh.md)：把视频生成用作世界模拟器。
- [阶段 12 · 17 视频-语言时序定位](../../../12-multimodal-ai/17-video-language-temporal-grounding/docs/zh.md)：视频理解侧的时序建模。
- [阶段 17 · 04 vLLM 服务内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：Production note 中类比的连续批处理与 KV-cache。

### 延伸关键词
`3D VAE / causal video VAE` · `spatiotemporal patch` · `factorized space-time attention` · `3D RoPE` · `re-captioning` · `image-to-video` · `keyframe anchoring` · `sliding window generation` · `flicker / temporal consistency` · `tensor parallelism`
