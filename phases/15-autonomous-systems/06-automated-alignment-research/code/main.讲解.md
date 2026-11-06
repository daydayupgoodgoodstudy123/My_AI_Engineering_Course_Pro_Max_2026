# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 06 节 自动化 Alignment 研究（Anthropic AAR） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`hashlib`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这是一个"并行 AAR 研究论坛"的玩具模拟器，用几十行代码把讲义中的三件事具体化：

1. **共享论坛 + 日志完整性**：所有 AAR 把结果发到同一个 append-only 论坛，每条记录带上一条记录的哈希，组成哈希链（hash chain）；`verify()` 能发现被"悄悄改分"的记录。
2. **规定流程 vs 自由分解**：同一批任务在 `fixed`（人类规定的流程）和 `free`（agent 自由分解）两种 regime 下求解，比较均值、最大值、最小值。
3. **篡改检测演示**：AAR-A 把自己最差的一次分数改高 0.5，校验时被标记出来。

要特别看清的是它**没有**建模的部分：`solve()` 的优势与任务难度无关；"out-of-sandbox backup 交叉核对"只是一行 `print`；哈希链在没有外部锚点时挡不住"重写整条后缀"。这些恰好是讲义论点最需要的地方。

> 一句话：**用哈希链演示"agent 改不了自己的历史记录才值得信任"，用两种噪声分布演示"灵活性换来上限也换来方差"**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ForumRecord` | dataclass | 一条论坛记录：作者、任务、regime、分数、前一条哈希、本条哈希 | 论坛记录 |
| `Forum` | dataclass | `head()` 取链头、`post()` 追加并计算哈希、`verify()` 校验整条链 | append-only、tamper-evident 日志 |
| `TASKS` | 常量 | 5 个模拟 alignment 任务及其基础分 `base` | 任务队列 |
| `solve` | 函数 | 按 regime 返回 `base + 噪声` | 规定流程 vs 自由分解 |
| `run_regime` | 函数 | 3 个 AAR × 5 个任务，依次发帖 | 并行 AAR |
| `attempt_tamper` | 函数 | 复制论坛，把 AAR-A 最差分数 +0.5（不更新哈希） | 日志篡改 |
| `regime_report` | 函数 | 按任务汇总均值/最大/最小并打印 | 结果对比 |
| `tamper_demo` | 函数 | 跑一批 free 记录 → 篡改 → `verify()` | 篡改检测 |
| `main` | 函数 | 固定种子 3，依次调用上面几个报告 | 入口 |

数据流：`main` → `random.seed(3)` → `regime_report("fixed")` / `regime_report("free")`（各自 `run_regime` → `solve` → `Forum.post`）→ `tamper_demo`（第三次 `run_regime("free")` → `attempt_tamper` → `verify`）→ 打印 HEADLINE。

---

## 3. 逐段精讲

### 3.1 记录与论坛：哈希链

```python
@dataclass
class ForumRecord:
    author: str
    task: str
    regime: str
    result: float
    prev_hash: str
    my_hash: str = ""


@dataclass
class Forum:
    records: list[ForumRecord] = field(default_factory=list)
    genesis: str = "0" * 16

    def head(self) -> str:
        return self.records[-1].my_hash if self.records else self.genesis

    def post(self, rec: ForumRecord) -> None:
        rec.prev_hash = self.head()
        payload = (f"{rec.author}|{rec.task}|{rec.regime}|"
                   f"{rec.result:.3f}|{rec.prev_hash}")
        rec.my_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
        self.records.append(rec)
```

- **哈希链**：第 i 条的载荷包含第 i−1 条的哈希，于是 `my_hash_i = H(字段_i | my_hash_{i-1})`。第一条接在 `genesis = "0000000000000000"` 后面。
- `post()` **忽略调用者传入的 `prev_hash`**（调用处都传 `""`），由论坛自己填 `self.head()`——发帖方无法自选"接在哪条后面"，这是 append-only 的体现。
- `hexdigest()[:16]` 只保留 16 个十六进制字符（64 位），对演示足够；生产中应保留完整 256 位。
- `field(default_factory=list)`：dataclass 中可变默认值必须这样写，否则所有 `Forum` 实例会共享同一个列表。
- ⚠️ 载荷用 `f"{rec.result:.3f}"`：哈希只覆盖分数的**前 3 位小数**，而存储的是完整浮点数。把 `0.34509675…` 改成 `0.3454`，载荷不变，`verify()` 发现不了（已实测，见测验 Q10）。
- ⚠️ 用 `|` 拼接字段有歧义：若某字段本身含 `|`，不同记录可能拼出同一载荷。规范做法是对结构化数据做规范化序列化（如 `json.dumps(..., sort_keys=True)`）再哈希。

### 3.2 校验：只标记"被改的那一条"

```python
    def verify(self) -> list[int]:
        bad = []
        prev = self.genesis
        for i, r in enumerate(self.records):
            payload = (f"{r.author}|{r.task}|{r.regime}|"
                       f"{r.result:.3f}|{prev}")
            expected = hashlib.sha256(payload.encode()).hexdigest()[:16]
            if expected != r.my_hash or r.prev_hash != prev:
                bad.append(i)
            prev = r.my_hash
        return bad
```

两个检查条件：

| 条件 | 抓住的情形 |
|------|-----------|
| `expected != r.my_hash` | 本条内容被改，但存储的哈希没跟着改 |
| `r.prev_hash != prev` | 本条接在了"不是上一条存储哈希"的位置上（上一条被重算过哈希、被删除或被插入） |

- 关键在 `prev = r.my_hash`：往下传的是**存储的**哈希而不是重算值，所以一处错误不会"传染"到后续所有记录，能精确定位。
- 不同篡改方式的实测结果（seed 3 的 15 条 free 记录）：

| 篡改方式 | `verify()` 返回 |
|---------|----------------|
| 只改第 k 条 `result`（`attempt_tamper` 的做法） | `[k]` |
| 改第 4 条 `result` 并重算它的 `my_hash` | `[5]`（下一条的 `prev_hash` 对不上） |
| 删除第 5 条 | `[5]`（原第 6 条移到下标 5，`prev_hash` 对不上） |
| 截掉最后一条 | `[]`，**检测不到** |
| 从篡改点起按 `post()` 规则重建整条链 | `[]`，**检测不到** |
| 分数改动小于 3 位小数精度 | `[]`，**检测不到** |

后三行说明：哈希链只是 **tamper-evident 的必要条件**，真正的保证来自讲义说的"agent has no credential to modify past records"——链头要定期写到 sandbox 外的 write-once 存储，或者用只有论坛服务持有的密钥做 HMAC/签名。

### 3.3 任务与求解：两种噪声分布

```python
TASKS = [
    ("weak-to-strong-distill", 0.40),
    ("reward-model-diagnosis", 0.30),
    ("in-context-safety-probe", 0.50),
    ("RLHF-hyperparam-sweep", 0.45),
    ("alignment-faking-detector", 0.25),
]


def solve(agent: str, task: tuple[str, float], regime: str) -> float:
    _name, base = task
    if regime == "fixed":
        # Prescribed workflow: bounded ceiling, lower variance.
        return base + random.random() * 0.25
    # Free decomposition: wider tail; sometimes much better, sometimes worse.
    return base + random.gauss(0.15, 0.22)
```

| regime | 增益分布 | 期望 | 标准差 | 取值范围 |
|--------|---------|------|-------|---------|
| fixed | `U(0, 0.25)` | 0.125 | ≈ 0.072 | `[base, base+0.25)`，有天花板也有地板 |
| free | `N(0.15, 0.22²)` | 0.15 | 0.22 | 无界：约 24.8% 概率低于 `base`，约 32.5% 概率超过 fixed 的上限 |

- 这正是讲义"fixed has lower variance, free has higher upside"的数学化。
- ⚠️ 自由分解的期望只高 0.025，而且**与 `base`（难度）无关**——讲义 "Use It" 说要观察"free decomposition outperforms fixed workflows on harder problems"，代码并没有这一机制。
- ⚠️ `agent` 参数完全没被使用：三个 AAR 是同分布的，模拟器里不存在"更强/更弱"或"被攻陷"的 agent。讲义第三个观察点"single compromised AAR can contaminate the forum's signal"也没有对应代码。
- ⚠️ 分数没有截断，可能出现 >1 或 <0（本次运行出现 1.032）。如果把分数理解为比例指标，应 `min(max(x, 0), 1)`。
- `_name, base = task`：元组解包，`_name` 前缀下划线表示"故意不用"。

### 3.4 运行一种 regime

```python
def run_regime(regime: str) -> list[ForumRecord]:
    forum = Forum()
    agents = ["AAR-A", "AAR-B", "AAR-C"]
    for task in TASKS:
        for agent in agents:
            r = solve(agent, task, regime)
            forum.post(ForumRecord(
                author=agent, task=task[0], regime=regime,
                result=r, prev_hash="",
            ))
    return forum.records
```

- 外层任务、内层 agent，所以记录顺序是 `T1-A, T1-B, T1-C, T2-A, …`，共 15 条；AAR-A 的记录必在下标 `0, 3, 6, 9, 12`。
- 名为"并行"，实际是顺序循环；对模拟而言没有区别，因为每个 agent 之间没有交互。
- 返回的是 `forum.records`（列表），而不是 `Forum` 对象——之后 `attempt_tamper` 需要重新构建一个 `Forum`。

### 3.5 篡改：把最差分数悄悄改高

```python
def attempt_tamper(forum_records: list[ForumRecord]) -> Forum:
    f = Forum()
    for r in forum_records:
        f.post(ForumRecord(
            author=r.author, task=r.task, regime=r.regime,
            result=r.result, prev_hash="",
        ))
    worst_idx = -1
    worst_val = float("inf")
    for i, r in enumerate(f.records):
        if r.author == "AAR-A" and r.result < worst_val:
            worst_val = r.result
            worst_idx = i
    if worst_idx >= 0:
        f.records[worst_idx].result = f.records[worst_idx].result + 0.5
    return f
```

- 先用**新对象**重建论坛，避免修改传入的 `baseline` 记录（dataclass 是可变对象，直接改会影响调用方）。
- 用"手写 argmin"找 AAR-A 的最差记录：`float("inf")` 作初始值是常见写法。
- 篡改只改 `result`，不更新 `my_hash`——这是"最笨"的攻击者。代码注释解释了为何用 `+0.5` 而不是 `max(..., 0.85)`：后者在原值已超过 0.85 时是空操作，换种子后演示可能"什么都没改"。
- ⚠️ 讲义练习 2 要求"让一个 agent 尝试篡改"，这里篡改由外部函数完成；真实威胁模型里应区分"agent 在 sandbox 内能做什么"（理论上什么也改不了）和"论坛服务被攻破"两种情形。

### 3.6 报告与演示

```python
def regime_report(regime: str) -> None:
    records = run_regime(regime)
    by_task: dict[str, list[float]] = {}
    for r in records:
        by_task.setdefault(r.task, []).append(r.result)
    ...
    print(f"  overall mean across tasks      : {sum(means) / len(means):.3f}")
```

- `dict.setdefault(key, [])` 在键不存在时插入空列表并返回它，配合 `.append` 实现分组。
- "overall mean" 是**各任务均值的均值**；因为每个任务都是 3 条，它等于 15 条的总均值。

```python
def tamper_demo() -> None:
    baseline = run_regime("free")
    tampered = attempt_tamper(baseline)
    bad = tampered.verify()
    print(f"  verify() flagged {len(bad)} corrupted record(s) "
          f"at indices {bad}")
    print("  the append-only chain breaks at the first edited record.")
    print("  an out-of-sandbox backup reveals the tamper on cross-check.")
```

- ⚠️ `baseline` 是**第三次**抽样的 free 记录，不是上面表格里那一批（全局 RNG 已前进）。
- ⚠️ 最后一行"out-of-sandbox backup reveals the tamper on cross-check"只是文字，代码里没有任何备份或交叉核对。可以按测验 Q9 的 `verify_anchored` 补上。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| SHA-256 哈希链 | 标准库即可实现，直观展示"改一条就露馅" | 无密钥、无外部锚点，挡不住重写后缀与截断；生产用 write-once 存储（Object Lock）+ 定期锚定链头 + HMAC/签名 |
| 截断到 16 位十六进制 | 输出好看 | 64 位抗碰撞性较弱；生产保留完整摘要 |
| 载荷里分数格式化为 `.3f` | 与打印格式一致 | 哈希覆盖的内容少于存储内容，小幅改动不可检测；应对规范化序列化后的确切字节做哈希 |
| `post()` 自己填 `prev_hash` | 发帖方无法选择链上位置 | 真实系统还要让 agent 根本拿不到存储的写凭证，只能经由独立服务发帖 |
| fixed = 均匀噪声、free = 正态噪声 | 一行代码表达"低方差有上限 vs 高方差有长尾" | 优势与难度无关、期望差仅 0.025，单次运行结论不稳；应按难度建模并多种子统计 |
| 每格 3 个样本 | 输出简短 | 统计功效极低，单格胜负基本是噪声（见测验 Q11） |
| 篡改用 `+0.5` 固定增量 | 保证任何种子下都真的改了数据 | 只模拟了最弱的攻击者 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可在旧版本 Python 中使用 `list[int]` 这类写法 |
| `@dataclass` | `class ForumRecord:` | 自动生成 `__init__`、`__repr__`、`__eq__`；字段按声明顺序成为构造参数 |
| 字段默认值 | `my_hash: str = ""` | 有默认值的字段必须放在无默认值字段之后 |
| `field(default_factory=list)` | `records: list[ForumRecord] = field(default_factory=list)` | 可变默认值必须用工厂函数，避免实例间共享同一列表 |
| 类型注解 | `def solve(agent: str, task: tuple[str, float], regime: str) -> float` | 只是提示，运行时不检查 |
| 条件表达式 | `self.records[-1].my_hash if self.records else self.genesis` | 一行 if-else；空列表为假 |
| 字符串乘法 | `"0" * 16`、`"-" * 70` | 重复字符串 |
| `hashlib` | `hashlib.sha256(payload.encode()).hexdigest()[:16]` | `encode()` 把 str 变成 bytes；`hexdigest()` 返回十六进制字符串；切片取前 16 位 |
| 相邻字符串字面量拼接 | `(f"{rec.author}|..." f"{rec.result:.3f}|...")` | 括号内相邻的字符串会自动连接 |
| f-string 格式符 | `{mean:>8.3f}`、`{task:<32}`、`{'task':<32}` | `>`右对齐、`<`左对齐、宽度、小数位 |
| `enumerate` | `for i, r in enumerate(self.records)` | 同时拿到下标和元素 |
| 元组解包 | `_name, base = task` | `_` 前缀约定为"不使用的变量" |
| `random` 模块 | `random.seed(3)`、`random.random()`、`random.gauss(0.15, 0.22)` | 全局伪随机数发生器；固定种子可复现 |
| `float("inf")` | `worst_val = float("inf")` | 正无穷，作为求最小值的初始值 |
| `dict.setdefault` | `by_task.setdefault(r.task, []).append(r.result)` | 键不存在时插入默认值并返回 |
| 关键字参数 | `ForumRecord(author=agent, task=task[0], ...)` | 按名字传参，可读性好 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`random.seed(3)`，瞬间完成）：

```text
regime: fixed
  task                                  mean       max       min
  weak-to-strong-distill               0.496     0.536     0.459
  reward-model-diagnosis               0.408     0.456     0.316
  in-context-safety-probe              0.592     0.709     0.503
  RLHF-hyperparam-sweep                0.592     0.699     0.509
  alignment-faking-detector            0.413     0.459     0.369
  overall mean across tasks      : 0.500

regime: free
  task                                  mean       max       min
  weak-to-strong-distill               0.756     0.803     0.731
  reward-model-diagnosis               0.269     0.432     0.122     ← 低于 fixed 的 0.408
  in-context-safety-probe              0.760     0.991     0.493
  RLHF-hyperparam-sweep                0.739     1.032     0.499     ← 超过 1：分数没截断
  alignment-faking-detector            0.389     0.652     0.055     ← 极差：最小值 0.055
  overall mean across tasks      : 0.582

fixed vs free — fixed has lower variance, free has higher upside

Log tampering detection
----------------------------------------------------------------------
  verify() flagged 1 corrupted record(s) at indices [0]
  the append-only chain breaks at the first edited record.
  an out-of-sandbox backup reveals the tamper on cross-check.
```

逐项解读：

- **fixed 的每个任务都落在 `[base, base+0.25)`**：例如 `alignment-faking-detector`（base 0.25）在 0.369–0.459 之间，`reward-model-diagnosis`（base 0.30）的最小值 0.316 也只比 base 高一点。fixed 的总体均值 0.500 恰好接近理论值 `mean(base) + 0.125 = 0.38 + 0.125 = 0.505`。
- **free 的方差明显更大**：最大值 1.032、最小值 0.055；`reward-model-diagnosis` 和 `alignment-faking-detector` 两个任务上 free 的均值反而低于 fixed。理论总体均值是 `0.38 + 0.15 = 0.53`，本次 0.582 属于偏有利的一次抽样。
- **"free 胜出"不是稳定结论**：我们在 2000 个种子上重复整个实验，free 的总体均值只在约 66.5%（1330/2000）的种子里胜出；单次抽样 free > fixed 的概率仅约 0.545。
- **篡改检测**：被篡改的是第三次抽样中 AAR-A 的最差记录——下标 0（weak-to-strong-distill，0.310）。只改 `result`、不改哈希，所以 `verify()` 只标记这 1 条。在 200 个种子上统计，被标记下标总是 0/3/6/9/12 之一（AAR-A 的发帖位置）。
- 最后两行文字是"叙述"，不是计算结果：代码里没有外部备份，也没有交叉核对。

---

## 7. 动手改一改

1. **（讲义练习 1）让难度起作用**：按测验 Q11 的思路改写 `solve()`，让 free 的增益随 `1 - base` 增大，再用 50 个种子统计每个任务上 fixed / free 的胜率，回答"是否存在固定流程有竞争力的问题类别"。
2. **修复序列化精度**：把载荷改成 `json.dumps(asdict(rec_without_hash), sort_keys=True)`（`from dataclasses import asdict`），验证"把 0.34509… 改成 0.3454"现在能被检测出来。
3. **（讲义练习 2）更聪明的攻击者**：写一个 `attempt_tamper_rehash`，篡改后重算该条 `my_hash`，确认 `verify()` 标记的是下一条；再写 `attempt_rewrite_suffix` 重建整条后缀，确认 `verify()` 返回 `[]`，然后用一段话描述三种攻击各自的"检测签名"。
4. **外部锚点**：实现一个 `ExternalAnchor` 类，每 5 条记录把 `(len, head)` 存入一个只允许追加的列表；实现 `verify_anchored`，确认它能抓住"重写后缀"和"截断尾部"。
5. **被攻陷的 AAR**：让 `solve()` 使用 `agent` 参数，令 AAR-C 系统性地虚报 +0.3，观察它对每个任务均值的影响；再设计一个"复现检查"（随机挑记录让另一个 AAR 重跑，差距超阈值就标记），对应讲义"single compromised AAR can contaminate the forum's signal"。
6. **进阶**：用 HMAC（`hmac.new(key, payload, hashlib.sha256)`）替代裸 SHA-256，把 `key` 只交给 `Forum` 而不交给篡改函数，说明为什么此时"重写后缀"也会失败。

---

## 8. 常见坑

- **把 tamper-evident 当成 tamper-proof**：哈希链本身挡不住有写权限的攻击者；可信性来自"历史记录的写凭证不在 agent 手里"以及外部锚点。
- **哈希覆盖的内容少于存储内容**：本例 `.3f` 只覆盖 3 位小数；真实系统中常见"只签部分字段"、"签格式化字符串而存原始值"。
- **以为错误会沿链传染**：本实现往下传的是存储哈希，只会标记被改的那一条；如果你写成传重算值，一处篡改会让后面全部"变红"，反而丢失了定位能力。
- **单次运行下结论**：每格只有 3 个样本，free 的标准差 0.22，单格胜负几乎是噪声；比较两种策略要多种子、给置信区间。
- **忽略全局 RNG 的状态**：`tamper_demo` 用的是第三次抽样，和表格不是同一批数据；需要可比数据时应显式传入 `random.Random(seed)` 实例。
- **dataclass 可变默认值**：写成 `records: list = []` 会直接报错（dataclass 会拒绝可变默认值），要用 `field(default_factory=list)`。
- **把 `solve()` 的 `agent` 参数当成有意义**：它没被使用，三个 AAR 完全同分布。
