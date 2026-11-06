# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 05 节 LLaVA 与视觉指令微调 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码围绕 LLaVA 的"最简单连接方式"做三件事：

1. **2 层 MLP projector**：手写 Linear → GELU → Linear，把 16 个 16 维"ViT patch"逐个投影到 24 维"LLM 空间"，并统计参数量。对应讲义 The architecture 中的 `1024 → 4096 → 4096`。
2. **LLaVA prompt 模板**：拼出带 `<image>` 占位符的 SYSTEM / USER / ASSISTANT 文本，估算文本 token 数，再计算 576 个视觉 token 在 2k / 8k / 32k / 128k 上下文中的占比。对应讲义 The prompt format 与"576 tokens at 2048 context"。
3. **AnyRes 的 token 成本**：按"网格块数 × 576 + 缩略图 576"计算不同分辨率的视觉 token 数。对应讲义 LLaVA-NeXT 一节。

> 一句话：**LLaVA 的核心是"一个小 MLP + 把视觉向量塞进 prompt"，这份代码把这两件事和它们的 token 账单算给你看**。需要注意：代码没有真正把 projector 的输出塞进 prompt（三个 DEMO 是分开的），也没有训练，Stage 1 / Stage 2 只出现在 TAKEAWAYS 的文字里。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PATCH_COUNT` / `PATCH_DIM` / `HIDDEN_DIM` / `LLM_DIM` | 模块常量 | 16 / 16 / 32 / 24 | 玩具规模（真实为 576 / 1024 / 4096 / 4096） |
| `rng = random.Random(11)` | 随机数生成器 | 可复现的随机初始化 | — |
| `vec` / `mat` | 函数 | `N(0, 0.3²)` 向量 / 矩阵 | 权重初始化 |
| `linear` | 函数 | `W·x + b` | 全连接层 |
| `gelu` / `gelu_vec` | 函数 | tanh 近似的 GELU | 激活函数 |
| `MLPProjector` | 类 | 两层线性 + GELU，`num_params` 统计参数 | LLaVA projector |
| `fake_vit_output` | 函数 | 16 个随机 patch 向量 | 冻结 ViT 的输出 |
| `build_llava_prompt` | 函数 | 生成含 `<image>` 的模板，估算文本 token | Prompt 格式 |
| `visualize_context` | 函数 | 打印视觉/文本 token 在不同窗口的占比 | 上下文预算 |
| `demo_projector` / `demo_prompt` / `demo_anyres` | 函数 | 三个独立 DEMO | 见第 1 节 |
| `main` | 函数 | 依次运行并打印 TAKEAWAYS | — |

数据流：`fake_vit_output()`（16 × 16）→ `MLPProjector.forward`（逐 patch，16 → 32 → 24）→ 16 个视觉 token（DEMO 1 到此为止）；`build_llava_prompt`（文本模板 + "576" 这个数字）→ `visualize_context`（占比表）；`demo_anyres` 只做乘法。

---

## 3. 逐段精讲

### 3.1 线性层与 GELU

```python
def linear(W, b, x):
    return [sum(r * v for r, v in zip(row, x)) + bi
            for row, bi in zip(W, b)]


def gelu(x):
    return 0.5 * x * (1.0 + math.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x * x * x)))
```

- `linear` 计算 `W·x + b`：`W` 按行存储，形状 `(out, in)`，与 PyTorch `nn.Linear.weight` 的约定相同；`zip(W, b)` 让每一行配上它的 bias。
- `gelu` 是 GELU 的 **tanh 近似**：`0.5·x·(1 + tanh(√(2/π)·(x + 0.044715·x³)))`。精确定义是 `x·Φ(x) = 0.5·x·(1 + erf(x/√2))`。我们在 `[-6, 6]` 上对比，两者最大误差约 4.7e-4（例如 x = 1 时 0.84119 vs 0.84134）。GPT-2 等模型沿用了这个近似，因为早期框架里 `tanh` 比 `erf` 更快。
- GELU 与 ReLU 的区别：负半轴不是硬截断为 0，而是平滑地趋于 0（x = −1 时约 −0.159），处处可导。讲义："2-layer MLP with GELU activation"。

### 3.2 `MLPProjector`

```python
class MLPProjector:
    def __init__(self, in_dim, hidden, out_dim):
        self.W1 = mat(hidden, in_dim)
        self.b1 = [0.0] * hidden
        self.W2 = mat(out_dim, hidden)
        self.b2 = [0.0] * out_dim

    def forward(self, x):
        h = gelu_vec(linear(self.W1, self.b1, x))
        return linear(self.W2, self.b2, h)

    def num_params(self):
        return (len(self.W1) * len(self.W1[0]) + len(self.b1)
                + len(self.W2) * len(self.W2[0]) + len(self.b2))
```

- 结构就是讲义的 projector：`in_dim → hidden →(GELU)→ out_dim`。bias 初始化为 0，权重 `N(0, 0.3²)`。
- `forward` 每次只处理**一个** patch 向量；`demo_projector` 用列表推导式对 16 个 patch 逐个调用。真实实现是一次矩阵乘法 `(576, 1024) @ (1024, 4096)`，projector 对每个 patch **独立**作用、不混合不同位置——这与 Q-Former 的 cross-attention 完全不同：LLaVA 不做任何压缩，576 进 576 出。
- `num_params`：权重元素数（行 × 列）+ bias 长度。玩具规模 `16×32 + 32 + 32×24 + 24 = 1,336`。
- 按讲义规模 `1024 → 4096 → 4096`：`1024×4096 + 4096 + 4096×4096 + 4096 = 20,979,712 ≈ 21.0M`（已计算）。⚠️ 讲义 Parameter economy 与代码 TAKEAWAYS 写"22M"，对比表格写"40M"，均不精确。另外讲义把 LLaVA-1.5-13B 的 projector 写成 `1024 → 4096 → 4096`，但 13B 模型的隐藏维度是 5120，此时应为约 31.5M。
- ⚠️ 讲义 Use It 写 toy 维度为 "16 → 32 → 32"，代码实际是 `16 → 32 → 24`。

### 3.3 Prompt 模板

```python
def build_llava_prompt(system, user, image_tokens):
    placeholder = "<image>"
    template = (
        f"SYSTEM: {system}\n"
        f"USER: {placeholder} {user}\n"
        f"ASSISTANT: "
    )
    return {
        "raw_prompt": template,
        "placeholder": placeholder,
        "image_tokens": image_tokens,
        "text_token_estimate": len(template.split()) + 10,
    }
```

- 三段 f-string 用括号包起来，相邻字符串字面量会被自动拼接成一个字符串。
- 返回一个 dict，把"原始模板 / 占位符 / 视觉 token 数 / 文本 token 估计"打包。
- ⚠️ `text_token_estimate`：`template.split()` 得到 24 个以空白分隔的"词"，再加 10，结果 34。词数不等于 BPE token 数，`<image>` 也被算进了文本，"+10"没有依据。正确做法是用目标 LLM 的 tokenizer 计数。
- ⚠️ 格式与讲义不同：讲义是一行 "`<系统提示> USER: <image> ... ASSISTANT:`"，系统提示前没有 `SYSTEM:` 前缀；代码加了前缀并用换行分隔。真实部署中格式必须与训练时逐字一致。
- ⚠️ 没有真正替换：DEMO 2 的标题说"LLM receives this after image-token replacement"，但打印的仍是带 `<image>` 的字符串。真实流程是：tokenize 文本（`<image>` 变成一个特殊 id）→ 查 embedding → 在占位位置插入 576 个 projector 输出向量 → labels 同步插入 576 个忽略标记（测验 Q11 给出实现）。讲义说"Before tokenization, it is replaced with the 576 visual tokens"也是一种简化表述——视觉 token 是连续向量，只能在 embedding 层拼接。

### 3.4 上下文预算

```python
def visualize_context(num_image_tokens, text_tokens):
    totals = (2048, 8192, 32768, 131072)
    for t in totals:
        used = num_image_tokens + text_tokens
        remain = t - used
        pct_image = 100 * num_image_tokens / t
        print(f"  window {t:>6d}: image {pct_image:5.1f}% | "
              f"text {100*text_tokens/t:4.1f}% | remain {max(remain, 0):>6d} tokens")
```

- 对每个窗口大小计算视觉 token 占比、文本占比和剩余空间；`max(remain, 0)` 防止窗口不够时打印负数。
- 2048 窗口：`576 / 2048 = 28.1%`，剩余 `2048 − 576 − 34 = 1438`。讲义"leaves 1472 tokens for text"是只扣视觉 token 的数字（2048 − 576）。
- 32k 窗口只占 1.8%，128k 只占 0.4%，这就是讲义"At 32k context, it is a rounding error"和"token budget was no longer the binding constraint"的数值依据。

### 3.5 AnyRes 的 token 账单

```python
    tile_tokens = 576
    configs = [
        ("336x336 (base)", 1, 0),
        ("672x336 (1x2)", 2, 1),
        ("672x672 (2x2)", 4, 1),
        ("1344x672 (2x4)", 8, 1),
        ("1344x1344 (4x4)", 16, 1),
    ]
    for name, tiles, thumb in configs:
        total = tiles * tile_tokens + thumb * tile_tokens
```

- 每个配置是一个三元组 `(名称, 块数, 缩略图数)`，`for name, tiles, thumb in configs` 直接解包。
- 总 token = `(块数 + 缩略图数) × 576`。base 不加缩略图（整张图就是一块）。
- 672×672（2×2）+ 缩略图 = 2880，与讲义一致。1344×672（讲义练习 3）为 5184，是 base 的 9 倍；1344×1344 为 9792。
- ⚠️ 讲义说 AnyRes 的网格是 "2x2 or 1x3"，代码用了 1×2、2×4、4×4。后两种块数超过了讲义描述的范围，这里只用于展示"token 随分辨率平方增长"。真实系统会限定一组允许的网格，并按原图长宽比选择最接近的一种。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| projector 逐 patch 前向 | 与"MLP 对每个位置独立作用"的概念一一对应 | 慢；生产用一次批量矩阵乘法 |
| tanh 近似 GELU | 只需 `math.tanh` | 与精确 GELU 差约 5e-4；PyTorch 两种都支持（`approximate="tanh"`） |
| `N(0, 0.3²)` 初始化、bias 为 0 | 数值温和 | 真实 projector 用框架默认初始化，并在 Stage 1 中训练 |
| 文本 token 用"词数 + 10"估计 | 不依赖 tokenizer | 误差大；应调用真实 tokenizer |
| 只打印模板、不做替换 | 让模板一目了然 | 看不到 embedding 层拼接与 labels 对齐；见测验 Q11 |
| AnyRes 只做乘法 | 聚焦 token 成本 | 没有切块、缩放、网格选择逻辑；第 06 节进一步讨论 |
| 没有训练循环 | 篇幅控制 | Stage 1 / Stage 2 只停留在文字；真实训练需冻结策略与 loss mask |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解 |
| 类与 `__init__` | `class MLPProjector: def __init__(self, in_dim, hidden, out_dim)` | 构造函数里创建参数，`self.W1` 等保存在实例上 |
| 实例方法 | `proj.forward(p)`、`proj.num_params()` | 通过 `self` 访问参数 |
| 列表乘法初始化 | `[0.0] * hidden` | 一维列表可以这样写（元素是不可变的 float，不会有共享问题） |
| 嵌套 `zip` 推导式 | `[sum(r * v for r, v in zip(row, x)) + bi for row, bi in zip(W, b)]` | 一行实现 `W·x + b` |
| 字符串字面量自动拼接 | `("SYSTEM: ..." "USER: ..." "ASSISTANT: ")` | 括号内相邻字符串会被拼成一个 |
| f-string 嵌入变量 | `f"USER: {placeholder} {user}\n"` | `\n` 是换行 |
| 返回字典 | `return {"raw_prompt": template, ...}` | 用键名访问：`prompt["image_tokens"]` |
| `str.split()` | `len(template.split())`、`prompt["raw_prompt"].split("\n")` | 无参数按任意空白切分；传参按指定分隔符切分 |
| 元组列表 + 解包 | `for name, tiles, thumb in configs:` | 每个元素是三元组 |
| 内置 `max` 截断 | `max(remain, 0)` | 防止负数 |
| f-string 格式符 | `{t:>6d}`（右对齐宽 6）、`{pct_image:5.1f}`、`{name:20s}`、`{tiles:2d}`、`{proj.num_params():,}`（千分位） | 对齐与数字格式 |
| f-string 中调用表达式 | `{100*text_tokens/t:4.1f}`、`{len(visual_tokens[0])}` | 花括号内可以写任意表达式 |
| `math.sqrt` / `math.pi` / `math.tanh` | `math.sqrt(2.0 / math.pi)` | GELU 近似公式中的常数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，瞬间完成）：

```text
DEMO 1: 2-layer MLP projector forward pass
  ViT out: 16 patches of dim 16
  MLP:     16 -> 32 -> 24
  params:  1,336
  output:  16 visual tokens of dim 24
  token 0 sample: [0.29, 0.079, -0.075, 0.036, -0.54, 0.169]

DEMO 2: LLaVA prompt template
  raw prompt (LLM receives this after image-token replacement):
    SYSTEM: A chat between a curious human and an artificial intelligence assistant.
    USER: <image> Describe what you see in this image in detail.
    ASSISTANT:
  <image> placeholder -> replaced with 576 visual tokens
  text token estimate: ~34 tokens

context budget at different LLM windows
  window   2048: image  28.1% | text  1.7% | remain   1438 tokens
  window   8192: image   7.0% | text  0.4% | remain   7582 tokens
  window  32768: image   1.8% | text  0.1% | remain  32158 tokens
  window 131072: image   0.4% | text  0.0% | remain 130462 tokens

DEMO 3: LLaVA-NeXT AnyRes token cost
  336x336 (base)      :  1 tiles + 0 thumbnail =   576 tokens
  672x336 (1x2)       :  2 tiles + 1 thumbnail =  1728 tokens
  672x672 (2x2)       :  4 tiles + 1 thumbnail =  2880 tokens
  1344x672 (2x4)      :  8 tiles + 1 thumbnail =  5184 tokens
  1344x1344 (4x4)     : 16 tiles + 1 thumbnail =  9792 tokens
```

逐项解读：

- **DEMO 1**：16 个 patch 进、16 个 token 出——MLP 不改变 token 数，只改变维度（16 → 24）。参数 1,336 可手算验证（3.2 节）。按真实规模这个数是约 21.0M，相对 7B 的 LLM 不到 0.3%。
- **DEMO 2**：文本估计 34 = 24 个词 + 10。2048 窗口下视觉 token 占 28.1%（TAKEAWAYS 近似为 30%），这正是早期 LLaVA 在 2k 上下文中"一张图吃掉近三分之一"的处境；到 32k 时只占 1.8%。
- **DEMO 3**：token 数与块数线性相关、与分辨率面积近似成正比。672×672 的 2880 与讲义一致；1344×1344 已接近 1 万，在 8k 上下文中放不下。这说明"高分辨率 = 更多 token"，也是第 06 节要解决的问题。
- 注意三个 DEMO 彼此独立：DEMO 1 的 16 个视觉 token 并没有被放进 DEMO 2 的 prompt。

---

## 7. 动手改一改

1. **（讲义练习 1）**用 `MLPProjector(1024, 4096, 4096).num_params()` 计算真实规模的参数量（纯 Python 创建矩阵会比较慢，可以只写一个公式函数），再按 5120 维重算，分别求占 7B、13B 模型的比例。
2. **精确 GELU**：用 `math.erf` 实现精确 GELU，打印两种实现在 `[-6, 6]` 上的最大误差。
3. **真正的替换**：给 `build_llava_prompt` 增加一个"tokenize → 展开 `<image>` → 生成 labels"的流程（参考测验 Q11），把 DEMO 1 的 16 个视觉 token 拼进去，打印最终序列长度与 labels 中非忽略位置的数量。
4. **用真实 tokenizer 计数**：安装一个分词库（例如 `tiktoken`）替换 `len(split()) + 10`，比较两种估计的差别。
5. **AnyRes 网格选择**：写一个函数，输入原图宽高和一组允许的网格（如 `[(1,1), (1,2), (2,1), (2,2), (1,3), (3,1)]`），选择长宽比最接近、且 token 数不超过预算的那一个，输出 token 数。
6. **进阶**：用 PyTorch 实现 projector + 一个冻结的小语言模型（如 GPT-2），只训练 projector，在少量图文对上做 Stage 1，观察 caption loss 的下降。

---

## 8. 常见坑

- **把视觉 token 当成文本 token**：视觉 token 是连续向量，只能在 embedding 层拼接，不能在 tokenization 之前替换字符串。
- **labels 没有同步展开**：插入 576 个视觉向量后 labels 长度不变，会导致 logits 与 labels 错位，loss 完全错误。
- **对视觉 token 或用户问题计算 loss**：Stage 2 应只对 assistant 回答计算 loss。
- **推理 prompt 与训练格式不一致**：少一个空格或换行都可能让模型回答质量下降。
- **用词数估计 token 数**：误差可能很大，尤其是中文、代码和数字。
- **projector 输出维度与 LLM 不匹配**：第二层输出必须等于 LLM 的 embedding 维度（7B 为 4096，13B 为 5120）。
- **只看上下文占比、忽略计算成本**：即使 32k 窗口装得下 9792 个视觉 token，每层 self-attention 的计算和 KV cache 也会随之增长。
