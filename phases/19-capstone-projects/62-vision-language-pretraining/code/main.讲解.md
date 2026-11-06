# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 62 节 视觉与语言联合 Pretraining ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`cd code && python3 main.py`；测试 `python3 -m unittest test_main.py` ｜ **依赖**：`torch`、`numpy`（第三方）；标准库 `importlib`、`math`、`sys`、`dataclasses`、`pathlib`。**运行时还依赖同级目录** `59-vit-transformer/code/main.py`、`60-projection-layer-modality-align/code/main.py`、`61-cross-attention-fusion/code/main.py`

---

## 1. 这份代码在考察什么

前三节分别做好了 ViT encoder（59）、投影层（60）、cross-attention decoder（61）。这一节把它们接起来，用两个目标联合训练：

1. **InfoNCE 对比损失**（CLIP 式）：图像 CLS 经投影得到图像 embedding，caption 经一个简单的文本 encoder 得到文本 embedding，在 batch 内做 N×N 的双向交叉熵——学会"排序/检索"。
2. **LM 损失**（captioning）：decoder 通过 cross-attention 读取图像 token，做 next-token prediction，padding 不计入——学会"生成"。
3. **可学习温度**：`log_tau` 作为 `nn.Parameter` 与模型一起训练。
4. **多任务组合**：`total = contrast + lm_weight × lm`，用 Adam 训练 50 步，观察两个 loss 都下降。
5. **跨课程复用**：用 `importlib` 按文件路径加载前三节的模块。

> 一句话：**这是 CoCa 式"对比 + captioning"预训练的最小可运行骨架**，重点是"梯度管线接通"，而不是学到真实的视觉-语言对齐——它的模拟语料决定了 LM 下降几乎全部来自文本规律（见第 3.6 节和第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_load_module` + 三个 `_..._mod` | 函数 / 模块对象 | 按路径加载 59/60/61 节的 `main.py`，取出 `ViTConfig`、`VisionEncoder`、`MLPProjector`、`DecoderConfig`、`VisionLanguageDecoder` | 代码复用 |
| `PAD_ID = 0` | 常量 | padding token | LM 掩码 |
| `PretrainConfig` | frozen dataclass | 维度、语料、batch、步数、学习率、`lm_weight`、初始 `log_tau` | 配置 |
| `info_nce_loss` | 函数 | 归一化 → 相似度 × scale → 双向交叉熵 | InfoNCE |
| `lm_loss` | 函数 | 展平后 `cross_entropy(ignore_index=PAD)` | LM 损失 |
| `TextSideEncoder` | `nn.Module` | embedding 查表 + 对非 padding 位置求均值 | 文本 embedding |
| `MultimodalModel` | `nn.Module` | encoder + projector + text encoder + decoder + `log_tau`；`forward` 返回两个 loss 与统计量 | 多任务模型 |
| `make_mock_corpus` | 函数 | 生成 200 对确定性的 (图像, caption) | 模拟数据 |
| `sample_batch` | 函数 | 按下标把若干对拼成 batch | 数据加载 |
| `train` | 函数 | 50 步 Adam 训练，每 5 步打印 | 训练循环 |
| `main` | 函数 | 打印配置、训练、汇总 loss 变化 | 演示 |

数据流：

```text
images (B,3,32,32) ─► VisionEncoder ─► tokens (B,5,128) ─────────────► decoder(cross-attn) ─► logits ─► lm_loss
                                    └► cls (B,128) ─► MLPProjector ─► image_emb (B,128) ─┐
text_ids (B,16) ─► TextSideEncoder ─► text_emb (B,128) ──────────────────────────────────┴► info_nce_loss
total = contrast + lm_weight × lm ─► Adam
```

---

## 3. 逐段精讲

### 3.1 跨课程加载模块

```python
THIS_DIR = Path(__file__).resolve().parent
LESSON_59 = THIS_DIR.parent.parent / "59-vit-transformer" / "code"
...

def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
```

- 三节课的入口文件都叫 `main.py`，不能用普通 `import main`（会撞名，而且本文件自己也叫 `main`）。所以用 `spec_from_file_location` 以**唯一的名字**（`vit_encoder_lesson59` 等）加载。
- `sys.modules[name] = mod` 必须在 `exec_module` **之前**：被加载的文件里有 `@dataclass`，dataclass 装饰器会通过 `sys.modules[cls.__module__]` 查找模块，提前注册才不会出错。
- `if name in sys.modules: return` 保证重复导入（例如测试文件也 import 本模块）时不会重复执行。
- `Path(__file__).resolve().parent.parent`：从 `62-.../code` 回到 `19-capstone-projects`，再拼接兄弟目录。这意味着**本节代码不能脱离仓库目录结构单独运行**。

### 3.2 配置

```python
@dataclass(frozen=True)
class PretrainConfig:
    vision_hidden: int = 128
    projection_hidden: int = 256
    embed_dim: int = 128
    text_vocab: int = 512
    max_text_len: int = 16
    n_pairs: int = 200
    batch_size: int = 16
    steps: int = 50
    lr: float = 5e-4
    lm_weight: float = 1.0
    init_log_tau: float = math.log(1.0 / 0.07)
    seed: int = 0
```

- `init_log_tau = log(1/0.07) ≈ 2.659`：这是 CLIP 的初始化。注意它存的是 **1/τ 的对数**，`exp` 之后是 14.286，是 logit scale（逆温度），不是温度本身。
- `embed_dim = 128` 同时用作联合 embedding 维度**和** decoder 的 `hidden`。

### 3.3 `info_nce_loss`

```python
    n = image_emb.shape[0]
    img_n = F.normalize(image_emb, dim=-1)
    txt_n = F.normalize(text_emb, dim=-1)

    scale = log_tau.exp().clamp(min=1e-3, max=100.0)
    sim = (img_n @ txt_n.T) * scale

    targets = torch.arange(n, device=sim.device)
    loss_i2t = F.cross_entropy(sim, targets)
    loss_t2i = F.cross_entropy(sim.T, targets)
    return (loss_i2t + loss_t2i) * 0.5, sim
```

| 步骤 | 形状 / 数值 |
|------|-----------|
| `img_n`, `txt_n` | `(16, 128)`，每行 L2 范数为 1 |
| `img_n @ txt_n.T` | `(16, 16)`，元素是余弦相似度 ∈ [−1, 1] |
| `× scale` | 初始 scale = 14.286，元素 ∈ [−14.3, 14.3] |
| `targets` | `[0, 1, ..., 15]`：第 i 行的正确答案是第 i 列 |
| `cross_entropy(sim, targets)` | 图→文：每张图在 16 段文本中找自己的 caption |
| `cross_entropy(sim.T, targets)` | 文→图：每段文本在 16 张图中找自己的图 |

- 讲义说这是"八行的 CLIP loss"，与 CLIP 论文伪代码几乎一一对应。
- `clamp(min=1e-3, max=100.0)`：scale 上限 100 与 CLIP 相同，防止温度过小导致 logits 爆炸；被 clamp 时 `log_tau` 梯度为 0。
- ⚠️ 讲义公式写 `S = I Tᵀ / tau`，代码是 `× exp(log_tau)`，所以代码里的 "tau" 其实是 `1/τ`（测验 Q2、Q10）。
- 返回 `sim` 供 `forward` 计算对角/非对角统计。注意这些统计值是**乘过 scale 的**，不是原始余弦。
- 两个方向的 loss 一般不相等（测验 Q4 的手算例子：0.065 vs 1.063），所以要都算。

### 3.4 `lm_loss` 与 `TextSideEncoder`

```python
def lm_loss(logits, target_ids, padding_id=PAD_ID):
    if logits.dim() != 3 or target_ids.dim() != 2:
        raise ValueError(...)
    b, l, v = logits.shape
    flat_logits = logits.reshape(b * l, v)
    flat_target = target_ids.reshape(b * l)
    return F.cross_entropy(flat_logits, flat_target, ignore_index=padding_id)
```

- `F.cross_entropy` 要求 logits 是 `(N, C)`、目标是 `(N,)`，所以先把 batch 和序列维展平：`(16, 15, 512) → (240, 512)`。
- `ignore_index=0`：目标为 PAD 的位置不计 loss，**也不计入平均的分母**。
- 位移（shift）在函数外部完成——docstring 说明"调用方决定哪些是输入、哪些是预测"。

```python
class TextSideEncoder(nn.Module):
    def __init__(self, vocab_size, embed_dim):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=PAD_ID)

    def forward(self, ids):
        x = self.embed(ids)
        mask = (ids != PAD_ID).float().unsqueeze(-1)
        denom = mask.sum(dim=1).clamp(min=1.0)
        return (x * mask).sum(dim=1) / denom
```

- 文本 embedding = 非 padding token 的 embedding **平均值**（masked mean pooling），形状 `(B, 128)`。
- `padding_idx=PAD_ID`：PAD 的 embedding 行初始化为 0 且不更新。即使如此，代码还是显式乘 `mask`，并只除以真实 token 数。
- `clamp(min=1.0)` 防止全 PAD 的序列除以 0。
- 这是一个**极简的词袋**文本 encoder：没有位置信息，也不与 decoder 的 `tok_emb` 共享参数。真实的 CLIP 文本侧是一个完整的 Transformer。

### 3.5 `MultimodalModel`

```python
        vit_cfg = ViTConfig(image_size=32, patch_size=16, hidden=cfg.vision_hidden,
                            depth=2, heads=4, mlp_ratio=2.0)
        self.encoder = VisionEncoder(vit_cfg)
        self.projector = MLPProjector(cfg.vision_hidden, cfg.projection_hidden, cfg.embed_dim)
        self.text_encoder = TextSideEncoder(cfg.text_vocab, cfg.embed_dim)

        dec_cfg = DecoderConfig(hidden=cfg.embed_dim, heads=4, depth=2, mlp_ratio=2.0,
                                text_vocab=cfg.text_vocab, max_text_len=cfg.max_text_len,
                                vision_dim=cfg.vision_hidden,
                                vision_tokens=(32 // 16) ** 2 + 1)
        self.decoder = VisionLanguageDecoder(dec_cfg)
        self.log_tau = nn.Parameter(torch.tensor(cfg.init_log_tau))
```

- 32×32 图像、16×16 patch → `2 × 2 = 4` 个 patch + 1 个 CLS = **5 个图像 token**，每个 128 维。
- 各模块参数量（实测）：encoder 363,776；projector 65,920；text encoder 65,536；decoder 530,944；加上 `log_tau` 1 个，合计 **1,026,177**。
- decoder 的 `vision_dim = cfg.vision_hidden`：说明 memory 是 **ViT 原始 token**，不经过 projector。

```python
    def encode_image(self, images):
        tokens, cls = self.encoder(images)
        return tokens, self.projector(cls)

    def forward(self, images, text_ids):
        memory, image_emb = self.encode_image(images)
        text_emb = self.text_encoder(text_ids)

        contrast, sim = info_nce_loss(image_emb, text_emb, self.log_tau)

        b, l = text_ids.shape
        inputs = text_ids[:, :-1]
        targets = text_ids[:, 1:]
        if inputs.shape[1] == 0:
            lm = torch.tensor(0.0, device=images.device)
        else:
            logits = self.caption_logits(memory, inputs)
            lm = lm_loss(logits, targets, padding_id=PAD_ID)

        diag = sim.diag().mean().item()
        offdiag = (sim.sum() - sim.diag().sum()).item() / max(1, b * b - b)
        stats = {"diag": diag, "off_diag": offdiag, "tau": self.log_tau.exp().item()}
        return contrast, lm, stats
```

- **teacher forcing 位移**：输入 `ids[:, :-1]`（15 个），目标 `ids[:, 1:]`（15 个）。没有 BOS token，所以第一个 caption token 永远不会被预测。
- `if inputs.shape[1] == 0`：长度为 1 的序列没有可预测位置，返回 0 防止空张量报错。
- `diag` / `off_diag`：对角线（正样本）与非对角线（负样本）的平均缩放相似度。训练正常时 `diag − off` 应逐渐变大。
- `.item()` 把统计量转成 Python 浮点，不参与反向传播。
- ⚠️ **梯度流向**（实测，见第 6 节）：
  - LM 损失 → decoder + encoder（经 cross-attention 回到 ViT 的全部 token）；
  - InfoNCE → encoder（经 CLS）+ projector + text encoder + `log_tau`；
  - projector **不**收到 LM 梯度，decoder **不**收到 InfoNCE 梯度。
  讲义表格写 LM 影响 "Encoder + projection + decoder"，与代码不符（测验 Q12）。

### 3.6 模拟语料：`make_mock_corpus`

```python
    for i in range(n_pairs):
        img_seed = seed * 100 + i
        rng_i = np.random.default_rng(img_seed)
        noise = rng_i.standard_normal((3, 32, 32)).astype("float32") * 0.2
        gx, gy = np.meshgrid(np.linspace(0.0, 1.0, 32), np.linspace(0.0, 1.0, 32))
        bias = (i % 7) / 7.0
        img = np.clip(noise + bias, -1.0, 1.0).astype("float32")
        img = torch.from_numpy(img).unsqueeze(0)

        length = min(6 + (i % 8), max_len)
        ids = np.zeros((max_len,), dtype=np.int64)
        base = (i * 17) % (vocab_size - 50)
        for j in range(length):
            ids[j] = 1 + (base + j * 3 + (i % 5)) % (vocab_size - 1)
        pairs.append((img, torch.from_numpy(ids).unsqueeze(0)))
```

- **图像**：每张图是"固定亮度 + 高斯噪声"。亮度只有 7 档（`i % 7`），实测前 7 张图均值为 0.004、0.139、0.282、0.431、0.565、0.708、0.83，第 8 张又回到 0.001。同档图像只靠噪声区分。
- ⚠️ `gx, gy` 计算了却**从未使用**（死代码，可能原本打算加渐变图案）。
- **caption**：长度 6–13；`ids[j] = 1 + (base + 3j + i%5) % 511`，取值范围 `[1, 511]`，永不等于 PAD。实测第 0 条 `[1, 4, 7, 10, 13, 16, 0, ...]`、第 1 条 `[19, 22, 25, 28, 31, 34, 37, 0, ...]`——**每条都是公差 3 的等差数列**。
- ⚠️ 这意味着 LM 只需学会"下一个 = 当前 + 3"就能把 loss 降到接近 0，完全不需要看图。docstring 说 "Caption tokens are correlated with the image seed"，讲义说 "random caption ids"，两种说法都与实际不符。
- 每对数据都带一个 batch 维（`unsqueeze(0)`），方便 `torch.cat` 拼 batch。

### 3.7 训练循环

```python
def train(cfg):
    torch.manual_seed(cfg.seed)
    model = MultimodalModel(cfg).train()
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    corpus = make_mock_corpus(cfg.seed + 1, cfg.n_pairs, cfg.text_vocab, cfg.max_text_len)
    if cfg.batch_size > len(corpus):
        raise ValueError(...)

    rng = np.random.default_rng(cfg.seed + 2)
    for step in range(cfg.steps):
        idx = rng.choice(len(corpus), size=cfg.batch_size, replace=False).tolist()
        imgs, ids = sample_batch(corpus, idx)
        contrast, lm, stats = model(imgs, ids)
        total = contrast + cfg.lm_weight * lm
        opt.zero_grad(set_to_none=True)
        total.backward()
        opt.step()
```

- 每步从 200 对中**无放回**随机抽 16 对；`replace=False` 要求 `batch_size ≤ 语料大小`，所以前面专门检查。
- 三个种子错开（`seed`、`seed+1`、`seed+2`）：模型初始化、语料、采样顺序互不干扰。
- `zero_grad(set_to_none=True)`：把梯度设为 `None` 而不是零张量，省内存，也让"没收到梯度的参数"一目了然。
- 单个 batch 的 loss 噪声很大：日志里 contrast 在 2.36–3.05 之间上下跳，最后一步 2.3622 恰好是低点；最后 10 步均值约 2.54。
- `log_tau` 与其他参数共享学习率 5e-4，50 步只移动了很少（14.286 → 14.060）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 按文件路径加载前三节代码 | 直接复用、不重复造轮子 | 依赖仓库目录结构；生产中会打包成可 import 的包 |
| 对比用 CLS + projector，LM 用 ViT 原始 token | 对比只需全局向量，生成需要 token 级信息 | projector 只被对比损失训练，与讲义描述不符；LLaVA 式做法会把所有 token 投影 |
| 文本侧用 masked mean pooling 的词袋 | 极简、参数少 | 不懂词序；CLIP 用完整 Transformer 文本 encoder |
| 可学习的 `log(1/τ)` + clamp 100 | 照搬 CLIP | 变量名 `log_tau` 容易误解；CLIP 官方叫 `logit_scale` |
| `lm_weight = 1.0` 简单相加 | 多任务最朴素的写法 | 两个 loss 量级不同（3 vs 6.5），实际需要调权重 |
| 无 BOS token | 简单 | 第一个词不被预测，而它恰恰最依赖图像 |
| 200 对确定性模拟语料 | 不需下载、可复现 | caption 是等差数列，LM 可以完全不看图；图像只有 7 档亮度 |
| 50 步、batch 16、单卡 | 几秒跑完 | 对比学习需要大 batch；生产用 all-gather 拿全局负样本 |
| 每步打印单个 batch 的 loss | 简单 | 噪声大，应该看滑动平均或验证集 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `pathlib.Path` 路径运算 | `THIS_DIR.parent.parent / "59-vit-transformer" / "code"` | `/` 拼接路径；`.parent` 取上级目录 |
| `Path(__file__).resolve()` | 文件开头 | 取当前文件的绝对路径 |
| `importlib.util` 动态导入 | `spec_from_file_location`、`module_from_spec`、`spec.loader.exec_module(mod)` | 按文件路径加载模块并起一个自定义名字 |
| `sys.modules` | `sys.modules[name] = mod` | 全局模块缓存；先注册再执行，dataclass 才能找到所属模块 |
| 模块级常量 | `PAD_ID = 0` | 全大写约定为常量 |
| `@dataclass(frozen=True)` + 默认值表达式 | `init_log_tau: float = math.log(1.0 / 0.07)` | 默认值在类定义时计算一次 |
| 用关键字参数新建配置 | 测试里 `PretrainConfig(vision_hidden=32, ...)` | frozen 实例不能改，只能新建（也可用 `dataclasses.replace(cfg, lm_weight=0.0)`） |
| 类型注解返回元组 | `-> tuple[torch.Tensor, torch.Tensor, dict]` | 一次返回多个值 |
| `nn.Parameter` | `self.log_tau = nn.Parameter(torch.tensor(...))` | 把标量注册为可训练参数，会出现在 `model.parameters()` 里 |
| 张量切片 | `text_ids[:, :-1]`、`text_ids[:, 1:]` | 去掉最后一列 / 第一列，实现 next-token 位移 |
| 布尔张量转浮点 | `(ids != PAD_ID).float().unsqueeze(-1)` | 比较得到 bool，再转 0/1 浮点作为 mask |
| `clamp` | `.clamp(min=1e-3, max=100.0)`、`.clamp(min=1.0)` | 限制取值范围 |
| `F.normalize` | `F.normalize(image_emb, dim=-1)` | 沿最后一维做 L2 归一化 |
| `F.cross_entropy(..., ignore_index=)` | `lm_loss` | 内含 log-softmax + NLL；忽略指定目标 |
| `.diag()` / `.T` | `sim.diag().mean()`、`sim.T` | 取对角线 / 转置 |
| NumPy 新式随机数 | `np.random.default_rng(seed)`、`rng.choice(n, size, replace=False)`、`rng.standard_normal(shape)` | 独立的随机数生成器，推荐写法 |
| `np.meshgrid` / `np.linspace` / `np.clip` | `make_mock_corpus` | 网格坐标 / 等间距数列 / 截断（`gx, gy` 未被使用） |
| NumPy ↔ Torch | `torch.from_numpy(img)` | 共享内存地把数组变成张量 |
| 列表推导式 + `torch.cat` | `torch.cat([pairs[i][0] for i in indices], dim=0)` | 沿 batch 维拼接 |
| 字典记录历史 | `history = {"contrast": [], "lm": [], "total": []}` | 每步 `append` |
| f-string 格式符 | `{step:3d}`、`{contrast.item():.4f}`、`{stats['diag']:+.3f}` | 宽度 3 整数；4 位小数；`+` 强制显示正负号 |
| 链式 `if/elif/else` | `main()` 末尾判断两个 loss 是否下降 | 三种结果分别打印 |

---

## 6. 运行结果解读

实际运行（PyTorch CPU，约 4.2 秒）：

```text
  text vocab     : 512
  max text length: 16
  embed dim      : 128
  n pairs        : 200
  batch size     : 16
  steps          : 50
  lm weight      : 1.0
  initial tau    : 14.286          ← 其实是 1/τ，τ = 0.07

training:
  step   0  contrast 3.0456  lm 6.5010  tau 14.286  diag -0.094  off -0.060
  step   5  contrast 2.8772  lm 6.2508  tau 14.250  diag +0.317  off +0.259
  step  10  contrast 2.9886  lm 6.2738  tau 14.218  diag +0.156  off +0.088
  step  15  contrast 2.8854  lm 6.0325  tau 14.188  diag +0.706  off +0.420
  step  20  contrast 2.5979  lm 5.7725  tau 14.160  diag +0.495  off +0.042
  step  25  contrast 2.6557  lm 5.5554  tau 14.138  diag +0.879  off +0.282
  step  30  contrast 2.7214  lm 5.6859  tau 14.117  diag +0.502  off +0.057
  step  35  contrast 2.4358  lm 5.3232  tau 14.095  diag +0.695  off -0.030
  step  40  contrast 2.6289  lm 5.1966  tau 14.078  diag +0.714  off +0.399
  step  45  contrast 2.6681  lm 5.0135  tau 14.065  diag +0.264  off -0.103
  step  49  contrast 2.3622  lm 4.7041  tau 14.060  diag +1.012  off +0.266

contrast loss : 3.0456 -> 2.3622  (drop +0.6834)
lm loss       : 6.5010 -> 4.7041  (drop +1.7969)
ok: both losses decreased
```

逐项解读：

- **初始 contrast 3.0456**：讲义说"从约 ln 16 = 2.77 开始"。实际更高，因为 scale = 14.3 时随机向量的相似度也会被放大，softmax 不是均匀的——我们用随机 `(16,128)` 向量测得 scale = 14.3 时 loss 约 3.19，scale = 1 时约 2.75（接近 ln 16）。
- **初始 lm 6.5010**：均匀基线 `ln 512 = 6.24`，随机初始化的 logits 不完全均匀，所以略高。
- **contrast 下降但抖动大**：单 batch、batch 只有 16。`diag − off` 总体在拉大（step 0 为 −0.03，step 49 为 +0.75），说明正样本相似度开始高于负样本。
- **"tau" 单调下降**：logit scale 从 14.286 降到 14.060，对应真实温度从 0.0700 升到 0.0711——模型在把 softmax 调平一点。
- **lm 稳定下降**：比 contrast 平滑得多，因为它学的是 caption 的等差规律。

我们另外做的验证实验：

| 实验 | 结果 | 结论 |
|------|------|------|
| 只对 LM 反传，看各模块梯度 | encoder 有（范数 0.53）、decoder 有（1.20）、projector / text encoder / `log_tau` 为 `None` | LM 不训练 projector |
| 只对 contrast 反传 | encoder（7.94）、projector（5.46）、text encoder（0.16）、`log_tau`（0.39）有，decoder 为 0 | InfoNCE 不训练 decoder |
| 训练时把图像全部置零 | LM 最后 10 步均值 5.016（正常为 5.004）；contrast 停在约 2.84 | LM 下降与图像无关；contrast 没有图像信号就学不动 |
| 训练后打乱 batch 内图像 | eval LM 4.689 → 4.697；置零 memory 4.748 | decoder 几乎没有利用图像 |
| `lm_weight = 0`（讲义练习 5） | 最终 contrast 2.3603（正常 2.3622） | LM 损失没有拖累排序目标 |
| 训练延长到 300 步 | contrast 约 0.62，LM 约 0.148 | LM 已掌握"+3"规则；contrast 也能记住 200 张图 |

---

## 7. 动手改一改

1. **改名去歧义**：把 `log_tau` 改名为 `logit_scale`，打印时同时输出 `scale` 与 `τ = 1/scale`，让日志与讲义公式一致。
2. **讲义练习 5 + 盲测**：分别用 `lm_weight = 0` 和 `1` 训练，记录 contrast；再加一个"训练时图像全置零"的对照组，确认 LM 的下降不依赖图像。
3. **讲义练习 4（让 caption 依赖图像）**：让 caption 的起始 token 和步长都由 `i % 7`（亮度档）决定，例如 `step = 1 + (i % 7)`；重新做"打乱图像"消融，观察 LM loss 是否出现明显差距。同时在开头加 `<bos>` token，让第一个词也被预测。
4. **讲义练习 1（SigLIP）**：实现 sigmoid 逐对损失（测验 Q11），加可学习的 `t`（初始 log 10）与 `b`（初始 −10），比较 50 步内 contrast 的下降。
5. **让 projector 被两种损失共享**：把 `self.projector` 作用于全部 token，并把 decoder 的 `vision_dim` 改为 `embed_dim`；用梯度检查确认 projector 现在同时收到两种梯度，再比较两种结构的 loss。
6. **讲义练习 2（难负样本）**：记录上一个 batch 中非对角线最大的那一对，在下一个 batch 中加入它，观察 contrast 下降速度。

---

## 8. 常见坑

- **把 logit scale 当温度**：`exp(log_tau) = 14.3` 是 1/τ。调参时方向会完全反掉。
- **只看 loss 下降就以为模型学会了看图**：本节 LM 下降完全来自文本规律；必须做"打乱/置零图像"的消融。
- **忘了双向**：只做 `cross_entropy(sim, targets)` 只训练了图→文检索，文→图会变弱。
- **忘了归一化**：不做 L2 归一化时相似度可以无限放大，loss 被 embedding 范数而不是方向主导。
- **`ignore_index` 与真实 token 冲突**：PAD_ID = 0 时，语料必须保证真实 token 不会是 0（本节用 `1 + ... % (V-1)` 保证）。
- **batch 内假负样本**：同一亮度档的图几乎一样，却被当作负样本；真实数据中同一张图的多个 caption 也会出现这个问题。
- **脱离目录结构运行**：`_load_module` 依赖兄弟目录 59/60/61，单独拷贝本文件会 `FileNotFoundError`。
- **单 batch loss 噪声**：不要因为某一步 loss 升高就判断训练失败，看滑动平均。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m unittest -v test_main.py`。测试用缩小配置 `small_cfg()`（vision 32 维、vocab 64、长度 8、16 对、batch 4）。

| 测试 | 验证的性质 |
|------|-----------|
| `TestInfoNCE.test_zero_loss_on_perfect_diagonal` | `emb = eye(4, 8)`、scale = 100：对角 100、其余 0，loss < 1e-3；`sim` 形状 `(4, 4)` |
| `TestInfoNCE.test_symmetric_across_directions` | 交换图像与文本参数，loss 相同。由于函数本身就是两个方向取平均，这个性质是"构造上成立"的 |
| `TestInfoNCE.test_shape_mismatch_raises` | `(3,4)` 与 `(5,4)` 抛 `ValueError` |
| `TestLMLoss.test_pad_positions_excluded` | 含 2 个 PAD 目标的 4 位置 loss 等于只取前 2 位置的 loss。（测试里定义的 `targets_no_pad` 变量未被使用） |
| `TestModel.test_forward_returns_two_losses` | 随机输入下两个 loss 都是有限值，`stats` 含 `tau` |
| `TestModel.test_training_reduces_total_loss` | 用滑动窗口取 batch 训练 10 步，最后一步 total ≤ 第一步 + 1e-3。阈值宽松，只防"训练发散" |
| `TestCorpus.test_make_mock_corpus_shapes` | 每对图像 `(1,3,32,32)`、caption `(1,10)`，id 在 `[0, 64)` |

实际运行结果：

```text
Ran 7 tests in 1.874s

OK
```

测试没有覆盖：梯度流向（projector 是否收到 LM 梯度）、温度的语义、LM 是否依赖图像。讲义 Tests 一节说测试覆盖"5-step training loop reduces the combined loss"，实际测试跑的是 10 步。
