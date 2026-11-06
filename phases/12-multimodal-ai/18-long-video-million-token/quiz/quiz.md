# 测验 · 百万 Token 上下文中的长视频理解（Long-Video Understanding at Million-Token Context）

> **阶段 12 · 多模态 AI · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，错误较多（如"384 native resolution"被译成"340 本地分辨率"、needle-in-a-haystack 被译成"针头在海雀中"），请以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 长视频 token 预算公式 | `tokens = 时长(秒) × FPS × 每帧 token`；384 分辨率约 729 token/帧，3×3 池化后 81；30 分钟 1 FPS = 145,800，2 小时 = 583,200 |
| 2 | 路径 1：brute context | 直接把上下文扩到百万级，一次前向看完全部（Gemini 1.5 / 2.5）；工程细节未公开，不开源 |
| 3 | 路径 2：ring attention | 序列切块分布在多设备组成的"环"上，KV 块沿环轮转、各设备算局部注意力再合并；单卡显存随 `n / 设备数` 增长（LWM、LongVILA） |
| 4 | LongVILA 的规模 | 讲义：1,400 帧 × 192 token = 约 268k 上下文，8 路并行的 ring attention 训练 |
| 5 | 路径 3：token compression | 进 LLM 前先压缩：Video-XL 每个片段产生一个"视觉摘要 token"；LongVA 做"long context transfer"；代价是特定时刻的召回率下降（recall tax） |
| 6 | 路径 4：agentic retrieval | VideoAgent：LLM 读问题 → 调检索工具找片段 → VLM 读片段 → 回答或追问；推理便宜，但检索质量成为瓶颈 |
| 7 | Needle-in-a-haystack（NIAH） | 在视频随机位置插入唯一标记再提问；指标是按视频长度和标记位置统计的 Recall@k |
| 8 | 按时长选路径 | <15 分钟：开源 72B 直接看；30–60 分钟：LongVILA / Video-XL 或 Gemini 2.5 Pro；2 小时以上：检索或分层摘要 |
| 9 | 2026 生产混合模式 | 全片动态 FPS + 激进池化得到约 100k token 的全局表示 → 72B VLM 做全局摘要 → 细节问题用以摘要为索引的 agentic retrieval |
| 10 | 成本对比的隐藏项 | 代码里检索方案约 7,490 token、brute context 583,200 token（便宜约 98.7%），但没算建立检索索引时对整段视频的一次性处理成本 |

### 核心技能（能动手做到）

- [ ] 给任意时长、FPS、池化方案算出 token 数，并判断能否放进 32k / 128k / 256k / 1M 上下文
- [ ] 反推：给定上下文上限（如 80k）和视频时长，求出最多能用的 FPS 或每帧 token 数
- [ ] 用 NumPy 写出 ring attention 的 online-softmax 合并，并验证它与完整注意力结果一致
- [ ] 设计一个 30 分钟视频的 NIAH 测试：插入位置、标记类型、查询格式、评分方式
- [ ] 把本节"只返回概率"的 NIAH 模拟改成真正的多次试验并计算 recall
- [ ] 根据时长、问题类型（单事件 vs 全局摘要）、开源/闭源约束选择长视频策略

---

## 二、基础自测（选择题）

**Q1.**（讲义练习 1）一段 45 分钟的讲座，按 1 FPS 抽帧、每帧 81 个 token，总 token 数是：

- A. 145,800
- B. 218,700
- C. 291,600
- D. 3,645

**Q2.** 关于 ring attention，下列说法正确的是：

- A. 它让注意力的总计算量随上下文长度线性增长，彻底消除了二次复杂度
- B. 每个设备只对自己持有的那一块做注意力，块与块之间不交互
- C. 每个设备保留自己的 Q 块，K/V 块沿环依次传递，逐块计算并用 online softmax 合并；单卡显存随"序列长度 / 设备数"增长，而注意力的总 FLOPs 仍是序列长度的二次方
- D. 它是一种 token 压缩方法，通过减少 token 数来支持长视频

**Q3.** Video-XL 处理长视频的核心手段是：

- A. 每个 N 帧片段产生一个"视觉摘要 token"，该 token 对这 N 帧做注意力；推理时 LLM 每个片段只看一个摘要 token
- B. 把 LLM 的上下文扩到 1,000 万 token
- C. 用 LLM 调用检索工具找相关片段
- D. 在 8 张卡上用 ring attention 训练 268k 上下文

**Q4.** 按讲义，agentic retrieval（VideoAgent）路线的主要工程瓶颈是：

- A. prefill 阶段的算力
- B. 检索质量——工具找不到正确片段，后面的 VLM 再强也没用
- C. ring attention 的环形通信
- D. KV cache 显存

**Q5.** 本节代码中 `Qwen2.5-VL-72B @ 15min` 的召回曲线为 `[(0.1, 0.98), (0.5, 0.90), (1.0, 0.85)]`，随机插入的 needle 在第 560.6 秒（视频共 900 秒），`nih_trial` 返回的 `recall_prob` 是：

- A. 0.98
- B. 0.90
- C. 0.62
- D. 0.85

**Q6.** 代码打印 "-> 99% cheaper inference for single-event queries"（检索约 7,490 token vs brute context 约 583,000 token）。这个对比**遗漏**了哪项成本？

- A. 检索工具要能"找到猫跳的片段"，前提是事先对整段视频建立索引（字幕、片段描述或嵌入），这一步要处理全部视频
- B. 3 个 30 秒片段 × 81 token/帧的编码成本
- C. 问题和答案本身的约 200 个 token
- D. brute context 方案按 1 FPS、81 token/帧计算的 token 数

**Q7.** 讲义开头说"1 小时 4K、24 FPS 的视频，打成 patch 并嵌入后约有 6,000 万 token"。这个数字隐含的每帧 token 数约为：

- A. 42,000（按 4K 原生分辨率、14×14 patch 计算）
- B. 196
- C. 694
- D. 81

**Q8.** 用户上传 2 小时电影，问"猫是在什么时候跳起来的"，要求用开源模型。按讲义和 skill 文件，最合理的策略是：

- A. Qwen2.5-VL-72B 以 1 FPS、81 token/帧直接看完整部电影
- B. 自己用 ring attention 从头训练一个 1M 上下文的视频模型
- C. 用 Video-XL 式压缩直接回答，不必提示召回损失
- D. VideoAgent 式 agentic retrieval：先检索候选片段，再让 VLM 精读

---

## 三、动手 / 代码题

**Q9.** 阅读 `budget_table()`：

```python
    cases = [
        (60, 1, 81,     "32k+"),
        (300, 1, 81,    "32k"),
        (300, 2, 81,    "128k"),
        (1800, 1, 81,   "256k"),
        (3600, 1, 81,   "1M / LongVILA"),
        (7200, 1, 81,   "Gemini 2.5 only"),
        (7200, 1, 32,   "agentic retrieval"),
    ]
    for dur, fps, pf, fits in cases:
        t = tokens(dur, fps, pf)
        print(f"{dur//60}min{' ':<8}{fps:>5}{pf:>12}{t:>12,}   {fits}")
```

1. 运行输出里，`1min`、`5min` 两行与 `30min`、`120min` 行的列对不齐，原因是什么？怎么改？
2. "fits in" 一列有两处值得商榷，请结合讲义数字指出。

**Q10.** `nih_trial` 返回的只是查表得到的概率，并没有真正"测试召回"：

```python
def nih_trial(duration_s, model_recall_curve):
    needle_t = random.uniform(0, duration_s)
    needle = Needle(t=needle_t, marker="unique sticker")
    pct_into_video = needle_t / duration_s
    for thresh, recall in model_recall_curve:
        if pct_into_video <= thresh:
            return {"needle_time": needle_t, "pct_into_video": pct_into_video, "recall_prob": recall}
    ...
```

1. 指出这段代码里没有被用到的东西。
2. 写一个 `nih_recall(duration_s, curve, n_trials=10000)`：多次插针、按概率判定答对与否，返回经验召回率。`Qwen2.5-VL-72B @ 30min` 的理论期望值是多少？与讲义"开源 72B 在 30 分钟约 85–90%"是否一致？

**Q11.**（讲义练习 3）1 小时视频，开源方案是 80k 上下文的 Qwen2.5-VL-72B，另一方案是 VideoAgent（检索 3 个 30 秒片段）。

1. 若坚持每帧 81 token，brute context 最多能用多大 FPS？总 token 数是多少？
2. 对"猫第一次出现在第几秒"这种单事件问题，哪种方案召回更好？哪种延迟更低？对"总结这一小时讲了什么"呢？

**Q12.**（讲义练习 4）用 NumPy 实现一个玩具 ring attention：序列长 12、维度 4、3 个"设备"，每个设备持有一块 Q，K/V 块沿环轮转。

1. 写出合并各块结果的 online softmax 更新公式并实现，验证与完整注意力的最大误差。
2. 如果去掉"沿环轮转"这一步（每个设备只用自己的 K/V 块），结果会怎样？

---

## 四、面试高频题

**Q13.**（基础必考）长视频理解有哪几条技术路线？各自的代表工作、优点和代价是什么？

**Q14.**（原理深挖）ring attention 是怎么把百万 token 的注意力分到多张卡上的？它节省的是计算还是显存？为什么通信可以被"藏"起来？

**Q15.**（工程实践）如何为一个长视频 VLM 设计 needle-in-a-haystack 评测？只测 NIAH 够不够？

**Q16.**（场景设计）设计一个"企业会议录像问答"系统：每场 1–3 小时，用户既会问"讨论了哪些议题"，也会问"张三什么时候提到预算"。请给出架构与 token / 延迟预算。

**Q17.**（追问型）既然 Gemini 已经能吃下几小时的视频，为什么还需要 agentic retrieval？反过来，检索方案在什么问题上会输给 brute context？

---

## 五、参考答案与解析

### Q1 — 答案：B

`45 × 60 × 1 × 81 = 218,700`（已用 Python 计算）。能放进 256k 级别上下文，放不进 128k。A 是 30 分钟的结果；C 是 30 分钟 2 FPS 或 60 分钟 1 FPS 的结果；D 是 `45 × 81`（误把分钟当帧数）。

### Q2 — 答案：C

ring attention 的本质是**分布式的分块注意力**：每个设备持有一块 Q，K/V 块沿环传递 N 次，每次算一个"Q 块 × KV 块"的部分结果，用 online softmax（维护行最大值和归一化分母）合并，最终与完整注意力**数值等价**（见 Q12 实测误差约 1e-16）。

- A 是讲义原文的说法（"Training compute scales linearly with context, not quadratically"），但不准确：所有 Q 和所有 K 仍要两两相乘，总 FLOPs 仍为 O(n²)；被"摊销"的是**单卡显存和单卡计算量**——它们按设备数平分了。
- B 是去掉轮转后的"块内局部注意力"，会丢失跨块信息（Q12 第 2 问实测误差 1.35）。
- D 混淆了路径 2 和路径 3。

### Q3 — 答案：A

讲义："Video-XL uses a visual summary token: each clip of N frames produces a single 'summary' token that attends over the N. At inference, the LLM sees one summary token per clip"。B 是 Gemini 1.5 的 brute context；C 是 VideoAgent；D 是 LongVILA。

### Q4 — 答案：B

讲义："Cheaper inference (only relevant clips encoded), harder engineering (retrieval quality becomes the bottleneck)"。skill 文件也强调检索路线不是万能的。A、D 是 brute context 的瓶颈；C 是 ring attention 训练的问题。

### Q5 — 答案：D

`pct_into_video = 560.6 / 900 ≈ 0.623`。按顺序比较阈值：0.623 > 0.1，0.623 > 0.5，0.623 ≤ 1.0，于是返回第三档 0.85（与实际运行输出 `p(recall)=0.85` 一致）。C 是位置百分比本身，不是召回率。

### Q6 — 答案：A

`agentic_retrieval_sim` 里 `hits` 是三个随机数，工具"凭空"返回了时间戳。真实系统中，`find_clips(keyword='jump')` 只有在事先对整段视频做过索引（逐段生成描述、提取 CLIP 嵌入或语音转写）时才能工作，这一步本身就要把全部视频过一遍；只是它可以离线做、一次索引多次查询摊薄。B、C 已包含在 `tokens_used = 3 * 30 * 81 + 200 = 7,490` 中；D 是对比的另一侧。顺带一提：`7,490 / 583,200 ≈ 1.28%`，即便宜约 98.7%，代码说"99%"是取整。

### Q7 — 答案：C

1 小时 24 FPS = 86,400 帧，`60,000,000 / 86,400 ≈ 694` token/帧（已用 Python 计算），相当于每帧缩到约 384 分辨率（讲义自己给出的 384 分辨率约 729 token/帧）。如果真按 4K 原生分辨率、14×14 patch 计算，每帧约 `274 × 154 = 42,196` token，1 小时约 **36 亿** token，比讲义说的多 60 倍。所以"6,000 万"这个数字只在"先降采样到 ~384 分辨率"的前提下成立。

### Q8 — 答案：D

2 小时 × 1 FPS × 81 = 583,200 token，超过开源 72B 的上下文。skill 文件的硬性否决第一条就是"Proposing brute-context for a 2-hour video on an open 72B model. Context does not fit"（A 错）；B 成本不现实；C 违反了"Recommending token compression without flagging the recall tax"。单事件定位问题恰好是检索最擅长的场景，讲义："For 2+ hour content: VideoAgent or similar retrieval patterns"。

### Q9 — 参考答案

1. `f"{dur//60}min{' ':<8}"` 先输出变长的 `"1min"` / `"30min"` / `"120min"`，再固定补 8 个空格，所以分钟数位数不同，后面所有列就整体右移。正确做法是把整个时长字符串作为一个字段统一对齐：

```python
label = f"{dur // 60}min"
print(f"{label:<14}{fps:>5}{pf:>12}{t:>12,}   {fits}")
```

2. 两处商榷：
   - `60min` 行（291,600 token）标为 "1M / LongVILA"：放进 1M 没问题，但讲义说 LongVILA 训练的上下文是 `1,400 × 192 ≈ 268,800`（讲义写作 268k），291,600 已经超出。
   - `120min @ 32 token/帧`（230,400 token）标为 "agentic retrieval"：这一行本身是"更激进的池化 + brute context"，230,400 能放进 256k 上下文，与检索无关；检索方案的 token 数应是几千（见代码后面的 7,490）。把它写成 "256k (aggressive pool)" 更准确。

### Q10 — 参考答案

1. `needle = Needle(...)` 创建后从未使用，`marker="unique sticker"` 也没有参与任何判断；函数既没有"提问"，也没有"判分"，只是按位置查表返回一个概率。`Needle` dataclass 因此是摆设。另外，曲线中的召回率是作者设定的假设值，不是任何测量结果。
2. 参考实现（已运行验证）：

```python
def nih_recall(duration_s, curve, n_trials=10000, seed=0):
    rng_state = random.getstate()
    random.seed(seed)
    hits = 0
    for _ in range(n_trials):
        r = nih_trial(duration_s, curve)
        hits += random.random() < r["recall_prob"]   # 按概率抛硬币，模拟答对与否
    random.setstate(rng_state)                       # 不影响主程序后续的随机序列
    return hits / n_trials
```

   - 理论期望：位置均匀分布，落在 `[0, 0.1]`、`(0.1, 0.5]`、`(0.5, 1]` 的概率是 0.1、0.4、0.5，所以 `0.1 × 0.95 + 0.4 × 0.85 + 0.5 × 0.75 = 0.81`；10,000 次试验实测 0.8153。
   - 与讲义"Open 72B models ... score ~85-90% at 30 minutes"不一致：代码把后半段设成 0.75，导致平均值只有 81%。15 分钟曲线的期望是 0.883（实测 0.8875）。
   - 改进方向：真实 NIAH 要在视频帧里贴入标记、构造查询、让模型回答并自动判分，按"时长 × 插入深度"画热力图。

### Q11 — 参考答案

1. `80,000 / 3,600 ≈ 22.2` token/秒，除以 81 得最大 FPS ≈ 0.274，即**约每 4 秒取 1 帧**（0.25 FPS）：`3,600 × 0.25 × 81 = 72,900` token。也可以反过来保持 1 FPS、把每帧压到 22 token 以下（约 4×4 的网格），代价是空间细节。
2. 单事件问题（"猫第一次出现在第几秒"）：
   - **召回**：0.25 FPS 意味着两帧间隔 4 秒，短暂出现的猫可能直接被抽帧漏掉；检索方案若索引质量好，可以精确命中片段并以高帧率精读，通常**检索更好**（讲义："VideoAgent can match or beat raw-context models at 2+ hours because retrieval hits the needle if the tool is good"）。
   - **延迟**：brute context 只有一次约 73k token 的 prefill；检索需要"LLM 规划 → 工具检索 → VLM 编码片段 → LLM 回答"多轮调用，单次查询未必更快，但每次的 token 量只有约 7k。若索引已离线建好，检索方案的在线计算量小得多。
   - 全局摘要问题：检索方案只看到 3 个片段，必然以偏概全；brute context 虽然稀疏，但覆盖了全片，**brute context 胜出**。skill 文件："Claiming agentic retrieval always wins ... For holistic-summary questions it loses to brute context"。

### Q12 — 参考答案

1. online softmax：对每一行维护当前最大值 `m`、分母 `l` 和未归一化的输出 `acc`。来一个新块的分数 `s` 时：

```text
m_new = max(m, rowmax(s))
scale = exp(m - m_new)
p     = exp(s - m_new)
l     = l * scale + rowsum(p)
acc   = acc * scale + p @ V_block
m     = m_new
最终输出 = acc / l
```

```python
import numpy as np
np.random.seed(0)
n, d, N = 12, 4, 3
Q, K, V = (np.random.randn(n, d) for _ in range(3))

def full_attn(Q, K, V):
    s = Q @ K.T / np.sqrt(d)
    w = np.exp(s - s.max(1, keepdims=True)); w /= w.sum(1, keepdims=True)
    return w @ V

def ring_attn(Q, K, V, N):
    Qs, Ks, Vs = np.split(Q, N), np.split(K, N), np.split(V, N)
    outs = []
    for i in range(N):                       # 设备 i 只持有自己的 Q 块
        m = np.full((len(Qs[i]), 1), -np.inf)
        l = np.zeros((len(Qs[i]), 1))
        acc = np.zeros_like(Qs[i])
        for step in range(N):                # KV 块沿环转一圈
            j = (i + step) % N
            s = Qs[i] @ Ks[j].T / np.sqrt(d)
            m_new = np.maximum(m, s.max(1, keepdims=True))
            scale = np.exp(m - m_new)
            p = np.exp(s - m_new)
            l = l * scale + p.sum(1, keepdims=True)
            acc = acc * scale + p @ Vs[j]
            m = m_new
        outs.append(acc / l)
    return np.vstack(outs)

print(np.abs(full_attn(Q, K, V) - ring_attn(Q, K, V, N)).max())   # 1.1e-16
```

   实测最大误差 `1.1e-16`（浮点舍入级），说明分块 + 轮转 + online softmax 与完整注意力等价。单卡同时只需存 1 个 Q 块和 1 个 KV 块，显存 ∝ n/N；真实实现中"算当前块"与"把 KV 块发给下一个设备"同时进行，通信被计算掩盖。

2. 去掉轮转（每个设备只对自己的 K/V 做注意力）后实测最大误差 **1.35**：模型退化成"块内局部注意力"，第 1 块的 token 永远看不到第 3 块。对长视频而言，这意味着开头的画面无法与结尾的问题关联，NIAH 召回会在跨块位置崩溃。

### Q13 — 参考回答要点

| 路线 | 代表 | 优点 | 代价 |
|------|------|------|------|
| brute context | Gemini 1.5 / 2.5 Pro | 一次看全，全局与细节兼顾；讲义称 NIAH 召回极高 | 硬件成本极高；闭源、细节未公开；prefill 延迟大 |
| ring attention | LWM、LongVILA | 开源可训练超长上下文；与完整注意力数值等价 | 需要多卡集群；总 FLOPs 仍是 O(n²)；推理同样昂贵 |
| token compression | Video-XL、LongVA | 便宜，可在单卡上处理更长视频 | recall tax：特定时刻、细小物体可能丢失 |
| agentic retrieval | VideoAgent | 推理只编码相关片段，超长视频也可做 | 工程复杂；检索质量决定上限；对全局摘要类问题吃亏 |

- 加分点：说出生产中常用混合方案——全局低分辨率摘要 + 局部检索精读（讲义 "2026 production pattern"）。
- 常见误区：把 ring attention 说成"线性复杂度"；把 token compression 和检索混为一谈。

### Q14 — 参考回答要点

- **切分**：长度为 n 的序列切成 N 块，第 i 个设备持有第 i 块的 Q、K、V。
- **轮转**：每一步，设备用本地 Q 块与当前手上的 KV 块算部分注意力，同时把 KV 块发给环上的下一个设备、接收上一个设备的 KV 块；N 步后每个 Q 块都见过全部 KV。
- **合并**：用 online softmax（与 FlashAttention 同样的技巧）维护每行的最大值和分母，逐块累加，结果与完整注意力完全一致。
- **省的是什么**：主要是**单卡显存**——不再需要在一张卡上放下 n×n 的分数矩阵或全部 KV；单卡计算量也被 N 张卡平分。**总计算量没有变**，仍是 O(n²)。讲义"compute scales linearly"的表述应理解为"单卡负担随设备数线性摊薄"。
- **通信为什么能藏起来**：每一步的计算量 ∝ (n/N)² × d，传输量 ∝ (n/N) × d，块足够大时计算时间大于传输时间，可以完全重叠。
- 对因果模型还要处理掩码导致的负载不均（后面的块要看更多前文），实际实现会用条带式（striped）分块等方式均衡。这一点属于加分项。

### Q15 — 参考回答要点

- **构造**：在视频的不同深度（如 0%、10%、25%、50%、75%、90%、100%）插入唯一标记——视觉标记（画面角落叠加一个特殊图案或一行文字）或文本标记（字幕中插入一句话）；同时覆盖多种视频长度（5、15、30、60、90 分钟）。
- **查询格式**：固定模板，如"视频中出现过一个印有 `XJ-42` 的贴纸，它出现在第几分钟、贴在什么物体上？"；答案可自动判分（时间误差 ≤ 30 秒且物体正确）。
- **指标**：Recall@k 按"长度 × 深度"画热力图，观察"中间迷失"（lost in the middle）现象；同时记录 prefill 延迟和成本。
- **对照组**：不插针的视频问同样的问题，检验模型是否会"幻觉出"一个贴纸。
- **只测 NIAH 不够**：NIAH 只测"能否找回一个突兀的标记"，不测跨时间段的推理（如"他第二次进门时手里拿的是什么"）、计数、因果关系。还要配合 EgoSchema、VideoMME 长视频子集等基准（第 17 节）。
- 本节代码的 NIAH 只是查表，不算真正的测试（见 Q10）。

### Q16 — 参考回答要点

- **预处理（离线，一次）**：
  1. 音频 ASR + 说话人分离，得到带时间戳和说话人的转写——会议问答的主要信息在语音里（2 小时转写约 3 万 token，讲义开头就给出了这个量级）；
  2. 视频动态 FPS（幻灯片切换时加密）+ 激进池化，对每个 30–60 秒片段生成描述，并抽取幻灯片 OCR；
  3. 把转写段、片段描述、OCR 建成带时间戳的检索索引（向量 + 关键词混合）。
- **全局类问题**（"讨论了哪些议题"）：用全部转写 + 片段描述（约几万到十几万 token）一次性送入长上下文模型生成分层摘要，结果缓存。
- **定位类问题**（"张三什么时候提到预算"）：说话人过滤 + 关键词/语义检索 → 返回候选片段 → 对候选片段的转写和关键帧做精读 → 输出时间戳 JSON（第 17 节格式）。
- **预算**：3 小时 × 1 FPS × 81 = 874,800 token，直接 brute context 不现实；检索方案每次查询约几千到 1 万 token，延迟主要来自 1–2 轮 LLM 调用。
- **评测**：人工标注议题列表与若干"谁在何时说了什么"问题，分别评估摘要覆盖率与定位 recall@IoU。

### Q17 — 参考回答要点

- **为什么还需要检索**：
  - 成本：每次提问都 prefill 几十万到几百万 token，费用和延迟都高；检索只编码相关片段（本节估算约 7k vs 58 万 token）。
  - 开源约束：开源模型上下文放不下 2 小时视频。
  - 超长或流式视频：监控录像、直播等长度无上限，没有上下文能装下。
  - 可解释性：检索结果天然带"证据片段"，便于展示和审计。
- **检索会输的场景**：
  - 全局摘要、情节走向、人物关系等需要通盘理解的问题；
  - 线索分散在多个片段、单独看每段都不起眼的问题（检索的 query 很难写出来）；
  - 检索索引本身质量差（描述漏掉了关键物体），后续环节无法补救。
- 结论：两者互补，生产中用混合模式。加分点：引用 skill 文件的规则——需要实时流式时拒绝检索方案（太慢），整体摘要类问题不能宣称检索总是更好。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 17 视频语言模型：时间 Tokens 与 Grounding](../../17-video-language-temporal-grounding/docs/zh.md)：本节的先修课，抽帧、池化和时间编码是 token 预算的基础。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：ring attention 的 online softmax 与 FlashAttention 同源。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：理解多卡切分和通信重叠。
- [阶段 05 · 28 长上下文 Evaluation — NIAH、RULER、LongBench、MRCR](../../../05-nlp-foundations-to-advanced/28-long-context-evaluation/docs/zh.md)：文本领域的 NIAH 与长上下文评测方法。

### 本节被哪些后续内容用到
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../24-multimodal-rag-cross-modal/docs/zh.md)：agentic retrieval 所依赖的跨模态检索索引。
- [阶段 12 · 25 多模态 Agents 与计算机操作（综合项目）](../../25-multimodal-agents-computer-use/docs/zh.md)：LLM-as-agent 模式在多模态任务中的综合应用。
- [阶段 11 · 05 Context Engineering: 窗口、预算、记忆和检索](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：上下文预算与"塞满 vs 检索"的一般性取舍。
- [阶段 19 · 12 综合项目 12：视频理解流程——场景、问答与搜索](../../../19-capstone-projects/12-video-understanding-pipeline/docs/zh.md)：把长视频索引、问答和搜索落到工程中。

### 延伸关键词
`ring attention` · `blockwise parallel transformer` · `online softmax` · `sequence parallelism` · `visual summary token` · `long context transfer` · `needle-in-a-haystack` · `lost in the middle` · `VideoAgent` · `hierarchical summarization` · `recall tax`
