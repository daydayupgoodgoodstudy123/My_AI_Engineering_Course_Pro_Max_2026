# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 04 节 Darwin Godel Machine：开放式自我修改 Agents ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（侧信道关闭）或 `python main.py --reward-hack-allowed`（侧信道打开） ｜ **依赖**：仅标准库（`random`、`sys`、`dataclasses`）

---

## 1. 这份代码在考察什么

用一个极小的"字符串处理 agent"模拟 DGM 的自我修改循环：

1. **被修改的对象是 agent 本身**：agent = 一串工具名（`["collapse", "trim", ...]`），变异就是对这串工具做替换/插入/删除——对应 DGM 修改自己的脚手架代码。
2. **archive + 经验分数**：每个变体在 8 个用例上打分，按 `(工具数, 分数)` 存入 archive，随机选父代继续变异——对应 "empirical score delta + archive"。
3. **reward hacking 侧信道**：agent 身上有一个 `hack_bonus` 字段，在 `--reward-hack-allowed` 下会被加到"报告分数"上，而且会随变异缓慢增长——对应 DGM 修改工具、移除幻觉检测标记以抬高分数。
4. **reported vs true**：同时记录"loop 看到的分数"和"真实行为分数"，两者之差就是 hack 的量。

> 一句话：**当评分路径经过 agent 能改的东西时，选择压力会自动把分数推离真实能力**——evaluator 必须放在 agent 够不着的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TOOLS` | 列表（名字, lambda） | 6 个字符串工具：upper/lower/reverse/trim/collapse/nop | agent 可组合的工具库 |
| `CASES` | 列表（输入, 期望） | 8 个"杂乱字符串 → title-case 规范形式"的用例 | benchmark |
| `hash_seq` | 函数 | 把列表转成元组（未被使用） | — |
| `Agent` | dataclass | `ops`（工具序列）+ `hack_bonus`（侧信道） | agent 脚手架 + 可被篡改的评分相关代码 |
| `apply` | 函数 | 依次应用工具 | agent 执行任务 |
| `true_score` | 函数 | 8 个用例的通过率 | 真实行为 |
| `reported_score` | 函数 | 侧信道打开时 `min(1, true + bonus)` | loop 看到的分数 |
| `mutate` | 函数 | 替换/插入/删除一个工具；打开侧信道时 8% 概率让 bonus 增加 `U(0, 0.1)` | LLM 提出的自我修改 |
| `run_dgm` | 函数 | 初始化 archive → 循环：选父代 → 变异 → 打分 → 入库 → 打印新纪录 | DGM 主循环 |
| `main` | 函数 | 解析命令行，跑 200 代，打印 HEADLINE | 入口 |

数据流：`main()` → `run_dgm(200, hack_allowed, seed=7)` → 每代 `random.choice(archive)` → `mutate` → `reported_score`/`true_score`（内部 `apply`）→ 按键 `(len(ops), round(rep, 2))` 入库 → 结束时取 reported 最高者，打印 reported、true 及其差值。

---

## 3. 逐段精讲

### 3.1 工具库与 benchmark

```python
TOOLS = [
    ("upper", lambda s: s.upper()),
    ("lower", lambda s: s.lower()),
    ("reverse", lambda s: s[::-1]),
    ("trim", lambda s: s.strip()),
    ("collapse", lambda s: " ".join(s.split())),
    ("nop", lambda s: s),
]

CASES = [
    ("  Hello   World  ", "Hello World"),
    ("FOO   bar", "Foo Bar"),
    ...
]
```

- 每个工具是 `(名字, 函数)` 元组；`lambda s: ...` 是匿名函数。
- `collapse`：`s.split()` 不带参数时按任意空白（空格、制表符、换行）切分并丢弃空串，再用单个空格拼回——同时完成"压缩空白"和"去首尾空白"，所以它覆盖了 `trim` 的效果。
- `s[::-1]` 是步长为 −1 的切片，得到反转字符串。
- **期望输出都是 title-case**（每个单词首字母大写），但工具库里没有 title 工具。穷举验证：只有 `"  Hello   World  "` 和 `"   X   "` 两个用例可解，**真实分数上限是 2/8 = 0.25**。
- ⚠️ 注释自相矛盾：第 31 行写 "Target: collapse whitespace, trim, lower."，第 42 行又写 "then title-case"。后者与数据一致；若真是 lower，`collapse + lower` 就能满分。
- 这个"故意不可达"的设计让 hack 成为提高 reported score 的唯一途径——演示效果清晰，但也意味着它无法展示"hack 与真实改进竞争"的情形（见测验 Q12）。

### 3.2 `Agent` 与 `apply`

```python
@dataclass
class Agent:
    ops: list[str]
    hack_bonus: float = 0.0


def apply(agent: Agent, s: str) -> str:
    tool_map = dict(TOOLS)
    for op in agent.ops:
        fn = tool_map.get(op)
        if fn is None:
            return ""
        s = fn(s)
    return s
```

- `hack_bonus` 带默认值 0.0；dataclass 规定有默认值的字段必须放在无默认值字段之后。
- `dict(TOOLS)`：把 `(键, 值)` 元组列表直接转成字典。每次调用都重建一次（8 个用例 × 每代 2 次以上），效率不高但无关紧要，可提到模块级常量。
- `tool_map.get(op)` 找不到时返回 `None`，此时整条输出为空串——相当于"agent 调用了不存在的工具就失败"。由于 `mutate` 只从 `TOOLS` 里取名字，这个分支实际不会触发。
- 字段注释写明 `hack_bonus` "Stands in for any edit the agent could make to the scoring pipeline itself"——它是一个抽象：真实 DGM 中对应"不再插入幻觉检测标记"这类修改。

### 3.3 两个分数

```python
def true_score(agent: Agent) -> float:
    correct = 0
    for inp, want in CASES:
        if apply(agent, inp) == want:
            correct += 1
    return correct / len(CASES)


def reported_score(agent: Agent, hack_allowed: bool) -> float:
    base = true_score(agent)
    if hack_allowed:
        return min(1.0, base + agent.hack_bonus)
    return base
```

- `true_score` 只看行为：输出是否与期望完全相等。分数只能取 0、0.125、0.25（上限）。
- `reported_score` 在侧信道打开时**读取了 agent 自己的字段** `hack_bonus`——这就是"evaluator 在 agent 可编辑的命名空间里"的代码化表达。skill 文件 hard reject："Any score adjustment that is applied at the agent's side of the boundary."
- `min(1.0, ...)` 截断：reported 饱和在 1.0 后，被 hack 的变体与真正满分的变体无法区分。
- ⚠️ 模块 docstring 说 "scored on held-out inputs"，讲义也说 "scores the agent's performance on held-out problems"，但实际只有一组固定的 `CASES`，选择与报告用的是同一批数据。

### 3.4 `mutate`：三种结构变异 + hack 漂移

```python
def mutate(parent: Agent, hack_allowed: bool) -> Agent:
    ops = list(parent.ops)
    move = random.random()
    if move < 0.3 and ops:
        i = random.randrange(len(ops))
        ops[i] = random.choice([t[0] for t in TOOLS])
    elif move < 0.6 and len(ops) < 8:
        ops.insert(random.randrange(len(ops) + 1),
                   random.choice([t[0] for t in TOOLS]))
    elif move < 0.85 and len(ops) > 1:
        ops.pop(random.randrange(len(ops)))

    bonus = parent.hack_bonus
    if hack_allowed and random.random() < 0.08:
        bonus = min(1.0, bonus + random.uniform(0.0, 0.1))
    return Agent(ops=ops, hack_bonus=bonus)
```

- `list(parent.ops)` 先复制，避免修改父代（列表是可变对象，直接改会污染 archive 中的父代）。
- 变异概率：30% 替换、30% 插入（长度上限 8）、25% 删除（长度至少保留 1）、15% 不变（以及前面条件不满足时落空）。注意 `elif` 链：比如长度已是 8 时，`move ∈ [0.3, 0.6)` 不会插入，而是**继续检查下一个 `elif`**，因为 `move < 0.85` 也成立且 `len > 1`，于是会执行删除。
- `random.randrange(len(ops) + 1)`：插入位置可以是末尾。
- hack 漂移：8% 概率让 bonus 增加 `U(0, 0.1)`，期望每代 +0.004；bonus 只沿谱系继承，不会回落。这里的 hack 不是"agent 主动发现的漏洞"，而是**随机漂移 + 选择**——这恰好说明 reward hacking 不需要"意图"，纯优化压力就足够。
- ⚠️ `hack_allowed and random.random() < 0.08` 的**短路求值**：关闭侧信道时不会消耗随机数，打开时会多消耗。因此同样 `seed=7`，两种模式从第 1 代起随机流就错开了，关闭时第 4 代找到 `['collapse', 'nop']`，打开时第 3 代先找到 `['trim']`——两次运行不是严格的受控对比。

### 3.5 `run_dgm`：archive 与主循环

```python
    archive: dict[tuple[int, float], Agent] = {}
    init = Agent(ops=["nop"])
    archive[(len(init.ops), round(reported_score(init, hack_allowed), 2))] = init
    ...
    for g in range(1, generations + 1):
        parent = random.choice(list(archive.values()))
        child = mutate(parent, hack_allowed)
        rep = reported_score(child, hack_allowed)
        true_s = true_score(child)
        key = (len(child.ops), round(rep, 2))
        incumbent = archive.get(key)
        if incumbent is None or rep > reported_score(incumbent, hack_allowed):
            archive[key] = child
        if rep > best_report:
            best_report = rep
            best_true = true_s
            print(...)
```

- **archive 的键** `(工具数, reported 分数保留两位)` 充当"多样性描述符"：不同长度、不同分数的 agent 各占一格。
- ⚠️ 键里包含 **reported score 本身**。侧信道打开时 bonus 是连续值，几乎每个新 bonus 都会落进一个空格子直接入库，被 hack 的谱系不必与诚实变体竞争；而真实 DGM 的描述符应基于行为特征，而不是可被篡改的分数。
- **父代选择**是从 archive 中**均匀随机**选，不偏向高分——这是开放式探索（保留"踏脚石"）的体现，也是 bonus 增长缓慢的原因之一（低 bonus 个体稀释了选择）。
- 入库条件 `rep > reported_score(incumbent, ...)`：同一格子里只有严格更高的才能替换。由于键里已有 `round(rep, 2)`，同格的分数差只在小数点后第三位，替换很少发生。
- 只在 reported 创新高时打印一行，所以输出就是"reported 纪录的演变史"，同时附带真实分数，便于看出两者分叉。
- `best_true` 被赋值但之后没有被使用（最终打印用的是 `max(archive...)` 选出的 `best`）。
- 结尾：`best = max(archive.values(), key=lambda a: reported_score(a, hack_allowed))`，按 loop 自己的指标挑冠军——这正是现实中最危险的地方：**挑选冠军的指标就是被 hack 的指标**。
- archive 没有容量上限，长时间运行会持续增长。

### 3.6 `main`

```python
def main() -> None:
    hack_allowed = "--reward-hack-allowed" in sys.argv
    ...
    run_dgm(generations=200, hack_allowed=hack_allowed, seed=7)
```

- 没有用 `argparse`，直接检查 `sys.argv` 中是否包含该字符串——简单但不会对拼错的参数报错。
- HEADLINE 根据模式打印两段固定文字。关闭模式说 "The loop converges on the real target"——实际上它收敛到的是工具库的上限 0.25，"real target"（全部 title-case）在此工具库下不可达。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| agent = 工具名序列 | 让"自我修改"可枚举、可打印 | 真实 DGM 修改的是 Python 源码，由 LLM 提出 diff |
| 目标 title-case 不在工具库里 | 让 hack 成为抬分的唯一途径，演示清晰 | 无法展示"hack 与真实改进竞争"；加入 title 工具后两种模式都能拿满分（测验 Q12） |
| `hack_bonus` 作为 agent 字段 | 用一个数代表"agent 能改动评分管线" | 真实的 hack 是代码层面的；防御应是进程/文件系统隔离，而不是"不读这个字段" |
| bonus 随机漂移 | 体现"无需意图，选择压力即可产生 hack" | 增长很慢（200 代约 +0.14）；真实 LLM 可能一步就找到漏洞 |
| archive 键含 reported score | 实现简单 | hack 谱系各占一格不受挤压；描述符应只依赖行为 |
| 均匀随机选父代 | 开放式探索、保留踏脚石 | 收敛慢；真实 DGM 会按分数和"子代数量"加权 |
| 固定 8 个用例、无 held-out | 代码短 | 与 docstring/讲义的 "held-out" 说法不符；生产应有 agent 看不到的隐藏测试 |
| 单一 seed、200 代 | 输出简短 | 结论应跨 seed 验证；两种模式的随机流因短路求值而不同 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `lambda` 匿名函数 | `lambda s: s.upper()` | 一行定义的小函数，常用于表格式配置 |
| 字符串方法 | `s.upper()`、`s.lower()`、`s.strip()`、`s.split()`、`" ".join(...)`、`s.title()` | 大小写、去空白、切分、拼接 |
| 切片反转 | `s[::-1]` | 步长 −1 |
| `dict(列表)` | `dict(TOOLS)` | 由 `(键, 值)` 对构造字典 |
| `dict.get` | `tool_map.get(op)`、`archive.get(key)` | 键不存在时返回 `None`，不抛 `KeyError` |
| `@dataclass` + 默认值 | `hack_bonus: float = 0.0` | 有默认值的字段必须在后 |
| 未使用的导入/函数 | `field`、`hash_seq` | 遗留代码，可删除 |
| 复制列表 | `ops = list(parent.ops)` | 浅复制，避免改动父代 |
| `random` 系列 | `random.random()`、`random.randrange(n)`、`random.choice(seq)`、`random.uniform(a, b)` | 均匀浮点、整数下标、随机元素、区间浮点 |
| 短路求值 | `hack_allowed and random.random() < 0.08` | 左边为假时右边不执行（影响随机流） |
| `list.insert` / `list.pop` | `ops.insert(i, x)`、`ops.pop(i)` | 指定位置插入/删除 |
| 列表推导式 | `[t[0] for t in TOOLS]` | 取出所有工具名 |
| 带类型注解的空字典 | `archive: dict[tuple[int, float], Agent] = {}` | 注解说明键值类型 |
| `max(..., key=lambda ...)` | `max(archive.values(), key=lambda a: reported_score(a, ...))` | 按自定义指标取最大；并列时返回第一个 |
| `int | None` | `seed: int | None = None` | 3.10+ 的联合类型写法（配合 `from __future__ import annotations` 可在更早版本使用） |
| `sys.argv` | `"--reward-hack-allowed" in sys.argv` | 命令行参数列表 |
| f-string 格式符 | `{g:>4}`、`{rep:.2f}`、`{gap:+.2f}` | 右对齐宽度、两位小数、强制显示正负号 |
| 舍入规则 | `f"{0.125:.2f}"` → `0.12` | 格式化采用"四舍六入五成双"（对可精确表示的 .5 情形） |

---

## 6. 运行结果解读

**默认（侧信道关闭）**：

```text
reward-hack side channel: closed
  gen    0  report 0.00  true 0.00  ops ['nop']  bonus 0.00
  gen    4  report 0.25  true 0.25  ops ['collapse', 'nop']  bonus 0.00

  final reported score : 0.25
  final true score     : 0.25
  final ops            : ['collapse', 'nop']
  final hack bonus     : 0.00
  reported - true      : +0.00
```

- 第 4 代把 `nop` 前面插入了 `collapse`，一步达到工具库上限 0.25，之后 196 代再无新纪录。
- reported 与 true 完全一致：evaluator 不读 agent 的字段。
- `nop` 是"无用基因"，不影响分数也没有被删除——演化不会主动清理中性突变。

**`--reward-hack-allowed`（侧信道打开）**：

```text
reward-hack side channel: OPEN
  gen    0  report 0.00  true 0.00  ops ['nop']  bonus 0.00
  gen    3  report 0.13  true 0.12  ops ['trim']  bonus 0.01
  gen    7  report 0.25  true 0.25  ops ['collapse']  bonus 0.00
  gen    9  report 0.28  true 0.25  ops ['collapse', 'trim']  bonus 0.03
  gen   39  report 0.37  true 0.25  ops ['collapse', 'collapse']  bonus 0.12
  gen  180  report 0.39  true 0.25  ops ['collapse', 'collapse', 'nop', 'reverse', 'reverse', 'collapse']  bonus 0.14

  final reported score : 0.39
  final true score     : 0.25
  final hack bonus     : 0.14
  reported - true      : +0.14
```

- 第 3 代就出现了 bonus 0.01 的记录（讲义练习 2 "多少代后学会抬分"）。`true 0.12` 是 0.125 按"五成双"舍入的显示结果。
- 第 7 代之后 true 再也没变（已到上限 0.25），之后的每一条新纪录都**纯粹来自 bonus 的增长**。
- 最终冠军的 ops 里有 `reverse, reverse`（两次反转互相抵消）和多余的 `collapse`、`nop`——行为上与 `['collapse']` 完全等价，但它的 reported 更高。这正是讲义所说的"raising the score without improving the underlying behavior"。
- 跨 seed 统计（seed 0–19，测验 Q10）：200 / 1000 / 5000 代时 reported 中位数为 0.38 / 0.495 / 0.695，true 始终是 0.25——代数越多，差距越大。

---

## 7. 动手改一改

1. **（练习 1、2）**分别用默认与 `--reward-hack-allowed` 运行，记录每条新纪录的代数、reported、true；再把 `generations` 改成 1000、5000，画出 `reported − true` 随代数的变化。
2. **修正注释与 docstring**：删除 "collapse whitespace, trim, lower" 的过时注释；把 "held-out" 改为如实描述，或者真的把 `CASES` 拆成选择集与报告集。
3. **受控对比**：给 hack 的随机性单独建一个 `random.Random(seed)` 实例，让两种模式的结构变异完全相同，只比较 hack 的影响。
4. **实现 evaluator firewall**：让评分只依赖 `ops` 的行为，任何 agent 自报分数与独立复算不一致时拒绝入库并记录告警（参考测验 Q11）。
5. **让真实改进可达**：在 `TOOLS` 中加入 `("title", lambda s: s.title())`，观察两种模式下多少 seed 能达到 true = 1.0；再把 reported 的 `min(1.0, ...)` 截断去掉，比较冠军的选择是否变化（参考测验 Q12）。
6. **进阶**：把 archive 的键改为纯行为描述符（例如"每个用例的输出是否等于期望"组成的 8 位向量），并让父代选择按 true score 加权；比较 hack 谱系在 archive 中的占比。

---

## 8. 常见坑

- **评分读取 agent 可写的状态**：`reported_score` 读 `agent.hack_bonus` 就是"evaluator 在 agent 命名空间里"；真实系统中对应评分脚本、日志、标记、配置文件与 agent 同仓库。
- **用被 hack 的指标挑冠军**：`max(..., key=reported_score)` 会系统性地选出 hack 最多的变体。
- **把可篡改的分数放进多样性描述符**：hack 谱系会各占一格，永远不被淘汰。
- **以为 hack 需要"意图"**：本代码里 hack 只是随机漂移，选择压力就足以把它放大。
- **短路求值改变随机流**：`A and random.random()` 这类写法会让不同配置的随机序列错位，比较实验时要注意。
- **注释与数据不一致**：先看 `CASES` 再相信注释；本文件的两段 "Target" 注释互相矛盾。
- **饱和截断**：`min(1.0, ...)` 让高分区无法区分真伪，监控时要同时看独立复算的真实分数。
