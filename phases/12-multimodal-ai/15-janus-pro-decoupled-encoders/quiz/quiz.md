# 测验 · Janus-Pro：用于统一 Multimodal Models 的解耦 Encoders（Janus-Pro: Decoupled Encoders for Unified Multimodal Models）

> **阶段 12 · 多模态 AI · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 统一模型的内在矛盾 | 理解要**语义**特征（SigLIP/DINOv2：同类图像聚在一起），生成要**可重建**的编码（VQ：能解码回清晰像素），一个编码器很难两头兼顾 |
| 2 | 单编码器的"质量税" | Chameleon、Show-o、Transfusion 都用同一个视觉 tokenizer 走两个方向，必然在其中一个方向上打折扣 |
| 3 | 解耦视觉编码 | 理解：图像 → SigLIP-SO400m → 2 层 MLP → 主干；生成：（可选输入图）→ VQ tokenizer → 主干 → 预测 image token → VQ 解码器 → 像素 |
| 4 | 共享主干 | 只有 Transformer 主干共享，且每个 block 没有模态专属权重；主干前后的部件都是任务专属的 |
| 5 | 路由 | 由 prompt 格式（讲义写作 `<understand>` / `<generate>` 标签）或任务本身决定走哪条输入路径 |
| 6 | 从 LLM 初始化 | 主干可以用预训练 LLM 初始化，借来推理能力；从零训练的统一模型很难达到 |
| 7 | Janus → Janus-Pro 的扩展 | 讲义：参数 1.3B → 7B（5.4 倍）；阶段 1 72M → 90M 对、阶段 2 26M → 72M 对（约 2.8 倍）、阶段 3 增加 20 万条生成指令样本 |
| 8 | 结果（讲义转述） | GenEval 0.80，超过 DALL-E 3 的 0.67；讲义称理解侧与 LLaVA 相当 |
| 9 | JanusFlow | 把 VQ 生成路径换成 rectified flow（连续），仍是"解耦编码器 + 共享主干" |
| 10 | 适用边界 | 只要理解 → LLaVA 系；只要生成 → SD3 / Flux；两者都要 → Janus-Pro 是参考开源架构；代价是两套 tokenizer、两条输入路径、两套故障模式 |

### 核心技能（能动手做到）

- [ ] 画出 Janus-Pro 理解、文生图、图像编辑三种任务的数据流，标出每一步用哪个编码器、主干输出什么
- [ ] 解释"语义特征"与"重建编码"为什么难以统一，并能举出单编码器在哪个方向吃亏
- [ ] 读懂 `code/main.py` 的 `route` / `run_pipeline`，指出关键词子串匹配、`hash()` 不可复现、prompt 文本没进主干、"ambiguous 并行跑两路"等问题
- [ ] 为讲义练习 2 写一个更稳健的路由器，正确处理"先画再描述"这类复合指令
- [ ] 说清 Janus → Janus-Pro 的模型与数据扩展倍数，以及"三阶段训练"各阶段的作用
- [ ] 在 Janus-Pro、JanusFlow、Transfusion、Show-o、LLaVA、SD3 之间按需求做选型

---

## 二、基础自测（选择题）

**Q1.** 讲义认为统一多模态模型"不可避免的矛盾"是：

- A. 文本 token 和图像 token 的数量差距太大
- B. Transformer 无法同时处理离散和连续输入
- C. 理解需要语义丰富的特征（如 SigLIP），生成需要便于重建像素的编码（如 VQ），两种目标在单个编码器中不兼容
- D. 统一模型必须使用 MoE 结构

**Q2.** 关于 Janus-Pro 的数据路由，正确的是：

- A. 理解任务：图像 → SigLIP-SO400m → 2 层 MLP → 共享主干 → 文本；生成任务：（可选输入图）→ VQ tokenizer → 共享主干 → image token → VQ 解码器
- B. 理解与生成都走 VQ tokenizer，只是输出头不同
- C. 理解走 VQ，生成走 SigLIP
- D. 两个任务分别用两个独立的 Transformer

**Q3.** Janus-Pro 中真正在理解与生成之间**共享**的是：

- A. 视觉编码器
- B. 输出头与 VQ 解码器
- C. 每个 block 中按模态划分的 QKV 权重
- D. Transformer 主干本身，且每个 block 没有模态专属权重

**Q4.** JanusFlow 相对 Janus-Pro 的变化是：

- A. 把理解侧的 SigLIP 换成 VQ
- B. 把生成侧的 VQ 路径换成 rectified flow 的连续生成，主干在生成时输出连续量（速度场），损失从交叉熵变为回归式的 flow 损失
- C. 去掉共享主干，改为两个模型
- D. 只是把参数量从 7B 扩到 70B

**Q5.** 讲义引用的 Janus-Pro-7B 与 DALL-E 3 在 GenEval 上的分数是：

- A. 0.54 vs 0.55
- B. 0.80 vs 0.67
- C. 0.61 vs 0.80
- D. 0.67 vs 0.80

**Q6.** 按讲义与代码数据表，Janus → Janus-Pro 的扩展中，**模型参数**与**阶段 2 数据量**的倍数大约是：

- A. 2.0 倍与 1.25 倍
- B. 7 倍与 3.5 倍
- C. 1.25 倍与 5.4 倍
- D. 5.4 倍与 2.8 倍

**Q7.** 产品只需要"看图回答问题"，完全不需要生成图像。按讲义与 outputs 技能文件，应该：

- A. 不用 Janus-Pro，选 LLaVA 系理解模型——一个编码器就够，解耦是过度设计
- B. 用 Janus-Pro，因为它是参考开源架构
- C. 用 Stable Diffusion 3
- D. 用 InternVL-U 并从零做原生预训练

**Q8.** 对 `code/main.py` 的 `route("What's in this painting?")`，返回值是：

- A. `"understand"`
- B. `"generate"`
- C. `"ambiguous"`
- D. 抛出异常

---

## 三、动手 / 代码题

**Q9.** 阅读路由函数：

```python
def route(prompt: str) -> str:
    u_keywords = ["describe", "what", "why", "caption", "explain", "how many"]
    g_keywords = ["draw", "generate", "sketch", "render", "create", "paint"]
    p = prompt.lower()
    u_score = sum(1 for k in u_keywords if k in p)
    g_score = sum(1 for k in g_keywords if k in p)
    if g_score > u_score:
        return "generate"
    if u_score > g_score:
        return "understand"
    return "ambiguous"
```

1. 写出下列输入的返回值，并指出哪些是误判：`"What's in this painting?"`、`"Withdraw cash icon"`、`"Draw me a diagram that explains how a transformer works"`、`"Make this photo look like night time"`、`"Explain how to draw a cat"`。
2. 误判的根源有哪几类？
3. （讲义练习 2）设计一个更稳健的路由方案，并说明如何处理 `"Sketch a cat and then describe its breed"` 这类复合指令。

**Q10.** 连续三次用不同的 `PYTHONHASHSEED` 运行 `python main.py`，"Generate a picture of a sunset" 的输出分别是：

```text
VQ-decoded image from tokens [36, 204, 246, 42]...
VQ-decoded image from tokens [32, 153, 88, 207]...
VQ-decoded image from tokens [131, 15, 75, 252]...
```

文件开头明明写了 `random.seed(3)`。

1. 为什么输出不可复现？
2. `SiglipStub.encode` 和 `VQStub.encode` 内部都调用了 `random.seed(...)`，这会带来什么副作用？
3. 给出修复方法。

**Q11.** 阅读 `run_pipeline` 的生成分支和 ambiguous 分支：

```python
    elif task == "generate":
        tokens = vq.encode(image_seed) if image_seed else []
        trace["route"] = "(optional VQ) -> shared body -> image VQ -> decoder"
        out_tokens = body.process(tokens, kind="image_out")
        trace["output"] = vq.decode(out_tokens)
    else:
        trace["route"] = "ambiguous: run both and merge"
        feats = siglip.encode(image_seed)
        tokens = vq.encode(image_seed)
        ...
        trace["output"] = (body.process(feats, "text_out"),
                           vq.decode(body.process(tokens, "image_out")))
```

1. 用户的 prompt 文本有没有进入共享主干？这与 Janus-Pro 的"统一序列"有什么出入？
2. `demo_routing` 中 `image_seed = hash(p) % 1000` 几乎总是非零。对一个纯文生图请求，生成分支实际做了什么多余的事？
3. 对 `"Sketch a cat and then describe its breed"`，代码"并行跑两路再合并"，描述的是哪张图？正确的执行顺序应该是什么？

**Q12.** 讲义 "Use It" 说代码会"Print the routed paths for 3 examples: image QA, T2I, image editing"，但代码里没有编辑示例。请为**图像编辑**（如 "Make this photo look like night time"，附一张输入图）设计路由：哪些编码器参与？主干的输入序列和输出分别是什么？给出 `run_pipeline` 新增 `edit` 分支的伪代码。

---

## 四、面试高频题

**Q13.**（基础必考）为什么统一多模态模型要"解耦视觉编码器"？只用一个编码器会有什么问题？

**Q14.**（原理深挖）Janus-Pro 的共享主干同时看到 SigLIP 特征和 VQ token 两种输入分布，它为什么能工作？为什么要从预训练 LLM 初始化？

**Q15.**（原理深挖）请对比 Janus-Pro（解耦编码器）、Transfusion（耦合 + 连续）、Show-o（耦合 + 离散）三种统一架构。

**Q16.**（工程实践）Janus 到 Janus-Pro 做了哪些扩展？如果你来训练一个解耦编码器的统一模型，三个训练阶段分别做什么？

**Q17.**（追问型）讲义练习 1：为什么一个 7B 开源模型在 GenEval 上能超过 DALL-E 3，但在理解任务上很难追上前沿闭源模型？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Understanding wants semantic features... Generation wants reconstruction-friendly codes... The two goals are not compatible in a single encoder." A、B 不是讲义的论点（Transformer 可以同时接离散和连续输入，Transfusion 就是例子）；D 与本节无关。

### Q2 — 答案：A

讲义 Decoupled visual encoding 一节原文三条路径。B 是 Show-o/Chameleon 式单编码器；C 方向反了；D 违背"共享主干"。

### Q3 — 答案：D

讲义："The transformer body is shared. Everything upstream and downstream of the body is task-specific." 以及 "The body has no modality-specific weights per block." C 是 MMDiT 的做法；A、B 恰恰是解耦（任务专属）的部分。

### Q4 — 答案：B

讲义："JanusFlow swaps the VQ generation path for a rectified-flow generation path (continuous). The split becomes SigLIP-for-understanding + rectified-flow-for-generation." 练习 3 问"主干现在输出什么、损失怎么变"：输出从"VQ 码本上的 logits"变成"连续的速度/去噪向量"，损失从交叉熵变为 flow matching 的 MSE（与第 13 节 Transfusion 相同）。A、C、D 都不是 JanusFlow 的改动。

### Q5 — 答案：B

讲义："beats DALL-E 3 on GenEval (0.80 vs 0.67)"。A 是第 12 节 Emu3 vs SDXL；C 是代码表中 Janus（0.61）→ Janus-Pro（0.80）；D 把两者写反了。

### Q6 — 答案：D

`7 / 1.3 ≈ 5.4`，`72 / 26 ≈ 2.8`（已计算）。outputs 技能文件："Cite Janus-Pro's 5.4x model + 2.8x data scaling result." A 中的 1.25 是阶段 1（72M → 90M）的倍数。

### Q7 — 答案：A

讲义 Limitations："For products that do not need generation, Janus-Pro is over-engineered — pick a LLaVA-family understanding model." 技能文件拒绝规则："If the user needs only understanding, refuse decoupled and recommend LLaVA-family." C 无法理解图像；D 成本极高且不必要。

### Q8 — 答案：C

`"painting"` 包含子串 `"paint"`，g_score = 1；`"what"` 命中，u_score = 1；平局返回 `"ambiguous"`（已实际运行验证）。这是一个明确的理解请求，却因为子串匹配被判为歧义，并会触发"两路都跑"。

### Q9 — 参考答案

1. 已实际运行：

   | 输入 | 返回 | 是否误判 |
   |------|------|---------|
   | `What's in this painting?` | ambiguous | 误判（应为 understand；`paint` 命中 `painting`） |
   | `Withdraw cash icon` | generate | 碰巧对（但原因是 `draw` 命中 `withdraw`，不是理解了意图） |
   | `Draw me a diagram that explains how a transformer works` | ambiguous | 误判（应为 generate；`explain` 命中 `explains`） |
   | `Make this photo look like night time` | ambiguous | 无法识别（编辑请求，两个列表都不含 `make`） |
   | `Explain how to draw a cat` | ambiguous | 误判（应为 understand，用户要的是文字教程） |

2. 根源：
   - **子串匹配**：`k in p` 不看词边界（`paint`⊂`painting`、`draw`⊂`withdraw`、`what`⊂`somewhat`）；
   - **只数关键词、不看语法角色**："explain how to draw" 中 `draw` 是宾语从句里的动词，不是用户要求执行的动作；
   - **词表不完整**：`make`、`show me`、`edit`、`remove` 等都缺；
   - **任务类型只有二元**：编辑（理解 + 生成）、多步任务无处安放。
3. 稳健方案：
   - **首选显式协议**：讲义所说的 `<understand>` / `<generate>` 标签，或由 UI/API 参数（如"生成图片"按钮）决定，不靠猜；
   - **次选学习式分类器**：用小模型或让 LLM 本身输出结构化计划，例如 `[{"op": "generate", "prompt": "a cat sketch"}, {"op": "understand", "target": "step1_output", "question": "what breed"}]`；
   - **兜底规则**：用分词 + 词边界正则（`\bdraw\b`）、识别祈使句主动词；
   - **复合指令**：拆成有依赖的步骤序列，按顺序执行——先生成，再把**生成的图像**送入 SigLIP 做理解（见 Q11）。歧义时宁可向用户澄清，也不要并行跑两路。

### Q10 — 参考答案

1. `hash(p)` 对字符串的结果在每个 Python 进程中随机化（由 `PYTHONHASHSEED` 控制，默认每次启动随机），所以 `image_seed = hash(p) % 1000` 每次运行都不同；`random.seed(3)` 只固定了全局随机流的起点，管不到 `hash`。
2. 两个 `encode` 方法里调用 `random.seed(image_seed)` 会**重置全局随机数生成器**。后果：
   - 文件开头的 `random.seed(3)` 实际上被覆盖，之后 `SharedBody.process` 用 `random.randint` 生成的"输出 token"变成 `image_seed` 的确定函数；
   - 调用顺序一变（例如先 encode SigLIP 再 encode VQ），后续所有随机数都会变，模块之间产生隐式耦合；
   - 在多线程或更大的程序中，一个组件重置全局种子会悄悄改变其他组件的行为。
3. 修复：
   - 用稳定哈希代替 `hash`：`int(hashlib.md5(p.encode()).hexdigest(), 16) % 1000`，或 `zlib.crc32(p.encode()) % 1000`；
   - 每个组件持有自己的 `random.Random(seed)` 实例，例如 `rng = random.Random(image_seed); [rng.gauss(0, 0.5) for _ in range(self.dim)]`，不再触碰全局状态。

### Q11 — 参考答案

1. **没有**。`body.process(input_stream, kind)` 只接收图像特征/token 和一个 `kind` 字符串，完全不看 `input_stream` 的内容，prompt 文本从未被 tokenize、也没有进入主干。真实 Janus-Pro 中主干处理的是"文本 token + 图像特征/token"拼成的**统一序列**——理解时是 `[SigLIP 特征经 MLP 后的向量, 问题文本 token]`，生成时是 `[prompt 文本 token, <begin_of_image>]`，然后自回归吐出 image token。没有文本条件，"文生图"就无从谈起。
2. 因为 `image_seed` 非零，生成分支会对一张**并不存在的输入图**做 VQ 编码（讲义的"optional"变成了"总是"），而这些 token 随后又被 `body.process` 完全忽略。纯文生图应当 `tokens = []`，只用 prompt 文本作为条件；`if image_seed` 用 0 表示"无图"也是脆弱的约定，应改为 `image: Optional[...] = None`。
3. 代码对**同一个 `image_seed` 的输入图**同时跑 SigLIP 理解和 VQ 生成，描述的是输入图（甚至是凭空编码的图），而不是刚画出来的猫。正确顺序：
   1. 生成：`[prompt 文本] → 主干 → image token → VQ 解码器 → 像素`；
   2. 理解：把**生成的像素**送入 SigLIP → MLP → 主干，加上问题"它是什么品种" → 文本。

   两步之间有数据依赖，不能并行；这也说明为什么理解路径的输入必须是像素（经 SigLIP），而不是直接复用生成出的 VQ token——VQ token 语义弱，正是解耦的出发点。

### Q12 — 参考答案

- **参与的编码器**：
  - VQ tokenizer：把源图编码为 token，作为生成的条件（保留结构与细节）；
  - SigLIP（可选但推荐）：提供源图的语义理解，帮助主干弄清"这是一张白天街景照片"。
- **主干输入序列**：`[SigLIP(源图) 经 MLP, 编辑指令文本 token, VQ(源图) token, <begin_of_image>]`；**输出**：编辑后图像的 VQ token（自回归），再经 VQ 解码器得到像素。
- 伪代码：

  ```python
  elif task == "edit":
      sem = siglip.encode(image)                       # 理解源图
      src_codes = vq.encode(image)                     # 生成条件
      seq = [("feat", sem), ("text", tokenize(prompt)), ("vq", src_codes), ("tag", "<begin_of_image>")]
      out_codes = body.generate_image_tokens(seq, n=len(src_codes))
      trace["route"] = "SigLIP + VQ(src) + text -> shared body -> image VQ -> decoder"
      trace["output"] = vq.decode(out_codes)
  ```

- 路由层面：`route` 需要第三类 `edit`，判断依据是"有输入图 + 指令是修改动作（make / change / remove / add …）"。这说明讲义练习 4 的思路——每多一种任务，就可能多一个专属编码器或一种序列模板。

### Q13 — 参考回答要点

- **两种需求**：理解需要高层语义（类别、属性、关系），SigLIP 这类对比学习编码器擅长；生成需要能精确重建像素的编码，VQ-VAE 擅长。
- **单编码器的代价**：
  - 用 VQ 做理解：token 语义弱，同类图像的码字可能相差很大，VQA/推理性能差；
  - 用 SigLIP 做生成：特征丢失了细节，几乎无法解码回清晰像素。
  讲义："Show-o and Transfusion pay for this with a visible quality tax on one direction."
- **解耦方案**：理解走 SigLIP、生成走 VQ，只共享 Transformer 主干，两边各取所需。
- **代价**：两套 tokenizer、两条输入路径、两套故障模式；路由逻辑也要设计。
- 加分点：解耦后，主干可以从预训练 LLM 初始化，理解能力能直接继承 LLM 的知识与推理。

### Q14 — 参考回答要点

- **为什么能工作**：两种输入在进入主干前都被投影到同一个隐藏维度（SigLIP 经 2 层 MLP，VQ token 经生成侧的 embedding/adaptor），对主干来说只是"不同来源的向量序列"。讲义："enough data + enough parameters, the body absorbs the switching." 任务由序列格式和标签区分，主干学会在不同上下文中做不同的事——这与 LLM 能同时写代码和写诗是同一个道理。
- **为什么从 LLM 初始化**：
  - 讲义："the LLM contributes reasoning ability that pure-from-scratch unified models struggle to reach"；
  - 预训练 LLM 已经有语言能力和世界知识，多模态训练只需学"如何读视觉特征、如何写图像 token"，数据效率高得多；
  - 技能文件："Recommending from-scratch pretraining for a <10B model" 是拒绝项。
- 风险：两种输入分布可能互相干扰；需要合适的数据配比和分阶段训练（先对齐 adaptor，再联合训练）。
- 加分点：讲义称 Janus-Pro 从 DeepSeek-MoE-7B 初始化，而代码写的是 "DeepSeek-7B-init"；具体是哪个 DeepSeek 底座建议核对 Janus-Pro 原文。

### Q15 — 参考回答要点

| 维度 | Janus-Pro | Transfusion | Show-o |
|------|-----------|-------------|--------|
| 视觉编码 | 解耦：理解 SigLIP、生成 VQ | 耦合：同一套连续 patch 表示 | 耦合：同一个 VQ tokenizer |
| 生成方式 | 自回归 VQ token（JanusFlow 改为 rectified flow） | 连续扩散/flow，约 20 步 | 掩码离散扩散，约 16 步 |
| 理解质量 | 高（语义特征） | 受限于生成导向的表示 | 受限于 VQ 的弱语义 |
| 生成质量 | 受 VQ 上限约束（JanusFlow 提升） | 讲义认为最高 | 受 tokenizer 上限约束 |
| 复杂度 | 两套编码器、路由 | 两种损失要平衡 | 最简单（单 tokenizer、单损失） |

- 选择逻辑：两侧都要"接近前沿"时选解耦（技能文件："The decoupled approach is the only path"）；只追生成质量选 Transfusion/MMDiT；资源有限、要 inpainting 和速度选 Show-o。

### Q16 — 参考回答要点

- **扩展内容（讲义转述）**：参数 1.3B → 7B；阶段 1 对齐数据 72M → 90M 对；阶段 2 统一预训练 26M → 72M 对；阶段 3 增加 20 万条图像生成指令样本（代码表中 1.2M → 1.4M）。
- **结果**：GenEval 0.61 → 0.80（代码表）；讲义称理解侧显著提升。
- **三阶段**：
  1. **对齐**（alignment）：冻结 LLM 主干与视觉编码器，主要训练 SigLIP 后的 MLP adaptor 和生成侧的 adaptor/head，让两种视觉输入"说主干的语言"；技能文件建议 50–100M 对；
  2. **统一预训练**（unified）：解冻主干，用图文理解、文生图、纯文本混合数据联合训练；技能文件建议 70M+；
  3. **指令微调**（instruction）：对话、VQA、生成指令数据，让模型遵循 prompt；1M+ 样本。
- **教训**：解耦的想法在 1.3B、小数据时（Janus）效果有限，扩模型 + 扩数据（尤其阶段 2）后才成立——架构选择需要足够规模才能兑现。讲义练习 5 让你读原文判断哪个阶段贡献最大。

### Q17 — 参考回答要点

- **GenEval 测什么**：主要是组合性正确性（物体数量、颜色、位置关系、属性绑定），用检测器自动判分。这类能力依赖"文本条件与图像 token 的对齐"，7B 主干 + 大量合成/高质量图文数据就能做得很好；DALL-E 3 不一定针对这些项优化。
- **理解为什么难**：MMMU 这类基准考的是大学水平的多学科知识和多步推理，强依赖 LLM 本身的规模与知识量；前沿闭源模型的语言主干远大于 7B。
- **统一模型的额外压力**：同一个 7B 主干还要分出容量做图像生成，理解侧可用容量更少。
- **基准本身的局限**：GenEval 不衡量美学、细节、真实感，"GenEval 超过 DALL-E 3"不等于"整体画质超过 DALL-E 3"。
- 常见误区：用单一基准分数断言"全面超越"。另外，讲义写 Janus-Pro-7B MMMU 60.3、LLaVA 约 58，这两个数字与笔者所知的公开报告差距较大（建议核对 Janus-Pro 原文的理解基准表），回答时应以原论文为准。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：SigLIP 所属的对比学习编码器为什么语义强、重建弱。
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：理解路径"视觉编码器 + MLP + LLM"的原型。
- [阶段 12 · 13 Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像](../../13-transfusion-autoregressive-diffusion/docs/zh.md)：耦合 + 连续的统一模型。
- [阶段 12 · 14 Show-o 与离散扩散统一模型](../../14-show-o-discrete-diffusion-unified/docs/zh.md)：耦合 + 离散的统一模型。
- [阶段 08 · 02 自动编码器和变分自动编码器 (VAE)](../../../08-generative-ai/02-autoencoders-vae/docs/zh.md)：VQ 等重建型编码器的基础。

### 本节被哪些后续内容用到
- [阶段 12 · 10 InternVL3：原生多模态 Pretraining](../../10-internvl3-native-multimodal/docs/zh.md)：讲义提到的 InternVL-U 所基于的原生预训练路线。
- [阶段 12 · 16 MIO 与任意模态互转的 Streaming Multimodal Models](../../16-mio-any-to-any-streaming/docs/zh.md)：把统一模型扩展到语音、音乐、视频。
- [阶段 12 · 20 全模态模型：Qwen2.5-Omni 与 Thinker-Talker 分工](../../20-omni-models-thinker-talker/docs/zh.md)：另一种"理解与生成分工"的架构思路。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../../08-generative-ai/13-flow-matching-rectified-flows/docs/zh.md)：JanusFlow 生成路径使用的方法。

### 延伸关键词
`decoupled visual encoding` · `SigLIP-SO400m` · `VQ tokenizer` · `shared backbone` · `JanusFlow` · `InternVL-U` · `GenEval` · `MMMU` · `three-stage training` · `task routing` · `DreamLLM` · `semantic vs reconstruction features`
