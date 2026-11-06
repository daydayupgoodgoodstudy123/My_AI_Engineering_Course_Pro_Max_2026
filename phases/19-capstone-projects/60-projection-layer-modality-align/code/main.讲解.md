# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 60 节 用于 Modality Alignment 的投影层 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下，CPU 约 15 秒）；测试：`python3 -m unittest test_main.py` 或 `python3 -m pytest -q test_main.py` ｜ **依赖**：第三方 `torch`、`numpy`；标准库 `importlib`、`dataclasses`、`pathlib`；**要求**同级目录 `59-vit-transformer/code/main.py` 与 `58-vision-encoder-patches/code/main.py` 存在（按路径链式加载）

---

## 1. 这份代码在考察什么

视觉 encoder（第 58–59 节）输出 768 维的图像向量，语言侧使用 512 维的文本 embedding。本节搭一座"桥"：一个两层 MLP，把图像向量投影到文本空间，用余弦损失让配对的图像与 caption 指向同一方向。它考察：

1. **投影层的结构与规模**：`768 → 1024 → 512`，GELU 非线性，约 1.31M 参数。
2. **冻结与只训练桥**：视觉 encoder 与文本表都 `requires_grad=False`，优化器只拿到投影层参数——adapter 式 VLM（LLaVA 第一阶段）的基本形态。
3. **带 mask 的平均池化**：caption 的 token embedding 去掉 padding 后取平均。
4. **余弦对齐损失**：`1 − cos`，尺度不变，范围 [0, 2]。
5. **跨课程组合**：链式加载第 59 节（它又加载第 58 节）。

> 一句话：**冻结两端、只训一个小 MLP，把图像特征"翻译"成文本空间里的方向**。但要看清本节演示的局限：随机初始化的 encoder + 几乎相同的合成图像 + 与图像无关的随机 caption，使得投影层实际上只学到了"平均 caption 方向"（测验 Q6）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_load_module` | 函数 | 按路径加载第 59 节 `main.py`（失败时从 `sys.modules` 清理） | 跨课程复用 |
| `ViTConfig` / `VisionEncoder` / `synthesize_image` | 来自第 59（58）节 | 视觉 encoder 与图像夹具 | 冻结的视觉塔 |
| `AlignConfig` | 冻结 dataclass | 维度、词表、caption 长度、样本数、步数、学习率、种子 | 配置 |
| `MLPProjector` | `nn.Module` | `fc2(GELU(fc1(x)))` | 投影头 |
| `MockTextEmbedding` | `nn.Module` | 固定随机 embedding 表 + 忽略 id 0 的平均池化 | 冻结的文本侧 |
| `make_pair` | 函数 | 生成一对（224×224 图像，长度 4–16 的随机 token 序列） | 合成图文对 |
| `cosine_alignment_loss` | 函数 | `mean(1 − cos(normalize(img), normalize(txt)))` | 对齐目标 |
| `freeze` | 函数 | 把模块所有参数设为 `requires_grad=False` | 冻结 |
| `TrainStats` | dataclass | 初始/最终损失、最终余弦、全部损失 | 训练记录 |
| `train` | 函数 | 构造 encoder/文本表/投影层/样本，循环 200 步，每 25 步打印 | 训练循环 |
| `main` | 函数 | 打印配置、训练、参数量与损失变化 | 演示 |

数据流：`make_pair` → `(img (1,3,224,224), ids (1,16))` → `encoder(img)` 取 `cls (1,768)`（no_grad）→ `projector(cls)` → `image_emb (1,512)`；`text(ids)` → `text_emb (1,512)`（no_grad）→ `cosine_alignment_loss` → `backward` → `Adam.step`（只更新投影层）。

---

## 3. 逐段精讲

### 3.1 链式加载第 59 节

```python
THIS_DIR = Path(__file__).resolve().parent
LESSON_59 = THIS_DIR.parent.parent / "59-vit-transformer" / "code"

def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    ...
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod

_encoder_mod = _load_module("vit_encoder_lesson59", LESSON_59 / "main.py")
```

- 执行第 59 节的模块代码时，它又会按路径加载第 58 节（注册为 `vision_front_end_lesson58`），形成 60 → 59 → 58 的链。
- 比第 57、59 节多了一步：`exec_module` 失败时把半初始化的模块从 `sys.modules` 删掉再抛出，避免后续导入拿到一个残缺模块——这是更规范的写法。
- `synthesize_image` 经由第 59 节重新导出，最终来自第 58 节。

### 3.2 配置 `AlignConfig`

```python
@dataclass(frozen=True)
class AlignConfig:
    vision_hidden: int = 768
    projection_hidden: int = 1024
    text_hidden: int = 512
    vocab_size: int = 4096
    max_caption_len: int = 16
    pairs: int = 32
    steps: int = 200
    lr: float = 3e-4
    seed: int = 0
```

- `vision_hidden` 必须与 encoder 的 `hidden` 一致（`train()` 中用它构造 encoder）。
- 32 对样本、200 步：每对样本大约被看到 6 次。
- 注意：配置里**没有** encoder 的深度/头数，`train()` 中写死为 `depth=4, heads=8, mlp_ratio=2.0`。

### 3.3 `MLPProjector`

```python
class MLPProjector(nn.Module):
    def __init__(self, in_dim, hidden_dim, out_dim):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, out_dim)

    def forward(self, x):
        return self.fc2(F.gelu(self.fc1(x)))
```

- 参数：`fc1` 787,456 + `fc2` 524,800 = **1,312,256**（与讲义"about 1.3M"一致）。
- 中间层 1024 比输入、输出都宽；GELU 提供一次"非线性弯折"（讲义："one non-linear bend"）。
- 输入可以是 `(B, 768)` 也可以是 `(B, N, 768)`——`nn.Linear` 只作用于最后一维，所以同一个投影层可以直接用于全部 patch token（LLaVA 的做法），本节只用了 CLS。

### 3.4 `MockTextEmbedding`：冻结的文本表与 mask 平均池化

```python
    def __init__(self, vocab_size, dim, seed):
        super().__init__()
        gen = torch.Generator().manual_seed(seed)
        weight = torch.randn(vocab_size, dim, generator=gen) * (1.0 / dim ** 0.5)
        self.table = nn.Embedding(vocab_size, dim, _weight=weight)
        for p in self.table.parameters():
            p.requires_grad_(False)

    def forward(self, ids):
        if ids.dim() != 2:
            raise ValueError(...)
        embed = self.table(ids)                          # (B, L, D)
        mask = (ids != 0).float().unsqueeze(-1)          # (B, L, 1)
        denom = mask.sum(dim=1).clamp(min=1.0)           # (B, 1)
        pooled = (embed * mask).sum(dim=1) / denom       # (B, D)
        return pooled
```

- **独立的随机数生成器**：`torch.Generator().manual_seed(seed)` 不影响全局随机状态，文本表的内容只由 `seed` 决定。
- 初始化 std `1/√512`，每一行的期望范数约为 1。
- `nn.Embedding(..., _weight=weight)` 用给定张量初始化；公开 API 的等价写法是 `nn.Embedding.from_pretrained(weight, freeze=True)`。
- 构造函数里已经冻结，`train()` 中又调用一次 `freeze(text)`，是冗余但无害的双保险。
- **mask 平均池化**：`ids != 0` 得到布尔 mask，转浮点后 `unsqueeze(-1)` 以便与 `(B, L, D)` 广播相乘；分母是非 padding token 数，`clamp(min=1.0)` 防止全 padding 时除零。
- ⚠️ `nn.Embedding` 没有设置 `padding_idx=0`，id 0 那一行也是随机向量——忽略 padding 完全依赖这里的 mask。

### 3.5 `make_pair`：合成样本

```python
def make_pair(seed, vocab_size, max_len):
    img = synthesize_image(seed=seed)
    rng = np.random.default_rng(seed + 10_000)
    length = int(rng.integers(4, max_len + 1))
    ids = np.zeros((max_len,), dtype=np.int64)
    ids[:length] = rng.integers(1, vocab_size, size=length)
    return img, torch.from_numpy(ids).unsqueeze(0)
```

- caption 长度在 [4, max_len] 内随机（`rng.integers` 的上界不含，所以写 `max_len + 1`），其余位置补 0。
- token 从 `[1, vocab_size)` 中均匀随机采样，**与图像内容毫无关系**。
- 图像与 caption 用不同的种子派生（`seed` 与 `seed + 10_000`），互不干扰；`10_000` 是 Python 的数字分隔写法。
- ⚠️ 所有图像都来自 `synthesize_image`：共享同一个颜色梯度，只是噪声不同。随机初始化的 encoder 对它们给出的 CLS 两两余弦 ≥ 0.99997（我们实测），几乎无法区分。

### 3.6 余弦对齐损失与冻结

```python
def cosine_alignment_loss(image_emb, text_emb):
    if image_emb.shape != text_emb.shape:
        raise ValueError(...)
    img_n = F.normalize(image_emb, dim=-1)
    txt_n = F.normalize(text_emb, dim=-1)
    cos = (img_n * txt_n).sum(dim=-1)
    return (1.0 - cos).mean()

def freeze(module):
    for p in module.parameters():
        p.requires_grad_(False)
```

- `F.normalize(x, dim=-1)` 把每个向量除以 L2 范数（带 `eps` 防零），之后逐元素相乘再求和就是余弦。
- 损失 = `1 − cos` 的 batch 平均：同向 0、正交 1、反向 2（测试 `test_max_loss_on_antiparallel_vectors` 验证 2.0）。
- **尺度不变**：投影输出放大任意正数倍损失不变（测验 Q7）。
- 先检查形状一致——如果投影维度配错（如 512 vs 768），错误会在这里清晰暴露，而不是在广播时悄悄出错。
- `freeze` 只关梯度，不切换 `eval()`；`train()` 中 encoder 另外调用了 `.eval()`（本 encoder 的 dropout 为 0，模式其实不影响结果）。

### 3.7 `train()`：训练循环

```python
    torch.manual_seed(cfg.seed)
    encoder_cfg = ViTConfig(image_size=224, patch_size=16, hidden=cfg.vision_hidden,
                            depth=4, heads=8, mlp_ratio=2.0)
    encoder = VisionEncoder(encoder_cfg).eval()
    freeze(encoder)
    text = MockTextEmbedding(cfg.vocab_size, cfg.text_hidden, seed=cfg.seed + 1)
    freeze(text)
    projector = MLPProjector(cfg.vision_hidden, cfg.projection_hidden, cfg.text_hidden)
    pairs = [make_pair(seed=cfg.seed + 1000 + i, ...) for i in range(cfg.pairs)]
    opt = torch.optim.Adam(projector.parameters(), lr=cfg.lr)

    for step in range(cfg.steps):
        img, ids = pairs[step % cfg.pairs]
        with torch.no_grad():
            _, cls = encoder(img)
            text_emb = text(ids)
        image_emb = projector(cls)
        loss = cosine_alignment_loss(image_emb, text_emb)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        ...
```

- 开头先校验 `pairs`、`steps`、`max_caption_len >= 4`（`make_pair` 的最短长度是 4）。
- ⚠️ **encoder 规模**：4 层、8 头（head_dim 96）、`mlp_ratio=2`，我们实测参数 19,501,056，且**随机初始化**。讲义的"frozen vision encoder ... 86M parameters"与代码不符。
- **三重"冻结"**：`requires_grad_(False)`（不算梯度）+ `with torch.no_grad()`（不建计算图，省内存）+ 优化器只接收 `projector.parameters()`（即使有梯度也不会更新别的参数）。
- `opt.zero_grad(set_to_none=True)`：把梯度设为 `None` 而不是 0 张量，省一次内存写入。
- `pairs[step % cfg.pairs]`：按顺序循环使用 32 对样本，每步 batch = 1。
- 每 25 步（以及最后一步）在 `no_grad` 下用 `F.cosine_similarity` 打印当前样本的余弦。
- ⚠️ **效率**：encoder 冻结、输入固定，却在每一步重新前向；200 次 4 层 ViT 前向占了约 15 秒运行时间的大部分。预先缓存 32 个 CLS 特征后，同样 200 步只需约 3.8 秒（测验 Q10）。
- ⚠️ **指标**：`initial_loss` 是第 0 对样本的损失，`final_loss` 是第 7 对（`199 % 32`）的损失，二者不可直接相减（测验 Q5）。

### 3.8 `main()`

打印配置 → 调用 `train` → 打印投影层参数量、初始/最终损失、最终余弦与 `loss drop`；`drop > 0.0` 就打印 "ok: projector learned an alignment direction"。这个判据过弱，单样本噪声就足以让它通过（测验 Q17）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 两层 GELU MLP | LLaVA-1.5 的标准做法，比线性层表达力更强 | 小数据上更易过拟合；讲义练习 3 建议与线性层对比 |
| 冻结 encoder 与文本表 | 只训小桥，便宜、不破坏两端能力 | 本节 encoder 是随机初始化的小 ViT，冻结的是"随机特征" |
| CLS pooling | 一个向量对一个 caption | VLM 通常把全部 patch token 投影后送入 LLM |
| 逐对余弦损失 | 简单、动态直观（讲义："so the dynamics are visible"） | 没有负样本，容易坍缩到平均方向；第 62 节改用对比损失 |
| 随机 token caption | 无需下载语料 | 图文之间不存在可学习的对应，"对齐"无从谈起 |
| 每步重算 encoder | 写法直观 | 浪费大量计算；应缓存冻结特征 |
| batch = 1、单样本指标 | 代码最短 | 梯度噪声大，初始/最终损失不可比；应 mini-batch + 全量/留出评估 |
| `_load_module` 失败清理 | 避免残缺模块留在 `sys.modules` | 链式按路径加载仍是脚手架，正式项目应打包 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `try/except` + 重新抛出 | `except Exception: sys.modules.pop(name, None); raise` | 清理后用裸 `raise` 保留原始异常 |
| `dict.pop(key, default)` | `sys.modules.pop(name, None)` | 键不存在时不报错 |
| `@dataclass(frozen=True)` | `class AlignConfig` | 不可变配置 |
| 普通 `@dataclass` | `class TrainStats` | 简单记录结构 |
| 数字分隔符 | `10_000` | 等于 10000，提升可读性 |
| `torch.Generator().manual_seed` | `MockTextEmbedding.__init__` | 局部随机数生成器，不影响全局种子 |
| `**` 幂运算 | `1.0 / dim ** 0.5` | `**` 优先级高于 `/`，即 `1 / sqrt(dim)` |
| `requires_grad_(False)` | `p.requires_grad_(False)` | 原地关闭梯度（下划线 = in-place） |
| 布尔张量转浮点 | `(ids != 0).float()` | 比较得到 bool，再转 0/1 |
| `clamp(min=...)` | `mask.sum(dim=1).clamp(min=1.0)` | 下限截断，防除零 |
| `F.normalize` / `F.cosine_similarity` | `F.normalize(x, dim=-1)` | L2 归一化；直接算余弦 |
| `np.random.default_rng().integers(lo, hi)` | `rng.integers(4, max_len + 1)` | 上界不含 |
| `np.zeros(..., dtype=np.int64)` + 切片赋值 | `ids[:length] = ...` | 先补 0 再填前缀 |
| `torch.from_numpy(...).unsqueeze(0)` | `make_pair` 返回值 | NumPy 转张量并加 batch 维 |
| 元组返回与解包 | `img, ids = pairs[step % cfg.pairs]`；`_, cls = encoder(img)` | `_` 丢弃不需要的返回值 |
| 取模循环 | `step % cfg.pairs` | 循环使用样本 |
| `with torch.no_grad()` | 冻结部分的前向 | 不建计算图 |
| `opt.zero_grad(set_to_none=True)` | 训练循环 | 梯度设为 None |
| 链式比较的 `or` | `if step % 25 == 0 or step == cfg.steps - 1` | 周期打印 + 最后一步 |
| f-string 格式 | `f"{loss.item():.4f}"`、`f"{cos:+.4f}"`、`f"{n_proj:,}"` | 小数、带符号、千分位 |
| 类型注解返回元组 | `def train(cfg) -> tuple[MLPProjector, TrainStats]` | 多返回值的类型 |

---

## 6. 运行结果解读

实际运行（PyTorch CPU，`python3 main.py`，耗时约 14.7 秒）：

```text
training (vision encoder frozen, text table frozen, projector trains):
  step    0  loss 1.0684  cos -0.0684
  step   25  loss 0.9438  cos +0.0562
  step   50  loss 0.9409  cos +0.0591
  step   75  loss 0.7767  cos +0.2233
  step  100  loss 0.7889  cos +0.2111
  step  125  loss 0.7592  cos +0.2408
  step  150  loss 0.9145  cos +0.0855
  step  175  loss 0.8066  cos +0.1934
  step  199  loss 0.7984  cos +0.2016

projector params  : 1,312,256
initial loss      : 1.0684
final loss        : 0.7984
final cosine sim  : +0.2016
loss drop         : 0.2701
  ok: projector learned an alignment direction
```

与讲义"drop from initial loss around 1.07 down to about 0.80 within 200 steps"完全一致。逐项解读：

- **每行的 loss 与 cos 满足 `loss = 1 − cos`**：因为 batch = 1，平均就是单个值。
- **第 0 步约 1**：随机方向在 512 维中几乎正交。
- **75 步后在 0.76–0.91 之间波动**：不同样本的损失差别很大（第 150 步跳回 0.91），说明打印的是单样本损失，而不是稳定的训练曲线。
- **为什么停在 0.8 左右**：我们额外诊断（测验 Q6、Q9）：
  - 32 张图的 CLS 两两余弦最小 0.99997——投影层的输入几乎相同；
  - 训练后 32 个投影输出两两余弦 ≥ 0.9999993，与"平均 caption 方向"余弦 0.998；
  - 在全部 32 对上的平均余弦 0.1867，而任何单一方向能达到的上界是 `‖mean(t̂_i)‖ = 0.1870`。
  
  所以"learned an alignment direction"字面上是对的——学到了**一个**方向，但没有学到任何图文对应关系。
- **全量平均**：前 32 步平均损失 1.005、最后 32 步 0.832，比单点的 1.0684 → 0.7984 更可信。
- **参数 1,312,256**：只有投影层被训练；encoder 的 19.5M 参数与文本表的 2.1M 参数都冻结。

---

## 7. 动手改一改

1. **诊断上界**：按测验 Q9 计算 CLS 两两余弦与单方向上界，确认训练结果贴着上界。
2. **缓存特征 + 全量评估**：实现测验 Q10 的 `train_cached`，报告训练前后全部样本的平均损失与耗时。
3. **讲义练习 1**：把 CLS pooling 换成对 196 个 patch token 取平均（`tokens[:, 1:].mean(dim=1)`），比较 200 步后的全量平均损失。
4. **讲义练习 3**：把 `MLPProjector` 换成单个 `nn.Linear(768, 512)`，比较损失差距（在本节数据上两者都会贴着同一个上界——这本身就是一个有价值的结论）。
5. **有对应关系的数据**：按测验 Q9 第 3 问构造 4 类图像与类专属词表，留出 8 对评估类别检索准确率。
6. **讲义练习 2 / 第 62 节预习**：实现测验 Q11 的对比损失，比较逐对余弦与 InfoNCE 下投影输出的两两余弦（是否仍然坍缩）。

---

## 8. 常见坑

- **只冻结不 `no_grad`**：参数虽不更新，但仍会构建计算图、占用内存；冻结部分的前向应放在 `torch.no_grad()` 中。
- **把优化器建在整个模型上**：`Adam(model.parameters())` 会把冻结参数也传进去（虽然没有梯度不会更新），更清晰的做法是只传要训练的参数。
- **忘记处理 padding**：直接对 `(B, L, D)` 求平均会把 padding 的 embedding 也算进去；本节的 mask 平均池化是正确写法。
- **用单样本损失判断训练效果**：batch = 1 的损失噪声远大于训练带来的变化。
- **"损失下降 = 学到了对齐"**：先检查输入特征是否可区分、数据是否存在对应关系，再看留出集。
- **训练集上的高余弦可能只是记忆**：32 对样本、130 万参数，标准化特征后 full-batch 训练可以把训练集余弦推到 1.0（我们实测），但这对新样本毫无意义。
- **余弦损失的坍缩**：没有负样本时，所有输出指向同一方向也能拿到"还不错"的分数。
- **讲义与代码的 encoder 不一致**：讲义说 86M 冻结 encoder，代码用的是 4 层随机初始化的小 ViT。

---

## 9. 测试在验证什么

测试文件：`code/test_main.py`（8 个测试）。

| 测试类 / 测试 | 验证的性质 | 说明 |
|--------------|-----------|------|
| `TestProjector.test_output_shape` | `(5, 64)` → `(5, 32)` | 投影维度正确 |
| `TestProjector.test_gradient_flows` | 余弦损失反传后 `fc1.weight.grad` 非零 | 投影层可训练、损失可微 |
| `TestTextTable.test_table_is_frozen` | 文本表没有 `requires_grad=True` 的参数 | 冻结生效 |
| `TestTextTable.test_pooling_ignores_padding` | `[1,2,3,4]` 与 `[1,2,3,4,0,0]` 池化结果相同 | mask 平均池化正确 |
| `TestCosineLoss.test_zero_loss_on_identical_vectors` | 相同向量损失 0 | 下界 |
| `TestCosineLoss.test_max_loss_on_antiparallel_vectors` | 反向向量损失 2 | 上界 |
| `TestTrainingLoop.test_loss_drops_over_steps` | 小配置（32×32 图、2 层 ViT、4 对样本、40 步、lr 1e-3）下最终损失 < 初始损失 | 通过 `_train_small` 中**复制的**训练循环实现 |
| `TestPairFixture.test_make_pair_shapes` | 图像 `(1, 3, 224, 224)`、ids `(1, 8)`、取值在 `[0, 128)` | 夹具形状与范围 |

运行方式（在 `code/` 目录下）：

```bash
python3 -m unittest test_main.py -v
# 或
python3 -m pytest -q test_main.py
```

实际运行结果：`8 passed in 2.29s`。

需要注意的问题：

- `test_loss_drops_over_steps` 并没有调用 `train()`（`train` 被导入但未使用），而是在 `_train_small` 中复制了一份循环，并以 `vit_encoder_lesson59_test` 为名**再加载一次**第 59 节模块。`train()` 本身的回归不会被这个测试发现；它比较的也是第 0 步与第 39 步两个不同样本的单次损失。讲义说测试覆盖"the training loop reduces loss between step 0 and step 200"，与实际不符。
- `train()` 难以直接测试，是因为 encoder 配置与 224×224 的 `make_pair` 被写死。测验 Q12 给出了依赖注入的重构方案与直接测试 `train()` 的单元测试（我们在副本上验证通过：同一组 4 个样本的平均损失从 1.120 降到 0.254，且 encoder 参数全部保持冻结）。
- 没有测试验证"训练后 encoder 的参数确实未改变"，也没有任何留出集或"是否坍缩"的检查。
