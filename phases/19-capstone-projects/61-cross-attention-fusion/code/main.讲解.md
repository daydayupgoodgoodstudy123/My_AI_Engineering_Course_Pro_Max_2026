# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 61 节 Cross-Attention 融合 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`cd code && python3 main.py`；测试 `python3 -m unittest test_main.py` ｜ **依赖**：`torch`（第三方，CPU 即可）；其余为标准库 `math`、`dataclasses`

---

## 1. 这份代码在考察什么

这份代码搭出一个 Flamingo 形状的 **late-fusion vision-language decoder**：文本 token 走自己的 decoder，每个 block 里通过 cross-attention 去"看"一组固定的图像 memory token。重点考察：

1. **cross-attention 的写法**：Q 来自文本（`q_proj: hidden→hidden`），K/V 来自图像（`kv_proj: vision_dim→2·hidden`），输出长度跟着 query 走。
2. **mask 纪律**：文本 self-attention 用 `(Nt, Nt)` 下三角因果 mask；cross-attention 不加 mask。
3. **三子层 pre-LN block**：self-attention → cross-attention → FFN，每个子层一个 LayerNorm 和一条残差。
4. **图像侧 KV cache 的接口**：`project_memory` / `build_kv_cache` 把图像 K/V 投影抽出来，可以预先算好再传入。
5. **形状防御**：mask 形状、batch 不一致、KV cache 形状、文本过长都显式 `raise ValueError`。

> 一句话：**用不到 300 行 PyTorch 把"文本问、图像答"的 cross-attention 和它的 mask/缓存约定写清楚**。同时要注意它的 KV cache 只是"接口演示"，并没有真正的逐 token 生成。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DecoderConfig` | frozen dataclass | 超参数；`head_dim` 属性顺带校验整除 | 配置 |
| `causal_mask` | 函数 | 返回 `(L, L)` 下三角布尔张量，True = 可看 | 因果 mask |
| `CausalSelfAttention` | `nn.Module` | 合并 `qkv` 投影、拆头、mask、softmax、合头、输出投影 | 文本 self-attention |
| `CrossAttention` | `nn.Module` | `q_proj` + `kv_proj`，支持传入 `kv_cache` | cross-attention |
| `FeedForward` | `nn.Module` | `hidden → 4·hidden → hidden`，GELU | FFN |
| `DecoderBlock` | `nn.Module` | 三个 pre-LN 子层 + 残差 | decoder block |
| `VisionLanguageDecoder` | `nn.Module` | token/位置 embedding → 4 个 block → LN → LM head；`build_kv_cache` | 完整 decoder |
| `synth_memory` / `synth_text` | 函数 | 用固定种子生成随机图像 memory 和文本 ID | 模拟输入 |
| `main` | 函数 | 打印配置、参数量、mask、logits 形状、cache 对比、逐位置范数 | 演示 |
| `test_main.py` | 测试 | 9 个单元测试（见第 9 节） | 验证 |

数据流：`text_ids (B,Nt)` → `tok_emb + pos_emb (B,Nt,256)` → 4 × `DecoderBlock(x, memory (B,197,256), causal_mask)` → `LayerNorm` → `head` → `logits (B,Nt,1024)`。

---

## 3. 逐段精讲

### 3.1 配置：`DecoderConfig`

```python
@dataclass(frozen=True)
class DecoderConfig:
    hidden: int = 256
    heads: int = 8
    depth: int = 4
    mlp_ratio: float = 4.0
    text_vocab: int = 1024
    max_text_len: int = 32
    vision_dim: int = 256
    vision_tokens: int = 197
    dropout: float = 0.0

    @property
    def head_dim(self) -> int:
        if self.hidden % self.heads != 0:
            raise ValueError(...)
        return self.hidden // self.heads
```

- `frozen=True`：实例不可修改，配置一旦创建就固定，避免训练中途被意外改动。
- `head_dim = 256 / 8 = 32`。校验放在 `@property` 里，**每次访问时**才检查；创建一个非法配置（如 `hidden=100, heads=8`）本身不会报错，直到第一次访问 `head_dim` 时才抛出。
- `vision_tokens = 197`：ViT-B/16 在 224×224 图像上的 `14×14 = 196` 个 patch + 1 个 CLS token。注意这个字段只被 `main()` 用来生成 memory，模型本身不依赖它——模型可以接收任意 Nv。
- `vision_dim` 与 `hidden` 分开：允许视觉 encoder 的输出维度与文本 decoder 不同，由 `kv_proj` 负责把 `vision_dim` 映射到 `hidden`。

### 3.2 因果 mask

```python
def causal_mask(length: int) -> torch.Tensor:
    return torch.tril(torch.ones(length, length, dtype=torch.bool))
```

- `torch.tril` 保留主对角线及以下：`mask[i, j] = True` 当且仅当 `j ≤ i`，表示"位置 i 可以看位置 j"。
- 约定是 **True = 允许**。这与 PyTorch `nn.MultiheadAttention` 的 `attn_mask`（布尔 True = 屏蔽）恰好相反，混用时非常容易写反。
- 对角线为 True 保证每一行至少有一个可见位置，后面用 `-inf` 填充时不会出现整行 −∞ 导致的 NaN。

### 3.3 `CausalSelfAttention`：合并 QKV 投影

```python
        b, n, d = x.shape
        h, hd = self.cfg.heads, self.cfg.head_dim
        qkv = self.qkv(x).reshape(b, n, 3, h, hd).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]

        scores = (q @ k.transpose(-2, -1)) * self.scale
        if mask is not None:
            if mask.shape != (n, n):
                raise ValueError(...)
            scores = scores.masked_fill(~mask.unsqueeze(0).unsqueeze(0), float("-inf"))
        attn = F.softmax(scores, dim=-1)
        out = (attn @ v).transpose(1, 2).reshape(b, n, d)
        return self.drop(self.out(out))
```

形状追踪（B=2、n=10、hidden=256、H=8、hd=32）：

| 步骤 | 形状 |
|------|------|
| `self.qkv(x)` | `(2, 10, 768)` |
| `.reshape(b, n, 3, h, hd)` | `(2, 10, 3, 8, 32)` |
| `.permute(2, 0, 3, 1, 4)` | `(3, 2, 8, 10, 32)`：把"Q/K/V"维提到最前 |
| `q, k, v` | 各 `(2, 8, 10, 32)` |
| `scores` | `(2, 8, 10, 10)` |
| `~mask.unsqueeze(0).unsqueeze(0)` | `(1, 1, 10, 10)`，广播到 batch 与头维 |
| `(attn @ v).transpose(1, 2).reshape(b, n, d)` | `(2, 10, 256)` |

- 合并的 `qkv` 线性层（`256 → 768`）与三个独立线性层数学上等价，但一次大矩阵乘更高效（GPT-2 也这样写）。
- `self.scale = 1/√32`：缩放点积，防止 softmax 饱和。
- `masked_fill(~mask, -inf)`：对**取反后**为 True 的位置（未来位置）填 −∞，softmax 后这些位置权重为 0。
- `mask` 是可选的：传 `None` 就**完全不因果**。我们实测：不传 mask 时修改第 4 个位置的输入，第 0 个位置的输出变化约 0.17——即发生了"偷看未来"。`DecoderBlock` 把 `text_mask` 设为必填参数，从调用方向上堵住了这个口子。
- `self.drop` 作用在输出投影之后（residual dropout），而不是注意力权重上；默认 `dropout=0.0`，所以实际不生效。

### 3.4 `CrossAttention`：Q 与 KV 分开投影

```python
        self.q_proj = nn.Linear(cfg.hidden, cfg.hidden, bias=True)
        self.kv_proj = nn.Linear(cfg.vision_dim, cfg.hidden * 2, bias=True)
        self.out = nn.Linear(cfg.hidden, cfg.hidden, bias=True)

    def project_memory(self, memory):
        if memory.dim() != 3:
            raise ValueError(...)
        b, nv, _ = memory.shape
        h, hd = self.cfg.heads, self.cfg.head_dim
        kv = self.kv_proj(memory).reshape(b, nv, 2, h, hd).permute(2, 0, 3, 1, 4)
        return kv[0], kv[1]
```

- 与 self-attention 的关键差异：**Q 的输入是文本 `x`，K/V 的输入是图像 `memory`**，所以投影必须分成两个线性层，且 `kv_proj` 的输入维是 `vision_dim`。
- `project_memory` 输出 `k, v` 各 `(B, H, Nv, hd) = (2, 8, 197, 32)`。把它单独抽成方法，是为了能在解码开始时预先计算并缓存。

```python
    def forward(self, x, memory, kv_cache=None):
        if x.dim() != 3:
            raise ValueError(...)
        if memory.shape[0] != x.shape[0]:
            raise ValueError(f"batch mismatch: text {x.shape[0]} vs memory {memory.shape[0]}")
        b, nt, d = x.shape
        h, hd = self.cfg.heads, self.cfg.head_dim

        q = self.q_proj(x).reshape(b, nt, h, hd).transpose(1, 2)
        if kv_cache is None:
            k, v = self.project_memory(memory)
        else:
            k, v = kv_cache
            expected = (b, h, memory.shape[1], hd)
            if k.shape != expected or v.shape != expected:
                raise ValueError(...)

        scores = (q @ k.transpose(-2, -1)) * self.scale
        attn = F.softmax(scores, dim=-1)
        out = (attn @ v).transpose(1, 2).reshape(b, nt, d)
        return self.drop(self.out(out))
```

| 步骤 | 形状 |
|------|------|
| `q` | `(2, 8, 10, 32)` |
| `k`, `v` | `(2, 8, 197, 32)` |
| `scores` | `(2, 8, 10, 197)`：每个文本位置对每个图像 token 一个分数 |
| `softmax(dim=-1)` | 在 197 个图像 token 上归一化 |
| `attn @ v` | `(2, 8, 10, 32)` |
| 输出 | `(2, 10, 256)`——长度跟着 query |

- **没有 mask**：讲义 "Why no mask on cross-attention"——单图 + caption 时图像完全可见。
- 传入 `kv_cache` 时仍然需要 `memory`：只是用 `memory.shape[1]` 来校验 cache 的 Nv，并做 batch 校验。真正的生产实现通常允许只传 cache 不传 memory。
- ⚠️ 讲义说 "shape mismatch between text and image streams raises a clear `ValueError`"，但代码只校验了**batch 维**。如果 memory 的最后一维不是 `vision_dim`（例如 128），我们实测抛出的是 PyTorch 的 `RuntimeError: mat1 and mat2 shapes cannot be multiplied (394x128 and 256x512)`。
- ⚠️ 讲义的 `DecoderBlock` 片段写的是 `cross_attn(..., mask=cross_mask)`，代码里 `CrossAttention.forward` **没有 mask 参数**，`DecoderBlock.forward` 也没有 `cross_mask`。做讲义练习 2（交错多图）时需要自己加上。

### 3.5 `FeedForward` 与 `DecoderBlock`

```python
class FeedForward(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        inner = int(cfg.hidden * cfg.mlp_ratio)
        self.fc1 = nn.Linear(cfg.hidden, inner)
        self.fc2 = nn.Linear(inner, cfg.hidden)

    def forward(self, x):
        return self.fc2(F.gelu(self.fc1(x)))


class DecoderBlock(nn.Module):
    def forward(self, x, memory, text_mask, kv_cache=None):
        x = x + self.self_attn(self.ln1(x), mask=text_mask)
        x = x + self.cross_attn(self.ln2(x), memory, kv_cache=kv_cache)
        x = x + self.ffn(self.ln3(x))
        return x
```

- FFN：`256 → 1024 → 256`，GELU 激活（与 GPT-2 一致）。
- block 是三子层 **pre-LN**：每个子层先 LayerNorm 再计算，最后加回残差主干。顺序是"先看自己说过的话，再看图，再逐位置变换"——这与原始 Transformer decoder（masked self-attn → cross-attn → FFN）的顺序相同。
- `LayerNorm(eps=1e-6)`：比 PyTorch 默认的 1e-5 小，是 ViT 系代码的常见取值。
- 讲义提到 Flamingo 在 cross-attention 残差上有可学习的 tanh gate，这里是"canonical baseline"，**没有 gate**（讲义练习 1 要求加上，见测验 Q11）。

### 3.6 `VisionLanguageDecoder`：组装与 `build_kv_cache`

```python
    def build_kv_cache(self, memory):
        cache = []
        for block in self.blocks:
            k, v = block.cross_attn.project_memory(memory)
            cache.append((k, v))
        return cache

    def forward(self, text_ids, memory, use_cache=False):
        if text_ids.dim() != 2:
            raise ValueError(...)
        b, nt = text_ids.shape
        if nt > self.cfg.max_text_len:
            raise ValueError(...)

        positions = torch.arange(nt, device=text_ids.device)
        x = self.tok_emb(text_ids) + self.pos_emb(positions).unsqueeze(0)
        mask = causal_mask(nt).to(text_ids.device)
        cache = self.build_kv_cache(memory) if use_cache else [None] * len(self.blocks)

        for block, kv in zip(self.blocks, cache):
            x = block(x, memory=memory, text_mask=mask, kv_cache=kv)

        x = self.norm(x)
        return self.head(x)
```

- 位置 embedding 是**可学习的绝对位置**（`nn.Embedding(32, 256)`），所以文本长度上限是 32，超过就 `ValueError`（否则 `pos_emb` 会索引越界）。
- 图像 memory **没有在 decoder 里加位置信息**——默认假设视觉 encoder（ViT）已经在 token 内部编码了位置。
- 每个 block 的 `cross_attn.kv_proj` 是**独立的参数**，所以 KV cache 是"每层一份"，列表长度 = depth = 4。
- `[None] * len(self.blocks)`：不使用缓存时给每层传 `None`，让 `zip` 写法保持一致。
- LM head `Linear(256, 1024, bias=False)` 与 `tok_emb` **不共享权重**（没有 weight tying）。
- ⚠️ **KV cache 只是接口演示**：`build_kv_cache` 在每次 `forward` 调用内部重新计算，与 `use_cache=False` 做的是完全相同的计算，所以对比结果 drift 恰好为 0。代码中没有逐 token 生成循环，图像 K/V 实际上没有被"跨 decode step 复用"；文本侧也没有 self-attention 的 KV cache。真正复用的写法见测验 Q10。

参数量（实测 4,746,752，可逐项手算）：

| 部分 | 计算 | 参数量 |
|------|------|-------|
| `tok_emb` | 1024 × 256 | 262,144 |
| `pos_emb` | 32 × 256 | 8,192 |
| 每个 block：3 个 LN | 3 × 2 × 256 | 1,536 |
| 每个 block：self-attn | (256×768+768) + (256×256+256) | 263,168 |
| 每个 block：cross-attn | (256×256+256) + (256×512+512) + (256×256+256) | 263,168 |
| 每个 block：FFN | (256×1024+1024) + (1024×256+256) | 525,568 |
| 4 个 block 合计 | 4 × 1,053,440 | 4,213,760 |
| 最终 LN | 2 × 256 | 512 |
| `head` | 256 × 1024 | 262,144 |
| **合计** | | **4,746,752** |

cross-attention 让每个 block 多出 263,168 + 512（一个 LN）参数，约占 block 的 25%。

### 3.7 模拟输入与 `main()`

```python
def synth_memory(batch, n_tokens, dim, seed):
    gen = torch.Generator().manual_seed(seed)
    return torch.randn(batch, n_tokens, dim, generator=gen)

def synth_text(batch, length, vocab, seed):
    gen = torch.Generator().manual_seed(seed + 1)
    return torch.randint(low=0, high=vocab, size=(batch, length), generator=gen)
```

- 用**独立的 `torch.Generator`** 而不是全局种子，保证输入数据与模型初始化（`torch.manual_seed(0)`）互不干扰，任何时候调用结果都一样。
- memory 是标准正态随机数，代表"冻结视觉 encoder 的输出"——讲义 "mock vision encoder output"。

`main()` 依次打印：配置 → 参数量 → 输入形状 → 10×10 因果 mask 左上角 → 两条路径的 logits 形状与最大差 → block 0 cross-attention 的逐位置输出范数。

```python
    block = decoder.blocks[0]
    ln_x = block.ln2(decoder.tok_emb(text_ids) + decoder.pos_emb(torch.arange(10)))
    with torch.no_grad():
        cross_out = block.cross_attn(ln_x, memory)
    norms = cross_out[0].norm(dim=-1).tolist()
```

- ⚠️ 标题写 "(head 0, sample 0)"，但 `cross_out[0]` 是 **sample 0** 在输出投影之后的 `(10, 256)` 向量，范数是在全部 256 维上算的，与 head 0 无关。
- ⚠️ 这里 `ln2` 的输入是 embedding 本身，**跳过了 self-attention 残差**；真实前向中 `ln2` 的输入是 `x + self_attn(ln1(x))`。所以打印值只是示意。
- `ln_x` 在 `no_grad` 外计算，会建立不必要的计算图（不影响结果）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| Late fusion（cross-attention）而非拼接 | 文本流干净、图像 K/V 可只算一次 | 每 block 多一个子层；生产（Flamingo）只在部分层插 cross-attention 并冻结 LM |
| Q 与 KV 分开投影，`kv_proj` 输入维 = `vision_dim` | 两种模态维度可以不同 | 无 |
| self-attention 用合并 `qkv` | 一次矩阵乘更快 | 与 cross 的写法不对称，读者需注意 |
| 布尔 mask，True = 允许 | 与 `tril` 直觉一致 | 与 `nn.MultiheadAttention` 约定相反，混用易错 |
| cross-attention 不加 mask | 单图 + caption 无泄漏风险 | 不支持 padding、交错多图、无图样本；生产需 key padding mask |
| 无 tanh gate | 保持"canonical baseline" | 接到冻结 LM 上训练时初期可能破坏 LM；Flamingo 用 0 初始化的 gate |
| `build_kv_cache` 在 `forward` 内构建 | 接口简单、便于对比测试 | 没有真正跨 step 复用；生产在 prefill 时构建一次，decode 复用 |
| 可学习绝对位置，长度上限 32 | 简单 | caption 长度受限；生产常用 RoPE |
| 大量 `ValueError` 形状校验 | 让 mask/形状错误立即暴露 | 未校验 `vision_dim`，那种错误仍是 `RuntimeError` |
| 随机 memory、随机文本、无训练 | 只演示形状与数据流 | 不能说明模型学会了 grounding |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值，旧版本 Python 也能写 `torch.Tensor \| None` |
| `@dataclass(frozen=True)` | `class DecoderConfig` | 自动生成 `__init__` 等；`frozen` 让实例只读 |
| `@property` | `def head_dim(self)` | 像属性一样访问方法：`cfg.head_dim` |
| 类型注解 | `def forward(self, x: torch.Tensor, mask: torch.Tensor \| None = None) -> torch.Tensor` | `X \| None` 表示可选；只是提示，不做运行时检查 |
| 返回元组的注解 | `-> tuple[torch.Tensor, torch.Tensor]` | 内置泛型写法（Python 3.9+） |
| `nn.Module` 子类 | `class CrossAttention(nn.Module)` + `super().__init__()` | 注册子模块与参数；必须先调用父类构造 |
| 调用模块 | `self.qkv(x)`、`block(x, ...)` | 调用 `__call__`，内部会执行 `forward` 及钩子 |
| `nn.ModuleList` | `nn.ModuleList([DecoderBlock(cfg) for _ in range(cfg.depth)])` | 让列表里的子模块参数被正确注册 |
| 元组解包 | `b, n, d = x.shape`、`q, k, v = qkv[0], qkv[1], qkv[2]` | 一次取多个值 |
| `reshape` / `permute` / `transpose` | `.reshape(b, n, 3, h, hd).permute(2, 0, 3, 1, 4)` | 改形状 / 任意重排维度 / 交换两个维度 |
| 负数维度 | `k.transpose(-2, -1)`、`softmax(dim=-1)` | 从最后一维往前数 |
| 布尔取反与广播 | `~mask.unsqueeze(0).unsqueeze(0)` | `~` 对布尔张量逐元素取反；`unsqueeze` 加维度以便广播 |
| `masked_fill` | `scores.masked_fill(~mask, float("-inf"))` | 把条件为 True 的位置替换成指定值 |
| f-string | `f"batch mismatch: text {x.shape[0]} vs memory {memory.shape[0]}"`、`{n_params:,}`、`{drift:.6e}`、`{i:2d}` | 插值；千分位；科学计数法 6 位；宽度 2 的整数 |
| 条件表达式 | `cache = self.build_kv_cache(memory) if use_cache else [None] * len(self.blocks)` | 一行 if/else；`[None] * n` 生成重复列表 |
| `zip` | `for block, kv in zip(self.blocks, cache)` | 并行遍历两个序列 |
| `with torch.no_grad()` | `main()` 中 | 上下文管理器：关闭梯度记录，省内存 |
| `.eval()` | `VisionLanguageDecoder(cfg).eval()` | 切换到推理模式（关闭 dropout） |
| 独立随机数生成器 | `torch.Generator().manual_seed(seed)` | 不影响全局随机状态 |
| 生成器表达式 | `sum(p.numel() for p in decoder.parameters())` | 不建中间列表直接求和 |
| `.tolist()` / `.item()` | `mask[:5, :5].int().tolist()`、`.max().item()` | 张量转 Python 列表 / 标量 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被测试 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3 + PyTorch CPU，约 1.8 秒）：

```text
============================================================
CROSS-ATTENTION FUSION DECODER
============================================================
  hidden          : 256
  heads           : 8 (head dim 32)
  depth           : 4
  text vocab      : 1024
  max text length : 32
  vision tokens   : 197
  vision dim      : 256

decoder params  : 4,746,752          ← 与第 3.6 节手算一致

text_ids shape  : (2, 10)
memory shape    : (2, 197, 256)      ← 196 patch + 1 CLS

causal mask shape : (10, 10)
causal mask top-left 5x5:
  1 0 0 0 0
  1 1 0 0 0
  1 1 1 0 0
  1 1 1 1 0
  1 1 1 1 1                          ← 下三角，True=可看

logits shape    : (2, 10, 1024)
logits cached   : (2, 10, 1024)
max drift cache vs uncached : 0.000000e+00   ← 两条路径执行完全相同的运算
  ok: KV cache path matches uncached

cross-attention output norm per text position (head 0, sample 0):
  pos  0  norm 0.774
  pos  1  norm 0.764
  ...
  pos  7  norm 0.806
  pos  8  norm 0.786
  pos  9  norm 0.767

done.
```

逐项解读：

- **logits `(2, 10, 1024)`**：每个样本、每个文本位置一个词表分布，与讲义描述一致。
- **drift 恰好 0**：`use_cache=True` 只是把同一个 `project_memory` 调用提前，浮点运算完全相同。这个检查验证的是"接口等价"，不是"生成加速"。
- **逐位置范数都在 0.75–0.81**：未训练、随机 memory 下，注意力在 197 个图像 token 上几乎均匀，各位置输出相似。标签中的 "head 0" 不准确（实际是全部 256 维、输出投影之后），输入也跳过了 self-attention。

我们另外做的验证：

| 实验 | 结果 | 说明 |
|------|------|------|
| 改变第 9 个文本 token | 位置 0–8 logits 变化 0.0，位置 9 变化约 2.11 | 因果 mask 生效 |
| 改变 memory 的第 100 个图像 token | 所有文本位置 logits 都变化（约 0.0055） | cross-attention 无 mask，每个位置都看整张图 |
| self-attention 传 `mask=None` | 修改位置 4，位置 0 输出变化约 0.17 | 不传 mask 会泄漏未来 |
| memory 最后一维传 128 | `RuntimeError: mat1 and mat2 shapes cannot be multiplied` | 未做 `vision_dim` 校验 |
| KV cache 的 Nv 传 196 | `ValueError: kv_cache must be (B,H,Nv,hd)=(2, 8, 197, 32)...` | cache 形状校验生效 |

---

## 7. 动手改一改

1. **讲义练习 1（tanh gate）**：写 `GatedDecoderBlock`，在 cross 残差上乘 `torch.tanh(self.gate)`，gate 初始为 0。用两份不同的 memory 验证输出相同；再反向传播，观察 `gate.grad ≠ 0` 而 `cross_attn` 参数梯度为 0（测验 Q11）。
2. **真正的图像 KV cache**：写一个贪心 caption 生成循环，`build_kv_cache` 只在循环外调用一次；用 `time.perf_counter` 比较"每步重建 cache"和"只建一次"在 Nv = 576、生成 30 个 token 时的耗时（测验 Q10）。
3. **讲义练习 2（交错多图 mask）**：给 `CrossAttention.forward` 加 `mask` 参数（`(B, Nt, Nv)` 布尔），在 softmax 前 `masked_fill`；处理全屏蔽行（输出置 0），并写测试验证"段 1 的输出不受图 0 影响"。
4. **讲义练习 3（开销对比）**：在 `Nt=64, Nv=576` 下分别用 `torch.profiler` 或计时测 self-attention 与 cross-attention，验证分数矩阵 4,096 vs 36,864（9 倍）的差距如何反映在耗时上。
5. **补齐形状校验**：在 `project_memory` 中加入 `memory.shape[-1] != cfg.vision_dim` 的 `ValueError`，让讲义"shape mismatch raises a clear ValueError"名副其实，并补一个测试。
6. **讲义练习 5（Q-Former 风格）**：增加一组 `nn.Parameter(torch.randn(32, hidden))` 的可学习 query，让它们 cross-attend 到 197 个图像 token 得到 32 个压缩 token，再把这 32 个 token 作为 decoder 的 memory，对比 cross-attention 的分数矩阵大小。

---

## 8. 常见坑

- **mask 语义写反**：本文件 True = 可看、用 `~mask` 填 −∞；`nn.MultiheadAttention` 的布尔 `attn_mask` 是 True = 屏蔽。混用会让模型只看未来。
- **给 cross-attention 套因果 mask**：Nt ≠ Nv 时形状根本对不上；即使碰巧相等，也会错误地禁止文本看后半张图。
- **以为 drift = 0 就证明 KV cache 有效**：它只证明两条路径等价；性能收益要在逐 token 生成循环里体现。
- **全屏蔽行导致 NaN**：交错多图时第一张图之前的文本整行被屏蔽，softmax 得 NaN，并污染整个 batch 的 loss。
- **合头时漏 `transpose(1, 2)`**：直接 `reshape(b, nt, d)` 不会报错，但会把不同头、不同位置的数据混在一起。
- **超过 `max_text_len`**：位置 embedding 只有 32 行，生成循环里要提前停止或截断。
- **把 `vision_tokens` 当成模型约束**：模型可以接收任意 Nv，`vision_tokens` 只是演示数据的大小；真正要匹配的是 `vision_dim`。
- **同时零初始化 gate 和 cross 参数**：两者梯度互相乘 0，永远学不动；只把 gate 置 0。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m unittest -v test_main.py`。测试统一使用缩小的配置 `small_cfg()`（hidden 64、4 头、2 层、vocab 128、max_len 16、vision_dim 64、Nv 20），保证毫秒级跑完。

| 测试 | 验证的性质 |
|------|-----------|
| `TestCausalMask.test_shape` | `causal_mask(7)` 形状 `(7, 7)`、dtype 为 `torch.bool` |
| `TestCausalMask.test_lower_triangular` | 与 `torch.tril(ones)` 逐元素相等，即下三角 |
| `TestCrossAttention.test_output_shape_independent_of_key_length` | Nv = 10 和 Nv = 50 时输出都是 `(2, 6, hidden)`——输出长度跟 query 走 |
| `TestCrossAttention.test_kv_cache_matches_uncached` | 先 `project_memory` 再传 `kv_cache` 与不传的结果 `allclose(atol=1e-5)` |
| `TestCrossAttention.test_batch_mismatch_raises` | 文本 batch 2、memory batch 3 时抛 `ValueError` |
| `TestSelfAttention.test_rejects_wrong_mask_shape` | 序列长 5 却传 `(4, 4)` mask 时抛 `ValueError` |
| `TestDecoder.test_forward_shape` | 完整 decoder 输出 `(2, 8, text_vocab)` |
| `TestDecoder.test_cache_path_matches` | `use_cache=True/False` 两条路径 logits 一致 |
| `TestDecoder.test_rejects_too_long_input` | 长度 `max_text_len + 1` 时抛 `ValueError` |

实际运行结果：

```text
Ran 9 tests in 0.022s

OK
```

测试没有覆盖的点：因果性本身（"改未来 token 不影响过去"，见第 6 节我们的补充实验）、`vision_dim` 不匹配、真正的逐步解码复用。讲义 Tests 一节说"shape mismatch between text and image streams raises a clear ValueError"，实际测试只覆盖了 batch 维不一致。
