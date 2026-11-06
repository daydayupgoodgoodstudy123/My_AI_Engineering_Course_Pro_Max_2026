# 参考答案讲解：EvalGate（14/30）

计时结束后再看。参考实现在同目录的 `evalgate/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修评测框架

**现象**：解锁后的第一个错误是 `replay.py` 里的 `LookupError: session 'sess-0412' recorded 1 turn(s); the eval asked for turn 2`，而 `Replay` 本身没有 bug。

**顺着往上找**：`Replay` 回放的是一段生产会话，里面只有一轮输出：agent 把 SSN 转发给了下游。问它要第二轮的是 `evaluator_optimizer`。这个 guardrail 用例写着 `refine=False`，docstring 说这种用例只有一轮，因为第一轮的输出已经作用到外部了：SSN 已经发出去，第二轮改口拒绝也撤不回来。代码却照课里的写法跑满 `max_rounds`。这一关想练的是：报错的位置往往不是出 bug 的位置。把 `Replay` 改成“录完了就重复最后一轮”，等于改坏了证据，后面的断言照样会挂。

**依次修四处**：

1. 轮数上限：`refine=False` 时只跑一轮。依据是 `refine` 字段，不是类别。`custom_c002` 是发周报邮件的用例，也是一轮，按 `category == "online"` 判断会在它的 Replay 上再挂一次。
2. 下一轮 proposer 要拿到上一次失败 judge 的 `reason`，不能拿到被拒绝的 `candidate`。benchmark 的“missing sticks”和 citation 的诊断都是反馈的一部分。每轮替换成最新 reason，原样保留空白和 Unicode；附加用例连续给出两条不同诊断，防止只保存第一条。`run_suite` 已经在每次运行时新建用例，闭包计数和 Replay 请求断言检查每次运行的独立性。
3. 失败分支的 rounds：课里的代码返回 `case.max_rounds`，只跑了一轮的用例也报 3 轮。要返回实际跑了几轮。
4. `FlakyTracker.record` 每记一次都把整段历史按 id 筛一遍，是 O(N²)，15000 次运行要 1 秒左右。每个用例只保留最近 window 次结果，一个有界的 deque 加一个通过计数就够了：

```python
if len(recent) == self.window:
    self._passes[cid] -= recent.popleft()
recent.append(result.passed)
self._passes[cid] += result.passed
```

**护栏**：所有用例都改成一轮会挂，可以修订的用例还要靠 judge 的反馈通过；捕获 `LookupError` 来结束循环会挂，agent 被多问了一次；`run_suite` 要整个套件跑完一遍再跑下一遍，同一个用例连着跑会挂；所有用例共用一个窗口会挂，窗口要按用例各算各的；旧的运行不滑出窗口会挂，用例稳定 window 次以后要离开隔离区；只看满窗口也会挂，两次运行一过一不过就已经是 flaky。窗口大小也要正好：bench_t007 最近三次是不过、过、过时还在名单上，再过一次才离开，窗口差一次就会在这两步之一挂掉。

这组用例修订后 3/5 通过，首轮通过是 0/5。课里的 4/4 PASS 也是这么来的，它看的是修订后的结果，judge 的理由（"missing sticks in recipe"）又直接告诉了 agent 怎么改。两个数都要报。

## Part 2 每个提交一份快照

参考实现每个提交写一个 `<sha>.json`，里面是 `{"sha": ..., "cases": {id: {...}}}`。Python 的 dict 和 JSON 对象都保留插入顺序，所以用例按套件顺序写进去、读出来。写的时候先在同一个目录里写临时文件，再 `os.replace` 盖过去，读者看到的要么是旧快照，要么是新快照。

容易漏的几点：

- **重跑就是替换**：同一个提交再存一次，整份覆盖。合并新旧用例会把已经删掉的用例留下来。
- **基线按历史找**：`history` 是 `git rev-list main` 的顺序，从新到旧。取第一个有快照的提交；没有结果的提交跳过；PR 的快照不在主干历史里，再新也不是基线。按文件修改时间找是错的：测试里最后存的是 c1 的重跑，它的文件最新，但主干上最新的有结果的提交是 c3。c3 有一个失败的用例，它照样是基线：基线是主干现在的样子，不是最后一次全绿；退到更早的全绿快照，主干上已有的失败就会算到这个 PR 头上。
- **顺序**：按层分组或按 id 排序再存，读回来的用例顺序就变了，Part 3 的回归列表和 Part 4 的日志都依赖套件顺序。参考实现按 id 把用例存成 JSON 对象，所以不能加 `sort_keys=True`。
- **校验在写之前做**：重复的 id 用 dict 存会悄悄只剩一个，要报 ValueError；未知类别（`"Online"`）要报 ValueError，否则它会在按层汇总时消失；sha 只认 40 位小写十六进制，`"HEAD"`、短 sha 和大写的 sha 都拒绝，这也挡住了用 sha 拼出奇怪路径的可能。只查长度或者用 `string.hexdigits` 查会放过大写的 sha，而大写和小写的同一个 sha 在 macOS 默认的文件系统上是同一个文件，在 Linux 上是两个文件。末尾带换行的 sha（`git rev-parse` 的原始输出）也要拒绝：`re.match` 加 `$` 会放过它，因为 `$` 能在末尾的换行之前匹配，所以参考实现用 `re.fullmatch`。
- **找不到就 KeyError**：没有快照的提交 `load` 报 KeyError，不返回 None。

## Part 3 合并闸门

先按 id 对齐两个快照，每个用例落进一类：

| 情况 | 处理 |
|---|---|
| 主干没有 | new，只报告 |
| 两边任一 flaky | flaky，只报告 |
| 主干通过、现在失败 | 回归，计数 |
| 其他 | 可比，不是回归 |
| 主干有、现在没有 | removed，只报告 |

然后每一层单独判：`regressed * 100 > limit * comparable` 就拦。整数比较没有浮点误差，可比用例为 0 时左边是 0，不会除以 0，也不会拦。这里必须是 `>`：写成 `>=`，上限为 0 的层和没有可比用例的层在没有任何回归时也会被拦（`0 >= 0`）。

这组数据里每个陷阱都会改变结论：

- benchmark：b03 回归，b07 修好了。按总数比，一升一降抵消；按用例比，1/12 超过 5%。b07 主干上失败，照样是可比用例，分母是 12。
- benchmark 还有 10 个新用例。算进分母就成了 1/22，低于 5%，闸门放行。
- benchmark 的 b13 在主干上 flaky、这次失败，b14 在主干上 flaky、两边都通过。两个都只进 flaky 列表，不进分母。只在“本来要算回归”的用例上查 flaky，b14 就会从 flaky 列表里漏掉，或者被当成可比用例。
- custom：c12、c13 这次 flaky 且失败，c11 在主干上 flaky，三个新用例失败。任何一种算进回归，custom 都会被拦。
- online：上限是 0，o2 一个回归就拦。第二组数据里只有一个 guardrail 回归，总体是 1/44，按课里 `ci_gate` 那样全体合算会放行。
- drift：benchmark 1/40 是 2.5%，在 5% 以内，放行，但 b17 照样列进 regressed。上限是容忍度，只要有回归就拦的写法在这里挂。
- 顺序：regressed、flaky、new 按本次快照的顺序，removed 按主干的顺序。本次快照把新加的 benchmark 用例和 b14 排在最后，主干把 b99 排在最后，用集合求差再排序都会排错。参考实现在一次遍历里按本次快照的顺序收集前三个列表，removed 再按主干的顺序扫一遍。

没有基线时拦下，理由是 "no baseline on main"，对应课里的 No baseline：没有 last-known-good，评测结果没法读。空快照也拦，和课里 `ci_gate` 的 `"no cases"` 一样。

最后一段是端到端检查：课里的用例在两个主干提交上运行，经过 Part 1 的框架和 tracker、Part 2 的库；一个不再引用论文的 PR 提交，custom 层 1/2 回归，被拦下。guardrail 在主干上就是失败的，所以它不是回归，这一点值得和面试官讨论。

## Part 4 GitHub Actions 日志

每层一个缓冲区，外加一个按固定顺序排队的层列表：

```python
async for record in records:
    done[record.cid] = record
    waiting[category_of[record.cid]] -= 1
    while queue and waiting[queue[0]] == 0:
        for line in group(queue.pop(0)):
            yield line
```

- 一层的最后一个用例到了、前面的层也输出了，这一层马上输出。用 `while` 不用 `if`：custom 比 benchmark 先完成，benchmark 一输出，custom 要紧接着出来。
- 组内按套件顺序，所以要等这一层全部到齐，不能来一条打一条。套件顺序既不是完成顺序，也不是 id 顺序：测试里的套件把 `custom_c002` 排在 `custom_c001[en,de]` 前面。
- flaky 优先于失败：flaky 的用例不管这次过没过都是 warning，所以先判断 flaky，再判断失败。隔离区里的用例失败了，在 PR 上应该是提醒，不是错误。
- 转义分两套。消息只转 `%`、`\r`、`\n`；属性值还要转 `:` 和 `,`。`%` 要最先替换，否则 `%0A` 里的 `%` 会被再转义一次。`%` 也不能不转：`bench_t002` 的消息里本来就有 `%25`（链接里编码过的 `90%`），原样写出去会被 runner 解码成 `%`。`\r` 不能漏：runner 把单独的 CR 也当成换行。
- 结论放在最后一行，`decide` 拿到的是按套件顺序排好的全部结果。缺了用例或者重复，都报 ValueError。
- 格式由测试的解析代码决定，它照 Actions runner 的方式读：CR、LF、CRLF 都算换行；以 `::` 开头的是命令，`title=` 后面到下一个 `::` 是属性，再往后是消息。

## Part 5 护栏和规则的覆盖图

先做所有校验：类别、重名、covers 和 derived_from 里的未知名字。然后算每个要求的“支撑用例”：在快照里、通过、不 flaky。支撑用例要按快照顺序列出，所以遍历的是 `snapshot.cases`，不是 covers：测试里 covers 把 `online_o003` 写在 `online_o001` 前面。再递归 `gap(name)`：

- 先把所有父规则都算一遍（这样环一定能查出来），再看自己有没有支撑用例：没有就是 `(name,)`；有就看父规则，第一个没覆盖的父规则的链接在自己后面；都覆盖了就是空，表示覆盖。
- 结果记进 `gaps`，同一个要求只算一次。菱形结构里 `rule:cite` 会被走到两次，第二次直接取结果，不是环。
- 环按当前路径判：`active` 里是正在算的要求，又遇到它就是自己派生自己。

`rule:verified-cites` 的两个父规则都写在它后面，`rule:scope` 覆盖、`rule:cite` 没覆盖，它的链是 `("rule:verified-cites", "rule:cite")`。按给定顺序算一遍是算不对的，要递归去算父规则。`rule:tests-first` 有三个没覆盖的父规则，链走 derived_from 里的第一个 `rule:cite`，不是链最长的 `rule:verified-cites`；`rule:small-diffs` 同样走第一个 `rule:tests-first`，不是链最短的 `rule:cite`。

这样 `rule:small-diffs` 的链是 `("rule:small-diffs", "rule:tests-first", "rule:cite")`：它自己有通过的用例，父规则 `rule:tests-first` 也有，但 `rule:tests-first` 的父规则 `rule:cite` 只有一个 flaky 用例和一个失败用例。课里说“every learned rule maps to a failure case”，这里的意思更进一步：从别的规则派生出来的规则，前提也得有用例撑着。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试评测框架，分清首轮通过和修订后通过，让每次运行从干净的状态开始，按提交存结果并找对基线，按用例、按层做回归闸门并把 flaky 单独隔离，写出能被 CI 正确解析的流式日志，以及在派生关系图上做覆盖检查。它不涉及真实的 LLM-as-judge 和 grounding（课里说的 CRITIC 模式），不涉及 SWE-bench Verified、GAIA 这类静态基准本身的运行和污染问题，也不涉及线上的 session replay 平台和成本、延迟追踪。课里的练习 2（三维 rubric）和练习 4（轨迹效率）需要另外动手做。
