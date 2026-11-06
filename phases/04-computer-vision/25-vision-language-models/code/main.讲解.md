# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 25 节 Vision-Language Models — ViT-MLP-LLM 模式 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`torch`（`torch.nn`、`torch.nn.functional`）；CPU 即可，不加载任何预训练 ViT 或 LLM，无需联网

---

## 1. 这份代码在考察什么

真实 VLM 动辄几十亿参数，没法在课堂上训练。这份代码把 ViT-MLP-LLM 模式里**最常被训练、也最值得理解的那一段**单独拎出来，用合成数据跑通：

1. **Projector 的形态**：2 层 MLP + GELU，把 `d_vit` 维的视觉 token 映射到 `d_llm` 维，逐 token 作用、不改变 token 数。
2. **"只训 projector 也能学会"**：用"假 ViT 特征"训练 projector + 一个分类头，几十步内就能把 5 类分开，对应讲义"对齐阶段只训 projector"的思想。
3. **DeepStack 的直觉**：多个 ViT 深度的特征沿通道维拼接，维度变成 `层数 × d`。
4. **CMER（Cross-Modal Error Rate，跨模态错误率）**：用"高置信 + 低图文相似度"的比例来量化幻觉，并用模拟数据验证它能抓到"幻觉"样本。

> 一句话：**VLM 的"桥"就是一个小 MLP，幻觉监控就是一个余弦相似度 + 两个阈值**——这份代码把两者都拆到最小可运行的形态。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Projector` | `nn.Module` | `Linear → GELU → Linear`，`d_vit → d_llm` | ViT-MLP-LLM 中的 MLP（"桥"） |
| `ToyVLM` | `nn.Module` | projector + 对 patch 维做 mean pooling + 线性分类头 | 用分类头代替 LLM 的"玩具 VLM" |
| `cross_modal_error_rate(...)` | 函数 | 归一化 → 余弦相似度 → 高置信且低相似的比例 | CMER 幻觉 KPI |
| `deepstack_features(per_layer_features)` | 函数 | 多层特征沿最后一维拼接 | DeepStack 多层特征 |
| `synthetic_vision_class_data(...)` | 函数 | 每类一个原型向量 + 小噪声，复制成 16 个 patch | 假的 ViT patch 特征 |
| `main()` | 演示入口 | 训练 ToyVLM → 演示 DeepStack 形状 → 模拟 CMER | — |

数据流：`synthetic_vision_class_data` 产出 `(200, 16, 32)` 的"视觉 token" → `ToyVLM` 中 projector 映射到 `(…, 16, 64)` → 平均池化成 `(…, 64)` → 分类头输出 5 类 logits → 交叉熵训练。DeepStack 和 CMER 是两段独立演示。

---

## 3. 逐段精讲

### 3.1 `Projector`：VLM 的"桥"

```python
class Projector(nn.Module):
    def __init__(self, vit_dim=32, llm_dim=64, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(vit_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, llm_dim),
        )

    def forward(self, x):
        return self.net(x)
```

- 结构和讲义 Step 1 完全一致，只是维度从真实的 `768 → 4096 → 4096` 缩小到 `32 → 64 → 64`，方便在 CPU 上秒级跑完。
- `nn.Linear` **只作用在最后一维**：输入 `(B, N_patches, d_vit)`，输出 `(B, N_patches, d_llm)`。每个 patch 独立映射，token 数不变——这就是 MLP projector 和 Q-former（输出固定数量 query token）的本质区别。
- 为什么用 GELU：它是 Transformer 系模型的标准激活，平滑、在 0 附近有非零梯度；中间必须有非线性，否则两层 Linear 等价于一层线性变换。
- `nn.Sequential` 把多层按顺序串起来，`forward` 一行搞定。
- ⚠️ 简化：真实 VLM 的 projector 是 2–4 层；有些模型还会在投影前做 token 合并（如把相邻 2×2 patch 拼起来）来减少 token 数，这里没有体现。

### 3.2 `ToyVLM`：用分类头代替 LLM

```python
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

- 形状变化：`(B, 16, 32)` →（projector）→ `(B, 16, 64)` →（`mean(dim=1)`，在 patch 维平均）→ `(B, 64)` →（head）→ `(B, 5)`。
- 参数量：`Linear(32,64)` 2,112 + `Linear(64,64)` 4,160 + `Linear(64,5)` 325 = **6,597**。
- **为什么这样设计**：真实 VLM 中，projector 的输出会被当成 token 送进 LLM，再由 LLM 生成文本。这里用"平均池化 + 线性分类头"代替 LLM，目的是只验证一件事——**projector 能被梯度训练出有用的映射**。讲义原话："Fake 'ViT features' go in; a tiny LLM-style token predicts a class."
- ⚠️ 简化：没有文本 token、没有 `<image>` 占位符替换、没有自回归生成；讲义 Step 2 的 `MinimalVLM._merge` 才展示了占位符替换的真实做法（本文件没有包含那段代码）。

### 3.3 合成数据：每类一个"原型"

```python
def synthetic_vision_class_data(num_classes=5, num_patches=16, d_vit=32, per_class=40, seed=0):
    g = torch.Generator().manual_seed(seed)
    proto = torch.randn(num_classes, d_vit, generator=g)
    X = []
    Y = []
    for c in range(num_classes):
        for _ in range(per_class):
            base = proto[c].unsqueeze(0).expand(num_patches, -1)
            noise = 0.1 * torch.randn(num_patches, d_vit, generator=g)
            X.append(base + noise)
            Y.append(c)
    return torch.stack(X), torch.tensor(Y)
```

- 每个类有一个随机原型向量 `proto[c]`（32 维），每个样本的 16 个 patch 都是"原型 + 0.1 倍高斯噪声"。原型之间的距离远大于噪声，所以任务非常简单——重点是演示流程，不是难度。
- `unsqueeze(0)` 把 `(32,)` 变成 `(1, 32)`，`expand(num_patches, -1)` 再"广播"成 `(16, 32)`。`expand` 不复制内存，只是创建一个视图；随后 `base + noise` 产生新张量，所以不会出现多个样本共享内存的问题。
- 独立的 `torch.Generator().manual_seed(seed)`：数据生成用自己的随机数流，和训练时 `torch.randperm` 使用的全局随机数互不干扰，便于复现。
- `torch.stack(X)` 把 200 个 `(16, 32)` 堆成 `(200, 16, 32)`。
- ⚠️ **注意样本顺序**：样本是按类别依次生成的——前 40 个全是类 0，最后 40 个全是类 4。这会直接影响下一节的切分。

### 3.4 训练循环与一个切分问题

```python
    X, Y = synthetic_vision_class_data()
    split = int(0.85 * len(X))
    x_tr, y_tr = X[:split], Y[:split]
    x_va, y_va = X[split:], Y[split:]
    print(f"  train {len(x_tr)}, val {len(x_va)}")

    model = ToyVLM(vit_dim=32, llm_dim=64, num_classes=5)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    for step in range(150):
        idx = torch.randperm(len(x_tr))[:32]
        logits = model(x_tr[idx])
        loss = F.cross_entropy(logits, y_tr[idx])
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 30 == 0:
            with torch.no_grad():
                acc = (model(x_va).argmax(-1) == y_va).float().mean().item()
            print(f"  step {step:3d}  ce {loss.item():.3f}  val_acc {acc:.3f}")
```

- 训练部分是标准 PyTorch 三板斧：前向 → `F.cross_entropy`（内部含 softmax）→ `zero_grad / backward / step`。
- `torch.randperm(len(x_tr))[:32]`：每步随机抽 32 个样本组成 mini-batch（有放回地跨步抽样，每步内不重复）。
- 评估时 `torch.no_grad()` 关闭梯度记录，省内存、省计算。
- ⚠️ **切分 bug**：因为数据按类别有序且**切分前没有打乱**，`split = 170` 意味着：
  - 训练集（下标 0–169）= 类 0–3 各 40 个 + 类 4 只有 10 个；
  - 验证集（下标 170–199）= **30 个全是类 4**。

  所以打印的 `val_acc` 只反映"能否认出类 4"，而不是 5 类整体准确率；又因为这 30 个样本几乎一样，`val_acc` 通常只会是 0.000 或 1.000。修复方法是切分前 `perm = torch.randperm(len(X))` 打乱，或按类分层抽样（见测验 Q10）。
- ⚠️ 没有调用 `model.eval()`：本模型没有 Dropout/BatchNorm，所以不影响结果；但养成"评估前 `eval()`、训练前 `train()`"的习惯很重要。

### 3.5 `deepstack_features`：多层特征拼接

```python
def deepstack_features(per_layer_features):
    """
    Simulate DeepStack: per_layer_features is list of (N_patches, d) tensors
    from multiple ViT depths. Stack along channel dim and project.
    """
    return torch.cat(per_layer_features, dim=-1)
```

```python
    layers = [torch.randn(4, 16, 32) for _ in range(3)]  # 3 ViT depths
    stacked = deepstack_features(layers)
```

- `torch.cat(..., dim=-1)` 沿最后一维（通道维）拼接：3 个 `(4, 16, 32)` → `(4, 16, 96)`。每个 patch 现在同时携带浅层（空间、纹理）和深层（语义）信息。
- 对应讲义：深层特征回答"图里有什么"，浅层特征回答"具体在哪"，两者一起送入 LLM，改善空间定位（grounding）。
- ⚠️ 与文档字符串的出入：
  - 文档字符串说输入是 `(N_patches, d)`，但演示传入的是带 batch 维的 `(4, 16, 32)`——因为用的是 `dim=-1`，两种都能工作；
  - 文档字符串说"拼接并投影（and project）"，但函数**只做了拼接**。要真正使用，需要接一个 `Projector(vit_dim=96, ...)`。
- ⚠️ 这只是对"多层特征融合"的直观模拟。Qwen3-VL 技术报告把 DeepStack 描述为"利用多层 ViT 特征来收紧视觉-语言对齐"，具体如何把多层特征注入 LLM 应以技术报告为准，不要把"通道拼接"当作其唯一实现。

### 3.6 `cross_modal_error_rate`：CMER

```python
def cross_modal_error_rate(image_emb, text_emb, text_confidence,
                           sim_threshold=0.25, conf_threshold=0.8):
    image_emb = F.normalize(image_emb, dim=-1)
    text_emb = F.normalize(text_emb, dim=-1)
    sim = (image_emb * text_emb).sum(dim=-1)
    high_conf_low_sim = (text_confidence > conf_threshold) & (sim < sim_threshold)
    return high_conf_low_sim.float().mean().item()
```

- `F.normalize(..., dim=-1)` 把每个向量除以自身 L2 范数；归一化后"逐元素相乘再求和"就是**余弦相似度**。
- `(A) & (B)`：两个布尔张量的逐元素与。注意必须用 `&` 而不是 Python 的 `and`（`and` 不能作用于多元素张量），且每个比较要加括号——`&` 的优先级高于 `>` / `<`。
- `.float().mean()`：True/False 变成 1/0 后求平均，就是"被标记的比例"；`.item()` 把单元素张量转成 Python 浮点数。
- 判定语义：**模型很自信（`conf > 0.8`），但生成文本和图像不像（`sim < 0.25`）**——这是"一本正经地胡说"的典型信号。
- 两个边界细节：严格不等号意味着 `conf == 0.8` 不计入、`sim == 0.25` 也不计入。
- ⚠️ 生产要点（见 `outputs/skill-cmer-monitor.md`）：
  - `text_confidence` 必须是 [0,1] 的概率（如逐 token 概率的几何平均 `exp(mean(log_probs))`），不能传原始 logits；
  - 图文 embedding 要用**独立的** CLIP 系编码器计算，用 VLM 自己的 embedding 只能衡量自洽性；
  - 阈值需要在自己的数据上校准。

### 3.7 CMER 模拟

```python
    image = F.normalize(torch.randn(8, 32), dim=-1)
    text_good = image + 0.05 * torch.randn_like(image)
    text_good = F.normalize(text_good, dim=-1)
    text_bad = F.normalize(torch.randn(8, 32), dim=-1)
    text = torch.cat([text_good[:4], text_bad[4:]], dim=0)
    conf = torch.tensor([0.95, 0.9, 0.88, 0.85, 0.92, 0.9, 0.87, 0.91])
    cmer = cross_modal_error_rate(image, text, conf)
```

- 前 4 个文本 = 对应图像 + 小噪声，相似度接近 1，代表"有依据的回答"；后 4 个是与图像无关的随机向量，代表"幻觉"。
- 8 个置信度都高于 0.8，所以是否被标记完全取决于相似度。
- `torch.randn_like(image)` 生成与 `image` 同形状、同 dtype 的高斯噪声。
- ⚠️ 为什么注释写"expected ~0.5"而不是"= 0.5"：随机 32 维单位向量之间的余弦大约以 0 为中心、标准差约 `1/√32 ≈ 0.18`，单个幻觉样本有约 8% 的概率相似度 ≥ 0.25 而漏标。按此估算，CMER 打印 0.500 的概率约 72%，打印 0.375 的概率约 25%。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用合成"ViT 特征"代替真实 ViT | 不用下载模型权重，CPU 秒级跑完 | 学不到真实视觉特征；生产用 CLIP-L/14、SigLIP、DINOv3 等 |
| 用池化 + 分类头代替 LLM | 只验证"projector 可训练"这一件事 | 没有 `<image>` 占位符合并与文本生成；真实做法见讲义 Step 2 |
| 2 层 MLP + GELU | 与主流 VLM projector 一致，最简单的非线性桥 | 真实模型 2–4 层，可能配合 token 合并；也有 Q-former 方案 |
| DeepStack 用通道拼接模拟 | 直观展示"多层特征 = 更多信息" | 具体注入方式以 Qwen3-VL 技术报告为准 |
| CMER 用两个固定阈值 | 简单、可解释、可做 KPI | 阈值要在业务数据上校准；按 prompt 类型分别统计 |
| 按顺序切分训练/验证集 | 代码简短 | **导致验证集只有类 4**，应先打乱或分层切分 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类继承 + `super().__init__()` | `class Projector(nn.Module)` | PyTorch 模块必须先调用父类构造函数，才能注册子模块和参数 |
| `forward` 与 `__call__` | `model(x_tr[idx])` | 调用模块实例会自动调用 `forward`（并处理 hook），不要直接调 `forward` |
| 默认参数 | `def __init__(self, vit_dim=32, llm_dim=64, hidden=64)` | 不传参时使用默认值 |
| 列表推导式 | `[torch.randn(4, 16, 32) for _ in range(3)]` | `_` 表示"不关心的循环变量" |
| 元组解包 | `X, Y = synthetic_vision_class_data()`、`x_tr, y_tr = X[:split], Y[:split]` | 一次接收多个返回值 |
| 切片 | `X[:split]`、`text_good[:4]`、`torch.randperm(n)[:32]` | 张量也支持 Python 切片 |
| 张量花式索引 | `x_tr[idx]`（`idx` 是下标张量） | 一次按多个下标取样本 |
| 布尔张量运算 | `(a > t1) & (b < t2)` | 逐元素与；必须加括号，不能用 `and` |
| 链式方法调用 | `high_conf_low_sim.float().mean().item()` | 类型转换 → 求均值 → 转 Python 数 |
| 分号写多条语句 | `opt.zero_grad(); loss.backward(); opt.step()` | 合法但不推荐，可读性差 |
| `with` 上下文管理器 | `with torch.no_grad():` | 代码块内不记录梯度，退出后自动恢复 |
| f-string 格式符 | `f"{step:3d}"`、`f"{loss.item():.3f}"` | `:3d` 整数右对齐占 3 位；`:.3f` 保留 3 位小数 |
| `tuple(...)` | `tuple(stacked.shape)` | 把 `torch.Size` 转成普通元组以便打印 |
| 文档字符串 | `deepstack_features` 下的 `"""..."""` | 函数说明，可通过 `help()` 查看 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

> 未实际运行（当前环境缺少 `torch`，按规范不安装依赖）。以下是根据代码推断的预期输出结构，具体数值以你本地运行为准。

```text
[toy vlm: train projector + head on synthetic vision tokens]
  train 170, val 30
  step   0  ce <约 1.6 左右>  val_acc <0.000 或 1.000>
  step  30  ce <明显下降>      val_acc <...>
  step  60  ce <接近 0>        val_acc <...>
  step  90  ...
  step 120  ...

[deepstack concatenation]
  3 layers of (4, 16, 32) -> deepstack (4, 16, 96)

[CMER simulation]
  CMER = 0.500  (expected ~0.5 with 4 hallucinations out of 8)
```

逐段解读：

- **`train 170, val 30`**：确定值，`int(0.85 × 200) = 170`。
- **step 0 的 ce**：5 分类随机初始化时交叉熵约为 `ln 5 ≈ 1.609`，第一步打印的值应在这个量级附近。之后由于类原型间距远大于噪声，ce 会迅速下降。
- **`val_acc`**：注意它只衡量类 4（见 3.4），并且大概率是 0.000 / 1.000 这样的整值。如果你本地看到"step 0 就 1.000"或"从 0.000 直接跳到 1.000"，不要误以为模型神奇——是验证集只有一个类、样本几乎相同造成的。
- **DeepStack**：`(4, 16, 96)` 是确定值，32 × 3 = 96。
- **CMER**：大概率 0.500；约 25% 的随机情况下会是 0.375（有一个"幻觉"样本的随机相似度碰巧 ≥ 0.25）。

---

## 7. 动手改一改

1. **修切分**：在切分前加 `perm = torch.randperm(len(X))` 打乱，再看 `val_acc` 是否变成 0.2、0.4、0.8 这类"多类混合"的数值。
2. **数参数**：打印 `sum(p.numel() for p in model.parameters())`，验证是 6,597；再算出 projector 占比。
3. **加难度**：把噪声从 `0.1` 调到 `1.0`、`2.0`，观察收敛步数和最终准确率如何变化。
4. **接上 DeepStack**：写一个 `DeepStackToyVLM`，输入 3 层特征列表，先 `deepstack_features` 拼接，再用 `Projector(vit_dim=96, llm_dim=64)` 投影，确认前向形状正确。
5. **实现占位符合并**：参照讲义 Step 2 的 `MinimalVLM._merge`，用一个小的 `nn.Embedding` 当作"LLM 词表"，在 `input_ids` 中放入若干 `<image>` 占位符，把 projector 输出替换进去，并测试占位符数量不匹配时是否抛出 `ValueError`。
6. **CMER 鲁棒性**：把 `sim_threshold` 改成 0.1 和 0.35，分别统计 1,000 次随机模拟下 CMER 的分布，体会阈值对漏报/误报的影响。

---

## 8. 常见坑

- **有序数据直接切分**：按类别顺序生成或读取的数据，不打乱就切分会让验证集只含部分类别，指标完全失真（本文件就有这个问题）。
- **用 `and` 组合布尔张量**：`(a > t) and (b < t)` 对多元素张量会报 "Boolean value of Tensor with more than one value is ambiguous"；要用 `&`，并给每个比较加括号。
- **忘记归一化就算"余弦"**：未归一化的点积会受向量长度影响，CMER 阈值就失去意义。
- **把 logits 当置信度**：CMER 的 `conf_threshold=0.8` 假设输入是 [0,1] 的概率，原始 logits 无界，会让标记结果毫无意义。
- **维度对不上**：DeepStack 拼接后维度变为 `层数 × d`，后面的 projector `vit_dim` 必须跟着改，否则 `Linear` 报形状不匹配。
- **评估时不关梯度**：不用 `torch.no_grad()` 会在验证时也构建计算图，浪费内存；有 Dropout/BN 的模型还要记得 `model.eval()`。
