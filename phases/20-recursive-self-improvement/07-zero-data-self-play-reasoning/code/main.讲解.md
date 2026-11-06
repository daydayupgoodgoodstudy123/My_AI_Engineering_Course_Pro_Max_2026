# 代码讲解 · main.py

> **所属小节**：阶段 20 · 递归自我改进 · 第 07 节 零数据自博弈：Absolute Zero、R-Zero、Agent0 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [--rounds 40] [--reward learnability|azr|random|hardest|easiest] [--verifier-fp 0.0] [--attempts 4] [--max-difficulty 14] [--proposer-start 4.0] [--seed 11] [--out x.json]` ｜ **依赖**：仅标准库（`argparse`、`json`、`math`、`random`、`statistics`、`dataclasses`）

---

## 1. 这份代码在考察什么

讲义把 Absolute Zero、R-Zero、Agent0 压缩成一个共同骨架：**提出者**出题 → **执行器**校验题目 → **求解器**多次尝试 → **执行器**验证答案 → 两个角色各自拿奖励。这份代码就是这个骨架的最小可运行版本，题目是模 97 的小整数程序，执行器是一个十几行的 Python 函数。

它要回答四个问题：

1. **提出者奖励的形状重要吗？** 同一个求解器、同一个种子，分别用"可学习性帐篷"（R-Zero / Agent0）、AZR 的非对称式 4、随机、总出最难、总出最简单五种奖励训练提出者，看最终技能差多少。
2. **提出者能跟上移动的前沿吗？** 求解器每轮都在变强，提出者只看得到"被接受的解出率" p̂，它能不能让平均难度 d̄ 贴着技能 s 走？
3. **解出的题多就学得多吗？** `easiest` 解出的题最多，学到的却不多——因为全胜的组在 GRPO 里没有梯度。
4. **验证器漏判会怎样？** `--verifier-fp` 让执行器以一定概率把错误答案判对。提出者据此把题出得更难，求解器则在错误解法上训练，技能反而下降。

> 一句话：**用一个真会执行、真会验证的玩具执行器，把"奖励 p ≈ 0.5 的任务"这一公式与它的四种失效方式放在一张表里。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_SEED`、`MODULUS`、`OPS`、`MODES`、`REWARD_SCHEMES` | 常量 | 种子 11、模 97、四种运算、三种任务模式、五种奖励 | 任务空间 |
| `sigmoid`、`solve_probability` | 函数 | p(解出) = sigmoid(s − d) | 求解器的潜在能力 |
| `Task` | frozen dataclass | 模式 + 程序 + 4 个样本输入；`difficulty` = 程序长度 | 一道题 |
| `execute` | 函数 | **执行器**：逐条运行 `add/sub/mul/xor` | 标准答案的唯一来源 |
| `sample_program`、`propose_task` | 函数 | 按难度 d 随机生成程序和输入 | 提出者写题 |
| `validate_task` | 函数 | 执行器校验：拒绝常数输出等退化题 | AZR 的"环境过滤提案" |
| `reference_answer`、`verify`、`wrong_answer` | 函数 | 三种模式各自的参考答案、验证规则、"看着像但会被拒"的错误答案 | 演绎 / 溯因 / 归纳 |
| `attempt`、`judge` | 函数 | 求解器按概率给出对/错答案；验证器判定，可带假阳性 | GRPO 的一次 rollout + 验证 |
| `learnability_reward`、`azr_reward`、`proposer_reward` | 函数 | 五种提出者奖励 | 可学习性 vs 其他 |
| `Proposer` | dataclass | 对难度的高斯策略，REINFORCE 更新均值 μ | Challenger / 课程 agent |
| `Config`、`RoundStat`、`RunResult` | dataclass | 参数、每轮统计、整次运行结果 | 可复现实验 |
| `run_loop` | 函数 | 完整循环；求解器按 4p̂(1−p̂) 信号学习 | 自博弈闭环 |
| `round_table`、`comparison_table`、`fp_table`、`headline` | 函数 | 报表与由数字拼出的 HEADLINE | 结果解读 |
| `main` | 函数 | 解析参数，跑 1 次详细 + 5 种奖励 + 3 档漏判率 | 入口 |

数据流：命令行 → `Config` → `run_loop`（每轮：`Proposer.sample` → `propose_task` → `validate_task` → 4 × `attempt`/`judge` → `proposer_reward` → `Proposer.update` → 求解器技能更新）→ 五种奖励各跑一遍 → 三档 `verifier_fp` 各跑一遍 → `headline` 用这些数字生成结论。

---

## 3. 逐段精讲

### 3.1 求解器的潜在能力

```python
def solve_probability(skill: float, difficulty: int) -> float:
    """The solver's latent chance of solving a task of difficulty d."""
    return sigmoid(skill - difficulty)
```

- 技能 s 和难度 d 在同一尺度上：s = d 时正好五成，s − d = 2 时约 88%，s − d = −2 时约 12%。
- 这是整个模拟器里**唯一的"隐变量"**：提出者看不到 s，只能从被验证器接受的次数反推。
- `sigmoid` 用了数值稳定的分段写法，避免 `exp(-x)` 在 x 很负时溢出。

### 3.2 执行器：标准答案从这里来

```python
def execute(program: Program, x: int) -> int:
    """The executor. Ground truth for every task comes from running this."""
    for op, k in program:
        if op == "add":
            x = (x + k) % MODULUS
        elif op == "sub":
            x = (x - k) % MODULUS
        elif op == "mul":
            x = (x * k) % MODULUS
        elif op == "xor":
            x = (x ^ k) % MODULUS
        else:
            raise ValueError(f"unknown op {op!r}")
    return x
```

- 每一步都取模 97，所有中间值都在 0..96 之间，程序再长也不会溢出。
- 它既是"出题时算答案"的工具，也是"验证时重算"的工具——与 AZR 里 Python 执行器的双重角色一致。
- 对应讲义的关键句：零数据不等于零接地，接地来自这个函数。

### 3.3 出题与校验

```python
def sample_program(d: int, rng: random.Random) -> Program:
    ops: list[tuple[str, int]] = []
    for _ in range(d):
        op = rng.choice(OPS)
        if op == "mul":
            k = rng.randint(0, 12)  # k = 0 collapses the program to a constant
        ...
```

```python
def validate_task(task: Task) -> tuple[bool, str]:
    """Executor-side validation (AZR: the environment filters proposals)."""
    ...
    outputs = [execute(task.program, x) for x in task.inputs]
    if len(set(outputs)) == 1:
        return False, "constant-output"
    return True, "ok"
```

- `mul 0` 是故意留的"陷阱"：它让后面所有输入的输出都一样。这类程序对溯因（任何输入都对）和归纳（没有信息）都是退化题，执行器在 4 个样本输入上跑一遍，发现输出全同就拒绝。
- 被拒的任务提出者拿 0 奖励（见 `run_loop`），对应 AZR 里"程序必须能跑、确定、安全"的过滤。
- 报表里的 `reject` 列和 `rejected` 列就是这里的计数。

### 3.4 三种任务模式：各自的验证规则

```python
def verify(task: Task, answer) -> bool:
    """Executor-side verification, one rule per task mode (AZR Section 3.2)."""
    if task.mode == "deduction":  # given p and i, predict o
        return answer == execute(task.program, task.inputs[0])
    if task.mode == "abduction":  # given p and o, find any i with p(i) = o
        if not isinstance(answer, int):
            return False
        return execute(task.program, answer) == execute(task.program, task.inputs[0])
    try:  # induction: the synthesized program must match shown AND held-out pairs
        return all(execute(answer, x) == execute(task.program, x) for x in task.inputs)
    except (ValueError, TypeError):
        return False
```

- **演绎**：直接比较输出。
- **溯因**：不比较"是不是原来那个输入"，而是把求解器给的输入跑一遍看输出对不对——程序不是单射，多个输入可能都对，这正是 AZR 的处理方式。
- **归纳**：求解器交的是一段程序，要在全部 4 个输入上与原程序一致。前两对相当于"给出的样例"，后两对相当于保留集（held-out），防止只拟合看到的样例。

`wrong_answer` 负责造出"一定会被拒"的错误答案：演绎加一个非零偏移；溯因从随机起点扫描直到找到输出不同的输入（非常数程序一定存在）；归纳在程序末尾追加 `add k`（k ≠ 0 mod 97），所有输出整体平移，必然不一致。这样 `--verifier-fp 0` 时假阳性恒为 0，验证器漏判成为**唯一**的噪声来源。

### 3.5 一次尝试与一次判定

```python
def attempt(task: Task, skill: float, rng: random.Random):
    """The solver: correct with probability sigmoid(s - d), otherwise wrong."""
    if rng.random() < solve_probability(skill, task.difficulty):
        return reference_answer(task)
    return wrong_answer(task, rng)


def judge(task: Task, answer, verifier_fp: float, rng: random.Random) -> tuple[bool, bool]:
    """Return (accepted, truly_correct). A leaky verifier accepts some failures."""
    truly = verify(task, answer)
    accepted = truly or (verifier_fp > 0.0 and rng.random() < verifier_fp)
    return accepted, truly
```

- 求解器是"按概率答对"的随机模型，但答案本身是真实的、要经执行器验证的——模拟器不信求解器的自我报告。
- `judge` 返回两个布尔值：`accepted` 是循环内部能看到的（提出者、求解器都只看它），`truly` 只有报表和测试看得到。两者的差就是假阳性数。

### 3.6 五种提出者奖励

```python
def learnability_reward(p_hat: float) -> float:
    """R-Zero / Agent0 uncertainty reward: 1 - |2p - 1|. Peaks at p = 0.5."""
    return 1.0 - abs(2.0 * p_hat - 1.0)


def azr_reward(p_hat: float) -> float:
    """Absolute Zero Eq. 4: 0 if the solver never succeeds, else 1 - p (so 0 at p = 1)."""
    return 0.0 if p_hat <= 0.0 else 1.0 - p_hat
```

| 方案 | 公式 | p̂ = 0 | 0.25 | 0.5 | 0.75 | 1 |
|------|------|------|------|-----|------|---|
| `learnability` | 1 − \|2p̂ − 1\| | 0 | 0.5 | **1** | 0.5 | 0 |
| `azr` | p̂ = 0 → 0，否则 1 − p̂ | 0 | **0.75** | 0.5 | 0.25 | 0 |
| `hardest` | d / max_d | 与 p̂ 无关 | | | | |
| `easiest` | (max_d − d) / (max_d − 1) | 与 p̂ 无关 | | | | |
| `random` | 不更新，均匀抽 d | — | | | | |

- 4 次尝试下 p̂ 只有 5 个取值，所以帐篷奖励只会出现 0 / 0.5 / 1 三个数——这也是为什么逐轮表里的平均奖励稳定在 0.3–0.5。
- `azr` 偏向"难但可解"：p̂ = 0.25 的奖励比 p̂ = 0.75 高三倍。讲义的对比表里它跟踪得更紧、出的题略难。

### 3.7 提出者：对难度的高斯策略

```python
@dataclass
class Proposer:
    max_d: int
    scheme: str
    mu: float = 4.0
    sigma: float = 1.5
    step: float = 0.15
    baseline: float = 0.5

    def sample(self, rng: random.Random) -> int:
        if self.scheme == "random":
            return rng.randint(1, self.max_d)
        d = int(round(rng.gauss(self.mu, self.sigma)))
        return min(max(d, 1), self.max_d)

    def update(self, d: int, reward: float) -> None:
        if self.scheme == "random":
            return
        adv = reward - self.baseline
        self.mu += self.step * adv * (d - self.mu) / self.sigma
        self.mu = min(max(self.mu, 1.0), float(self.max_d))
        self.baseline += 0.1 * (reward - self.baseline)
```

- `mu` 是提出者"认为前沿在哪"的信念；`sigma` 固定为 1.5，所以出的题总有一定难度分布。
- `update` 是对高斯策略的 REINFORCE：score function ∝ (d − μ)/σ，乘以优势（奖励减去滑动基线）。比均值难的题拿到高于平均的奖励，μ 就往上走；反之往下。
- `mu` 初始值 4.0（命令行 `--proposer-start`），比求解器初始技能 2.0 高两级，对应三篇论文都从"基座模型已能部分解出"的种子任务起步。练习 4 把它改成 7.5 看冷启动代价。
- 真实系统里的 Challenger 是一个 LLM，输出的是题目文本而不是一个数字；这里把"题目有多难"压缩成一维，是为了让跟踪行为可见。

### 3.8 主循环：求解器怎么学

```python
            p_hat = k_acc / cfg.attempts  # the proposer only sees what the verifier accepted
            reward = proposer_reward(cfg.reward, p_hat, d, cfg.max_difficulty)
            proposer.update(d, reward)
            # Solver learns from accepted solutions. Group signal 4p(1-p) is zero when
            # every attempt agrees (GRPO-style: no advantage). Accepted-but-wrong
            # solutions teach the wrong thing and pull skill down.
            signal = 4.0 * p_hat * (1.0 - p_hat)
            if k_acc > 0:
                skill += cfg.learning_rate * signal * (k_true - (k_acc - k_true)) / k_acc
                skill = min(max(skill, 0.0), cfg.max_difficulty + 1.0)
```

- `signal = 4p̂(1−p̂)`：组内全败（p̂ = 0）或全胜（p̂ = 1）时为 0——GRPO 归一化后优势为零，权重不动。这是讲义"为什么奖励前沿有效"一节的核心。
- `(k_true − k_false) / k_acc`：被接受的解法里，真对的推高技能、假对的拉低技能。`--verifier-fp 0` 时这一项恒为 1。
- 技能上限 `max_difficulty + 1`：求解器学不到比最难的题还难的东西，对应 Agent0 的论点"任务空间的天花板由求解器 + 工具决定"。
- 注意 `p_hat` 用的是 `k_acc`（被接受数），不是 `k_true`——提出者和求解器都只能看到验证器的输出，这是漏判能传染整个循环的原因。

### 3.9 由数字生成的 HEADLINE

```python
    verb = "beats" if lrn.final_skill > max(hard.final_skill, easy.final_skill) else "does not beat"
    lines = [
        f"Learnability reward {verb} 'hardest' and 'easiest': final skill {lrn.final_skill:.2f} "
        f"vs {hard.final_skill:.2f} and {easy.final_skill:.2f} ...",
```

- 结论里的动词（beats / does not beat、cut / did not cut）都由比较结果决定，参数一改结论会跟着变——阶段 15 · 07 的讲解里批评过硬编码结论的问题，这里刻意避开。
- `main` 里五种奖励共用同一个 `Config`，只替换 `reward` 字段：`Config(**{**asdict(base), "reward": s})`。漏判率对比同理。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用真实可执行的小程序做任务，而不是抽象的"难度数字" | 让执行器的校验 / 验证是真的，三种任务模式有真实区别 | 程序空间很小、难度只由长度决定；真实系统的难度是多维的、不可直接观测 |
| 求解器是 `sigmoid(s − d)` 的随机模型 | 把"学习"压缩成一个标量，便于比较奖励方案 | 没有参数、没有泛化；生产中技能只能通过 held-out 基准间接测 |
| 学习量 = 4p̂(1−p̂) × 真假解法净值 | 直接对应 GRPO 组内归一化"全同则零梯度" | 这是对梯度大小的近似；真实的 GRPO 还有 KL、裁剪、长度等因素 |
| 提出者是一维高斯策略 + REINFORCE | 能跟踪移动的前沿，且每一步可解释 | 真实的 Challenger 输出文本，还要处理多样性、格式、重复惩罚 |
| 提出者热启动 μ₀ = 4（高于 s₀ = 2） | 对应论文从种子任务起步；冷启动需要很多轮才能找到前沿 | 练习 4 展示 μ₀ = 7.5 时跟踪误差翻倍、叠加漏判时坍缩 |
| `--verifier-fp` 只模拟假阳性 | 假阳性是会被循环放大的那一类错误（错解被当成正解训练） | 假阴性（对的被判错）只浪费样本、不污染数据，故未建模 |
| 每种方案都用同一个 `random.Random(seed)` | 公平对比、完全可复现 | 不同方案的随机流在第一次分叉后就不同步了，差异含有随机成分，应多换几个种子（练习里有 seed 3、5） |
| HEADLINE 全由 f-string 生成 | 参数改变时结论不会失真 | 句式固定，极端参数下措辞可能生硬 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类型别名 | `Program = tuple[tuple[str, int], ...]` | `...` 表示"任意长度的同类型元组" |
| `@dataclass(frozen=True)` | `class Task:` | 不可变、可哈希；`difficulty` 用 `@property` 由程序长度推出 |
| 多返回值 | `return False, "constant-output"` | 返回元组，调用处 `ok, _reason = validate_task(task)` 解包 |
| 元组拼接 | `task.program + (("add", k),)` | 单元素元组要写成 `(x,)`，否则只是括号 |
| 生成器表达式 + `all` | `all(execute(answer, x) == ... for x in task.inputs)` | 短路求值，第一个不相等就返回 False |
| `isinstance` 守卫 | `if not isinstance(answer, int): return False` | 归纳模式会把程序当答案传进来，先排除类型不符 |
| 布尔转整数 | `k_acc += int(accepted)` | `True → 1`、`False → 0` |
| 条件表达式 | `verb = "beats" if ... else "does not beat"` | 三元运算 |
| `statistics.fmean` | `statistics.fmean(ds)` | 浮点均值，比 `sum/len` 更稳 |
| `asdict` + 字典解包 | `Config(**{**asdict(base), "reward": s})` | 复制一个 dataclass 并只改一个字段 |
| 集合去重排序 | `sorted({0.0, 0.10, 0.25, base.verifier_fp})` | 保证用户给的漏判率也进入对比表且不重复 |
| f-string 格式 | `{x:>7.2f}`、`{p:>9.1%}`、`{gap:>+6.2f}` | 右对齐宽度、两位小数、百分比保留一位、强制正负号 |
| `argparse` 的 `choices` | `choices=REWARD_SCHEMES` | 非法取值直接报错并列出可选项 |
| `RawDescriptionHelpFormatter` | `formatter_class=...` | 让 `--help` 原样显示模块文档字符串的换行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.12，seed 11，约 0.15 秒），节选：

```text
Round-by-round, proposer reward = 'learnability'
  round  mean d   skill     d-s  obs solve  true solve  reject  reward
      4    2.68    2.75   -0.07      48.9%       48.9%       2    0.48   ← 前 4 轮 μ 从 4.0 回落到求解器真实水平
      8    2.77    3.40   -0.63      58.0%       58.0%       2    0.43
     16    4.61    4.71   -0.10      56.5%       56.5%       1    0.30   ← d 贴着 s 走
     24    5.43    5.99   -0.56      54.3%       54.3%       1    0.39   ← 平均难度首次超过 5（练习 1）
     32    6.25    7.27   -1.02      66.2%       66.2%       4    0.47
     40    8.11    8.63   -0.53      48.7%       48.7%       5    0.39   ← 40 轮技能 2.00 → 8.63
  verified solutions by task mode: deduction 704, abduction 682, induction 699   ← 三种模式各约三分之一

Comparison across proposer rewards (same seed, same verifier fp)
  scheme       final s   gain track|d-s| true solved false acc zero-grad rejected
  learnability    8.63  +6.63       0.67        2085         0       351       77
  azr             8.74  +6.74       0.27        1655         0       346       74   ← 跟踪最紧、解出更少、技能略高
  random          4.54  +2.54       3.92         707         0       636       116  ← 一半以上的组是零梯度
  hardest         2.79  +0.79       7.09          95         0       741       153  ← 3840 次尝试只对 95 次
  easiest         5.42  +3.42       2.60        3160         0       645        31  ← 解得最多，学得不多

Contrast: leaky verifier under 'learnability'
  verifier fp final s true solved false acc obs solve (last) true solve (last) mean d (last)
         0.0%    8.63        2085         0            48.7%             48.7%          8.11
        10.0%    6.89        1656       180            47.6%             42.9%          7.24
        25.0%    2.08         983       664            34.4%             13.5%          4.67   ← 观测 34.4% vs 真实 13.5%
```

HEADLINE（全部由上表数字生成）：

```text
  Learnability reward beats 'hardest' and 'easiest': final skill 8.63 vs 2.79 and 5.42 (all start at 2.00; ceiling is difficulty 14).
  Learnability proposals stayed within 0.67 difficulty levels of the solver's skill on average; random stayed within 3.92 and spent 75.4% of its valid tasks on zero-gradient groups (all fail or all pass).
  'hardest' produced 95 verified solutions out of 3840 attempts; 'easiest' produced 3160 but plateaued at skill 5.42 because 69.4% of its groups were all-pass.
  AZR's asymmetric reward (0 at p=0, else 1-p) ended at 8.74 with tracking error 0.27; the symmetric tent ended at 8.63.
  A verifier that wrongly accepts 25.0% of failures cut final skill from 8.63 to 2.08 under 'learnability'; it let through 664 false positives and the observed solve rate (34.4%) overstated the true one (13.5%).
  Best scheme at seed 11: 'azr' (final skill 8.74).
```

逐项解读：

- **跟踪**：`d-s` 列从第 16 轮起基本在 −1 到 0 之间，平均 0.67 级。帐篷奖励略微偏"易"，因为 4 次尝试下 p̂ = 0.75 和 0.25 奖励相同，而 μ 稍低时全胜组少、全败组也少。
- **解出率 ≠ 奖励**：`obs solve` 在 48%–68% 之间摆，平均奖励却稳定在 0.3–0.5。奖励是逐题算的（取值只有 0 / 0.5 / 1），再按题平均；而解出率是把难度分布里的易题和难题混在一起的总量。
- **数量不是信号**：`easiest` 解出 3,160 题（最多），技能只到 5.42；`learnability` 解出 2,085 题，技能 8.63。差别在 `zero-grad`：`easiest` 有 645 个组是全胜，GRPO 里这些组的优势为零。
- **漏判传染**：25% 漏判时，观测解出率 34.4% 远高于真实 13.5%，提出者据此把题出到平均 4.67 级，而求解器真实技能只有 2.08——它在 664 个错误"正解"上训练过。

**非默认参数** `python3 main.py --seed 3 --reward azr --verifier-fp 0.1 --rounds 30`：

```text
Round-by-round, proposer reward = 'azr'
  round  mean d   skill     d-s  obs solve  true solve  reject  reward
      3    3.91    2.05   +1.86      21.6%       10.2%       2    0.38   ← 观测 21.6% 中有一半是假阳性
      9    3.50    2.32   +1.18      40.9%       33.0%       2    0.41
     18    3.43    3.37   -0.03      40.5%       38.1%       3    0.40
     30    4.96    4.54   +0.42      46.7%       40.2%       1    0.36   ← 30 轮后 4.54，而 fp = 0 时为 7.19

Comparison across proposer rewards (same seed, same verifier fp)
  scheme       final s   gain track|d-s| true solved false acc zero-grad rejected
  learnability    5.34  +3.34       0.60        1138       156       221       48
  azr             4.54  +2.54       0.89         901       165       237       57
  random          2.09  +0.09       4.87         372       193       327       88
  hardest         0.25  -1.75       6.63          93       253       350       95   ← 全靠假阳性"学"，技能跌破起点
  easiest         4.67  +2.67       2.07        2190        62       419       24   ← 易题假阳性少（大多本来就对）

Contrast: leaky verifier under 'azr'
  verifier fp final s true solved false acc obs solve (last) true solve (last) mean d (last)
         0.0%    7.19        1176         0            64.3%             64.3%          6.43
        10.0%    4.54         901         165           46.7%             40.2%          4.96
        25.0%    0.00         204         629           32.6%              2.2%          3.61   ← 坍缩到 0
```

- 换种子、换奖励后，定性结论不变：learnability / azr 远胜 hardest / easiest，漏判率越高技能越低。但**谁是第一名会换**：seed 11、fp 0 时 `azr` 略胜，seed 3、fp 0.1 时 `learnability` 略胜。两者相差不到 1 级，属于随机成分。
- `hardest` 在漏判下跌破起点（0.25 甚至 0.00）：它出的题几乎没人真解得出，被接受的"正解"几乎全是假阳性，求解器学到的全是错的。

**其他参数的最终技能**（seed 11，`learnability` 方案）：

| 参数 | learnability | azr | random | hardest | easiest | 说明 |
|------|-------------|-----|--------|---------|---------|------|
| 默认 | 8.63 | 8.74 | 4.54 | 2.79 | 5.42 | 基线 |
| `--attempts 8` | 9.69 | 9.43 | 5.24 | 3.05 | 5.61 | p̂ 分辩率更高，零梯度组 351 → 168 |
| `--proposer-start 7.5` | 7.08 | 7.35 | 4.54 | 2.02 | 5.29 | 冷启动，跟踪误差 0.67 → 1.78 |
| `--max-difficulty 8` | 8.85 | 9.00 | 6.74 | 2.69 | 5.41 | 顶到上限 9（max_d + 1） |
| `--rounds 80` | 14.77 | 14.99 | 7.21 | 2.79 | 6.41 | 顶到上限 15；任务空间就是天花板 |
| `--verifier-fp 0.1` | 6.89 | 6.23 | 1.67 | 0.00 | 5.20 | random、hardest 跌破起点 |
| `--seed 3` | 8.71 | 8.96 | 5.02 | 2.72 | 5.36 | 定性结论不变 |
| `--seed 5` | 8.54 | 8.81 | 4.58 | 2.79 | 5.39 | 定性结论不变 |

---

## 7. 动手改一改

1. **（讲义练习 1）** 跑默认命令，找出 `mean d` 首次超过 5 的那一行（第 24 轮，5.43），再把 `obs solve` 与 `reward` 两列画成折线，解释为什么一个在波动、一个很平。
2. **（讲义练习 2）** 跑 `--attempts 8` 与默认对比：9.69 vs 8.63、零梯度组 168 vs 351。再试 `--attempts 2`，预测零梯度组会变多还是变少，验证之。
3. **（讲义练习 3）** 跑 `--verifier-fp 0.1`，解释 `hardest` 为何跌到 0.00、`random` 为何跌破起点（1.67）。然后在 `run_loop` 里加一个"外部审计"：每轮随机抽 10 个被接受的解法用 `verify` 重新核对，估计假阳性率并打印——这就是 R-Zero 第 4.4 节用 GPT-4o 做的事的玩具版。
4. **（讲义练习 4）** 跑 `--proposer-start 7.5`（跟踪误差 1.78），再叠加 `--verifier-fp 0.1`（技能 0.00）。把 `Proposer.sigma` 改成 3.0 重跑冷启动，看更宽的探索是否能挽救。
5. **（讲义练习 5）** 把 `signal = 4.0 * p_hat * (1.0 - p_hat)` 改成 `signal = 1.0`，重跑五种方案的对比。`easiest` 是否反超？解释你去掉的是 GRPO 的哪一条性质。
6. **进阶：多数投票验证器。** 把 `judge` 改成 R-Zero 式：不调用 `verify`，而是把 4 次尝试的答案做多数投票当伪标签，与伪标签一致即"接受"。观察随着技能上升、题目变难，伪标签与 `reference_answer` 的一致率如何下降——复现讲义里 79% → 63% 的曲线形状。

---

## 8. 常见坑

- **把"被接受"当成"正确"**：`p_hat` 用的是 `k_acc`。这是刻意的——循环内部只能看到验证器的输出。读报表时要同时看 `obs solve` 和 `true solve`。
- **以为解出得多就学得多**：`easiest` 的 `true solved` 最高，技能却远低于 `learnability`。全胜的组在 GRPO 里没有梯度。
- **拿单个种子的冠军下结论**：`azr` 与 `learnability` 谁更高随种子变化，差距不到 1 级；稳健的结论是"两者都远胜 hardest / easiest"。
- **冷启动**：`--proposer-start 7.5` 时提出者在远离前沿的地方拿到的奖励几乎全是 0，REINFORCE 没有方向；三篇论文都从种子任务起步不是偶然。
- **忘了上限**：技能被钳在 `max_difficulty + 1`，`--rounds 80` 跑到 14.77 不是"收敛"而是"碰顶"。这正是 Agent0 用工具抬高任务空间天花板的理由。
- **只模拟了假阳性**：假阴性（对的被判错）会浪费样本但不会污染训练数据，本模拟器没有建模；真实验证器两种错误都有。
- **难度一维化**：这里难度 = 程序长度，真实任务的难度不可直接观测，`mean d` 这列在生产中只能用 held-out 基准代替。
