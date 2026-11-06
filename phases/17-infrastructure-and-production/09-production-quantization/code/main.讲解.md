# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 09 节 生产环境中的 Quantization：AWQ、GPTQ、GGUF K-quants、FP8、MXFP4/NVFP4 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）；无需 GPU、无需网络

---

## 1. 这份代码在考察什么

这是一个"量化格式的显存与吞吐计算器"。它把 7 种部署配置（BF16 基线 + 讲义的 6 种生产格式）放在 4 个场景（7B、70B 两种负载、405B）下比较：

1. **显存三件套**：权重（随格式变化）+ KV cache（随并发 × 上下文线性增长，**与权重格式无关**，只看 KV 位宽）+ 激活（粗略常数）。
2. **能放进哪张卡**：按总显存判定 H100 80GB / H200 141GB / B200 192GB / 多卡。
3. **相对吞吐**：memory-bound 假设下 `16 / 权重位宽`。

它对应讲义的"六种格式"表格、"KV cache 陷阱"（权重量化不动 KV）和"按硬件/引擎/负载选格式"三部分。

> 一句话：**用一张表让你看到"把权重压到 4 bit"之后，显存账里还剩下多大一块 KV cache**——以及这个玩具模型在吞吐和硬件兼容性上省略了什么。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Format` | `@dataclass` | 一种部署格式：名称、权重位宽、KV 位宽、引擎、备注 | 六种生产格式 |
| `FORMATS` | 列表常量 | 7 行：BF16、GGUF Q5_K_M、GGUF Q4_K_M、GPTQ、AWQ、FP8、NVFP4 + FP8 KV | 格式动物园 |
| `memory_breakdown` | 函数 | 返回 `{"weight", "kv", "act", "total"}`（GB） | HBM 整体预算 |
| `relative_throughput` | 函数 | `16 / weight_bits`，以 BF16 = 1.0 | memory-bound decode |
| `gpu_check` | 函数 | 按总显存给出最小能放下的 GPU | 硬件选择 |
| `print_scenario` | 函数 | 打印一个场景下 7 种格式的对比表 | — |
| `main` | 函数 | 跑 4 个场景并打印 KEY FINDINGS | — |

数据流：`main` → `print_scenario(params, conc, ctx)` → 对每个 `Format` 调 `memory_breakdown` → `gpu_check(total)` 与 `relative_throughput(fmt)` → 打印一行。

---

## 3. 逐段精讲

### 3.1 `Format` 与 7 种配置

```python
@dataclass
class Format:
    name: str
    weight_bits: float
    kv_bits: float
    engine: str
    notes: str


FORMATS = [
    Format("BF16 baseline (vLLM)",       16, 16, "vLLM",     "reference"),
    Format("GGUF Q5_K_M (llama.cpp)",     5, 16, "llama.cpp", "CPU/edge"),
    Format("GGUF Q4_K_M (llama.cpp)",     4, 16, "llama.cpp", "CPU/edge, default"),
    Format("GPTQ-Int4 + Marlin (vLLM)",   4, 16, "vLLM",     "multi-LoRA support"),
    Format("AWQ-Int4 + Marlin (vLLM)",    4, 16, "vLLM",     "best Pass@1 at INT4"),
    Format("FP8 (vLLM / TRT-LLM)",        8,  8, "multi",    "safe default reasoning"),
    Format("NVFP4 + FP8 KV (TRT-LLM)",    4,  8, "TRT-LLM",  "Blackwell aggressive"),
]
```

- 每种格式被抽象成两个数：**权重位宽**和 **KV 位宽**。这正是讲义"KV cache is separate from weight quantization"的建模方式：GGUF、GPTQ、AWQ 只改权重，KV 仍是 16 bit；FP8 两者都是 8 bit；NVFP4 行权重 4 bit、KV 8 bit。
- `engine` 和 `notes` 只用于显示，**不参与任何计算**——这一点在 3.4、3.5 节会变成问题。
- ⚠️ 位宽是"名义值"。真实的 4-bit 格式还要存每组的 scale（以及 zero point），有效位宽略高于 4（例如分组量化通常每组 128 个权重共享一组 scale；GGUF K-quants 带多级 scale，Q4_K_M 内部还混用了更高位宽的块）。代码统一用整数 4 / 5，会略微低估权重显存。

### 3.2 `memory_breakdown`：三件套显存

```python
def memory_breakdown(params_b: float, fmt: Format,
                     concurrency: int = 128, ctx: int = 2048) -> dict:
    weight_gb = params_b * fmt.weight_bits / 8
    layers = 64 * (params_b / 70.0)**0.5
    kv_heads = 8
    head_dim = 128
    per_seq_kv_gb = layers * 2 * kv_heads * head_dim * ctx * (fmt.kv_bits / 8) / 1e9
    kv_total = per_seq_kv_gb * concurrency
    activations_gb = 0.05 * params_b       # rough constant
    return {
        "weight": weight_gb,
        "kv": kv_total,
        "act": activations_gb,
        "total": weight_gb + kv_total + activations_gb,
    }
```

- **权重**：`params_b × bits / 8`。70B：BF16 140 GB、FP8 70 GB、INT4 35 GB。
- **KV**：标准公式 `层数 × 2(K,V) × KV 头 × head_dim × ctx × 字节`，再乘并发数。**线性**依赖并发和上下文：70B 从 128 × 2k 到 256 × 8k，KV 放大 8 倍（BF16 68.7 → 549.8 GB）。
- **激活**：`0.05 × params_b`，70B 为 3.5 GB（讲义写约 5 GB）。真实激活随 batch 内 token 数和实现变化，这里只是占位常数。
- ⚠️ **层数启发式** `64 × sqrt(params/70)`：7B → 20.2 层、70B → 64 层、405B → 153.9 层。真实值分别约为 32、80、126 层；7B 级模型的 KV 头数也因模型而异（例如 Llama 2 7B 是 32 个 KV 头的 MHA，Mistral 7B 是 8 个 KV 头）。所以代码的 KV 数字只是数量级示意：70B 时它给出 68.7 GB，按 Llama 3 70B 真实形状（80 层、8 KV 头）应为约 85.9 GB。
- ⚠️ **与讲义的冲突**：讲义"KV cache 陷阱"一节说 70B、128 并发 × 2k 的 KV 约 20 GB、AWQ 总计约 60 GB 能放进 H100；代码自己算出 68.7 GB、总计 107.2 GB、需要 H200。讲义的数字低估了 3–4 倍（详见测验 Q9）。
- 返回 `dict`（字典），调用方用 `m['weight']` 取值；用 `dataclass` 或 `TypedDict` 会更类型安全。

### 3.3 `relative_throughput`：只看权重位宽

```python
def relative_throughput(fmt: Format) -> float:
    """Decode is memory-bandwidth-limited. Fewer weight bytes per token = higher throughput.
    Normalize to BF16 = 1.0."""
    return 16 / fmt.weight_bits
```

- BF16 1.00x、Q5 3.20x、所有 4-bit 4.00x、FP8 2.00x。
- ⚠️ 三个被忽略的因素：
  1. **引擎与 kernel**：`engine` 不参与计算，GGUF Q4_K_M 与 AWQ + Marlin 都给 4.00x，但讲义的实测是 GGUF 在 vLLM 约 93 tok/s、AWQ + Marlin 约 741 tok/s（相差约 8 倍）。KEY FINDING 5 自己也承认"~93 tok/s in vLLM ... is the wrong engine"，但表格看不出这一点。
  2. **KV 读取**：`kv_bits` 不参与计算。并发 128、2k 上下文时 KV（68.7 GB）比 INT4 权重（35 GB）还大；计入 KV 后，AWQ 的相对吞吐从 4.00x 降到约 2.01x，与 FP8（2.00x）打平，NVFP4 + FP8 KV 为约 3.01x（测验 Q11 的实际计算）。
  3. **反量化开销与算力上限**：weight-only INT4 需要在 kernel 里反量化；大 batch 时进入 compute-bound，位宽减半不再意味着吞吐翻倍。
- 所以这一列应理解为"理想上限"，而不是预期吞吐。

### 3.4 `gpu_check`：只比容量

```python
def gpu_check(total_gb: float) -> str:
    if total_gb <= 80:
        return "H100 80GB"
    if total_gb <= 141:
        return "H200 141GB"
    if total_gb <= 192:
        return "B200 192GB"
    return "MULTI-GPU"
```

- 一串 `if` 从小到大比较，返回第一个放得下的 GPU。
- ⚠️ **不检查格式与硬件的兼容性**：70B / 128 / 2k 场景下，`NVFP4 + FP8 KV` 总量 72.9 GB 被判为 "H100 80GB"，但 NVFP4 需要 Blackwell 的 FP4 Tensor Core（`notes` 就写着 "Blackwell aggressive"）。GGUF 行同样被判到 GPU，而它的主场是 CPU。
- ⚠️ **不留余量**：72.9 GB 对 80 GB 只剩 7 GB，实际还有 CUDA 上下文、CUDA graph、碎片等开销；生产中通常只把 HBM 的 85%–90% 当作可用。
- 想在 H100 上真正达到 72.9 GB，应使用"AWQ 权重 + FP8 KV"的组合（讲义练习 5），代码里没有这一行。

### 3.5 `print_scenario` 与 `main`

```python
    print_scenario(params_b=7, concurrency=128, ctx=2048)
    print_scenario(params_b=70, concurrency=128, ctx=2048)
    print_scenario(params_b=70, concurrency=256, ctx=8192)
    print_scenario(params_b=405, concurrency=128, ctx=2048)
```

- 四个场景：小模型、70B 常规负载、70B 高并发长上下文、405B。
- 表头 `f"{'format':36} {'W GB':>7} ..."` 用 f-string 对齐列宽；每行 `f"{tput:10.2f}x"` 在数字后加 `x`。
- KEY FINDINGS 是硬编码文字：
  1. "KV cache grows linearly with concurrency × context"——与输出一致（70B 256 × 8k 时 KV 占 AWQ 总量的约 93%）。
  2. "AWQ vs GPTQ = same 4-bit footprint"——一致，两行数字完全相同。
  3. "NVFP4 + FP8 KV stacks: shrink weights AND KV"——一致，但 FP8 行同样压缩了 KV，并非 NVFP4 独有。
  4. "For reasoning workloads, FP8 is the safe default"——来自讲义，代码没有质量建模。
  5. "GGUF ... wrong engine"——正确，但表格里 GGUF 的 4.00x 恰好给出了相反的印象。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 格式 = (权重位宽, KV 位宽) | 用两个数说清"权重量化与 KV 量化是两件事" | 忽略 scale / zero point 开销、混合精度块；生产中直接看量化后 checkpoint 的实际大小 |
| 层数用 `64·sqrt(params/70)` | 不必为每个模型查配置 | 层数与 KV 头数都不准，KV 误差可达 20%–40%；生产中读模型 `config.json` |
| 激活取 `0.05 × params` | 占位常数 | 真实激活随 batch token 数变化；生产中用引擎的 profiling（如 vLLM 的显存探测）|
| 吞吐只看权重位宽 | 体现 memory-bound 的一阶效应 | 忽略 kernel/引擎（GGUF 在 vLLM 慢 8 倍）、KV 读取、反量化；生产中按格式 × 引擎实测 |
| `gpu_check` 只比容量 | 简单直观 | 不检查硬件是否支持格式、不留余量；生产中要同时满足"放得下"和"跑得了" |
| 所有序列都满上下文 | 给出最坏情况的 KV | PagedAttention 按实际长度分配，平均情况通常更好 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值注解 |
| `@dataclass` | `class Format:` | 自动生成构造函数；`Format("BF16 ...", 16, 16, "vLLM", "reference")` 按字段顺序传参 |
| 类型注解 | `params_b: float`、`-> dict`、`-> str` | 文档作用 |
| 多行参数 | `def memory_breakdown(params_b: float, fmt: Format,\n concurrency: int = 128, ctx: int = 2048)` | 括号内可以自由换行 |
| 关键字参数调用 | `print_scenario(params_b=7, concurrency=128, ctx=2048)` | 按名字传参，可读性好、顺序无关 |
| 字典字面量 | `return {"weight": weight_gb, "kv": kv_total, ...}` | 返回多个具名结果 |
| 字典取值 | `m['weight']` | 在 f-string 里取字典值时外层用双引号、内层用单引号 |
| 幂运算开方 | `(params_b / 70.0)**0.5` | `**0.5` 即平方根 |
| 早返回的 `if` 链 | `gpu_check` | 依次判断，第一个满足条件就 `return` |
| f-string 对齐 | `{f.name:36}`、`{'W GB':>7}`、`{gpu_check(...):>14}` | 左对齐到 36；`>` 右对齐；花括号里可以直接调用函数 |
| f-string 数值格式 | `{m['total']:7.1f}`、`{tput:10.2f}x` | 宽度 + 小数位；格式化后的字面量 `x` 紧跟其后 |
| 字符串重复 | `"=" * 98` | 画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行，便于在练习中复用 `memory_breakdown` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，输出确定）。截取最关键的两个场景：

```text
Model: 70B params  |  concurrency 128  |  ctx 2048
format                                  W GB   KV GB  Act GB   Total        fits on   rel tput
BF16 baseline (vLLM)                   140.0    68.7     3.5   212.2      MULTI-GPU       1.00x
GGUF Q4_K_M (llama.cpp)                 35.0    68.7     3.5   107.2     H200 141GB       4.00x
AWQ-Int4 + Marlin (vLLM)                35.0    68.7     3.5   107.2     H200 141GB       4.00x
FP8 (vLLM / TRT-LLM)                    70.0    34.4     3.5   107.9     H200 141GB       2.00x
NVFP4 + FP8 KV (TRT-LLM)                35.0    34.4     3.5    72.9      H100 80GB       4.00x

Model: 70B params  |  concurrency 256  |  ctx 8192
AWQ-Int4 + Marlin (vLLM)                35.0   549.8     3.5   588.3      MULTI-GPU       4.00x
FP8 (vLLM / TRT-LLM)                    70.0   274.9     3.5   348.4      MULTI-GPU       2.00x
NVFP4 + FP8 KV (TRT-LLM)                35.0   274.9     3.5   313.4      MULTI-GPU       4.00x
```

逐项解读：

- **AWQ 与 FP8 的总显存几乎相同**（107.2 vs 107.9 GB）：AWQ 权重省了 35 GB，但 KV 仍是 BF16，多了 34.3 GB；FP8 权重多 35 GB，但 KV 省一半。**在高并发下，"只压权重"和"权重 + KV 各压一半"殊途同归**。
- **NVFP4 + FP8 KV 是唯一 < 80 GB 的行**，但它需要 Blackwell；`gpu_check` 把它判到 H100 是误导（见 3.4）。
- **256 × 8k 场景**：KV 达到 549.8 GB（BF16），占 AWQ 行总量的约 93%；即使 NVFP4 + FP8 KV 也要 313 GB，必须多卡。这就是 KEY FINDING 1 "KV alone dwarfs weight savings"。
- **7B 场景**（未贴出）：BF16 总量 36.1 GB，KV 21.7 GB 已超过权重 14 GB；所有格式都能放进 H100。小模型的瓶颈几乎全在 KV。
- **405B 场景**：BF16 995.5 GB、NVFP4 + FP8 KV 305.4 GB，全部多卡；FP8（507.9）反而比 AWQ（388.0）大，因为此时权重是大头（405 层数启发式给出 153.9 层，偏高）。
- **rel tput 列**：只反映权重位宽，与讲义的实测吞吐（GGUF 在 vLLM 93 tok/s vs AWQ 741 tok/s）不一致；计入 KV 读取后，70B / 128 / 2k 下 AWQ 约 2.01x、FP8 约 2.00x、NVFP4 + FP8 KV 约 3.01x。

---

## 7. 动手改一改

1. **（入门）** 讲义练习 1：只看 70B / 128 / 2k 那张表，哪些格式能放进单张 H100 80GB？再把 `gpu_check` 改为只使用 HBM 的 90%，结论有什么变化？
2. **（入门）** 讲义练习 5：在 `FORMATS` 中加入 `Format("AWQ-Int4 + FP8 KV (vLLM)", 4, 8, "vLLM", "H100-friendly")`，比较它与 NVFP4 + FP8 KV 的数字，说明二者的差别在于硬件而不是显存。
3. **（进阶）** 给 `Format` 增加 `hardware: set[str]` 字段（例如 NVFP4 → `{"B200", "GB200"}`，GGUF → `{"CPU", ...}`），让 `gpu_check` 只在支持的硬件里挑选。
4. **（进阶）** 用真实模型配置替换层数启发式：给 `memory_breakdown` 增加 `layers`、`kv_heads`、`head_dim` 参数，用 Llama 3 70B（80 / 8 / 128）重算，并实现 `max_concurrency()`（参考测验 Q10）。
5. **（进阶）** 实现 KV 感知的吞吐（参考测验 Q11），再加一个 `kernel_efficiency` 字段（例如 GGUF-in-vLLM 取 93/741），让表格同时反映讲义的实测差距。
6. **（挑战）** 把 skill 文件的决策树写成 `pick_format()`，输入硬件、引擎、负载、是否需要 LoRA、是否已验证 NVFP4，输出格式 + 显存预算 + 校准/验证/回滚计划（参考测验 Q12）。

---

## 8. 常见坑

- **只算权重不算 KV**：讲义的"4 GB 陷阱"；本代码的 7B 场景中 KV 已比权重大，70B 高并发长上下文时 KV 占 90% 以上。
- **相信讲义的"~20 GB KV"**：按代码或真实形状，70B / 128 / 2k 的 BF16 KV 是 69–86 GB。
- **以为同样 4 bit 就一样快**：GGUF 在 vLLM 里慢一个数量级；AWQ / GPTQ 也要 Marlin kernel 才快。
- **只按容量选 GPU**：NVFP4 在 H100 上跑不了；GGUF 在 GPU 上不是最佳。
- **用通用语料校准领域模型**：讲义的校准陷阱；代码不建模质量，但上线前必须做 eval。
- **把 KV 量化当成免费**：FP8 / INT8 KV 直接影响 attention 精度，推理与长上下文任务要先验证。
- **忽略 scale 开销**：4-bit 格式的实际文件大小略大于 `params × 0.5` 字节，规划显存时要留余量。
- **不留运行时余量**：72.9 / 80 GB 看似能放，实际可能因 CUDA graph、碎片而 OOM。
