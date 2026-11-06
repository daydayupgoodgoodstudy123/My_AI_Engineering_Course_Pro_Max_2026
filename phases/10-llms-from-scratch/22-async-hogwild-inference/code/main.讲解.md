# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 22 节 异步与 Hogwild! Inference ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

这份代码分两部分：

1. **一个玩具 Hogwild! 模拟器**：若干个 worker 每步各写一个"token"到共享 cache（一个列表），token 只有 4 种类别：工作类 A、B，以及 noise、coord。worker 读 cache 后按一定概率"协调"——改写当前计数最少的工作类别。程序统计固定步数内的"unique progress"（每步不重复的工作类别数），并与单 worker 基线比较。
2. **一个 Amdahl 形式的理论加速比计算**：`T_serial / (T_serial · ((1 − p) + p/N) + c · N)`，在长推理任务与短对话任务两组参数下打表。

它对应讲义 "Build It" 的五个步骤、"Wall-time math" 与 "Concrete example"，以及练习 1–3。

需要提前说明：模拟器里没有任何语言模型，"协调"是一个概率开关，"冗余"只在同一步内判断——它演示的是"共享状态 → 分工"的**形状**，而不是真实的 Hogwild! 行为；第二部分的公式比模拟器更能说明问题。

> 一句话：**用一个共享列表演示"读别人写了什么、再决定自己写什么"，并用 Amdahl 公式说清 Hogwild! 什么时候值得**；同时学会识别模拟器里不公平的基线与没有用上的参数。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Category` | 类型别名（`Literal`） | token 类别只能是 `"A"`、`"B"`、`"noise"`、`"coord"` | token 种类 |
| `SharedCache` | dataclass | `tokens` 列表 + `counts()` 统计各类别数量 | 共享 KV cache |
| `Worker` | dataclass | id、默认意图类别、协调权重、独立随机数生成器 | 一个模型实例 |
| `decide_next_category` | 函数 | 5% noise；按协调权重改选最少的类别；否则 10% coord；否则写默认类别 | 协调启发式 |
| `run_hogwild` | 函数 | 按步循环：每个 worker 决策并写入；统计本步不重复的工作类别 | 模拟主循环 |
| `expected_speedup` | 函数 | Amdahl + 协调开销 | 理论加速比 |
| `main` | 函数 | Step 1–5：基线、2 worker、协调权重扫描、两张理论表 | 演示入口 |

数据流：`main` → `run_hogwild(n_workers, step_budget, ..., coordination_weight)` → 每步对每个 worker 调 `decide_next_category`（读 `cache.counts()`）→ 追加到 `cache.tokens` → 统计 `progress` → 返回结果字典 → 打印；Step 4、5 直接调 `expected_speedup`。

---

## 3. 逐段精讲

### 3.1 类型与共享 cache

```python
Category = Literal["A", "B", "noise", "coord"]


@dataclass
class SharedCache:
    tokens: List[tuple[int, Category]] = field(default_factory=list)

    def counts(self) -> dict:
        c = {"A": 0, "B": 0, "noise": 0, "coord": 0}
        for _, cat in self.tokens:
            c[cat] += 1
        return c
```

- `Literal[...]` 告诉读者（和类型检查器）类别只能取这四个字符串之一；运行时并不强制。
- 共享 cache 是 `(worker_id, category)` 元组的列表，对应讲义 "Step 1: the shared cache"——真实系统里是共享的 KV 张量，需要锁或更精细的并发控制；讲义说"Simple locking (`threading.Lock`) in a real implementation; we simulate with a counter"，代码里其实连计数器都没有，worker 是串行执行的。
- `field(default_factory=list)`：dataclass 的可变默认值必须这样写，否则所有实例会共享同一个列表。
- `counts()` 每次从头遍历，整个模拟是 O(步数²)；这里步数只有几百，无所谓。

### 3.2 `Worker`：一个"模型实例"

```python
@dataclass
class Worker:
    id: int
    intended: Category
    coordination_weight: float
    rng: random.Random
```

- 每个 worker 有自己的 `random.Random(seed + i)`，保证可复现且彼此独立。
- `coordination_weight` 是"推理模型读懂共享 cache 并分工"的能力的替身：0 表示完全不会协调，1 表示理想协调（docstring 原话）。

### 3.3 协调启发式 `decide_next_category`

```python
    if worker.rng.random() < 0.05:
        return "noise"

    counts = cache.counts()
    base = worker.intended

    if worker.rng.random() < worker.coordination_weight:
        candidates = sorted(("A", "B"), key=lambda c: counts[c])
        return candidates[0]

    if worker.rng.random() < 0.1:
        return "coord"

    return base
```

决策顺序与各分支概率：

| 分支 | 条件 | 概率（cw = 0.8） |
|------|------|-----------------|
| noise | 5% | 0.05 |
| 协调：写当前最少的类别 | `0.95 × cw` | 0.76 |
| coord | 不协调时 10% | `0.95 × 0.2 × 0.1 = 0.019` |
| 默认类别（A） | 其余 | 0.171 |

- `sorted(("A", "B"), key=lambda c: counts[c])[0]`：按计数排序取最小者；计数相同时 `sorted` 是稳定排序，保留原顺序，返回 "A"。
- ⚠️ 参数 `target_per_category` **从未使用**。docstring 说"if the other worker already produced enough tokens in a category, switch"，但代码里没有"够了"的阈值；协调只是"永远去最少的类别"。
- ⚠️ `coord` token 只在**不协调**的分支出现：协调权重越高，coord token 越少（cw = 1 时为 0）。这与讲义"协调要花 c 个 token"的设定相反——在模拟器里协调是免费的。
- ⚠️ "协调"不区分是在和别人协调还是和自己协调：单 worker（N = 1）在 cw = 0.8 时也会在 A、B 之间来回切换（基线计数 A 95、B 94）。

### 3.4 主循环 `run_hogwild`

```python
    while step < step_budget:
        this_step_categories = []
        for w in workers:
            cat = decide_next_category(w, cache, target_per_category)
            cache.tokens.append((w.id, cat))
            this_step_categories.append((w.id, cat))

        seen_work_categories = set()
        for w_id, cat in this_step_categories:
            tag = "redundant"
            if cat in ("A", "B") and cat not in seen_work_categories:
                seen_work_categories.add(cat)
                progress += 1
                tag = "unique"
            trace.append((w_id, cat, tag))
        step += 1
```

- **一步 = 一个墙钟时间单位**：所有 worker 在同一步里各写一个 token，模拟"并行"；因此 N 个 worker 每步共写 N 个 token（`tokens_per_step` = 2.00）。
- **即时可见**：worker 按顺序决策并立即 `append`，第二个 worker 在同一步内就能看到第一个 worker 刚写的 token——对应讲义"Each worker sees every other worker's generated tokens immediately"。真实并发中两者更可能读到同一个旧快照。
- **unique progress**：每步用一个集合记录已出现的工作类别，同一步内重复的类别记为 "redundant"、不计分。于是：
  - 每步最多得 2 分（只有 A、B 两类），worker 再多也没用——N = 4、cw = 0.8 实测 progress 397，相对基线仅 2.10×；
  - 冗余只是不计分，不会拖慢进度，所以 N = 2 永远不会比 N = 1 慢（与讲义"Step 5"中"speedup drops below 1"不符）；
  - 不同步写同一类别都算 unique，类别没有"做完"的概念。
- ⚠️ `noise` token 也被标为 `"redundant"`（trace 中 `(1, 'noise', 'redundant')`），标签有误导性。
- 返回的字典中 `sample_trace` 取前 12 条，但 `main` 并没有打印它（讲义说会报告"A trace of which worker wrote which token"）。

### 3.5 理论加速比 `expected_speedup`

```python
def expected_speedup(T_serial: int, p: float, c: int, N: int,
                     steps_per_worker: int) -> float:
    parallel = T_serial * ((1 - p) + p / N) + c * N
    return T_serial / parallel
```

- 前半部分是 Amdahl 定律：串行部分 `(1 − p)` 无法加速，可并行部分 `p` 被 N 等分。
- 后半部分 `+ c · N` 是协调开销。讲义正文写的是 `+ c · steps_per_worker`，例子却用 `200 × 4`（即 `c · N`）；代码采用后者，`steps_per_worker` 参数被传入但没有使用。若按讲义正文公式计算，例子会变成 504,750 步，显然不对。
- `c · N` 隐含"所有 worker 的协调串行发生"，偏保守；若协调并行发生，墙钟上更接近只加一次 c（讲义例子会从 1.80× 变为约 2.02×）。
- 上限：N → ∞ 且 c = 0 时为 `1 / (1 − p)`。p = 0.7、N = 4 时不计开销的上限是 2.105×，所以讲义"5 万 token 时可达 2.5–3×"在这组参数下不可能。

### 3.6 `main` 的五个步骤

```python
    for cw in (0.0, 0.2, 0.5, 0.8, 1.0):
        r = run_hogwild(n_workers=2, step_budget=200, target_per_category=100,
                        coordination_weight=cw)
        speedup = r["unique_progress"] / r_1["unique_progress"]
```

- Step 3 的所有行都除以**同一个基线** `r_1`（N = 1、cw = 0.8）。基线与实验组的协调权重不同，于是 cw = 1.0 的一行出现了 2.04× 的"超线性"加速（详见第 6 节与测验 Q9）。
- Step 4、5 的表头用嵌套 f-string 生成：`f"{f'N={N}':>10}"`——内层先拼出 `"N=2"`，外层再右对齐到宽 10。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 4 种类别代替真实 token | 无需模型就能演示"读共享状态后分工" | 没有"子任务完成"的概念，冗余与进度都很粗糙 |
| 协调 = 概率开关、免费 | 代码简短 | 与讲义"协调开销 c"相反；真实中协调要花 token 读写计划 |
| 同一步内顺序执行、立即可见 | 模拟"即时可见" | 不是真并发；真实系统需要处理同时读到旧状态、写冲突 |
| unique progress 只按同一步判重 | 一行集合即可 | 冗余不受罚、进度上限为类别数，加速比恒 ≥ 1 且最多约 2 |
| 所有扫描共用一个 cw = 0.8 的基线 | 方便对比 | 基线与实验组不同条件，出现 2.04× 超线性 |
| Amdahl + `c · N` | 与讲义例子一致、易算 | 公式与讲义正文不一致；并行协调应只加一次 c |
| 未使用的参数（`target_per_category`、`steps_per_worker`） | 预留接口 | 让读者误以为实现了阈值切换和按步开销 |
| 真实系统 | — | 参考实现基于 PyTorch、单节点多进程；需要共享 KV 管理、RoPE 位置处理与协作提示词 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `Literal` 类型 | `Category = Literal["A", "B", "noise", "coord"]` | 限定取值范围的类型注解；同时这是一个类型别名 |
| `@dataclass` + `field(default_factory=...)` | `tokens: List[...] = field(default_factory=list)` | 可变默认值必须用工厂函数，避免实例间共享同一个列表 |
| dataclass 中的方法 | `def counts(self) -> dict` | dataclass 也可以定义普通方法 |
| 元组解包 + `_` | `for _, cat in self.tokens` | 忽略不需要的元素 |
| 独立随机数生成器 | `random.Random(seed + i)`、`worker.rng.random()` | 每个 worker 一条随机流，结果可复现 |
| `lambda` 作为排序键 | `sorted(("A", "B"), key=lambda c: counts[c])` | 按计数排序；`sorted` 是稳定排序 |
| `set` 去重 | `seen_work_categories = set()`、`cat not in seen` | 判断本步是否已出现该类别 |
| 成员判断 | `cat in ("A", "B")` | 对元组做 `in` 判断 |
| `while` 循环与计数器 | `while step < step_budget: ... step += 1` | 也可写成 `for step in range(step_budget)` |
| 返回字典 | `return {"workers": n_workers, ...}` | 用字符串键访问：`r_2['unique_progress']` |
| 列表切片 | `trace[:12]` | 取前 12 个元素 |
| 关键字实参 | `run_hogwild(n_workers=2, step_budget=200, ...)` | 参数多时清晰 |
| 整除 | `T_serial // N` | 结果为 int |
| f-string 格式符 | `{r_1['work_per_step']:.2f}`、`{cw:>14.2f}`、`{s:>9.2f}x` | 小数位、对齐与宽度 |
| 嵌套 f-string | `f"{f'N={N}':>10}"` | 内层生成字符串，外层再格式化 |
| 生成器表达式 + `join` | `"".join(f"..." for N in (2, 4, 8))` | 拼接一行表头 |
| 打印字典 | `print(f"... {r_1['category_counts']}")` | 字典的 `repr` 直接显示为 `{'A': 95, ...}` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.09 秒）：

```text
Step 1: baseline — single worker, 200 steps
  tokens emitted    : 200
  work-tokens       : 189  (0.94 / step)
  unique progress   : 189  (0.94 / step)
  category counts   : {'A': 95, 'B': 94, 'noise': 6, 'coord': 5}

Step 2: Hogwild — 2 workers, shared cache, strong coordination
  tokens emitted    : 400  (2.00 / step)
  work-tokens       : 376  (1.88 / step)
  unique progress   : 341  (1.71 / step)
  category counts   : {'A': 189, 'B': 187, 'noise': 18, 'coord': 6}
  speedup vs N=1    : 1.80x

Step 3: coordination-weight sweep (N=2, same step budget)
    coord weight    progress   speedup vs N=1
            0.00         197             1.04x
            0.20         238             1.26x
            0.50         292             1.54x
            0.80         341             1.80x
            1.00         385             2.04x

Step 4: Amdahl-style theoretical speedup     (T_serial = 10000, c = 200)
      p         N=2       N=4       N=8
   0.30       1.12x     1.17x     1.11x
   0.50       1.27x     1.42x     1.38x
   0.70       1.45x     1.80x     1.83x
   0.90       1.69x     2.47x     2.68x

Step 5: worst case (short task, weak coordination)   (T_serial = 1000, c = 150)
      p         N=2       N=4       N=8
   0.10       0.80x     0.66x     0.47x
   0.30       0.87x     0.73x     0.52x
   0.50       0.95x     0.82x     0.57x
```

逐项解读：

- **Step 1**：单 worker 在 cw = 0.8 下也在 A、B 间交替（95 / 94），189 个工作 token 全算 unique。
- **Step 2**：376 个工作 token 中 341 个 unique，35 个在同一步内重复（两个 worker 恰好写了同一类别）。1.80× 与讲义例子里的理论值 1.80× 恰好相同，但两者毫无关系——一个是模拟器计数，一个是 Amdahl 公式。讲义练习 1 要确认的"N = 2 多于 N = 1"成立。
- **Step 3**：
  - cw = 0 时仍有 1.04×：冗余不受罚，两个 worker 都写 A 时"至少一个写出 A"的概率（约 0.979）高于单 worker（约 0.945）。50 个随机种子下 cw = 0 的加速比在 1.005–1.124 之间，从未低于 1，讲义"降到 1 以下"无法复现。讲义练习 2 的 cw = 0.1 实测为 1.16×，也谈不上"崩溃"。
  - cw = 1.0 的 2.04× 超过 worker 数：因为 cw = 1 时从不写 coord token，而基线（cw = 0.8）要浪费约 1.9% 的步数在 coord 上。用相同 cw 的单 worker 作基线，cw = 1.0 时为 1.99×，cw = 0 时为 1.15×。
- **Step 4**：
  - p = 0.7、N = 4 → 1.80×，就是讲义的 "Concrete example"（5550 步）。
  - N 从 4 增到 8 时，p = 0.3、0.5 的加速比反而下降：`c · N` 随 N 线性增长，超过了并行收益——体现了讲义"收益递减通常出现在 N = 4–8"。
- **Step 5**：短任务里 `c · N` 与 `T_serial` 同量级，所有组合都低于 1×，即并行反而更慢；对应讲义"Short interactive chat. Coordination overhead dominates."
- **讲义练习 3**（用同一公式计算）：50k token、p = 0.8、c = 500、N = 4 → 2.27×；1k token、p = 0.3、c = 200、N = 4 → 0.63×。

---

## 7. 动手改一改

1. **公平基线**：让 Step 3 每一行都与"相同 cw 的单 worker"比较，确认加速比不再超过 2。
2. **让协调付费**：在 `decide_next_category` 中，当 worker 决定改变意图类别时返回 `"coord"`（花掉这一步）并更新 `worker.intended`；再让同一步内所有 worker 读取同一个快照（在循环前 `snapshot = cache.counts()`）。观察 N = 1 基线与各 cw 下的结果如何变化——我们实测这样改后 N = 1 基线的 progress 从 189 降到 115，结论对建模假设非常敏感。
3. **用上 `target_per_category`**：给每个类别设定所需工作量，类别达到目标后视为"完成"、之后再写该类别算冗余；度量改为"完成所有类别所需的步数"（真正的墙钟时间）。
4. **更多子任务**：把类别扩展为 `["A", "B", "C", "D", ...]`，观察 N = 4、8 时加速比是否不再被 2 封顶，并与 Amdahl 公式中的 p 建立联系。
5. **讲义练习 3 与公式对比**：实现 `expected_speedup_v2`（协调开销只加一次 `c`，或按 `c × 协调轮数` 计），在 Step 4、5 的参数下与原公式对比。
6. **讲义练习 5**：给每个 worker 加一个"2-token 草稿 + 验证"的过程（草稿以一定概率被拒），草稿先写进私有暂存区、验证通过后才提交到共享 cache；统计被拒草稿的回滚次数与最终加速比。

---

## 8. 常见坑

- **基线条件不一致**：比较并行方案时，基线必须与实验组只差"并行度"一个变量；否则会出现 2.04× 这样的超线性假象。
- **把"不计分"当成"惩罚"**：模拟器里冗余 token 只是不计分，不会拖慢进度，因此永远看不到"并行比串行慢"。
- **以为协调免费**：真实 Hogwild! 中读他人输出、写计划都要消耗 token（讲义中的 c），这才是短任务上得不偿失的原因。
- **忽略 Amdahl 上限**：可并行比例 p 决定了天花板 `1 / (1 − p)`，任务再长也突破不了。
- **公式口径混乱**：讲义正文 `c · steps_per_worker`、讲义例子 `c · N`、代码 `c · N`，务必先弄清 c 的单位。
- **把 RoPE 的作用理解为"完全不用动缓存"**：缓存的 K 已按其位置旋转，换位置仍需旋转（可以转移到 query 上做），只是不必重算前向。
- **直接相乘多种加速**：spec decode 与 Hogwild! 争用同一份算力与带宽，"3 × 1.8 = 5.4×"只是理想上限。
- **把实验性方法当成生产方案**：讲义明确"Worth experimenting with. Not yet worth betting a product on."
