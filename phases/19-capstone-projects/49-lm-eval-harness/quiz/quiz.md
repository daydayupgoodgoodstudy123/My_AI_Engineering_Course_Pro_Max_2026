# 测验 · 语言模型 Evaluation Harness（Language Model Evaluation Harness）

> **阶段 19 · 综合项目 · 第 49 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Harness 的四个部件 | 任务定义（JSONL）+ 指标（metric）+ 运行器（runner）+ 排行榜（leaderboard JSON）；换模型只换 adapter |
| 2 | 任务格式 | 每行一个样例：`id`、`prompt`、`targets`、`metric`，可选 `extras`；文件名即任务名，同一文件共用一个 metric |
| 3 | 指标契约 | `(prediction, targets, extras) → [0, 1] 的浮点数`；样例分取平均得任务分，任务分再取平均得总分 |
| 4 | 五个指标 | `exact_match`（小写+压空白后相等）、`substring_contains`（包含）、`multiple_choice`（首字符）、`rouge_l`（LCS 的 F1）、`code_exec`（执行函数比对 IO 对） |
| 5 | ROUGE-L | `P = LCS/len(pred)`，`R = LCS/len(ref)`，`F1 = 2PR/(P+R)`；只看词序上的最长公共子序列，多个参考取最大 |
| 6 | Adapter 是唯一的接缝 | `ModelAdapter` 是 `Protocol`：只要有 `generate(prompts) -> list[str]` 和 `name`；Toy、HTTP、本地推理、测试桩可以任意替换 |
| 7 | 运行器 | 按 `batch_size` 分批调 adapter，校验输出条数，逐样例打分，记录延迟；`--include-per-example` 保存每条预测便于 diff |
| 8 | 总分是宏平均 | `overall = mean(task scores)`，每个任务权重相同，与样例数无关 |
| 9 | 指标的可被钻空子 | 首字母选择题、子串包含、去掉 builtins 的 `exec` 都很脆弱：常数答案、回声（echo）答案、内省逃逸都能拿分或越权 |
| 10 | 可复现三原则 | 讲义：固定任务文件（sha256）、diff 预测而不只是分数、限制 batch 大小以兼容各家速率限制 |

### 核心技能（能动手做到）

- [ ] 读写 JSONL 任务文件，跳过注释与空行，在 JSON 出错时报出文件名与行号
- [ ] 手算 ROUGE-L（用 LCS 的动态规划）和 exact match / substring / multiple choice 的分数
- [ ] 写一个新的 adapter（HTTP 或桩）接入 `run_leaderboard`，不改其他任何代码
- [ ] 用"常数答案"和"回声答案"两种基线检查任务集是否太容易被钻空子
- [ ] 说清 `code_exec` 的"受限命名空间"为什么不是安全边界，并改成子进程 + 超时执行
- [ ] 给排行榜加任务内容 sha256 与两次结果的 diff（讲义练习 3、5）
- [ ] 区分宏平均与微平均，估算小样本评测的误差范围

---

## 二、基础自测（选择题）

**Q1.** 关于本节的指标契约与分数汇总，正确的是：

- A. 指标函数返回 0 或 1 的整数，任务分是答对的条数
- B. 总分 = 所有样例分数的平均（每个样例权重相同）
- C. 指标函数把 `(prediction, targets, extras)` 映射为 `[0, 1]` 的浮点数；样例分平均得任务分，任务分再平均得总分
- D. 每个任务可以在同一个 JSONL 文件里混用不同的 metric

**Q2.** `metric_rouge_l("the river flows east", ["the river bends slowly"])` 的返回值是：

- A. 0.5
- B. 0.25
- C. 0.667
- D. 1.0

**Q3.** `metric_exact_match("25", ["25.0"])` 返回 0.0。原因是：

- A. `exact_match` 区分大小写
- B. `exact_match` 会先把数字四舍五入
- C. `targets` 里只能放整数
- D. `normalize` 只做"去首尾空白、转小写、压缩连续空白"，不做数值归一化，`"25"` 与 `"25.0"` 是不同字符串

**Q4.** 写一个永远返回 `"A"` 的 adapter，在仓库自带的 5 个 fixture 任务上运行，总分是多少？

- A. 0.0
- B. 0.2
- C. 0.4
- D. 1.0

**Q5.** 关于 `metric_code_exec` 里的 `safe_globals = {"__builtins__": {...}}`，正确的是：

- A. 它能挡住 `import os`（因为没有 `__import__`），但不是安全边界：通过 `().__class__.__base__.__subclasses__()` 之类的对象内省仍能拿到 `os` 的函数，而且没有超时，死循环会卡住整个 harness
- B. 它是完整的沙箱，可以安全运行任意不可信代码
- C. 它禁止了所有循环语句
- D. 它会在子进程中执行代码并限制内存

**Q6.** 两个任务：`arithmetic` 有 100 个样例，得分 0.5；`summary` 有 5 个样例，得分 1.0。按 `run_leaderboard` 的算法，`overall_score` 是多少？

- A. 0.524
- B. 0.5
- C. 1.0
- D. 0.75

**Q7.** 讲义说"Swap the adapter, the leaderboard moves; swap the tasks, the leaderboard moves. Nothing else should move." 接入一个新模型时，应该改动哪一部分？

- A. 修改各个 metric 的归一化规则，让新模型得分更高
- B. 只写一个新的 adapter（实现 `generate` 和 `name`），任务、指标、运行器、排行榜格式都不动
- C. 修改 `ToyAdapter._answer` 的分支
- D. 修改 JSONL 中的 `targets`

**Q8.** 3 个 `code_exec` 样例，每个都只通过 3 个 IO 对中的 2 个。`run_task` 返回的 `score` 与 `correct` 分别是：

- A. `score = 0.0`，`correct = 0`
- B. `score = 0.667`，`correct = 3`
- C. `score = 0.667`，`correct = 2`
- D. `score = 1.0`，`correct = 3`

---

## 三、动手 / 代码题

**Q9.** "基线测试"：写一个 `EchoAdapter`，把每个 prompt 冒号后面的内容原样返回（例如 `"write: hello world"` → `"hello world"`），在 5 个 fixture 任务上跑 `run_leaderboard`。

1. 预测各任务分数与总分，再实际运行验证。
2. 结合 Q4 的"常数 A"基线，指出 fixture 任务设计上的问题，并给出修改建议。

**Q10.** `metric_code_exec` 的"安全"问题：

```python
    safe_globals = {"__builtins__": {"range": range, "len": len, "min": min, "max": max, "abs": abs, "int": int, "float": float}}
    local: Dict[str, object] = {}
    try:
        exec(prediction, safe_globals, local)
    except Exception:
        return 0.0
```

1. 构造一个"预测代码"，在不 `import` 的情况下调用到 `os.getcwd()`，并解释原理。
2. 再构造一个让 harness 永远卡住的预测。
3. 改写成"子进程 + 超时"版本 `metric_code_exec_subprocess`，并说明它解决了什么、还没解决什么。
4. 顺便指出这个函数里的一行死代码，以及畸形 IO 对的计分问题。

**Q11.** 讲义练习 3 与练习 5：

1. 写 `task_digest(path)`，返回任务文件的 sha256，并说明应该把它放在排行榜 JSON 的什么位置。
2. 写 `diff_leaderboards(old, new)`，返回分数变化的任务列表 `(task, old, new, delta)`；新增/删除的任务也要列出。
3. 用 `ToyAdapter` 与 Q9 的 `EchoAdapter` 的两份结果演示输出。

**Q12.** 让指标更稳健：

1. `metric_multiple_choice` 只看预测的第一个字符。下面三个预测在目标分别为 `B`、`B`、`A` 时得几分？`"The answer is B"`、`"(B)"`、`"Apple? no, B"`。
2. 写一个 `extract_choice(pred)`，能从 `"The answer is B"`、`"(B)"`、`"answer: c"`、`"a) the apple"` 中正确抽出选项字母，而对 `"Apple? no, B"` 不误判为 A。
3. 给 `exact_match` 加数值归一化，使 `"25"` 与 `"25.0"`、`"4."` 与 `"4"` 判为相等。

---

## 四、面试高频题

**Q13.**（基础必考）如果让你从零为团队搭一个 LLM 评测 harness，你会怎么拆模块？每个模块的接口是什么？

**Q14.**（原理深挖）Exact match、ROUGE-L、执行型指标（如 pass@k）、LLM-as-judge 各适合什么任务？各有什么坑？

**Q15.**（工程实践）怎样保证"昨天的分数和今天的分数可以比较"？除了讲义的三条，还要记录什么？

**Q16.**（场景设计）要评测一个代码生成模型，需要执行模型写出的代码。请设计执行环境与指标。

**Q17.**（追问型）新模型在你的 harness 上总分比旧模型高了 5 个百分点。你会直接宣布"新模型更好"吗？怎么判断这是真提升？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Every metric is a function from `(prediction, targets, extras) -> float in [0.0, 1.0]`. The harness averages the per-example scores to get a task score, then averages task scores to get the overall." A 错：`rouge_l`、`code_exec` 会给部分分；B 描述的是微平均，代码实际是对任务分做宏平均（见 Q6）；D 错：`run_task` 里 `assert all(ex.metric == metric for ex in examples)` 会拒绝混用（注意 `assert` 在 `python -O` 下会被跳过）。

### Q2 — 答案：A

分词后 pred = `[the, river, flows, east]`，ref = `[the, river, bends, slowly]`，LCS = `[the, river]` 长度 2。`P = 2/4 = 0.5`，`R = 2/4 = 0.5`，`F1 = 2·0.5·0.5/(0.5+0.5) = 0.5`（实际运行结果 0.5）。这正是测试 `test_rouge_l_partial_overlap_below_one` 里的例子，测试只断言"在 0 和 1 之间"。B 是 P·R；C 是错把 LCS 当成 3；D 是完全相同时的值。

### Q3 — 答案：D

`normalize` 的实现是 `re.sub(r"\s+", " ", s.strip().lower())`，只处理大小写和空白。fixture 里 `100 / 4` 的目标写的是 `"25.0"`，因为 `ToyAdapter` 用 Python 的真除法 `str(25.0)` 得到 `"25.0"`——目标是**按 Toy 的输出格式**写的。一个真实模型回答 `"25"`、`"25."` 或 `"The answer is 25"` 都会得 0 分（实测 `"4."` vs `"4"`、`"The answer is 4"` vs `"4"` 也都是 0）。A 错，已经转小写；B、C 都是代码里没有的行为。

### Q4 — 答案：B

实测：`multiple-choice` 1.0，其余四个任务 0.0，总分 `1/5 = 0.2`。原因是 5 道选择题的正确答案**全部是 A**，常数答案就能拿满分——这是典型的"答案位置偏置"。真实基准会打乱选项顺序并检查答案字母分布。A 忽略了选择题；C、D 是没有实际计算的猜测。

### Q5 — 答案：A

`exec` 的 `__builtins__` 里没有 `__import__`，`import os` 会抛异常，所以测试 `test_code_exec_runs_pairs_and_blocks_unsafe` 能通过。但 Python 对象模型可以绕开 builtins：`().__class__.__base__` 是 `object`，`object.__subclasses__()` 里有 `os._wrap_close`，它的 `__init__.__globals__` 就是 `os` 模块的全局字典。我们实测这样的预测代码能调用 `getcwd()` 并在 IO 对上得 1.0 分（见 Q10）。另外 `exec` 在当前进程同步执行，没有超时与资源限制。讲义说"you cannot reach the filesystem from a code prediction"，这个说法过强。B 错；C 错，`while` / `for` 都能用；D 描述的是改进方案，不是现状。

### Q6 — 答案：D

`run_leaderboard` 中 `overall = sum(r.score for r in results) / len(results)`，即对**任务**做宏平均：`(0.5 + 1.0) / 2 = 0.75`。A 是微平均 `(50 + 5)/105 ≈ 0.524`；B、C 只取了其中一个任务。宏平均的好处是小任务不会被大任务淹没；代价是 5 个样例的任务与 100 个样例的任务权重相同，小任务的噪声会被放大。报告时应同时给出每个任务的 `total`。

### Q7 — 答案：B

`ModelAdapter` 是 `typing.Protocol`（结构化类型）：任何对象只要有 `generate(prompts) -> List[str]` 和 `name`，就能传给 `run_leaderboard`，不需要继承。讲义 "Use It" 一节给出的 `HttpAdapter` 就是这样接入的。A、D 是"为了让某个模型得分而改评测"，正是讲义警告的 over-fitting 陷阱；C 改的是 Toy 模型本身，与接入新模型无关。

### Q8 — 答案：C

每个样例得 `2/3`，`correct_sum = 2.0`，`score = 2.0/3 ≈ 0.667`，`correct = int(round(2.0)) = 2`（实测 `0.6667, 2, 3`）。`correct` 是"部分分的和取整"，并不是"完全答对的样例数"（这里一个完全答对的都没有）。对 `rouge_l`、`code_exec` 这类部分分指标，`correct/total` 这一列容易误导读者。

### Q9 — 参考答案

```python
class EchoAdapter:
    name = "echo"
    def generate(self, prompts):
        return [p.split(":", 1)[1].strip() for p in prompts]
```

1. 预测与实测（一致）：

| 任务 | 回声输出举例 | 分数 | 原因 |
|------|------------|------|------|
| arithmetic | `"2 + 2"` | 0.0 | 不等于 `"4"` |
| code-exec | `"write a function f ..."` | 0.0 | 不是合法 Python，`exec` 抛异常 |
| generation | `"hello world"` | **1.0** | 目标 `"hello"` 就是 prompt 里的词 |
| multiple-choice | `"A | mammal, ..."` | **1.0** | 首字符是 A，而答案全是 A |
| summary | `"Cats are mammals. Mammals are warm blooded."` | **0.698** | 参考摘要是原文第一句，回声包含它，`R = 1`；五题 `P` 依次为 3/7、3/6、4/7、4/7、5/8，F1 依次为 0.600、0.667、0.727、0.727、0.769 |
| **总分** | | **0.54** | |

   以 `sum-00` 为例：pred 7 个词、ref 3 个词、LCS 3，`P = 3/7`，`R = 1`，`F1 = 0.6`。

2. 暴露的问题与建议：
   - **generation**：目标子串直接出现在 prompt 里，回声即满分。目标应该是需要模型**生成**的内容（例如问题的答案关键词），并检查 prompt 中不包含目标。
   - **multiple-choice**：答案全是 A（Q4 常数基线 1.0）。应打乱选项、让答案字母均匀分布，并报告"常数基线"分数作为下界。
   - **summary**：参考摘要就是第一句，"lead-1"（取首句）基线即满分，回声也有 0.7。ROUGE 应与"取首句""全文"两种基线一起报告。
   - **ToyAdapter 本身**是按 fixture 写的模式匹配，满分不代表 harness 能区分好坏模型。应把这些基线 adapter 加进测试：要求"真模型分数显著高于基线"才有意义。

### Q10 — 参考答案

1. 逃逸示例（实测能返回当前工作目录，IO 对设为该目录时得 1.0）：

```python
def f(x):
    for c in ().__class__.__base__.__subclasses__():
        if c.__name__ == '_wrap_close':
            return c.__init__.__globals__['getcwd']()
```

   原理：`exec` 只限制了"名字查找"时能看到的 builtins，但任何对象都可以通过 `__class__`、`__base__`、`__subclasses__()`、`__globals__` 等属性一路走到已加载模块的全局变量。`os._wrap_close` 是 `os` 模块里定义的类，其方法的 `__globals__` 就是 `os` 的命名空间，`system`、`remove` 等函数都在里面。

2. 卡死示例：`"def f(x):\n    while True:\n        pass\n"`。`exec` 只是定义函数，调用 `fn(x)` 时进入死循环，`run_task` 永远不返回。

3. 子进程 + 超时版本（已运行验证：正常代码 1.0，死循环 1 秒后得 0.0，语法错误 0.0）：

```python
import json, subprocess, sys

RUNNER = r'''
import json, sys
src, pairs = json.loads(sys.stdin.read())
ns = {}
exec(src, ns)
f = ns["f"]
ok = 0
for x, y in pairs:
    try:
        ok += (f(x) == y)
    except Exception:
        pass
print(ok)
'''

def metric_code_exec_subprocess(prediction, targets, extras, timeout=2.0):
    pairs = extras.get("io_pairs") or []
    if not pairs:
        return 0.0
    try:
        proc = subprocess.run([sys.executable, "-I", "-c", RUNNER],
                              input=json.dumps([prediction, pairs]),
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 0.0
    if proc.returncode != 0:
        return 0.0
    return int(proc.stdout.strip() or 0) / len(pairs)
```

   - **解决了**：死循环/崩溃/内存炸裂不会拖垮 harness 进程（超时即判 0）；预测代码改不了 harness 的全局状态。
   - **没解决**：子进程仍以同一用户身份运行，**可以读写文件、访问网络**。真正的隔离要靠容器或 gVisor/Firecracker 一类沙箱，禁网、只读文件系统、`setrlimit` 限 CPU/内存/进程数、以非特权用户运行。

4. 死代码：函数开头已经 `if not isinstance(pairs, list) or not pairs: return 0.0`，末尾的 `if not pairs: return 0.0` 永远不会触发。计分问题：格式不对的 IO 对（如 `[5]`）被 `continue` 跳过，但仍计入分母 `len(pairs)`。实测 `[[1,2],[3,6],[5]]` 对 `x*2` 得 0.667，模型因为**任务文件的错误**被扣分；应在加载任务时校验 IO 对格式，而不是在打分时静默跳过。另外 `targets=["ok"]` 在打分中完全没用到，docstring 却说 "Targets is a list of stringified expected results"。

### Q11 — 参考答案

```python
import hashlib
from pathlib import Path

def task_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def diff_leaderboards(old, new, eps=1e-9):
    a = {t["task"]: t["score"] for t in old["tasks"]}
    b = {t["task"]: t["score"] for t in new["tasks"]}
    rows = []
    for task in sorted(set(a) | set(b)):
        sa, sb = a.get(task), b.get(task)
        if sa is None or sb is None:
            rows.append((task, sa, sb, None))          # 新增或删除的任务
        elif abs(sb - sa) > eps:
            rows.append((task, sa, sb, sb - sa))
    return rows
```

1. 放在每个任务条目里，例如 `{"task": "arithmetic", "sha256": "bb67c876...", "score": ...}`；再加一个"所有任务摘要按名称排序后拼接再哈希"的 `task_set_sha256` 放在顶层。两次结果对比时，先比较 sha256，不同就说明任务变了，分数不可直接比较。本仓库 fixture 的摘要前 12 位实测为：arithmetic `bb67c8760bfc`、code-exec `45eb7965609d`、generation `35b4073a1e13`、multiple-choice `43f25a9ccea8`、summary `1615bfd74602`。
2. 见上面代码。用并集遍历，才能发现"任务被删掉了"这种静默变化。
3. Toy → Echo 的实测输出：

```text
('arithmetic', 1.0, 0.0, -1.0)
('code-exec', 1.0, 0.0, -1.0)
('summary', 1.0, 0.698088578088578, -0.30191142191142195)
```

   generation 与 multiple-choice 都是 1.0 → 1.0，不出现在 diff 中。加分点：再对 `per_example` 做 diff，列出"从 1 变 0"的样例 id 与两次预测，才能回答"为什么掉分"。

### Q12 — 参考答案

1. 实测：`"The answer is B"` → 首字符 `T`，0 分；`"(B)"` → 首字符 `(`，0 分；`"Apple? no, B"`（目标 A）→ 首字符 `A`，**误判为 1 分**。首字符规则既漏判又误判。
2. 参考实现（已运行验证六个例子）：

```python
import re
CHOICE_RE = re.compile(r"(?:answer\s*(?:is|:)?\s*|^\s*)\(?([A-D])\)?(?![A-Za-z])", re.I)

def extract_choice(pred):
    m = CHOICE_RE.search(pred.strip())
    return m.group(1).upper() if m else ""
```

   结果：`"The answer is B"` → B，`"(B)"` → B，`"answer: c"` → C，`"a) the apple"` → A，`"Apple? no, B"` → 空（不误判）。关键是 `(?![A-Za-z])`：字母后面不能紧跟字母，才不会把单词首字母当成选项。生产中更稳妥的做法是在 prompt 中要求固定输出格式，或比较各选项的对数似然（lm-evaluation-harness 对选择题的常用做法），而不是解析自由文本。
3. 数值归一化（已验证 `"25"`/`"25.0"`、`"4."`/`"4"`、`"2.5"`/`"2.50"` 都判为相等，`"hello"`/`"Hello"` 仍相等）：

```python
def normalize_num(s):
    s = normalize(s).rstrip(".")
    try:
        v = float(s)
        return repr(int(v)) if v == int(v) else repr(v)
    except ValueError:
        return s
```

   注意：归一化规则一旦改动，所有历史分数都要重跑，规则本身也应该带版本号写进排行榜。

### Q13 — 参考回答要点

- **任务层**：版本化的数据文件（JSONL），每条有 id、输入、参考答案、指标名、附加字段；附带 sha256。
- **模型层（adapter）**：`generate(prompts) -> list[str]`（必要时还有 `loglikelihood(context, continuation)` 用于选择题）；封装 prompt 模板、解码参数、重试与限速。这是唯一允许出现模型相关代码的地方。
- **指标层**：纯函数 `(pred, targets, extras) -> [0,1]`，有单元测试；按名字注册到字典里分发。
- **运行器**：分批、并发、超时、失败重试、缓存（相同输入不重复调用 API）。
- **报告层**：带 schema 版本的 JSON，包含每任务分数、样例数、延迟、置信区间、per-example 记录、模型/任务/代码版本。
- 加分点：说出 lm-evaluation-harness、lighteval 等开源实现是同样的形状（讲义的 Further Reading）。

### Q14 — 参考回答要点

- **Exact match**：适合答案唯一且短的任务（算术、抽取式问答）。坑：格式差异（`25` vs `25.0`、带句号、带解释）导致假阴性；需要答案抽取与归一化规则。
- **ROUGE-L**：适合有参考文本的摘要。坑：只看词序重叠，不看语义；同义改写得低分，照抄原文得高分（Q9 回声 0.698）；**本节的 `_tokens` 用 `[a-z0-9]+` 分词，中文文本得不到任何 token，实测两段完全相同的中文 ROUGE-L 为 0.0**，中文需要按字或分词器切分。
- **执行型（pass@k）**：适合代码，直接验证功能正确。坑：需要沙箱（Q10）、测试用例覆盖不足会放过错误实现、非确定性代码难评。
- **LLM-as-judge**：适合开放式生成、对话质量。坑：位置偏置、长度偏置、偏爱同家族模型、自身不稳定；需要校准（与人工标注比对一致性）与交换顺序。
- 结论：能用确定性指标就不用 judge；用 judge 时固定 judge 模型版本与提示词。

### Q15 — 参考回答要点

- 讲义三条：**固定任务文件**（sha256）、**diff 预测而不只是分数**、**限制 batch 大小**。
- 还要记录：模型标识（含 checkpoint 哈希，讲义提到第 47 节）、adapter/提示模板版本、解码参数（temperature、top_p、max_tokens、stop）、随机种子、harness 代码的 git commit、指标归一化规则的版本、运行时间与环境。
- 排行榜里的 `timestamp` 让 JSON 每次都不一样——"可复现"指的是分数可复现，diff 时应忽略这类元数据字段。
- 小细节：仓库自带的 `outputs/leaderboard.json` 中 `"adapter": "arithmetic"`，而当前代码会写 `"toy.v1"`——说明这份产物是旧版本代码生成的。没有代码版本号，就无法判断一份结果是谁、用什么生成的，这正是要记录版本的原因。
- 加分点：对 API 模型做 temperature = 0 也不保证完全确定，应重复运行并报告方差。

### Q16 — 参考回答要点

- **执行环境**：每个样例一个一次性容器或 microVM（gVisor/Firecracker 等）；禁网；只读根文件系统 + 临时可写目录；非 root；`setrlimit` 限制 CPU 时间、内存、进程数、文件大小；墙钟超时后强杀。不要依赖"去掉 builtins"这类语言层限制（Q5、Q10）。
- **指标**：每题多组单元测试（含边界条件与隐藏测试）；报告 pass@1 与 pass@k（采样 n 个、用无偏估计 `1 − C(n−c, k)/C(n, k)`）；区分"编译/语法错误""超时""断言失败"几类失败原因。
- **防作弊**：检查模型输出是否硬编码了测试用例的期望值；测试集与训练数据去重以防污染。
- **工程**：并发执行队列、结果缓存、失败重试只针对基础设施错误而不是测试失败。

### Q17 — 参考回答要点

- **先看样本量与误差**：本节 fixture 每个任务只有 5 题，一题就是 20 个百分点。以 25 题、正确率 0.8 估算，二项分布标准误约 `sqrt(0.8·0.2/25) = 0.08`，即 ±8 个百分点——5 个点的提升完全可能是噪声。用 bootstrap 求置信区间，或对两个模型在同一批题上做配对检验（如 McNemar 检验）。
- **看是哪里涨的**：用 per-task 与 per-example diff 定位，是普遍提升还是某个小任务大涨（宏平均下小任务的波动会被放大）。
- **排除评测本身的变化**：任务文件 sha256、prompt 模板、解码参数、指标归一化规则是否变了。
- **排除钻空子**：与常数/回声/lead-1 基线比较（Q9）；检查答案格式是否恰好迎合了某个脆弱指标（如首字母选择题）。
- **排除数据污染**：新模型的训练数据是否包含测试题；用改写过的题目复测。
- **多次运行**：采样解码时多跑几次看方差。
- 结论：只有在置信区间不重叠、提升在多个任务上一致、且排除了评测变化与污染之后，才能说"更好"。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：基准与 lm-evaluation-harness 的概念介绍。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：ROUGE、LLM-as-judge 等指标框架。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：同样"固定任务 + 指标 + 运行器"的思路，用于 agent 评测。
- [阶段 19 · 41 完整 Evaluation 流程](../../41-eval-pipeline/docs/zh.md)：本阶段前面训练 GPT 时搭建的评测流程。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：被评测的 checkpoint 格式，讲义建议把它的哈希写进排行榜。

### 本节被哪些后续内容用到
- [阶段 19 · 70 任务规范格式](../../70-task-spec-format/docs/zh.md)：把本节的 JSONL 任务格式扩展成更完整的规范。
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)：EM、F1、BLEU、ROUGE 等指标的系统实现。
- [阶段 19 · 72 代码执行评估指标](../../72-code-exec-metric/docs/zh.md)：把 `code_exec` 做成带沙箱与超时的 pass@k。
- [阶段 19 · 73 Perplexity 与 Calibration](../../73-perplexity-calibration/docs/zh.md)：基于对数似然的评测。
- [阶段 19 · 74 排行榜汇总](../../74-leaderboard-aggregation/docs/zh.md)：宏平均、加权与置信区间。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：把以上组件串起来。
- [阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：研究 agent 中对实验结果打分。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把 harness 用到 agent 的日常迭代。

### 延伸关键词
`lm-evaluation-harness` · `lighteval` · `JSONL task spec` · `exact match / normalization` · `ROUGE-L / LCS` · `pass@k` · `LLM-as-judge` · `macro vs micro average` · `bootstrap confidence interval` · `McNemar test` · `data contamination` · `answer position bias` · `sandboxed code execution` · `typing.Protocol`
