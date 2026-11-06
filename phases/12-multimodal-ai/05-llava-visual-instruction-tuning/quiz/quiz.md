# 测验 · LLaVA 与视觉指令微调（LLaVA and Visual Instruction Tuning）

> **阶段 12 · 多模态 AI · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | LLaVA 的"简单" | 用 2 层 MLP 代替 Q-Former，用直接 token 拼接代替 Flamingo 的 gated cross-attention，全程只用 LM loss |
| 2 | 前向流程 | 图像 → CLIP ViT-L/14 @ 336 → `(336/14)² = 576` 个 1024 维 patch → MLP（`1024 → 4096 → 4096`，GELU）→ 576 个 4096 维 token → 替换 prompt 中的 `<image>` → LLM |
| 3 | 上下文占用 | 讲义：576 个视觉 token 在 2048 上下文中只剩 1472 给文本（占 28%）；在 32k 上下文里"is a rounding error" |
| 4 | Stage 1 对齐 | 冻结 ViT 和 LLM，只训练 MLP；558k 图文对（LAION-CC-SBU），对 caption 做 LM loss；几个小时 |
| 5 | Stage 2 视觉指令微调 | projector 继续训练，LLM 解冻（全量或 LoRA），在 158k 条 GPT-4 生成的指令数据上训练；讲义：8×A100 约 20 小时 |
| 6 | 指令数据生成 | 只给 GPT-4（纯文本）看 COCO 的 5 条 caption + bounding box 列表，用三种模板生成"对话 / 详细描述 / 复杂推理"；GPT-4 看不到图像，会产生幻觉噪声 |
| 7 | 为什么被大量复制 | 无 Stage-1 专用损失；projector 训练几小时；换 LLM 只需重训 projector；数据管道便宜可复制 |
| 8 | LLaVA-NeXT 的 AnyRes | 高分辨率图切成 336×336 的网格块 + 1 张全局缩略图，每块 576 token；2×2 网格总计约 2880 token，OCR 与图表任务大幅提升 |
| 9 | 与 Q-Former 的取舍 | 讲义："MLP wins on simplicity and token flexibility. Q-Former wins on token budget." 上下文涨到 32k–128k 后，token 预算不再是硬约束 |
| 10 | Prompt 格式 | `系统提示 USER: <image> 问题 ASSISTANT: 回答`；`<image>` 是占位符，最终被 N 个视觉 embedding 替换 |

### 核心技能（能动手做到）

- [ ] 手写 2 层 MLP projector（Linear → GELU → Linear），并按任意维度计算参数量（含 bias）
- [ ] 计算任意分辨率、patch 大小、AnyRes 网格下的视觉 token 数，以及它们在不同上下文窗口中的占比
- [ ] 正确实现 `<image>` 的替换：在 **embedding 层**把占位符展开为 N 个视觉向量，并同步展开 labels
- [ ] 为 Stage 2 构造训练标签：只对 assistant 回答计算 loss，系统提示、用户问题、视觉 token 全部忽略
- [ ] 说清 LLaVA 两阶段各冻结什么、训练什么、用什么数据，以及跳过 Stage 1 的影响
- [ ] 能指出讲义与代码中的不一致（projector 参数量的三个数字、prompt 格式、"替换发生在 tokenization 之前"的表述）

---

## 二、基础自测（选择题）

**Q1.** LLaVA-1.5（CLIP ViT-L/14 @ 336 + 2 层 MLP + 4096 维 LLM）处理一张图时，下列流程正确的是：

- A. 336×336 图像被切成 `24 × 24 = 576` 个 14×14 patch，ViT 输出 576 个 1024 维向量，MLP 逐个投影成 4096 维，替换 prompt 中的 `<image>` 后整体送入 LLM
- B. ViT 输出一个 pooled 向量，MLP 把它扩展成 576 个 token
- C. 576 个 patch 先经 Q-Former 压缩成 32 个 token 再送入 LLM
- D. 视觉特征通过 LLM 每层的 cross-attention 注入，不进入输入序列

**Q2.** 关于 LLaVA 的两阶段训练，正确的是：

- A. Stage 1 解冻 ViT 和 LLM，只冻结 projector
- B. Stage 1 使用 ITC + ITM + ITG 三种损失
- C. Stage 1 冻结 ViT 和 LLM，只训练 MLP projector，在 558k 图文对上对 caption 做 LM loss；Stage 2 继续训练 projector 并解冻 LLM，在 158k 条视觉指令数据上训练
- D. Stage 2 只训练 projector，LLM 始终冻结

**Q3.** 2 层 MLP projector `1024 → 4096 → 4096`（两层都带 bias）的参数量是：

- A. 约 8.4M
- B. 约 21.0M
- C. 约 40M
- D. 约 4.2M

**Q4.** LLaVA-Instruct（158k）的数据是怎样生成的？

- A. 人工标注员看图写问答
- B. 用 GPT-4V（多模态）直接看图生成问答
- C. 用 LLaVA 自身生成再人工筛选
- D. 把 COCO 图像的 5 条人工 caption 和 bounding box 列表以文本形式交给纯文本 GPT-4，用"对话 / 详细描述 / 复杂推理"三种模板生成指令与回答

**Q5.** 在 2048 token 上下文的 LLM 中放一张 576 token 的图，下列说法正确的是：

- A. 剩余 1024 个 token，图像占 50%
- B. 图像占 576 / 32768 ≈ 1.8%
- C. 剩余 1472 个 token 给文本，图像约占 28.1%
- D. 放不下

**Q6.** 讲义认为 2023 年后社区从 Q-Former 转向 MLP projector，最主要的原因是：

- A. LLM 上下文增长到 32k–128k，token 预算不再是硬约束，而 MLP 更简单、只用 LM loss、换 LLM 只需重训 projector、天然支持多图和视频
- B. MLP 的视觉 token 更少
- C. MLP 不需要任何训练
- D. Q-Former 无法用于单张图像

**Q7.** LLaVA-NeXT 的 AnyRes 把一张 672×672 的图切成 2×2 个 336×336 块，再加一张全局缩略图，每块 576 token。视觉 token 总数为：

- A. 576
- B. 2304
- C. 9792
- D. 2880

**Q8.** 讲义写道："Before tokenization, it (`<image>`) is replaced with the 576 visual tokens." 关于 `<image>` 的替换，更准确的说法是：

- A. 在 tokenization 之前把 `<image>` 替换成 576 个特殊文本字符串
- B. 文本照常 tokenization，`<image>` 被编码为一个特殊占位 id；在 embedding 层把这个位置展开为 576 个**连续向量**（projector 的输出），labels 也要同步展开
- C. 视觉 token 被离散化成词表中的 576 个 id
- D. `<image>` 不需要替换，LLM 会自动去读图像

---

## 三、动手 / 代码题

**Q9.** projector 参数量的"三个数字"。

1. 本节代码 `MLPProjector(16, 32, 24)` 打印 `params: 1,336`，请手算验证。
2. 讲义中 projector 的参数量出现了 "~22M"（Parameter economy 与代码 TAKEAWAYS）和 "40M + LM"（对比表格）两个数字。按 `1024 → 4096 → 4096`、含 bias 精确计算，应为多少？
3. 讲义练习 1 问它占 LLaVA-13B 的比例。但讲义同时写"LLaVA-1.5 at 13B 的 projector 是 `1024 → 4096 → 4096`"——Vicuna-13B（Llama-13B 架构）的隐藏维度是 5120。按 5120 重新计算 projector 参数量，并分别给出两种口径下占 13B 模型的比例。

**Q10.** 阅读 `build_llava_prompt`：

```python
def build_llava_prompt(system: str, user: str, image_tokens: int) -> dict:
    placeholder = "<image>"
    template = (
        f"SYSTEM: {system}\n"
        f"USER: {placeholder} {user}\n"
        f"ASSISTANT: "
    )
    return {
        "raw_prompt": template,
        "placeholder": placeholder,
        "image_tokens": image_tokens,
        "text_token_estimate": len(template.split()) + 10,
    }
```

1. DEMO 2 打印 "text token estimate: ~34 tokens"。这个数是怎么来的？它有哪些问题？
2. 这里的模板与讲义 "The prompt format" 小节给出的格式有什么不同？为什么 prompt 格式在推理时必须与训练时完全一致？
3. 打印标题写着 "raw prompt (LLM receives this after image-token replacement)"，但打印出来的仍然包含 `<image>`。代码真的做了替换吗？

**Q11.** 实现 Stage 2 训练样本的构造：给定 token id 序列（`<image>` 用特殊 id `-200` 表示）、对应的 labels（只有 assistant 回答部分是真实 id，其余为 `-100` 表示忽略）、投影后的视觉向量列表和 embedding 表，写出 `splice(input_ids, labels, image_embeds, embed)`，返回展开后的 embedding 序列和对齐后的 labels。用"SYSTEM: USER: <image> describe it ASSISTANT: a red car ."、3 个视觉 token 验证长度与 labels。

**Q12.** AnyRes 的 token 成本（讲义练习 3）。代码 DEMO 3 输出：

```text
  336x336 (base)      :  1 tiles + 0 thumbnail =   576 tokens
  672x336 (1x2)       :  2 tiles + 1 thumbnail =  1728 tokens
  672x672 (2x2)       :  4 tiles + 1 thumbnail =  2880 tokens
  1344x672 (2x4)      :  8 tiles + 1 thumbnail =  5184 tokens
  1344x1344 (4x4)     : 16 tiles + 1 thumbnail =  9792 tokens
```

1. 1344×672 的图在这种切法下是 base 的多少倍 token？在 4k、32k 上下文中各占多少？
2. 讲义说 AnyRes 把图切成 "2x2 or 1x3 grid"，代码给出的是 1×2、2×4、4×4。这些网格的选择会影响什么？如果允许无限细分，会出什么问题？
3. 为什么 AnyRes 还要额外加一张全局缩略图？

---

## 四、面试高频题

**Q13.**（基础必考）请介绍 LLaVA 的架构和两阶段训练流程：每个阶段冻结什么、训练什么、用什么数据、loss 是什么？

**Q14.**（原理深挖）LLaVA 的 Stage 1 只训练一个 MLP，它到底学到了什么？如果跳过 Stage 1 直接做视觉指令微调，会发生什么？（讲义练习 4 提到 Prismatic VLMs 的消融）

**Q15.**（原理深挖）用纯文本 GPT-4 根据 caption 生成视觉指令数据，这个方法为什么有效？有哪些风险？如果要为医学影像或遥感图像构建类似数据，你会怎么做？

**Q16.**（工程实践）你要基于 LLaVA 路线做一个"财报图表问答"模型。从分辨率、数据、训练配置、评估四个方面给出方案。

**Q17.**（追问型）LLaVA 类模型常出现"物体幻觉"（描述图中不存在的物体）。可能的原因有哪些？如何评估和缓解？

---

## 五、参考答案与解析

### Q1 — 答案：A

`336 / 14 = 24`，`24² = 576`（已计算）。讲义：

```
img -> ViT -> 576 patches of dim 1024
patches -> MLP -> 576 tokens of dim 4096
replace <image> token with the 576 projected tokens
```

B 错：LLaVA 用的是全部 patch token，而不是 pooled 向量。C 是 BLIP-2 的 Q-Former 路线。D 是 Flamingo 的 gated cross-attention 路线。

### Q2 — 答案：C

讲义 Stage 1："Freeze ViT. Freeze LLM. Train only the 2-layer MLP. Dataset: 558k image-caption pairs (LAION-CC-SBU). Loss: language modeling on the caption"；Stage 2："Unfreeze the projector (still trainable). Unfreeze the LLM (usually fully, sometimes LoRA). Train on 158k visual-instruction turns." B 是 BLIP-2 Stage 1 的损失。D 错：Stage 2 的关键就是解冻 LLM。

### Q3 — 答案：B

`1024 × 4096 + 4096 + 4096 × 4096 + 4096 = 4,198,400 + 16,781,312 = 20,979,712 ≈ 21.0M`（已用 Python 计算）。讲义 Parameter economy 写"~22M"，对比表格写"40M"，都与精确值不符；C 就是表格里的 40M。A ≈ 只算第一层的两倍；D ≈ 只算第一层（4.2M）。

### Q4 — 答案：D

讲义："Feed GPT-4 the COCO caption and bounding-box data for an image ... None of this touches the image directly — only the text description. GPT-4 hallucinates plausible image content." A 正是 LLaVA 想避免的高成本方案。B 是后来 ShareGPT4V 的做法（用 GPT-4V 生成稠密 caption），不是原始 LLaVA-Instruct。C 不对。

### Q5 — 答案：C

`2048 − 576 = 1472`，`576 / 2048 = 28.1%`（代码 DEMO 2 输出 "image 28.1%"，扣除约 34 个文本 token 后 remain 1438）。代码 TAKEAWAYS 写"30% of 2k context"，是近似。B 是 32k 窗口下的比例。

### Q6 — 答案：A

讲义："By late 2023 the token budget was no longer the binding constraint (LLM contexts grew to 32k-128k+) and simplicity dominated." 以及 "LLM can be swapped ... by retraining just the projector"、对比表中 Multi-image / Video 一栏"Natural (concat)"。B 说反了（MLP 的 token 更多）。C 错：MLP 需要训练。D 错。

### Q7 — 答案：D

`4 × 576 + 1 × 576 = 2880`，与讲义"total around 2880 visual tokens per image"一致。B 漏掉了缩略图。C 是 4×4 网格 + 缩略图（代码最后一行）。

### Q8 — 答案：B

视觉 token 是 projector 输出的**连续向量**，不在词表中，不可能"在 tokenization 之前"被替换成文本。正确流程：先对含 `<image>` 的文本 tokenize（`<image>` 映射为一个特殊 id），查 embedding 表得到文本向量，再把占位位置展开为 576 个视觉向量；labels 同步在该位置插入 576 个"忽略"标记（见 Q11）。A、C 把视觉 token 当成了离散 id（那是第 11 节 Chameleon 一类 early-fusion 模型的做法）。D 错。讲义的这句话是一个值得注意的简化表述。

### Q9 — 参考答案

1. `16 × 32 + 32 + 32 × 24 + 24 = 512 + 32 + 768 + 24 = 1,336`，与代码输出一致。`num_params` 用 `len(W) * len(W[0])` 计算权重矩阵元素数，再加 bias 长度。
2. 精确值 **20,979,712 ≈ 21.0M**。"~22M"是粗略取整，"40M"偏差较大（相当于约两倍）。讲义的 Use It 写 toy 维度为 "16 → 32 → 32"，而代码实际是 `16 → 32 → 24`，也不一致。
3. 按 5120 维：`1024 × 5120 + 5120 + 5120 × 5120 + 5120 = 31,467,520 ≈ 31.5M`。按约 13.35B 的模型总量估算：
   - 4096 口径：`21.0M / 13.35B ≈ 0.16%`；
   - 5120 口径：`31.5M / 13.35B ≈ 0.24%`。

   无论哪种口径，projector 都不到模型的 0.3%，这正是"projector is trivial next to the LLM"的含义。但第二层的输出维度必须等于 LLM 的 embedding 维度，13B 模型写成 4096 是讲义的笔误。

### Q10 — 参考答案

1. `template.split()` 按空白切出 24 个"词"，再加 10，得到 34（已运行验证）。问题：
   - 词数不等于 token 数：BPE 会把 "artificial"、标点、换行等切成不同数量的 token，应当用目标 LLM 的 tokenizer 实际计数；
   - `<image>` 本身被算进了文本词数，而它在实际序列中会被 576 个视觉 token 替换；
   - "+10" 是没有依据的魔法数字。
2. 讲义格式是一行："`<系统提示> USER: <image> Describe this image in detail. ASSISTANT:`"，系统提示前**没有** `SYSTEM:` 前缀，各部分以空格连接；代码加了 `SYSTEM:` 前缀并用换行分隔。推理时的格式必须与 Stage 2 训练格式一致，因为模型在指令微调中学到的是"看到 `ASSISTANT:` 之后开始回答"这一特定模式；格式不一致会导致回答质量下降、不停止生成或角色混乱。
3. 没有。`build_llava_prompt` 只记录了 `image_tokens = 576` 这个数字，DEMO 2 打印的仍是含占位符的原始字符串，也没有与 DEMO 1 的 projector 输出连接起来。替换应当在 embedding 层完成（见 Q11）。

### Q11 — 参考答案

```python
IMAGE_TOKEN = -200          # 占位 id，不在词表中
IGNORE = -100               # 不计算 loss 的标签

def splice(input_ids, labels, image_embeds, embed):
    seq, lab = [], []
    for tid, y in zip(input_ids, labels):
        if tid == IMAGE_TOKEN:
            seq.extend(image_embeds)                 # 1 个占位 -> N 个视觉向量
            lab.extend([IGNORE] * len(image_embeds))  # 视觉位置不算 loss
        else:
            seq.append(embed[tid])
            lab.append(y)
    return seq, lab

vocab = {w: i for i, w in enumerate("SYSTEM: USER: ASSISTANT: describe it a red car .".split())}
embed = [[float(i)] * 4 for i in range(len(vocab))]
prompt = ["SYSTEM:", "USER:", "<image>", "describe", "it", "ASSISTANT:"]
answer = ["a", "red", "car", "."]
ids = [IMAGE_TOKEN if w == "<image>" else vocab[w] for w in prompt + answer]
labels = [IGNORE] * len(prompt) + [vocab[w] for w in answer]
img = [[0.5] * 4 for _ in range(3)]
seq, lab = splice(ids, labels, img, embed)
print(len(ids), len(seq), len(lab), lab)
```

实际运行输出：`10 12 12 [-100, -100, -100, -100, -100, -100, -100, -100, 5, 6, 7, 8]`。原始 10 个 id，1 个占位展开成 3 个视觉向量，序列长度变为 12；labels 中只有回答 "a red car ." 的 4 个位置是真实 id。

要点：
- 视觉位置、系统提示、用户问题都不计算 loss，模型只学"如何回答"；
- 训练时还要把 labels 整体左移一位与 logits 对齐（next-token prediction），框架通常在 loss 函数内部完成；
- 真实实现是批量操作：同一 batch 中各样本展开后长度不同，需要再做 padding 并生成 attention mask。

### Q12 — 参考答案

1. `5184 / 576 = 9` 倍（8 块 + 1 张缩略图）。4k 上下文：`5184 > 4096`，放不下；32k 上下文：`5184 / 32768 ≈ 15.8%`。
2. 网格选择决定了：
   - token 数（随块数线性增长）；
   - 对原图长宽比的保真度（选与原图比例最接近的网格，减少拉伸或填充）；
   - 每块的有效分辨率（块越多，每个像素区域被看得越细）。

   如果允许无限细分，高分辨率图会产生成千上万个视觉 token，挤占上下文、拖慢推理，并且 LLM 训练时见过的视觉 token 数分布也会被打破。所以实际系统会限定一组允许的网格（讲义说 2×2 或 1×3；按笔者对 LLaVA-NeXT 公开资料的理解，其支持的配置总块数上限为 4，可对照原博客核对），代码中的 2×4、4×4 超出了这个范围，仅用于演示 token 增长。第 06 节会讨论更系统的方案（Patch-n'-Pack、NaFlex）。
3. 每个块只看到局部，缺少整体构图和物体之间的位置关系；全局缩略图用 576 个 token 提供"整张图长什么样"的上下文，块提供细节，二者互补。

### Q13 — 参考回答要点

- **架构**：CLIP ViT-L/14 @ 336（576 个 patch，1024 维）→ 2 层 MLP（GELU，`1024 → 4096 → 4096`）→ LLM（Vicuna，后来 Llama 等）。视觉 token 直接替换 prompt 中的 `<image>`，与文本 token 一起进入 LLM 的 self-attention。
- **Stage 1（对齐）**：冻结 ViT 和 LLM，只训练 projector；558k 图文对，LM loss 只计算 caption 部分；目的是把 ViT 空间映射到 LLM 的词嵌入空间。
- **Stage 2（指令微调）**：projector + LLM（全量或 LoRA）训练；158k GPT-4 生成的对话 / 详细描述 / 复杂推理数据；loss 只计算 assistant 回答；讲义：8×A100 约 20 小时。
- **参数**：讲义：LLaVA-1.5-7B 约 7.3B，其中 ViT 303M、projector 约 22M（精确值约 21.0M）。
- 加分点：说明讲义开头"LLaVA (April 2023) ... replaced BLIP-2's Q-Former with a 2-layer MLP"的说法需要区分版本——据 LLaVA-1.5 论文，2 层 MLP 连接器是 1.5 版引入的改进，最初版本使用的是单个线性投影层。

### Q14 — 参考回答要点

- **Stage 1 学到的**：一个"翻译器"，把 ViT 的 patch 特征映射到 LLM 的 embedding 空间中 LLM 能"读懂"的区域。因为 LLM 冻结，只有 projector 调整，所以它被迫让视觉 token "看起来像" LLM 熟悉的词嵌入组合，从而使 LLM 能为图片生成 caption。
- **为什么便宜**：只有约 21M 参数可训练，讲义："In a single epoch at batch 128 this is done in a few hours."
- **跳过 Stage 1**：直觉上，Stage 2 开始时 projector 是随机的，LLM 被解冻后会先看到大量噪声视觉 token，可能被这些噪声梯度扰动、损伤语言能力，也可能学会忽略视觉输入。但讲义练习 4 要你查 Prismatic VLMs 的消融结论——据笔者对该论文的理解，在其设定下单阶段训练（跳过对齐预训练）的效果与两阶段相当且节省算力；具体结论以论文为准，面试时可以说明"这是一个经验问题，取决于数据量、学习率和是否解冻 LLM"。
- 加分点：讲义 Prompt format 小节："the LLM handles the novel input because stage 1 taught it to"——这是两阶段设计的原始动机。

### Q15 — 参考回答要点

- **为什么有效**：GPT-4 的语言能力很强，给它 5 条 caption + 物体框坐标，它就能"想象"出图像内容并生成多样的问答（对话、细节描述、需要推理的问题）；LLaVA 只需要学会"把视觉 token 和这些文字关联起来"。成本低、无需人工标注、可快速扩展。
- **风险**：
  - **幻觉**：讲义："GPT-4 hallucinates plausible image content"，caption 中没有的细节会被编造，模型学到"说出看起来合理但图中不存在的内容"；
  - **覆盖面窄**：只覆盖 COCO 的物体类别和场景；
  - **空间信息粗糙**：bounding box 坐标以文本形式传递，GPT-4 对空间关系的推理可能出错；
  - **风格单一**：回答风格被 GPT-4 主导。
- **新领域数据管道**（讲义练习 5 的四步）：
  1. 收集领域图像与已有的文本元数据（放射报告、遥感地物标注）；
  2. 设计领域化的生成模板（如"根据报告提出鉴别诊断问题"），交给强 LLM 生成指令-回答；
  3. 过滤与校验：规则过滤 + 领域专家抽检，删除报告中不存在的发现；
  4. 混合通用数据训练并在领域评测集上验证。
- **每步可能出错**：元数据不完整导致幻觉增多；模板引导出超出证据的结论；专家抽检比例太低；只用领域数据导致通用能力退化。医学场景还要注意隐私与合规（技能文件明确拒绝把 vibes-eval 用于医学诊断）。

### Q16 — 参考回答要点

- **分辨率**：图表包含小字号数字和图例，336×336 远远不够；使用 AnyRes 或原生高分辨率方案（第 06 节），并评估 token 成本——一张 2×2 + 缩略图是 2880 token。技能文件建议："Run one OCR-requiring prompt at 336x336 base and again at AnyRes; note the delta."
- **数据**：
  - Stage 1 可复用通用对齐数据；
  - Stage 2 混合通用指令数据 + 图表/文档数据（讲义提到 LLaVA-1.5 混入 VQA 等学术任务数据）+ 领域内用强模型生成并人工校验的财报图表问答；
  - 加入 ShareGPT4V 式稠密描述提升细节能力。
- **训练**：LLM 用 LoRA 或全量；视觉 encoder 视预算决定是否在 Stage 2 解冻（讲义："often unfrozen stage 2"）；loss 只算回答部分。
- **评估**：数值精确匹配率（读数是否正确）、推理正确率、幻觉率（编造不存在的数值）；跑一遍 10 条 vibes-eval 做冒烟测试，再做正式 benchmark。
- 常见误区：只用通用 VQA 数据，指望模型自动学会读图表；只看最终答案而不检查推理链（技能文件："Claiming a pass on reasoning prompts without checking the reasoning chain"）。

### Q17 — 参考回答要点

- **原因**：
  - 训练数据本身有幻觉（GPT-4 根据 caption 编造的细节）；
  - LLM 强大的语言先验："餐桌"出现时倾向于说出"叉子"，即使图中没有；
  - 分辨率低，小物体看不清只能"猜"；
  - 长回答越往后越依赖语言先验，幻觉更多。
- **评估**：技能文件要求区分"编造物体"与"描述啰嗦"（"Flag specifically which objects are invented vs merely elaborately described"）；可以用针对物体存在性的是/否问答评测（如 POPE 类方法），以及对详细描述做逐物体核对。
- **缓解**：
  - 数据侧：用更准确的稠密 caption（讲义提到的 ShareGPT4V），过滤生成数据中的不实内容，加入"图中没有 X"的负样本问答；
  - 模型侧：提高分辨率（AnyRes）、使用更强的视觉 encoder；
  - 推理侧：降低温度、限制回答长度、要求模型对不确定处表态；
  - 对齐侧：用偏好优化（如 DPO）惩罚幻觉回答。
- 加分点：讲义开头说 LLaVA "beat Flamingo on MMMU"。这一点值得核对——MMMU 基准发布时间晚于 LLaVA 原论文，原论文的对比主要基于 LLaVA-Bench 和 ScienceQA；面试中引用 benchmark 数字时要说清模型版本和来源。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：LLaVA 的视觉塔是 CLIP ViT-L/14。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../03-blip2-qformer-bridge/docs/zh.md)：LLaVA 要替代的 Q-Former 路线。
- [阶段 12 · 04 Flamingo：面向 Few-Shot VLM 的门控 Cross-Attention](../../04-flamingo-gated-cross-attention/docs/zh.md)：LLaVA 要替代的 gated cross-attention 路线。
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：Stage 2 本质上是多模态 SFT，loss mask 的做法相同。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：Stage 2 常用 LoRA 微调 LLM。
- [阶段 04 · 25 Vision-Language Models — ViT-MLP-LLM 模式](../../../04-computer-vision/25-vision-language-models/docs/zh.md)：从计算机视觉角度认识同一模式。

### 本节被哪些后续内容用到
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../06-any-resolution-patch-n-pack/docs/zh.md)：AnyRes 之后的高分辨率方案。
- [阶段 12 · 07 开放 Weight VLM 的构建方案：真正重要的因素](../../07-open-weight-vlm-recipes/docs/zh.md)：数据与结构的消融（Prismatic 等）。
- [阶段 12 · 08 LLaVA-OneVision：统一处理单图、多图与视频](../../08-llava-onevision-single-multi-video/docs/zh.md)：讲义提到的 OneVision。
- [阶段 12 · 22 文档与图解理解](../../22-document-diagram-understanding/docs/zh.md)：对高分辨率与 OCR 的进一步需求。
- [阶段 19 · 60 用于 Modality Alignment 的投影层](../../../19-capstone-projects/60-projection-layer-modality-align/docs/zh.md)、[阶段 19 · 63 多模态 Evaluation](../../../19-capstone-projects/63-multimodal-eval/docs/zh.md)：综合项目中实现 projector 并评估。

### 延伸关键词
`MLP projector` · `visual instruction tuning` · `LLaVA-Instruct-158k` · `LAION-CC-SBU 558k` · `<image> placeholder` · `IGNORE_INDEX / loss mask` · `AnyRes` · `LLaVA-NeXT` · `ShareGPT4V` · `Prismatic VLMs` · `object hallucination` · `POPE` · `vibes eval`
