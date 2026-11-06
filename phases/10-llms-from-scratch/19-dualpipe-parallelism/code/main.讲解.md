# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 19 节 DualPipe 并行 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数；讲义说它接受 `(P, n_micro_batches, schedule)`，实际没有命令行参数，要改配置需直接改 `main()` 或在交互环境中调用函数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

这份代码是一个"pipeline bubble 估算器"：对 1F1B、Zero Bubble、DualPipe、DualPipeV 四种流水线调度，用**闭式公式**算出 bubble 占比，并打印四张表：

1. P = 8、M = 16 时四种调度的 bubble、参数份数、通信重叠程度；
2. 固定 P = 8，M 从 4 到 128 时 bubble 占比的变化；
3. 固定 M = 64，P 从 4 到 64 时 bubble 占比的变化；
4. 按 DeepSeek-V3 的总算力（约 2.8M GPU 小时）估算 DualPipe 相对 1F1B "回收"的 GPU 小时。

它对应讲义的 "Bubble accounting"、"DualPipeV — the refinement"、"What it means for a 14.8T-token run" 三节。讲义自己也说明它是"teaching tool"，数字只代表定性趋势。

需要特别注意：文件开头的 docstring 自称 "simulator"，但代码里**没有时间轴、没有 rank、没有依赖关系**，只有四个手写公式；DualPipeV 更是直接取 DualPipe 的 1.2 倍。

> 一句话：**用几行公式建立"bubble 占比 ≈ 固定空泡 / 总工作量"的直觉，看清 P 和 M 如何影响它**；同时学会质疑这些公式的口径。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ScheduleStats` | dataclass | 描述一种调度的统计信息 | （定义了但**从未使用**） |
| `bubble_1f1b` | 函数 | `2(P−1) / (2M + 2(P−1))` | 1F1B 的 warmup/cooldown 空泡 |
| `bubble_zero_bubble` | 函数 | `(P−1) / (3M + 2(P−1))` | 拆分 B/W 后的残余空泡 |
| `bubble_dualpipe` | 函数 | `((P−1)//2) / (3M + (P−1))` | 双向调度的固定空泡 |
| `bubble_dualpipev` | 函数 | `1.2 × bubble_dualpipe` | V 形单参数副本调度（经验系数） |
| `summarize` | 函数 | 返回四元组列表：名称、bubble、参数份数、通信重叠 | 讲义中的对比表 |
| `gpu_hours_recovered` | 函数 | `(b_1F1B − b_DualPipe) × 总 GPU 小时` | 把 bubble 换算成算力 |
| `main` | 函数 | 打印 Step 1–4 | 演示入口 |

数据流：`main` → `summarize(P, M)` 依次调用四个 `bubble_*` → 格式化成表格；Step 4 调 `gpu_hours_recovered(P=16, M=128, 2.8M)`。

---

## 3. 逐段精讲

### 3.1 1F1B：经典公式的"chunk 计数"写法

```python
def bubble_1f1b(P: int, M: int) -> float:
    total = 2 * M + 2 * (P - 1)
    bubble = 2 * (P - 1)
    return bubble / total
```

- 把一个 micro-batch 在一个 stage 上的前向记 1 个单位、反向记 1 个单位（即假设 F = B）。每个 rank 有 `2M` 个有效单位，外加 warmup 的 `P−1` 个前向空位和 cooldown 的 `P−1` 个反向空位。
- 化简后是经典结论 `(P−1)/(M+P−1)`。P = 8、M = 16 时 `7/23 = 30.4%`。
- 注意：分子 `2(P−1)` **与 M 无关**。1F1B 的绝对 bubble 本来就不随 micro-batch 数增长，增大 M 只是把它摊薄。讲义表格说 1F1B "grows" 并不准确（见测验 Q9）。
- 讲义正文的公式写成 `bubble_1F1B = (P − 1) × forward_chunk_time`，漏了反向那一半；DeepSeek-V3 报告中的写法是 `(PP−1)(F+B)`，与代码的 `2(P−1)` 一致。

### 3.2 Zero Bubble：换了单位的近似

```python
def bubble_zero_bubble(P: int, M: int) -> float:
    total = 3 * M + 2 * (P - 1)
    bubble = (P - 1)
    return bubble / total
```

- Zero Bubble 把反向拆为 B（对输入的梯度）和 W（对权重的梯度），所以每个 micro-batch 变成 F、B、W 三个 sub-chunk，分母用 `3M`。
- 分子取 1F1B 的一半（`P−1`），表示 W 填掉了一部分空泡。这是作者的近似，没有严格推导；DeepSeek-V3 报告给出的 ZB1P 为 `(PP−1)(F+B−2W)`。
- 分母里 warmup 项仍写 `2(P−1)`，与 DualPipe 的 `P−1` 并不统一。

### 3.3 DualPipe：整除与固定空泡

```python
def bubble_dualpipe(P: int, M: int) -> float:
    total = 3 * M + (P - 1)
    bubble = (P - 1) // 2
    return bubble / total
```

- `//` 是**整除**。P 为偶数时 `(P−1)//2 = P/2 − 1`（P = 8 → 3，P = 16 → 7），这与 DeepSeek-V3 报告中 DualPipe bubble 的系数 `(PP/2 − 1)` 恰好一致；但报告中这个系数乘的是 `(F&B + B − 3W)`，代码把它当作 1 个 sub-chunk。
- 这里同样分子与 M 无关——讲义"bubble 不随 micro-batch 增长"的性质在代码中对**所有**调度都成立，DualPipe 的优势体现在系数约减半。
- ⚠️ DualPipe 要求 P 为偶数（两端对称），代码对 P = 7 也照算不误（`6//2 = 3`），没有任何校验；M 也没有"能被 2 整除"的检查。

### 3.4 DualPipeV：经验系数

```python
def bubble_dualpipev(P: int, M: int) -> float:
    return bubble_dualpipe(P, M) * 1.2
```

- 讲义表格说 DualPipeV 的 bubble 随 M "small growth"，但代码里它只是 DualPipe 的固定 1.2 倍，同样随 M 增大而占比下降——两者并不一致。1.2 这个系数没有出处，只用来表达"略大一点"。

### 3.5 `summarize` 与 `ScheduleStats`

```python
def summarize(P: int, M: int) -> List[tuple[str, float, int, str]]:
    return [
        ("1F1B",       bubble_1f1b(P, M),        1, "minimal"),
        ("Zero Bubble", bubble_zero_bubble(P, M), 1, "partial"),
        ("DualPipe",   bubble_dualpipe(P, M),    2, "full"),
        ("DualPipeV",  bubble_dualpipev(P, M),   1, "partial"),
    ]
```

- 返回元组列表，第三、四列"参数份数"和"通信重叠"是写死的常量，直接对应讲义的对比表（DualPipe 2 份、其余 1 份）。
- 文件开头定义了 `ScheduleStats` dataclass（含 `scales_with_micro_batches` 字段），本来适合承载这些信息，却**没有被使用**——是一段"死代码"，也说明作者原本想表达"是否随 M 增长"这一维度，最终没有实现。
- Step 2、3 的表头写的是 `"ZeroBubble"`，而 `summarize` 中名字是 `"Zero Bubble"`；表格靠位置对齐，不读名字，所以不影响结果。

### 3.6 `gpu_hours_recovered`：把占比换成算力

```python
def gpu_hours_recovered(P: int, M: int, total_gpu_hours: float) -> dict:
    b1 = bubble_1f1b(P, M)
    bd = bubble_dualpipe(P, M)
    recovered = (b1 - bd) * total_gpu_hours
```

- P = 16、M = 128：`b1 = 30/286 = 10.49%`，`bd = 7/399 = 1.75%`，差 8.74%，乘 2.8M 得 **244,583** GPU 小时。
- 隐含假设：总 GPU 小时全部花在 PP 训练上、且 bubble 是唯一的效率差异。实际上 DeepSeek-V3 的约 2.8M GPU 小时还包含上下文扩展和后训练；DualPipe 的主要收益还来自通信重叠，这个函数并没有建模。
- 打印语"roughly the cost of a full 70B dense pre-training run"明显高估：按 `6ND`、H800 BF16 峰值约 989 TFLOPS、MFU 40% 估算，24.5 万 GPU 小时只够 70B 模型训练约 0.83T token；按 15T token 训练需要约 4.4M GPU 小时（测验 Q11）。

### 3.7 `main` 的四张表

```python
    for M in (4, 8, 16, 32, 64, 128):
        row = f"  {M:>6}"
        for _, b, _, _ in summarize(P=8, M=M):
            row += f"{b:>12.1%}"
        print(row)
```

- 外层改变 M，内层遍历四种调度，用 `_` 丢弃不需要的元组字段，只取 bubble `b`。
- `f"{b:>12.1%}"`：`%` 格式符会把小数乘 100 并加百分号，`.1` 保留一位小数，`>12` 右对齐宽 12。
- Step 3 固定 M = 64、改变 P：所有调度的 bubble 都随 P 近似线性增长（分子 ∝ P），说明"流水线越深越难填满"对任何调度都成立。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 闭式公式而非逐时隙模拟 | 十几行就能出表，易于理解趋势 | 无法验证依赖关系与重叠；真实评估要用调度模拟器或直接 profiling |
| F = B = W = 1 的单位成本 | 简化 | 真实中 B ≈ 2F 左右、W 与 B 相近，比例会影响各调度的相对优劣 |
| 1F1B 与 ZB/DualPipe 用不同单位（2M vs 3M） | 体现 B/W 拆分 | 不同口径直接比较，数字只能看趋势 |
| DualPipeV = 1.2 × DualPipe | 表达"略大一点" | 无依据；DualPipeV 的真实 bubble 需要按其 V 形调度单独计算 |
| 参数份数、通信重叠写死 | 对应讲义表格 | 不随配置变化；没有建模 all-to-all 时间 |
| 不校验 P 为偶数、M 为偶数 | 代码简短 | 会给出物理上不成立的配置结果（如 P = 7 的 DualPipe） |
| 用总 GPU 小时 × bubble 差换算收益 | 直观 | 忽略了通信重叠收益和非 PP 阶段的算力，换算结论需要谨慎 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，旧版本 Python 也能写 `tuple[str, float, int, str]` |
| `@dataclass` | `class ScheduleStats` | 自动生成构造函数；本文件定义了但没用到 |
| 类型注解 | `def bubble_1f1b(P: int, M: int) -> float` | 标注参数与返回值类型 |
| 泛型注解 | `List[tuple[str, float, int, str]]` | "由四元组构成的列表" |
| 整除 `//` | `(P - 1) // 2` | 向下取整的除法，结果是 int |
| 真除 `/` | `bubble / total` | 即使两边是 int，结果也是 float |
| 返回字典 | `return {"1F1B_bubble_frac": b1, ...}` | 用键名访问结果：`r['recovered_gpu_hours']` |
| 元组解包 + `_` | `for name, b, pc, co in summarize(...)`、`for _, b, _, _ in ...` | 一次拆出多个值；`_` 表示不关心的值 |
| 关键字实参 | `summarize(P=8, M=16)` | 调用时写明参数名，可读性好 |
| 数字下划线 | `2_800_000` | 等同 `2800000` |
| f-string 百分号格式 | `{b:>9.1%}`、`{r['1F1B_bubble_frac']:.1%}` | 乘 100 并加 `%`，保留 1 位小数 |
| f-string 千分位 | `{r['recovered_gpu_hours']:,.0f}` | 加千位分隔符、不保留小数 |
| f-string 对齐 | `{name:<14}`、`{pc:>14}` | 左/右对齐与宽度 |
| f-string 中的引号 | `f"{r['1F1B_bubble_frac']:.1%}"` | 外层双引号、内层单引号，避免冲突 |
| 字符串方法 | `"M".rjust(6)`、`name.rjust(12)` | 右对齐填充到指定宽度 |
| 字符串累加 | `header += name.rjust(12)` | 逐列拼出表头 |
| 无占位符的 f-string | `print(f"  (that is roughly ...)")` | 合法但没必要，普通字符串即可 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，耗时约 0.05 秒）：

```text
Step 1: bubble fraction at P=8, micro_batches=16
  schedule           bubble   param copies   comm overlap
  1F1B               30.4%               1         minimal
  Zero Bubble        11.3%               1         partial
  DualPipe            5.5%               2            full
  DualPipeV           6.5%               1         partial

Step 2: bubble fraction scaling vs micro_batches (P=8)
       M        1F1B  ZeroBubble    DualPipe   DualPipeV
       4       63.6%       26.9%       15.8%       18.9%
       8       46.7%       18.4%        9.7%       11.6%
      16       30.4%       11.3%        5.5%        6.5%
      32       17.9%        6.4%        2.9%        3.5%
      64        9.9%        3.4%        1.5%        1.8%
     128        5.2%        1.8%        0.8%        0.9%

Step 3: bubble fraction scaling vs pipeline depth (M=64 fixed)
       P        1F1B  ZeroBubble    DualPipe   DualPipeV
       4        4.5%        1.5%        0.5%        0.6%
       8        9.9%        3.4%        1.5%        1.8%
      16       19.0%        6.8%        3.4%        4.1%
      32       32.6%       12.2%        6.7%        8.1%
      64       49.6%       19.8%       12.2%       14.6%

Step 4: recovered GPU-hours (DeepSeek-V3-shape run)
  1F1B bubble     : 10.5%
  DualPipe bubble : 1.8%
  recovered       : 244,583 GPU-hours
```

逐项解读：

- **Step 1**：`14/46 = 30.4%`、`7/62 = 11.3%`、`3/55 = 5.5%`、`5.5% × 1.2 = 6.5%`。讲义练习 1 要求的"利用率差"约为 `30.4% − 5.5% = 24.9` 个百分点。
- **Step 2**：所有调度的占比都随 M 增大而下降，因为分子（绝对 bubble）都是常数、分母随 M 增长。这与 takeaway 中"bubbles do not grow with M for DualPipe"并不矛盾，但它对 1F1B 同样成立——讲义表格里 1F1B "grows" 的说法在代码里找不到依据。
- **Step 3**：分子 ∝ P，所以所有调度的 bubble 都随 P 增加；P = 64 时即便 DualPipe 也有 12.2%。这呼应附带 skill 文件中的"P > 64 直接拒绝"。
- **Step 4**：8.74% × 2.8M = 244,583。注意讲义正文说"1F1B 会损失 12–15%，即 34–42 万 GPU 小时"，与这里 P = 16、M = 128 得到的 10.5% 不是同一组假设。
- **讲义"8 级流水线约 12% bubble"**：按公式需 M ≈ 51；而 Step 1 用 M = 16 得到 30.4%，说明这个数字强依赖 M。

---

## 7. 动手改一改

1. **加命令行参数**：用 `argparse` 支持 `--P`、`--M`、`--schedule`，让讲义练习 1 的写法 `(P=8, micro_batches=16, schedule=dualpipe)` 真正可用；并对 DualPipe/DualPipeV 校验 P、M 为偶数。
2. **统一口径**：把四个公式都改成以 F、B、W 为参数的版本（如 1F1B `(P−1)(F+B)`、ZB1P `(P−1)(F+B−2W)`、DualPipe `(P/2−1)(F&B+B−3W)`），用 `F=1, B=2, W=1, F&B=2.5` 之类的设定重算 Step 1，比较结论是否改变。
3. **写一个真正的模拟器**：用二维数组表示 `rank × 时隙`，按依赖关系（前向需上游完成、反向需下游完成）为 1F1B 排程，数出空格数，与 `bubble_1f1b` 的公式对照。
4. **讲义练习 2**：在上一题的模拟器里加入"从 rank P−1 注入"的反向流，手动（或贪心）排出 P = 4、M = 8 的 DualPipe 表，找到第一个没有空泡的时隙，并与讲义手画图对比（讲义图中 F5R 同时出现在 4 个 rank 上，是错误的）。
5. **讲义练习 4**：写函数 `param_bytes_per_rank(non_expert, expert, P, EP, copies)`，比较稠密 70B（P = 8）与 MoE 671B（P = 16、EP = 64）下 2 份参数的显存差。
6. **使用 `ScheduleStats`**：让 `summarize` 返回 `ScheduleStats` 对象列表，并把 `scales_with_micro_batches` 字段真正计算出来（比较 M 与 2M 时绝对 bubble 是否变化）。

---

## 8. 常见坑

- **把"占比下降"当成"绝对 bubble 不增长"的证据**：占比随 M 下降对所有调度都成立；要比较的是绝对 bubble 的系数。
- **不同口径直接比较**：1F1B 用 2 个单位/micro-batch，ZB 与 DualPipe 用 3 个；代码给出的倍数关系只能看趋势。
- **忽略 P、M 的整除要求**：DualPipe 需要偶数 P 与偶数 M，代码不检查。
- **只看 bubble 不看通信**：DualPipe 的核心收益是把 all-to-all 与计算重叠，这部分在代码中只是一个字符串 `"full"`。
- **轻信换算比喻**："约等于一次 70B 完整预训练"取决于 token 数和 MFU 假设，按常见配置严重高估。
- **只看聚合利用率**：讲义强调要逐 rank 监控，个别慢 rank 会拖住整条流水线。
- **中文讲义机翻错误**：如 micro-batch 被译成"微型蓄水池"、EP 被译成"欧洲议会"，遇到疑义请对照英文版。
