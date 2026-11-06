# 测验 · Vision-Language Models — ViT-MLP-LLM 模式（Vision-Language Models — The ViT-MLP-LLM Pattern）

> **阶段 04 · 计算机视觉 · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要 VLM | CLIP 只能给图文相似度打分、不生成文本，回答不了"图里有几辆红车"；VLM 把 CLIP 系图像编码器接到完整的语言模型上，看图 + 问题 → 生成答案 |
| 2 | ViT-MLP-LLM 三件套 | 视觉编码器（ViT / CLIP-L / SigLIP / DINOv3）出 patch token → projector（2–4 层 MLP 或 Q-former）映射到 LLM 的 embedding 维度 → decoder-only LLM 把视觉 token 和文本 token 当作同一序列读取并生成文本 |
| 3 | `<image>` 占位符合并 | 文本里的图像占位 token 被替换成 projector 输出的视觉 embedding；占位符个数必须等于 patch 数 |
| 4 | 三阶段训练 | 对齐（冻结 ViT 与 LLM，只训 projector，图文描述对）→ 预训练（全部解冻，大规模图文交错数据）→ 指令微调（(图, 问, 答) 三元组，变成可用助手）；多数 LoRA 微调针对第 3 阶段 |
| 5 | DeepStack | 不只用 ViT 最后一层，而是取多个深度的特征：深层管语义（"图里有什么"），浅层管细粒度空间与纹理（"具体在哪"） |
| 6 | 视频时间建模 | Qwen3-VL 从 T-RoPE（时间旋转位置编码）演进到"基于文本的时间对齐"：在视频帧之间插入显式时间戳文本 token |
| 7 | 幻觉与 CMER | 爬取数据中约 12% 的图文对描述并不完全基于图像；CMER = 文本置信度高、但（独立 CLIP 系检查器测得的）图文相似度低的输出占比，作为生产 KPI，高 CMER 输出转人工审核 |
| 8 | LoRA / QLoRA 微调 | rank 16–64 加在 attention + projector 上，或 4-bit 底座的 QLoRA，单张 A100/H100 可跑；5k–50k 样本、100–5,000 美元算力、2–10 小时 |
| 9 | 空间推理仍是短板 | 当前 VLM 在上下左右、计数、距离类基准上约 50–60%；纯空间任务优先用关键点/姿态、深度模型或检测框几何后处理 |

### 核心技能（能动手做到）

- [ ] 能用 PyTorch 写出 2 层 MLP projector，并说清输入 `(B, N_patches, d_vit)` → 输出 `(B, N_patches, d_llm)` 的形状变化
- [ ] 能手算 `ToyVLM(vit_dim=32, llm_dim=64, num_classes=5)` 的参数量，并解释每一层的作用
- [ ] 能写出 `<image>` 占位符替换（`_merge`）的逻辑，并说明占位符数量与 patch 数不一致时为什么必须报错
- [ ] 能实现 `cross_modal_error_rate`，并能手算给定置信度与相似度下的 CMER
- [ ] 能发现"按类别顺序生成的数据不打乱就切分，导致验证集只有一个类"这类数据泄漏 / 评估偏差 bug
- [ ] 能根据精度、延迟、上下文长度、预算，在托管 API / 开源自部署 / LoRA 领域微调三种路线中做出选择

---

## 二、基础自测（选择题）

**Q1.** 在 ViT-MLP-LLM 的**对齐（alignment）阶段**，通常训练哪一部分？

- A. 只训练视觉编码器
- B. 只训练 LLM
- C. 只训练 projector，ViT 和 LLM 冻结
- D. 三者同时全量训练

**Q2.** 关于 DeepStack（Qwen3-VL），下列说法正确的是：

- A. 把 LLM 的层数加倍
- B. 只使用 ViT 最深一层的特征，因为它语义最强
- C. 采样多个 ViT 深度的特征，让 LLM 同时拿到深层语义与浅层的细粒度空间信息
- D. 一种 4-bit 量化方案

**Q3.** 下列哪种输出会被 CMER 计为一次"跨模态错误"？（阈值：`conf_threshold=0.8`，`sim_threshold=0.25`）

- A. 置信度 0.95，图文相似度 0.60
- B. 置信度 0.50，图文相似度 0.10
- C. 置信度 0.92，图文相似度 0.12
- D. 置信度 0.80，图文相似度 0.05

**Q4.** 为什么几乎所有现代 VLM 用 CLIP / SigLIP 系编码器，而不是 ImageNet 监督训练的 ResNet？

- A. SigLIP 参数更多
- B. ResNet 无法输出 token
- C. CLIP/SigLIP 与文本联合训练，输出空间已近似对齐语言，projector 只需做少量工作
- D. SigLIP 推理一定更快

**Q5.** 讲义 `MinimalVLM._merge` 中，若某个 batch 样本里 `<image>` 占位 token 的个数与 `vision_embeds` 的 patch 数不一致，会发生什么？

- A. 自动截断多余的 patch
- B. 自动用零向量补齐
- C. 抛出 `ValueError`，要求每个样本预先填充相同数量的图像占位 token
- D. 静默跳过该样本

**Q6.** 关于 VLM 三阶段训练，下列说法**错误**的是：

- A. 对齐阶段使用图文描述对（image-caption pairs）
- B. 预训练阶段解冻全部模块，使用大规模图文交错数据
- C. 指令微调使用精选的（图像，问题，答案）三元组，教会模型对话行为
- D. 大多数 LoRA 微调针对的是对齐阶段，因为只有 projector 需要训练

**Q7.** 你的业务需要判断"货架上哪个商品放在另一个商品的上面"，讲义建议怎么做？

- A. 直接信任通用 VLM 的回答，它在空间推理上已超越人类
- B. 重度验证；纯空间任务可优先考虑检测模型 + 框几何后处理、深度模型或关键点模型
- C. 换一个上下文更长的 VLM 就能解决
- D. 只要把 prompt 写得更长即可

**Q8.** Q-former 与 MLP projector 相比，最显著的特点是：

- A. Q-former 输出固定数量的视觉 query token（BLIP-2 风格），而 MLP 的输出 token 数等于 patch 数
- B. Q-former 不需要训练
- C. Q-former 只能用于视频
- D. MLP projector 会改变 token 的数量

---

## 三、动手 / 代码题

**Q9.**（形状与参数量）阅读 `main.py`：

```python
class Projector(nn.Module):
    def __init__(self, vit_dim=32, llm_dim=64, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(vit_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, llm_dim),
        )

class ToyVLM(nn.Module):
    def __init__(self, vit_dim=32, llm_dim=64, num_classes=5):
        super().__init__()
        self.projector = Projector(vit_dim, llm_dim, hidden=64)
        self.head = nn.Linear(llm_dim, num_classes)

    def forward(self, vision_tokens):
        projected = self.projector(vision_tokens)
        pooled = projected.mean(dim=1)
        return self.head(pooled)
```

1. 输入 `vision_tokens` 形状为 `(32, 16, 32)`，写出 `projected`、`pooled`、输出 logits 的形状。
2. `ToyVLM()` 的总参数量是多少？
3. `deepstack_features` 把 3 个 `(4, 16, 32)` 张量沿最后一维拼接，输出形状是什么？若要把这个结果送进 `Projector`，`vit_dim` 应设为多少？

**Q10.**（找 bug）`main.py` 的数据生成与切分如下。请指出验证集有什么问题、会让打印出来的 `val_acc` 呈现什么特征，并给出修复。

```python
def synthetic_vision_class_data(num_classes=5, num_patches=16, d_vit=32, per_class=40, seed=0):
    # ...
    for c in range(num_classes):
        for _ in range(per_class):
            # ...
            X.append(base + noise)
            Y.append(c)
    return torch.stack(X), torch.tensor(Y)

# main() 中
X, Y = synthetic_vision_class_data()
split = int(0.85 * len(X))
x_tr, y_tr = X[:split], Y[:split]
x_va, y_va = X[split:], Y[split:]
```

**Q11.**（手算 + 解释）`cross_modal_error_rate` 的实现：

```python
def cross_modal_error_rate(image_emb, text_emb, text_confidence,
                           sim_threshold=0.25, conf_threshold=0.8):
    image_emb = F.normalize(image_emb, dim=-1)
    text_emb = F.normalize(text_emb, dim=-1)
    sim = (image_emb * text_emb).sum(dim=-1)
    high_conf_low_sim = (text_confidence > conf_threshold) & (sim < sim_threshold)
    return high_conf_low_sim.float().mean().item()
```

1. 若 4 个输出归一化后的余弦相似度为 `[0.90, 0.10, 0.10, 0.30]`，置信度为 `[0.95, 0.70, 0.90, 0.85]`，CMER 是多少？
2. `main()` 中模拟了 4 个"好"输出和 4 个"幻觉"输出（幻觉文本是与图像无关的随机 32 维单位向量），注释说"expected ~0.5"。为什么实际打印值**不一定**正好是 0.500？

---

## 四、面试高频题

**Q12.**（基础必考）请画出 / 描述 ViT-MLP-LLM 架构：一张图片 + 一个问题，是怎样一步步变成答案的？每一步的张量形状是什么？

**Q13.**（原理深挖）为什么 VLM 训练第一阶段要冻结 ViT 和 LLM、只训练 projector？MLP projector 和 Q-former 各有什么取舍？

**Q14.**（工程实践）你负责一个线上 VLM 服务，用户投诉"模型一本正经地描述图里不存在的东西"。你会怎么监控和治理？CMER 有什么局限？

**Q15.**（场景设计）公司要做"工厂产线缺陷图片的自动描述与分类"，预算有限。请在托管 API、开源自部署、LoRA 领域微调之间做选型，并给出数据、成本和上线方案。

**Q16.**（追问型）VLM 为什么在计数、上下左右这类空间推理上表现差？从架构和数据两方面分析，并给出工程上的补救方案。

---

## 五、参考答案与解析

### Q1 — 答案：C

对齐阶段冻结视觉编码器和 LLM，只用图文描述对训练 projector，让它学会"把视觉空间映射进语言空间"。projector 很小，训练便宜，承担了模态桥接的主要工作。D 是第 2 阶段（预训练）的做法；A、B 不是标准流程。

### Q2 — 答案：C

普通做法只投影 ViT 最后一层；DeepStack 取多个深度的特征。深层特征携带高层语义（"这是一张图表"），浅层特征携带细粒度空间和纹理（"x=120 处的柱子是红色的"），两者结合缩小了"有什么"与"在哪里"之间的差距，对 GUI 智能体操作、密集描述这类需要精确定位的任务尤其有用。

### Q3 — 答案：C

条件是 `conf > 0.8` **且** `sim < 0.25`。A 相似度高，说明有图像依据；B 置信度低，模型自己也不确定，不算"自信地胡说"；C 两个条件都满足；D 的置信度恰好是 0.80，而代码用的是严格大于 `>`，所以**不计入**——这是阈值边界的细节陷阱。

### Q4 — 答案：C

视觉-语言预训练把编码器塑造成"与文本兼容"的空间；ImageNet 监督训练的 ResNet 从未见过文本信号，要接到 LLM 需要更大的 projector 和更多数据。B 错：CNN 的特征图同样可以展平成 token；A、D 不是根本原因。

### Q5 — 答案：C

`_merge` 逐个样本找出 `input_ids[b] == image_token_id` 的位置，数量不等于 `vision_embeds.size(1)` 时直接 `raise ValueError`，提示"batch 中每个样本都必须预先填充到相同数量的图像占位 token"。宁可报错也不静默截断或补零，是因为错位的替换会让模型"看到"错误的视觉内容，而且很难排查。

### Q6 — 答案：D

讲义明确说"大多数 LoRA 微调针对第 3 阶段（指令微调），用一个小的标注数据集"。A、B、C 都是正确描述。

### Q7 — 答案：B

讲义指出当前 VLM 在空间推理基准上只有约 50–60%，低于人类；如果业务依赖"谁在谁上面"，必须重度验证，纯空间任务更好的替代是专门的关键点/姿态估计器、深度模型，或对检测框做几何后处理。A 与事实相反；C、D 没有触及根本问题。

### Q8 — 答案：A

Q-former（BLIP-2 风格）用一组可学习的 query 通过注意力"提取"视觉信息，输出**固定数量**的视觉 token；MLP projector 逐 token 映射，输出 token 数等于 patch 数（D 错）。B 错：Q-former 需要训练；C 错：它不限于视频。

### Q9 — 参考答案

1. 形状：
   - `projected`：`(32, 16, 64)`——`nn.Linear` 只作用于最后一维，前面的 `(B, N)` 维度原样保留；
   - `pooled`：`(32, 64)`——在第 1 维（patch 维）上取平均；
   - logits：`(32, 5)`。
2. 参数量（`nn.Linear(in, out)` 有 `in×out` 个权重 + `out` 个偏置；GELU 没有参数）：
   - `Linear(32, 64)`：32×64 + 64 = 2,112
   - `Linear(64, 64)`：64×64 + 64 = 4,160
   - `head = Linear(64, 5)`：64×5 + 5 = 325
   - 合计 **6,597**。可以用 `sum(p.numel() for p in model.parameters())` 验证。
3. `torch.cat(layers, dim=-1)` 输出 `(4, 16, 96)`（32×3）。送进 projector 时 `vit_dim=96`，即 `Projector(vit_dim=96, llm_dim=64)`。注意：`deepstack_features` 的文档字符串写着"拼接并投影（and project）"，但函数本身只做了拼接，投影需要调用方自己接一个 `Projector`。

### Q10 — 参考答案

**问题**：数据是按类别顺序生成的——前 40 个是类 0、接着 40 个是类 1……最后 40 个（下标 160–199）是类 4。`split = int(0.85 × 200) = 170`，于是：

- 训练集 = 下标 0–169：类 0–3 各 40 个，类 4 **只有 10 个**；
- 验证集 = 下标 170–199：**30 个样本全是类 4**。

**对 `val_acc` 的影响**：验证集只衡量"模型能否认出类 4"，不代表整体准确率。而且同一类的样本只差 0.1 倍的小噪声、又经过 16 个 patch 的平均，模型对这 30 个样本的预测几乎总是相同的，所以 `val_acc` 往往只会是 0.000 或 1.000 这种"全错 / 全对"的跳变值——这本身就是一个"验证集有问题"的警报信号。

**修复**：切分前打乱，或做分层切分：

```python
X, Y = synthetic_vision_class_data()
perm = torch.randperm(len(X), generator=torch.Generator().manual_seed(0))
X, Y = X[perm], Y[perm]
split = int(0.85 * len(X))
x_tr, y_tr = X[:split], Y[:split]
x_va, y_va = X[split:], Y[split:]
```

更稳妥的是按类分层：每类各取 15% 进验证集，保证类分布一致。

### Q11 — 参考答案

1. 逐条判断 `conf > 0.8 且 sim < 0.25`：
   - 第 1 条：sim 0.90 不低 → 否
   - 第 2 条：conf 0.70 不高 → 否
   - 第 3 条：conf 0.90、sim 0.10 → **是**
   - 第 4 条：sim 0.30 ≥ 0.25 → 否

   CMER = 1/4 = **0.25**。

2. 前 4 个"好"文本是图像向量加上很小的噪声后再归一化，相似度接近 1，不会被标记；8 个置信度都大于 0.8。关键在后 4 个"幻觉"文本：它们是与图像独立的随机 32 维单位向量，余弦相似度大致以 0 为中心、标准差约 `1/√32 ≈ 0.18`。所以单个幻觉样本的相似度有约 8% 的概率 ≥ 0.25，从而**不被标记**。按这个概率估算，4 个都被标记（CMER = 0.500）的概率约 72%，只有 3 个被标记（CMER = 0.375）的概率约 25%。具体打印哪个取决于随机种子。

   这也揭示了 CMER 的一个性质：**阈值 + 相似度分布**决定了漏报率。真实 CLIP 嵌入空间里，即使无关的图文对相似度也不一定接近 0，`sim_threshold` 需要在自己的数据上校准。

### Q12 — 参考回答要点

以 Qwen3-VL / LLaVA 风格为例：

1. **图像编码**：图像 `(H, W, 3)` → 切 patch → ViT → patch token `(N, d_vit)`（如 CLIP-L/14、SigLIP、DINOv3）。
2. **投影**：projector（2–4 层 MLP + GELU，或 Q-former）→ `(N, d_llm)`，此后 LLM 把每一行当成一个普通 token。
3. **文本编码**：prompt 经 LLM tokenizer → 文本 embedding `(M, d_llm)`；prompt 中预留 `<image>` 占位 token。
4. **合并**：占位 token 的 embedding 被替换为视觉 embedding（交错或拼接），得到 `inputs_embeds`。
5. **生成**：decoder-only LLM 自回归生成答案。
- 加分点：说明差异主要在"选哪个 ViT、哪种 projector、哪个 LLM、训练数据和对齐配方"，理解模式后替换任一组件都是机械性的；提到生产中 `processor.apply_chat_template` 隐藏了占位符的处理，模型内部完成合并。

### Q13 — 参考回答要点

- **为什么先只训 projector**：
  - ViT 和 LLM 都是昂贵的预训练成果，直接解冻在小规模图文对上训练，容易破坏已有能力（灾难性遗忘）；
  - projector 很小，训练便宜，先让它学会"翻译"两种表示空间；
  - 先对齐、再解冻全部做大规模预训练、最后指令微调，是现代 VLM 的标准三阶段流程。
- **MLP vs Q-former**：

| | MLP projector | Q-former |
|---|---|---|
| 输出 token 数 | 等于 patch 数，随分辨率增长 | 固定数量的 query token |
| 信息保留 | 逐 patch 映射，信息损失小 | 压缩到固定数量，可能丢细节 |
| 计算 | 简单、便宜 | 多一组注意力层，结构更复杂 |
| 对 LLM 上下文的压力 | 高分辨率时 token 多 | 可控 |

- 常见误区：认为 projector 只是"维度变换"无关紧要——讲义指出微调主要就发生在这里。

### Q14 — 参考回答要点

- **根因**：爬取数据中约 12% 的图文对描述并不完全基于图像，模型在训练中"学会了"幻觉——编造物体、读错数字、虚构关系，这是生产中的主要失效模式。
- **监控**：
  - 每个请求计算：文本置信度（逐 token 概率的平均，必须是概率而非原始 logits）+ 用**独立的** CLIP 系模型计算生成文本与图像的相似度；
  - 标记"高置信 + 低相似"，按时间窗聚合成 CMER；按 endpoint、prompt 类型、客户、模型版本分别看；
  - 记录原始 `sim` 值而不只是标记位，分布漂移会先在低分位体现。
- **治理**：讲义的思路是"不是去修模型，而是把高 CMER 的输出转人工审核"；据讲义，Skywork.ai 把 CMER 当作 KPI 后幻觉率下降约 35%。持续升高时检查输入分布变化，再考虑微调或换模型。
- **CMER 的局限**：
  - 检查器本身有偏差（CLIP 对计数、空间关系不敏感）；
  - "Yes / No / 3" 这类短答案与图像的相似度天然很低，容易误报，需要按 prompt 类型分别设阈值；
  - 只能发现"不相关"，发现不了"相关但细节错误"（如数字读错）；
  - 阈值需要在业务数据上校准。

### Q15 — 参考回答要点

- **三条路线**（讲义 Use It）：
  - 托管 API（OpenAI / Anthropic / Google 的视觉接口）：零基础设施，适合快速验证，但有供应商风险和数据出域问题；
  - 开源自部署（Qwen3-VL、InternVL3.5，通过 `transformers` / `vllm`）：完全可控，前期投入大；
  - 领域微调（如 Qwen2.5-VL-7B 或 LLaVA-1.6-7B + LoRA，用 `vllm` 或 TGI 服务）。
- **建议方案**：先用 API 或开源模型零样本跑一批真实图片，人工打分（正确 / 部分正确 / 幻觉），确定基线；缺陷类别专业、零样本不达标时做 LoRA。
- **成本参考（讲义数字）**：LoRA rank 16–64 加在 attention + projector 上，或 QLoRA 4-bit 底座，单张 A100/H100；5k–50k 样本，100–5,000 美元算力，训练 2–10 小时。
- **上线**：接入 CMER 监控；缺陷判定涉及"位置/大小"时不要只靠 VLM，结合检测或分割模型输出几何信息；高风险判定走人工复核。
- 加分点：数据一定按产线、时间分层切分评测集，避免同一批次图片同时出现在训练和测试中。

### Q16 — 参考回答要点

- **现状**：讲义给出的数字是当前 VLM 在空间推理基准（上下、左右、计数、距离）上约 50–60%，低于人类。
- **架构原因**：
  - 只用 ViT 最后一层特征时，高层语义强但精确位置信息弱——这正是 DeepStack 引入浅层特征想补的东西；
  - Q-former 类压缩到固定 token 数时会丢细节；
  - 图像 patch 被摊平成一维序列，二维空间关系要靠位置编码和学习来恢复。
- **数据原因**：图文描述中很少有精确的空间关系和计数，且有不少描述本身就不基于图像。
- **补救**：
  - 用专门模型做纯空间任务：检测模型 + 框几何后处理（比较 y 坐标判断上下）、深度模型（远近）、关键点/姿态模型；
  - VLM 负责语义理解和最终的自然语言回答，几何事实由专用模型提供（工具调用 / 结构化输入）；
  - 选用多层特征融合的模型、或在空间类数据上做指令微调，并重度验证。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 14 Vision Transformers (ViT)](../../14-vision-transformers/docs/zh.md)：patch token 的由来。
- [阶段 04 · 18 开放词表视觉——CLIP](../../18-open-vocab-clip/docs/zh.md)：图文共享 embedding 空间，VLM 视觉编码器的主要来源。
- [阶段 07 · 02 从零实现 Self-Attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：LLM 如何把视觉 token 与文本 token 一起处理。

### 本节被哪些后续内容用到
- [阶段 12 · 03 BLIP-2 与 Q-Former](../../../12-multimodal-ai/03-blip2-qformer-bridge/docs/zh.md)：本节提到的固定数量 token 桥接方案的完整展开。
- [阶段 12 · 05 LLaVA 视觉指令微调](../../../12-multimodal-ai/05-llava-visual-instruction-tuning/docs/zh.md)：ViT-MLP-LLM 模式与指令微调的代表作。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率](../../../12-multimodal-ai/09-qwen-vl-family-dynamic-fps/docs/zh.md)：Qwen 系 VLM 的视频与时间建模。
- [阶段 12 · 10 InternVL3](../../../12-multimodal-ai/10-internvl3-native-multimodal/docs/zh.md)：另一条主流开源 VLM 路线。
- [阶段 12 · 25 多模态智能体与 Computer Use](../../../12-multimodal-ai/25-multimodal-agents-computer-use/docs/zh.md)：OSWorld 这类"会点击的 VLM"。
- [阶段 11 · 08 LoRA 微调](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：VLM 领域微调使用的 LoRA / QLoRA。
- [阶段 19 · 60 投影层与模态对齐](../../../19-capstone-projects/60-projection-layer-modality-align/docs/zh.md)：从零实现 projector 的实战项目。
- [阶段 04 · 26 单目深度](../../26-monocular-depth/docs/zh.md)：补足 VLM 空间推理短板的专用模型之一。

### 延伸关键词
`SigLIP` · `DINOv3` · `Q-Former` · `DeepStack` · `T-RoPE` · `MMMU / MMBench / DocVQA / ChartQA / MathVista` · `OSWorld` · `CMER` · `QLoRA` · `vLLM`
