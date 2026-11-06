# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 12 节 边缘 Inference：Apple Neural Engine、Qualcomm Hexagon、WebGPU/WebLLM、Jetson ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`__future__`），无需网络、GPU 或 API key

---

## 1. 这份代码在考察什么

讲义的核心论断只有一句：**边缘设备上 decode 的速度由内存带宽决定，而不是算力**。这份不到 80 行的脚本把这句话变成一张表：

1. **带宽上限公式**：decode 每生成一个 token 要把全部权重读一遍，所以 `tok/s 上限 = 带宽 / 模型字节数`。
2. **"实测 / 上限" = 运行时效率**：把各平台的公开实测值放在上限旁边，看运行时把带宽用掉了多少。
3. **量化的作用**：同一台设备（iPhone 16），模型字节数减半，上限就翻倍。

它刻意不模拟算力、KV cache、热降频、内存容量——只保留"字节 / 带宽"这一个变量，让学习者看清第一性原理。也正因为简化得厉害，它的几处数字值得逐一推敲（见 3.4 与第 8 节）。

> 一句话：**用一个除法解释为什么同一个 8B 模型在 H100 上 170 tok/s、在 iPhone 上只有个位数**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Target` | `@dataclass` | 一个部署目标：名称、带宽、实测 tok/s、备注 | 边缘目标（ANE / Hexagon / WebGPU / Jetson） |
| `TARGETS` | 列表常量 | 9 个目标，从 H100 到手机浏览器 | 数据中心与边缘的带宽差距 |
| `ceiling()` | 函数 | `1 / (model_gb / bandwidth)` | 带宽上限 |
| `efficiency()` | 函数 | 实测 / 上限，格式化为百分比；无实测返回 `-` | 运行时效率 |
| `main()` | 函数 | 打印两张表：各目标上限对比、iPhone 16 上不同量化格式的上限 | 带宽瓶颈、量化收益 |

数据流：`TARGETS` → 对每个目标 `ceiling(t, 4.7)` → `efficiency(observed, ceiling)` → 打印表 1 → 固定 `iphone_bw = 60`，遍历 4 种格式大小 → 打印表 2。

---

## 3. 逐段精讲

### 3.1 `Target` 数据类

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Target:
    name: str
    bandwidth_gb_s: float
    observed_toks_per_s_llama8b_q4: float | None
    notes: str
```

- `@dataclass` 根据类型注解自动生成 `__init__`、`__repr__`、`__eq__`，所以后面可以直接写 `Target("Jetson AGX Orin", 205, 45, "...")` 按位置传参。
- `float | None` 表示"可能没有实测值"。这种 `X | Y` 写法在 Python 3.10 才能在运行时求值；`from __future__ import annotations` 让注解延迟成字符串，从而在更老的 3.7+ 上也不会报错。
- 字段名 `observed_toks_per_s_llama8b_q4` 很长，但它把**口径**写进了名字：这是"Llama 8B Q4 单流 decode"的实测值。后面会看到，有一条数据并不符合这个口径。

### 3.2 目标列表：带宽差距一目了然

```python
TARGETS = [
    Target("Datacenter H100 HBM3",  3350, 170,  "reference ceiling"),
    Target("Jetson AGX Orin",        205,  45,  "edge-datacenter bridge"),
    Target("Apple M3 Max",           400,  55,  "unified memory MPS"),
    Target("Apple M4 (MacBook Air)", 120,  25,  "consumer laptop"),
    Target("Apple A18 (iPhone 16)",   60,   8,  "phone with ANE"),
    Target("Snapdragon 8 Gen 3",      77,   7,  "mid/high Android"),
    Target("Snapdragon X Elite",     135,  22,  "Windows ARM laptop"),
    Target("WebGPU on M3 Max",       400,  41,  "browser penalty ~25%"),
    Target("WebGPU on Pixel 9",       77,   6,  "mobile browser Chrome 121+"),
]
```

- 带宽从 3350 GB/s（H100 的 HBM3）到 60 GB/s（iPhone），相差约 56 倍；讲义说"30–50x"，是按 2–3 TB/s 与 50–90 GB/s 的区间粗估的。
- 同一块 M3 Max 出现两次：原生 55 tok/s、WebGPU 41 tok/s，`41 / 55 ≈ 75%`，即备注"browser penalty ~25%"——**相对原生**损失 25%，这与讲义"roughly 70-80% of native"一致。
- `WebGPU on Pixel 9` 直接用了与 Snapdragon 8 Gen 3 相同的 77 GB/s，属于假设值，代码没有注明来源。

### 3.3 两个小函数：上限与效率

```python
def ceiling(target: Target, model_gb: float) -> float:
    seconds_per_token = model_gb / target.bandwidth_gb_s
    return 1 / seconds_per_token


def efficiency(observed: float | None, ceiling_val: float) -> str:
    if observed is None:
        return "    -"
    return f"{observed / ceiling_val * 100:4.0f}%"
```

- `ceiling` 先算"读一遍权重需要几秒"，再取倒数。它等价于 `bandwidth / model_gb`，写成两步是为了对应讲义的叙述："Reading 3.5 GB at 50 GB/s takes 70 ms — a theoretical ceiling of ~14 tok/s."
- 单位：GB / (GB/s) = 秒，倒数即 token/秒。这里隐含"每生成一个 token 恰好读一遍全部权重"，忽略了 KV cache 读取、激活读写和缓存命中。
- `efficiency` 返回字符串而不是数字，因为它直接用于打印。`:4.0f` 表示宽度 4、0 位小数。`None` 分支返回 `"    -"`（4 个空格加横线），在当前 `TARGETS` 中没有触发，因为每个目标都有实测值。

### 3.4 `main()` 第一张表：上限与效率

```python
    model_name = "Llama 3.1 8B Q4"
    model_gb = 4.7
    ...
    for t in TARGETS:
        c = ceiling(t, model_gb)
        obs = t.observed_toks_per_s_llama8b_q4
        eff = efficiency(obs, c)
        obs_display = f"{obs:>8.0f}  " if obs is not None else f"{'-':>10}  "
        print(f"{t.name:26}  {t.bandwidth_gb_s:8.0f}   {c:15.1f}   {obs_display}{eff:>11}  {t.notes}")
```

- 模型大小取 4.7 GB：8.03B 参数 × 约 4.7 bit / 8 ≈ 4.7 GB，相当于常见的 Q4_K_M 量级（Q4 量化还要存 scale 等元数据，所以每参数略多于 4 bit）。注意讲义正文用的是"7B Q4 = 3.5 GB"，两者口径不同。
- `obs_display` 用条件表达式处理"有 / 无实测值"两种情况；两边宽度分别是 `8+2` 和 `10+2`，保证列对齐。
- `header` 用 f-string 的对齐格式（`:26`、`:>9`、`:>16`）拼出表头，`"-" * len(header)` 画出等长分隔线。

**这张表里最值得追问的是 Jetson AGX Orin 一行**：上限 `205 / 4.7 = 43.6`，实测写的是 45，效率 103%。在"每 token 读一遍 4.7 GB"的模型下，效率不可能超过 100%。讲义里 AGX Orin 的"~40 tok/s"是 **gpt-oss-20b（MoE，每 token 只读激活参数）通过 vLLM** 的数字，很可能被挪用到了"Llama 8B Q4"这一列。这是代码与讲义口径不一致的地方，也是很好的教学点：**效率 > 100% 时先查数据口径，而不是怀疑物理**。

### 3.5 `main()` 第二张表：量化的影响

```python
    iphone_bw = 60.0
    for name, size in [("BF16", 18.8), ("INT8", 9.4), ("Q4 GGUF", 4.7), ("Q3 GGUF", 3.6)]:
        c = 1 / (size / iphone_bw)
        print(f"iPhone 16 + {name:8}  model={size:5.1f} GB  ceiling={c:6.1f} tok/s")
```

- 遍历 `(名称, 大小)` 元组列表并在 `for` 中直接解包。
- 结论"字节数减半 → 上限翻倍"是对的，这正是量化在边缘最直接的收益。
- 两处简化需要注意：
  1. **BF16 的 18.8 GB 是 `4.7 × 4` 乘出来的**。8.03B 参数 × 2 字节 ≈ 16.1 GB；INT8 也应约 8.5 GB 而非 9.4 GB。原因是 4.7 GB 对应约 4.7 bit/参数，不能当作恰好 4 bit 去倍乘。
  2. **没有容量检查**。iPhone 16 只有 8 GB 内存，BF16（18.8 GB）和 INT8（9.4 GB）根本装不下，打印出的 3.2 tok/s、6.4 tok/s 只是算术结果，不是能达到的速度。
- 名称写的是 "Q4 GGUF"，但讲义表格里 iOS 推荐的是 Core ML INT4 + FP16 激活；GGUF 是 llama.cpp（在 Apple 上走 Metal/MPS，不走 ANE）的格式。这里的名字只是用来标注大小。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用"字节 / 带宽"一个变量 | 把讲义的第一性原理讲透 | 忽略 KV cache 读取、算力、调度开销；生产估算应把"每步读取字节"写成 权重 + 当前 KV |
| 用峰值带宽 | 公开数据容易获得 | 实际可持续带宽低于峰值，还与 GPU、显示等共享；需要用实测带宽（如 STREAM 类基准）校准 |
| 实测值硬编码在表里 | 便于对比 | 来源、口径（单流 / 批处理、模型、量化、上下文长度）没有标注，出现了 103% 这种不可能的值；生产中每个数字应附来源与测试条件 |
| 量化表按比例乘出大小 | 代码简洁 | BF16/INT8 大小偏大；应按"参数量 × 每参数 bit 数"计算 |
| 不检查内存容量 | 聚焦速度 | 会打印装不下的模型的速度；配套 skill 要求"先判断能否装下再谈速度" |
| 单一模型（8B Q4） | 横向比较方便 | 看不到 MoE（只读激活参数）和小模型（3B）在边缘的优势 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头的三引号字符串 | 说明模块用途，可通过 `main.__doc__` 读取 |
| `from __future__ import annotations` | 文件第 8 行 | 注解延迟求值，使 `float \| None` 在旧版本 Python 中也不报错 |
| `@dataclass` | `@dataclass class Target:` | 根据字段注解自动生成构造函数等方法 |
| 类型注解 | `bandwidth_gb_s: float`、`-> float`、`-> None` | 只是说明，运行时不强制检查 |
| 联合类型 `X \| None` | `float \| None` | 表示"可能为空"，等价于 `Optional[float]` |
| `is None` 判断 | `if observed is None:` | 判断空值应用 `is`，不用 `==` |
| 条件表达式 | `f"..." if obs is not None else f"..."` | 一行内的 if/else |
| f-string 对齐与精度 | `{t.name:26}`、`{c:15.1f}`、`{eff:>11}`、`{obs:>8.0f}` | 宽度、右对齐 `>`、小数位数 |
| f-string 内嵌字面量 | `f"{'-':>10}  "` | 花括号里可以放任意表达式，包括字符串字面量 |
| 字符串乘法 | `"=" * 95`、`"-" * len(header)` | 重复字符串，画分隔线 |
| 元组解包遍历 | `for name, size in [("BF16", 18.8), ...]` | 每次取出一个元组并拆成两个变量 |
| 入口保护 | `if __name__ == "__main__": main()` | 直接运行时执行；被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`timeout 180 python3 main.py`，瞬间完成）：

```text
EDGE DECODE CEILING — Llama 3.1 8B Q4 (4.7 GB in HBM/DRAM)
Target                      BW (GB/s)   ceiling (tok/s)    observed   efficiency  Notes
Datacenter H100 HBM3            3350             712.8        170          24%  reference ceiling
Jetson AGX Orin                  205              43.6         45         103%  edge-datacenter bridge
Apple M3 Max                     400              85.1         55          65%  unified memory MPS
Apple M4 (MacBook Air)           120              25.5         25          98%  consumer laptop
Apple A18 (iPhone 16)             60              12.8          8          63%  phone with ANE
Snapdragon 8 Gen 3                77              16.4          7          43%  mid/high Android
Snapdragon X Elite               135              28.7         22          77%  Windows ARM laptop
WebGPU on M3 Max                 400              85.1         41          48%  browser penalty ~25%
WebGPU on Pixel 9                 77              16.4          6          37%  mobile browser Chrome 121+

QUANTIZATION IMPACT — same target, different format
iPhone 16 + BF16      model= 18.8 GB  ceiling=   3.2 tok/s
iPhone 16 + INT8      model=  9.4 GB  ceiling=   6.4 tok/s
iPhone 16 + Q4 GGUF   model=  4.7 GB  ceiling=  12.8 tok/s
iPhone 16 + Q3 GGUF   model=  3.6 GB  ceiling=  16.7 tok/s
```

逐项解读：

- **H100 只有 24%**：并不说明 H100 跑得差。单流 decode 在 H100 上还受 kernel 启动、同步等固定开销限制，数据中心真正的吞吐来自批处理（多个请求共享一次权重读取），单流效率低是常态。
- **AGX Orin 103%**：数据口径问题，见 3.4。
- **M4 MacBook Air 98%**：几乎贴着上限，属于非常乐观的数据，现实中很难稳定达到。
- **手机三行（A18 63%、Snapdragon 43%、Pixel WebGPU 37%）**：上限本身就只有 12.8–16.4 tok/s，再打折后只剩个位数，这就是讲义说"同一个模型在 iPhone 上只有 3 tok/s"的物理原因（讲义 The Problem 给 iPhone 16 Pro 的实测是 3 tok/s，代码写的是 8，两处不一致）。
- **WebGPU 与原生的对比**：同一块 M3 Max，原生 65%、WebGPU 48%，二者之比 `48/65 ≈ 41/55 ≈ 75%`，就是"浏览器罚 25%"。
- **量化表**：`60 / 4.7 = 12.8`，`60 / 3.6 = 16.7`，上限与字节数严格成反比；但 BF16、INT8 两行在 8 GB 的 iPhone 上装不下，只能当算术练习看。

---

## 7. 动手改一改

1. **完成讲义练习 1**：新增一个目标 `Target("7B Q4 on SD 8 Gen 3", 77, 7, "...")`，把 `model_gb` 改成 3.5，验证上限是 22 tok/s，效率约 32%。
2. **加容量检查**：给 `Target` 增加 `ram_gb` 字段（iPhone 16 为 8、Orin Nano Super 为 8、AGX Orin 为 64 等），在量化表中对 `size + 2.5 > ram_gb` 的格式打印 `DOES NOT FIT` 而不是速度。
3. **把 KV cache 读取量算进去**：实现 `ceiling_with_kv(bw, model_gb, ctx, kv_bytes_per_token)`，对 Llama 3.1 8B（每 token 131,072 字节）画出上下文 1K、4K、16K、32K 时的上限曲线（参考测验 Q10）。
4. **修正量化表的大小**：改成 `params * bits / 8`，参数量 8.03e9，BF16 = 16 bit、INT8 ≈ 8.5 bit、Q4 ≈ 4.7 bit、Q3 ≈ 3.6 bit，对比修改前后的上限。
5. **加入 MoE**：给函数增加 `active_gb` 参数，用"只读激活参数"计算 gpt-oss-20b 在 AGX Orin 上的上限，再与讲义的 ~40 tok/s 对比，解释 103% 那一行的来源。
6. **进阶**：给每个实测值加上 `source` 与 `conditions` 字段（模型、量化、上下文、batch、运行时），并让 `efficiency` 在结果 > 100% 时打印警告。

---

## 8. 常见坑

- **把公式写反**：`model_gb / bandwidth` 是"每 token 秒数"，要取倒数才是 tok/s。
- **把 TOPS 当速度**：38 TOPS 与 45 TOPS 的差别对 decode 几乎没影响；只看 TOPS 选设备会选错。
- **只算权重不算 KV cache**：长上下文时每步还要读全部 K/V，速度会随上下文增长而下降，内存也可能先爆。
- **只算速度不算容量**：代码会给 18.8 GB 的模型在 8 GB 手机上算出 3.2 tok/s；先判断能否装下，再谈速度。
- **混用不同口径的实测数据**：MoE 与稠密、单流与批处理、有无投机解码的数字不能放在同一列比较，否则就会出现 103%。
- **以为 llama.cpp 在 Mac 上用的是 ANE**：它的 Metal 后端用的是 MPS（GPU）；原生 ANE 只能经 Core ML。
- **以为 WebLLM 能加载 GGUF**：WebLLM 用 MLC 格式（q4f16_1），GGUF 不支持；配套 skill 文件中"Q4 GGUF (browser/edge CPU)"的说法与讲义表格矛盾。
