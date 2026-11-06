# 测验 · 开放 Weight VLM 的构建方案：真正重要的因素（Open-Weight VLM Recipes: What Actually Matters）

> **阶段 12 · 多模态 AI · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：本节中文讲义是机器翻译，质量较差（例如"轴 1"一段把语言模型列表译成了一串重复的 "720B"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 五轴设计空间 | Idefics2 把 VLM 设计归纳为五个轴：image encoder、connector（连接器）、LLM、训练数据、resolution schedule（分辨率计划） |
| 2 | encoder 比 connector 重要 | 讲义："swapping from CLIP ViT-L/14 to SigLIP SO400m/14 added 3+ points MMMU"，而 MLP → Perceiver Resampler "added less than 1 point" |
| 3 | 视觉中心基准上的 encoder 排名 | Cambrian-1 比较 20+ 个 encoder：DINOv2 与 SigLIP 居前，CLIP 居中，CLIP ViT-L 到 DINOv2 ViT-g/14 在 CV-Bench 上差约 5–7 分 |
| 4 | connector 架构"打平" | 固定视觉 token 数时，2 层 MLP 与 32-query Q-Former 相差不到 1 分；Q-Former 是**成本杠杆**（把 token 封顶在 32–64），不是质量杠杆 |
| 5 | 视觉 token 数 | 64 个对 OCR 太少；576–1024 是多数开放 VLM 的甜点；2048+ 只对文档、图表有帮助 |
| 6 | LLM 规模决定上限 | 7B → 13B 稳定 +2–4 MMMU；VLM 的多模态推理上限就是 LLM 的文本推理上限，encoder 只能"喂"它 |
| 7 | 详细人类字幕胜过蒸馏 | Molmo + PixMo：712K 张由人类口述（1–3 分钟，语音转文字）得到的 dense caption，**完全不用** GPT-4V 蒸馏；Molmo-72B 在 11/11 个基准上胜过 Llama-3.2-90B-Vision |
| 8 | 分辨率与其计划 | Idefics2：384 → 448 +1–2 分；448 → 980（图像切分 / AnyRes）OCR 再 +3–5；分辨率爬坡（224 起步）比固定分辨率训得更快、终点更高 |
| 9 | Prismatic 方差分解 | 讲义给出的粗略分解：每图视觉 token 数 ~60%、encoder ~20%、connector ~5%、其余（数据、调度器、LR）~15% |
| 10 | 2026 默认配方 | SigLIP 2 SO400m/14（NaFlex，原生分辨率）± DINOv2、2 层 MLP、7B/70B LLM、PixMo + ShareGPT4V + Cauldron、动态分辨率 256–1280、三阶段训练 |

### 核心技能（能动手做到）

- [ ] 不看讲义写出五个设计轴，并对每个轴说出至少两个典型选项
- [ ] 读一张 MM1 / Idefics2 / Cambrian-1 风格的消融表，判断"换哪个旋钮会动哪个 benchmark"（MMMU、CV-Bench、DocVQA）
- [ ] 给定算力预算和任务组合（OCR、UI agent、推理），按轴写出完整配方并为每个选择给出依据
- [ ] 读懂本节 `pick_recipe` 的加权打分，能手算任意一行的 score，并指出不同 benchmark 量纲不一致带来的偏差
- [ ] 指出代码 `axis_impact()` 与讲义 Prismatic 分解不一致的地方，并把百分比真正归一化
- [ ] 设计一个最少运行次数的消融实验，把"数据质量"与"encoder 质量"两个因素分离开

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项**不是** Idefics2 归纳的 VLM 五轴设计空间之一？

- A. image encoder（如 CLIP ViT-L/14、SigLIP SO400m/14）
- B. resolution schedule（固定 336/448、AnyRes、原生动态，是否爬坡）
- C. training data（caption 对、交错图文、指令数据）
- D. optimizer 与学习率（AdamW / Lion、峰值 LR）

**Q2.** 按讲义转述的 MM1 与 Idefics2 结论，在**相同视觉 token 数**下，把 connector 从 MLP 换成 Perceiver Resampler，MMMU 的变化大约是：

- A. 不到 1 分
- B. 3 分以上
- C. 5–7 分
- D. 10 分以上

**Q3.** 关于 Q-Former 与 MLP connector，下列说法正确的是：

- A. Q-Former 的 cross-attention 能提炼更多信息，因此在任何分辨率下质量都明显优于 MLP
- B. MLP 会把 patch token 压缩成固定 32 个，Q-Former 则输出全部 patch token
- C. Q-Former 不论输入分辨率多高都把视觉 token 封顶在 32–64 个，高分辨率输入时能节省 LLM 上下文；低分辨率时两者差别只是噪声
- D. Q-Former 只能接 CLIP，不能接 SigLIP

**Q4.** 讲义转述的 Prismatic VLMs 受控比较中，解释 benchmark 方差**最多**的因素是：

- A. image encoder 的选择（~20%）
- B. 每张图的视觉 token 数（~60%）
- C. connector 架构（~5%）
- D. 数据组合、调度器、学习率（~15%）

**Q5.** `axis_impact()` 中每个轴的横条由 `bar = "#" * (pct // 2)` 生成。"LLM size" 一行（`pct = 15`）会打印几个 `#`？

- A. 15
- B. 8
- C. 30
- D. 7

**Q6.** 关于 Molmo 的训练数据 PixMo，下列描述正确的是：

- A. 约 712K 张图，由人类标注员用 1–3 分钟口述、再转写成密集描述；训练数据中没有任何 GPT-4V 蒸馏
- B. 约 1.2M 条由 GPT-4V 生成的详细描述，再经人工抽检
- C. 从 LAION 中用 CLIP 分数过滤出的高质量 alt-text
- D. 人类描述与 GPT-4V 描述各占一半的混合数据集

**Q7.** 关于每张图的视觉 token 数，与讲义一致的是：

- A. 越多越好，没有收益递减
- B. 64 个已足够应对 OCR 任务
- C. 576–1024 是多数开放 VLM 的甜点；64 个对 OCR 太少；2048+ 只对文档和图表有帮助
- D. token 数只影响推理速度，不影响 benchmark 分数

**Q8.** 关于 LLM 规模这一轴，下列说法与讲义一致的是：

- A. 只要 connector 设计得足够好，7B VLM 可以替代 70B VLM
- B. 7B → 13B 在各篇 VLM 论文中都稳定带来 +2–4 MMMU；VLM 的多模态推理上限由 LLM 的文本推理能力决定
- C. LLM 规模对 MMMU 几乎没有影响，主要影响 DocVQA
- D. LLM 越大越需要 Q-Former，否则无法训练

---

## 三、动手 / 代码题

**Q9.** 阅读 `axis_impact()`：

```python
    axes = [
        ("visual-token count", 60, "64 -> 576 -> 1024 tokens; diminishing past 1024"),
        ("image encoder",      20, "CLIP vs SigLIP vs DINOv2; concatenation helps"),
        ("connector arch",      5, "MLP ~= Q-Former ~= Perceiver at same token count"),
        ("data mix",           10, "detailed human caps > distilled GPT-4V data"),
        ("LLM size",           15, "7B -> 70B plateau around MMMU 55"),
        ("resolution sched",    5, "ramp 224 -> 448 > flat 448; native wins OCR"),
    ]
    total_weight = sum(a[1] for a in axes)
    ...
    print(f"note: weights rebased from ~{total_weight}% to ~100% after rounding.")
```

1. 打印出的 `total_weight` 是多少？代码真的做了 "rebase" 吗？
2. 把它和讲义的 Prismatic 分解（60 / 20 / 5 / 其余 15）对比，指出两处不一致。为什么"LLM size"出现在这张表里在逻辑上有问题？
3. 改写这段代码，让打印的百分比真正归一化到 100%（保留 1 位小数），并写出归一化后的 6 个数字。

**Q10.** `pick_recipe` 的打分函数是：

```python
    def score(r: Recipe) -> float:
        return r.mmmu * weights["mmmu"] + r.cv_bench * weights["cv"] + r.docvqa * weights["doc"]
```

实际运行时，`budget=10` 下 ocr、agent 两个任务（以及额外测试的 reasoning、默认权重）的第一名**全部**是 Molmo-7B-D。

1. 已知 Molmo-7B-D 为 `(MMMU 45.3, CV-B 65.0, DocVQA 92.4)`，Cambrian-1-8B 为 `(42.7, 67.8, 77.8)`。在 agent 权重下（`mmmu=1.0, doc=0.8`），`cv` 权重至少要大于多少，Cambrian-1-8B 才会排第一？
2. 本表中 DocVQA 的取值范围是 55.0–93.5，MMMU 是 35.3–54.1。说明直接加权求和会产生什么偏差，并给出一种改进方法。
3. 这个 "picker" 实际上是在"挑现成模型"还是"按轴组合配方"？它和讲义 "Use It" 一节的描述有什么差距？

**Q11.** 手算并回答：

1. 在 `reasoning` 权重（`mmmu=1.5, cv=0.5, doc=0.8`）下，Idefics2-8B（43.0, 60.0, 74.0）的 score 是多少？
2. `pick_recipe(5, "reasoning")` 会输出什么？
3. `outputs/skill-vlm-recipe-picker.md` 的拒绝规则写着："If the user wants a 1-3B VLM for reasoning-heavy tasks, refuse and recommend a larger LLM"。请修改 `pick_recipe`，让它在这种情况下打印拒绝理由；同时让未知的 `task` 名（例如 `"OCR"` 大写）报错而不是悄悄使用等权重。

**Q12.**（讲义练习 5）为一个 7B VLM 设计消融实验，把"数据质量"与"encoder 质量"两个因素分离开。最少需要几次训练？给出每次运行的四个轴设置（encoder、connector、数据、分辨率），并说明如何从结果中读出两个因素各自的效应以及交互效应。

---

## 四、面试高频题

**Q13.**（基础必考）一个 VLM 有哪几个关键设计轴？如果你的开放 VLM 在 benchmark 上表现不佳，你会按什么顺序排查和消融？

**Q14.**（原理深挖）为什么多篇论文都发现"在相同视觉 token 数下，connector 架构几乎不影响结果"？那在什么场景下你仍然会选 Q-Former / Perceiver Resampler？

**Q15.**（原理深挖）为什么 Molmo 的"详细人类字幕"能胜过 GPT-4V 蒸馏数据？如果预算买不起人工标注，你会怎么做？

**Q16.**（场景设计）（讲义练习 3）你要在 2B LLM 上做一个手机 UI agent（看截图、点按钮）。请给出 encoder、connector、分辨率、数据组合与训练阶段的选择，并说明依据。

**Q17.**（追问型）讲义说"视觉 token 数解释约 60% 的方差"。你会如何评价这种方差分解？读别人的消融表时有哪些常见陷阱？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义的五个轴是：image encoder、connector、language model、training data、resolution schedule。优化器与学习率当然影响训练，但它们属于讲义里"其余 ~15%"中的训练超参数，不是 Idefics2 所说的设计轴。A、B、C 分别是第 1、5、4 轴。

### Q2 — 答案：A

讲义："Swapping the connector from MLP to Perceiver Resampler added less than 1 point. Idefics2 replicated: SigLIP > CLIP, Q-Former ≈ MLP ≈ Perceiver at the same token count." B 是 encoder 从 CLIP 换成 SigLIP 的收益（3+ 分）；C 是 Cambrian-1 中 CLIP ViT-L 与 DINOv2 ViT-g/14 在 CV-Bench 上的差距；D 没有出处。

### Q3 — 答案：C

讲义："Q-Former vs MLP is a cost question, not a quality question: Q-Former caps tokens at 32-64 regardless of image resolution; MLP emits all patch tokens." A 把成本杠杆说成了质量杠杆，正是 skill 文件里的 "Hard rejects" 之一；B 把两者说反了；D 没有依据，connector 只关心 encoder 的输出维度。

### Q4 — 答案：B

讲义："Per-image visual-token count explains ~60% of variance." A、C、D 是其余三项。注意讲义自己也说 "This is a rough decomposition"，见 Q17 的讨论。

### Q5 — 答案：D

`//` 是向下取整除法，`15 // 2 = 7`，所以打印 7 个 `#`。实际运行输出为 `LLM size                  15% #######`。A 忘了除以 2；B 是四舍五入（或向上取整）的结果；C 是乘以 2。同理 5% 的行只有 2 个 `#`，60% 的行有 30 个。

### Q6 — 答案：A

讲义："Allen AI had human annotators describe images in 1-3 minute dense speech-to-text passes, yielding 712K densely-captioned images. No GPT-4V distillation anywhere in the training data." D 描述的是 ShareGPT4V / Cauldron 的"人类 + GPT-4V 混合"路线；B、C 都与 Molmo 的核心主张相反。

### Q7 — 答案：C

讲义："64 tokens per image is too few for OCR. 576-1024 tokens is the sweet spot for most open VLMs. 2048+ helps only for documents and charts." A 忽略了收益递减；B 与原文相反；D 错，token 数是 Prismatic 分解里影响最大的因素。

### Q8 — 答案：B

讲义："Doubling the LLM from 7B to 13B reliably adds 2-4 points on MMMU across every VLM paper... A 7B VLM cannot substitute for a 70B VLM through clever connector design." A 与原文相反；C 错在 MMMU 恰恰是对 LLM 规模最敏感的推理型基准；D 无依据。

### Q9 — 参考答案

1. `total_weight = 60 + 20 + 5 + 10 + 15 + 5 = 115`，运行输出 `note: weights rebased from ~115% to ~100% after rounding.`。但代码**没有做任何 rebase**：打印的仍是原始的 60%、20%……，6 行加起来是 115%。这句 note 只是"声明"而没有实现。
2. 不一致之处：
   - 讲义的"其余 ~15%"包括 "data mix, scheduler, LR"；代码把它拆成了 data mix 10% + LLM size 15% + resolution sched 5% = 30%，比讲义多出 15 个百分点。
   - 讲义说 Prismatic 的实验是 "Same 13B LLM, same instruction data, same evaluation — only one axis varies at a time"。LLM 被固定时，LLM 规模不可能解释这组实验的方差，所以"LLM size 15%"不可能出自这次受控比较。它是作者把讲义"轴 3"的结论混进了这张表。
3. 改写（已运行验证）：

```python
    total_weight = sum(p for _, p, _ in axes)
    for name, pct, note in axes:
        share = 100 * pct / total_weight
        bar = "#" * round(share / 2)
        print(f"{name:<22}{share:>6.1f}% {bar}")
        print(f"{'':<22}       {note}")
    print(f"note: raw weights summed to {total_weight}%, rebased to 100%.")
```

归一化后：visual-token count 52.2%、image encoder 17.4%、connector arch 4.3%、data mix 8.7%、LLM size 13.0%、resolution sched 4.3%（合计 99.9%，舍入误差）。更好的做法是直接改成讲义的四项分解：60 / 20 / 5 / 15，并把 LLM size 移出这张表、单独说明。

### Q10 — 参考答案

1. Cambrian − Molmo 的三项差值是 `(−2.6, +2.8, −14.6)`。Cambrian 胜出需要 `−2.6 × 1.0 + 2.8 × w_cv − 14.6 × 0.8 > 0`，即 `w_cv > (2.6 + 11.68) / 2.8 ≈ 5.1`。代码里 agent 的 `cv` 权重只有 1.2，远远不够。换句话说，只要 DocVQA 权重不为 0，Molmo-7B-D 在 ≤10B 档几乎不可撼动。
2. 偏差：各 benchmark 的量纲和离散程度不同。本表 9 个模型中 DocVQA 的标准差约 11.8，MMMU 约 5.4，CV-Bench 约 5.2。直接相加时 DocVQA 的差异会主导排名，"权重 1.0"并不代表"同等重要"。改进：先对每列做 z-score（减均值、除标准差）或 min-max 归一化，再加权；或者改用"相对某个基线的提升"作为分数。（实测：z-score 之后，在 ≤10B 档 Molmo-7B-D 仍是第一，因为它在三项中有两项最高——这时结论才可信。）
3. 它是在**挑现成模型**：候选集就是 `RECIPES` 里的 9 个已发表模型，输出的 encoder/data/res 只是被选中模型的字段。讲义 "Use It" 说可以查询"如果我在 7B Llama 上把 CLIP 换成 SigLIP，MMMU 的预期变化是多少"以及"应该先消融哪个轴"，但 `pick_recipe` 不会组合各轴，也不输出预期 delta 或 "ablate first" 建议；encoder 对比表和数据对比表只是打印，没有被 picker 使用。另外 `budget_b` 只和 `llm_b` 比较，不计 encoder 参数（例如 InternViT-6B 本身就有 6B 参数）。

### Q11 — 参考答案

1. `1.5 × 43.0 + 0.5 × 60.0 + 0.8 × 74.0 = 64.5 + 30.0 + 59.2 = 153.7`（与额外运行 `pick_recipe(10, "reasoning")` 得到的第三名分数一致）。
2. `budget=5` 时只剩 `MM1-3B`（3B）一个候选，输出：

```text
PICKER: budget 5B params, task profile: reasoning
------------------------------------------------------------
  MM1-3B                 LLM 3B  score=137.0
    encoder=CLIP L/14
    data   =interleaved + caption
    res    =672
```

   `1.5 × 38.6 + 0.5 × 59.0 + 0.8 × 62.0 = 57.9 + 29.5 + 49.6 = 137.0`。

3. 参考改法：

```python
TASK_WEIGHTS = {
    "general":   {"mmmu": 1.0, "cv": 1.0, "doc": 1.0},
    "ocr":       {"mmmu": 0.4, "cv": 0.3, "doc": 1.2},
    "agent":     {"mmmu": 1.0, "cv": 1.2, "doc": 0.8},
    "reasoning": {"mmmu": 1.5, "cv": 0.5, "doc": 0.8},
}

def pick_recipe(budget_b: int, task: str) -> None:
    if task not in TASK_WEIGHTS:
        raise ValueError(f"unknown task {task!r}; choose from {sorted(TASK_WEIGHTS)}")
    if task == "reasoning" and budget_b <= 3:
        print("REFUSE: reasoning ceiling is set by the LLM; use >= 7B (ideally 70B).")
        return
    weights = TASK_WEIGHTS[task]
    ...
```

   原代码用 `if/elif` 链，没有 `else` 分支，`"OCR"` 这样的拼写会悄悄退化为等权重，结果看起来正常却是错的。用字典查表 + 显式报错更安全。

### Q12 — 参考答案

最少 **4 次**训练：两个因素各取两个水平，做 2×2 全因子实验，其余轴全部固定。

| 运行 | encoder | connector | 数据 | 分辨率 |
|------|---------|-----------|------|--------|
| R1 | CLIP ViT-L/14 @336 | 2 层 MLP | 蒸馏数据（LLaVA-Inst + ShareGPT4V） | 固定 384，同样 token 数 |
| R2 | SigLIP SO400m/14 @384 | 2 层 MLP | 蒸馏数据 | 同上 |
| R3 | CLIP ViT-L/14 @336 | 2 层 MLP | 人类 dense caption（PixMo） | 同上 |
| R4 | SigLIP SO400m/14 @384 | 2 层 MLP | 人类 dense caption | 同上 |

- encoder 主效应 = `[(R2 − R1) + (R4 − R3)] / 2`；数据主效应 = `[(R3 − R1) + (R4 − R2)] / 2`；交互效应 = `(R4 − R3) − (R2 − R1)`（好数据是否放大或缩小了 encoder 的收益）。
- 关键控制：两种 encoder 输出的**视觉 token 数要对齐**（例如统一池化到 576），否则 token 数（方差最大的因素）会混进 encoder 效应；两种数据的**训练 token 数**要相同（Molmo 的论点就是"at the same token count"）；LLM、学习率、步数、评测集一致。
- 加分点：每个格子至少跑 2 个随机种子以估计噪声；benchmark 至少要同时覆盖 MMMU（推理）、CV-Bench（感知）和 DocVQA（OCR），因为两个因素对不同基准的影响方向可能不同。

### Q13 — 参考回答要点

- **五个轴**：image encoder（CLIP / SigLIP / DINOv2 / InternViT）、connector（MLP / Q-Former / Perceiver / C-Abstractor）、LLM（7B / 70B …）、训练数据（caption 对、交错图文、指令数据）、resolution schedule（固定、AnyRes、原生动态，是否爬坡）。
- **排查顺序**（依据讲义的证据强度）：
  1. 先看**视觉 token 数和分辨率**是否满足任务（OCR / 文档任务 64 个 token 远远不够）；
  2. 再看 **encoder**（CLIP → SigLIP 2，需要定位 / 分割时拼接 DINOv2）；
  3. 再看**数据**（是否有足够的 dense caption、OCR / 图表数据）；
  4. 若是推理类基准（MMMU）上不去，看 **LLM 规模**；
  5. 最后才动 connector。
- 加分点：说明"每次只动一个轴"的消融原则；以及每个轴影响的 benchmark 不同（encoder 主要影响 CV-Bench，分辨率主要影响 DocVQA，LLM 主要影响 MMMU）。
- 常见误区：一上来就换 connector 架构，花大量算力换来不到 1 分的变化。

### Q14 — 参考回答要点

- **为什么打平**：connector 只负责把 encoder 的特征映射到 LLM 的 embedding 空间。encoder 已经提取好了信息，LLM 负责推理；只要 connector 容量足够、输出 token 数相同，信息瓶颈就不在 connector 上。2 层 MLP 已经是足够强的映射，Q-Former 的 cross-attention 并不能"创造"encoder 没有的信息。
- **真正的变量是 token 数**：MLP 输出全部 patch token，Q-Former 输出固定数量的 query；比较时如果不对齐 token 数，看到的"connector 差异"其实是 token 数差异（讲义 skill 的 hard reject："Claiming connector architecture explains variance that actually comes from token count"）。
- **仍会用 Q-Former / Perceiver 的场景**：高分辨率、多图、视频输入下 LLM 上下文吃紧（例如每帧只能给 32–64 个 token）；端侧部署需要严格控制 prefill 成本；需要冻结 LLM、只训练轻量桥接模块（BLIP-2 路线）。
- 加分点：提到后续几节的主流模型用"MLP + 降 token 手段"代替 Q-Former：LLaVA-OneVision 在 patch 网格上做 bilinear 池化（第 08 节），Qwen2-VL 把相邻 2×2 patch 合并后再接 2 层 MLP（第 09 节）。

### Q15 — 参考回答要点

- **信息密度**：讲义："Detailed human captions contain 5-10x more information per image than short web captions"；口述 1–3 分钟能覆盖物体、位置、文字、关系等细节。
- **事实一致性**：人类描述基于真实观察，"stay factually grounded where GPT-4V distillation hallucinates"；蒸馏数据会把教师模型的幻觉一起学进来，而且学生的上限被教师限制。
- **结果**：讲义 Molmo-72B 在 11/11 个基准上胜过 Llama-3.2-90B-Vision，"The delta is not architecture — it is caption quality"；本节代码的数据表中，PixMo 只用人类字幕得到 45.3 MMMU，比 "+ShareGPT4V"（42.0）高 3.3、比 "+Cauldron"（43.0）高 2.3。
- **没有人工预算时**：用开放数据集（PixMo、ShareGPT4V 中的人工部分、Cauldron）；蒸馏时用多个教师交叉验证、过滤幻觉；把少量人工 dense caption 用于最后阶段；并在报告中明确标注预期的 2–3 MMMU 上限损失（skill 文件的 refusal rule）。
- 常见误区：只追求 caption **数量**。讲义的排序是 "caption density > caption quantity > distillation convenience"。

### Q16 — 参考回答要点

- **LLM**：2B 已定，推理上限低，所以任务设计要偏感知和定位（点哪里），复杂规划交给外部逻辑或更大模型。
- **encoder**：SigLIP 2 SO400m/14，NaFlex 原生分辨率（UI 截图长宽比极端，不能压成正方形）；UI 定位需要精细空间信息，可考虑拼接 DINOv2 特征，但 2B 模型要注意 encoder 参数和延迟。
- **connector**：2 层 MLP + 2×2 token 合并控制数量；只有当截图 token 数超出上下文预算时才考虑 Q-Former。
- **分辨率**：UI 文字小、图标密集，属于 OCR 型任务——讲义 448 → 980 切图在 OCR 上 +3–5；目标长边上限 1280 左右，阶段 1 固定 384 对齐、阶段 2 动态分辨率。
- **数据**：PixMo（含 pointing 数据）+ Cauldron 的 OCR / 截图部分 + 任务专用的 UI 截图–动作对（元素描述、坐标定位）。
- **训练阶段**：阶段 1 只训 projector；阶段 2 全参微调；阶段 3 UI agent 专项微调。
- 加分点：每个选择都引用对应的消融（Idefics2 分辨率消融、MM1 encoder 消融、Molmo 数据结论）；提出延迟预算并据此限制视觉 token 数。

### Q17 — 参考回答要点

- **如何评价**：讲义自己承认 "This is a rough decomposition"。方差分解只在**被测范围内**成立：如果实验里 token 数从 64 变到 1024、而 encoder 只在三个相近的选项间切换，token 数自然显得更重要。换一组取值范围，比例就会变。它也依赖所选 benchmark：OCR 型基准会放大分辨率和 token 数的作用。
- **因素不独立**：encoder 决定 patch 大小和分辨率，从而决定 token 数；"换 encoder"常常同时改变了 token 数。若不控制，就会出现本节代码里那种"分解加起来 115%"的混乱。
- **读消融表的陷阱**：
  - 只看一个 benchmark（MMMU 偏 LLM 推理，CV-Bench 偏感知，DocVQA 偏分辨率）；
  - 没有控制视觉 token 数或训练 token 数；
  - 没有随机种子方差，1 分以内的差异可能只是噪声；
  - 不同论文的分数不可直接比较（评测协议、prompt、数据泄漏都不同）——本节代码把多篇论文的数字放在同一张表里，适合建立直觉，但不能当作精确的消融结论（代码 docstring 也说 "The point is the structure of the evidence, not the numeric precision"）。
- 加分点：建议用因子设计（见 Q12）或回归模型估计主效应和交互效应。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：本节的基线配方（CLIP + MLP + LLaVA-Instruct），讲义的先修要求。
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：CLIP / SigLIP 类 encoder 的训练目标。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../03-blip2-qformer-bridge/docs/zh.md)：理解"Q-Former 是成本杠杆"这一结论的对照对象。
- [阶段 12 · 04 Flamingo：面向 Few-Shot VLM 的门控 Cross-Attention](../../04-flamingo-gated-cross-attention/docs/zh.md)：Perceiver Resampler 的来源。
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../06-any-resolution-patch-n-pack/docs/zh.md)：AnyRes / NaFlex 是第 5 轴的具体实现。
- [阶段 07 · 13 Scaling Laws（规模定律）](../../../07-transformers-deep-dive/13-scaling-laws/docs/zh.md)：理解"LLM 规模决定上限"。

### 本节被哪些后续内容用到
- [阶段 12 · 08 LLaVA-OneVision：统一处理单图、多图与视频](../../08-llava-onevision-single-multi-video/docs/zh.md)：在固定 token 预算下的数据课程设计。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：原生动态分辨率与 M-RoPE。
- [阶段 12 · 10 InternVL3：原生多模态 Pretraining](../../10-internvl3-native-multimodal/docs/zh.md)：InternViT-6B 与另一种训练配方。
- [阶段 12 · 22 文档与图解理解](../../22-document-diagram-understanding/docs/zh.md)：高分辨率、高 token 数对文档任务的意义。
- [阶段 12 · 25 多模态 Agents 与计算机操作（综合项目）](../../25-multimodal-agents-computer-use/docs/zh.md)：Q16 的 UI agent 场景。
- [阶段 19 · 63 多模态 Evaluation](../../../19-capstone-projects/63-multimodal-eval/docs/zh.md)：如何正确地跑 MMMU / DocVQA 等基准。

### 延伸关键词
`MM1` · `Idefics2` · `Cambrian-1` · `Prismatic VLMs` · `Molmo / PixMo` · `SigLIP 2` · `DINOv2` · `Spatial Vision Aggregator` · `C-Abstractor` · `Perceiver Resampler` · `CV-Bench` · `MMMU` · `DocVQA` · `factorial ablation`
