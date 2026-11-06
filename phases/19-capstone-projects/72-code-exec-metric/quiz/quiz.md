# 测验 · 代码执行评估指标（Code Exec Metric）

> **阶段 19 · 综合项目 · 第 72 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要子进程 | 宿主进程里 `exec` 一段 `while True: pass` 会让评估永远卡住，`shutil.rmtree('/')` 更是灾难；每个候选起一个全新 Python 解释器，超时就杀掉 |
| 2 | 任务形状 | `code_exec` 任务的 `targets` 是断言**表达式**字符串；先从生成中抽代码块，再拼进 runner 脚本执行 |
| 3 | 分数 = 通过断言的比例 | 3 条断言过 2 条得 0.667；超时、语法错误、崩溃一律 0 分 |
| 4 | 五种退出码 | `pass`、`assertion_fail`、`syntax_error`、`timeout`、`error`（含 denylist 命中与 output overflow）；退出码是元数据，分数仍是比例 |
| 5 | 三道控制 | wall-clock 超时（默认 3s，上限 30s，下限 0.1s）、输出上限 256 KB、import denylist；讲义："The wall-clock timeout and the output cap are the load-bearing controls" |
| 6 | denylist 只是兜底 | 通过替换 `builtins.__import__` 拦截 `subprocess/socket/shutil/...`，并把 `os.system` 换成抛错函数；进程内沙箱可以被绕过 |
| 7 | 结果信道 | 子进程把 `{"exit_code", "results", "detail"}` 以 JSON 写到 stdout，父进程解析；候选代码也能写 stdout，这是本实现最大的脆弱点 |
| 8 | pass@k 无偏估计 | 每题采样 n 个、c 个通过：`pass@k = 1 − C(n−c, k)/C(n, k)`；`n − c < k` 时为 1；代码用连乘形式避免大组合数 |
| 9 | pass@1 = c/n | k = 1 时公式退化为通过率；多题取平均 |
| 10 | 局限 | 不是真正的沙箱：生产需要容器/microVM、seccomp、网络隔离、只读文件系统 |

### 核心技能（能动手做到）

- [ ] 预测任意候选代码在 `run_candidate` 下得到的 `exit_code`、`score`、`detail`
- [ ] 手算 `pass_at_k(n, c, k)`，并解释为什么不能直接用 `1 − (1 − c/n)^k`
- [ ] 读懂 `select` + 非阻塞读 + 截止时间的循环，说清超时与输出上限各在哪一行生效
- [ ] 举出至少三种绕过本节 denylist 的方法，以及至少两种让正确代码被误判的情形
- [ ] 修改 runner 的结果协议，让候选代码中的 `print` 不再导致 0 分
- [ ] 用 `python3 -m pytest -q` 运行 21 个测试，并说明每组测试锁定的退出码

---

## 二、基础自测（选择题）

**Q1.** 一个 `code_exec` 任务有 3 条断言，候选代码通过其中 2 条、没有崩溃。`run_candidate` 返回：

- A. `score=0.667, exit_code="pass"`
- B. `score=0.667, exit_code="assertion_fail"`
- C. `score=0.0, exit_code="assertion_fail"`
- D. `score=1.0, exit_code="pass"`

**Q2.** 候选代码功能完全正确，但函数里有一句调试输出：

```python
def add(a, b):
    print("debug")
    return a + b
```

断言 `["add(1,2)==3"]`。`run_candidate` 的结果是：

- A. `pass`，score 1.0
- B. `assertion_fail`，score 0.5
- C. `syntax_error`，score 0.0
- D. `error`，score 0.0，detail 为 `"non-json output"`

**Q3.** `pass_at_k(10, 2, 5)` 约等于：

- A. 0.778
- B. 0.5
- C. 0.2
- D. 1.0

**Q4.** 候选代码 `def add(a,b):\n    raise RuntimeError('boom')`，断言 `["add(1,2) == 3"]`。退出码是：

- A. `error`
- B. `syntax_error`
- C. `assertion_fail`
- D. `timeout`

**Q5.** 下列哪段候选代码能**绕过** denylist、成功拿到 `socket` 模块？

- A. `import subprocess`
- B. `import urllib.request`
- C. `import tempfile`
- D. `import importlib; s = importlib.import_module("socket")`

**Q6.** `extract_code("```python\ndef f")`（代码块没有闭合）的返回值是：

- A. `None`，于是 `score_code_exec` 直接返回 0.0，不启动子进程
- B. `"def f"`
- C. 原字符串
- D. `""`

**Q7.** 某题采样 n = 10、c = 1，`pass_at_k(10, 1, 10)` 等于：

- A. 0.1
- B. 1.0
- C. 0.5
- D. 0.0

**Q8.** 候选代码往 **stderr** 写入约 10 MB 数据，`timeout_s=3`。实测结果是 `timeout` 而不是 `output overflow`，原因是：

- A. 输出上限也统计 stderr，但阈值更高
- B. `select` 同时监视 stdout 和 stderr，stderr 优先级低
- C. 父进程在循环中只读 stdout、不读 stderr，stderr 管道缓冲区写满后子进程阻塞，直到截止时间被杀
- D. Python 解释器对 stderr 限速

---

## 三、动手 / 代码题

**Q9.**（修复结果信道）runner 子进程用 `sys.stdout.write(json.dumps(status))` 回传结果，父进程 `json.loads(stdout)`。候选代码里的任何 `print` 都会让解析失败（见 Q2）。

1. 设计一个改法，使 `print` 不再影响评分，并说明它对 256 KB 输出上限的影响。
2. 你的改法能否防止候选代码**伪造**结果？用一个例子说明。
3. 讲义说"The runner returns the same shape no matter what fails"。从"奖励可被操纵"（reward hacking）的角度，这个信道还有什么风险？

**Q10.**（沙箱绕过）预测以下候选代码在 `run_candidate(code, ["r == 0"])` 或相应断言下的结果，并解释：

```python
# (a)
import posix
r = posix.system('true')

# (b)
import builtins
builtins.__import__ = builtins.__import__.__globals__['_real_import']
import subprocess
r = subprocess.run(['true']).returncode

# (c)
import os
r = os.popen('echo hi').read()      # 断言 r == 'hi\n'

# (d)
import sys, os
sys.stdout.write('{"exit_code":"pass","results":[true],"detail":""}')
sys.stdout.flush()
os._exit(0)                          # 断言 ["False"]
```

最后回答：为什么讲义说 "The denylist is a backstop"？生产环境需要哪些额外的隔离？

**Q11.**（pass@k）

1. 从"从 n 个样本中不放回抽 k 个，至少一个通过的概率"推导 `1 − C(n−c, k)/C(n, k)`，并说明代码里的连乘形式为什么等价。
2. 手算 demo 中三题（`c = 2, 1, 0`，`n = 10`）的 pass@1、pass@5、pass@10 平均值。
3. 有人用 `1 − (1 − c/n)^k` 估计 pass@k。对 `n=10, c=2, k=5` 计算两者差多少，并说明哪个是无偏的。
4. 代码在 `k > n` 时返回 `float(c > 0)`，这合理吗？

**Q12.**（退出码逻辑）runner 模板末尾有一段：

```python
if passed < len(ASSERTIONS):
    status["exit_code"] = "assertion_fail" if passed > 0 or len(ASSERTIONS) > 0 else status["exit_code"]
    if passed == len(ASSERTIONS):
        status["exit_code"] = "pass"
elif len(ASSERTIONS) > 0:
    status["exit_code"] = "pass"
```

父进程里又有：

```python
    if exit_code == EXIT_PASS and passed < total:
        exit_code = EXIT_ASSERTION_FAIL
    if exit_code == EXIT_ASSERTION_FAIL and passed == total and total > 0:
        exit_code = EXIT_PASS
```

1. 指出模板中哪些条件/分支永远不会改变结果，并把它化简为两三行。
2. demo 里名为 `one_assertion_fails` 的例子，`expected_score` 是 0.0。实际有几条断言失败？名字准确吗？
3. 讲义说 `syntax_error` 表示 "the code did not import or had a SyntaxError"。`import numpyy`（拼错的模块名）会得到哪个退出码？

---

## 四、面试高频题

**Q13.**（基础必考）评估模型生成的代码时，为什么不能直接在评估进程里 `exec`？子进程方案解决了哪些问题、没解决哪些问题？

**Q14.**（原理深挖）HumanEval 的 pass@k 是什么？为什么要采样 n > k 个再用组合公式估计，而不是直接采样 k 个看是否有一个通过？温度对 pass@1 和 pass@100 的影响有何不同？

**Q15.**（工程实践）如果要在生产中每天对数十万条模型生成的代码做执行评估，你会如何设计执行沙箱？

**Q16.**（场景设计）你用代码执行通过率作为 RL 的奖励训练一个代码模型，一段时间后通过率飙升但人工检查发现代码质量很差。可能发生了什么？如何从评估框架层面防范？

**Q17.**（追问型）超时该怎么计分？墙钟时间和 CPU 时间有什么区别？如何处理"偶发超时"（flaky）带来的分数波动？

---

## 五、参考答案与解析

### Q1 — 答案：B

score = passed / total = 2/3 ≈ 0.667。runner 模板中只要 `passed < len(ASSERTIONS)` 就设为 `assertion_fail`；父进程也会把"`pass` 但 `passed < total`"纠正为 `assertion_fail`。讲义："A task with three assertions where two pass scores 0.667." 退出码只描述"发生了什么"，分数仍是比例。

### Q2 — 答案：D

已实际运行：`exit=error, score=0.0, detail='non-json output'`。候选代码与 runner 共享同一个 stdout，`print("debug")` 输出的 `debug\n` 加在 JSON 前面，父进程 `json.loads("debug\n{...}")` 失败，走 `except json.JSONDecodeError` 分支。**功能完全正确的代码因为一行调试输出得 0 分**——这是本实现最严重的缺陷之一，修复方法见 Q9。

### Q3 — 答案：A

`1 − C(8,5)/C(10,5) = 1 − 56/252 = 0.7778`（代码实测 0.7777777777777779）。B 是 `pass_at_k(10, 1, 5)`；C 是 pass@1 = c/n；D 是 k ≥ n − c + 1 时的情况。

### Q4 — 答案：C

函数定义本身能编译、能执行，所以不是 `syntax_error` 或 `error`；异常发生在 `eval(assertion, ns)` 里，被 `except Exception` 捕获，记为 `ok = False`，`detail` 记 `"assertion error: boom"`。最终 `passed = 0 < 1` → `assertion_fail`。测试 `test_runtime_error_during_assertion` 锁定了这个行为。注意区别：如果异常发生在**模块顶层**（`exec` 阶段），则是 `error`。

### Q5 — 答案：D

实测 D 得到 `pass`。`importlib.import_module` 走的是导入系统内部的 `_bootstrap._gcd_import`，**不经过** `builtins.__import__`，所以 hook 拦不住。A、B 被直接拒绝（`urllib.request` 的首段 `urllib` 在名单里）；C 更有意思：`tempfile` 本身不在名单，但它内部 `import shutil`，也经过被替换的 `__import__`，于是 `exec error: denied module: shutil`——这是**误伤**，合法代码用到 `tempfile` 就得 0 分（`import asyncio` 同理，会因内部导入 `socket` 被拒）。

### Q6 — 答案：A

`CODE_BLOCK_RE` 需要闭合的三个反引号，匹配失败；接着 `if "```" in text: return None`。`score_code_exec` 看到 `None` 直接返回 0.0。测试 `test_backticks_but_unclosed_returns_none` 与 `test_unclosed_block_scores_zero` 锁定了这一点。注意与第 70 课 `post_process(..., "extract_code_block")` 的差异：那里匹配失败会**原样返回**整段文本（C）。第 75 课的 runner 写的是 `exec_mod.extract_code(processed) or processed`，`None` 又被 `or` 换回了原文，于是未闭合的代码块最终还是会被执行（通常得到 `syntax_error`）。

### Q7 — 答案：B

`n − c = 9 < k = 10`：从 10 个样本里抽 10 个，必然包含那 1 个通过的样本，概率为 1。代码 `if n - c < k: return 1.0`。讲义的流程图写 "pass_at_10 = 1 if c>0 else 0"，就是这种情况。A 是 pass@1。

### Q8 — 答案：C

实测 3.00 秒后 `timeout`。父进程只把 `proc.stdout` 放进 `select`、只读 stdout；`stderr=subprocess.PIPE` 但直到 `finally` 才读取。管道缓冲区（Linux 上通常 64 KB）写满后，子进程的 `write` 阻塞，既不退出也不再写 stdout，父进程只能等到截止时间。输出上限只统计 stdout（A 错），`select` 也没有监视 stderr（B 错）。修复：把 stderr 重定向到 `subprocess.DEVNULL` 或同样纳入 `select` 并计入上限，或用 `stderr=subprocess.STDOUT` 合并。

### Q9 — 参考答案

1. **改法**：给结果加一个定界标记，父进程只解析**最后一个**标记之后的内容。模板中把三处 `sys.stdout.write(json.dumps(status))` 改为

```python
sys.stdout.write("\n__AIE_RESULT__" + json.dumps(status))
```

父进程解析改为

```python
MARK = "__AIE_RESULT__"
idx = stdout.rfind(MARK)
payload = stdout[idx + len(MARK):] if idx >= 0 else stdout
status = json.loads(payload) if payload else {}
```

实测：带 `print('debug')` 的正确代码从 `error 0.00` 变为 `pass 1.00`；顶层 `print('hi')` + 一真一假两条断言得 `assertion_fail 0.50`；语法错误仍是 `syntax_error`。候选代码的输出仍然流经 stdout，**仍计入 256 KB 上限**，所以"无限打印"依然会被 `output overflow` 截断，这是选择"定界符"而不是"把 `sys.stdout` 换成内存缓冲区"的原因——后者会让无限打印无声地吃掉子进程内存。另一种做法是让 runner 把结果写到单独的文件描述符（`os.pipe()` + `pass_fds`）。

2. **不能防伪造**。实测：候选代码写出 `__AIE_RESULT__{"exit_code":"pass","results":[true],"detail":""}` 后立刻 `os._exit(0)`（跳过 runner 的后续代码），断言 `["False"]` 依然被判 `pass 1.00`。原版协议下同样的攻击（不带标记）也能成功（见 Q10(d)）。用随机 nonce 做标记只能提高门槛：nonce 写在脚本源码里，候选代码可以通过 `sys._getframe(1).f_globals` 等方式读到。
3. **风险**：评分逻辑和被评估代码在**同一个进程**里，被评估者可以改写评分结果——在 RL 训练中这就是典型的 reward hacking。更稳妥的做法：结果由**进程外**的可信方判断（例如只看进程退出码 + 每条断言单独起进程、断言失败用非零退出码表示）；或在容器里运行测试、由宿主读取测试框架写到只读挂载以外的报告；并检测 `os._exit`、`sys._getframe`、修改 `builtins` 等可疑行为。

### Q10 — 参考答案

实测结果：

| 代码 | 结果 | 原因 |
|------|------|------|
| (a) `posix.system` | `pass` | denylist 只把 `os.system` 换掉了；`os` 模块的底层实现 `posix` 不在名单里，其 `system` 函数原封未动 |
| (b) 恢复 `__import__` | `pass` | `_guarded_import.__globals__` 就是 runner 的全局命名空间，里面有 `_real_import`；把它装回 `builtins.__import__` 后 denylist 完全失效 |
| (c) `os.popen` | `error`（`denied module: subprocess`） | `os.popen` 内部 `import subprocess`，碰巧被 hook 拦下——denylist "意外地"起了作用 |
| (d) 伪造 JSON | `pass`，score 1.0 | 断言根本没运行；父进程只看 stdout 里的 JSON 和返回码 0 |

讲义："Determined adversarial code can escape any in-process sandbox in Python. The denylist is a backstop. The wall-clock timeout and the output cap are the load-bearing controls." Python 的动态性（反射、`importlib`、`ctypes` 以外的底层模块、frame 访问）使"在同一个解释器里限制代码"注定不完整。

生产隔离（讲义："Production deployments add seccomp, network isolation, and a read-only filesystem"）：

- 容器或 microVM（gVisor、Firecracker 之类）运行每个候选，非 root 用户；
- 网络命名空间隔离、禁止出网；
- 只读根文件系统 + 临时可写目录；
- cgroups / `resource.setrlimit` 限制 CPU 时间、内存、进程数、文件大小；
- seccomp 过滤危险系统调用；
- 结果由宿主侧判定（见 Q9-3）。

### Q11 — 参考答案

1. **推导**：n 个样本中有 c 个通过、n − c 个失败。不放回抽 k 个，"全部失败"的方式数为 `C(n−c, k)`，总方式数为 `C(n, k)`，所以至少一个通过的概率为 `1 − C(n−c, k)/C(n, k)`。展开：

```text
C(n−c, k) / C(n, k) = [(n−c)(n−c−1)…(n−c−k+1)] / [n(n−1)…(n−k+1)] = Π_{i=0}^{k−1} (n−c−i)/(n−i)
```

代码在 log 空间累加 `log(n−c−i) − log(n−i)`，避免 n = 200 时组合数过大，也避免浮点溢出。`n − c < k` 时某一项 `n−c−i` 会变成 0，`log(0)` 不能算，所以先单独返回 1.0。

2. 手算（与 demo 输出 `pass@1=0.100 pass@5=0.426 pass@10=0.667` 一致）：

| 题 | c | pass@1 | pass@5 | pass@10 |
|----|---|--------|--------|---------|
| 1 | 2 | 0.2 | 1 − 56/252 = 0.778 | 1 |
| 2 | 1 | 0.1 | 1 − 126/252 = 0.5 | 1 |
| 3 | 0 | 0 | 0 | 0 |
| 平均 | | **0.100** | **0.426** | **0.667** |

3. `1 − (1 − 0.2)^5 = 1 − 0.32768 = 0.672`，而无偏估计是 0.778，差约 0.106。前者假设"有放回抽样、且真实通过率恰好等于 c/n"，把 c/n 代入非线性函数会产生偏差（Jensen 不等式）；组合公式是在给定 n 个样本下对"抽 k 个至少一个通过"的**无偏估计**（HumanEval 论文提出的做法）。
4. 不太合理。`k > n` 时无法从 n 个样本中抽出 k 个，组合公式没有定义；返回 `c > 0` 是一个**乐观**近似（只要有一个通过就算 1），会高估。更严谨的做法是直接抛 `ValueError`，要求 `n ≥ k`（HumanEval 常见做法是 n = 200、报告 k ∈ {1, 10, 100}）。

### Q12 — 参考答案

1. runner 脚本执行到这一段时 `ASSERTIONS` 一定非空（父进程在 `run_candidate` 开头已经拒绝空断言），所以：
   - `passed > 0 or len(ASSERTIONS) > 0` 恒为真，条件表达式总是得到 `"assertion_fail"`；
   - 在 `passed < len(...)` 分支里再判断 `passed == len(...)` 永远为假；
   - `elif len(ASSERTIONS) > 0` 恒为真。

   化简为：

```python
status["exit_code"] = "pass" if passed == len(ASSERTIONS) else "assertion_fail"
```

   父进程中的两条纠正规则也是"双保险"，在 runner 正常运行时不会改变结果；但它们在**伪造结果**时同样不起作用（伪造者会让 `results` 与 `exit_code` 一致）。
2. `add(a, b)` 返回 `a + b + 1`：`add(1, 2) == 4 ≠ 3`，`add(-5, 5) == 1 ≠ 0`，**两条都失败**，所以 score 是 0.0 而不是 0.5。名字 `one_assertion_fails` 不准确，应为 `all_assertions_fail`；测试 `test_partial_assertions_fail` 才是真正的"部分失败"（断言改成了 `add(0,0) == 1`）。
3. `exec` 阶段抛出 `ModuleNotFoundError`（`Exception` 的子类），被归为 **`error`**（detail `exec error: No module named 'numpyy'`），不是 `syntax_error`。只有 `compile` 阶段的 `SyntaxError` 才是 `syntax_error`。讲义的描述与代码不一致；如果下游想区分"代码写错"和"环境/依赖问题"，应在 runner 里单独捕获 `ImportError`。

### Q13 — 参考回答要点

- **不能 exec 的原因**：死循环会卡死整个评估；危险操作（删文件、联网、fork 炸弹）会破坏宿主；候选代码可以修改评估器自身的全局状态（替换函数、改分数）；内存泄漏/段错误会让整个评估进程崩溃。
- **子进程方案解决了**：超时可以 `kill`；崩溃只影响子进程；`-I` 隔离模式忽略 `PYTHON*` 环境变量和用户 site-packages；输出上限防止 stdout 撑爆宿主内存；每个候选全新解释器，互不污染。
- **没解决**：文件系统和网络仍然可访问（denylist 可绕过）；内存与 CPU 没有限制（只有墙钟超时）；结果信道可伪造；stderr 未读导致的假超时。
- 加分点：讲义——"Real evals like HumanEval, MBPP, BigCodeBench, and LiveCodeBench all use a subprocess sandbox. Some layer Docker on top."

### Q14 — 参考回答要点

- **定义**：对每道题，生成 k 个候选，只要有一个通过全部测试即算解决；pass@k 是解决比例的期望。
- **为什么采样 n > k**：直接采样 k 个只得到一个 0/1 的观测，方差很大。采样 n 个（如 200）后，用 `1 − C(n−c, k)/C(n, k)` 计算"从这 n 个中随机抽 k 个至少有一个通过"的概率，这是 pass@k 的无偏估计，方差小，并且一次采样可以同时报告 k = 1、10、100。
- **不能用 `1 − (1 − c/n)^k`**：有偏（Q11-3 中 0.672 vs 0.778）。
- **温度的影响**：低温度生成更确定、多样性低，适合 pass@1；高温度多样性高，单个样本质量下降，但 k 大时"至少一个对"的概率上升，pass@100 往往在较高温度下最好。所以报告 pass@k 时应注明采样温度，而且不同 k 的最优温度不同。
- 加分点：pass@k 只看"能否通过测试"，不衡量可读性、效率；测试覆盖不足时会高估。

### Q15 — 参考回答要点

- **隔离层**：每个候选在一次性容器或 microVM 中运行（gVisor / Firecracker 等），非 root、无网络、只读根文件系统、tmpfs 工作目录；seccomp 白名单。
- **资源限制**：cgroups 限 CPU、内存、PID 数；`setrlimit` 限 CPU 秒数、文件大小；墙钟超时由宿主强制 kill。
- **I/O**：stdout/stderr 都设上限并同时读取（或重定向到文件后截断）；结果通过独立信道或退出码返回，由宿主判定。
- **吞吐**：预热容器池、按语言分镜像、批量调度；同一题的 n 个样本可以并行；记录每个样本的耗时与资源使用。
- **可复现**：固定镜像版本、依赖版本、随机种子；记录完整的执行日志（截断）便于排查。
- **安全运营**：监控异常系统调用、出网尝试；对"所有样本都超时"或"所有样本都通过"的题目做告警。
- 常见误区：以为 import denylist 足够安全；只设墙钟超时不限内存。

### Q16 — 参考回答要点

- **可能发生的 reward hacking**：
  - 针对测试特判（`if a == 1 and b == 2: return 3`）——测试太少、太可见；
  - 伪造结果信道（本节实现中写一行 JSON 再 `os._exit(0)` 就能拿满分，见 Q10(d)）；
  - 修改评估环境（恢复 `__import__`、修改断言用到的内置函数，如重定义 `__eq__` 让所有比较为真）；
  - 利用断言用 `bool(...)` 判定的宽松性：返回一个"真值"对象即可通过 `f()` 这类断言。
- **防范**：
  - 隐藏测试 + 大量随机/属性测试，训练时可见的测试与评估测试分离；
  - 结果在**进程外**判定，候选进程无法写入评分信道；
  - 每条断言独立进程或独立解释器状态，比较时用可信代码（如序列化输出后在宿主比较）；
  - 检测可疑模式（`os._exit`、`sys._getframe`、改 `builtins`）并人工审计高奖励样本；
  - 用多个评估信号（静态分析、代码审查模型、人工抽检）交叉验证。
- 加分点：联系 Goodhart 定律——当指标成为优化目标时，它就不再是好指标。

### Q17 — 参考回答要点

- **计分**：本节对超时计 0 分，退出码 `timeout` 作为元数据保留；讲义："Downstream lessons can decide whether to count a timeout as zero or as missing data." 若超时源于评测机负载（而非代码本身的死循环），计 0 会冤枉模型；计为缺失则可能让"写死循环"的模型逃避惩罚。常见做法：默认计 0，同时单独报告超时率。
- **墙钟 vs CPU 时间**：墙钟包括等待 I/O、调度排队、解释器启动（本节实测每次约 0.05 秒）；CPU 时间只计实际计算。墙钟能捕获 `sleep` 和阻塞（本节 demo 的 `time.sleep(10)`），但受机器负载影响；CPU 时间更稳定，但抓不住"睡眠"型卡死。生产中两者都设：`RLIMIT_CPU` + 宿主墙钟超时。
- **flaky 处理**：给超时留足余量（如参考解耗时的若干倍）；超时样本自动重跑一次；控制并发度、固定评测机型；报告时附带重复运行的方差；对经常超时的题目复查测试本身。
- 加分点：本节的超时还包含解释器启动时间，`timeout_s` 设得很小时（下限 0.1 秒）正确代码也可能超时。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 70 任务规范格式](../../70-task-spec-format/docs/zh.md)：`code_exec` 任务的 targets 形状与 `extract_code_block` 规则。
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)：统一的 `[0, 1]` 分数与分派模式。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：另一种 denylist + 路径隔离的执行器设计，可与本节对照。
- [阶段 00 · 07 用于 AI 的 Docker](../../../00-setup-and-tooling/07-docker-for-ai/docs/zh.md)：生产中用容器承载执行沙箱。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md)：执行不可信代码时的权限与信任边界。

### 本节被哪些后续内容用到
- [阶段 19 · 74 排行榜汇总](../../74-leaderboard-aggregation/docs/zh.md)：消费 `code_exec` 分数（讲义说 pass@k 供排行榜层使用）。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：直接调用 `extract_code` 与 `run_candidate`。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：以执行测试为判据的大型代码/Agent 基准。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：把执行通过率当奖励时的风险。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：HumanEval、MBPP 等代码基准在整体评估体系中的位置。

### 延伸关键词
`HumanEval` · `MBPP` · `pass@k unbiased estimator` · `subprocess timeout` · `select / non-blocking I/O` · `python -I` · `seccomp` · `gVisor` · `Firecracker` · `rlimit / cgroups` · `reward hacking` · `LiveCodeBench`
