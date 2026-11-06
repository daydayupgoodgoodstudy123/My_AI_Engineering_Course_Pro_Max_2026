# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 10 节 InternVL3：原生多模态 Pretraining ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`__future__`）

---

## 1. 这份代码在考察什么

这节讲义讨论的是"训练策略与部署策略"，没有可以在 CPU 上跑的模型。代码用三个"记账"玩具把讲义里的数字算出来：

1. **语料配比 → 训练步数**（`CorpusMix`）：把 40 / 35 / 20 / 5 的配比换算成 50 万步训练中每种数据各占多少步。
2. **ViR 路由模拟**（`vir_sim`）：按查询分布计算平均视觉 token 数，以及相对"全部走高分辨率"的加速比。
3. **DvD 吞吐估算**（`dvd_throughput`）：比较 encoder 与 LLM"同卡串行"和"分卡流水"的耗时。

最后打印一张"后接式 vs 原生预训练"的对比表。

对应讲义的核心概念：原生多模态预训练、语料配比、对齐债、ViR、DvD、原生预训练的代价。

> 一句话：**把"配比、路由、拆分部署"三件事写成几行加权求和和 max/sum，让你能动手算、动手改**。但其中的加速比计算有明显的简化甚至不公平之处（尤其是 DvD 用两块 GPU 对比一块 GPU），这些恰恰是本节最值得讨论的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CorpusMix` | `@dataclass` | 四种数据的占比；`normalize()` 原地归一化；`steps(total)` 换算步数 | 原生预训练语料配比 |
| `RouterTier` | `@dataclass` | 一个路由档位：名字、视觉 token 数、流量占比 | ViR 的三档 |
| `vir_sim(tiers)` | 函数 | 加权平均 token 数、最高档 token 数、二者之比 | ViR 吞吐收益 |
| `dvd_throughput(encoder_flops, llm_flops, llm_tokens)` | 函数 | 串行耗时 = 两者之和；分离耗时 = 两者最大值；返回比值 | DvD 部署 |
| `posthoc_vs_native_table()` | 函数 | 打印对比表 | 后接式 vs 原生 |
| `main()` | 函数 | 依次打印四部分 | 入口 |

数据流：`main()` → 构造 `CorpusMix(40, 35, 20, 5)` → `normalize()` → `steps(500_000)` → 打印；构造三个 `RouterTier` → `vir_sim` → 打印；`dvd_throughput(300, 8, 128)` → 打印；`posthoc_vs_native_table()`。四部分彼此独立。

---

## 3. 逐段精讲

### 3.1 `CorpusMix`：配比与步数

```python
@dataclass
class CorpusMix:
    text_pct: float
    interleaved_pct: float
    caption_pct: float
    video_pct: float

    def normalize(self) -> None:
        total = self.text_pct + self.interleaved_pct + self.caption_pct + self.video_pct
        self.text_pct /= total
        ...

    def steps(self, total: int) -> dict:
        return {
            "text":       int(total * self.text_pct),
            "interleaved": int(total * self.interleaved_pct),
            "caption":    int(total * self.caption_pct),
            "video":      int(total * self.video_pct),
        }
```

- 传入的是百分数（40、35、20、5），`normalize()` 把它们除以总和变成比例（0.40、0.35、0.20、0.05）。这样无论传入百分数还是任意权重（如 4:3.5:2:0.5）都能得到同样的结果。`normalize()` 是**原地修改**（返回 `None`），重复调用结果不变。
- `steps(500_000)` 恰好得到 200,000 / 175,000 / 100,000 / 25,000。
- ⚠️ **`int()` 截断**：每项向下取整，余数被丢弃。`steps(999)` 总和 996，`steps(7)` 总和 5 且视频为 0 步；`CorpusMix(29, 36, 30, 5).steps(100)` 中 `100 × 0.29 = 28.999999999999996`，text 变成 28。修复方法是"最大余数法"（测验 Q11）。
- ⚠️ **"按步数分配"的假设**：真实预训练一般在每个 batch 内按比例混合多种数据，配比也更常按 token 计。按步数记账只是演示。
- ⚠️ 四个占比都为 0 时 `normalize()` 会除以零。

### 3.2 `RouterTier` 与 `vir_sim`：ViR 的收益

```python
@dataclass
class RouterTier:
    name: str
    tokens: int
    fraction: float


def vir_sim(tiers: list[RouterTier]) -> dict:
    avg = sum(t.tokens * t.fraction for t in tiers)
    baseline = max(t.tokens for t in tiers)
    return {"avg_tokens": avg, "baseline": baseline, "ratio": baseline / avg}
```

- `avg` 是视觉 token 的**期望值**：`256 × 0.5 + 576 × 0.3 + 2048 × 0.2 = 710.4`。
- `baseline` 取最高档（2048），代表"不路由、全部高分辨率"。
- `ratio = 2048 / 710.4 ≈ 2.88`，被打印成 "speed-up vs baseline"。
- ⚠️ 这个"加速比"假设吞吐与视觉 token 数成正比，忽略了文本 prompt、输出 token（decode 往往才是大头）和路由器本身的开销。加入 200 个 prompt token 和 128 个输出 token 后约为 2.29x（测验 Q10）。
- ⚠️ 没有考虑**误路由**：本该高分辨率的请求被分到低档时，要么答错，要么重编码一次。
- ⚠️ 没有检查 `fraction` 之和是否为 1。
- ⚠️ 数字口径不一致：代码分布是 50/30/20（80% 低或中），讲义"概念"说 60% 低或中即可，练习 4 说 60% 走低档，代码 note 又说 50%。

### 3.3 `dvd_throughput`：拆分部署的"加速比"

```python
def dvd_throughput(encoder_flops: int, llm_flops: int,
                   llm_tokens: int = 128) -> dict:
    colocated = encoder_flops + llm_flops * llm_tokens
    decoupled = max(encoder_flops, llm_flops * llm_tokens)
    return {"colocated": colocated, "decoupled": decoupled,
            "speedup": colocated / decoupled}
```

- **同卡（colocated）**：一个请求先跑 encoder、再跑 128 步 LLM，耗时相加：`300 + 8 × 128 = 1324`。
- **分卡（decoupled）**：encoder 和 LLM 在两块 GPU 上流水并行，稳态吞吐由较慢的一段决定：`max(300, 1024) = 1024`。
- `speedup = 1324 / 1024 ≈ 1.29`。
- ⚠️ **硬件不对等**：分卡方案用了两块 GPU。按每块 GPU 的吞吐比较，默认参数下分卡只有同卡的约 0.65 倍。讲义说 "doubles per-node throughput"，节点内 GPU 总数不变时，必须按每 GPU 吞吐比较才公平。
- ⚠️ **上限是 2**：`(a + b) / max(a, b) = 1 + min/max ≤ 2`，只有两段耗时完全相等时才翻倍（例如 encoder 改为 1024 GFLOPs）。
- ⚠️ **FLOPs 口径**：8B LLM 前向约 16 GFLOPs/token（2 × 参数量），代码的 8 相当于 4B 模型；代入 16 后 speedup 仅 1.15。更根本的是 decode 是显存带宽瓶颈，用 FLOPs 线性相加并不能反映真实耗时。
- 参数名叫 `encoder_flops: int`，实际传入的是 GFLOPs，单位容易混淆。

### 3.4 `posthoc_vs_native_table`：对比表

```python
    rows = [
        ("metric",                 "post-hoc",   "native"),
        ("-" * 22,                 "-" * 12,     "-" * 12),
        ("total GPU-hours",        "~30k",       "~300k"),
        ...
        ("examples",               "LLaVA, Qwen-VL v1", "InternVL3, GPT-4o, Chameleon"),
    ]
    for r in rows:
        print(f"  {r[0]:<22}{r[1]:<14}{r[2]}")
```

- 每行是一个三元组，用 `r[0]`、`r[1]`、`r[2]` 下标访问，分别左对齐到 22、14 列。
- ⚠️ **排版问题**：第一列分隔线正好 22 个 `-`，与第二列的 `-` 连成一条；`"LLaVA, Qwen-VL v1"` 17 个字符超过第二列宽度 14，与第三列直接粘连，输出成 `LLaVA, Qwen-VL v1InternVL3, ...`。
- ⚠️ **内容需要限定**：
  - "corpus flexibility: post-hoc = instr only"：后接式也能用交错数据，第 07 节 `RECIPES` 里 Idefics2-8B 的数据就是 "OBELICS + Cauldron"；
  - native "~300k" GPU-hours 与讲义 "millions of GPU-hours" 相差一个数量级；
  - native 的 MMLU / GSM8K 回退写成 "0"，过于绝对；
  - GPT-4o 的训练方式没有公开，列为原生示例属于推测。

### 3.5 `main()`：把三部分串起来

```python
    mix = CorpusMix(text_pct=40, interleaved_pct=35, caption_pct=20, video_pct=5)
    mix.normalize()
    total_steps = 500_000
    steps = mix.steps(total_steps)
    for k, v in steps.items():
        print(f"  {k:<14}: {v:>8,}  ({v * 100 / total_steps:.1f}%)")
```

- `500_000` 中的下划线只是数字分隔符，提高可读性，等价于 `500000`。
- `{v:>8,}`：右对齐 8 列并加千分位逗号；`{... :.1f}` 保留 1 位小数。
- 用关键字参数构造 dataclass（`text_pct=40`），比位置参数更不容易填错顺序。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 dataclass 表示配比与路由档位 | 字段清晰，可直接修改实验 | 缺少校验（占比之和、非负、非零） |
| 配比换算成"步数" | 直观 | 真实训练按 batch 内混合与 token 计量；整数分配应使用最大余数法 |
| ViR 收益 = 视觉 token 比值 | 一行公式说明路由的价值 | 忽略文本、decode、误路由与路由器开销；生产中用端到端吞吐和分档准确率评估 |
| DvD 用 `sum` vs `max` 建模 | 清楚体现"串行 vs 流水并行" | 硬件数量不对等；上限 2x；decode 应按显存带宽估算；还要计入跨 GPU 传输 |
| 对比表硬编码 | 快速建立印象 | 数字只是量级示意，部分说法过于绝对；排版有粘连 |
| 不训练任何模型 | 讲义类型是 "Learn"，重点是概念 | 无法验证对齐债本身；可参考 MM1.5 等论文的实测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class CorpusMix:`、`class RouterTier:` | 自动生成 `__init__`，可用位置参数或关键字参数构造 |
| 关键字参数构造 | `CorpusMix(text_pct=40, interleaved_pct=35, ...)` | 按名字传参，顺序无关，更易读 |
| 原地复合赋值 | `self.text_pct /= total` | 等价于 `self.text_pct = self.text_pct / total`，修改对象自身 |
| 返回 `None` 的方法 | `def normalize(self) -> None:` | 原地修改对象的方法通常不返回值（类似 `list.sort()`） |
| 类型注解 `list[RouterTier]` | `def vir_sim(tiers: list[RouterTier]) -> dict:` | 说明参数是 `RouterTier` 的列表 |
| 生成器表达式 + `sum` / `max` | `sum(t.tokens * t.fraction for t in tiers)`、`max(t.tokens for t in tiers)` | 不建中间列表直接聚合 |
| 默认参数 | `llm_tokens: int = 128` | 调用时可省略 |
| 函数参数跨行 | `def dvd_throughput(encoder_flops: int, llm_flops: int,\n llm_tokens: int = 128)` | 括号内可以换行 |
| 数字下划线分隔 | `500_000` | Python 3.6+ 支持，等于 500000 |
| f-string 千分位 | `{total_steps:,}`、`{v:>8,}` | 逗号表示千分位分隔 |
| f-string 百分比显示 | `{t.fraction * 100:>4.0f}%` | 花括号里先做乘法，再按 4 列、0 位小数输出 |
| 字典取值 | `r['avg_tokens']`、`d['speedup']` | f-string 中用单引号访问键，避免与外层双引号冲突 |
| 元组下标 | `r[0]`、`r[1]`、`r[2]` | 按位置访问元组元素 |
| `int()` 截断 | `int(total * self.text_pct)` | 向零取整，浮点误差可能导致少 1（如 28.999… → 28） |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（输出确定）：

```text
CORPUS MIX (target 500,000 training steps)
  text          :  200,000  (40.0%)
  interleaved   :  175,000  (35.0%)
  caption       :  100,000  (20.0%)
  video         :   25,000  (5.0%)

VIR ROUTING SIMULATION (production query mix)
  low-res photo QA              256 tok x   50%
  medium product shot           576 tok x   30%
  high-res doc + OCR           2048 tok x   20%

  avg tokens/req  : 710                    ← 128 + 172.8 + 409.6 = 710.4
  baseline (all high-res): 2048
  speed-up vs baseline  : 2.88x            ← 只比较视觉 token
  note: 50% of real-world queries need only low-res encoding

DVD DEPLOYMENT — encoder vs LLM parallelism
  encoder: 300 GFLOPs per image
  LLM    : 8 GFLOPs per output token, 128 tokens
  colocated total: 1324 GFLOPs             ← 300 + 8×128
  decoupled bottleneck: 1024 GFLOPs        ← max(300, 1024)
  speedup: 1.29x with DvD                  ← 用了 2 块 GPU；每 GPU 吞吐约 0.65x

POST-HOC vs NATIVE PRETRAINING
  metric                post-hoc      native
  ----------------------------------  ------------          ← 分隔线粘连
  total GPU-hours       ~30k          ~300k
  ...
  examples              LLaVA, Qwen-VL v1InternVL3, GPT-4o, Chameleon   ← 列宽不足粘连
```

逐项解读：

- **语料配比**：50 万恰好整除，看不出截断问题；换成 999 或 7 步就能看到总和不等于目标值。
- **ViR**：2.88x 落在讲义"2–3x throughput"区间内，但这是"视觉 token 数之比"。额外计算：按讲义"60% 低或中"假设 40/20/40 分布，降到 1.98x；加入文本 prompt 与输出后为 2.29x；全部高分辨率时为 1.00x（ViR 无用武之地）。
- **DvD**：1.29x 与讲义"roughly doubles"有明显差距。只有两段耗时相等（例如 encoder 1024 GFLOPs）时才是 2.00x；输出变长（512 token）时降到 1.07x。
- **对比表**：除排版问题外，几处绝对化的说法需要加限定（见 3.4）。

---

## 7. 动手改一改

1. **修复 `steps`**：用最大余数法保证总和等于 `total`，并为占比为 0 或总和为 0 的情况加校验（参考测验 Q11）。
2. **讲义练习 2**：把配比改为视频为主（例如 30 / 25 / 15 / 30），打印步数，并写一段注释说明为何不能把文本降到 10% 以下。
3. **更真实的 ViR**：给 `vir_sim` 增加 `text_tokens`、`output_tokens` 和 `misroute` 参数（参考测验 Q10），对比 50/30/20 与 40/20/40 两种分布。
4. **公平的 DvD**：增加 `gpus_colocated=1`、`gpus_decoupled=2` 参数，输出"每 GPU 吞吐比"；再把 LLM 的每 token 耗时改为"权重字节 / 显存带宽"的估算，观察结论变化（讲义练习 5）。
5. **修复对比表排版**：根据每列最长字符串动态计算列宽，并在列之间加两个空格。
6. **讲义练习 1**：查阅 InternVL3 与 LLaVA-OneVision 论文中的训练配置，在表格中加入两者的数据量与算力估计，计算 GPU-hours 比值。

---

## 8. 常见坑

- **用 `int()` 分配整数配额**：余数丢失、浮点误差导致少 1，小比例项可能变成 0。
- **把"token 数之比"当"吞吐之比"**：忽略文本、decode 与额外开销会高估路由收益。
- **比较不同硬件规模下的吞吐**：两块 GPU 对一块 GPU 的"加速"不能说明方案更好，应按每 GPU 或每节点（固定 GPU 数）比较。
- **以为流水线拆分能无限加速**：两段式流水线的上限就是 2 倍，且只在两段完全平衡时达到。
- **用 FLOPs 估算 decode**：decode 是显存带宽瓶颈，FLOPs 估算会严重偏差。
- **列宽小于内容长度**：f-string 的 `:<14` 不会截断超长字符串，导致列与列粘连。
- **对比表中的绝对化表述**：如"native 回退 0""post-hoc 只能用指令数据"，与其它小节或讲义正文矛盾。
