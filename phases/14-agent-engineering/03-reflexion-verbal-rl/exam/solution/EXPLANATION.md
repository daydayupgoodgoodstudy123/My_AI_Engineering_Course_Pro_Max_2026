# 参考答案讲解：Reflexion（14/03）

计时结束后再看。参考实现在同目录的 `reflexion/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修反思循环

**现象**：解锁后的第一个错误是 “reflexion should converge on a reachable target”。目标是 20，可 Actor 第二次给出 `[1, 1, 1]`，之后一直停在那里。

**顺着往上找**：Actor 不记自己的东西，每次只读最新一条反思，从里面拿到上次试了什么、差多少。把每个试次的反思打印出来，第一条是 “tried [1, 2, 3]: sum 6 overshoots by 14; pick smaller values”：和是 6、目标是 20，却说超了。Actor 照着往下调，没有错；错的是写反思的 `reflect`。报错出现在运行结果上，离根因隔着“下一个试次读反思”这一层。

**依次修四处**：

1. `SelfReflector.reflect` 按 docstring 的方向写：delta 是 `sum(attempt) - target`，小于零才是不够。

   ```python
   if delta < 0:
       return f"tried {attempt}: sum {total} is {-delta} short; pick larger values"
   return f"tried {attempt}: sum {total} overshoots by {delta}; pick smaller values"
   ```

2. `EpisodicMemory.add` 满了以后丢最旧的一条。原来的 `kept.pop()` 丢掉的是刚加进来的那一条，记忆就停在最早的几条上。默认 6 条的那次运行碰不到上限，所以要修完第 1 处才看得到：`max_len=2` 时，Actor 每次都读到第 2 次的反思，反复给出 `[9, 2, 3]`。
3. `run_reflexion` 遇到 `ToolDown` 时只记录这个试次，不写反思、不进记忆。工具宕机不是 agent 的错，讲义说这种反思对以后的运行没有帮助，把一次偶然的故障记下来就成了 superstition。原来的代码不光存了一条没用的反思，这条反思还成了最新的一条，Actor 读不懂，退回 `[1, 2, 3]`，前面学到的全丢了。
4. 记忆改成以规范化文本为键的 dict。dict 保持插入顺序，第一个键就是最旧的：

   ```python
   key = normalize(reflection.text)
   old = self._items.pop(key, None)
   if old is not None:
       reflection = replace(reflection, failures=old.failures + reflection.failures)
   self._items[key] = reflection
   if len(self._items) > self.max_len:
       del self._items[next(iter(self._items))]
   ```

   原来每加一条，都要把已有的每一条重新规范化、重建一次列表，回放一段长记录是 O(n²)。3,700 次写入（3,600 条不同的反思）本机实测 1.4 到 1.7 秒，改完以后约 1.2 毫秒。讲义的 memory rot 说的就是这个：缓冲越大，重跑越慢。只把规范化文本缓存起来、每次 add 仍然重建列表，还是每次都走一遍全部记忆，过不了计时。

**护栏**：

- 方向只能在 `reflect` 里修。让 Actor 把 “overshoots” 读成往上调，运行确实能收敛，但存下来的反思还是反的，别的读者（人、学习记录文件、下一个模型）都会被误导；测试比对反思原文。把 `scalar_check` 改成 `target - sum`，delta 的符号就错了。
- 提速不能丢掉去重的语义：同一条教训再学到一次，要挪到最新的位置，换成最新的试次号、措辞和 ttl，failures 相加。这样 Part 3 的 ttl 才是从最近一次学到算起。`if key in seen: return` 留下的是旧的试次号，这条教训会在仍然有用时过期。
- normalize 不能为了快而简化，大小写和空白都要处理。被淘汰的教训再学到时从头算，failures 是 1。
- 顺序是先拿掉旧的那条、放进新的，再检查有没有超过 max_len。记忆满了以后又学到一条已有的教训，条数没有变，什么都不用淘汰；先腾位置再去重，会白白挤掉最旧的一条。
- `dict.popitem()` 弹出的是最后插入的一条，等于把第 2 处缺陷写回去了。用列表加“键到下标”的 dict 也不行：删掉一条以后，后面的下标全都错了。

## Part 2 学习记录文件

写的时候先把每一条都检查完，再打开文件；每条的围栏比正文里最长的一串反引号多一个，至少三个：

```python
longest = max((len(run) for run in BACKTICKS.findall(reflection.text)), default=0)
fence = "`" * max(3, longest + 1)
```

读的时候按行走，从第一行起就认围栏。遇到一行纯反引号，就一直读到和它一模一样的那一行；如果前面有一个还没拿到正文的标题，这一段就是那条记录的正文，否则（文件头里的示例、人加的代码块）整段跳过。围栏外以 `## ` 开头的行就是标题，必须完全匹配 `## <task class> (trial N, ttl N, failures N)`。

- **为什么用围栏**：正文可能以 `- `、`#`、`## ` 开头，可能有行尾空格、行首缩进、开头结尾的空行。放进围栏里，Markdown 就不会解释它们，读回来也不用转义。剩下的问题只有一个：正文里本身就有反引号。围栏比正文里最长的那串多一个，正文的任何一行都不可能等于围栏行。
- **文件头不是记录**：HEADER 自己就在围栏里放了一个示例标题行。不认围栏、只认 `## ` 的读法，会把它读成第一条记录；把标题和围栏块按顺序配对，会整体错一位。
- **原样**：`newline=""` 打开，按 `\n` 切，正文用 `"\n".join(...)` 拼回去，不 strip。行尾两个空格在 Markdown 里是硬换行，编辑器常常顺手删掉，这正是测试要查的。
- **严格**：围栏外的 `## ` 行必须整行匹配标题格式（`fullmatch`，括号后面多一个字也不行），读回的条目再过一遍写的时候那套检查。把不认识的标题当备注跳过，后面的围栏也就成了备注，这条反思就悄悄没了。
- **先查后写**：`open(path, "w")` 一打开就把文件清空了。边写边查，一条坏数据就会把原来的学习记录毁掉。

## Part 3 评估器裁决与试次循环

`judge` 照 docstring 的顺序一条一条判断，第一条成立的说了算：

```python
if trial.error is not None:
    return Verdict(False, "external")
if trial.scalar is not None:
    return Verdict(trial.scalar, "scalar")
if any(a == b for a, b in zip(actions, actions[1:])):
    return Verdict(False, "stuck")
if len(actions) > max_steps:
    return Verdict(False, "inefficient")
if trial.self_score is not None:
    return Verdict(trial.self_score >= pass_score, "self")
return Verdict(False, "none")
```

- **为什么是这个顺序**：讲义的 2026 默认组合是 scalar when available, self-eval when not, heuristics as safety rails。scalar 是外部的 ground truth，有就听它的；护栏防的是最弱的自评，所以排在自评前面、scalar 后面。外部故障排在最前面：试次被打断了，什么信号都不可信。
- **护栏本身就是信号**：stuck 和 inefficient 是讲义里的 heuristic evaluator，只要成立就说了算，不只是在自评通过时才拿来推翻它。自评 0.2 又卡住了，来源是 stuck；完全没有自评但卡住了，来源也是 stuck，并且会写反思。连续两次可以出现在轨迹的任何位置。
- **`is not None`**：scalar 为 False 是“有信号，没通过”，self_score 为 0.0 是“有自评，打了零分”，都不是“没有”。
- **visible**：`r.trial < now <= r.trial + r.ttl`。下界保证一个试次看不到自己的、也看不到更晚试次的反思（从文件读回的记忆里可能有）；上界就是 ttl。本课测验第 11 题的写法 `now - trial < ttl` 少看一次。
- **循环**：第 n 次调用 `act(n, memory.visible(n))`，判定以后，失败且值得反思（不是 external，也不是 none）才调用 `reflect` 并存进记忆；成功就停。外部故障也占一次试次。`max_steps` 和 `pass_score` 要传给 `judge`。

## Part 4 学习曲线 CSV

每个任务一个后台任务，自己带一个记忆，一个试次接一个试次地跑；每判定完一次，就把 `(task, n, verdict)` 放进一个队列。读的那一边从队列里取，取到一个就输出一行：

```python
while finished < len(runners):
    item = await queue.get()
    if item is None:              # 一个任务跑完了
        finished += 1
        continue
    if isinstance(item, Exception):
        raise item
    task, n, verdict = item
    solved += verdict.success
    rate = f"{solved / len(names):.4f}"
    yield _record((task, n, 1 if verdict.success else 0, verdict.source, rate))
```

- **顺序就是完成的顺序**：队列里的顺序就是试次完成的顺序。先 gather 全部再输出，顺序对了，但测试记下的“每行到达时完成了几个试次”会全是 8。
- **为什么不按轮次跑**：论文的学习曲线是按试次号画的，很容易写成“所有任务的第 n 次都完成，再开始第 n+1 次”。那样每一轮都要等最慢的任务，Q4 的第二次只能排在 Q1 的第一次后面。按试次号的曲线可以事后从这些行里算出来。
- **每个任务一个记忆**：Reflexion 的记忆是按任务的。共用一个记忆，别的任务的反思会出现在这个任务的 prompt 里。什么样的失败值得反思，直接用 Part 3 的 `worth_reflecting`：Q4 的第一次没有任何信号，不写反思。
- **CSV**：问题文本里有逗号和双引号，交给 `csv.writer`。成功率的分母是全部任务。
- **关闭时取消**：生成器的 `finally` 里把后台任务全部取消。读的人中途走了，后台不能接着调用模型。
- **异常**：后台任务出错时把异常放进队列，由读的那一边抛出。否则读的那一边会一直等一个永远不来的结束标记。

## Part 5 任务类作用域

构造时把每个声明的类和它的每一个前缀都登记下来。recall 从类本身往上走到根，每一层按试次号从新到旧排（`sorted` 是稳定的，试次号相同的保持挂上去的顺序），取前 per_level 条，总数到 total 就停：

```python
for depth in range(len(parts), 0, -1):
    scope = "/".join(parts[:depth])
    level = sorted(self._attached[scope], key=lambda r: -r.trial)
    for reflection in level[:per_level]:
        if len(recalled) == total:
            return recalled
        recalled.append(Recalled(scope, reflection, depth == 1 and reflection.failures == 1))
```

- **按路径段走**：上级由 `split("/")` 的前缀得到，`code/test` 永远不会出现在 `code/tests/flaky` 的路上。用 `startswith` 判断上级，兄弟类就会互相看到。
- **只往上走**：一条反思挂在某一类上，管的是这一类和它下面的类。父类看不到子类的反思：从一个具体任务学到的东西，不能自动变成整个领域的规矩。
- **可疑**：挂在根上、只来自一次失败。讲义说反思会变成 superstition，把一次偶然的失败写成规律；挂在根上，这条规律还会影响整个领域。配套 skill 也说，永远不要自动升级到 agent 作用域。参考实现照样返回它，只是标出来，交给人决定。
- **未知类报错**：前缀之外的类（`math/arith/division`）不认识，recall 和 attach 都报 KeyError，不能悄悄返回空列表或者自动建一个。

## 这套题证明了什么，没证明什么

通过了说明你能顺着一个不收敛的试次序列找到写反的反思和存错的记忆，知道外部故障为什么不该进记忆，能在不改变去重语义的前提下把记忆从平方级改成线性；能为人要读要改的 Markdown 文件设计一套能原样往返的格式；能按讲义的组合规则实现三类评估器的裁决和带 ttl 的试次循环；能写一个并发运行、实时输出、关闭时会清理的 async generator；能在路径树上按作用域取反思。

它没有用真实的 LLM 跑过 Actor 和 Self-Reflector，所以反思写得好不好（skill 里的“I failed to do X because Y; next time, Z”、拒绝 “be more careful”、拒绝含密钥的反思）这里都没有考；近似去重、sleep-time 压缩、ALFWorld 和 HumanEval 上的效果也没有涉及。讲义的练习 4（Actor 忽略反思时，最少要做多少 prompt 工程）和练习 5（读论文第 4 节）需要另外动手做。
