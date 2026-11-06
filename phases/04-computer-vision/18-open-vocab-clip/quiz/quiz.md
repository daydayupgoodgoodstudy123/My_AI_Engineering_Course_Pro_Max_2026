# 测验 · 开放词表（Open-Vocabulary）视觉——CLIP（Open-Vocabulary Vision — CLIP）

> **阶段 04 · 计算机视觉 · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 封闭词表 vs 开放词表 | 传统分类器只能输出训练时固定的 C 个类别；CLIP 用一句自然语言就能"新增"一个类别，无需标注和重训 |
| 2 | 双塔（two-tower / dual encoder） | 图像编码器与文本编码器各自独立，最后都用线性投影映射到同一维度，L2 归一化后用余弦相似度比较 |
| 3 | 对比学习目标 | 一个 batch 的 N 对 (图, 文) 构成 N×N 相似度矩阵，让对角线高、非对角线低；本质是以 `arange(N)` 为标签的交叉熵 |
| 4 | 对称损失 | `loss = (CE(sim) + CE(simᵀ)) / 2`，同时训练"图找文"和"文找图"两个方向 |
| 5 | 温度 / logit_scale | 相似度先乘以 `1/τ` 再做 softmax；τ 是可学习标量，初始化为 0.07，即 `logit_scale = ln(1/0.07) ≈ 2.6592`，乘子 ≈ 14.3 |
| 6 | SigLIP | 把 batch 级 softmax 换成逐对 sigmoid：`log(1 + exp(-yᵢⱼ·simᵢⱼ))`，不依赖整批归一化，小 batch 下训练更好 |
| 7 | Zero-shot 分类 | 为每个类写 prompt → 文本编码得 `T (C,d)` → 图像编码得 `I (1,d)` → `I @ Tᵀ` → argmax |
| 8 | Prompt 模板集成 | 用多个模板（"a photo of a {}"、"a sketch of a {}"……）分别编码后取平均，作为类别"质心"，可提升约 1–3% top-1 |
| 9 | CLIP 家族的下游用途 | 检索、文本条件检测（Grounding DINO、OWL-ViT）、文本条件分割（CLIPSeg）、VLM 的视觉塔、文生图的文本条件 |

### 核心技能（能动手做到）

- [ ] 用 PyTorch 写出一个双塔模型：两个投影头 + `F.normalize` + 可学习的 `logit_scale`，并说清 `logit_scale.exp()` 为什么约等于 14.3
- [ ] 不看讲义写出对称 CLIP 损失 `clip_loss`，并能解释 `targets = torch.arange(N)` 的含义
- [ ] 写出 zero-shot 分类函数：编码 → 相似度矩阵 → argmax → 映射回类名，并能说出每一步张量的形状
- [ ] 能推导"随机初始化时损失约为 log N"的来历，并解释为什么实际值往往**高于** log N
- [ ] 能分析 batch 内同类样本（假负例）导致损失有下界，并估算本节合成数据的损失下界
- [ ] 能把 `clip_loss` 改写成 SigLIP 的逐对 sigmoid 损失（含可学习 bias）
- [ ] 能用 OpenCLIP / Hugging Face 的预训练 CLIP 完成 zero-shot 分类，并实现多模板平均

---

## 二、基础自测（选择题）

**Q1.** 一个已经训练好的 ImageNet-1k 分类器和一个 CLIP 模型，都要新增一个类别"电动滑板车"。下列说法最准确的是：

- A. 两者都必须收集带标签的数据并重训分类头
- B. CLIP 只需写一句 prompt（如 "a photo of an electric scooter"）编码成文本向量，加入类别向量矩阵即可；ImageNet 分类器需要新数据和新的分类头
- C. CLIP 需要用新类别的图片微调图像编码器
- D. ImageNet 分类器可以直接把新类别名作为第 1001 个输出

**Q2.** 代码中 `self.logit_scale = nn.Parameter(torch.ones([]) * 2.6592)`，前向时返回 `self.logit_scale.exp()`。这个设计的含义是：

- A. 温度 τ = 2.6592，相似度除以 2.6592
- B. 温度 τ = 0.07，相似度被乘以约 14.3；在对数空间参数化，保证乘子恒为正，且学习更平稳
- C. 这是学习率的初始值
- D. 这是给相似度加的偏置项

**Q3.** CLIP 的损失对 `sim` 和 `sim.T` 各做一次交叉熵再取平均，主要原因是：

- A. PyTorch 的 `cross_entropy` 要求输入是对称矩阵
- B. 为了让总损失恒为正
- C. 下游既要"文找图"（如 zero-shot 分类、以文搜图），也要"图找文"；只训练一个方向，另一个方向的检索效果会明显变差
- D. 为了让梯度只流向图像编码器

**Q4.** SigLIP 用逐对 sigmoid 替代 CLIP 的 batch 级 softmax，最核心的好处是：

- A. 只在 COCO 数据集上有效
- B. 每一对 (图, 文) 独立做"匹配 / 不匹配"的二分类，损失不再依赖整批样本做归一化分母，因此小 batch 也能训练好
- C. sigmoid 比 softmax 的 GPU kernel 快很多，这是唯一优势
- D. 不再需要负样本

**Q5.** 一个随机初始化的双塔模型（`logit_scale = ln(1/0.07)`）在 batch = 8 的随机数据上计算 `clip_loss`。下列说法正确的是：

- A. 损失一定精确等于 `log(8) ≈ 2.079`
- B. `log(8)` 是"每行 logits 全相等"时的交叉熵；对随机 embedding，按目标位置取期望时损失 ≥ `log(8)`，logits 的随机波动越大（如 logit_scale 越大）偏离越多
- C. 损失一定小于 `log(8)`，因为对角线上的配对天然更相似
- D. 损失与 `logit_scale` 无关，因为向量已经归一化

**Q6.** 用 80 个 prompt 模板做 zero-shot 分类时，讲义推荐的做法是：

- A. 把 80 个模板拼接成一句长文本，一次性编码
- B. 每个模板分别编码并 L2 归一化，按类别求平均（通常再归一化一次），每个类得到一个"质心"文本向量
- C. 只保留验证集上效果最好的那一个模板
- D. 每个模板单独做一次 argmax，最后对 80 个预测结果投票

**Q7.** 根据讲义，下列哪一项**不是**建立在 CLIP 式图文联合 embedding 之上的典型应用？

- A. Grounding DINO / OWL-ViT 这类"用文字指定要检测什么"的检测器
- B. LLaVA、Qwen-VL、InternVL 等 VLM 的视觉编码器
- C. Stable Diffusion 用文本 embedding 作为生成条件
- D. 只输出固定 80 个 COCO 类别的封闭集检测头

---

## 三、动手 / 代码题

**Q8.** 阅读本节 `main.py` 的以下片段，回答问题：

```python
class TwoTower(nn.Module):
    def __init__(self, img_in=128, txt_in=64, emb=64):
        super().__init__()
        self.image_proj = nn.Sequential(nn.Linear(img_in, 128), nn.ReLU(), nn.Linear(128, emb))
        self.text_proj = nn.Sequential(nn.Linear(txt_in, 128), nn.ReLU(), nn.Linear(128, emb))
        self.logit_scale = nn.Parameter(torch.ones([]) * 2.6592)
# ...
    class_text = torch.zeros(num_classes, 64)
    class_text[:, :dim] = proto
    test_img, _, test_labels = sample_pair_batch(batch=16)
    class_names = [f"class_{c}" for c in range(num_classes)]
    preds = zero_shot_classify(model, test_img, class_text, class_names)
```

1. 刚构造完的模型，`model(img, txt)` 返回的第三个值大约是多少？
2. 在 `zero_shot_classify` 内部，`i`、`t`、`sim`、`pred` 的形状分别是什么？（`num_classes = 5`、`dim = 32`）
3. 训练时文本特征的第 32–63 维是 `N(0,1)` 噪声，而这里 `class_text` 的第 32–63 维全是 0，为什么分类仍然能工作？这和讲义里的"多模板平均"有什么相似之处？

**Q9.** `main()` 第二段用 5 个类别的合成数据训练，batch = 32：

```python
    def sample_pair_batch(batch=32):
        labels = torch.randint(0, num_classes, (batch,))
        img = torch.randn(batch, 128)
        txt = torch.randn(batch, 64)
        img[:, :dim] = proto[labels] + 0.1 * torch.randn(batch, dim)
        txt[:, :dim] = proto[labels] + 0.1 * torch.randn(batch, dim)
        return img, txt, labels
```

有同学训练很多步后发现 `clip_loss` 始终降不到 0，认为是模型容量不够。请指出真正的原因，估算损失的理论下界（量级即可），并给出一种让损失能继续下降的改法。

**Q10.** 按讲义的 SigLIP 公式 `loss = mean(log(1 + exp(-yᵢⱼ · simᵢⱼ)))`（匹配对 y = +1，其他 y = -1），写一个可以直接替换 `clip_loss` 的函数 `siglip_loss(i, t, logit_scale, logit_bias)`，要求数值稳定；并说明需要给 `TwoTower` 增加什么参数。

---

## 四、面试高频题

**Q11.**（基础必考）讲一下 CLIP 是怎么训练的：模型结构、损失函数、温度参数分别起什么作用？为什么 CLIP 需要非常大的 batch？

**Q12.**（原理深挖）CLIP 的 softmax 对比损失和 SigLIP 的 sigmoid 损失有什么本质区别？在多卡分布式训练里，两者的通信与显存开销有什么不同？SigLIP 为什么还需要一个可学习的 bias？

**Q13.**（工程实践）你用开源 CLIP 在公司的工业质检图片上做 zero-shot 分类，准确率只有 40%。你会按什么顺序排查和改进？

**Q14.**（场景设计）设计一个"以文搜图"系统：图库 1 亿张图片，用户输入一句自然语言，200 ms 内返回 Top-20。说说离线、在线两部分怎么做。

**Q15.**（追问型）CLIP 在"数数""左右空间关系""否定句"（如 "a dog without a collar"）上经常出错，为什么？这和它的训练目标有什么关系？工业界一般怎么弥补？

---

## 五、参考答案与解析

### Q1 — 答案：B

开放词表的核心就是"类别由文本定义"。CLIP 的 zero-shot 分类器其实就是一个**由文本编码器即时生成权重的线性分类头**：每个类别的文本向量就是该类的权重行。新增类别 = 新增一行权重，只需编码一句 prompt。A、C 描述的是封闭词表或微调的做法；D 错在 ImageNet 分类器的输出层是固定的 1000 维线性层，没有"类名"这个输入通道。

### Q2 — 答案：B

`ln(1/0.07) = 2.6593`，`exp(2.6592) ≈ 14.28`，即相似度矩阵乘以 `1/τ ≈ 14.3`。在对数空间存参数有两个好处：①`exp` 保证乘子始终为正；②参数的加性更新对应乘子的乘性变化，学习更平稳。余弦相似度只在 [-1, 1]，不放大的话 softmax 几乎是均匀分布，梯度很弱，所以必须有温度。

### Q3 — 答案：C

`CE(sim)` 是"每张图在 N 段文字里找到自己的配对"，`CE(simᵀ)` 是"每段文字在 N 张图里找配对"。zero-shot 分类和以文搜图属于文本查询图像（或图像在文本集合里选类别），以图搜文则相反，两个方向都要好用。A 错，交叉熵对输入形状没有对称性要求；B 错，交叉熵本来就非负；D 错，两个方向的梯度都会流向两座塔。

### Q4 — 答案：B

CLIP 的每一行 softmax 分母包含整个 batch，有效负样本数 = N-1，batch 小时负样本"不够吃"，而且必须拿到全局 batch 的所有 embedding 才能算分母。SigLIP 把每一对独立看成二分类，损失可以分块累加，不需要全局归一化，因此小 batch 下表现更好，相同数据规模时可以持平或超过 CLIP。C 错在"唯一优势"——它的主要价值在训练动态和可扩展性；D 错，SigLIP 依然使用所有非对角对作为负样本（y = -1）。

### Q5 — 答案：B

对某一行 logits `z`，目标为 j 时损失为 `logsumexp(z) - zⱼ`。对 j 取平均得到 `logsumexp(z) - mean(z)`，由 Jensen 不等式 `logsumexp(z) ≥ log N + mean(z)`，等号仅在 `z` 全相等时成立。随机初始化时对角线并不比其他位置特殊，所以**期望损失 ≥ log N**，logits 波动越大越高。本节 `logit_scale` 初始就把余弦放大约 14.3 倍，随机余弦的小波动会被放大成明显的 logit 差异，因此实际打印值往往高于 2.079（用 NumPy 按 PyTorch 默认初始化方式模拟 200 次：均值约 2.9，范围约 1.9–4.0）。C 错在对角线并不"天然"更相似；D 错在温度直接缩放 logits。

### Q6 — 答案：B

讲义的做法是"Average the embeddings of all templates per class"：对每个模板分别编码，归一化后对同一类求平均，得到更稳健的类别质心，再与图像向量算余弦。A 改变了文本分布（训练时没见过这么长、这么怪的句子），还可能超出 77 token 上限；C 浪费了模板之间的互补性；D 计算量是 80 倍，且投票丢掉了分数信息，效果通常不如在 embedding 空间平均。

### Q7 — 答案：D

讲义列出的 CLIP 家族应用包括：zero-shot 分类、检索、文本条件检测（Grounding DINO、OWL-ViT）、文本条件分割（CLIPSeg）、VLM 视觉塔（LLaVA、Qwen-VL、InternVL）、文生图的文本条件（Stable Diffusion）。只输出固定 80 类的检测头是典型的**封闭词表**模型，与图文联合空间无关。

### Q8 — 参考答案

1. `exp(2.6592) ≈ 14.28`（即 `1/0.07`）。它是一个 0 维标量张量，因为 `torch.ones([])` 的形状是 `[]`。
2. `test_img` 为 `(16, 128)`，`class_text` 为 `(5, 64)`：
   - `i = model.encode_image(test_img)` → `(16, 64)`，每行 L2 范数为 1；
   - `t = model.encode_text(class_text)` → `(5, 64)`；
   - `sim = i @ t.T` → `(16, 5)`，第 (n, c) 个元素是第 n 张图与第 c 个类别的余弦相似度；
   - `pred = sim.argmax(dim=-1)` → `(16,)` 的整数张量，经 `.tolist()` 映射为 16 个类名字符串。
   - 注意这里**没有乘 logit_scale**：argmax 对正的缩放不敏感，只有需要概率时才乘温度再 softmax。
3. 训练时文本第 32–63 维是与配对无关的纯噪声，期望为 0。`class_text` 把这部分设为 0、前 32 维设为不带噪声的 `proto`，相当于给出了该类文本特征的**期望值 / 质心**。只要文本塔学到了"主要看前 32 维、忽略噪声维"，质心输入就会落在该类训练文本 embedding 的中心附近。这与多模板平均是同一个思想：用"去掉了个别表述噪声的类中心"来代表类别。（严格说 MLP 是非线性的，`f(E[x]) ≠ E[f(x)]`，真实 CLIP 也是在 embedding 空间而不是输入空间求平均。）

### Q9 — 参考答案

**原因：batch 内的"假负例"（false negatives）。** 5 个类、batch 32，平均每类约 6.4 个样本。同一类的图像 a 与文本 b 都等于 `proto[c] + 独立噪声`，图像第 32–127 维、文本第 32–63 维也是互相独立的噪声——除了类别，**没有任何信息能把图 a 和它"自己的"文本 a 区分于同类的其他文本**。可是 `clip_loss` 的目标是 `arange(N)`，只承认对角线是正例，同类其他样本都被当成负例。

**下界估算：** 对属于类 c 的图像，贝叶斯最优的预测是把概率平均分给本类的 `n_c` 段文本，此时交叉熵 = `log(n_c)`。图像自身所属类在 batch 中的样本数 `n_c = 1 + Binomial(31, 0.2)`，`E[log n_c] ≈ 1.92`（对比初始量级 `log 32 ≈ 3.47`）。两个方向对称，所以平均损失的下界约 1.9，再怎么增加容量都降不下去。

**改法（任选其一）：**

- 采样时让一个 batch 内类别不重复（本例最多 5 对，则下界变为 0）；
- 使用"标签感知"的多正例目标（SupCon 风格）：把同类位置都当正例，例如 `targets = (labels[:,None] == labels[None,:]).float()`，再归一化成软标签做交叉熵；
- 真实 CLIP 不会有这个问题吗？也会有，但网页图文对几乎都"独一无二"，同义重复的比例很低，影响远小于本例。

### Q10 — 参考答案

```python
import torch
import torch.nn.functional as F


def siglip_loss(i, t, logit_scale, logit_bias):
    # i, t: (N, d) 已 L2 归一化；logit_scale 已经是 exp 之后的正数
    N = i.size(0)
    logits = logit_scale * i @ t.T + logit_bias              # (N, N)
    labels = 2 * torch.eye(N, device=logits.device) - 1      # 对角 +1，其余 -1
    return F.softplus(-labels * logits).mean()               # log(1 + exp(-y·z))
```

要点：

- `F.softplus(x) = log(1 + exp(x))`，内部做了数值稳定处理；直接写 `torch.log(1 + torch.exp(-y*z))` 在 `-y*z` 很大时会溢出成 `inf`。等价写法是 `-F.logsigmoid(labels * logits).mean()`。
- 需要给 `TwoTower` 增加一个可学习标量 `self.logit_bias = nn.Parameter(torch.zeros([]))`（SigLIP 论文初始化为 -10，同时把温度乘子初始化为 10），并让 `forward` 一并返回。原因：N×N 矩阵里只有 N 个正例、N²-N 个负例，严重不平衡；负的 bias 让一开始所有对都"倾向于不匹配"，避免训练初期被大量负例的梯度主导。
- 讲义写的是"对所有对取平均"（除以 N²），论文是对所有对求和后除以 N；两者只差一个常数倍，相当于学习率缩放。

### Q11 — 参考回答要点

- **结构**：双塔——图像编码器（ViT 或 ResNet）+ 文本编码器（Transformer），各接一个线性投影到同一维度（如 CLIP ViT-B/32 为 512 维），L2 归一化后点积即余弦相似度。
- **损失**：一个 batch 的 N 对构成 N×N 相似度矩阵，以 `arange(N)` 为标签分别对行和列做交叉熵再平均，即对称的 InfoNCE。直觉：每张图要在 N 段文字中"认出"自己的描述，反之亦然。
- **温度**：余弦值在 [-1, 1]，范围太窄，softmax 太"平"。乘以 `1/τ` 拉开差距；τ 可学习、在对数空间参数化，初始化 0.07。温度太高 → 区分度不够；太低 → softmax 过尖、训练不稳定。
- **为什么要大 batch**：每个正例的负例数 = N-1，负例越多，对比任务越难、学到的特征越细；CLIP 原论文用的是 32k 量级的 batch。
- **加分点**：CLIP 论文还会把温度乘子截断在 100 以内防止不稳定；多卡训练时要 all-gather 各卡的 embedding 才能构成全局相似度矩阵；能说出"zero-shot 分类器 = 由文本塔生成权重的线性头"。
- **常见误区**：以为 CLIP 是"图像描述生成模型"——它只学对齐，不生成文字。

### Q12 — 参考回答要点

- **本质区别**：CLIP 每一行做 softmax，是"N 选 1"的多分类，分母依赖整批；SigLIP 每个格子独立做 sigmoid 二分类，`log(1 + exp(-y·z))`，没有跨样本的归一化。
- **分布式开销**：CLIP 要算全局 softmax，需要 all-gather 所有卡的 embedding 并构造完整的全局相似度矩阵（显存随全局 batch 平方增长）；SigLIP 的损失是逐对可加的，可以分块计算（例如各卡轮流交换文本 embedding 块，逐块累加损失），不必一次物化全局矩阵，更省显存、更容易扩到大 batch。
- **小 batch 表现**：讲义结论——SigLIP 在小 batch 下训练更好，相同数据下与 CLIP 持平或更优。
- **为什么要 bias**：N² 个格子里只有 N 个正例，正负极不平衡。不加 bias，初始化时所有 logit≈0，sigmoid≈0.5，海量负例的梯度会主导训练；加一个初始为较大负数（论文用 -10）的可学习 bias，相当于先验"绝大多数对不匹配"。
- **加分点**：SigLIP 系列常被用作新一代 VLM 的视觉塔（讲义也说新工作优先选 SigLIP）。

### Q13 — 参考回答要点

1. **先查数据与评测**：类别定义是否清晰、标签是否有噪声；看混淆矩阵，确认是全面差还是集中在几对相似类。
2. **Prompt 工程（零训练成本）**：类名改写成领域里的自然描述（如 "a scratch on a metal surface" 而非 "defect_type_3"）；加领域模板（"industrial inspection image of a {}"）；多模板平均；类名统一小写、避免缩写。
3. **换更合适的 checkpoint**：更大的模型（ViT-L 及以上）、SigLIP、或在相近领域数据上训练过的 CLIP 变体。
4. **少量标注 + 轻量适配**：在冻结的 CLIP 图像特征上训练 linear probe（几十到几百张/类往往就大幅超过 zero-shot）；也可用文本向量初始化分类头再微调。
5. **全量或部分微调**：数据足够时小学习率微调图像塔，注意保留通用能力（冻结前几层、混入通用数据）。
- **核心判断**：工业质检属于明显的分布外领域（网页图文对里很少见），zero-shot 只是起点；"文本定义类别"的价值在冷启动和长尾，不在追求最高精度。
- **常见误区**：一上来就全量微调，忘了先做 linear probe 基线；以为模板越多越好（讲义提到约 80 个之后收益递减）。

### Q14 — 参考回答要点

- **离线**：用 CLIP / SigLIP 图像塔批量编码 1 亿张图（GPU 批处理、fp16），L2 归一化后入向量库；元数据（URL、时间、标签）单独存储。
- **索引选型**：1 亿 × 512 维 float32 ≈ 200 GB，必须压缩 + 近似最近邻（ANN）：IVF + PQ、HNSW 或其变体，必要时分片；归一化后内积 = 余弦。
- **在线**：文本塔编码查询（可缓存高频查询）→ ANN 召回 Top-K（如 1000）→ 可选：用更强的模型或精确向量重排 → 业务过滤（安全、去重、权限）→ 返回 Top-20。
- **延迟预算**：文本编码约十毫秒级（GPU）、ANN 检索十毫秒级、重排视模型而定；文本塔可蒸馏小模型或用 ONNX/TensorRT 加速。
- **增量与一致性**：新图片增量编码追加入索引；**换模型必须全量重算**，因为不同 checkpoint 的 embedding 空间不兼容。
- **评测**：人工写查询集，看 Recall@K / nDCG（见第 20 节），线上看点击率。
- **加分点**：中文查询要用多语言 CLIP 或先翻译；可以加"以图搜图"复用同一索引。

### Q15 — 参考回答要点

- **现象**：CLIP 擅长"有什么"，不擅长"有几个、在哪儿、是不是没有"。
- **原因**：对比学习只要求在 batch 里把正确配对挑出来。随机 batch 里的负例描述通常与正例差别很大（不同物体、不同场景），只要识别出关键名词就能区分，模型就没有动力去理解词序、数量和否定——表现得像"词袋（bag-of-words）"。网页 caption 本身也很少精确描述数量和空间关系。
- **工业界弥补**：
  - 训练端：构造**困难负例**（打乱词序、替换数量/介词、否定改写）加入对比训练；用更精细的长描述（重新生成的 caption）训练。
  - 架构端：把 CLIP 当视觉塔接到 LLM 上做 VLM（第 25 节），由语言模型完成组合推理；检测/分割任务用 Grounding DINO 这类带定位能力的模型。
  - 应用端：需要计数/空间判断时不要只依赖 CLIP 相似度，改用检测器 + 规则，或 VLM 问答。
- **加分点**：能举出 zero-shot 中的另一个坑——类名歧义（如 "crane" 既是鹤也是起重机），需要用模板补充上位词（"a photo of a crane, a type of bird"）。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 14 Vision Transformers (ViT)](../../14-vision-transformers/docs/zh.md)：真实 CLIP 的图像塔就是 ViT（如 ViT-B/32、ViT-L/14）。
- [阶段 04 · 17 自监督视觉 — SimCLR、DINO、MAE](../../17-self-supervised-vision/docs/zh.md)：SimCLR 的 InfoNCE 与 CLIP 损失同源，区别是正例来自同一图像的两个增强视图还是图文配对。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：余弦相似度、L2 归一化。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵、softmax 与 sigmoid 损失。

### 本节被哪些后续内容用到
- [阶段 04 · 20 图像检索和度量学习](../../20-image-retrieval-metric/docs/zh.md)：CLIP embedding 直接用于检索，Recall@K 评估。
- [阶段 04 · 24 SAM 3 与开放词表分割](../../24-sam3-open-vocab-segmentation/docs/zh.md)：把"文本定义类别"从分类推广到分割。
- [阶段 04 · 25 Vision-Language Models](../../25-vision-language-models/docs/zh.md)：CLIP/SigLIP 视觉塔 + MLP + LLM 的 VLM 范式。
- [阶段 04 · 11 Stable Diffusion](../../11-stable-diffusion/docs/zh.md)：用 CLIP 文本编码器作为生成条件。
- [阶段 12 · 02 CLIP 对比预训练](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：在多模态阶段更深入地展开 CLIP 预训练。
- [阶段 08 · 14 评估：FID 与 CLIP Score](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：用 CLIP 相似度评估文生图的图文一致性。
- [阶段 12 · 24 跨模态多模态 RAG](../../../12-multimodal-ai/24-multimodal-rag-cross-modal/docs/zh.md)：图文共享空间是跨模态检索的基础。

### 延伸关键词
`InfoNCE` · `OpenCLIP / LAION` · `SigLIP / SigLIP 2` · `prompt ensembling` · `linear probe` · `false negatives in contrastive learning` · `hard negatives` · `FAISS (IndexFlatIP / IVF / HNSW)` · `CLIPSeg` · `OWL-ViT / Grounding DINO`
