# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 07 节 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）；无需 GPU、无需网络

---

## 1. 这份代码在考察什么

这是一个约 100 行的"玩具经济学计算器"，把讲义里"Blackwell + TRT-LLM 比 H100 + vLLM 便宜 7 倍"的说法落到可以手算的公式上：

1. **显存账**：不同精度下权重占多少 GB（`params × bits / 8`），KV cache 占多少 GB。
2. **memory-bound decode 模型**：单 GPU decode 的 tok/s ≈ HBM 带宽 / 每 token 读取的权重字节，再乘上 MTP 与 disaggregation 的加速系数。
3. **成本账**：GPU 小时价格 / 每小时 token 数 → $/M tokens。
4. **叠加效应**：在 dense 70B、GPT-OSS-120B（MoE）、Llama 3.1 405B、DeepSeek-V3 规模 MoE 四个模型上，比较 5 个硬件 × 精度 × 引擎组合。

它对应讲义的"精度分工"（权重 NVFP4、KV FP8）、"Blackwell 特性"（MTP、disaggregation）和"7 倍差距从哪来"三部分。

> 一句话：**用"带宽 ÷ 字节"这一个公式，看清精度、硬件、草稿解码、编排各自贡献了多少倍——同时也要看清这个玩具模型在哪些地方与真实服务不符。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Stack` | `@dataclass` | 描述一个部署栈：HBM 容量/带宽、权重与 KV 位宽、MTP 与 disaggregation 系数、GPU 小时价 | 四层叠加选择 |
| `STACKS` | 列表常量 | 5 个栈：H100 BF16、H100 FP8、H200 FP8、B200 NVFP4、GB200 NVL72 | Hopper vs Blackwell |
| `hbm_footprint_gb` | 函数 | 返回 `(权重 GB, 单条序列 KV GB)` | 显存足迹 |
| `decode_throughput` | 函数 | 单 GPU、单流 decode 的 tok/s | memory-bound decode |
| `cost_per_million_tokens` | 函数 | 由 tok/s 和 GPU 单价算 $/M | token 经济学 |
| `print_stack` | 函数 | 对一个模型打印 5 个栈的对比表 | — |
| `main` | 函数 | 依次跑 4 个模型并打印 KEY FINDING | — |

数据流：`main` → `print_stack(params, active)` → 对每个 `Stack` 调 `hbm_footprint_gb` / `decode_throughput` / `cost_per_million_tokens` → 格式化打印一行。

---

## 3. 逐段精讲

### 3.1 模块 docstring：说明与实现的出入

```python
"""Toy Blackwell + TRT-LLM economics calculator — stdlib Python.

Computes HBM footprint and decode throughput for a model under three stacks:
  H100 + BF16 + vLLM
  H100 + FP8 + vLLM
  B200 + NVFP4 weights / FP8 KV + TRT-LLM + Dynamo
  GB200 NVL72 + NVFP4 / FP8 + TRT-LLM + Dynamo
```

- 文字说"three stacks"，下面列了 4 个，`STACKS` 实际有 **5 个**（多了 H200 + FP8）。讲义"Use It"也写"three stacks"。这类不一致不影响运行，但读代码时以 `STACKS` 为准。
- docstring 坦白了核心假设："tokens/sec is proportional to HBM-bandwidth / bytes-per-token"，以及"Numbers are pedagogical illustrations"——数值是示意，不是基准测试。

### 3.2 `Stack` 数据类与 5 个栈

```python
@dataclass
class Stack:
    name: str
    hbm_gb: int               # per-GPU HBM
    hbm_bw_tbs: float         # HBM bandwidth in TB/s
    weight_bits: float        # effective weight precision
    kv_bits: float            # KV cache precision
    mtp_factor: float         # 1.0 = no draft, 1.8 = MTP on
    disagg_factor: float      # additional throughput from disaggregation
    price_per_gpu_hour: float


STACKS = [
    Stack("H100 + BF16 + vLLM",           80, 3.35,  16, 16, 1.0,  1.0,  2.50),
    Stack("H100 + FP8 + vLLM",            80, 3.35,   8,  8, 1.0,  1.0,  2.50),
    Stack("H200 + FP8 + vLLM",           141, 4.80,   8,  8, 1.0,  1.0,  3.50),
    Stack("B200 + NVFP4 + FP8 + TRT-LLM", 192, 8.00,   4,  8, 1.8,  1.6,  4.80),
    Stack("GB200 NVL72 + TRT-LLM + Dyn", 192, 8.00,   4,  8, 1.8,  2.5,  6.20),
]
```

把参数排成一张表更直观：

| 栈 | HBM | 带宽 | 权重位宽 | KV 位宽 | MTP | disagg | $/GPU·h |
|----|-----|------|---------|---------|-----|--------|---------|
| H100 + BF16 | 80 GB | 3.35 TB/s | 16 | 16 | 1.0 | 1.0 | 2.50 |
| H100 + FP8 | 80 | 3.35 | 8 | 8 | 1.0 | 1.0 | 2.50 |
| H200 + FP8 | 141 | 4.80 | 8 | 8 | 1.0 | 1.0 | 3.50 |
| B200 + NVFP4 | 192 | 8.00 | **4** | **8** | 1.8 | 1.6 | 4.80 |
| GB200 NVL72 | 192 | 8.00 | 4 | 8 | 1.8 | 2.5 | 6.20 |

- Blackwell 两行正是讲义的"典型配置"：权重 4 bit（NVFP4），KV 8 bit（FP8）。
- `mtp_factor = 1.8`、`disagg_factor = 1.6 / 2.5` 是**直接给定的倍数**，不是由接受率、prefill/decode 比例推出来的；讲义 KEY FINDING 里"Dynamo: ~1.6–2.5x"的区间就是这两个值。
- 前三行都是 vLLM，`mtp_factor = 1.0`：代码假设 Hopper 栈不开 speculative decoding（实际上 vLLM 也支持 EAGLE 等草稿解码，见第 05 节），这让对比偏向 TRT-LLM。
- 价格是示意值。注意 B200 / H100 单价比 = 1.92，这个数后面会"吃掉"一半的吞吐优势。

### 3.3 `hbm_footprint_gb`：权重 + KV 的显存账

```python
def hbm_footprint_gb(params_b: float, active_b: float, seq_len: int, stack: Stack) -> tuple[float, float]:
    weight_gb = params_b * stack.weight_bits / 8
    layers = 64 * (active_b / 35.0)**0.5
    kv_heads = 8
    head_dim = 128
    kv_gb = layers * 2 * kv_heads * head_dim * seq_len * (stack.kv_bits / 8) / 1e9
    return weight_gb, kv_gb
```

- **权重**：`params_b`（以十亿计）× 位宽 / 8 = GB。注意这里用的是**总参数**——MoE 的所有专家都必须常驻显存，即使每个 token 只激活一部分。例如 120B MoE 在 NVFP4 下是 `120 × 4 / 8 = 60 GB`。
- **KV cache 公式**：`层数 × 2(K 和 V) × KV 头数 × head_dim × 序列长度 × 每元素字节`，这是标准公式，KV 头数取 8 体现了 GQA。
- ⚠️ **层数是启发式**：`64 × sqrt(active_b / 35)`。实际计算：70B → 90.5 层（Llama 70B 实为 80 层）；36B 激活 → 64.9 层；405B → **217.7 层**（Llama 3.1 405B 实为 126 层）。大 dense 模型上严重高估，405B 在 128k 上下文时代码给出 58.4 GB，按真实形状只有约 33.8 GB（见测验 Q11）。
- ⚠️ 对 DeepSeek-V3 规模的模型套用 GQA 形状也只是近似——该系列使用不同的注意力/KV 压缩方案，讲义和代码都没有建模。
- 返回的是**单条序列**的 KV；并发 N 条序列要乘 N。
- `kv_bits / 8` 把位宽换算成字节，`/ 1e9` 换算成 GB（十进制 GB）。

### 3.4 `decode_throughput`：带宽 ÷ 字节

```python
def decode_throughput(active_b: float, stack: Stack) -> float:
    """Tokens per second per GPU, memory-bandwidth-limited.
    Each decoded token reads `active_b * weight_bits/8` bytes of weights.
    """
    bytes_per_token = active_b * 1e9 * stack.weight_bits / 8
    raw_tokens_per_s = stack.hbm_bw_tbs * 1e12 / bytes_per_token
    return raw_tokens_per_s * stack.mtp_factor * stack.disagg_factor
```

这是整份代码的核心，对应讲义"decode 是 memory-bound"：

- 每生成一个 token，必须把**激活参数**全部从 HBM 读一遍（MoE 只读被路由到的专家，所以用 `active_b`）。
- `tok/s = 带宽 / 每 token 字节`。例：120B MoE、36B 激活、H100 FP8：`3.35e12 / 36e9 ≈ 93 tok/s`；B200 NVFP4：`8e12 / 18e9 ≈ 444`，再 `× 1.8 × 1.6 ≈ 1,280 tok/s`。
- 精度翻倍压缩 → 字节减半 → tok/s 翻倍，这就是"量化直接提速 decode"的来源。

需要清楚的四个简化：

1. **batch = 1**：一次读权重只服务一个请求。真实服务用 continuous batching 把读权重的开销摊到几十上百个请求上，所以代码的绝对 $/M 比讲义高约两个数量级（H100 FP8 行 $7.46/M vs 讲义 $0.09/M）。
2. **不读 KV**：`kv_bits` 完全不参与吞吐计算。长上下文、大 batch 时 KV 读取会成为主要带宽开销，而 Blackwell 栈的 KV 仍是 FP8，NVFP4 帮不上这部分。测验 Q9 的扩展计算显示 batch = 64 时差距从约 7 倍缩到约 4.3 倍。
3. **没有算力上限**：纯带宽模型永远不会进入 compute-bound。
4. 另外，多 GPU 部署（`fits` 标记为 multi-GPU 的行）仍按单卡算 tok/s 和单卡价格，等价于假设张量并行完美线性扩展（N 卡带宽 N 倍、价格 N 倍，$/M 不变），忽略了卡间通信。

### 3.5 `cost_per_million_tokens`：价格 ÷ 产量

```python
def cost_per_million_tokens(active_b: float, stack: Stack) -> float:
    tps = decode_throughput(active_b, stack)
    tokens_per_hour = tps * 3600
    return stack.price_per_gpu_hour / tokens_per_hour * 1e6
```

- `$/M = 每小时价格 / 每小时 token 数 × 1,000,000`。
- 由此可以推出代码中"7 倍"的真正来源：B200 vs H100 FP8，tok/s 比 `= (8/3.35) × 2 × 1.8 × 1.6 ≈ 13.76`，价格比 `4.80 / 2.50 = 1.92`，成本比 `≈ 7.16`。**从 14 倍到 7 倍的"折半"来自 GPU 单价**，而不是 KEY FINDING 文案里说的"overhead and real-traffic alpha"。
- 同理 H200 FP8 比 H100 FP8 快 1.43 倍（4.8/3.35），但贵 1.4 倍，$/M 几乎不变（7.29 vs 7.46）。这说明"换更快的卡"不一定更省钱，要看每美元带宽。

### 3.6 `print_stack` 与 `main`：四个模型、一段结论

```python
def print_stack(params_b: float, active_b: float, seq_len: int = 8192) -> None:
    ...
    for s in STACKS:
        w, kv = hbm_footprint_gb(params_b, active_b, seq_len, s)
        tps = decode_throughput(active_b, s)
        cost = cost_per_million_tokens(active_b, s)
        fits = "" if (w + kv) <= s.hbm_gb else "  (multi-GPU)"
        print(f"{s.name:40} {w:7.1f} {kv:7.2f} {tps:9.0f} {cost:10.4f}{fits}")
```

- `fits` 只比较"权重 + 单条序列 KV"与单卡 HBM，没有留激活、运行时、并发 KV 的余量。例如 70B FP8 在 H100 上 `70 + 1.52 = 71.5 ≤ 80` 被判定为"能放下"，实际只剩不到 9 GB 给并发请求，生产中基本不可用。
- `main` 依次调用 `print_stack(70, 70)`（dense 70B）、`(120, 36)`（GPT-OSS-120B，注释写"30% active"）、`(405, 405)`（Llama 3.1 405B）、`(671, 37)`（DeepSeek-V3 规模）。
- KEY FINDING 是**硬编码的文字**，不是由上面的计算生成的：四个因子 `2.4 × 2.0 × 1.8 × 2.0 = 17.3`，并不等于打印的"~14x"（14 对应 disaggregation 取 1.6）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 memory-bound 模型（带宽 ÷ 字节） | 一个公式就能说明"精度 → 速度"的线性关系 | 忽略算力上限、kernel 效率、反量化开销；生产中用真实压测（如第 22 节的负载测试）测 tok/s |
| batch = 1 | 公式最简单，比例关系清楚 | 绝对 $/M 偏高约 70–80 倍；真实服务应按 batch、并发和 goodput 计算 |
| KV 不计入带宽 | 突出"权重量化"的作用 | 长上下文/大 batch 时高估 NVFP4 的收益（见测验 Q9） |
| MTP、disaggregation 用固定倍数 | 避免引入接受率、P/D 比例等更多参数 | 真实倍数随负载变化，需实测 MTP 接受率和 P/D 配比 |
| 层数用 `64·sqrt(active/35)` 估算 | 不必为每个模型查配置 | 大 dense 模型层数严重高估；生产中直接读模型 config（层数、KV 头、head_dim） |
| 多 GPU 行仍按单卡算成本 | 假设张量并行完美扩展 | 忽略通信开销，NVLink 拓扑不同时差别很大 |
| KEY FINDING 硬编码 | 给出讲义的叙事结论 | 与计算结果不完全一致（17.3 vs 14；7 倍其实来自单价比） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可以在旧版本 Python 中写 `tuple[float, float]` 这类新语法 |
| `@dataclass` | `@dataclass class Stack:` | 根据带类型注解的类属性自动生成 `__init__`、`__repr__` 等；`Stack("H100...", 80, 3.35, ...)` 按字段顺序传参 |
| 类型注解 | `def decode_throughput(active_b: float, stack: Stack) -> float:` | 标注参数和返回值类型，仅作文档与静态检查，运行时不强制 |
| 返回元组 + 解包 | `return weight_gb, kv_gb`；`w, kv = hbm_footprint_gb(...)` | 一次返回多个值，调用处直接拆开 |
| 幂运算 | `(active_b / 35.0)**0.5` | `**0.5` 即开平方 |
| 科学计数法字面量 | `1e9`、`1e12`、`1e6` | 浮点数 10⁹、10¹²、10⁶ |
| 默认参数 | `def print_stack(params_b, active_b, seq_len: int = 8192)` | 不传时取 8192 |
| 条件表达式 | `fits = "" if (w + kv) <= s.hbm_gb else "  (multi-GPU)"` | 一行写 if/else 取值 |
| f-string 宽度与对齐 | `{s.name:40}`、`{'W GB':>7}` | 字符串默认左对齐到 40 宽；`>` 右对齐 |
| f-string 数值格式 | `{w:7.1f}`、`{tps:9.0f}`、`{cost:10.4f}`、`{seq_len:,}` | 宽度 + 小数位；`,` 加千分位（`8,192`） |
| 字符串乘法 | `"=" * 90` | 重复字符串画分隔线 |
| 文档字符串 | 函数下第一行 `"""Tokens per second ..."""` | 可通过 `help(decode_throughput)` 查看 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`；被 `import main` 时不执行，便于在别处复用函数 |

---

## 6. 运行结果解读

实际运行（Python 3，`python3 main.py`，耗时约 0.06 秒，输出确定、无随机性）。截取 GPT-OSS-120B 一段：

```text
Model: 120B total, 36B active, 8,192 tokens context
------------------------------------------------------------------------------------------
stack                                       W GB   KV GB     tok/s    $/M tok
H100 + BF16 + vLLM                         240.0    2.18        47    14.9254  (multi-GPU)
H100 + FP8 + vLLM                          120.0    1.09        93     7.4627  (multi-GPU)
H200 + FP8 + vLLM                          120.0    1.09       133     7.2917
B200 + NVFP4 + FP8 + TRT-LLM                60.0    1.09      1280     1.0417
GB200 NVL72 + TRT-LLM + Dyn                 60.0    1.09      2000     0.8611
```

逐项解读：

- **W GB**：`120 × 16/8 = 240`，`× 8/8 = 120`，`× 4/8 = 60`，严格按位宽减半。
- **KV GB**：BF16 2.18 → FP8 1.09；Blackwell 行 KV 仍是 FP8，与 H100 FP8 相同（1.09）——权重降到 4 bit，KV 不动，正是讲义的分工。
- **tok/s**：47 → 93（精度减半，翻倍）→ 133（H200 带宽 4.8/3.35 = 1.43 倍）→ 1,280（带宽 2.39 × 精度 2 × MTP 1.8 × disagg 1.6）→ 2,000（disagg 换成 2.5）。最大的一跳来自 H200 → B200，四个因子在这里同时生效（讲义练习 1 的答案）。
- **$/M**：H100 FP8 / B200 = 7.16 倍；H100 BF16 / GB200 = 17.3 倍；H200 与 H100 FP8 几乎一样（价格涨幅 ≈ 带宽涨幅）。
- **(multi-GPU)**：H200 141 GB 能放下 120 + 1.09，所以没有标记；H100 80 GB 放不下 120 GB 权重。

其它三个模型的要点：

```text
Model: 70B total, 70B active ...
H100 + BF16 + vLLM                         140.0    3.04        24    29.0216  (multi-GPU)
B200 + NVFP4 + FP8 + TRT-LLM                35.0    1.52       658     2.0255
Model: 405B total, 405B active ...
B200 + NVFP4 + FP8 + TRT-LLM               202.5    3.65       114    11.7188  (multi-GPU)
Model: 671B total, 37B active ...
H100 + BF16 + vLLM                        1342.0    2.21        45    15.3400  (multi-GPU)
GB200 NVL72 + TRT-LLM + Dyn                335.5    1.10      1946     0.8850  (multi-GPU)
```

- 70B dense 在 H100 BF16 只有 24 tok/s（`3.35e12 / 140e9`），这是"单流 decode 很慢"的直观感受。
- 405B NVFP4 权重 202.5 GB 超过单卡 192 GB，即使在 B200 上也要多卡。
- 671B MoE 只激活 37B，tok/s 与 120B MoE 接近，但权重需要 335.5 GB（NVFP4）——**MoE 省的是带宽和算力，不省显存容量**。

最后的 KEY FINDING 是硬编码文字，与上面的计算对照：四因子乘积应为 17.3（或 disagg 取 1.6 时 13.8），而 7 倍来自 GPU 单价比 1.92，详见第 3.5 节与测验 Q10。

---

## 7. 动手改一改

1. **（入门）** 讲义练习 1：只看 120B 那张表，把 tok/s 依次相除，写出 H100 BF16 → H100 FP8 → H200 FP8 → B200 → GB200 每一步的倍数，并标出每一步是哪个字段在起作用。
2. **（入门）** 给 vLLM 栈也打开草稿解码：把 H100 FP8 的 `mtp_factor` 改成 1.8（vLLM 也支持 EAGLE 类草稿），重新看 B200 相对 H100 的成本差距还剩多少。
3. **（进阶）** 把 `decode_throughput` 改为支持 `batch` 参数，并把 KV 读取计入每步字节数（参考测验 Q9）；画出 batch = 1、4、16、64、256 时两种栈的 $/M 曲线，观察差距如何收窄。
4. **（进阶）** 用真实模型配置替换层数启发式：给 `print_stack` 增加 `layers`、`kv_heads`、`head_dim` 参数，用 Llama 3.1 405B（126 层、8 KV 头、128 head_dim）完成讲义练习 5，计算 128k 上下文下单卡/NVL72 能并发多少条序列。
5. **（进阶）** 为 `fits` 增加 20% 的运行时余量，并输出"至少需要几张卡"（`ceil((w + kv × 并发) / (hbm × 0.8))`）。
6. **（挑战）** 实现讲义练习 2 的回本计算：输入年支出、成本倍数、迁移工程成本、GPU 价格（或租金），输出回本月数，并按 skill 文件规则在年支出 < $500K 或回本 > 18 个月时给出警告。

---

## 8. 常见坑

- **把玩具的绝对 $/M 当真**：代码是 batch = 1，绝对值比讲义高 70–80 倍，只能看相对比例。
- **只说"7 倍"不说基线**：相对 H100 FP8 约 7.2 倍，相对 H100 BF16 约 17 倍；还要说明是否包含 MTP、disaggregation 和 GPU 单价差。
- **忘了 MoE 的显存按总参数算**：tok/s 看激活参数，显存看总参数，671B MoE 的权重仍是 335.5 GB（NVFP4）。
- **把 KV cache 也压到 FP4**：讲义明确指出会导致 attention 分数崩塌；本代码也让 Blackwell 栈的 KV 保持 8 bit。
- **以为量化后吞吐线性提升永远成立**：大 batch、长上下文时 KV 读取占主导，或进入 compute-bound 后，权重量化的收益会递减。
- **相信层数启发式**：405B 被估成 217.7 层，KV 被高估约 1.7 倍；应读真实模型配置。
- **`fits` 判断过于乐观**：不含激活、运行时开销和并发 KV，"能放下"不等于"能服务"。
- **忽略质量验证**：NVFP4 对推理类负载会明显掉点，任何转换都要先在 eval set 上验证。
