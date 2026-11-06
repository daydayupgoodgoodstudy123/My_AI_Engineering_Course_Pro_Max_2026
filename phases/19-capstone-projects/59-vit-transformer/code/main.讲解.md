# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 59 节 Vision Transformer Encoder ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m unittest test_main.py` 或 `python3 -m pytest -q test_main.py` ｜ **依赖**：第三方 `torch`（CPU 即可）；`numpy` 被导入但未使用；**要求**同级目录 `58-vision-encoder-patches/code/main.py` 存在（运行时按路径加载）

---

## 1. 这份代码在考察什么

第 58 节把图像变成了 197 个彼此"互不相识"的 token。本节在其上堆叠 12 层 pre-LN Transformer，让每个 token 通过自注意力获得全图上下文，并用 CLS token 汇总整张图。它考察：

1. **Transformer block 的标准写法**：合并 qkv 投影、拆头、缩放点积注意力、合头、输出投影、GELU FFN、两条残差。
2. **pre-LN 结构**：LayerNorm 放在子层之前，残差主干保持干净，最后加一个 LayerNorm。
3. **ViT-Base 规模直觉**：12 × 12 × 768，约 85M 参数在 encoder，前端只占 0.6M。
4. **可观测的健全性检查**：逐层 CLS 范数、注意力行和、从 CLS 反传到 patch 投影的梯度。
5. **跨课程复用**：用 `importlib` 加载第 58 节的前端。

> 一句话：**一个 `Block` 类写对，堆 12 次，再加一个 LayerNorm，就是所有开源 VLM 视觉塔的骨架**（讲义："the engine room of every modern vision-language model"）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_load_front_end_module` | 函数 | 按路径加载第 58 节 `main.py`，注册为 `vision_front_end_lesson58` | 跨课程复用 |
| `ViTConfig` | 冻结 dataclass | 尺寸、hidden、depth、heads、mlp_ratio、dropout；派生 `head_dim`；转成 `FrontEndConfig` | 配置 |
| `MultiHeadSelfAttention` | `nn.Module` | 合并 qkv → 拆头 → `softmax(QKᵀ/√d)` → `@V` → 合头 → 输出投影；可保存注意力 | 多头自注意力 |
| `FeedForward` | `nn.Module` | `Linear(d, 4d)` → GELU → `Linear(4d, d)` | FFN |
| `Block` | `nn.Module` | `x + attn(ln1(x))`，`x + ffn(ln2(x))` | pre-LN block |
| `ViT` | `nn.Module` | `ModuleList` 堆叠 depth 个 block + 最终 LayerNorm | encoder 主体 |
| `VisionEncoder` | `nn.Module` | 前端 + ViT，返回 `(tokens, cls)` | 完整视觉编码器 |
| `count_params` | 函数 | 统计参数元素总数 | 规模估算 |
| `main` | 函数 | 打印配置、参数、形状、逐层 CLS 范数、注意力与梯度检查 | 演示 |

数据流：`synthesize_image` → `(1, 3, 224, 224)` → `VisionFrontEnd` → `(1, 197, 768)` → 12 × `Block` → `LayerNorm` → `tokens (1, 197, 768)` → `cls = tokens[:, 0]` → `(1, 768)`。

---

## 3. 逐段精讲

### 3.1 加载第 58 节的前端

```python
THIS_DIR = Path(__file__).resolve().parent
LESSON_58 = THIS_DIR.parent.parent / "58-vision-encoder-patches" / "code"

def _load_front_end_module():
    import importlib.util
    name = "vision_front_end_lesson58"
    if name in sys.modules:
        return sys.modules[name]
    src = LESSON_58 / "main.py"
    spec = importlib.util.spec_from_file_location(name, src)
    ...
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
```

- `pathlib.Path` 的 `/` 运算符拼接路径，比 `os.path.join` 更易读；`resolve()` 得到绝对路径。
- 先查 `sys.modules` 缓存，避免重复执行第 58 节的模块代码（第 60 节也会间接加载它）。
- 与第 57 节相同的套路：同名 `main.py` 用唯一模块名按路径加载。与第 60 节不同的是，这里加载失败时**没有**从 `sys.modules` 中移除半初始化的模块（第 60 节的 `_load_module` 做了 `try/except` 清理）。

### 3.2 配置 `ViTConfig`

```python
@dataclass(frozen=True)
class ViTConfig:
    image_size: int = 224
    patch_size: int = 16
    in_channels: int = 3
    hidden: int = 768
    depth: int = 12
    heads: int = 12
    mlp_ratio: float = 4.0
    dropout: float = 0.0

    @property
    def head_dim(self) -> int:
        if self.hidden % self.heads != 0:
            raise ValueError(...)
        return self.hidden // self.heads
```

- 默认值就是 ViT-Base/16：`head_dim = 768 / 12 = 64`。
- `head_dim` 的整除检查是**惰性**的：`ViTConfig(hidden=65, heads=4)` 构造时不报错，第一次访问 `.head_dim` 才报错（测试 `test_invalid_head_dim_rejected` 正是这样写的）。若想在构造时就报错，可以用 `__post_init__`。
- `front_end_config()` 把共享字段转成第 58 节的 `FrontEndConfig`，保证两边的 `hidden`、`patch_size` 一致。

### 3.3 多头自注意力

```python
        self.qkv = nn.Linear(cfg.hidden, cfg.hidden * 3, bias=True)
        self.out = nn.Linear(cfg.hidden, cfg.hidden, bias=True)
        self.drop = nn.Dropout(cfg.dropout)
        self.scale = 1.0 / math.sqrt(cfg.head_dim)
        self.last_attn: torch.Tensor | None = None

    def forward(self, x, store_attn=False):
        b, n, d = x.shape
        h = self.cfg.heads
        hd = self.cfg.head_dim

        qkv = self.qkv(x).reshape(b, n, 3, h, hd).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]

        scores = (q @ k.transpose(-2, -1)) * self.scale
        attn = F.softmax(scores, dim=-1)
        if store_attn:
            self.last_attn = attn.detach()

        out = attn @ v
        out = out.transpose(1, 2).reshape(b, n, d)
        out = self.out(out)
        out = self.drop(out)
        return out
```

形状追踪（B = 1，N = 197，D = 768，h = 12，hd = 64）：

| 步骤 | 形状 |
|------|------|
| `self.qkv(x)` | `(1, 197, 2304)` |
| `.reshape(b, n, 3, h, hd)` | `(1, 197, 3, 12, 64)` |
| `.permute(2, 0, 3, 1, 4)` | `(3, 1, 12, 197, 64)` |
| `q, k, v` | 各 `(1, 12, 197, 64)` |
| `k.transpose(-2, -1)` | `(1, 12, 64, 197)` |
| `scores` | `(1, 12, 197, 197)` |
| `attn @ v` | `(1, 12, 197, 64)` |
| `.transpose(1, 2).reshape(b, n, d)` | `(1, 197, 768)` |

- **合并 qkv**：一次 `768 → 2304` 的矩阵乘代替三次 `768 → 768`，数学等价、更高效（一个大 GEMM 比三个小的快）。第 10 阶段第 04 节的 NumPy 版本用的是三个独立矩阵。
- `scale = 1/√64 = 1/8`：缩放点积，防止 softmax 饱和（测验 Q17）。
- **没有 mask**：视觉 encoder 是双向的（讲义："No mask"）。讲义练习 3 要求加 `attn_mask`（测验 Q10）。
- `attn.detach()`：保存一份不参与梯度的注意力，供可视化或测试；默认 `store_attn=False` 不保存，避免占内存。
- `transpose(1, 2)` 之后张量不连续，`reshape` 会自动复制；用 `view` 会报错。
- dropout 只作用在输出投影之后，**注意力权重本身没有 dropout**（timm 等实现通常还有 `attn_drop`）；默认 `dropout = 0.0`，两者都不生效。
- 这段手写注意力与 `F.scaled_dot_product_attention(q, k, v)` 数值一致（我们实测最大误差 1e-7），生产中应换成后者以使用 FlashAttention 等融合 kernel。

### 3.4 FFN 与 Block

```python
class FeedForward(nn.Module):
    def __init__(self, cfg):
        inner = int(cfg.hidden * cfg.mlp_ratio)
        self.fc1 = nn.Linear(cfg.hidden, inner)
        self.fc2 = nn.Linear(inner, cfg.hidden)
        self.drop = nn.Dropout(cfg.dropout)

    def forward(self, x):
        x = self.fc1(x)
        x = F.gelu(x)
        x = self.fc2(x)
        x = self.drop(x)
        return x


class Block(nn.Module):
    def __init__(self, cfg):
        self.ln1 = nn.LayerNorm(cfg.hidden, eps=1e-6)
        self.attn = MultiHeadSelfAttention(cfg)
        self.ln2 = nn.LayerNorm(cfg.hidden, eps=1e-6)
        self.ffn = FeedForward(cfg)

    def forward(self, x, store_attn=False):
        x = x + self.attn(self.ln1(x), store_attn=store_attn)
        x = x + self.ffn(self.ln2(x))
        return x
```

- FFN：`768 → 3072 → 768`，`F.gelu` 默认使用精确的 erf 形式（不是 tanh 近似）。`int(hidden * mlp_ratio)` 允许非整数比例（测试用 2.0）。
- `LayerNorm(eps=1e-6)`：与 ViT/timm 的惯例一致（PyTorch 默认 1e-5）。
- **pre-LN**：LN 只作用于子层输入，残差主干 `x` 本身不被归一化。后果是主干范数随深度增长（demo：CLS 0.53 → 35.8），因此 `ViT` 末尾必须有一个 `norm`。
- 每个 block 参数：qkv 1,771,776 + out 590,592 + fc1 2,362,368 + fc2 2,360,064 + 2 个 LN 3,072 = **7,087,872**（测验 Q1）。

### 3.5 堆叠：`ViT` 与 `VisionEncoder`

```python
class ViT(nn.Module):
    def __init__(self, cfg):
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.depth)])
        self.norm = nn.LayerNorm(cfg.hidden, eps=1e-6)

    def forward(self, x, store_attn=False):
        for block in self.blocks:
            x = block(x, store_attn=store_attn)
        return self.norm(x)


class VisionEncoder(nn.Module):
    def __init__(self, cfg=None):
        self.cfg = cfg or ViTConfig()
        self.front = VisionFrontEnd(self.cfg.front_end_config())
        self.vit = ViT(self.cfg)

    def forward(self, x, store_attn=False):
        tokens = self.front(x)
        tokens = self.vit(tokens, store_attn=store_attn)
        cls = tokens[:, 0]
        return tokens, cls
```

- `nn.ModuleList`：必须用它（而不是普通 list）保存子模块，否则 `parameters()`、`.to(device)`、`state_dict()` 都看不到这些 block。
- 列表推导式创建的是 12 个**独立**的 block（各有各的权重）；如果写成 `[Block(cfg)] * 12` 就会变成同一个 block 共享 12 次。
- `cfg or ViTConfig()`：`None` 时使用默认配置。
- 返回 `(tokens, cls)`：`tokens` 给需要所有 patch 的下游（第 61 节 cross-attention），`cls` 给需要单个图像向量的下游（第 60 节投影层）。`tokens[:, 0]` 取出第 0 个位置，形状 `(B, 768)`。
- `store_attn` 一路传到每个 block，所以 `encoder(img, store_attn=True)` 后每层的 `attn.last_attn` 都可用（测验 Q9）。

### 3.6 `main()`：五组检查

1. **参数量**：前端 591,360、ViT 85,056,000、合计 85,647,360。
2. **前向形状**：`(1, 197, 768)` 与 `(1, 768)`。
3. **逐层 CLS 范数**：手动循环 `encoder.vit.blocks`，每两层打印一次，最后过 `encoder.vit.norm`。这段代码在 `no_grad` 下复现了 `ViT.forward` 的逻辑。
4. **注意力检查**：

   ```python
   encoder.vit.blocks[0].attn(encoder.front(img), store_attn=True)
   attn = encoder.vit.blocks[0].attn.last_attn
   ```

   ⚠️ 这里直接把前端输出喂给 `attn`，**绕过了 `ln1`**，看到的不是真实前向中的注意力；且没有包在 `no_grad` 里。行和 1.000000 说明 softmax 正确，但"CLS 行标准差 0.0000"主要是绕过 LN 造成的（实测 std ≈ 2.1e-5；加上 `ln1` 后约 1.0e-3）。正确做法见测验 Q9。
5. **梯度检查**：新建一个 `enc2`（训练模式，dropout=0 所以无影响），以 `(cls * cls).sum()` 为损失反传，确认 `patch.proj.weight` 和 `cls_token` 都收到非零梯度——证明 CLS 输出依赖于所有 patch（通过注意力）且梯度能穿过 12 层流回前端。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合并 qkv 投影 | 一次大矩阵乘更快，与 timm/HF 权重布局一致 | 加载外部权重时要确认 `(3, h, hd)` 的拆分顺序 |
| 手写 softmax 注意力 | 每一步可见，便于教学与保存注意力图 | 显式存储 `N × N` 矩阵；生产用 `F.scaled_dot_product_attention` |
| pre-LN + 最终 LN | 深层训练稳定 | 主干范数随深度增长；需要最终 LN |
| `LayerNorm(eps=1e-6)` | 与 ViT 惯例一致 | 与 PyTorch 默认值不同，转换权重时要注意 |
| 无 mask | 视觉 encoder 双向 | 复用为解码器 block 时需要扩展（练习 3） |
| CLS pooling | 简单、一个向量即可表示整图 | 丢失空间细节；VLM 通常使用全部 patch token |
| `store_attn` 开关 | 按需保存注意力，默认零开销 | 保存的是最后一次调用的结果，多次前向会被覆盖 |
| 随机初始化、无预训练权重 | 演示结构 | 注意力接近均匀、CLS 无语义；真实使用需加载预训练权重 |
| dropout 只在输出投影与 FFN 之后 | 简化 | 没有 attention dropout、drop path（stochastic depth），大模型训练常用后者 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `pathlib.Path` | `THIS_DIR.parent.parent / "58-vision-encoder-patches" / "code"` | 面向对象的路径操作，`/` 拼接 |
| 函数内 `import` | `def _load_front_end_module(): import importlib.util` | 只在需要时导入 |
| `importlib.util.spec_from_file_location` | 加载第 58 节 | 按路径加载同名模块 |
| `@dataclass(frozen=True)` + `@property` | `ViTConfig.head_dim` | 不可变配置 + 惰性校验的派生字段 |
| 返回另一个 dataclass | `def front_end_config(self) -> FrontEndConfig` | 配置之间的转换 |
| 类型注解 `torch.Tensor \| None` | `self.last_attn: torch.Tensor \| None = None` | 实例属性的可选类型 |
| `nn.Linear` / `nn.LayerNorm` / `nn.Dropout` | `self.qkv = nn.Linear(D, 3 * D)` | PyTorch 基础层 |
| `nn.ModuleList` | `nn.ModuleList([Block(cfg) for _ in range(cfg.depth)])` | 让子模块列表被正确注册 |
| `F.softmax` / `F.gelu` | `F.softmax(scores, dim=-1)` | 函数式 API，无参数 |
| 负数维度索引 | `k.transpose(-2, -1)`、`dim=-1` | 从最后一维往前数 |
| `reshape` + `permute` | `.reshape(b, n, 3, h, hd).permute(2, 0, 3, 1, 4)` | 拆分并重排维度 |
| 批量矩阵乘 `@` | `q @ k.transpose(-2, -1)` | 前面的维度当作 batch |
| `.detach()` | `self.last_attn = attn.detach()` | 从计算图中分离 |
| 元组返回值 | `return tokens, cls`；`tokens, cls = encoder(img)` | 多返回值与解包 |
| `x or default` | `self.cfg = cfg or ViTConfig()` | `None` 时使用默认值 |
| 生成器表达式求和 | `sum(p.numel() for p in module.parameters())` | 参数计数 |
| `enumerate(..., start=1)` | `for i, block in enumerate(encoder.vit.blocks, start=1)` | 下标从 1 开始 |
| f-string 格式 | `f"{i:2d}"`、`f"{x:.3e}"`、`f"{n:,}"` | 宽度、科学计数法、千分位 |
| `.eval()` 与 `torch.no_grad()` | `VisionEncoder(cfg).eval()`；`with torch.no_grad():` | 推理模式；关闭梯度 |
| `.backward()` 与 `.grad` | `loss.backward()`；`enc2.front.patch.proj.weight.grad.norm()` | 反向传播与读取梯度 |

---

## 6. 运行结果解读

实际运行（PyTorch CPU，`python3 main.py`，耗时约 3.8 秒）：

```text
  depth x heads   : 12 x 12 (head dim 64)
front-end params : 591,360
vit params       : 85,056,000
total params     : 85,647,360

fixture image    : (1, 3, 224, 224)
output tokens    : (1, 197, 768)
cls shape        : (1, 768)
cls L2 norm      : 27.713

layer-by-layer CLS norm trace:
  layer  0 (after front end) : cls norm 0.534
  layer  2                    : cls norm 13.693
  layer  4                    : cls norm 19.958
  layer  6                    : cls norm 24.630
  layer  8                    : cls norm 28.794
  layer 10                    : cls norm 32.474
  layer 12                    : cls norm 35.802
  final LN                   : cls norm 27.713

attention sanity:
  block 0 head 0 CLS row sum (should be 1.0) : 1.000000
  block 0 head 0 CLS row stddev              : 0.0000

gradient sanity:
  patch.proj.weight grad norm                : 1.198e-03
  front.cls_token grad norm                  : 3.862e-05
  ok: gradients flow from CLS back through the encoder
```

逐项解读：

- **85,647,360**：讲义说"about 86M"。差额来自口径：本节用 0 参数的正弦位置、没有分类头；按可学习位置（151,296）+ 1000 类头（769,000）计算是 86,567,656（测验 Q8）。
- **CLS 范数 0.534 → 35.8**：pre-LN 残差主干不断累加子层输出。前两层增长最快（从几乎为 0 的 CLS 开始，注意力把 patch 信息"灌"进来）。
- **最终 LN 后 27.713 = √768**：LN 在初始化（γ=1、β=0）时把每个 token 标准化为方差 1，范数恒等于 `sqrt(768)`（测验 Q2）。讲义说"stabilizes at the final LayerNorm"，本质是重新标准化，所以"最终 cls L2 norm"本身不携带信息。
- **行和 1.000000**：softmax 正确。
- **stddev 0.0000**：绕过 `ln1` + 随机初始化 → 几乎均匀（实际约 2.1e-5）。按测验 Q9 的正确方式测，各层 CLS 行的熵约 5.270–5.280，非常接近均匀分布的 `ln 197 = 5.283`。
- **梯度**：patch 投影梯度 1.2e-3、CLS 梯度 3.9e-5，都非零。CLS 参数的梯度小，是因为它的原始量级只有 0.53，而且要先经过多层 LN 的"缩放"才影响输出。

---

## 7. 动手改一改

1. **修正注意力检查**：按测验 Q9 从完整前向中取每层注意力，打印每层 CLS 行的熵与最大权重。
2. **讲义练习 3**：为注意力与 block 加 `attn_mask`（测验 Q10），写一个"修改最后一个 token 不影响前面输出"的因果性测试。
3. **讲义练习 1**：加 4 个 register tokens（测验 Q11），确认输出形状与参数量（+4 × 768）。
4. **讲义练习 2**：实现 post-LN 版本的 `Block`（`x = ln1(x + attn(x))`），去掉最终 LN，比较逐层 CLS 范数的变化（post-LN 每层输出范数都约为 27.7）。
5. **讲义练习 4**：用 `torch.profiler` 或 `time.perf_counter` 测 batch 1/8/64 的前向耗时，再把注意力换成 `F.scaled_dot_product_attention` 比较速度。
6. **换规模**：实例化 ViT-L（1024/24/16），验证测验 Q12 的参数量 303,099,904。

---

## 8. 常见坑

- **绕过 LayerNorm 观察注意力**：demo 的注意力检查就是反例；可视化要从完整前向中取。
- **用普通 list 保存 block**：参数不会被注册，优化器看不到它们，`.to("cuda")` 也不会移动它们。
- **`[Block(cfg)] * 12`**：12 个引用指向同一个 block，变成权重共享。
- **合头时漏 `transpose`**：直接 `out.reshape(b, n, d)` 不报错，但会把不同 token 的数据混在一起。
- **qkv 拆分顺序与外部权重不一致**：本节是 `(3, h, hd)`；有的实现是 `(h, 3, hd)`，加载前需转换。
- **以为 pre-LN 不需要最终 LN**：主干范数随深度增长，下游会看到尺度漂移。
- **把讲义的"cross-attention 用 causal mask"当真**：第 61 节讲义明确 cross-attention 不加 mask。
- **用随机初始化的 encoder 做"语义"实验**：注意力接近均匀，CLS 不携带图像语义；第 60 节的对齐实验就受此影响。
- **`head_dim` 的校验是惰性的**：错误的 `hidden/heads` 组合要等到访问 `head_dim` 时才报错。

---

## 9. 测试在验证什么

测试文件：`code/test_main.py`（8 个测试），使用小配置 `ViTConfig(image_size=32, patch_size=16, hidden=64, depth=2, heads=4, mlp_ratio=2.0)`，32/16 = 2×2 = 4 个 patch + CLS = 5 个 token。

| 测试类 / 测试 | 验证的性质 | 说明 |
|--------------|-----------|------|
| `TestSubLayers.test_attention_preserves_shape` | 注意力输出形状与输入相同 | `(2, 5, 64)` |
| `TestSubLayers.test_attention_rows_sum_to_one` | 保存的注意力每行和为 1（`atol=1e-5`） | softmax 沿 key 维 |
| `TestSubLayers.test_feed_forward_expansion` | `fc1.out_features == hidden × mlp_ratio`，`fc2` 回到 hidden | 64 × 2 = 128 |
| `TestBlock.test_block_residual_wired` | block 输出与输入不同、形状不变 | 只能说明"block 做了点什么"，不能真正证明残差连接存在 |
| `TestViTStack.test_full_stack_shape` | 4 层堆叠后 tokens `(3, 5, 64)`、cls `(3, 64)` | 完整 encoder 形状 |
| `TestViTStack.test_gradient_reaches_patch_projection` | 以 `cls.pow(2).sum()` 反传，patch 投影收到非零梯度 | 证明 CLS 依赖于 patch（通过注意力） |
| `TestEncoderConfig.test_head_dim_divides` | 64 / 4 = 16 | |
| `TestEncoderConfig.test_invalid_head_dim_rejected` | `hidden=65, heads=4` 访问 `head_dim` 时抛 `ValueError` | 惰性校验 |

运行方式（在 `code/` 目录下）：

```bash
python3 -m unittest test_main.py -v
# 或
python3 -m pytest -q test_main.py
```

实际运行结果：`8 passed in 1.24s`。

与讲义描述的差异：讲义说测试覆盖"a single block ... is invariant to input batch size"和"zero input still produces non-zero output via the CLS token"，但测试文件中**没有**批大小不变性的测试，残差测试用的是随机输入而不是零输入。我们另外验证了批大小不变性：同一张图单独前向与在 batch=3 中前向，输出最大差 7.2e-7，性质成立，只是没有被测试固定下来。一个更有力的残差测试是：把 `attn.out` 和 `ffn.fc2` 的权重与 bias 全部置零，此时 block 应退化为恒等映射，`out` 应与 `x` 完全相等。
