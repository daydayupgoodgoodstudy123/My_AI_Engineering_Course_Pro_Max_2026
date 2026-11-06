# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 21 节 Jamba——混合 SSM-Transformer ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）

---

## 1. 这份代码在考察什么

这是一个"推理缓存显存计算器"，比较 6 种 32 层、hidden 4096 的配置在 8K / 64K / 128K / 256K 上下文下需要多少缓存显存：

- 纯 Transformer（MHA，32 个 KV 头）与纯 Transformer（GQA，8 个 KV 头）；
- Jamba 风格混合：1:3（8 层注意力）、1:7（4 层注意力）、1:15（2 层注意力）；
- 纯 Mamba（0 层注意力）。

缓存 = 注意力层的 KV cache（随上下文线性增长）+ Mamba 层的 SSM 状态（固定大小）。它对应讲义 "The memory budget" 一节和练习 1、2。

核心结论非常直观：**长上下文下缓存显存几乎完全由注意力层数决定**——每减少一层注意力，KV cache 就按比例下降，而 SSM 状态只有 MB 级。

> 一句话：**用两条公式量化"把注意力层换成 Mamba 层"省下了多少显存**；同时要注意代码的 Jamba 配置用了 MHA 而非真实的 GQA，且结尾 takeaway 的数字与表格不一致。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BYTES_BF16` / `BYTES_FP8` | 常量 | 每个元素的字节数（FP8 定义了但未使用） | 精度 |
| `HybridConfig` | dataclass | 名称、总层数、注意力层数、hidden、Q/KV 头数、head_dim、SSM 状态大小 | 混合架构配置 |
| `kv_cache_bytes` | 函数 | `2 × 注意力层 × KV头 × head_dim × ctx × 字节` | KV cache |
| `ssm_state_bytes` | 函数 | `Mamba层 × hidden × state × 字节` | SSM 状态 |
| `fmt_bytes` | 函数 | 1024 进制格式化 | 输出 |
| `main` | 函数 | 6 种配置 × 4 种上下文的表格、256K 节省比例、KV 占比 | 演示入口 |

数据流：`configs` 列表 → 对每个配置、每个上下文调用 `kv_cache_bytes` + `ssm_state_bytes` → 表 1；以第一个配置（纯 MHA）为基线算节省比例 → 表 2；算注意力层占比与 KV 在缓存中的占比 → 表 3；最后打印写死的 takeaway。

---

## 3. 逐段精讲

### 3.1 `HybridConfig`：用一个 dataclass 描述所有架构

```python
@dataclass
class HybridConfig:
    name: str
    total_layers: int
    attn_layers: int
    hidden: int
    n_q_heads: int
    n_kv_heads: int
    head_dim: int
    ssm_state_size: int
```

- 纯 Transformer、混合、纯 SSM 都可以用"注意力层数"和"SSM 状态大小"两个旋钮表达：`attn_layers = total_layers` 且 `ssm_state_size = 0` 就是纯 Transformer；`attn_layers = 0` 就是纯 Mamba。
- `n_q_heads` 在计算中**从未使用**——KV cache 只与 KV 头数有关，Q 头数不影响缓存（这本身是一个值得记住的知识点）。
- ⚠️ 三个 Jamba 配置都写了 `n_kv_heads=32`（MHA）。真实 Jamba 的注意力层是 GQA（32 个 query 头、8 个 KV 头），按真实配置 256K 时 KV cache 是 4 GiB 而不是 16 GiB（测验 Q10）。

### 3.2 KV cache 公式

```python
def kv_cache_bytes(cfg: HybridConfig, ctx: int, bytes_per_elem: int) -> int:
    return (2 * cfg.attn_layers * cfg.n_kv_heads * cfg.head_dim * ctx
            * bytes_per_elem)
```

- 因子 2 = K 和 V 各一份；只乘**注意力层数**，Mamba 层不贡献 KV cache。
- 以 Jamba 1:7（代码口径）在 262,144 token 为例：`2 × 4 × 32 × 128 × 262144 × 2 = 17,179,869,184 字节 = 16 GiB`。
- 每 token 的 KV：`2 × 4 × 32 × 128 × 2 = 64 KiB`；纯 MHA 32 层是它的 8 倍（512 KiB/token）。
- 这是单条序列的缓存；并发 B 条请求就乘以 B。

### 3.3 SSM 状态公式

```python
def ssm_state_bytes(cfg: HybridConfig, bytes_per_elem: int) -> int:
    ssm_layers = cfg.total_layers - cfg.attn_layers
    return ssm_layers * cfg.hidden * cfg.ssm_state_size * bytes_per_elem
```

- 没有 `ctx` 参数——这就是 SSM "常数显存"的代码体现。
- Jamba 1:7：`28 × 4096 × 16 × 2 = 3,670,016 字节 ≈ 3.5 MiB`；纯 Mamba 32 层为 4 MiB。
- ⚠️ 简化之处：Mamba 的状态宽度是扩展后的内部维度 `d_inner = expand × hidden`（常用 expand = 2），每层还要缓存短卷积状态 `d_inner × (d_conv − 1)`。按 `d_inner = 8192`、`d_conv = 4` 重算约 8.3 MiB，比代码大约 2.4 倍，但仍是 MB 级，不影响结论。

### 3.4 表 1：四种上下文下的总缓存

```python
    contexts = [8_192, 65_536, 131_072, 262_144]
    header = "  " + "config".ljust(32)
    for ctx in contexts:
        header += f"{ctx // 1000}k".rjust(10)
```

- 外层遍历配置、内层遍历上下文，每格是 `kv + ss`。
- ⚠️ 表头用 `ctx // 1000`，于是 65,536、131,072、262,144 显示为 "65k、131k、262k"，而讲义一律叫 64K、128K、256K；改成 `ctx // 1024` 即可对齐。
- 读表要点：
  - 纯 MHA 与 "Jamba 1:3" 在 KV 头数相同时，后者恰好是 GQA 8 的大小（都等于"注意力层数 × KV 头数 = 256"）——说明"减少注意力层"与"减少 KV 头"在 KV cache 上是等价的乘法因子。
  - 纯 Mamba 在任何上下文都是 4 MiB。

### 3.5 表 2：相对纯 MHA 的节省

```python
    baseline = kv_cache_bytes(configs[0], 262_144, BYTES_BF16)
    for cfg in configs:
        ...
        savings = (1 - total / baseline) * 100
        print(f"  {cfg.name:<32} total {fmt_bytes(total):>10}  "
              f"({savings:+.1f}% vs baseline)")
```

- `configs[0]` 是纯 MHA，所以所有比较都以它为 100%。
- `{savings:+.1f}` 强制显示正负号，因此"节省 87.5%"显示为 `+87.5%`。
- Jamba 1:7 节省 87.5% = 1 − 4/32：正是"注意力层数降为 1/8"。讲义所说的"8x reduction"就是这一行。

### 3.6 表 3：注意力层占比 vs KV 在缓存中的占比

```python
        attn_frac = cfg.attn_layers / cfg.total_layers if cfg.total_layers else 0
        ...
        mem_frac = kv / (kv + ss + 1) if (kv + ss) > 0 else 0
```

- `attn_frac` 是层数占比；`mem_frac` 是缓存显存中 KV cache 的占比。分母里的 `+ 1` 是多余的防御（外面已有 `if (kv + ss) > 0`）。
- 所有混合配置都打印 `1.000`：即使注意力层只占 6.25%（1:15），在 256K 时 KV cache 也占缓存的 99.9% 以上。计算可知，Jamba 1:7（代码口径）在上下文**只有 56 个 token** 时 KV cache 就已追平 SSM 状态（`3,670,016 / 65,536 = 56`）。这也回答了讲义练习 2"哪个比例下二者相等"——只要有一层注意力，长上下文下就不可能相等。

### 3.7 写死的 takeaway

```python
    print("  Pure Transformer at 256k = 67 GB just for KV cache — will not fit")
    ...
    print("  Jamba 1:7 = 8.4 GB KV cache + ~4 MB SSM state = fits comfortably.")
```

- ⚠️ 与程序自己的表格矛盾：表格显示纯 MHA 在 262K 为 128 GiB、Jamba 1:7 为 16 GiB。67 GB 与 8.4 GB 实际是 **128K** 上下文、十进制单位下的数字（68.7e9 字节、8.59e9 字节）。讲义正文也有同样的混乱（同一节里先说 8.4 GB、后说 16 GB）。
- "fits comfortably"还忽略了权重：Jamba 52B 参数用 BF16 需要 104 GB，单张 80GB 卡必须先把权重量化到 8-bit 左右。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只算缓存（KV + SSM 状态） | 突出混合架构的核心差异 | 不含权重、激活、碎片；真实部署要整体预算 |
| 所有配置统一 32 层、hidden 4096 | 对照实验，只变注意力层数与 KV 头数 | 真实模型的层数、宽度各不相同 |
| Jamba 配置用 32 个 KV 头 | 与"纯 MHA"对比时只差注意力层数 | 与真实 Jamba（GQA 8）不符，KV cache 高估 4 倍 |
| SSM 状态 = `hidden × 16` | 一行公式 | 忽略 `expand = 2` 与卷积状态，低估约 2.4 倍；实际常用 FP32 存状态 |
| BF16 单一精度 | 简单 | `BYTES_FP8` 定义了却没用；生产中常用 FP8 KV cache |
| 上下文表头 `ctx // 1000` | 随手写法 | 显示 262k 而非 256K |
| takeaway 写死字符串 | 便于叙述 | 与计算结果脱节；应从计算结果生成 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| 模块级常量 | `BYTES_BF16 = 2` | 全大写表示常量，避免"魔法数字" |
| `@dataclass` | `class HybridConfig` | 自动生成构造函数，字段带类型注解 |
| 关键字参数构造对象 | `HybridConfig(name=..., total_layers=32, ...)` | 字段多时用关键字传参最清晰 |
| 括号内换行 | `return (2 * cfg.attn_layers * ...\n * bytes_per_elem)` | 括号让长表达式可以跨行 |
| 数字下划线 | `262_144` | 等同 262144 |
| 整除 | `ctx // 1000` | 向下取整 |
| 字符串对齐方法 | `"config".ljust(32)`、`fmt_bytes(total).rjust(10)` | 左/右填充到固定宽度 |
| f-string 带符号格式 | `{savings:+.1f}%` | `+` 强制显示正负号 |
| f-string 宽度 | `{cfg.name:<32}`、`{fmt_bytes(total):>10}` | 左/右对齐 |
| 条件表达式防除零 | `a / b if b else 0` | 分母为 0 时给默认值 |
| 列表索引取基线 | `configs[0]` | 约定第一个配置为基线 |
| `for` 循环中提前 `return` | `fmt_bytes` | 找到合适的单位立即返回 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.06 秒）：

```text
Memory at BF16 (2 bytes per element)
  config                                  8k       65k      131k      262k
  pure Transformer 32L                4.00GB   32.00GB   64.00GB  128.00GB
  pure Transformer 32L (GQA 8)        1.00GB    8.00GB   16.00GB   32.00GB
  Jamba 1:7 hybrid 32L              515.50MB    4.00GB    8.00GB   16.00GB
  Jamba 1:3 hybrid 32L                1.00GB    8.00GB   16.00GB   32.00GB
  Jamba 1:15 hybrid 32L             259.75MB    2.00GB    4.00GB    8.00GB
  pure Mamba 32L                      4.00MB    4.00MB    4.00MB    4.00MB

Headline savings at 256k context (BF16), vs pure Transformer full-MHA
  pure Transformer 32L             total   128.00GB  (+0.0% vs baseline)
  pure Transformer 32L (GQA 8)     total    32.00GB  (+75.0% vs baseline)
  Jamba 1:7 hybrid 32L             total    16.00GB  (+87.5% vs baseline)
  Jamba 1:3 hybrid 32L             total    32.00GB  (+75.0% vs baseline)
  Jamba 1:15 hybrid 32L            total     8.00GB  (+93.7% vs baseline)
  pure Mamba 32L                   total     4.00MB  (+100.0% vs baseline)

Attention layer fraction vs memory fraction at 256k (BF16)
  Jamba 1:7 hybrid 32L             attn_frac=0.125  kv_frac_of_total_cache=1.000
  ...
TAKEAWAY
  Pure Transformer at 256k = 67 GB just for KV cache ...
  Jamba 1:7 = 8.4 GB KV cache + ~4 MB SSM state = fits comfortably.
```

逐项解读：

- **8K 列的 Jamba 1:7 为 515.50MB**：KV cache `2 × 4 × 32 × 128 × 8192 × 2 = 512 MiB`，加 SSM 状态 3.5 MiB。这是唯一能看出 SSM 状态的地方——短上下文时两者才在同一量级附近。
- **所有行随上下文严格线性增长**（纯 Mamba 除外），每翻一倍上下文缓存翻一倍。
- **GQA 8 与 Jamba 1:3 完全相同**：都是"注意力层 × KV 头 = 256"。
- **+87.5%**：Jamba 1:7 相对纯 MHA 的节省，即讲义"8x reduction"。若与 GQA 8 纯 Transformer 比，只有 2 倍（16 vs 32）；但这是因为代码里的 Jamba 用的是 MHA，按真实 GQA 8 计算 Jamba 为 4 GiB，相对 GQA 纯 Transformer 依然是 8 倍。
- **`+93.7%`**：1:15 的真实值是 93.747%，四舍五入为 93.7。
- **表 3 的 1.000**：KV 在缓存中的占比约 0.9998，三位小数显示为 1.000。
- **takeaway 的 67 GB / 8.4 GB**：对应 128K 上下文的十进制数值，与表格 262K 列不符（测验 Q9）。

---

## 7. 动手改一改

1. **修正口径**：把表头改为 `ctx // 1024`；把 takeaway 改为根据计算结果动态生成，使其与表格一致。
2. **真实 Jamba 配置**：新增 "Jamba-v0.1 (GQA 8)" 配置（`n_kv_heads=8`），验证 256K 时 KV cache 为 4 GiB，相对 32 层 GQA 8 纯 Transformer 为 1/8。
3. **更真实的 SSM 状态**：给 `HybridConfig` 增加 `expand=2`、`d_conv=4` 字段，状态 = `(总层 − 注意力层) × expand × hidden × (state + d_conv − 1) × 字节`；再加一个 `state_bytes_per_elem=4`（FP32）选项。
4. **讲义练习 2**：对注意力层数 1、2、4、8、16、32 循环，打印 256K 时的 KV cache 与 SSM 状态，并求出两者相等时的上下文长度（提示：`ctx* = ssm_bytes / kv_bytes_per_token`）。
5. **并发估算**：增加参数 `gpu_mem=80e9, weight_bytes=52e9, reserve=4e9`，计算每种配置在 256K 时能并发多少条请求（测验 Q12）。
6. **FP8 KV cache**：用上 `BYTES_FP8`，增加一张 FP8 表，观察 KV cache 减半而 SSM 状态（若仍用 BF16/FP32）不变。

---

## 8. 常见坑

- **以为 Q 头数影响 KV cache**：只有 KV 头数和注意力层数影响缓存；`n_q_heads` 在本文件中根本没用到。
- **混用 GB 与 GiB、混用 128K 与 256K**：讲义与 takeaway 中的 8.4 GB、67 GB 都是 128K、十进制下的数字。
- **把"混合比 8x"套到 GQA 基线上**：8 倍是在 KV 头数相同的前提下比较的；若一边用 MHA、一边用 GQA，倍数就会变化。
- **忽略权重显存**：52B 模型 BF16 权重 104 GB，单卡 80GB 必须量化权重，"256K 单卡"并非无条件成立。
- **低估 SSM 状态**：Mamba 的状态宽度是 `expand × hidden`，还要加卷积状态；不过即使修正后也只是 MB 级。
- **把 SSM 状态当成可以随意截断/复用的缓存**：它代表"到当前位置为止的整个历史"，不能像 KV cache 那样按 token 截断，这对 prefix caching 和 speculative decoding 的回滚都有影响。
- **练习 3 的时间线**：讲义要你从 Jamba 论文（arXiv:2403.19887，2024 年 3 月）中找"为何用 Mamba-1 而非 Mamba-2"，但 Mamba-2（arXiv:2405.21060）是 2024 年 5 月才发布的，原始 Jamba 论文不可能讨论它；这类对比应到 Jamba 1.5 论文（arXiv:2408.12570）中去找。
- **练习 2 的比例写法**：讲义写"1:3 hybrid (4 Mamba : 1 Attention)"和"1:15 hybrid (14 Mamba : 1 Attention)"，比例与括号内的层数对不上；代码中 1:3 是 8 层注意力 + 24 层 Mamba，1:15 是 2 层注意力 + 30 层 Mamba，即"1 层注意力对 3 层 / 15 层 Mamba"。
