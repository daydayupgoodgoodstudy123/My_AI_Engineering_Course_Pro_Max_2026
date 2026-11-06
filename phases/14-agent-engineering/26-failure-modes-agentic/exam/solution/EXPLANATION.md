# 参考答案讲解：FailTag（14/26）

计时结束后再看。参考实现在同目录的 `failtag/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修检测器

**现象**：解锁后第一个失败是 "a write verb only counts as a whole word of the request"：总结一份 credit memo 时写了文件，却没有标 scope_creep。

**依次修四处**：

1. `mentions`：`re.search(verb, request)` 是子串匹配，credit 里有 edit，于是这次写入被当成用户要求的。改成按词比较：`re.findall(r"[a-z]+", request.lower())` 取出单词再查，或者给正则两边都加 `\b`。只在前面加的话，saved 还是会被当成 save。课里 `detect_scope_creep` 的 `w in request` 是同样的问题。
2. `parse_constraint`：修好第 1 处后，报错变成 `violates` 里的 TypeError：`argument of type 'NoneType' is not iterable`。`violates` 本身没有错，问题在上游：遇到 "do not exceed 5 searches" 这种动词不在 VERB_TOOLS 里的约束，`parse_constraint` 返回了 `Rule(tools=None)`，而 docstring 说这种约束不是工具规则，应该返回 None。在 `violates` 里绕开 None 也能让这一条通过，但测试接着会直接检查 `parse_constraint`。这一关想练的是：报错的位置往往不是出 bug 的位置。
3. `detect_cascading_errors`：原代码把失败之后所有带 `${N}` 的调用都算成下游，引用的是别的步骤也算。条件要改成 `i in references(later)`。
4. 改完第 3 处，长 trace 的计时断言挂了：每个失败步都把后面所有步骤的 `references()` 重算一遍，O(S²)，4000 步在本机要 1.2 到 1.6 秒。先扫一遍，统计每一步被多少个调用引用，再看失败步的计数，就是 O(S)，约 3 毫秒。只把 `references()` 缓存起来、仍然两层循环，复杂度没变，本机 40 到 130 毫秒，时过时不过。

**护栏**：

- "Edit the README." 和 "then SAVE." 都必须算写入。只用 `split()` 会留下标点，没转小写会漏掉大写。
- 提速时不能只看后面几十步：测试里的消费者在 2000 步之后。
- 一个调用里两次用到失败结果，只算一个消费者。按 `${N}` 出现次数计数会把它算成两个。`references()` 返回的是集合，正好不会重复。
- 一遍计数时只数 tool call，并且每个失败步分别计数。message 引用了失败结果不算消费者；两个失败步各被一个调用用到，也不是级联。

## Part 2 trace 存储与基线

目录结构：`traces/<tid 的 sha256>.json` 每个 trace 一个文件，文件里存 `{"trace": asdict(trace), "labels": labels}`；`BASELINE` 存基线的 tid 列表。

容易漏的几点：

- **文件名**：tid 是运行时给的任意字符串。直接拼成文件名，"run/7\n" 变成了子目录；百分号编码在大小写不敏感的文件系统（macOS、Windows 默认如此）上会让 "T001" 和 "t001" 共用一个文件。sha256 的十六进制只有小写字母和数字，两个问题都没有。tid 本身存在文件里，`tids()` 读出来再排序。
- **原样读回**：`asdict` 会把嵌套的 TraceStep 也转成 dict，读回时要用 `TraceStep(**step)` 还原。JSON 能原样保存 `0.1 + 0.2`、大整数、None 和各种 Unicode 字符。标签列表保持原顺序。
- **原子替换**：用 `tempfile.mkstemp(dir=同一目录)` 写临时文件，写完 `os.replace`。读者要么看到旧基线，要么看到新基线。替换失败时删掉临时文件再把异常抛出去。临时文件必须和目标在同一个文件系统上，`os.replace` 才是原子的。
- **没有基线**：`baseline()` 返回 None。基线里的 tid 必须都已经存过，否则报 ValueError，旧基线不动，所以要先检查再写。
- **基线的格式**：也存成 JSON 列表。一行一个 tid 的话，测试里结尾带换行的 "run/7\n" 读回来就不一样了。

## Part 3 漂移与构建闸门

- `mode_rates`：每种模式出现在多少条 trace 上，除以 trace 总数。没有标签的 trace 也在分母里，同一个 trace 里重复的标签只算一次。
- `build_gate`：`count / n >= threshold`。两个都是精确的有理数时，`count / n` 和 `threshold` 都取最接近的那个 double，相等就是相等。写成 `count >= threshold * n` 会出错：0.07 × 200 = 14.000000000000002。
- `check`：
  1. 没有基线就报 LookupError。课里说，没有 last-known-good 就没法说“变坏了”。
  2. 窗口不足 min_traces 条不下结论。
  3. 当前占比比基线高出超过 tolerance 才算漂移，正好高出 tolerance 不算（测试里 1/20 = 0.05 对基线 0）。变少不算。
  4. 基线冻结。每次 check 都换成当前窗口的话，4%、8%、12% 一步一步涨，每一步都在容差内，永远不会告警。
  5. 冷却按模式记录最后一次真正发出告警的时间。每次发出都更新，被压下去的那次不更新；`now - last >= cooldown_s` 时可以再发。
  6. 告警按模式排序，不按模式在窗口里首次出现的顺序。

端到端的部分把 Part 1–3 串起来：课里的 7 条 trace 打标后存进去（t004 的后续调用改成引用失败搜索的结果，才算级联），确认成基线；再来 7 条同时写了文件又违反“do not modify any files”的 trace，告出 context_loss 和 scope_creep 两条，基线占比都是 2/7。

## Part 4 在线 syslog

课里的 gates at every step 是每走一步就查一步。这一关把 Part 1 的检测器拆成逐步判定：每个 trace 一份状态，按 tid 存，里面是用户请求、解析好的规则、步数、失败步集合、每个失败步的消费者计数、已经报过的模式。

```python
async for event in events:
    if isinstance(event, Start):
        open_traces[event.tid] = _Open(...)
        continue
    state = open_traces[event.tid]
    ...  # Step: 按 DETECTORS 顺序判定这一步能判定的模式；End: 只判 success_hallucination
    for mode in modes:
        if mode not in state.reported:
            state.reported.add(mode)
            yield syslog_line(mode, clock(), host, params)
```

- **状态按 tid 分开**：测试里 a、odd、c 三个 trace 交错到达。已报集合共用的话，c 的 scope_creep 会被 a 吞掉；共用一个集合、每次 Start 清空的话，a 在 c 开始之后的那次写入会把 scope_creep 和 context_loss 再报一遍。失败步、消费者计数和步号也都放在各自的状态里：失败步共用的话，a 第 2 步的 `${1}` 会被算成 odd 那个失败步的消费者；步号共用的话，odd 的 `${1}` 就对不上它自己的第 1 步。
- **每种模式每个 trace 只报一次**：a 的第 2 步写文件没带 content，同时触发 scope_creep、context_loss 和 tool_misuse，只有 tool_misuse 是新的。所以已报集合跟着 trace 走，不能每一步重开；同一步触发的几种模式也都要报，按 DETECTORS 顺序，a 的第 1 步就是两条。
- **success_hallucination 只在 End 判定**：成功声明和目标状态随 End 一起到达，所以这一条只带 tid。动词表和 Part 1 一样是 SUCCESS_VERBS，odd 的请求 "make a README" 里的动词只有 make。
- **PRI**：`FACILITY * 8 + SEVERITY[mode]`。local0 是 16，所以 critical、error、warning 分别是 130、131、132。
- cascading_errors 在第二个消费者到达的那一步判定。和 Part 1 一样只算直接引用、只算 tool call、每个失败步分别计数。四种逐步判定的模式都要在线判，包括 tool_misuse。
- 一判定就 `yield`，所以第一个 hallucinated_action 出来时只拉取了两个事件。
- 参数值的转义照 docstring 的顺序：先转义反斜杠，再转义引号和右方括号。顺序反了，`b"]\` 会变成 `b\\"\]\\`，解析器读到 `\\"` 就以为值结束了。测试里的 tid `b"]\` 和工具名 `magic"scan]` 用来确认这一点。
- 时间戳：`datetime.fromtimestamp(t, timezone.utc)`，`%f` 取前三位，再加 Z。测试里的时刻都是 0.25 的倍数，截断和四舍五入结果一样。
- 格式由测试的解析代码决定：整段文本以换行结尾，按 `\n` 切开后每一行都要完整匹配 RFC 5424 的正则，参数值按 RFC 5424 6.3.3 只允许 `\"`、`\\`、`\]` 三种转义。

## Part 5 级联半径

1. 先建图：第 j 步引用了第 i 步，就加一条 i → j 的边。i 不满足 `0 <= i < j` 就报 ValueError。这样建出来的图一定无环，步骤下标就是拓扑序。
2. 对每个失败步，用显式栈做 DFS，求出它影响到的所有步骤（集合，菱形只算一次）。遇到下游的失败步要接着往下走。不能递归：3000 步的长链会超过默认的递归深度。
3. 根因是不在任何失败步影响集合里的失败步。只看直接父节点不够，测试里 email.send 的失败隔着一个成功的 shipping.create。结果没人用到的失败也是根因，radius 和 depth 都是 0。
4. 对每个根因，按下标顺序遍历受影响的步骤，`depth[j] = 1 + max(depth[i])`，i 取 j 引用的、已经在根因的影响范围里的步骤。这是 DAG 上的最长路径，一遍就够。BFS 给出的是最短跳数。
5. 系统只从受影响的 tool_call 里取 `name` 点号前面的部分，message 不算系统，但算进半径。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试按规则写的检测器、把带嵌套参数的 trace 原样存进目录并原子更新基线、写有冻结基线和按模式冷却的漂移告警、写在交错到达的多个 trace 上逐步判定、逐条输出 RFC 5424 的异步生成器，以及在依赖 DAG 上算传播范围和最长路径。它不涉及课里 MASFT 的 14 种模式和三大类、Microsoft 的风险分类，也不涉及真实 trace 平台（Phoenix、Langfuse）的接入和用分类器做内容级判断。这些需要另外读课和动手。
