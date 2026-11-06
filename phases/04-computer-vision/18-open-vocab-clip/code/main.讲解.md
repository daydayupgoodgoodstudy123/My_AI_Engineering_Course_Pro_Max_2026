# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 18 节 开放词表（Open-Vocabulary）视觉——CLIP ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，全程 CPU） ｜ **依赖**：`torch`（`torch.nn`、`torch.nn.functional`）；无需 NumPy、无需联网、无需预训练权重

---

## 1. 这份代码在考察什么

真实的 CLIP 是 ViT + Transformer、在 4 亿图文对上训练的大模型，CPU 上根本跑不动。这份代码把它"缩小到骨架"，只保留让 CLIP 成立的三个关键部件，让你在几秒内看到对比学习的训练信号：

1. **双塔结构**：图像塔、文本塔各自独立，最后投影到同一维度并 L2 归一化——这就是"共享 embedding 空间"的全部含义。
2. **对称对比损失**：N×N 相似度矩阵 + 以 `arange(N)` 为标签的双向交叉熵，以及可学习温度 `logit_scale`。
3. **Zero-shot 分类**：不训练任何分类头，只用"类别的文本向量"与图像向量算余弦再取 argmax。
4. **合理性检查（sanity check）**：随机初始化时损失应在 `log N` 附近——这是调试任何对比学习代码的第一步。
5. **合成数据上的"可学习结构"**：用类别原型 `proto` 制造图文之间的共享信号，观察损失下降和 zero-shot 准确率。

> 一句话：**CLIP = 两个投影头 + 一个温度 + 一个对角线交叉熵**；学会这 30 行，就能读懂 OpenCLIP 的核心训练逻辑。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TwoTower` | `nn.Module` 类 | 图像塔 `image_proj`（128→128→64）、文本塔 `text_proj`（64→128→64）、可学习 `logit_scale` | 双塔 / dual encoder、温度 |
| `TwoTower.encode_image / encode_text` | 方法 | 投影后 `F.normalize`，输出单位向量 | 共享 embedding 空间、余弦相似度 |
| `TwoTower.forward` | 方法 | 返回 `(图像向量, 文本向量, exp(logit_scale))` | 与 CLIP 官方 API 同形 |
| `clip_loss(i, t, logit_scale)` | 函数 | 对称交叉熵：`(CE(sim) + CE(simᵀ)) / 2` | 对比学习目标 / InfoNCE |
| `zero_shot_classify(...)` | 函数（`@torch.no_grad()`） | 编码图像和类别文本 → 相似度 → argmax → 类名 | Zero-shot 分类 |
| `main()` 第一段 | 演示 | 随机数据上算一次损失，对照 `log(8)` | 初始化合理性检查 |
| `main()` 第二段 | 演示 | 5 类原型合成数据，Adam 训练 100 步 | 对比训练 |
| `main()` 第三段 | 演示 | 用"类别原型"作为文本输入做 zero-shot，统计 16 张图的准确率 | 开放词表推理 |

数据流：`main` 生成特征 → `model(img, txt)` 得到归一化向量和温度 → `clip_loss` → 反向传播更新两座塔和温度 → 训练结束后 `zero_shot_classify` 只用两座塔的编码函数做推理。

---

## 3. 逐段精讲

### 3.1 双塔模型：两个投影头 + 一个温度

```python
class TwoTower(nn.Module):
    def __init__(self, img_in=128, txt_in=64, emb=64):
        super().__init__()
        self.image_proj = nn.Sequential(nn.Linear(img_in, 128), nn.ReLU(), nn.Linear(128, emb))
        self.text_proj = nn.Sequential(nn.Linear(txt_in, 128), nn.ReLU(), nn.Linear(128, emb))
        self.logit_scale = nn.Parameter(torch.ones([]) * 2.6592)
```

- **两座塔输入维度不同**（图像 128、文本 64），输出维度相同（`emb=64`）。这正是 CLIP 的关键：模态各自有各自的编码器，只在最后的投影空间"会师"。真实 CLIP 中，ViT-B/32 的投影维度是 512。
- 讲义说"towers are small MLPs over pre-extracted features"：这里的输入假装是"已经抽好的图像特征 / 文本特征"，塔只是两层 MLP。⚠️ 这是刻意简化——真实系统里塔本身就是 ViT 和 Transformer，参数量上亿。
- `nn.Sequential` 把层按顺序串起来，调用时依次执行，省去手写 `forward`。
- **`logit_scale` 的魔法数字**：`2.6592 ≈ ln(1/0.07)`，所以 `exp(logit_scale) ≈ 14.28 = 1/τ`，τ = 0.07 就是讲义说的初始温度。
  - `torch.ones([])` 创建一个 **0 维标量张量**（形状 `[]`），乘 2.6592 后用 `nn.Parameter` 包装，它就会出现在 `model.parameters()` 中，被优化器一起更新。
  - 为什么存 log 值而不是直接存 14.28？①`exp` 永远为正，温度不会被优化成负数；②在对数空间的加性更新相当于乘子的乘性变化，学习更平稳。

### 3.2 编码函数：归一化是"余弦相似度"的前提

```python
    def encode_image(self, x):
        return F.normalize(self.image_proj(x), dim=-1)

    def encode_text(self, x):
        return F.normalize(self.text_proj(x), dim=-1)

    def forward(self, img_feats, txt_feats):
        i = self.encode_image(img_feats)
        t = self.encode_text(txt_feats)
        return i, t, self.logit_scale.exp()
```

- `F.normalize(x, dim=-1)` 把每一行除以它的 L2 范数（内部对范数做了 `eps` 下限保护，不会除以 0）。归一化之后，**点积 = 余弦相似度**，取值 [-1, 1]。
- 把编码拆成 `encode_image` / `encode_text` 两个方法，是照搬 OpenCLIP 的 API 形状（讲义 "Use It" 部分的 `model.encode_image(image)`、`model.encode_text(text)`）。好处是：**推理时两座塔可以完全独立运行**——图库里的图像向量离线算一次存起来，查询来了只算文本塔。
- `forward` 返回 `exp` 之后的温度，而不是原始 log 值，调用方直接拿去乘就行。
- 和讲义 Step 1 的写法相比，代码多抽了两个编码方法，但数学完全相同。

### 3.3 对称对比损失

```python
def clip_loss(i, t, logit_scale):
    N = i.size(0)
    sim = logit_scale * i @ t.T
    targets = torch.arange(N, device=sim.device)
    l_i = F.cross_entropy(sim, targets)
    l_t = F.cross_entropy(sim.T, targets)
    return (l_i + l_t) / 2
```

逐行看：

| 行 | 形状 | 含义 |
|----|------|------|
| `sim = logit_scale * i @ t.T` | `(N, N)` | 第 (a, b) 格 = 图 a 与文 b 的余弦 × 14.3 |
| `targets = torch.arange(N)` | `(N,)` | `[0, 1, …, N-1]`：第 a 行的正确答案是第 a 列（对角线） |
| `F.cross_entropy(sim, targets)` | 标量 | 每张图在 N 段文本里做 N 选 1 分类（image→text） |
| `F.cross_entropy(sim.T, targets)` | 标量 | 每段文本在 N 张图里做 N 选 1 分类（text→image） |

- **为什么是交叉熵**：把"在 batch 里找到自己的配对"看成一个 N 类分类问题，类别 = batch 里的列号。这就是 InfoNCE。
- **为什么对称**：两个方向的检索下游都要用（见测验 Q3）。
- `device=sim.device` 让标签和 logits 在同一设备上；本脚本全在 CPU，但这样写搬到 GPU 也不用改。
- 运算优先级：`logit_scale * i @ t.T` 中 `*` 和 `@` 优先级相同、从左到右结合，先算 `logit_scale * i`（缩放 N×d 矩阵）再乘 `t.T`，结果与先乘后缩放完全一致。
- ⚠️ 简化：真实 CLIP 会把温度乘子截断在 100 以内防止训练不稳定；多卡训练时还要先 all-gather 各卡的 embedding 才能构成全局 N×N 矩阵。这里都省略了。

### 3.4 Zero-shot 分类：文本向量就是分类头的权重

```python
@torch.no_grad()
def zero_shot_classify(model, image_feats, class_text_feats, class_names):
    i = model.encode_image(image_feats)
    t = model.encode_text(class_text_feats)
    sim = i @ t.T
    pred = sim.argmax(dim=-1)
    return [class_names[p] for p in pred.tolist()]
```

- `@torch.no_grad()` 作为**装饰器**，让整个函数体不构建计算图：推理时既省显存又更快，也避免意外把推理结果的梯度带回训练。
- 形状：`image_feats (M, 128)` → `i (M, 64)`；`class_text_feats (C, 64)` → `t (C, 64)`；`sim (M, C)`；`pred (M,)`。
- **没乘 `logit_scale`**：argmax 对正数缩放不变；只有需要输出"概率"时（如讲义里 OpenCLIP 例子的 `(100.0 * image_features @ text_features.T).softmax(dim=-1)`）才需要温度。
- 关键洞察：`sim = i @ t.T` 等价于一个**没有偏置的线性分类层**，权重矩阵就是 `t`。传统分类器的权重是训练出来的；CLIP 的权重是"由文本塔即时生成的"——想加一个类，就多编码一句话。这就是"开放词表"。
- `pred.tolist()` 把张量转成 Python 整数列表，再用列表推导映射成类名。

### 3.5 合理性检查：随机初始化的损失

```python
    torch.manual_seed(0)
    model = TwoTower()

    print("[random batch sanity]")
    img = torch.randn(8, 128)
    txt = torch.randn(8, 64)
    i, t, scale = model(img, txt)
    loss = clip_loss(i, t, scale)
    print(f"  batch {i.size(0)}  loss={loss.item():.3f}  expected~log(8)={torch.log(torch.tensor(8.0)).item():.3f}")
```

- `torch.manual_seed(0)` 固定全局随机种子：模型初始化和后面所有 `torch.randn` / `torch.randint` 都可复现。
- **为什么参考值是 `log(8)`**：如果 8 个 logit 完全相等，softmax 是均匀分布，交叉熵 = `-log(1/8) = log 8 ≈ 2.079`。这是"模型什么都没学会"时的基准。
- ⚠️ 但要注意，`log N` 其实是**下限而不是精确值**：对任意一行 logits，"按目标位置平均的交叉熵" = `logsumexp(z) - mean(z) ≥ log N`，只有 logits 全相等时才取等号。这里 `logit_scale` 一开始就把随机余弦放大约 14.3 倍，随机波动会让损失明显高于 2.079。所以看到 2.5、3.0 之类的数不必惊慌；如果看到远小于 2.079 的值（比如 0.1），反而说明有 bug（例如标签泄漏）。
- `.item()` 把 0 维张量转成 Python 浮点数，才能用 `:.3f` 格式化。

### 3.6 合成训练数据：用"类别原型"制造图文共享信号

```python
    rng = torch.Generator().manual_seed(42)
    dim = 32
    num_classes = 5
    proto = F.normalize(torch.randn(num_classes, dim, generator=rng), dim=-1)

    def sample_pair_batch(batch=32):
        labels = torch.randint(0, num_classes, (batch,))
        img = torch.randn(batch, 128)
        txt = torch.randn(batch, 64)
        img[:, :dim] = proto[labels] + 0.1 * torch.randn(batch, dim)
        txt[:, :dim] = proto[labels] + 0.1 * torch.randn(batch, dim)
        return img, txt, labels
```

- `proto`：5 个随机的 32 维单位向量，代表 5 个"概念"。用独立的 `torch.Generator` 生成，原型本身不受全局种子变化影响。
- 每对 (图, 文) 的**前 32 维**都是"同一个原型 + 小噪声"——这是图文之间唯一的共享信号；图像的后 96 维、文本的后 32 维都是纯噪声，模型必须学会忽略它们。
- `proto[labels]` 是**高级索引**：用长度为 32 的标签向量从 `(5, 32)` 中取行，得到 `(32, 32)`。
- `img[:, :dim] = ...` 是**切片原地赋值**，只覆盖前 32 列。
- `sample_pair_batch` 是定义在 `main` 里的**嵌套函数**，直接读取外层的 `proto`、`dim`、`num_classes`（闭包）。
- ⚠️ 一个很值得注意的隐藏性质：5 个类、batch 32，**一个 batch 里同类样本平均有 6 个以上**。同类的图 a 和文 b 在统计上与真正的配对文 a 无法区分，但 `clip_loss` 只承认对角线为正例——这就是对比学习里的**假负例（false negatives）**。因此损失有一个大约 1.9 的理论下界（推导见测验 Q9），训练再久也降不到 0。

### 3.7 训练循环

```python
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    for step in range(100):
        img_b, txt_b, _ = sample_pair_batch(32)
        i_emb, t_emb, s = model(img_b, txt_b)
        loss = clip_loss(i_emb, t_emb, s)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 20 == 0:
            print(f"  step {step:3d}  loss {loss.item():.3f}")
```

- 标准的 PyTorch 三步：`zero_grad`（清空旧梯度）→ `backward`（反向传播）→ `step`（更新参数）。用分号写在一行只是为了紧凑，效果与分三行相同。
- `model.parameters()` 包含两座塔的全部权重**以及 `logit_scale`**——温度也在学习。Adam 每步对单个参数的更新幅度约为 lr 量级，100 步下来 `logit_scale` 最多变化约 0.3，所以温度乘子大致仍在 10–20 之间。
- 每步都现采样一个新 batch（无限数据流），不存在"过拟合训练集"的问题。
- `_` 是"我不需要这个返回值"的惯用占位名（这里丢弃了 labels——**对比学习训练时根本不用类别标签**，只用配对关系）。
- `{step:3d}` 让步数右对齐占 3 位，日志更整齐。

### 3.8 Zero-shot 评估

```python
    class_text = torch.zeros(num_classes, 64)
    class_text[:, :dim] = proto
    test_img, _, test_labels = sample_pair_batch(batch=16)
    class_names = [f"class_{c}" for c in range(num_classes)]
    preds = zero_shot_classify(model, test_img, class_text, class_names)
    correct = sum(p == f"class_{l}" for p, l in zip(preds, test_labels.tolist()))
    print(f"  zero-shot accuracy: {correct}/16 = {correct / 16:.3f}")
```

- `class_text` 扮演"类别 prompt 的文本特征"：前 32 维是不带噪声的原型，后 32 维为 0（即训练时噪声维的期望值）。这相当于每个类的"理想文本描述"，与讲义"多模板取平均得到类别质心"是同一个思路。
- 训练时**从没出现过"类别"这个概念**（标签被丢弃），推理时却能按类别分类——因为图文共享空间里，同一概念的图和文会聚到一起。这就是 zero-shot 的本质。
- `sum(p == ... for ...)`：生成器里每个比较结果是 `bool`，而 `True` 在 Python 里等于 1，所以 `sum` 直接得到正确个数。
- ⚠️ 简化："held-out" 只是"新采样的样本"，与训练同分布，而且类别也是训练中出现过的那 5 个原型。真实 zero-shot 的难点在于**分布外的类别和图像**，这个玩具实验测不出来。
- ⚠️ `16` 在打印中写死了，如果改了 `batch=16`，要同步改这里（更好的写法是 `len(preds)`）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 塔是两层 MLP，输入是"预抽特征" | CPU 几秒内能看到训练信号 | 生产用 ViT + Transformer，端到端从像素和 token 训练 |
| `logit_scale` 存 log 值、可学习 | 保证温度为正，学习平稳 | CLIP 还会把乘子截断在 100 以内 |
| 拆出 `encode_image / encode_text` | 与 OpenCLIP API 同形，推理时两塔可独立运行 | 生产中图像向量离线批量计算并入向量库 |
| 对称交叉熵 | 两个检索方向都要好用 | 大规模训练可换 SigLIP 逐对 sigmoid，省去全局归一化 |
| 推理不乘温度 | argmax 对缩放不变 | 需要校准概率时乘温度再 softmax |
| 5 类原型 + 噪声的合成数据 | 制造可控的"共享语义"，结果可解释 | batch 内同类重复造成假负例，损失有下界；真实网页数据重复率低 |
| 训练不使用标签 | 体现"只靠配对关系学习" | 若有标签，可用多正例的监督对比损失 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import ... as ...` | `import torch.nn.functional as F` | 给模块起短别名，PyTorch 社区惯例 |
| 函数默认参数 | `def __init__(self, img_in=128, txt_in=64, emb=64)`、`def sample_pair_batch(batch=32)` | 不传参时用默认值；调用时可用关键字参数覆盖，如 `sample_pair_batch(batch=16)` |
| 类继承与 `super()` | `class TwoTower(nn.Module)`、`super().__init__()` | 继承 `nn.Module` 才能自动注册子层和参数；必须先调用父类构造函数 |
| `__call__` 与 `forward` | `model(img, txt)` | 调用模型实例时，`nn.Module.__call__` 会转到你写的 `forward` |
| 装饰器 | `@torch.no_grad()` | 用一个函数包装另一个函数；这里让函数体内不记录梯度 |
| 元组返回与解包 | `return i, t, self.logit_scale.exp()`；`i, t, scale = model(img, txt)` | 一次返回/接收多个值 |
| `_` 占位变量 | `img_b, txt_b, _ = sample_pair_batch(32)` | 表示"这个值不用" |
| 嵌套函数 / 闭包 | `main` 里定义 `sample_pair_batch`，读取外层的 `proto` | 内层函数可以读取外层函数的局部变量 |
| 列表推导式 | `[class_names[p] for p in pred.tolist()]` | 一行生成列表 |
| 生成器表达式 + 布尔求和 | `sum(p == f"class_{l}" for p, l in zip(...))` | `True` 当 1 计数，统计满足条件的个数 |
| `zip` | `zip(preds, test_labels.tolist())` | 把两个序列按位置配对 |
| f-string 格式符 | `{loss.item():.3f}`、`{step:3d}` | `.3f` 保留 3 位小数；`3d` 整数右对齐占 3 位 |
| 一行多语句 | `opt.zero_grad(); loss.backward(); opt.step()` | 分号分隔，等价于写三行（风格上一般不推荐） |
| 张量切片赋值 / 高级索引 | `img[:, :dim] = proto[labels] + ...` | 原地覆盖前 `dim` 列；用整数张量按行取原型 |
| `@` 与 `.T` | `i @ t.T` | 矩阵乘法与转置 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 根据代码，输出由三段组成，格式如下（具体数值依赖 PyTorch 的随机数，这里不编造）：

```text
[random batch sanity]
  batch 8  loss=?.???  expected~log(8)=2.079

[train on structured synthetic pairs]
  step   0  loss ?.???
  step  20  loss ?.???
  step  40  loss ?.???
  step  60  loss ?.???
  step  80  loss ?.???

[zero-shot on held-out images]
  zero-shot accuracy: ??/16 = ?.???
```

可以确定或合理预期的部分：

- `expected~log(8)=2.079` 是确定值（`ln 8 = 2.0794`）。
- 第一行的随机损失**通常高于 2.079**。我用 NumPy 按 PyTorch `nn.Linear` 的默认初始化分布（权重和偏置都是 `U(-1/√fan_in, 1/√fan_in)`）、相同的网络结构和 `logit_scale` 模拟了 200 次：平均约 2.92，范围约 1.87–3.97。原因见 3.5 节：`log N` 是期望意义下的下限，温度放大了随机波动。
- 训练日志共 5 行（step 0、20、40、60、80，第 99 步不打印）。step 0 的损失应在 `log 32 ≈ 3.47` 或更高的量级；之后下降，但会趋近约 **1.9** 的下界而不是 0（batch 内同类假负例，见 3.6 节和测验 Q9）。如果你看到损失停在 2 左右，这是**正确**的行为，不是 bug。
- zero-shot 准确率预期较高：5 个原型是随机单位向量，彼此距离约 √2，而噪声的范数约 `0.1 × √32 ≈ 0.57`，类别之间可分性很好；但训练只有 100 步，具体能否 16/16 需实际运行确认。

---

## 7. 动手改一改

1. **温度消融**：把 `2.6592` 改成 `0.0`（乘子为 1）和 `4.6`（乘子约 100），比较随机初始化损失和 100 步后的损失。观察：乘子为 1 时初始损失非常接近 `log 8`，但训练很慢。
2. **假负例实验**：把 `num_classes` 改为 32 和 1000，或者在 `sample_pair_batch` 里让一个 batch 内类别不重复，观察训练损失的下界如何变化（类越多，同类重复越少，下界越低）。
3. **单向损失**：把 `clip_loss` 改成只返回 `l_i`，训练后分别评估"图找文"和"文找图"的 top-1 准确率，验证对称损失的作用。
4. **实现 SigLIP**：给 `TwoTower` 加 `logit_bias` 参数，写 `siglip_loss`（参考测验 Q10），在 batch = 8 和 batch = 32 两种设置下与 `clip_loss` 对比。
5. **模板平均**：为每个类构造 10 个"带不同噪声的文本特征"（模拟 10 个 prompt 模板），分别编码、归一化、取平均再归一化，对比与"单个带噪声文本特征"做 zero-shot 的准确率。
6. **用真模型**：按讲义 "Use It" 部分用 OpenCLIP 的 ViT-B-32 对几张自己的照片做 zero-shot，并尝试不同的 prompt 写法。

---

## 8. 常见坑

- **忘记 L2 归一化**：不归一化时点积会被向量长度主导，温度也失去意义；zero-shot 时图像和文本两侧都必须归一化。
- **把 `logit_scale` 当成 τ**：代码里存的是 `ln(1/τ)`，用的时候要 `exp()`；直接拿 2.6592 去乘或除都是错的。
- **期待随机初始化损失精确等于 `log N`**：它只是 logits 全相等时的值，实际往往偏高；远低于 `log N` 才可疑。
- **期待损失降到 0**：batch 内有同类样本（假负例）时损失有下界；真实训练中重复的图文对、近义 caption 也会造成这个问题。
- **推理时忘了 `no_grad` / `eval`**：大批量编码图库时会累积计算图，显存暴涨（本模型没有 Dropout/BN，`eval()` 不影响结果，但真实模型会）。
- **训练和推理的文本分布不一致**：这里 `class_text` 的噪声维为 0、真实场景里 prompt 写法与训练 caption 风格不同，都会影响 zero-shot 效果——这正是 prompt 工程存在的原因。
