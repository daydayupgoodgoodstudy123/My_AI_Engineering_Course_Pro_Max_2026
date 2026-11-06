# 参考答案讲解：HandoffPkt（14/40）

计时结束后再看。参考实现在同目录的 `handoffpkt/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修交接包生成器

**现象**：解锁后的第一个错误是 `review_total` 里的 `AttributeError: 'NoneType' object has no attribute 'get'`，可这个辅助函数只是被调用的那一方。

**顺着往上找**：`generate_handoff` 调 `build_payload`，`build_payload` 调 `derive_risks`，`derive_risks` 把 `snapshot.review` 原样交给 `review_total`。这次会话没有 reviewer 运行，review 是 None。`review_total` 照搬课里的写法，`review.get("total", 10)`，转不成整数也算 10 分。这一层想练两件事：报错的位置不是出错的位置；把报错消掉（`review or {}`）不等于修好，缺报告会被读成满分，风险被悄悄吞掉。

**依次修五处**：

1. **缺评审是风险**。`derive_risks` 先判断 review 是不是 None，是就加一条 `review report missing`；total 不是整数（`"n/a"`）也是一条 warn 风险；低于 7 分才是 `review total 5 below 7`，正好 7 分不算。没人写的评审报告，永远不能当成通过。
2. **没有退出码也是失败**。`failed()` 是课里的 `not in (0, None)`，超时的那条命令既不进 `failed_attempts`，也不进 `feedback_tail`。改成 `exit_code != 0`。None 代表命令没给出答案，下一个会话最该知道的恰恰是它（第 37 课遇到 None 拒绝推进，第 38 课把它列为 block）。被信号杀掉的命令退出码是负数（第 7 条记录是 -9），同样是失败，所以也不能写成 `exit_code is None or exit_code > 0`。
3. **裁剪保持日志顺序**。课里的 `trim_feedback` 先放最后 k 条、再放所有失败，顺序乱了。按下标判断最直接：

   ```python
   start = max(len(records) - k, 0)
   return [record for i, record in enumerate(records) if i >= start or failed(record)]
   ```

   不要按相等去重或排序：两次一样的运行是两条记录，`r in keep` 会把相等的旧记录带回来，`records.index` 找到的是第一条相等的记录。`records[-k:]` 在 k=0 时是整个日志，用下标也就没有这个问题。
4. **Markdown 只从 payload 渲染**。`render_markdown` 多了一个 `state` 参数，next action 取的是状态原文，里面有换行和缩进；payload 里的那句已经压成一行。去掉参数，只读 payload。测试会用 handoff.json 单独重渲染一遍 handoff.md，要求逐字相同，这就是课里 “If they diverge, the JSON wins” 的意思：Markdown 是 JSON 的渲染，不是另一份来源。
5. **预算一次找准**。交接包的字节数随保留的命令条数单调增长，所以可以二分：

   ```python
   if size_keeping(len(commands)) <= max_bytes:
       return payload
   if size_keeping(0) > max_bytes:
       raise PacketTooLarge(...)
   fits, too_big = 0, len(commands)
   while too_big - fits > 1:
       middle = (fits + too_big) // 2
       if size_keeping(middle) <= max_bytes:
           fits = middle
       else:
           too_big = middle
   size_keeping(fits)
   ```

   原来的循环每丢一条命令就把整个包重新序列化一次，3500 条命令要 1.1 秒左右；二分只序列化十几次，约 4 毫秒。也可以从最新的命令往回累加每条命令的字节数，最后实测一两次，但要算准缩进、逗号和 `commands_omitted` 的位数。从零条开始每次多放一条、整体重新序列化，这道题里约 17 毫秒，也能过，可它的次数随留下的条数增长：默认 64 KiB 的预算要 250 毫秒左右，二分仍是 7 毫秒。

**护栏**：

- 放得下指的是整个 handoff.json：只拿 commands_run 的大小去比，或者二分停在第一个放不下的位置，文件都会超。
- 尽量多留：再多一条就放不下。“只留最近 100 条”或者一次丢 50 条都更快，但会丢掉放得下的命令。
- 留下的是最新的命令，按原顺序；`commands_omitted` 记下丢了几条，handoff.md 在预算之后渲染，最后一行写明有多少条在完整日志里。
- 失败记录永远不丢。预算正好等于零条命令的大小时成功，再少一个字节就报 `PacketTooLarge`。为了凑预算删掉 `failed_attempts` 或 `feedback_tail`，正是这一关要拦住的写法。

起始代码里已经正确的部分测试也在守着：没有或只有空白的 next_action 报 `NoNextAction`（课里的代码填一句占位文字，测验 Q10 说那样只是形式上满足，实际是状态报告）；`changed_files` 是 `sorted(set(...))`，换一个进程 set 的顺序就变，排序才能幂等（测验 Q11）；命令用 `shlex.join` 渲染成能复制执行的一行，而不是 `str(list)`（测验 Q10）。

## Part 2 交接包历史

参考实现：

- `sessions()` 用正则 `session-([0-9]{4,})\.json` 对整个文件名做 `fullmatch`，把数字转成整数再排序。目录不存在时返回空列表。
- `save()` 先去掉包里的 `session` 和 `previous`，和最新一份去掉这两个键以后的内容比较，相同就直接返回最新的编号。否则编号是最大值加一，previous 是最大值（第一份是 None），先 `json.dumps` 成文本，再写临时文件、`os.replace` 到 `session-{number:04d}.json`。
- `load()` 读文件，不存在就报 KeyError；`latest()` 读编号最大的那一份。

要点：

- **编号来自磁盘上的会话文件**。只认 `session-<nnnn>.json`，从文件名解析出整数。目录里还有 session-0001.md、编辑器的备份 session-0001.json~ 和 notes.txt：`glob("session-*")` 会数出三个 1，`re.match` 不锚定结尾会把备份也算进去，数文件个数会跳号。补零到四位让 `ls` 列出来的顺序和编号一致，但排序和找最新的一份仍然按整数，不按文件名。
- **previous 用 null**。第一份没有上一份，写 0 的话，Part 5 会把它当成一份缺失的会话。
- **幂等只看最新的一份**。会话结束的 hook 可能触发两次，第二次不该多出一份。比较时要去掉历史自己分配的两个键；和更早的某一份相同，说明任务回到了从前的状态，是新的会话；任何字段不同都是新会话。
- **session 和 previous 由历史分配**，包里带来的旧值要替换。这样“读回最新一份、改一句 next_action、再保存”才会正确地成为下一份。

## Part 3 清理检查

参考实现按课里那张表的顺序跑五项检查，每项按自己输入的顺序报告。每一行怎么匹配，docstring 都写明了，这一关要想清楚的是下面四处：

1. **工作区要数全**。每一行 `git status --porcelain` 报一条，未跟踪的 `??` 也是。课里的标准是 every change committed or explicitly stashed with a note：未跟踪的文件既没提交也没 stash，下一个会话打开时它就在那里，分不清是有意留下的还是忘了删。`?? notes/window.tmp` 在临时产物里还会再报一次，两项检查各读各的输入，不互相去重。暂存了没提交的改名也是未提交：状态码有两列，第一列是暂存区，第二列是工作区，`R  ` 的第二列是空格。路径从第 4 个字符开始取，不能先 `strip()`，否则 ` M app/signup.py` 会少掉一个字符。
2. **diff 的行号按新文件算**。下一个会话要在新文件里找到那一行，所以从 hunk 头 `@@ -a,b +c,d @@` 的 `c` 开始数：上下文行和新增行各加一，删除行在新文件里不存在，不加；先判断这一行，再加一。`app/signup.py` 第二个 hunk 的旧起点是 40、新起点是 41，因为前一个 hunk 净增了一行。路径取自 `+++ b/`：新文件的 `--- ` 行是 `/dev/null`；删掉的文件 `+++ ` 是 `/dev/null`，它的行全是删除行，本来就不报。
3. **看板要和发生的事一致**。多于一个 in_progress 报一条，按看板顺序列出，只有一个是正常状态；这次会话完成的 feature，看板上不管还写着 in_progress 还是 todo，都要报；active 还指着一个已经 done 的 feature，就是课里说的 stale board，下一个会话会被派去做已经做完的事。最后这一条看的是看板上的状态，不是 finished：signup-form 是以前的会话做完的。
4. **分支**。分离 HEAD 时没有当前分支，也就谈不上是不是预期的分支，只报一条 `detached HEAD`。没有合并、又不是基础分支和预期分支的，是孤儿分支。预期分支上的工作本来就还没合并，要按预期分支排除；拿当前分支代替，分离 HEAD 时预期分支就会被报成孤儿。

其余几处照 docstring 做：改名取 ` -> ` 后面的新路径；failed 和 error 是红，skipped 不是，open risk 的 `"test"` 和 node id 完全相同才不算阻塞；路径里除文件名以外有一段叫 `scratch`，就报到这一段为止的目录，只报一次，目录里的文件不再单独报；其余文件名以 `.tmp` 结尾的报 temp file；这两种在同一遍 files 里报，所以按 files 的顺序交错；调试 print 只看 .py 文件里新增的行，去掉缩进以后以 `print(`、`pprint(` 或 `breakpoint(` 开头才算；stash 的消息以 `WIP on <branch>:` 开头就是没写说明，那是 git 在不带 `-m` 时自己写的。

数据里放了几处名字相近的东西，照 docstring 的匹配方式做自然不会报，测试顺带守着：`app/tmpl/signup.html`、`app/scratchcard.py`、`app.register_blueprint(`、`print_table(rows)`、说明里写了 “WIP on” 的 stash@{1}，以及和 `test_burst` 同前缀的 `test_burst_window`。

clean_state 的结果交给 `generate_handoff(snapshot, clean_state=...)`，非空就报 DirtyWorkbench。课里把它写成前置条件而不是习惯，因为习惯在难熬的一天会被跳过。

## Part 4 单遍裁剪

```python
window = deque()
for record in records:
    window.append(record)
    if len(window) > k:
        oldest = window.popleft()
        if failed(oldest):
            yield json.dumps(oldest, ensure_ascii=False) + "\n"
while window:
    yield json.dumps(window.popleft(), ensure_ascii=False) + "\n"
```

- 一条记录离开最后 k 条的窗口时，它前面要保留的记录都已经写出去了，这时写它不会打乱顺序；它若是成功记录就直接丢掉。
- 失败记录一到就写会打乱顺序（前面可能有会留在最后 k 条里的成功记录）；攒到最后再写就不是流式，也不是有界内存。
- 内存里最多 k+1 条记录。k=0 时每条记录一进来就离开窗口，只剩失败记录。
- 失败的判断直接用 Part 1 修好的 `failed()`：None 和 -9 这样的负数退出码都是失败。

## Part 5 分支交接链

1. 按会话号建索引，同时检查：编号重复、previous 不存在（BrokenChain，写出缺的编号）、previous 不早于自己（指向自己也算，所以是 `>=`）。
2. 按编号从小到大走一遍，每条分支记下最后一个编号，这就是它的头。较早的包被取代，即使它是叶子。
3. 从头沿 previous 走到根，倒过来就是 lineage，可以跨过分支。
4. 按 lineage 的顺序处理风险：先把这一份的 open_risks 按 id 写进一个 dict（已有的 id 原位替换），再删掉它 closed_risks 里的 id。重新打开的风险会插到最后。dict 的插入顺序正好就是要求的输出顺序。替换是给这个 id 换一个值，不是 `.update()` 旧的那份风险：那份 dict 属于调用方传进来的包，改了它，第 1 次会话的记录就变了。
5. 结果按头的会话号排序。

只走头自己的那条链，是“分叉后各自携带”的关键：api 在 s6 关闭 R-2，不影响 ui。课里说 One active handoff per branch and topic，只有 active 的那份驱动下一个会话；这里每条分支的头就是那份 active 的交接包。

## 这套题证明了什么，没证明什么

通过了说明你能在交接包生成器里顺着调用链找到缺评审、缺退出码、裁剪顺序和两种形式不一致的问题，能看出按字节预算裁剪时的平方级写法并改对；能把每次会话的交接包存成可回溯的 JSON 快照并做到幂等；能把 Leave a clean state 的五项检查落成精确的规则；能单遍、有界内存地裁剪任意长的 feedback 日志；能在分叉的交接链上按 id 携带风险。

它没有涉及真实的 git 仓库和真实的 agent 运行时：仓库快照是测试写好的数据，会话结束钩子、PR 模板、跨产品交接（Claude Code 接 Codex）都没有考。compaction（Codex 的 compact 端点、Claude Code 的五阶段压缩）不在本课范围。注释掉的代码块这一项清理检查没有考，因为它没有不靠启发式的精确规则。
