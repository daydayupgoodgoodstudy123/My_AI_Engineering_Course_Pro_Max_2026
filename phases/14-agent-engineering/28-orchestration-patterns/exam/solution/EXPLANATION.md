# 参考答案讲解：Orchestra（14/28）

计时结束后再看。参考实现在同目录的 `orchestra/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修监督者路由

**现象**：解锁后的第一个错误是 `prompt line is not a member: 'Refunds, crashes and bug reports.'`，出在测试提供的路由器假对象里，而那个假对象本身没有 bug。

**顺着往上找**：路由器按行读提示词，每行应该是 `- name: description`。出问题的那一行是 customer_ops 描述的第二行。`prompt()` 只对描述做了 `strip()`，描述中间的换行原样进了提示词，一个成员占了两行。docstring 要求把所有连续空白（包括换行）折成一个空格。真实系统里这类错误更隐蔽：LLM 不会报错，只会把第二行当成一个不存在的成员。

**依次修四处**：

1. `prompt()`：`" ".join(description.split())`，把描述折到一行。
2. `run()`：子监督者的结果要接在自己后面，path 前面加上自己的名字，ops 加上自己这一次路由决策。原代码 `return member.run(task)` 把子监督者的结果原样交回，desk → customer_ops → bug 只记了 2 次 op，path 也从 customer_ops 开始。worker 是对的，错的是账：课里的 `hierarchical` 每一层都记一次 op，层级多出来的成本就记在这里，少记一层，层级就显得和单层一样便宜。
3. `route()`：回复对不上任何成员时返回 `ESCALATE`，不能退回第一个成员。课里 `classify` 最后的 `return "sales"` 就是这个毛病：认不出的请求被悄悄当成销售。只认字面上的 `none` 也不够，路由器可能回一个别的团队的名字（测试里 commercial 的路由器回了 refund），一样要交给人：监督者只能把任务交给自己的成员。
4. 提示词只在成员变化时重建。原代码每次路由都把 3000 行描述重新拼一遍，800 个任务约 0.5 秒；缓存后不到 1 毫秒。

路由器的回复前后带空白，`route()` 里原本就有 `strip()`，保持不动。

**护栏**：缓存必须在 `register` 里失效，测试在两批任务之间注册了 `late`，缓存不失效的话它永远收不到任务。也不能在 `register` 里立刻重建提示词，那样注册 N 个成员是 O(N²)，3000 个成员要 0.7 秒以上，限值是 0.05 秒。参考实现在 `register` 里只把缓存清空，下一次 `prompt()` 再重建。

## Part 2 拓扑快照

快照是一个 JSON 对象：`format`、`root`、`workers` 列表、`teams` 列表，列表保持配置里的顺序。`json.dumps(..., ensure_ascii=False)` 加 UTF-8 写入，非 ASCII 和换行都能原样还原。

容易漏的几点：

- **继承和 null 是两回事**：`router` 缺省表示继承上一层，`null` 表示这个团队不用 LLM、按关键词路由（课里 CrewAI 的 Flow），字符串是 LLM 路由器的模型名（Crew）。写的时候继承就不写这个键，读的时候没有这个键就是 `INHERIT`。
- **类型**：`members` 和 `keywords` 读回来是 list，要转成 tuple，dataclass 比较才相等。
- **原样保存**：描述不能折叠或 strip，那是 Part 1 生成提示词时才做的事。
- **先校验再写**：重名（worker 和团队共用一个命名空间）、引用不存在的成员、root 不是团队，都要在打开任何文件之前报 ValueError。测试最后会看目录，被拒的保存不能留下临时文件。
- **原子替换**：先写到同目录的临时文件（`tempfile.mkstemp(dir=target.parent)`），`flush` 加 `fsync`，再 `os.replace` 到快照路径。崩溃时磁盘上要么是旧快照，要么是新快照，不会有半个文件。临时文件必须在同一个目录，跨文件系统的 `os.replace` 会失败。
- **失败要清理**：`os.replace` 失败时删掉临时文件再把异常抛出去。

## Part 3 按上下文预算建层级

一层一层往上做。当前这一层放不进一个提示词（`overhead + Σ成本 > budget`）时，按顺序贪心切组：每组从 `overhead` 开始累加，加下一个会超预算就另起一组。两个以上元素的组包成新监督者 `L{k}-{j}`，只有一个元素的组原样带到上一层。新监督者在上一层里的成本是 `team_tokens`，不是它下面所有成员的 token 之和，因为父级的提示词里只有这个团队的一行描述。

测试的数据：

- 第 1 层：a、b、c 正好 100，d、e 正好 100，f、g 是 80，h、i 是 50，各加 20 的开销都不超过 120；j 单独一组，带上去。
- 第 2 层：四个 L1 团队各 15，加上 j 的 80 超了，于是 L1-0 到 L1-3 合成 L2-0，j 再带上去。
- 第 3 层：L2-0 的 15 加 j 的 80 放得下，成为 root 的成员。
- 另一组 e、b、f：token 合计 120，加上开销是 140，根放不下，要切。e 加 b 超了，e 单独一组带上去，b、f 合成 L1-0；上一层是 e、L1-0，成本 95，成为 root 的成员。这一组同时检查三件事：判断一层放不放得下时也算开销；带上去的元素留在原位；编号只数新建的监督者，所以是 L1-0 而不是 L1-1。

这里体现了课里的两条：层级只在监督者的上下文预算放不下时才加；只有一个孩子的层要折叠（Fake hierarchy）。另外两个错误路径：单个 worker 超预算时直接报错并写出名字；一层切完元素数没变少，说明再切也没用（任何两个相邻元素都放不进一个提示词），这时报 ValueError，不能死循环。

## Part 4 工具调用式监督

```python
for call_id, call in enumerate(calls, start=1):
    context = {f: case[f] for f in views[call.specialist] if f in case}
    await channel.send(json.dumps({"jsonrpc": "2.0", "id": call_id, ...}))
    pending[call_id] = call
while pending:
    message = json.loads(await channel.receive())
    if "id" not in message:
        continue                      # progress 通知
    call = pending.pop(message["id"])
    yield ToolResult(...)             # error 或 result
```

- **上下文由监督者决定**：这就是课里 2026 年 LangChain 建议用直接的工具调用做监督的原因。views 是允许清单，case 里没有的字段不发，不写成 null；卡号只给 refund。
- **先全部发出，再收**：调用是并发的。发一个等一个，既慢，也会被测试的假专家池拦下。
- **按 id 关联**：回复乱序到达，`pending` 用 id 做键。
- **通知和错误**：没有 id 的帧是通知，跳过；带 `error` 的回复变成 `ok=False`，不让一个专家的失败打断其他调用。
- **到一个转一个**：结果在回复到达时就 yield，第一个结果出来时只调用了两次 `receive()`。所有调用都有回复后循环结束，不再多读。也可以开一个后台任务读回复、放进队列，但生成器关闭时要取消它，否则调用方已经不要结果了，它还在读。
- 在发任何请求之前检查 views，缺 view 的调用整批拒绝。

## Part 5 层级路由回溯

分词已经给了：`tokenize(task)` 取 `\w+` 的连续串并转成小写，关键词是其中一个词才算匹配，所以 `Quote,` 里有 quote，`debugger` 里没有 bug。

递归 `visit(team)`，每个团队记一个位置指针：

- 每次向团队要一个选择，`ops += 1`，从指针往后找第一个“匹配、且没有走空过”的成员，然后写一行 trace。走空过的团队直接跳过，不算一次选择，也不写 trace。
- 选中 worker：`ops += 1`，结束。worker 接手不是一次选择，不写 trace。
- 选中团队：递归进去。子团队走空，回到这一层算一次 backtrack，再要下一个选择；这次选择的那一行末尾写 `, back from <子团队>`，什么都没选出也要写。
- 找不到：写 `<team> -> none`，把这个团队记进 `failed`，从 path 里弹出，返回 None。
- 需要第 `max_backtracks + 1` 次回溯时，用一个内部异常直接结束整个搜索。
- 进入一个已经在 path 上的团队，报 ValueError。

trace 的缩进是 `"  " * (len(path) - 1)`：路径上它上面有几个团队，就缩进几个两格，和课里 `hierarchical` 的 trace 一样，每深一层多缩进一级。死路的团队已经从 path 里弹出，下一行自然回到上一层。另记一个深度计数也可以，但走空返回时要减回去，否则死路那一层会一直留在后面的缩进里。`back from` 写在退回之后的那次选择上，不写在死路那一行：走空的那一刻，还不知道上一层会继续选还是因为回溯上限放弃。

发票那个任务的 9 次 op 和 8 行 trace：

```text
desk -> billing                          op 1
  billing -> none                        op 2，退回 desk（第 1 次回溯）
desk -> support, back from billing       op 3
  support -> accounts                    op 4
    accounts -> none                     op 5，退回 support（第 2 次回溯）
  support -> none, back from accounts    op 6，退回 desk（第 3 次回溯）
desk -> commercial, back from support    op 7
  commercial -> quotes                   op 8，跳过已经走空的 accounts
                                         op 9，quotes 接手
```

共 3 次回溯，正好等于默认上限。如果 accounts 被再进一次，会需要第 4 次回溯，任务就失败了。上限是 2 时，第 6 行之后需要第 3 次回溯，搜索在这里放弃，trace 停在前 6 行。没走通的任务照样带着 trace，排查时最需要的就是这一份。

`Route` 比较时不看 trace（`compare=False`），repr 里也不显示，所以前面几条断言只比结果和成本，trace 由测试单独逐行比。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着调用链调试、给编排配置做可靠的持久化、按上下文预算设计层级、写并发的 JSON-RPC 工具调用和按 id 关联的异步生成器，以及在带共享节点的嵌套结构里回溯，并给每次选择留下能读的 trace。它不涉及真实的 LLM 路由质量、提示词写法、LangGraph 或 CrewAI 的 API，也不涉及 swarm 的 handoff 和 debate。课里的练习 4（在真实负载上比较四种模式的延迟、成本、准确率和可调试性）需要另外动手跑。
