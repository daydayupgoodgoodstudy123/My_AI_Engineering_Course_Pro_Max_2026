# 测验 · InternVL3：原生多模态 Pretraining（InternVL3: Native Multimodal Pretraining）

> **阶段 12 · 多模态 AI · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：中文讲义为机器翻译，有疑义以英文版为准。本节讲义对 InternVL3 的若干描述与公开论文可能有出入（见 Q13 的"常见误区"），学习时建议对照原论文。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 后接式（post-hoc）VLM 的常规三步 | ① 冻结 LLM 与 encoder，只训 projector 对齐；② 解冻 LLM 做指令微调；③ 可选的任务微调。LLaVA、BLIP-2、Qwen-VL、Idefics 都是这条路 |
| 2 | 对齐债（alignment debt） | 讲义列出三个可测症状：灾难性遗忘（GSM8K 掉 5–10 分）、答案漂移（同一问题换个说法答案不同）、视觉-文本不一致（描述对了图却答出矛盾的答案） |
| 3 | 原生多模态预训练 | 文本 token、视觉 token 和跨模态交互从第一步起就在同一个 loss 里；基础模型单阶段训练，再做指令微调 |
| 4 | 语料配比 | 讲义：40% 纯文本、35% 交错图文、20% 图文对、5% 视频-文本；40% 文本是保住语言能力的"地板"，交错数据是多图推理的关键 |
| 5 | V2PE | 讲义描述：按模态（文本 1D、图像 2D、视频 3D）可变的位置编码，相对 M-RoPE 在视频基准上 +1–2 分 |
| 6 | ViR（Visual Resolution Router） | 编码前用小分类器预测回答问题所需的最低分辨率；三档 256 / 576 / 2048+ token；讲义称吞吐提升 2–3 倍 |
| 7 | DvD（Decoupled Vision-Language deployment） | 视觉 encoder 与 LLM 放到不同 GPU、流式衔接；二者瓶颈不同（encoder 每图一次，LLM 每输出 token 一次） |
| 8 | 讲义转述的效果 | 78B 对标 Gemini 2.5 Pro 的 MMMU-Pro，38B 对标 GPT-4o，8B 领跑开放 8B 档；InternVL3-8B 每单位视觉收益损失的文本分数更少 |
| 9 | 原生预训练的代价 | 算力（与训练文本 LLM 同量级）、交错语料稀缺（讲义：OBELICS 141M 文档）、放弃日后替换底座 LLM 的灵活性 |
| 10 | 后续：InternVL3.5 与 InternVL-U | 3.5 扩大规模；InternVL-U 在同一骨干上加 MMDiT 生成头，走"理解 + 生成"统一路线 |

### 核心技能（能动手做到）

- [ ] 说清后接式与原生预训练在训练流程、数据、算力、可复用性上的区别，并能列出对齐债的三个症状
- [ ] 读懂 `CorpusMix`，并能修复 `int()` 截断导致的步数总和不等于目标值的问题
- [ ] 手算 ViR 路由的平均 token 数与加速比，并考虑文本 token、误路由后对估算做修正
- [ ] 指出 `dvd_throughput` 的"加速比"在 GPU 数量上不公平，算出其理论上限，并说出 DvD 什么时候会适得其反
- [ ] 按任务（视频为主、OCR 为主）调整语料配比，并解释为什么仍要保留大量文本与图文对数据
- [ ] 按团队的算力、数据和"是否要换底座"的需求，给出原生 / 后接 / 混合的决策

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项**不是**讲义列出的后接式 VLM"对齐债"三个症状之一？

- A. 视觉 encoder 在第一阶段训练时不收敛
- B. 灾难性遗忘：纯文本能力下降，GSM8K 掉 5–10 分
- C. 答案漂移：同一视觉问题换个措辞，答案就变了
- D. 视觉-文本不一致：正确描述了图像，却给出与自己描述相矛盾的答案

**Q2.** 讲义给出的 InternVL3 原生预训练语料配比是：

- A. 10% 文本、40% 交错图文、40% 图文对、10% 视频
- B. 70% 文本、10% 交错图文、15% 图文对、5% 视频
- C. 40% 文本、35% 交错图文、20% 图文对、5% 视频
- D. 25% 文本、25% 交错图文、25% 图文对、25% 视频

**Q3.** 本节 `vir_sim` 使用三档 `256 / 576 / 2048` token、流量占比 `50% / 30% / 20%`，输出的平均 token 数与"加速比"是：

- A. 960 与 2.13x
- B. 1036.8 与 1.98x
- C. 2048 与 1.00x
- D. 710.4（打印为 710）与 2.88x

**Q4.** `dvd_throughput(300, 8, 128)`（encoder 每图 300 GFLOPs，LLM 每输出 token 8 GFLOPs，输出 128 个 token）打印的 speedup 是：

- A. 2.00x
- B. 1.29x
- C. 4.41x
- D. 0.77x

**Q5.** 关于原生预训练的代价，与讲义一致的是：

- A. 原生预训练比后接式更便宜，因为省去了对齐阶段
- B. 大规模交错图文语料稀缺；算力开销与训练文本 LLM 同量级；且放弃了日后只重训 adapter 就替换底座 LLM 的选项
- C. 原生预训练无法做指令微调
- D. 原生预训练必须冻结 LLM 才能稳定

**Q6.** 关于 ViR，下列说法正确的是：

- A. 它在 LLM 生成过程中动态丢弃视觉 token
- B. 它是一个替代 ViT 的轻量 encoder
- C. 对每一个请求都使用最高分辨率，以保证质量
- D. 它在编码之前用一个小分类器预测"回答该问题所需的最低分辨率"，只有查询分布混杂时才有收益

**Q7.** 关于 DvD，讲义的出发点是：

- A. 视觉 encoder 每张图只跑一次，LLM 却要为每个输出 token 自回归地跑一次，两者瓶颈不同，于是把它们拆到不同 GPU 上、用流式方式衔接
- B. 把 LLM 拆成多个专家放到不同 GPU 上
- C. 把训练和推理放到不同集群
- D. 让视觉 encoder 和 LLM 共享同一份 KV cache

**Q8.** 执行 `m = CorpusMix(29, 36, 30, 5); m.normalize(); m.steps(100)`，返回字典中 `"text"` 的值是：

- A. 29
- B. 30
- C. 28
- D. 0.29

---

## 三、动手 / 代码题

**Q9.** 阅读 `dvd_throughput`：

```python
def dvd_throughput(encoder_flops: int, llm_flops: int,
                   llm_tokens: int = 128) -> dict:
    colocated = encoder_flops + llm_flops * llm_tokens
    decoupled = max(encoder_flops, llm_flops * llm_tokens)
    return {"colocated": colocated, "decoupled": decoupled,
            "speedup": colocated / decoupled}
```

1. 这个 speedup 在硬件上公平吗？如果按"每块 GPU 的吞吐"比较，默认参数下 DvD 是变好还是变差？
2. 证明这个公式的 speedup 永远不超过 2，并说明什么条件下恰好等于 2。讲义说 "For an 8B + 400M encoder model, DvD roughly doubles per-node throughput"，代码默认算出多少？
3. 按"前向 FLOPs ≈ 2 × 参数量"，8B LLM 每个输出 token 约多少 GFLOPs？代入后 speedup 是多少？
4. 用 FLOPs 估算 decode 阶段的耗时有什么根本问题？（提示：回忆阶段 10 · 04 关于 prefill / decode 瓶颈的结论。）

**Q10.** 讲义与代码中关于 ViR 流量分布的数字：

- 讲义"概念"一节："For 60% of queries in production traffic, low or medium is sufficient."
- 讲义练习 4："ViR routes 60% of traffic to low-resolution encoding."
- 代码与 "Use It"：50% 低 / 30% 中 / 20% 高；代码最后打印 "note: 50% of real-world queries need only low-res encoding"。

1. 这三处说法一致吗？若按"60% 低或中、40% 高"并假设 40/20/40 的分布，`vir_sim` 的加速比是多少？
2. `ratio = baseline / avg` 只比较了视觉 token。若每个请求还有 200 个文本 prompt token 和 128 个输出 token，按"总 token 数"估算，默认分布下的加速比变为多少？
3. 改写 `vir_sim`，加入"误路由率"参数：被错误路由到低分辨率的高细节请求需要重新以高分辨率编码一次（额外付出 2048 个 token）。写出函数并说明它如何影响结论。

**Q11.** 阅读 `CorpusMix`：

```python
    def steps(self, total: int) -> dict:
        return {
            "text":       int(total * self.text_pct),
            "interleaved": int(total * self.interleaved_pct),
            "caption":    int(total * self.caption_pct),
            "video":      int(total * self.video_pct),
        }
```

1. `steps(999)` 和 `steps(7)` 的四个数之和分别是多少？为什么？
2. 用"最大余数法"改写 `steps`，保证总和恰好等于 `total`。
3. "按模态分配训练步数"隐含了"每一步只训练一种模态"的假设。真实的预训练通常怎么做？配比应当按样本数、token 数还是步数来计？
4. （讲义练习 2）你的目标任务以视频为主，请提出新的配比，并说明为什么仍需要大量文本与图文对数据。

**Q12.** `posthoc_vs_native_table()` 的输出中有这样两行：

```text
  ----------------------------------  ------------
  examples              LLaVA, Qwen-VL v1InternVL3, GPT-4o, Chameleon
```

1. 解释这两处排版问题的成因，并修复。
2. 表中 "corpus flexibility: post-hoc = instr only, native = interleaved"，请结合第 07 节代码 `RECIPES` 中 Idefics2-8B 的数据字段（`"OBELICS + Cauldron"`）评价这一说法。
3. 表中写 native 的 GPU-hours 为 "~300k"、MMLU / GSM8K 回退为 "0"。对照讲义的 "millions of GPU-hours" 以及 skill 文件的 hard reject（"Claiming post-hoc has zero alignment debt"），你认为这张表哪些地方需要加限定语？

---

## 四、面试高频题

**Q13.**（基础必考）什么是"后接式"VLM 和"原生多模态预训练"？什么是对齐债？InternVL3 押注的是什么？

**Q14.**（原理深挖）为什么原生多模态预训练的语料里还要保留约 40% 的纯文本？交错图文数据在其中起什么作用？如果目标是视频为主的模型，你会怎么调配比？

**Q15.**（工程实践）（讲义练习 4）ViR 会在哪些情况下把需要高分辨率的请求错误地路由到低分辨率？请给出三种失效模式和对应的缓解办法。

**Q16.**（场景设计）你的团队有约 15k GPU-hours、没有大规模交错语料、并且希望每 6–12 个月换一次底座 LLM。请给出训练策略决策，并说明理由；如果预算是 500k GPU-hours 呢？

**Q17.**（追问型）（讲义练习 5）DvD 在什么流量模式下反而会降低吞吐？它和 LLM 服务里的"prefill / decode 分离"有什么相似和不同？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义的三个症状是 catastrophic forgetting、answer drift、visual-text inconsistency（B、C、D）。A 不是对齐债：后接式通常直接使用已预训练好的视觉 encoder，第一阶段甚至冻结它，"encoder 不收敛"与对齐债无关。

### Q2 — 答案：C

讲义：40% text-only（FineWeb、Proof-Pile-2 等）、35% interleaved（OBELICS、MMC4 风格）、20% paired image-caption、5% video-text。代码 `CorpusMix(text_pct=40, interleaved_pct=35, caption_pct=20, video_pct=5)` 与之一致。B 文本过多、多模态过少；A 文本太少会损伤语言能力；D 是均分，没有依据。

### Q3 — 答案：D

`256 × 0.5 + 576 × 0.3 + 2048 × 0.2 = 128 + 172.8 + 409.6 = 710.4`，`2048 / 710.4 ≈ 2.88`。代码用 `:.0f` 打印为 710。A 是三档均分（各 1/3）的结果；B 是 40/20/40 分布的结果（见 Q10）；C 是全部走高分辨率时的情况。

### Q4 — 答案：B

`colocated = 300 + 8 × 128 = 1324`，`decoupled = max(300, 1024) = 1024`，`1324 / 1024 ≈ 1.29`。A 是讲义"roughly doubles"的说法，代码默认参数达不到；C 是 1324 / 300；D 是 1024 / 1324（倒数）。

### Q5 — 答案：B

讲义 "Trade-offs of native pretraining" 列了三条：Compute（"costs the same as training a text LLM — millions of GPU-hours"）、Data（交错语料稀缺）、Base-LLM reuse（"Post-hoc lets you swap Llama-3.1 for Llama-4 by retraining only the adapter"）。A 与讲义相反；C、D 无依据，讲义明确说原生预训练之后仍有指令微调。

### Q6 — 答案：D

讲义："ViR is a small classifier that predicts the minimum resolution needed to answer the question, before encoding." skill 文件的 hard reject："Recommending ViR for a workload where every query needs high-resolution encoding. ViR only helps when query distribution is mixed."——全部高分辨率时 `vir_sim` 的加速比就是 1.00。A 描述的是 token 剪枝类方法；B、C 都不对。

### Q7 — 答案：A

讲义："the vision encoder runs once per image but the LLM runs autoregressively for every output token. The two components have different bottlenecks... DvD splits them onto separate GPUs with streaming between." B 是 MoE / 专家并行；C 无关；D 错，encoder 不使用 LLM 的 KV cache。

### Q8 — 答案：C

normalize 后 `text_pct = 29 / 100 = 0.29`，而 `100 × 0.29` 在浮点数中等于 `28.999999999999996`，`int()` 向零截断得到 **28**（实际运行验证；四项之和为 99，不是 100）。A 是"期望值"；B、D 无依据。这说明按比例分配整数时不能直接 `int()`，见 Q11。

### Q9 — 参考答案

1. **不公平**。colocated 是 1 块 GPU 依次完成 encoder 与 LLM；decoupled 用了 2 块 GPU 流水并行。按单 GPU 吞吐比较：colocated 每块 GPU 每 1324 单位完成 1 个请求；decoupled 两块 GPU 每 1024 单位完成 1 个请求，即每块 GPU 每 2048 单位 1 个请求。默认参数下**每 GPU 吞吐只有 colocated 的 0.646 倍**（实际计算）。讲义说的是 "per-node throughput"，如果节点内 GPU 总数不变，就必须按每 GPU 吞吐比较。
2. 记 encoder 耗时为 a、LLM 耗时为 b，`speedup = (a + b) / max(a, b) = 1 + min(a, b) / max(a, b) ≤ 2`，当且仅当 `a = b`（两个阶段完全平衡）时等于 2。默认参数 `a = 300`、`b = 1024`，只有 1.29x；只有把 encoder 改成 1024 GFLOPs 才会得到 2.00x（实际验证）。即便如此，这个 2x 也是用两倍 GPU 换来的，每 GPU 吞吐仍是 1.0x。
3. 8B 参数前向约 `2 × 8×10⁹ = 16` GFLOPs/token（代码的 8 GFLOPs 相当于 4B 模型）。代入 `dvd_throughput(300, 16, 128)`：colocated 2348、decoupled 2048、**speedup ≈ 1.15x**，每 GPU 吞吐约 0.57 倍。
4. decode 阶段每步只处理 1 个 token，但要从显存读取全部权重和 KV cache，瓶颈是**显存带宽**而不是 FLOPs（阶段 10 · 04："Decode throughput scales with memory bandwidth"）。用 FLOPs 线性相加会严重低估 decode 耗时、高估 encoder 的占比。更合理的估算应分别用"FLOPs / 算力"估 encoder（以及 prefill）、用"权重与 KV 字节数 / 显存带宽"估每个 decode 步，并考虑 batching。讲义写 "vision = GPU memory bandwidth for conv + attention; LLM = KV cache"，把 ViT 编码也归为带宽瓶颈，与"一次处理大量 patch 的前向偏算力密集"的常见认识不同，也值得商榷。

### Q10 — 参考答案

1. 不一致：讲义"概念"说 60% 只需低或中分辨率（即 40% 需要高分辨率），练习 4 说 60% 走低分辨率，代码和 "Use It" 是 50% 低 + 30% 中 = 80% 低或中、20% 高，代码 note 又说 50%。按 40/20/40 分布：`avg = 102.4 + 115.2 + 819.2 = 1036.8`，加速比 `2048 / 1036.8 ≈ 1.98x`——仍在讲义说的"2–3x"区间的下沿，但比代码默认的 2.88x 低不少。
2. 加入文本：`(2048 + 200 + 128) / (710.4 + 200 + 128) ≈ 2.29x`。如果 prompt 更长或输出更长，加速比会进一步缩小；并且输出 token 走的是 decode，单个 token 的成本远高于 prefill 中的视觉 token，因此按 token 数线性估算仍然偏乐观。
3. 参考实现：

```python
def vir_sim(tiers, misroute=0.0, high_tokens=2048, text_tokens=0):
    """misroute: 高细节请求被错误路由到低档的比例，需以高分辨率重编码一次。"""
    low = tiers[0].tokens
    avg = 0.0
    for t in tiers:
        if t.tokens == high_tokens:
            avg += t.fraction * ((1 - misroute) * high_tokens
                                 + misroute * (low + high_tokens))
        else:
            avg += t.fraction * t.tokens
    avg += text_tokens
    baseline = high_tokens + text_tokens
    return {"avg_tokens": avg, "baseline": baseline, "ratio": baseline / avg}
```

   默认分布、误路由率 20% 时，高档部分变为 `0.2 × (0.8 × 2048 + 0.2 × 2304) = 419.8`，平均 720.6，加速比约 2.84x——token 层面影响不大。但真正的代价在质量：如果系统**没有**检测并重试机制，误路由的请求会直接给出错误答案（比如读不出小字），这无法用 token 数衡量。因此评估 ViR 时要同时报告"吞吐提升"和"在高细节请求上的准确率损失"。

### Q11 — 参考答案

1. `steps(999)` = `399 + 349 + 199 + 49 = 996`；`steps(7)` = `2 + 2 + 1 + 0 = 5`（视频 0 步）。原因：`int()` 对每一项向下截断，各项丢掉的小数部分累积起来就会少几步；比例很小的模态在总步数很小时会被截断成 0。
2. 最大余数法：

```python
    def steps(self, total: int) -> dict:
        names = ["text", "interleaved", "caption", "video"]
        pcts = [self.text_pct, self.interleaved_pct, self.caption_pct, self.video_pct]
        raw = [total * p for p in pcts]
        base = [int(x) for x in raw]
        remainder = total - sum(base)
        order = sorted(range(4), key=lambda i: raw[i] - base[i], reverse=True)
        for i in order[:remainder]:
            base[i] += 1
        return dict(zip(names, base))
```

   `steps(999)`：精确值为 `399.6 / 349.65 / 199.8 / 49.95`，先取整得 `399 / 349 / 199 / 49`（差 3），再把 3 步按小数部分从大到小（0.95、0.8、0.65）补给 video、caption、interleaved，结果 `{text 399, interleaved 350, caption 200, video 50}`，总和 999；`steps(7)` → `3 / 3 / 1 / 0`，总和 7；`CorpusMix(29, 36, 30, 5)` 的 `steps(100)` → text 29，总和 100（均已运行验证）。
3. 真实预训练通常是**每个 batch 内混合多种模态**（按比例从各数据源采样），而不是让某些步只训练文本。配比更常按 **token 数**（或样本数）计：一个交错文档可能有几千个 token，一条图文对只有几百个，按样本数 40% 和按 token 数 40% 差别很大。代码按"步数"分配，只是一种记账方式，需要说明口径。
4. 视频为主的示例：文本 30% / 交错 25% / 图文对 15% / 视频 30%（skill 文件也要求"exclusively video"任务不要沿用 40/35/20/5）。仍需大量文本与图文对的理由：
   - 推理与语言能力来自文本数据（第 07 节："The VLM's multimodal reasoning ceiling is the LLM's text reasoning ceiling"），文本过少会导致对齐债中的遗忘；
   - 图文对是"看懂单帧"的感知基础，视频理解建立在逐帧感知之上（与第 08 节"单图先行"的逻辑一致）；
   - 视频数据贵且冗余（相邻帧高度相似），单位 token 的信息量低于图文对。

### Q12 — 参考答案

1. 成因：
   - 第一列宽 22，`"-" * 22` 正好填满，没有留空格，与第二列的 12 个 `-` 连成一条 34 个字符的长线；
   - 第二列宽 14，`"LLaVA, Qwen-VL v1"` 有 17 个字符，超出宽度后 f-string 不会截断也不会补空格，直接与第三列粘连。
   - 修复：在列之间加固定分隔（如 `f"  {r[0]:<22}  {r[1]:<20}  {r[2]}"`），并把列宽设为该列最长字符串的长度：`w = max(len(r[1]) for r in rows)`。
2. 这一说法不准确。后接式同样可以使用交错图文数据：第 07 节 `RECIPES` 中 Idefics2-8B 的数据就是 `"OBELICS + Cauldron"`，MM1 的数据是 `"interleaved + caption"`，它们都是在预训练好的 LLM 上后接视觉。区别不在"能不能用交错数据"，而在"LLM 是否从一开始就和多模态数据一起训练"。
3. 需要加限定语的地方：
   - **GPU-hours**：表中 native ~300k，讲义正文说原生预训练 "millions of GPU-hours"，两处差一个数量级；这些数字都只是量级示意，应标注规模（例如 8B 还是 78B）。
   - **"0" 回退**：原生模型的文本能力是与什么基线比较的？与同等算力的纯文本 LLM 相比仍可能有差距。更稳妥的说法是"显著小于后接式"。skill 文件一方面要求不能声称后接式对齐债为 0，另一方面自己也写 native "Zero"，同样过于绝对。
   - **示例**：把 GPT-4o 列为原生预训练的例子，其训练细节并未公开，属于推测；Chameleon（下一节）是早期融合、从头训练的例子，更贴切。

### Q13 — 参考回答要点

- **后接式**：先有一个只在文本上预训练好的 LLM，再接上视觉 encoder 和 projector，按"对齐 → 指令微调 → 任务微调"分阶段训练。优点是便宜、可复用底座；缺点是 LLM 的全部预训练预算都花在纯文本上，视觉是"事后学"的。
- **对齐债**：后接带来的、可测量的代价——灾难性遗忘（GSM8K 掉 5–10 分、HellaSwag 下降）、答案漂移、视觉-文本不一致。讲义引用 MM1.5 第 4 节对其做了量化。
- **原生多模态预训练**：文本与多模态数据从第一个梯度步起就在同一个 loss 中联合训练，基础模型单阶段完成，然后指令微调。
- **InternVL3 的押注**："the alignment debt is worse than the reuse loss"——宁可放弃复用和更多算力，也要消除对齐债。讲义称 InternVL3-8B 每单位视觉收益损失的文本分数比 Qwen2.5-VL-7B 更少。
- **常见误区 / 加分点**：讲义说 InternVL3 "trains from scratch"，并把 ViR、DvD 放在 InternVL3 名下。据公开论文，InternVL3 仍是 ViT-MLP-LLM 结构，语言部分以预训练 LLM（如 Qwen2.5 系列）初始化，"原生"指的是用一个联合的多模态预训练阶段取代"先纯文本、再多阶段适配"的流程；ViR 和 DvD 出现在 InternVL3.5 论文（arXiv:2508.18265）中；V2PE 在原文中的含义是给视觉 token 使用更小、可变的位置增量，与讲义"可学习的 band 维度分配"的描述不同。面试时如果被追问细节，应以原论文为准。

### Q14 — 参考回答要点

- **为什么要 40% 文本**：语言理解与推理能力主要来自文本；多模态数据中的文字短而模式化（图片描述、alt-text），无法替代高质量文本。文本占比过低，模型会出现与后接式相同的语言能力退化。代码打印："40% text floor keeps base LLM skills"。
- **交错图文的作用**：文档中图片与文字按自然阅读顺序穿插，模型可以学到"多张图之间的指代与比较""图文上下文推理"，这是图文对（一图一句）学不到的；代码打印："interleaved is the key unlock that lets the model learn multi-image reasoning during pretraining"。
- **图文对的作用**：提供大量"图像 ↔ 描述"的直接对齐信号，是感知的基础。
- **视频为主的配比**：见 Q11 第 4 问，示例 30/25/15/30；同时提高视频数据的质量（密集描述、时间标注），并在指令微调阶段进一步加重视频。
- 加分点：配比应按 token 计量并给出口径；对配比做小规模消融（第 07 节的方法）。

### Q15 — 参考回答要点

三种典型失效模式：

1. **小而关键的细节**：整体是普通照片，但问题问的是角落里的小字、车牌、价签、仪表读数。路由器看到"简单图片"就分到低档。缓解：路由器同时读取**问题文本**（问题中出现"写着什么""多少钱""第几行"时提高档位）；对 OCR 类意图强制高档。
2. **长宽比极端或高密度内容**：长截图、表格、图表，按图片"复杂度"评分可能不高，但在低分辨率下文字无法辨认。缓解：把长宽比、边缘密度、文字检测结果作为路由特征。
3. **分布外输入与多轮追问**：第一轮问"这是什么"（低档足够），第二轮追问细节，但仍沿用低档的视觉 token。缓解：多轮对话中允许按需"升档"重编码；对置信度低的回答自动以高档重试。

- 评估：分档统计准确率，重点看"被路由到低档的请求中，本应高档的比例"以及这部分请求的准确率；ViR 的收益要和误路由的质量损失一起报告（Q10）。

### Q16 — 参考回答要点

- **15k GPU-hours、无交错语料、频繁换底座**：选择**后接式**。理由：
  - skill 文件的拒绝规则："If the user has less than ~20k GPU-hours, refuse native pretraining — it is infeasible"；
  - 没有大规模交错语料，原生预训练的数据前提不成立；
  - "If the user wants to swap the LLM backbone every 6-12 months, refuse native — that reuse path is closed."
  - 缓解对齐债：在指令微调中混入一定比例的纯文本数据；部分阶段冻结 LLM 或使用 LoRA；上线前把 MMLU、GSM8K 等纯文本基准纳入回归测试。
- **500k GPU-hours**：若同时拥有足够的交错语料、且不打算频繁换底座，可以考虑原生预训练（skill："checking that the user has 100k+ GPU-hours and a sizable interleaved corpus"）；也可以选**混合**方案——用原生方式训练一个多模态基础模型，再用后接方式做领域专精（skill 的 "hybrid" 选项）。
- 加分点：把决策写成表格（算力、数据、复用需求、目标任务四个维度），并给出每个维度的阈值依据。

### Q17 — 参考回答要点

- **DvD 适得其反的流量模式**：
  - 两个阶段严重不平衡：输出很长（LLM 主导，encoder GPU 大部分时间空闲），或者大量请求只有图片、输出很短（encoder 主导，LLM GPU 空闲）——speedup 上限 `1 + min/max`（Q9）接近 1，却多占一块 GPU；
  - 纯文本请求占比高：encoder GPU 完全闲置；
  - 高分辨率、多图请求：视觉特征需要在 GPU 之间传输，跨 GPU / 跨节点的传输带宽和延迟成为新瓶颈；
  - 低并发：流水线填不满，反而增加了一次跨设备传输的首 token 延迟（TTFT）。
- **与 prefill / decode 分离的相似之处**：都把"一次性、计算密集"的阶段（视觉编码 / prefill）与"逐 token、带宽密集"的 decode 拆开，各自按瓶颈配置硬件与 batch，并通过网络传递中间结果（视觉特征 / KV cache）。
- **不同之处**：DvD 拆的是两个不同的模型（ViT 与 LLM），传递的是视觉 embedding，数据量相对较小；prefill / decode 分离拆的是同一个 LLM 的两个阶段，需要传递的 KV cache 随上下文长度增长，传输成本更高。
- 加分点：给出按比例配置 encoder 与 LLM GPU 数量（如 1:3）的思路，并用 TTFT、TPOT、goodput 指标验证收益。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：典型的后接式训练流程，本节的对照对象。
- [阶段 12 · 07 开放 Weight VLM 的构建方案：真正重要的因素](../../07-open-weight-vlm-recipes/docs/zh.md)：讲义的先修要求，后接式配方各轴的消融结论。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：M-RoPE，与 V2PE 对比。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：预训练目标、prefill / decode 的瓶颈差异（Q9 第 4 问）。
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：原生预训练之后的指令微调阶段。

### 本节被哪些后续内容用到
- [阶段 12 · 11 Chameleon：仅用 Token 的早期融合 Multimodal Models](../../11-chameleon-early-fusion-tokens/docs/zh.md)：更彻底的"原生"——连图像都离散成 token、从头联合训练。
- [阶段 12 · 13 Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像](../../13-transfusion-autoregressive-diffusion/docs/zh.md)：InternVL-U 所追随的统一理解与生成路线。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)：ViR 本质上是一种按请求路由以降低成本的手段。
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../../17-infrastructure-and-production/17-disaggregated-prefill-decode/docs/zh.md)：与 DvD 同一思路的分离式部署。
- [阶段 19 · 62 视觉与语言联合 Pretraining](../../../19-capstone-projects/62-vision-language-pretraining/docs/zh.md)：在综合项目中动手做联合预训练。

### 延伸关键词
`native multimodal pretraining` · `alignment debt` · `catastrophic forgetting` · `interleaved corpus` · `OBELICS` · `MMC4` · `V2PE` · `Visual Resolution Router` · `Decoupled Vision-Language Deployment` · `largest remainder method` · `InternVL3.5` · `InternVL-U` · `MM1.5`
