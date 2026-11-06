# 参考答案讲解：Reviewer（14/39）

计时结束后再看。参考实现在同目录的 `reviewer/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 rubric 和签收队列

**第一个现象**：干净的 T-001 拿了 problem_fit 2 分、总分 10。打印 `review(task()).dimensions` 会看到备注是 `goal keywords found in touched paths: 2`，可目标里只有 `signup` 出现在路径里。`sum(k in f.lower() for k in keywords for f in files)` 数的是（关键词，文件）对：`signup` 同时在 `app/signup.py` 和 `tests/test_signup.py` 里，就算了两次。docstring 写的是不同关键词的个数。关键词放进集合，再看每个关键词是否出现在某条路径里：

```python
paths = [f.lower() for f in inputs.diff_summary.get("touched", [])]
keywords = {w for w in inputs.goal.lower().split() if len(w) > 4}
found = sorted(k for k in keywords if any(k in p for p in paths))
```

课里的写法 `sum(any(...) for k in keywords)` 已经按关键词去重了文件，但关键词本身还是列表：目标里写了两遍 `signup`，照样算两次。测试里第二个目标专门这么写。

**第二个现象**：构建者顺手改了 `scripts/release.sh`，gate 报了 `scope.forbidden`，这个任务却拿了 8 分 pass。打印维度会看到五个分数都对：scope_discipline 是 0，其余四维满分。错的是结论。`review()` 只看总分，低于 5 是 hard fail、低于 7 是 soft fail，这是讲义 rubric 一节的说法；docstring 和讲义 Key Terms 里的 hard fail 还有一条：任一维 0 分。补上这一条：

```python
if any(d.score == 0 for d in dims) or total < 5:
    verdict = "hard_fail"
```

总分照实写，仍是 8，由结论来说 hard fail；把总分清零，看板上的分数就错了。零分是 hard fail，不是 soft fail，而且要在 pass 之前判断。也不要拿 gate 的结论代替评审的结论：这一条的 gate 正好是 passed: False，按 `passed` 或 block 级的 finding 判 hard fail 能让它过，但紧接着那个没有任何反馈的任务，gate 是 passed: True，总分 7，只有 verification_quality 的 0 分能让它 hard fail。讲义的说法是 gate 管确定性的事实，评审管判断，两个都要。

**第三个现象**：一个改了 `docs/api.md` 的任务拿了 6 分 soft fail，断言要的是 7 分 pass。打印维度会看到 scope_discipline 是 1，备注是 `off-scope warnings: 1`；其余四维对照各自的 docstring 都没错（problem_fit、assumptions、handoff_readiness 各 1 分，verification_quality 2 分）。gate 报 `docs/api.md` 越界没有错，可 state 的 `approved_scope` 里记着，gate 报警之后人批准把这条路径加进合同。讲义 rubric 表里 Scope discipline 那一问的后半句问的就是这个："or was the contract grown deliberately?"。第 36 课的做法是越界时问人，要么扩大合同，要么退回，这一次人选了扩大。起始代码和课里的 `score_scope_discipline` 一样只看 gate 的 findings，从没读过 state。错误在 `review()` 的总分和结论里看到，根因在打分器里。forbidden 照旧先判，再只看没被批准的越界路径：

```python
approved = inputs.state.get("approved_scope") or []
unapproved = [f for f in findings if f.get("code") == "scope.off_scope" and f.get("path") not in approved]
```

测试还查三件事：

- 批准只抵消它点名的那条路径。`docs/api.md` 和 `README.md` 都越界、批准的是 `docs/api.md` 和 `CHANGELOG.md` 时仍是 1 分。“有批准就算 2 分”、any 代替 every、拿批准的条数和越界的条数比，都在这里挂。
- forbidden 写入是 0 分，人批准过也一样。forbidden_files 是合同的负空间，批准一次写入不能把它变成允许，所以 forbidden 的检查放在最前面，批准只用来过滤越界的 warning。先用批准把全部 findings 过滤一遍，批准过的 `scripts/release.sh` 就成了 2 分。
- 课里 T-002 的 state 没有 `approved_scope`，那就是没有批准。用 `.get(...) or []` 读；`state["approved_scope"]` 会报 KeyError。

批准按完整路径比较，和 gate 报出来的路径逐字相同才算。合同本身用 glob，但人批准的是自己看过的那一条写入；想放开一整类文件，应该改合同、重跑 scope check。

`score_handoff` 在起始代码里是对的：没有 `next_action` 是 0 分，不论任务关没关；任务没关但写了下一步是 1；关了又写了下一步是 2。测试里那两条 handoff 断言是护栏，防的是顺手把它改坏。

**第四个现象**：计时断言。每个打分器在生产里是一次模型调用，测试里用每次 2 毫秒的包装来代替，并且数调用次数。`SignOffQueue` 只存了输入，`report()` 每次调用 `review()`，`board()` 为了取 total、verdict 和零分维度又对每个任务调了三次 `report()`：读一遍看板、打开 20 份报告，要调用 400 次打分器，本机 1.0 到 1.2 秒。docstring 写的是 submit 时评审、之后只读：

```python
def submit(self, inputs):
    report = review(inputs, self._scorers)
    self._reports[inputs.task_id] = report
    return report
```

`report()` 直接返回存下的报告，`board()` 遍历存下的报告。读取不再调用打分器，0.01 毫秒左右。

这一处修法还有四个要求，测试都会查：

- 报告是一次评审的记录。构建者之后改了状态，存下的报告不能跟着变，所以“输入变了就重新评审”是错的。
- 同一个任务再 submit 一次，是新的一次评审，要替换旧报告，所以按 task_id 缓存“已经评过就不再评”也是错的。
- 替换的是报告，不是看板上的行。看板每个任务一行，位置是第一次提交时的位置。按 task_id 存进 dict，给已有的键赋值不会改变它的位置；存进列表每次追加，看板会多一行；先 pop 再插入，任务会挪到最后。
- 每个打分器每次 submit 只跑一次。在 submit 里评审两次、一份存一份返回，计时能过，调用次数不对。

在第一次读取时才评审并缓存也不行：第一次读看板就要 100 次调用，而且如果状态在 submit 之后、读取之前变了，报告记的就不是 submit 那一刻。

## Part 2 评审报告历史

磁盘上两样东西：`objects/<sha256>.json` 是报告正文，文件名是正文字节的 SHA-256；`index.jsonl` 每记录一次 attempt 追加一行 `{"task", "attempt", "sha256"}`。内存里按任务存一份 digest 列表，第 n 个就是 attempt n。

```python
body = _body(report)                      # JSON：task_id、total、verdict、按原顺序的维度
digest = hashlib.sha256(body).hexdigest()
recorded = self._digests.get(report.task_id, [])
if 1 <= attempt <= len(recorded):         # 已经记过的 attempt
    if recorded[attempt - 1] != digest:
        raise ReportConflict(...)
    return digest                         # 同一份报告：重试，什么都不写
if attempt != len(recorded) + 1:
    raise ValueError(...)                 # 跳号
# 先通过所有检查，再写对象和索引
```

几个要点：

- **名字就是内容**。hash 的必须是写进文件的那几个字节。先 hash 一份缩进过的 JSON、再写一份紧凑的，对象名和内容就对不上了。
- **只追加**。已记录的 attempt 不能改：不同的报告报 ReportConflict，同一份报告是重试，返回同一个 digest，不加索引行。被拒绝的 record 什么都不写，所以对象要在所有检查通过之后才写。
- **attempt 按任务编号**，从 1 开始不跳号。正文里不放 attempt 号，所以第二次评审的结论和第一次一样时，两个 attempt 指向同一个对象。用列表存 digest 时要查下界：attempt 0 会取到 `recorded[-1]`，record 把它当成重试，load 读出最新的一份。参考实现写的是 `1 <= attempt <= len(recorded)`。
- **往返完全一致**。第六个维度 money_safety 排在第二位，按模块里的 RUBRIC 重建维度会把它丢掉；verdict 是评审写下的 soft_fail，读回来时按阈值重算会变成 pass；note 里有引号、箭头、换行、制表符和行尾空格，JSON 都能原样保存。维度要读回成 list，tuple 不相等。
- **分数是 0 到 2 的 int**。`2.0 == 2`、`True == 1`，所以 `score in (0, 1, 2)` 两个都放过，`isinstance(score, int)` 放过 True。参考实现用 `type(score) is int`，再查 `0 <= score <= 2`，只查类型会放过 3。这和内容寻址有关：同样的结论写成 2.0 和 2，正文字节不同，就成了两个对象。
- **重开**时逐行读索引，恢复每个任务的 digest 列表，编号接着往下走。

## Part 3 带证据的评分与双评审对账

先把输入里能引用的东西做成一个集合：每条 touched 路径是 `file:<path>`，每条反馈记录是 `feedback:<command_id>`，每条 gate finding 是 `finding:<code>`，state 的每个键是 `state:<key>`。之后每条引用都是集合查找，逐字匹配。

每个评审的每条意见单独判断：引用了至少一样东西，而且每样都在集合里，才算有证据；否则这条意见最多计 1 分，并记进 unsupported。两个评审都算完，再按维度合并：

```python
for name in rubric:
    dims.append(DimensionScore(name, (a[name] + b[name]) // 2, note))
    if abs(a[name] - b[name]) > 1:
        escalate.append(name)
```

容易错的地方：

- **按维度名配对**。judge-b 的意见是乱序的，按位置配对会把 problem_fit 和 verification_quality 配在一起。先把每份草稿变成 `{维度: 意见}`，同时检查维度集合：少一维、多一维、同一维两次都报 ValueError。只比较长度会放过“同一维两次再少一维”。
- **证据的判断**。`file:App/signup.py` 不是 touched 里的 `app/signup.py`；`feedback:pytest -q` 是命令，这条命令跑了两次，一次失败一次成功，引用它说明不了是哪一次；`finding:scope.forbidden` 这一轮 gate 根本没报。`state:active_task_id` 的值是 None，但这一项存在，“任务已关闭”正是靠它证明的。`all([])` 是 True，不检查非空，什么都没引用的意见就算有证据了；用 `any` 会放过一真一假的引用。
- **unsupported 列全**。没证据的 0 分和 1 分不会被封顶降分，也要列出来。顺序是先第一个评审，各自按 rubric 顺序。
- **向下取整**。Python 的 `round` 是银行家舍入，`round(1.5)` 是 2、`round(0.5)` 是 0，1 对 2 会给出 2。取较高的同样错；取较低的在相差 1 时碰巧一样，到 2 对 0 时给 0。
- **escalate 看封顶后的分数**。无证据的 2 对有证据的 0，封顶后是 1 对 0，不 escalate，这个维度得 0，结论 hard fail；有证据的 2 对无证据的 0 仍是 2 对 0，要 escalate。escalate 是给人看的标记，不改分数也不改结论：测试第三组里被 escalate 的维度得 1，总分 9，照样 pass。
- **结论的边界**。任一维 0 或总分低于 5 是 hard fail，低于 7 是 soft fail：恰好 7 是 pass，恰好 5 是 soft fail，总分 7 但有一维 0 是 hard fail。这和 Part 1 的 `review()` 是同一条规则。

## Part 4 构建与评审交替的回合

```python
yield _record(HEADER)
before = dict(workspace)
for n in range(1, max_rounds + 1):
    await build(n, workspace, last)
    frozen = dict(workspace)                    # 回合返回的那一刻，复制一份
    changed = sorted(p for p in frozen.keys() | before.keys() if frozen.get(p) != before.get(p))
    last = await review(n, MappingProxyType(frozen))
    before = frozen
    ...                                         # 定 next：done / human / build
    yield _record((n, ";".join(changed), last.total, last.verdict, then))
    if then != "build":
        return
```

- **冻结副本**。`dict(workspace)` 在 `await build(...)` 返回后立刻执行，中间没有 await，任何别的任务都插不进来。构建者留下的格式化钩子 5 毫秒后才写，评审要等 20 毫秒的模型调用，钩子的写入只会落在实时的 workspace 里。直接把 workspace 给评审，或者给 `MappingProxyType(workspace)`，评审读到的都是钩子写过的内容：只读视图仍然是实时的。
- **只读**。`MappingProxyType` 的写入报 TypeError。给一份普通的 dict 副本，评审写进去不报错，测试要求它报错。讲义的原则是评审不能改 diff；构建者的工作区也确实没被动过。
- **changed 是快照之间的差**。钩子在第一轮评审期间写下的内容，第一轮的评审没看到，所以算第二轮的变化；删掉的 `docs/notes.md` 也算；内容没变的重写不算。排序后用 `;` 连接。两边都要用快照：评审结束后拿实时的 workspace 去比，钩子的写入会提前一轮算进来。测试最后一段专门让构建者只写测试文件、钩子去改 `app/signup.py`，第一轮的 changed 只能有测试文件。
- **何时停**。pass 结束（next 是 done，最后一轮也一样）；hard fail 按讲义的 Key Terms 立刻停下交给人；soft fail 进入下一轮，下一轮的构建者拿到这份报告；到上限还没 pass，最后一行写 human。
- **每轮立刻发出**。记录在下一轮 `build` 之前 yield，消费者拉取时生成器才继续，所以构建者开始第 n 轮时，已经收到了 n−1 行数据。
- **格式**。每个字符串是 `csv.writer` 写出的一条记录，带 `\r\n`。测试对每个字符串单独解析，再对拼接后的全文解析，两次结果必须一样。

## Part 5 意见线程

参考实现分两步。先把所有评论按 id 放进字典，再对每条评论沿 parent 往上走到 finding，记下它属于哪个线程。输入是乱序的，回复可能排在父评论前面，所以必须先建完字典再找根；往上走时记下走过的 id，遇到回环报错，不会死循环。

然后逐个线程判断：

```python
resolves = [c.at for c in thread if c.resolve and c.author == "reviewer"]
last_resolve = max(resolves) if resolves else None
later = [c for c in thread if not (c.resolve and c.author == "reviewer")]
resolved = last_resolve is not None and all(c.at < last_resolve for c in later)
```

- **任意深度**。fit-a 的 resolve 在第四层，scope-a 重新打开它的回复在第二层，只看 finding 的直接回复两个都会看错。
- **只有评审能 resolve**。构建者的 resolve 不算数，verify-a 一直是 open。
- **resolve 之后（同一秒也算）的评论重新打开线程**，不论是谁、在哪一层。handoff-a 里构建者在评审 resolve 之后又标了 resolve，这本身就是一条更晚的评论；测试第二组的 assume-b 里，评审自己 resolve 之后又追问了一句，线程也重新打开。
- **看评审最后一次 resolve，按时间取**。verify-b 被 resolve、构建者回复、再被 resolve，而两次 resolve 在输入里是倒着排的。参考实现取 `max(at)`；取第一次，或者遍历时用后出现的覆盖前面的，都会把它判成 open。
- **self_resolved**。仍然 open，并且构建者在评审最后一次 resolve 之后（或评审从没 resolve 过）标了 resolve。fit-b 里构建者先标、评审后来认可，已经 resolved；scope-a 里构建者的标记早于评审的 resolve，后来被别的回复重新打开，都不算。
- **输出**。线程按 finding 的时间排，self_resolved 也按这个顺序（输入里 handoff-a 在 verify-a 前面）；open_by_dimension 先放好 rubric 的每一维、初值 0，再累加；finding 的维度不在 rubric 里、回复指向不存在的评论，都报 ValueError，并写出那条 finding 或回复自己的 id（c12，不是它指向的 c404）。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着结论找到是哪个打分器给错了分、哪个打分器漏读了输入里的一项（人后来批准的扩大范围），或者分数都对、是结论漏了一条规则，看出“每次读取都重新评审”这种按调用次数计费的浪费；能设计一个只追加、内容寻址、往返精确的报告历史；能把带证据的评分和两个评审的合并规则写对，包括封顶、取整、escalate 和阈值边界；能用冻结快照把评审和构建者隔开，并按回合流式输出；能处理乱序输入里任意深度的回复树。

它不涉及真正的模型打分：打分器、评审和构建者都是脚本，rubric 的锚点描述、置信度下限、校准集上的一致率、位置偏差的缓解，都需要接上真实模型以后才能验证。它也不涉及真实的 git diff、PR 评论 API、多个进程同时写报告历史，以及讲义里 Cloudflare 那种专家评审加协调者的架构。
