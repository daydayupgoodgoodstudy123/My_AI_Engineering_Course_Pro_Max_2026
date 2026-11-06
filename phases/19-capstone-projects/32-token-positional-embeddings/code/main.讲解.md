# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 32 节 Token 与位置 Embeddings ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m pytest -q` 或 `python3 tests/test_embeddings.py` ｜ **依赖**：`torch`（第三方，CPU 即可）；`math`、`dataclasses`（标准库）

---

## 1. 这份代码在考察什么

这是"从零搭 GPT"系列（第 30–36 节）的第三步：把上一节产生的 `(B, T)` token id 变成 Transformer 能处理的 `(B, T, D)` 向量。代码考察：

1. **Embedding 就是查表**：`nn.Embedding(V, D)` 的前向是"按 id 取行"，反向只给被取到的行累加梯度。
2. **两种位置编码的对比**：learned（第二张可训练的表）vs sinusoidal（零参数的 sin/cos 公式）。
3. **组合方式**：token 向量与位置向量**相加**，靠广播把 `(T, D)` 复制到每个 batch。
4. **PyTorch 模块化写法**：`nn.Module`、`register_buffer`、参数计数、输入校验。
5. **一个可观测的诊断量**：相邻位置向量的平均余弦相似度，用来直观感受"随机表"和"有结构的表"的区别。

> 一句话：**把"id → 向量"和"位置 → 向量"两张表做出来、加在一起，并量化 learned 与 sinusoidal 的差异**。同时要注意：本节的 sinusoidal 实现预先建表，**和 learned 一样不能超过 `max_context_length`**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_INIT_STD` / `_init_normal` | 常量 / 函数 | 在 `no_grad` 下用 `N(0, 0.02²)` 原地初始化 | GPT 系初始化惯例 |
| `TokenEmbedding` | `nn.Module` | 包装 `nn.Embedding(V, D)`，校验 id 必须是 `long`、二维 | token 查表 |
| `LearnedPositionalEmbedding` | `nn.Module` | 包装 `nn.Embedding(L, D)`，输入是长度 `seq_len`，返回 `(T, D)` | learned 绝对位置 |
| `SinusoidalPositionalEmbedding` | `nn.Module` | 构造时算好 `(L, D)` 的 sin/cos 表存为 buffer，前向切片 | 固定位置编码 |
| `EmbeddingComposer` | `nn.Module` | `tok(ids) + pos(T).unsqueeze(0)` | 输入组合（相加 + 广播） |
| `count_parameters` | 函数 | 统计 `requires_grad` 的参数元素总数 | 参数量 |
| `neighbour_cosine_curve` | 函数 | 计算第 p 行与第 p+k 行余弦相似度的平均，k=1..max_offset | 位置表结构诊断 |
| `DemoConfig` | dataclass | demo 超参数：V=320、D=64、L=128、B=4、T=32、seed=11 | 配置 |
| `main` | 函数 | 打印形状、参数量、余弦曲线、单调性、长度边界 | 演示 |

数据流：`ids (4,32)` → `TokenEmbedding` → `(4,32,64)`；`seq_len=32` → 位置模块 → `(32,64)` → `unsqueeze(0)` → `(1,32,64)`；二者相加 → `(4,32,64)` 交给下一节的注意力层。

---

## 3. 逐段精讲

### 3.1 初始化工具

```python
DEFAULT_INIT_STD = 0.02


def _init_normal(weight: torch.Tensor, std: float = DEFAULT_INIT_STD) -> None:
    """Init a parameter tensor in place from a small Gaussian."""
    with torch.no_grad():
        weight.normal_(mean=0.0, std=std)
```

- `nn.Embedding` 默认用 `N(0, 1)` 初始化，对 Transformer 来说太大；GPT-2 惯例是 std 0.02（讲义："traditionally with mean zero and standard deviation around 0.02"）。
- `normal_` 末尾的下划线表示**原地**修改。对一个 `requires_grad=True` 的叶子张量做原地操作，autograd 会报错，所以要包在 `torch.no_grad()` 里。
- 函数名前的下划线 `_init_normal` 是 Python 约定，表示"模块内部使用"。

### 3.2 `TokenEmbedding`：查表 + 严格校验

```python
    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        if ids.dtype != torch.long:
            raise TypeError(f"ids must be long tensor, got {ids.dtype}")
        if ids.dim() != 2:
            raise ValueError(f"ids must be (B, T), got shape {tuple(ids.shape)}")
        return self.embedding(ids)
```

- `self.embedding(ids)` 本质是 `weight[ids]`：`(B, T)` 的整数索引取出 `(B, T, D)`。
- 反向时，PyTorch 把上游梯度按 id **scatter-add** 回对应行：没出现的行梯度为 0；同一 id 出现 n 次就累加 n 份（我们实际验证：`ids=[[3,3,3]]` 求和后反传，第 3 行梯度为 `[3,3,3,3]`）。
- 两个校验比 PyTorch 本身更严格：
  - `nn.Embedding` 其实也接受 `int32` 索引（实测可以运行），这里强制 `long` 是为了让错误尽早暴露（比如误把 float 张量传进来）。
  - 强制二维 `(B, T)`，一维输入会被拒绝——这固定了"形状契约"。
- **没有**检查 `ids < vocab_size`：越界 id 会由 PyTorch 抛 `IndexError`（CPU）或触发 CUDA device-side assert（GPU，更难调试）。
- 构造函数里的 `if vocab_size < 1: raise ValueError(...)` 是"fail fast"风格，整个系列都这么写。

### 3.3 `LearnedPositionalEmbedding`：第二张表

```python
    def forward(self, seq_len: int) -> torch.Tensor:
        if seq_len < 1:
            raise ValueError(f"seq_len must be >= 1, got {seq_len}")
        if seq_len > self.max_context_length:
            raise ValueError(
                f"seq_len {seq_len} exceeds max_context_length {self.max_context_length}"
            )
        positions = torch.arange(seq_len, device=self.embedding.weight.device)
        return self.embedding(positions)
```

- 输入不是 id 张量，而是一个整数长度；内部用 `torch.arange(seq_len)` 生成位置 `0..T-1` 再查表，输出 `(T, D)`，**不含 batch 维**。
- `device=self.embedding.weight.device`：位置张量要和权重在同一设备上，否则模型搬到 GPU 后会报设备不匹配。
- 超过 `max_context_length` 直接报错——表里根本没有那一行（讲义："The row does not exist"）。
- ⚠️ 位置永远从 0 开始，没有 `start/offset` 参数。做 KV cache 增量生成时，新 token 的位置是"已生成长度"，这个接口无法表达（见测验 Q11 的改造）。

### 3.4 `SinusoidalPositionalEmbedding`：用广播一次建好整张表

```python
    @staticmethod
    def _build_table(max_context_length: int, d_model: int, base: float) -> torch.Tensor:
        pos = torch.arange(max_context_length, dtype=torch.float32).unsqueeze(1)
        i = torch.arange(d_model // 2, dtype=torch.float32)
        denom = base ** (2 * i / d_model)
        angle = pos / denom
        pe = torch.zeros(max_context_length, d_model, dtype=torch.float32)
        pe[:, 0::2] = torch.sin(angle)
        pe[:, 1::2] = torch.cos(angle)
        return pe
```

形状追踪（demo：L=128，D=64）：

| 变量 | 形状 | 含义 |
|------|------|------|
| `pos` | `(128, 1)` | 位置列向量 |
| `i` | `(32,)` | 频率对的编号 k = 0..31 |
| `denom` | `(32,)` | `10000^(2k/64)`，从 1 增长到约 7499 |
| `angle = pos / denom` | `(128, 32)` | 广播：每个位置 × 每个频率 |
| `pe[:, 0::2]` / `pe[:, 1::2]` | 各 `(128, 32)` | 偶数列放 sin、奇数列放 cos，交错排列 |

- `0::2` 是"从 0 开始每隔 2 取一个"，即第 0、2、4… 列。这样同一频率的 sin 和 cos **相邻**，正好组成一个 2 维"旋转对"。
- 波长：第 k 对的波长 `2π·10000^(2k/D)`。k=0 时约 6.28，k=16 约 628，k=31 约 47,117（实际计算）。**低维变化最快、编码精细位置；高维变化最慢、编码粗略位置**。讲义写成 "lower dimensions encode coarse position and the higher dimensions encode fine position"，说反了。
- 构造函数要求 `d_model` 为偶数，否则 `0::2` 与 `1::2` 列数不相等，赋值会失败。
- `@staticmethod`：这个方法不访问 `self`，只依赖参数，可以直接 `SinusoidalPositionalEmbedding._build_table(...)` 调用。

```python
        pe = self._build_table(max_context_length, d_model, base)
        self.register_buffer("pe", pe, persistent=False)
```

- **buffer** 与参数的区别：不在 `parameters()` 里（参数量为 0、优化器不更新），但会随 `.to(device)`/`.half()` 一起移动。
- `persistent=False`：不写入 `state_dict()`（实测 `state_dict()` 为空）。表能随时由公式重建，没必要存进 checkpoint；好处是加载旧 checkpoint 时不会因为这个键对不上而报错。

```python
    def forward(self, seq_len: int) -> torch.Tensor:
        ...
        if seq_len > self.max_context_length:
            raise ValueError(...)
        return self.pe[:seq_len]
```

- 前向只是切片，返回的是表的**视图**（不复制）。
- ⚠️ 与讲义"公式可以延伸到任何位置"的直觉不同，这里同样受 `max_context_length` 限制（讲义和 `quiz.json` 都承认了这一点）。

### 3.5 `EmbeddingComposer`：相加 + 广播

```python
        if token_embedding.d_model != getattr(positional_embedding, "d_model", None):
            raise ValueError("token and positional embeddings must share d_model")
    ...
    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        if ids.dim() != 2:
            raise ValueError(f"ids must be (B, T), got shape {tuple(ids.shape)}")
        seq_len = ids.shape[1]
        tok = self.token_embedding(ids)
        pos = self.positional_embedding(seq_len)
        return tok + pos.unsqueeze(0)
```

- `isinstance(x, (A, B))` 接受一个类型元组，只允许 learned 或 sinusoidal 两种位置模块。
- `getattr(obj, "d_model", None)`：属性不存在时返回 `None` 而不是抛异常。
- `pos.unsqueeze(0)`：`(T, D)` → `(1, T, D)`，与 `(B, T, D)` 相加时沿 batch 维广播。其实不加 `unsqueeze` 也能广播（`(T,D)` 会自动在左侧补维），显式写出来更清楚。
- 把子模块赋值给 `self.xxx`，`nn.Module` 会自动注册，`parameters()` 会递归收集：`learned_composer` 参数量 = `20,480 + 8,192 = 28,672`（实测）。
- `@property d_model`：把方法伪装成只读属性，`composer.d_model` 不用加括号。
- demo 里两个 composer 共享同一个 `token_emb` 对象，这在 PyTorch 中就是"参数共享"。

### 3.6 诊断函数

```python
def count_parameters(module: nn.Module) -> int:
    return sum(p.numel() for p in module.parameters() if p.requires_grad)
```

- 生成器表达式 + `sum`；`numel()` 是元素个数。buffer 不在 `parameters()` 里，所以 sinusoidal 为 0。

```python
    rows = table.detach().to(torch.float32)
    norms = rows.norm(dim=1, keepdim=True).clamp(min=1e-8)
    unit = rows / norms
    result: list[float] = []
    for k in range(1, max_offset + 1):
        a = unit[:-k]
        b = unit[k:]
        dot = (a * b).sum(dim=1).mean().item()
        result.append(dot)
```

- 先把每行归一化成单位向量（`clamp` 防止除 0），再把表错开 k 行逐行点积，最后取平均——"第 p 行与第 p+k 行的平均余弦相似度"。
- `detach()`：传入的 learned 表是 `nn.Parameter`，切断计算图，避免无谓地记录梯度。
- `.item()` 把单元素张量转成 Python float。
- 一个漂亮的数学事实：对 sinusoidal 表，`pe[p]·pe[p+k] = Σ_i cos(ω_i k)`，每行范数恒为 `√(D/2)`（D=64 时 5.657，实测一致），所以**每一对 (p, p+k) 的余弦相似度都相同**，这里的"平均"其实是在对常数取平均。按公式 `(2/D)·Σ cos(ω_i k)` 算出的 6 个值与 demo 输出逐位一致。

### 3.7 `main`：五个诊断段落

1. **Shapes**：确认三个输出都是 `(4, 32, 64)`，并用 `assert` 固定。
2. **Parameter counts**：`320×64=20,480`、`128×64=8,192`、`0`。
3. **Neighbour cosine similarity**：两列对比。
4. **Sinusoidal property: smooth decay**：统计 5 个相邻步中"不上升"（容差 1e-3）的个数。
5. **Length extrapolation**：sinusoidal 在 64、128 长度可用；learned 在 129 报错并被 `except` 捕获。

⚠️ 第 5 段的问题：
- 先 `print("... : ok")` 再调用，顺序反了——即使调用失败也已经打印了 "ok"。
- 没有对 sinusoidal 测试 `long + 1`。如果测了，它同样会抛 `ValueError`。段落标题叫 "Length extrapolation"，却没有展示任何外推，容易让读者以为"sinusoidal 能外推、learned 不能"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `nn.Embedding` 包一层而不是直接用 | 统一加输入校验、初始化、记录 `d_model` | 多一层间接；生产代码通常直接用 `nn.Embedding` |
| std 0.02 初始化 | 与 GPT-2 一致，初始激活尺度合适 | 不同模型会按层数调整（如对残差投影缩放） |
| 位置模块输入是 `seq_len` 而不是位置张量 | 接口简单，训练时够用 | 无法表达 KV cache 生成时的位置偏移；生产实现会接收 `position_ids` 或 `start` |
| sinusoidal 预先建表 | 前向只切片，最快 | 失去"任意位置可算"的优点；可改为按需计算（测验 Q11） |
| buffer + `persistent=False` | 不算参数、跟随设备、不进 checkpoint | 加载时必须用相同的 `max_context_length` 重建 |
| 相加而不是拼接 | 保持 `D` 不变，残差/LN 设计统一 | 语义与位置共享同一空间；RoPE 改为在 Q/K 上做旋转 |
| 严格 `TypeError/ValueError` 校验 | 形状契约出错时立刻报错 | 每次前向多几个 Python 判断，开销可以忽略 |
| 用余弦曲线做诊断 | 直观展示"结构 vs 随机" | 只看初始化状态；训练后 learned 表也会出现平滑结构（讲义） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，`list[float]` 等新写法在旧版本也能用 |
| 模块级常量 | `DEFAULT_INIT_STD = 0.02` | 全大写表示常量（约定，不强制） |
| 类型注解 | `def forward(self, ids: torch.Tensor) -> torch.Tensor` | 标注参数和返回类型，不影响运行 |
| 变量注解 | `result: list[float] = []` | 给局部变量标注类型 |
| `with` 上下文管理器 | `with torch.no_grad():` | 进入时关闭梯度记录，退出时自动恢复 |
| 继承与 `super()` | `class TokenEmbedding(nn.Module)`、`super().__init__()` | 必须先调用父类构造函数，`nn.Module` 才能注册子模块和参数 |
| `raise` 异常 | `raise ValueError(f"...")`、`raise TypeError(...)` | 主动报错；类型不对用 `TypeError`，值不对用 `ValueError` |
| `try / except ... as e` | `except ValueError as e: print(f"  caught: {e}")` | 捕获异常并取出错误信息 |
| `@staticmethod` | `_build_table` | 不需要 `self` 的方法 |
| `@property` | `def d_model(self)` | 像属性一样访问方法结果 |
| `@dataclass` | `class DemoConfig` | 自动生成 `__init__`，字段带默认值 |
| `isinstance` 与类型元组 | `isinstance(p, (LearnedPositionalEmbedding, SinusoidalPositionalEmbedding))` | 判断是否属于其中任一类型 |
| `getattr` 默认值 | `getattr(positional_embedding, "d_model", None)` | 属性不存在时返回默认值 |
| 生成器表达式 | `sum(p.numel() for p in module.parameters() if p.requires_grad)` | 不建列表直接求和 |
| `enumerate(..., start=1)` + `zip` | `for k, (a, b) in enumerate(zip(c1, c2), start=1)` | 同时遍历两列并从 1 编号，嵌套解包 |
| 布尔求和 | `sum(curve[i] >= curve[i+1] - 1e-3 for i in ...)` | `True` 当作 1，统计满足条件的个数 |
| 切片步长 | `pe[:, 0::2]`、`pe[:, 1::2]` | 取偶数列 / 奇数列 |
| 负数切片 | `unit[:-k]`、`unit[k:]` | 去掉最后 k 行 / 前 k 行，实现"错开 k 行" |
| `unsqueeze` 与广播 | `pos.unsqueeze(1)`、`pos / denom` | 插入长度为 1 的维，再按规则自动扩展 |
| f-string 格式符 | `{token_params:>7}`、`{a:>+7.4f}`、`{k:>4}` | 右对齐宽 7；带符号、4 位小数 |
| `"-" * len(title)` | `_print_section` | 字符串重复 |
| `raise SystemExit(main())` | 文件末尾 | 把 `main()` 的返回值作为进程退出码 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 demo，被测试 `import` 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU，耗时约 1.7 秒）：

```text
Shapes
------
token_emb output  : (4, 32, 64)
learned composer  : (4, 32, 64)
sinusoidal cmp.   : (4, 32, 64)

Parameter counts
----------------
token embedding         :   20480      ← 320 × 64
learned positional      :    8192      ← 128 × 64
sinusoidal positional   :       0  (parameter-free)

Neighbour cosine similarity
---------------------------
offset k | learned cos | sinusoidal cos
      1  |   -0.0210  |   +0.9662
      2  |   -0.0026  |   +0.8845
      3  |   -0.0091  |   +0.7996
      4  |   -0.0133  |   +0.7479
      5  |   -0.0179  |   +0.7345
      6  |   +0.0078  |   +0.7362      ← 比 k=5 略高

Sinusoidal property: smooth decay
---------------------------------
sinusoidal curve monotone steps: 4/5

Length extrapolation
--------------------
sinusoidal at len  64 : ok
sinusoidal at len 128 : ok
learned bounded by max_context_length: must error past max
  caught: seq_len 129 exceeds max_context_length 128

Demo OK.
```

逐项解读：

- **形状**：三者都是 `(B, T, D)`，验证了形状契约。
- **参数量**：learned 位置表多出 `L × D`。放大到 GPT-2 Small 是 `1024 × 768 = 786,432`，只占 124M 的约 0.63%——两种方案的真正差别不在参数量。
- **learned 列 ≈ 0**：各行独立从 `N(0, 0.02²)` 采样，64 维随机向量几乎正交（单对余弦的标准差约 `1/√64 = 0.125`，再对 120 多对取平均，落在 ±0.02 附近）。
- **sinusoidal 列**：等于 `(2/64)·Σ_{i=0}^{31} cos(k / 10000^(2i/64))`。k=1 时高频几对已经明显转动、低频对几乎为 1，所以是 0.9662；之后逐渐降到 0.73 左右的"平台"——32 对里约一半波长超过几百个位置，在 k≤6 范围内几乎不变。
- **为什么 4/5**：最高频的那一对贡献 `cos(k)`，`cos 5 ≈ 0.284`、`cos 6 ≈ 0.960`，k 从 5 到 6 它跳升了 0.68，平均到 32 对上约 +0.021，超过了其余各对的下降，所以曲线回升了 0.0017（超过 1e-3 容差）。sinusoidal 的相似度是**多个余弦的叠加，总体下降但会振荡**，并不严格单调。
- **长度边界**：只证明了 learned 在 129 报错；sinusoidal 在 129 同样会报错（我们另行验证：`seq_len 129 exceeds max_context_length 128`）。

---

## 7. 动手改一改

1. **讲义建议的实验**：把 `DemoConfig.d_model` 改成 32，观察 sinusoidal 列。实测为 `0.9571, 0.8581, 0.7670, 0.7288, 0.7361, 0.7432`，单调步数降到 3/5——维度少了，高频对所占比例变大，振荡更明显。
2. **修正 demo 的长度测试**：在 "Length extrapolation" 中对 sinusoidal 也调用 `sinusoidal_pos(long + 1)` 并捕获异常；把 `print("ok")` 移到调用之后。
3. **真正可外推的 sinusoidal**：不预建表，`forward(seq_len, start=0)` 按需计算 `start..start+T-1` 的编码，并验证前 128 行与原表一致（参考测验 Q11）。再给 `EmbeddingComposer.forward` 加 `start` 参数。
4. **验证旋转性质**：为 k=3 构造分块旋转矩阵 `R_k`，检查 `R_k @ pe[p]` 与 `pe[p+k]` 的误差（我们实测约 1e-7）。
5. **观察稀疏梯度**：给 `TokenEmbedding` 输入 `[[1, 2, 2]]`，对输出求和后 `backward()`，打印每行梯度的绝对值之和，确认只有第 1、2 行非零、第 2 行是第 1 行的两倍。
6. **进阶**：实现 RoPE——写一个函数对形状 `(B, T, D)` 的张量按位置做分对旋转，并验证 `rope(q, p)·rope(k, p')` 只依赖 `p' − p`（为下一节注意力的可选扩展做准备）。

---

## 8. 常见坑

- **忘记 `no_grad` 就原地初始化参数**：`weight.normal_()` 对叶子参数会报 "a leaf Variable that requires grad is being used in an in-place operation"。
- **id 用了 float**：从 NumPy 或 JSON 读出的数组可能是浮点，本模块会抛 `TypeError`；用 `torch.tensor(x, dtype=torch.long)`。
- **id 越界**：`id >= vocab_size` 在 GPU 上报的是难懂的 device-side assert，先在 CPU 上复现。
- **位置张量不在同一设备**：自己写 `torch.arange` 时忘了 `device=`，模型上 GPU 后报设备不匹配。
- **把 sinusoidal 表注册成 `nn.Parameter`**：会被优化器更新、参数量也不再是 0；固定张量应该用 buffer。
- **以为 sinusoidal 一定能外推**：本节实现预建表就有上限；即便按需计算，模型在训练长度之外也未必能用好这些位置。
- **增量生成时位置从 0 开始**：KV cache 下每步只喂 1 个 token，如果位置模块仍从 0 编号，所有新 token 都会被当成位置 0。
- **奇数 `d_model`**：sin/cos 必须成对，本模块直接拒绝。

---

## 9. 测试在验证什么

`tests/test_embeddings.py` 共 21 个 `unittest` 测试，文件开头用 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加入导入路径，因此可以在 `code/` 下直接运行。实际运行结果：`python3 -m pytest -q` → `21 passed in 1.27s`；`python3 tests/test_embeddings.py` → `Ran 21 tests ... OK`。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TestTokenEmbedding` | `test_output_shape` | `(3,7)` → `(3,7,8)` |
| | `test_long_dtype_required` | float 输入抛 `TypeError` |
| | `test_rank_two_required` | 一维输入抛 `ValueError` |
| | `test_parameter_count` | 参数量 = `V × D` |
| `TestLearnedPositionalEmbedding` | `test_output_shape` | `seq_len=10` → `(10,16)`，没有 batch 维 |
| | `test_parameter_count` | 参数量 = `L × D` |
| | `test_rejects_seq_len_past_max` / `test_rejects_zero_seq_len` | 长度 17 > 16、长度 0 都报错 |
| `TestSinusoidalPositionalEmbedding` | `test_output_shape` | 形状正确 |
| | `test_zero_parameters` | 参数量为 0 |
| | `test_odd_d_model_rejected` | `d_model=5` 构造时报错 |
| | `test_sin_cos_formula` | 逐元素对照 `math.sin/cos` 公式（5 位小数） |
| | `test_deterministic_across_constructions` | 两次构造结果完全相同（没有随机性） |
| `TestComposer` | 两个 `*_composition_shape` | 两种位置模块组合后形状都是 `(B,T,D)` |
| | `test_composer_sums_token_and_position` | 输出严格等于 `tok + pos.unsqueeze(0)`，确认是相加而非拼接 |
| | `test_d_model_mismatch_rejected` | D 不一致时构造报错 |
| `TestNeighbourCosine` | `test_curve_length` | 返回长度等于 `max_offset` |
| | `test_sinusoidal_curve_decays` | 只比较 `curve[0] > curve[5]`——刻意没有要求单调，与实际 4/5 的结果相符 |
| `TestGradientFlow` | `test_token_embedding_gradient_only_for_used_rows` | 只有被查到的第 1、2 行有梯度，第 0、7 行梯度为 0 |
| | `test_sinusoidal_has_no_grad` | `parameters()` 为空列表 |

测试没有覆盖的地方：sinusoidal 超过 `max_context_length` 时报错（只测了 learned）、`state_dict` 不含 `pe`、模块在不同设备间移动、越界 id 的行为。
