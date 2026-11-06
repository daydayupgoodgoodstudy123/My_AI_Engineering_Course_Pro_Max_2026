# 参考答案讲解：Surfaces（14/31）

计时结束后再看。参考实现在同目录的 `surfaces/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修运行对照和失败报告

**现象**：解锁后的第一个错误是 json 编码器里的 `TypeError: Object of type set is not JSON serializable`，而 `json` 模块和 `write_report` 本身都没有 bug。

**顺着往上找**：traceback 从测试进 `compare`，再进 `write_report` 和 `json.dumps`，最后停在 `JSONEncoder.default`。那一帧的局部变量 `o = {'feedback', 'handoff', 'instructions', ...}` 是七个面的名字，说明报告里有一个字段是集合。报告由 `failure_report` 组装，`missing_surfaces` 和 `symptoms` 都来自 `RunResult.missing_surfaces()`，而它返回的是 `set(...).difference(...)`。出错的地方离根因隔了两层调用，根因所在的函数甚至不在 traceback 里。这一关想练的就是这一点：报错的位置往往不是出 bug 的位置。

**依次修五处**：

1. `missing_surfaces` 按 WORKBENCH_SURFACES 的顺序返回列表，就是课里那行列表推导式。只加一层 `sorted()` 会得到字母序，和讲义表格的顺序不一致。
2. `failure_report` 的允许集用 `set(task.allowed_files)`。课里的 `{"app.py", "test_app.py"}` 只对那一个任务成立，换成登录限流的任务后，三个允许的文件全被当成越界（测验 Q9 问的就是这件事）。禁止的文件单独列在 `forbidden_writes` 里，`off_scope_writes` 只放任务既没允许也没禁止的文件。
3. label：没有面是 prompt-only，七个面齐全是 workbench，其余是 partial。课里的写法只要有一个面就叫 workbench。三种情况都要留着，测试也读 failure_modes.json 里 prompt-only 的 label。
4. verification 读 feedback 捕获的那次测试运行，没有就 fail closed。课里的 stub 只看有没有 verification，于是只开 verification、从没跑过测试的运行也“证明”了通过（测验 Q6）。要改在 stub 里：这次运行的 `actually_passing` 是 False，`unverified_success` 才跟着是 True。只改 `failure_report` 里 `unverified_success` 的算式，stub 照样把它记成通过。
5. 越界列表和禁止列表都用一遍扫描得到：

```python
for path in dict.fromkeys(result.files_touched):
    if path in forbidden:
        forbidden_writes.append(path)
    elif path not in allowed:
        off_scope.append(path)
```

原来的写法先做集合运算，再用 `sorted(..., key=result.files_touched.index)` 恢复写入顺序。`list.index` 每次从头扫描，对 16,000 个越界文件就是上亿次比较，24,800 次写入的 codemod 要 1 秒多，一遍扫描约 1.5 毫秒。允许和禁止都要用集合查：两份清单各有 8,000 项，在 `task.allowed_files` 或 `task.forbidden_files` 这个列表里逐个找，同样要 0.3 到 0.8 秒。

**护栏**：

- 只把 stub 已知会乱写的 README.md 和 scripts/release.sh 当成越界，或者“没禁止就算允许”，都会漏掉幻觉写入的 CHANGELOG.md。越界的定义是对照任务自己的允许清单。测验 Q9 的参考修法把禁止的文件也放进 `off_scope_writes`，这里 docstring 要求分开列，越界断言会抓住。
- 为了提速改成 `sorted(set)` 或 `list(set)`，写入顺序就丢了；去掉 `dict.fromkeys`，写了两次的 README.md 会出现两次。
- “跑过测试就算通过”也不对：只有 scope 和 feedback 的运行没有闸门，课里的 stub 把它记成没有通过，`unverified_success` 应该是 True。

## Part 2 体检记分卡

一份追加写的 CSV：表头是 `COLUMNS`，之后一次体检一行。

```python
def record(self, audit: Audit) -> None:
    _validate(audit)
    new = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
    row = [audit.repo, audit.audited_at, *(audit.scores[s] for s in WORKBENCH_SURFACES), audit.notes]
    with open(self.path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(COLUMNS)
        writer.writerow(row)
```

容易漏的几点：

- **拒绝打分不是 0 分**。`outputs/skill-workbench-audit.md` 的拒绝规则写着：仓库连测试命令都没有，就拒绝给 verification 打分，并作为阻塞问题报出来。0 是“这个面缺失”，None 是“拒绝打分”。`csv.writer` 把 None 写成空字段，读回时空字段要变回 None，不能用 `int(v or 0)`。
- **先校验、后写入**。scores 必须正好覆盖七个面：少一个面时用 `scores.get(s)` 会悄悄写成空字段，看上去像拒绝打分；多一个面（练习 3 的第八个面）会被静默丢掉。两种都报 ValueError。分数只能是 0、1、2 或 None，3 和 -1 都要拒绝。没有 UTC 偏移的时间也要拒绝，否则无法和别人的体检排序。所有检查都在打开文件之前做完，被拒绝的体检不能改动文件。
- **分数按列取**。一行里的分数按 WORKBENCH_SURFACES 的顺序从 `audit.scores` 里取。scores 是 dict，键的顺序由写它的人决定：acme/web 那条把 handoff 写在最前面，照 `audit.scores.values()` 写，它的 1 分就落进了 instructions 那一列。
- **按时间点排序，保留原文**。`history` 用 `datetime.fromisoformat` 解析后排序，`sorted` 是稳定排序，同一时刻的体检保持记录顺序。测试里有一对同一时刻、偏移不同的体检：拿文本做第二排序键会把 -08:00 的那条排到前面，用以时间点为键的 dict 收集会丢掉一条。按文本排时，`2026-03-13T17:30:00-08:00` 排在 `2026-03-14T00:15:00+00:00` 前面，实际上它晚 75 分钟。为了让文本可排序而把 audited_at 改写成 UTC，又会让往返不再原样。
- **只追加**。之前的行一个字节都不变，表头只在文件为空时写一次。是否写表头要看文件本身，不能看实例上的标记：测试用新开的 Scorecard 追加第三条体检。“为空”也包括文件已经存在、却一个字节都没有的情况（刚创建就崩溃会留下这样的文件），所以参考实现看的是文件大小，不只是存不存在。备注里的逗号、双引号和换行交给 csv 模块，读写都用 `newline=""`。

## Part 3 拦截矩阵和下一步

每个失败沿着流程走，第一个在场、而且在它的 catchers 里的面拦住它：

```python
stop = next((s for s in FLOW_ORDER if s in present and s in failure.catchers), None)
```

FLOW_ORDER 是讲义流程图的顺序：scope、state、instructions、feedback、verification、review、handoff。instructions 不在图上，它是“attached to the runtime's startup”的策略，所以放在 agent loop 那一站。它和表格顺序（WORKBENCH_SURFACES）在前三个面上不同，`forbidden write` 就是用来区分这两种顺序的。没有 catchers 的失败（wrong acceptance criteria）在七面齐全时也会逃逸，要列在 `escaped` 里，不能丢，也不能算到哪个面头上。

`next_surfaces` 回答 audit skill 里的问题：先补哪个缺失的面，能消掉最多的失败模式。做法是贪心：

```python
while len(picks) < limit:
    gains = {s: sum(s in f.catchers for f in remaining)
             for s in FLOW_ORDER if s not in present and s not in picks}
    best = max(gains, key=gains.__getitem__, default=None)
    if best is None or gains[best] == 0:
        break
    picks.append(best)
    remaining = [f for f in remaining if best not in f.catchers]
```

- 只数还在逃逸的失败。已经被在场的面拦住的失败，加不加新面都一样。
- 选中一个面以后重新计算。review 加上以后，off-scope edit 已经被拦住，verification 的收益从 2 降到 0，第二个该补的是 state。静态计数或者只算第一轮，都会得到 review、verification、scope。
- `max` 在并列时返回先遇到的键，`gains` 按 FLOW_ORDER 建，所以平局归流程上靠前的面。`Counter.most_common` 按计数时先遇到的顺序破平局，七个面全缺时第三个会选成 verification，正确的是 feedback。
- 收益为 0 就停，不凑满 limit 个。

最后一段是端到端检查：`WorkbenchService.next_surfaces` 取第 2 关的最新一次体检（按时间点，不是文件最后一行），只把 2 分的面算作存在，再交给 `catch_matrix`。

## Part 4 运行事件监控

用一个按 seq 存的缓冲区，再加一个“下一个该检查的 seq”：

```python
async for event in events:
    if event.seq < next_seq or event.seq in waiting:
        continue  # a redelivery
    waiting[event.seq] = event
    while next_seq in waiting:
        for violation in checks(waiting.pop(next_seq)):
            yield json.dumps(violation) + "\n"
        next_seq += 1
```

- 队列是至少一次投递，所以会乱序、会重复。检查按 seq 顺序进行，每个 seq 只检查一次。迟到的重复事件 seq 小于 next_seq，直接丢掉。
- 检查顺序决定结论：第 9 步的 claim 要看第 8 步那次没有捕获退出码的 run，按到达顺序检查就会拿第 6 步的通过去判；end 要在 handoff 之后检查，否则会报一条假的“没有交接”。
- 违规一旦能判定就 `yield`。探针先发 seq 2，再发 seq 1，后面还有 297 条；seq 1 到达时两条一起检查，seq 2 的越界写入马上输出。先读完整个流再排序，结果对，但违规全都压到了最后。缺 handoff 也一样：检查 end 时就报。第二个探针只有一条 end，队列随后一直重投它，把这条违规留到流结束再报就得先读完全部重投。
- 每个检查都很浅：越界路径记在一个集合里，只报第一次，禁止的文件也在允许清单之外，同样要报；claim 看最近一次 run，`exit_code` 不是 0 就报，None 也报（`code != 0`，不是 `if code`），每个 claim 各判各的，同一次失败之后的第二个 claim 照样报；end 之前没有 handoff 就报。
- 流结束时缓冲区里还有事件，说明有 seq 一直没到。报 ValueError，写出缺的序号，不能静默丢掉。只写没到的：缓冲区里有 6、8、9，缺的是 5 和 7，不是 `range(5, 9)`，也不是“5 到 8”这样的区间。

## Part 5 线束原语检查

先递归遍历一次，把每个组件和每个函数按完整路径放进一张表：

```python
def walk(node, path):
    nodes[path] = node
    if node["kind"] == "runtime":
        for name, child in node.get("children", {}).items():
            walk(child, f"{path}/{name}" if path else name)
    elif node["kind"] == "worker":
        for name, function in node.get("functions", {}).items():
            nodes[f"{path}/{name}"] = {"kind": "function", "to": list(function.get("to", []))}
```

然后在这张表上做四项检查：

- **unresolved**：每个 ref（trigger 和 queue 的 to、trigger 的 on、函数的 to）都要在表里，找不到就报在持有它的组件或函数上。这份描述里断了三处：lint_hook 的 to 和 on，以及 reviewer/review 写入的 review_report。
- **no_function**：从 trigger 出发，沿 queue 一路往下走，终点必须是函数。指向 worker 不算。queue 成环时要用 seen 集合停下来，写成不带 seen 的递归会 RecursionError。
- **no_policy**：每个 worker，不论嵌套多深，都要有 policy。讲义把 scope 映射成授权策略。
- **open_loop**：讲义说 “The loop closes on the state file, not on chat history”。边从 store 指向在它上面触发的 trigger，从 trigger 和 queue 指向各自的 to，从函数指向它写入的每个 ref。只要有一个 durable store 能沿着边回到自己，环就闭合了。chat 的环不 durable；agent_state 被 handoff 写入，但没有路径能回到 handoff，也不算。feedback_log 经 on_feedback 触发 act，能走进 chat 的环，却回不到 feedback_log 自己，同样不算：要找的是一条从 store 出发、回到这个 store 的路径，不是“从 store 出发能不能遇到环”。后者是三色 DFS 的标准写法，在这里会把 chat 的环当成闭环。补上 plan 发出的 session_end trigger 之后，agent_state → startup → plan → session_end → handoff → agent_state 成环，open_loop 消失。

结果用 `sorted` 按 (path, code, detail) 排序，和遍历顺序无关。detail 也要参与排序：lint_hook 的两条 unresolved 里，sandbox/checkout 排在 sandbox/linter/run 前面。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试一条离根因很远的报错，能设计一份只追加、往返原样的 CSV，能实现首个拦截和贪心选择，能写一个按序号重排、去重并即时输出的异步消费者，能在嵌套结构上做引用解析和带环的可达性检查。它不涉及真实的 LLM agent 和真实仓库：agent 是课里的规则桩，拦截表是测试给的数据，不是测出来的效果。它也不实现任何一个面的细节：状态文件、规则、范围合同、反馈日志、验证闸门、评审和交接，是这个迷你系列后面第 32 到 42 课逐个去做的。
