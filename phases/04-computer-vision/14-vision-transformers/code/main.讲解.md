# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 14 节 Vision Transformers（ViT） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，CPU 几秒跑完） ｜ **依赖**：`torch`（`torch.nn`）；无需联网

---

## 1. 这份代码在考察什么

不到 90 行，从零搭出一个能前向的 ViT，并把每一步的形状打印出来：

1. **图像 → token**：一个 `kernel_size = stride = patch_size` 的卷积 + `flatten` + `transpose`，就把图像变成 Transformer 能吃的 `(batch, 序列长度, 维度)`。
2. **`[CLS]` 与位置编码**：两个 `nn.Parameter`，一个拼在序列最前面，一个加到每个 token 上。
3. **Pre-LN Transformer block**：`x + MSA(LN(x))`、`x + MLP(LN(x))`，借助 `nn.MultiheadAttention` 实现。
4. **规模直觉**：tiny ViT（dim=192, depth=6）约 282 万参数；换成 `dim=768, depth=12, num_heads=12` 就是 ViT-B/16（约 8,657 万参数）——同一份类定义。
5. **形状调试习惯**：`main()` 手动重放前向的前几步并打印形状，这正是讲义练习 1 和 skill 文件"patch/位置编码检查器"的思路。

> 一句话：**ViT = 把图像切成"单词"，然后原封不动地套用 Transformer encoder**；全部视觉相关的代码只有 patch embedding 那一个卷积。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PatchEmbedding` | `nn.Module` | `(N,3,H,W) → (N, num_patches, dim)` | 切 patch + 线性投影 |
| `Block` | `nn.Module` | Pre-LN：LN → 多头 self-attention → 残差；LN → MLP(GELU) → 残差 | Transformer encoder block |
| `ViT` | `nn.Module` | patch → 拼 `[CLS]` → 加位置编码 → `depth` 个 Block → LN → 线性头 | 完整 ViT 分类器 |
| `main()` | 演示入口 | 打印中间形状、参数量、softmax 概率和 | 形状检查 / sanity check |

数据流：`x (2,3,64,64)` → `PatchEmbedding` → `(2,16,192)` → 拼 `[CLS]` → `(2,17,192)` → `+ pos_embed` → 6 × `Block`（形状不变）→ 取第 0 个 token `(2,192)` → `LayerNorm` → `Linear` → `(2,10)`。

---

## 3. 逐段精讲

### 3.1 `PatchEmbedding`：一个卷积完成切块与投影

```python
class PatchEmbedding(nn.Module):
    def __init__(self, in_channels=3, patch_size=16, dim=192, image_size=64):
        super().__init__()
        assert image_size % patch_size == 0
        self.proj = nn.Conv2d(in_channels, dim, kernel_size=patch_size, stride=patch_size)
        self.num_patches = (image_size // patch_size) ** 2

    def forward(self, x):
        x = self.proj(x)
        return x.flatten(2).transpose(1, 2)
```

- **为什么卷积就能"切块"**：步长等于核大小，卷积窗口互不重叠、恰好铺满整张图。每个窗口里的 `16×16×3 = 768` 个像素被一个 `dim × 768` 的权重矩阵线性投影成 `dim` 维向量——这与"先把 patch 拉平，再接 `nn.Linear`"在数学上完全等价，只是用卷积写更简洁、也更快。
- **形状**：`(2,3,64,64)` → `proj` → `(2,192,4,4)` → `flatten(2)`（从第 2 维起展平）→ `(2,192,16)` → `transpose(1,2)` → `(2,16,192)`。
- **为什么要 `transpose`**：卷积输出是"通道在前"，而 `nn.MultiheadAttention(batch_first=True)` 期望 `(batch, seq, dim)`。
- **`assert`**：图像边长必须能被 patch 整除，否则卷积会静默丢掉右侧和底部的残余像素。⚠️ `assert` 在 `python -O` 下会被移除，生产代码应改成 `if ...: raise ValueError(...)`。
- **`num_patches`**：只在构造 `ViT` 时用来确定位置编码的长度。它根据**构造时**的 `image_size` 算出，这意味着模型只能接受这一种分辨率（见 3.3 末尾）。

### 3.2 `Block`：Pre-LN Transformer 编码层

```python
class Block(nn.Module):
    def __init__(self, dim, num_heads, mlp_ratio=4, dropout=0.0):
        super().__init__()
        self.ln1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(dim, num_heads, dropout=dropout, batch_first=True)
        self.ln2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(
            nn.Linear(dim, dim * mlp_ratio),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim * mlp_ratio, dim),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        normed = self.ln1(x)
        a, _ = self.attn(normed, normed, normed, need_weights=False)
        x = x + a
        x = x + self.mlp(self.ln2(x))
        return x
```

- **Pre-LN**：LayerNorm 放在子层**之前**，残差相加之后不再归一化。残差主干 `x` 只做加法，梯度可以沿恒等路径直达浅层，所以深层网络无需 warmup 也能稳定训练（讲义 "Why pre-LN"）。
- **`nn.MultiheadAttention`**：内部完成 Q/K/V 投影（合并为一个 `in_proj_weight`，形状 `(3·dim, dim)`）、按头切分、`softmax(QKᵀ/√d_head)V`、拼接各头并做输出投影 `out_proj`。`dim=192, num_heads=3` 时每个头 64 维；`dim` 必须能被 `num_heads` 整除。
- **`normed` 只算一次**：讲义版本写的是 `self.attn(self.ln1(x), self.ln1(x), self.ln1(x), ...)`，同一个 LayerNorm 算了 3 次。结果相同，但代码版本省了两次计算；三个参数是同一个对象时，PyTorch 也更容易识别出这是 self-attention。
- **`need_weights=False`**：不返回 attention 权重矩阵，省显存，也允许 PyTorch 使用融合的 attention 内核；返回元组的第二项为 `None`，用 `_` 丢弃。
- **MLP**：`dim → 4·dim → GELU → dim`，即讲义里的"Linear(d → 4d) → GELU → Linear(4d → d)"。GELU 是 Transformer 的标配激活，比 ReLU 更平滑。
- **`dropout=0.0`**：默认关闭。ViT 小数据训练常用 dropout 或 stochastic depth（DeiT 配方）来正则化，这里为了简单没有加。

### 3.3 `ViT`：组装

```python
class ViT(nn.Module):
    def __init__(self, image_size=64, patch_size=16, in_channels=3,
                 num_classes=10, dim=192, depth=6, num_heads=3, mlp_ratio=4):
        super().__init__()
        self.patch = PatchEmbedding(in_channels, patch_size, dim, image_size)
        num_patches = self.patch.num_patches
        self.cls_token = nn.Parameter(torch.zeros(1, 1, dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches + 1, dim))
        self.blocks = nn.ModuleList([Block(dim, num_heads, mlp_ratio) for _ in range(depth)])
        self.ln = nn.LayerNorm(dim)
        self.head = nn.Linear(dim, num_classes)
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)

    def forward(self, x):
        x = self.patch(x)
        cls = self.cls_token.expand(x.size(0), -1, -1)
        x = torch.cat([cls, x], dim=1)
        x = x + self.pos_embed
        for blk in self.blocks:
            x = blk(x)
        return self.head(self.ln(x[:, 0]))
```

- **`nn.Parameter`**：把张量注册为可训练参数，会出现在 `parameters()` 里、被优化器更新、随 `state_dict` 保存。`cls_token` 形状 `(1,1,dim)`，`pos_embed` 形状 `(1, 17, dim)`（16 个 patch + 1 个 CLS）。
- **截断正态初始化**：`trunc_normal_(std=0.02)` 是 ViT/timm 的惯例——小幅随机值打破对称性，又不会淹没 patch 特征。先用 `torch.zeros` 占位，再原地初始化（下划线结尾的函数表示原地修改）。
- **`expand` 而非 `repeat`**：`expand(x.size(0), -1, -1)` 把 `(1,1,dim)` "视为" `(N,1,dim)`，不复制内存，`-1` 表示该维保持不变。之后 `torch.cat` 会生成新张量，梯度也能正确累加回同一个 `cls_token`。
- **位置编码靠广播**：`(N,17,dim) + (1,17,dim)`，所有图像共享同一组位置向量。
- **`nn.ModuleList`**：用普通 Python 列表装子模块，PyTorch 不会注册它们（参数不会被统计和优化）；`ModuleList` 才会。这里配合 `for blk in self.blocks` 逐层调用。
- **读出**：`x[:, 0]` 取每张图的第 0 个 token（`[CLS]`）→ `(N, dim)` → 最终 `LayerNorm` → 线性头。Pre-LN 结构中残差主干从未被归一化，所以最后这个 LN 必不可少。
- ⚠️ 分辨率被"焊死"：`pos_embed` 长度在构造时固定为 17。输入 96×96 会得到 37 个 token，与 `pos_embed` 无法广播而报错。换分辨率需要对位置编码做 2D 插值（见测验 Q10）。
- ⚠️ 简化之处：没有 dropout / stochastic depth、没有权重初始化的细节（timm 还会专门初始化 Linear 层），也没有 DeiT 的蒸馏 token。

### 3.4 `main()`：手动重放前向并检查形状

```python
    patches = vit.patch(x)
    print(f"[shapes] input {tuple(x.shape)} -> patches {tuple(patches.shape)}")
    cls = vit.cls_token.expand(x.size(0), -1, -1)
    tokens = torch.cat([cls, patches], dim=1)
    # ...
    tokens = tokens + vit.pos_embed
    # ...
    logits = vit(x)
    # ...
    with torch.no_grad():
        probs = logits.softmax(-1)
    print(f"[probs row 0 sum]: {probs[0].sum().item():.4f}")
```

- 前三步是把 `ViT.forward` 的开头**手动重放**一遍，逐步打印形状——比在 `forward` 里塞 `print` 更干净，也正是讲义练习 1 的要求。
- `logits = vit(x)` 才是真正的完整前向，`nn.Module.__call__` 会调用 `forward`。
- `softmax(-1)` 在最后一维（类别维）上归一化，每行概率之和应为 1——一个最基础的 sanity check。
- `torch.no_grad()` 在这里只包住了 softmax；前面的 `vit(x)` 仍会构建计算图。演示中无所谓，真实推理应把整个前向都放进 `no_grad()`（或 `torch.inference_mode()`），并调用 `vit.eval()`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用卷积做 patch embedding | 一行完成切块 + 投影，等价于 Linear | 无重叠 patch 丢失 patch 间的局部关联；部分模型改用重叠或卷积 stem |
| 可学习的 1D 位置编码 | 简单，训练会自动适应 2D 结构 | 长度固定，换分辨率要插值；MAE 等使用固定的 2D sin-cos 编码 |
| `[CLS]` token 读出 | 沿用 BERT 惯例 | 也可用 patch token 的全局平均池化，效果相近 |
| Pre-LN | 深层稳定、无需 warmup | 需要最终 LN；残差幅值随深度增长 |
| 直接用 `nn.MultiheadAttention` | 少写代码，可用融合内核 | 想改 attention（如加相对位置偏置、窗口 attention）就得自己实现 |
| tiny 配置（192 维 × 6 层） | CPU 上可跑，约 2.8M 参数 | 小数据从零训练 ViT 效果一般，实际应加载 timm 预训练权重 |
| `assert` 检查整除 | 尽早暴露配置错误 | `-O` 模式下失效，生产用显式异常 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类继承与 `super()` | `class ViT(nn.Module)`、`super().__init__()` | 先初始化父类，子模块和参数才能被注册 |
| 默认参数 | `def __init__(self, image_size=64, patch_size=16, ...)` | 调用时可只传需要改的参数 |
| `assert` | `assert image_size % patch_size == 0` | 条件为假时抛 `AssertionError`；`python -O` 会跳过 |
| 取余 `%`、整除 `//`、幂 `**` | `(image_size // patch_size) ** 2` | 64 // 16 = 4，4² = 16 |
| 列表推导式 | `[Block(dim, num_heads, mlp_ratio) for _ in range(depth)]` | 生成 `depth` 个相互独立的 Block；`_` 表示不使用的循环变量 |
| 元组解包与 `_` | `a, _ = self.attn(...)` | 只要第一个返回值 |
| `for` 遍历模块 | `for blk in self.blocks: x = blk(x)` | `ModuleList` 可像列表一样迭代 |
| 关键字参数 | `nn.MultiheadAttention(dim, num_heads, dropout=dropout, batch_first=True)` | 按名字传参更清晰 |
| 方法链 | `x.flatten(2).transpose(1, 2)` | 每个方法返回新张量，可以连续调用 |
| 负数下标与切片 | `x[:, 0]`、`softmax(-1)` | `:` 取全部；`0` 取第 0 个；`-1` 表示最后一维 |
| `with` 上下文管理器 | `with torch.no_grad():` | 代码块内不记录梯度 |
| 生成器表达式 | `sum(p.numel() for p in vit.parameters())` | 统计参数总数 |
| f-string 格式符 | `{...:,}`、`{...:.4f}` | 千位分隔符；保留 4 位小数 |
| `tuple(...)` | `tuple(x.shape)` | `torch.Size` 转普通元组，打印更简洁 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 以下形状和参数量由代码确定性推出（参数量已逐模块计算）：

```text
[shapes] input (2, 3, 64, 64) -> patches (2, 16, 192)
[shapes] tokens with CLS: (2, 17, 192)
[shapes] after pos embed: (2, 17, 192)
[shapes] output logits:   (2, 10)
[params] total: 2,822,602
[probs row 0 sum]: 1.0000
```

逐行解读：

- **patches (2, 16, 192)**：64/16 = 4，4×4 = 16 个 patch，每个投影到 192 维。
- **tokens with CLS (2, 17, 192)**：序列最前面多了 1 个 `[CLS]`。
- **after pos embed**：加位置编码不改变形状，`(1,17,192)` 广播到 batch。
- **output logits (2, 10)**：每张图 10 个类别分数。
- **params 2,822,602**：
  - patch 卷积 147,648；`[CLS]` 192；位置编码 3,264；
  - 6 个 Block × 444,864 = 2,669,184（每个 Block 中 attention 148,224、MLP 295,872、两个 LN 共 768）；
  - 最终 LN 384；分类头 1,930。
  - 与讲义"约 2.8M"一致；约 95% 的参数在 Block 里，其中 MLP 又占 2/3。
- **probs row 0 sum 1.0000**：softmax 归一化正确。随机初始化的模型输出的 10 个概率大致均匀（约 0.1 上下）。

---

## 7. 动手改一改

1. **ViT-B/16 参数量**：用 `ViT(image_size=224, patch_size=16, num_classes=1000, dim=768, depth=12, num_heads=12)` 构造并打印参数量，应为 86,567,656（约 86.6M）。
2. **GAP 读出**：把 `x[:, 0]` 改成 `x[:, 1:].mean(dim=1)`（对 patch token 取平均），比较两种读出的输出形状和参数量（应完全相同）。
3. **Post-LN 对比**：写一个 `PostLNBlock`，在相同学习率、无 warmup 的条件下把 depth 加到 12，比较两种 block 在合成数据上前几百步的 loss 曲线。
4. **位置编码插值**：实现 `resize_pos_embed`，让 64×64 训练的模型接受 96×96 的输入，并打印插值前后 `pos_embed` 的形状。
5. **看 attention 图**：把 `need_weights=False` 改为 `True` 并返回权重，取最后一层 `[CLS]` 对 16 个 patch 的 attention，reshape 成 4×4 可视化。
6. **（进阶）讲义练习 3**：遮住 75% 的 patch，只让 encoder 处理可见 token，加一个 2 层的小 decoder 重建像素，实现迷你 MAE。

---

## 8. 常见坑

- **忘记 `transpose`**：卷积输出是 `(N, dim, L)`，直接送进 `batch_first=True` 的 attention 会把 dim 当成序列长度，若碰巧 `dim == L` 甚至不会报错。
- **子模块放在普通 list 里**：参数不会被注册，优化器看不到，模型"训练"了却永远不更新。要用 `nn.ModuleList`。
- **换分辨率直接加载权重**：`pos_embed` 长度不匹配；如果使用 `strict=False` 静默跳过，模型会带着随机位置编码"正常运行"，效果却很差。
- **`dim` 不能被 `num_heads` 整除**：`nn.MultiheadAttention` 构造时直接报错。
- **推理时没有 `eval()` 和 `no_grad()`**：本例 dropout=0 所以无影响，但一旦开启 dropout，输出就会随机，而且会白白构建计算图。
- **`expand` 后原地修改**：`expand` 得到的是共享内存的视图，对它做原地写入会报错或产生意外结果；需要可写副本时用 `repeat` 或 `.clone()`。
