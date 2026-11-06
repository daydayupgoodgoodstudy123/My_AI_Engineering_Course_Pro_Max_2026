# 代码讲解 · main.py

> **所属小节**：阶段 20 · 递归自我改进 · 第 01 节 "递归"多出了什么：从自我精炼到 RSI ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [--cycles 30] [--returns 1.2] [--noise 0.0] [--trials 200] [--seed 7] [--out FILE]` ｜ **依赖**：仅标准库（`argparse`、`json`、`random`、`statistics`、`dataclasses`、`enum`、`typing`）

---

## 1. 这份代码在考察什么

讲义的核心主张是：**"递归"不是一条曲线的形状，而是一种循环结构——被修改的对象是不是改进器本身**。这份代码把这个主张拆成两部分做数值实验：

1. **A 部分：三种循环形状的递推**。(a) 固定改进器作用于目标（自我精炼，收敛到天花板）；(b) 固定改进器、开放目标、收益递减（自我训练）；(c) 自指循环——改进器本身被修改，所以每轮增益 `g_n` 变成状态变量，`g_{n+1} = r · g_n`。代码并排打印每轮能力，给出每列的天花板与"达到 10× 所需轮数"，再做一个 **identity check**：证明 (a) 取 `k = 1 − r` 时和 (c) 取 `r < 1` 时的序列**逐位相同**。
2. **r 扫描**：对 r ∈ {0.8, 0.9, 1.0, 1.1, 1.2, 1.5} 分别给出天花板、确定性 10× 轮数；`--noise > 0` 时再做 Monte-Carlo，报告达到 10× 的比例、次数和中位轮次。
3. **B 部分：规则分级器**。用五个可观察属性（自主提出/应用/验证、是否修改改进机制、领域范围、是否迁移、验证器类型）把 10 个具名系统放到 Alibaba L1–L5 梯级和 Chen 等人的"改进对象 × 闭环程度"格子里。
4. **HEADLINE**：全部由计算结果用 f-string 拼出，不写死任何结论。

> 一句话：**用三条递推式说明"只有改进器被修改的循环才叫递归，而递归在 r < 1 时照样收敛"；再用一个规则分级器说明"梯级要从修改日志读，不能从曲线读"**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_SEED`、`TARGET_MULTIPLE`、`CONTRAST_RETURNS`、`SWEEP_RETURNS` | 常量 | 种子 7；10× 目标；对照列 r = 0.8；扫描的 r 列表 | 可复现、对照实验 |
| `LoopParams` | frozen dataclass | `c0, k, ceiling, g0, beta, returns, noise` | 三种循环的共享参数 |
| `realised` | 函数 | 给名义增益乘上 `max(0, 1 + ε)` 的噪声 | 机制噪声 |
| `simulate_fixed_improver` | 函数 | 形状 (a)：`C += k (ceiling − C)` | 自我精炼 |
| `simulate_diminishing` | 函数 | 形状 (b)：`C += g0 / (1+n)^β` | 自我训练 |
| `simulate_self_referential` | 函数 | 形状 (c)：`C += g; g = r · g_real` | RSI |
| `gains` / `cycles_to_multiple` | 函数 | 逐轮增益；首次 ≥ 10× 的轮次（没有则 `None`） | 曲线统计 |
| `analytic_ceiling` / `matched_fixed_improver` | 函数 | `c0 + g0/(1−r)`；构造与 (c) 等价的 (a) 参数 | 收敛、identity check |
| `run_part_a` / `run_sweep` | 函数 | 打印并排表、摘要、identity check；r 扫描与 Monte-Carlo | A 部分 |
| `Mechanism / Domain / Verifier / Target / Closure` | Enum | 五种属性的取值 | 梯级判据 |
| `SystemProfile` / `Verdict` | frozen dataclass | 一个系统的属性；分级结果与备注 | 数据即系统 |
| `alibaba_level` / `chen_closure` / `classify` | 函数 | L1–L5 规则；闭环程度；合成 `Verdict` | 两套梯级 |
| `SYSTEMS` | 元组 | 10 个具名系统的属性编码 | 讲义表格 |
| `run_part_b` / `headline` / `main` | 函数 | 打印分级表与备注；拼 HEADLINE；解析参数、可选写 JSON | 入口 |

数据流：命令行 `--cycles/--returns/--noise/--trials/--seed` → `run_part_a`（四条轨迹各用独立 `random.Random(seed + i)`）→ `run_sweep`（每个 r 一条确定性轨迹 + `trials` 条带噪声轨迹）→ `run_part_b`（`SYSTEMS` → `classify`）→ `headline` 从三者的返回值拼句子 → 可选 `--out` 写 JSON。

---

## 3. 逐段精讲

### 3.1 参数与噪声

```python
@dataclass(frozen=True)
class LoopParams:
    c0: float = 1.0
    k: float = 0.2        # (a) fraction of the remaining gap closed per cycle
    ceiling: float = 2.5  # (a) the fixed improver's ceiling, in units of c0
    g0: float = 0.3       # (b), (c) gain delivered by the first cycle
    beta: float = 1.0     # (b) power-law decay of the gain: g_n = g0 / (1+n)^beta
    returns: float = 1.2  # (c) meta-gain r in g_{n+1} = r * g_n
    noise: float = 0.0    # relative Gaussian noise applied to each realised gain


def realised(gain: float, noise: float, rng: random.Random) -> float:
    if noise <= 0.0:
        return gain
    return gain * max(0.0, 1.0 + rng.gauss(0.0, noise))
```

- 默认值不是随便取的：`k = 0.2 = 1 − 0.8`，`ceiling = 2.5 = 1 + 0.3 / (1 − 0.8)`，正好让形状 (a) 与 (c, r = 0.8) 重合（见 3.3）。
- 噪声是**乘法**的：`gain × (1 + ε)`，`ε ~ N(0, σ)`；`max(0, ·)` 保证能力不会倒退。这是一个简化（真实系统会回退，阶段 15 · 08 的 regression detection 就是为此而设）。
- `frozen=True` 让参数不可变，配合 `dataclasses.replace` 派生新参数（`replace(p, noise=0.0)`）。

### 3.2 三种循环形状

```python
def simulate_fixed_improver(cycles, p, rng):
    cap = p.ceiling * p.c0
    c = p.c0
    traj = [c]
    for _ in range(cycles):
        c += realised(p.k * (cap - c), p.noise, rng)
        traj.append(c)
    return traj
```

- (a) 每轮缩小"离天花板的差距"的 `k` 倍，所以增益 `g_n = k (cap − C_n)` 是**由目标位置决定**的：改进器没动，是目标快碰到改进器的上限了。

```python
def simulate_diminishing(cycles, p, rng):
    c = p.c0
    traj = [c]
    for n in range(cycles):
        c += realised(p.g0 / (1.0 + n) ** p.beta, p.noise, rng)
        traj.append(c)
    return traj
```

- (b) 增益按 `n` 的幂律衰减，是**写死的时间表**。β = 1 时和式发散（调和级数），所以没有硬天花板，但 30 轮只到 2.20×，再跑 10 轮只多 0.08×。

```python
def simulate_self_referential(cycles, p, rng, returns=None):
    r = p.returns if returns is None else returns
    c, g = p.c0, p.g0
    traj = [c]
    for _ in range(cycles):
        g_real = realised(g, p.noise, rng)
        c += g_real
        g = r * g_real
        traj.append(c)
    return traj
```

- (c) 的关键是 `g` 是**状态**：这一轮实际得到的增益 `g_real` 决定下一轮的名义增益 `r · g_real`。
- 噪声进入 `g_real` 之后被**继承**：一次差的修改让后面所有轮次都变差——这就是讲义说的"在 (c) 里一次坏修改会被每一轮继承"。(a)、(b) 的噪声只影响当轮。
- `returns` 参数允许同一个 `p` 跑不同的 r（对照列 0.8 与 `--returns`）。

### 3.3 收敛、天花板与 identity check

```python
def analytic_ceiling(p, returns):
    if returns >= 1.0:
        return None
    return p.c0 + p.g0 / (1.0 - returns)


def matched_fixed_improver(p, returns):
    cap = analytic_ceiling(p, returns)
    assert cap is not None, "a matched fixed improver exists only for r < 1"
    return replace(p, k=1.0 - returns, ceiling=cap / p.c0, noise=0.0)
```

- r < 1 时 `g_n = g0 · r^n` 是几何级数，和为 `g0 / (1 − r)`，所以极限是 `c0 + g0/(1−r)`：r = 0.8 → 2.5×，r = 0.9 → 4.0×。r ≥ 1 返回 `None`，表示没有天花板。
- **identity check 的代数**：形状 (c) 的差距 `cap − C_n` 每轮乘以 r；形状 (a) 的差距每轮乘以 `1 − k`。取 `k = 1 − r`、相同的 `cap` 与 `C_0`，两条序列逐位相同。`run_part_a` 用噪声为 0 的两次模拟验证，打印 `max |delta| = 0.000000`（实测 4.4e-16，浮点误差）。
- 这是讲义最重要的一句话的数值证据："The capability curve cannot tell you whether a loop is recursive; only the edit log can."

### 3.4 `run_part_a`：并排表与摘要

```python
    traj_a = simulate_fixed_improver(n, p, random.Random(args.seed + 1))
    traj_b = simulate_diminishing(n, p, random.Random(args.seed + 2))
    traj_lo = simulate_self_referential(n, p, random.Random(args.seed + 3), returns=CONTRAST_RETURNS)
    traj_hi = simulate_self_referential(n, p, random.Random(args.seed + 4))
    ...
    step = max(1, n // 6)
    rows = sorted({0, 1, 2, 3, 4, 5, n} | set(range(0, n + 1, step)))
```

- 四列各用**独立** RNG（`seed + 1 … seed + 4`），改一列的参数不会打乱另一列的噪声序列——和阶段 15 · 07 讲解里批评的"全局 RNG 连锁效应"相反。
- 打印行：前 5 轮逐轮打印（看清起步），之后每 `n // 6` 轮一行，并保证最后一轮一定出现。
- 摘要表给每列：天花板（有解析解才给）、`C_N`、首末增益、10× 轮数。`fmt_cycles` 把 `None` 显示成 `never (<= N)`。

### 3.5 `run_sweep`：r 扫描与 Monte-Carlo

```python
    for r in sorted(set(SWEEP_RETURNS) | {args.returns}):
        det = simulate_self_referential(n, replace(p, noise=0.0), random.Random(0), returns=r)
        n_det = cycles_to_multiple(det)
        cap = analytic_ceiling(p, r)
        if p.noise > 0:
            hits = []
            for t in range(args.trials):
                traj = simulate_self_referential(n, p, random.Random(args.seed * 100_003 + t), returns=r)
                h = cycles_to_multiple(traj)
                if h is not None:
                    hits.append(h)
            frac = len(hits) / args.trials
            med = statistics.median(hits) if hits else None
```

- 用户的 `--returns` 会并入扫描集合并用 `<- --returns` 标出。
- 每个 r 先跑一条**无噪声**轨迹给确定性答案，再在 `noise > 0` 时跑 `trials` 条带噪声轨迹；每条轨迹的种子是 `seed * 100_003 + t`，不同 r 之间复用同一组种子，便于比较。
- 统计口径：`frac` 是达到 10× 的比例（`.1%` 格式），`len(hits)/trials` 是次数，`median` 只对达到的试验计算（条件中位数）。

### 3.6 枚举与 `SystemProfile`

```python
class Mechanism(Enum):
    NONE = "none"            # mechanism fixed / maintained by humans
    OPERATORS = "operators"  # evolves its own improvement operators (e.g. mutation prompts)
    CODE = "code"            # the code that proposes/applies/validates improvements is editable


@dataclass(frozen=True)
class SystemProfile:
    name: str
    year: int
    proposes: bool
    applies: bool
    validates: bool
    mechanism: Mechanism
    domain: Domain
    transfers: bool
    verifier: Verifier
    target: Target
    lesson: str
```

- `Mechanism` 回答"被修改的东西本身是不是一个改进器"，分三档而不是布尔值，就是为了把 Promptbreeder 这种"只演化变异算子、搜索代码不动"的边界情况显式表达出来。
- `Verifier` 按 Chen 等人的层级排列（formal → execution → judge → self），另加 `HUMAN` 表示人类评审（在层级之外）。
- `Target` 与 `Closure` 对应 Chen 等人的两个轴。

### 3.7 `alibaba_level`：五条判据的规则顺序

```python
def alibaba_level(p):
    notes = []
    if not p.proposes:
        return "L1", tuple(notes)
    if not (p.applies and p.validates):
        if p.mechanism is not Mechanism.NONE:
            notes.append("edits its mechanism but a human applies/validates -> still L2")
        return "L2", tuple(notes)
    if p.mechanism is Mechanism.NONE:
        if p.transfers:
            notes.append("transfers without self-reference -> L3, not L5")
        return "L3", tuple(notes)
    if p.domain is Domain.OPEN and p.transfers:
        return "L5", tuple(notes)
    if p.mechanism is Mechanism.OPERATORS:
        notes.append("operators-only self-reference (shallow)")
    if p.transfers:
        notes.append("transfer across fixed benchmarks is not an open domain -> L4, not L5")
    return "L4", tuple(notes)
```

- 规则是**有序**的：先问"有没有人在应用/验证环节"，再问"机制是否被修改"，最后问"领域是否开放"。顺序决定了边界案例的归属——机制被修改但要人类合并 → 仍是 L2（测试 `test_boundary_editing_mechanism_but_human_applies_is_not_L4`）。
- 每条分支都把"为什么没到更高一级"写进 `notes`，分级表下面会逐条打印，这比只给一个字母诚实。
- L5 要求 `domain == OPEN` **且** `transfers`；10 个系统里没有一个满足，所以 L5 为 0。

### 3.8 `SYSTEMS` 与 `run_part_b`

```python
SYSTEMS = (
    SystemProfile("STaR", 2022, True, True, True, Mechanism.NONE, Domain.SINGLE, False,
                  Verifier.EXECUTION, Target.POLICY, "P15-02 / L05"),
    ...
    SystemProfile("Human-in-loop FT", 2022, True, False, False, Mechanism.NONE, Domain.MULTI, False,
                  Verifier.HUMAN, Target.POLICY, "P18-01"),
)
```

- 系统被编码成**数据**而不是 if-else，所以练习 3 "加入 Self-Rewarding LMs" 只需再加一行。
- 几个容易争议的编码：STaR 的验证器是人类提供的标准答案，按"可执行的客观判据"归为 `EXECUTION`；DGM 的 `transfers=True` 指跨模型、跨语言迁移，但领域仍是 `SINGLE`（coding）；AIDE² 的 `mechanism=CODE` 指外层 agent 改写**内层研究 agent 的搜索代码**——内层本身是一个改进器，所以算自指；ADAS 的元 agent 从不被修改，`mechanism=NONE`。
- `run_part_b` 打印 P/A/V、五个属性、Liu 级别、Chen 格子和所属课程，然后逐条打印 `notes`。

### 3.9 `headline` 与 `main`

```python
    counts = {lvl: sum(1 for v in verdicts if v.level == lvl) for lvl in LEVEL_NAMES}
    top = max(counts, key=lambda k: counts[k])
    lines.append(
        f"Ladder: {counts['L4']} of {total} systems reach L4 (bounded RSI), {counts['L5']} reach L5; "
        f"the most populated rung is {top} ({LEVEL_NAMES[top]}) with {counts[top]}.")
```

- 每句 HEADLINE 都从 `part_a["summary"]`、`sweep`、`verdicts` 里取数：改 `--returns`，"reaches 10x at cycle …"那句会变成"does not reach 10x within …"；改 `SYSTEMS`，梯级计数、验证器计数、"transfer yet none is L5"的名单都会跟着变。
- `main` 校验 `--cycles`、`--trials` ≥ 1；只有给了 `--out` 才写文件，否则只打印。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用加法递推 `C += g` 而不是乘法复利 | 让"增益是状态"（形状 c）和"增益是时间表"（形状 b）的区别一目了然 | 真实能力常以对数尺度衡量；第 02 节改用回报率与再生数 |
| 默认参数让 (a) 与 (c, 0.8) 完全重合 | identity check 是讲义的核心论点，必须精确到浮点 | 参数显得"巧合"；`matched_fixed_improver` 把这种构造显式化 |
| 噪声只进 `g_real`，且在 (c) 里被继承 | 诚实建模"修改改进器的错误会传给后代" | 没有建模能力倒退；回退监控见阶段 15 · 08 |
| `max(0, 1+ε)` 截断 | 防止负增益 | 截断让噪声均值略大于 1；对中位数的拖累结论不受影响 |
| 四列独立 RNG，Monte-Carlo 每条轨迹独立种子 | 改一列不影响另一列；不同 r 复用同一组种子 | 比全局 `random.seed` 多几行代码 |
| 规则分级器 + `notes`，而不是打分 | 梯级定义本身就是规则；备注让边界可见 | 真实分级需要从论文摘证据——见 skill 文件的拒绝规则 |
| `Mechanism` 三档而非布尔 | 表达 Promptbreeder 这类"浅自指" | 规则仍把 OPERATORS 判为 L4，深度限定由读者决定 |
| 系统即数据（`SYSTEMS` 元组） | 加系统、改属性不碰逻辑 | 属性是作者的判断，不是论文的自述 |
| HEADLINE 全部由数据拼出 | 阶段 15 · 07 的硬编码结论被数据推翻过 | 句子略长 |
| 只在 `--out` 时写文件 | 课程约定 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class LoopParams:` | 不可变数据类；字段带默认值 |
| `dataclasses.replace` | `replace(p, noise=0.0)` | 复制并改少数字段，原对象不变 |
| `dataclasses.asdict` | `asdict(p)` | dataclass → dict，用于 JSON 报告 |
| `Enum` | `class Mechanism(Enum): NONE = "none"` | 有限取值；用 `is` 比较成员，`.value` 取字符串 |
| `Optional[int]` | `-> Optional[int]` | 可能返回 `None` 的类型注解 |
| 集合运算选行 | `sorted({0, 1, 2, 3, 4, 5, n} \| set(range(0, n + 1, step)))` | 并集去重后排序 |
| 条件表达式 | `r = p.returns if returns is None else returns` | 参数覆盖默认 |
| `random.Random(seed)` 实例 | `random.Random(args.seed + 3)` | 独立 RNG，互不干扰 |
| `statistics.median` | `statistics.median(hits)` | 条件中位数 |
| `next(..., default)` | `next((row for row in noisy if ...), noisy[-1])` | 取第一个匹配项，没有则用默认 |
| f-string 嵌套花括号 | `f"C_{{n+1}} = C_n + g_n"` | `{{` 输出字面 `{` |
| 格式说明符 | `{frac:>7.1%}`、`{x:.1e}`、`{traj[i]:>11.2f}x` | 百分比、科学计数、宽度与小数位 |
| `max(..., key=lambda)` | `max(counts, key=lambda k: counts[k])` | 按值取最大键 |
| `parser.error` | `parser.error("--cycles and --trials must be >= 1")` | 参数校验并以退出码 2 结束 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.12，seed 7，0.07 s），节选：

```text
  cycle     (a) fixed  (b) diminish    (c) r=0.80    (c) r=1.20
      0         1.00x         1.00x         1.00x         1.00x
      1         1.30x         1.30x         1.30x         1.30x   ← 四列第一轮增益都是 g0 = 0.3
      5         2.01x         1.69x         2.01x         3.23x   ← (a) 与 (c, 0.8) 逐位相同
     10         2.34x         1.88x         2.34x         8.79x
     15         2.45x         2.00x         2.45x        22.61x
     30         2.50x         2.20x         2.50x       355.56x   ← 只有 r > 1 那列在加速

  shape                    ceiling        C_N  first gain   last gain  cycles to 10x
  (a) fixed improver         2.50x      2.50x       0.300       0.000  never (<= 30)
  (b) diminishing            none       2.20x       0.300       0.010  never (<= 30)   ← 没有天花板，但增益只降不升
  (c) r=0.80                 2.50x      2.50x       0.300       0.000  never (<= 30)
  (c) r=1.20                 none     355.56x       0.300      59.344  cycle 11        ← 最后一轮增益 59，第一轮 0.3

  identity check (noise off): ... max |delta| over 30 cycles = 0.000000               ← 曲线分不出 (a) 和 (c, r<1)
```

```text
      r   ceiling   C_N det.    to 10x det.   reach 10x (noise)  median cycle
   0.80     2.50x      2.50x  never (<= 30)           (noise 0)             -
   0.90     4.00x      3.87x  never (<= 30)           (noise 0)             -   ← 1 + 0.3/0.1 = 4.0
   1.00     none      10.00x       cycle 30           (noise 0)             -   ← 线性：1 + 0.3 × 30 = 10，恰好第 30 轮
   1.10     none      50.35x       cycle 15           (noise 0)             -
   1.20     none     355.56x       cycle 11           (noise 0)             - <- --returns
   1.50     none   115051.04x        cycle 7           (noise 0)             -
```

```text
  system             yr  P A V mech      domain xfer verifier  L   Chen: target x closure      lesson
  Promptbreeder      23  Y Y Y operators single -    execution L4  behaviour x closed-in-task  L09   ← 浅自指，按字面是 L4
  ADAS               24  Y Y Y none      multi  Y    execution L3  behaviour x closed-in-task  L09   ← 有迁移、无自指 → L3
  DGM                25  Y Y Y code      single Y    execution L4  behaviour x closed-in-task  P15-04 / L10
  Human-in-loop FT   22  Y - - none      multi  -    human     L2  policy x human-in-loop      P18-01 ← 人类应用 → L2

HEADLINE
  - Shape (c) with r=1.2 reaches 10x at cycle 11 and ends at 355.6x: the only column whose per-cycle gain grows.
  - Identity check: a fixed improver with k=0.20 reproduces the r=0.8 recursive curve to within 4.4e-16; ...
  - Ladder: 4 of 10 systems reach L4 (bounded RSI), 0 reach L5; the most populated rung is L3 (Programmatic self-improvement) with 5.
  - Verifiers: 9 of 10 systems are checked by formal or execution-grade signals, 0 by self-assessment alone, 1 by humans.
  - 4 systems show transfer yet none is L5 (ADAS, DGM, Hyperagents, AIDE^2): ...
```

逐项解读：

- **r = 1.2 的 10× 轮数**：`1 + 0.3 (1.2^n − 1)/0.2 ≥ 10 ⇔ 1.2^n ≥ 7 ⇔ n ≥ 10.67`，所以是第 11 轮，与输出一致。r = 1.1 要 `1.1^n ≥ 4`，第 15 轮；r = 1.5 要 `1.5^n ≥ 16`，第 7 轮。
- **r = 1.0 恰好第 30 轮**：线性 `C_30 = 1 + 30 × 0.3 = 10.0`，是一个临界情形；下面的带噪声实验就围绕它。
- **梯级计数**：L2 1 个、L3 5 个、L4 4 个、L5 0 个；验证器 9 个 formal/execution、1 个 human、0 个 self。

**非默认运行** `python3 main.py --seed 3 --noise 0.1 --returns 1.0 --trials 500`，节选：

```text
  cycle     (a) fixed  (b) diminish    (c) r=0.80    (c) r=1.00
     30         2.50x         2.13x         2.30x         9.34x   ← 带噪声的 (c, 0.8) 停在 2.30，没到 2.50
  (c) r=1.00                 none       9.34x       0.292       0.298  never (<= 30)   ← 临界情形在噪声下没到 10×

      r   ceiling   C_N det.    to 10x det.   reach 10x (noise)  median cycle
   0.90     4.00x      3.87x  never (<= 30)        0.0% (0/500)             -
   1.00     none      10.00x       cycle 30     37.0% (185/500)          26.0 <- --returns   ← 只有 37% 的试验达到 10×
   1.10     none     50.35x       cycle 15    100.0% (500/500)          16.0
   1.20     none    355.56x       cycle 11    100.0% (500/500)          11.0

  - With noise 0.1 on the mechanism, r=1.0 reaches 10x in 185/500 trials (37.0%), median cycle 26.0, versus cycle 30 without noise.
```

- **为什么噪声拖累中位数**：(c) 里 `g_n = g_0 · r^n · Π(1 + ε_i)`。乘积的对数是和，`E[log(1+ε)] ≈ −σ²/2 < 0`，所以乘积的**中位数**小于 1，大多数试验的增益序列整体偏低；少数运气好的试验大幅偏高，把**均值**拉回 1。达到 10× 的试验中位轮次 26 < 30，是因为能达到的恰是那些"早期修改走运"的试验。
- **(c, 0.8) 停在 2.30×**：噪声被继承，早期一次负偏差把后面的几何级数整体压低；(a) 列在同样噪声下仍到 2.50×，因为它的增益由"离天花板的距离"决定，噪声只影响当轮。
- 换 seed 7 跑同样参数（`--returns 1.0 --noise 0.1 --trials 500`）：41.8%（209/500），中位 25.0。两次的结论一致，比例在 37%–42% 之间浮动。

---

## 7. 动手改一改

1. **（讲义练习 1）** 跑 `python3 main.py --cycles 40 --returns 0.9 --noise 0`，确认 r = 0.9 列第 40 轮是 3.96×、天花板 4.00×，并用 `1 + 3 (1 − 0.9^40)` 手算核对。
2. **（讲义练习 2）** 跑 `python3 main.py --returns 1.0 --noise 0.1 --trials 500`，记录达到 10× 的比例与中位轮次；再把 `--noise` 改成 0.05、0.2，画出"噪声 → 比例"的关系，并解释为什么 r = 1.1 在 σ = 0.1 下仍然 100%。
3. **（讲义练习 3）** 在 `SYSTEMS` 里加一行 Self-Rewarding LMs（actor 与 judge 同一个模型），验证器填 `Verifier.SELF` 还是 `Verifier.JUDGE`？重跑，看 "Verifiers: … by self-assessment alone" 那句怎么变。
4. 给 `alibaba_level` 加一个"深度限定"：`Mechanism.OPERATORS` 归 L3 并备注 "would be L4 if the search code were editable"。跑测试，看哪条测试需要同步修改，并思考两种规则各自的理由。
5. 给形状 (c) 加"回退"：噪声截断改为 `max(-0.5, 1 + ε)`，允许单轮负增益；观察 r = 1.0 的 Monte-Carlo 比例如何变化，并把阶段 15 · 08 的 regression detection 作为暂停条件加进去。
6. **进阶**：实现讲义练习 5——写 `guess_shape(traj)`，只凭 31 个数判断来自 (b) 还是 (c, r<1)。用 `matched_fixed_improver` 构造反例证明它在一般情况下做不到，再设计最小的"修改日志"数据结构（改了什么、谁应用的、怎么验证的）让判断成为可能。

---

## 8. 常见坑

- **从曲线读"递归"**：identity check 已证明 (a) 与 (c, r<1) 曲线相同；判断梯级要看修改日志，不看分数。
- **把 r = 1 当作"安全线"**：它是临界点；噪声让 63% 的试验达不到确定性结果，而 r = 1.1 就已经 100% 达到——阈值两侧的行为差别很大，第 02 节会把它和再生数 R_AI 对应起来。
- **以为"有迁移"就是 L5**：ADAS 有迁移但元 agent 不动，是 L3；DGM、Hyperagents、AIDE² 自指但在固定基准上，是 L4。
- **忽略 P/A/V 里的人类**：机制被修改但要人类合并，仍是 L2；`alibaba_level` 的规则顺序就是为此设计的。
- **把 `Verifier.JUDGE` 写成 `EXECUTION`**：隐藏的 LLM 裁判不是可执行验证；分错会让"9 of 10 formal/execution"的结论失真。
- **噪声用加法**：加法噪声在能力很小/很大时含义不同；本文件用乘法噪声并截断于 0，但要记住截断会让均值略偏正。
- **硬编码 HEADLINE**：阶段 15 · 07 的教训；这里每一句都从数据来，改参数不会留下过时的结论。
