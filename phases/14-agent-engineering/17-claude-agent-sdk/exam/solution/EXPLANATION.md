# 参考答案讲解：Harness（14/17）

计时结束后再看。参考实现在同目录的 `harness/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 harness

**现象**：解锁后第一条失败是 “a denied call must not run the tool”：`stay_in_work` 明明返回了 Deny，`/etc/hosts` 还是被写了。

**依次修四处**：

1. `_dispatch` 要看 PreToolUse 钩子的返回值。拿到 Deny 就记下来并 `break`，后面的钩子不再运行，工具也不运行，结果是 `denied: <reason>`。被拒绝的结果和其他结果一样往下走，进 PostToolUse，也写进会话。
2. 工具抛异常的分支原来直接 `return`，PostToolUse 看不到这条错误。改成给 `result` 赋值，让它走到下面的审计循环。课里说 PostToolUse 用来 audit tool calls，审计漏掉的往往正是出错的那几次。
3. 接下来的报错是 `count_tokens` 里的 `AttributeError: 'list' object has no attribute 'split'`，而 `count_tokens` 本身没有错。往上找：`_record` 收到的 content 是一个 `list[Turn]`，是 `spawn_subagents` 把 `store.load(sub_session)`，也就是子 agent 的整段转录，当成一条 turn 交回了父会话。课里讲 subagent 的第二个用途是上下文隔离：子 agent 用自己的上下文，只有结果回到 orchestrator。所以交回去的是 `run.output`。把转录拼成字符串也能消掉报错，但 orchestrator 的上下文会从 26 涨到 89，隔离就没了。
4. 最后是计时。`_record` 每追加一条 turn 就 `load()` 整个会话、重新数一遍 token，5000 次调用是 O(n²)，本机测试里要 1.4 到 2.2 秒。改成 `run.context_tokens += count_tokens(content)`。但起点不能是 0：`context_tokens` 是整个会话的上下文，会话第二次 run 时，前面的轮次也在模型要读的内容里。所以在 `run_agent` 开头把已有会话数一次，之后增量累加。

## Part 2 会话镜像

每个会话一个 JSONL 文件，只追加。参考实现的格式就是 docstring 里那三种行：turn、`{"subagent": id}`、`{"removed": id}`。link 和删除记录写在父会话的文件里，这样 `list_subkeys` 保持 link 的顺序，删除也不用改写已有的行。内存里保留一份索引，新开的 `MirrorStore` 按文件回放出同样的索引。

容易漏的几点：

- **递归级联删除**。课里的 `delete` 只删一层子会话。参考实现用显式栈把整棵子树删掉，删掉它们的文件，再给仍然存在的父会话追加 `{"removed": ...}`，所以重开以后 subkeys 里也没有它们。
- **删除也只追加**。有人在 tail 父会话的镜像，所以不能把 link 那一行删掉再整份写回。测试在删除前后读 `lead` 的镜像，删除后的内容必须以删除前的内容开头。
- **只 link 过的会话也存在**。link 时父子会话都算存在，`lead/sub02` 一轮都没写，也要出现在 `list_sessions` 里、有自己的镜像文件，重开以后还在。测试把同一串操作放到 `SessionStore` 和 `MirrorStore` 上，逐个会话比较。
- **写完就落盘**。参考实现每次 `with open(..., "a")` 写一行就关闭。一直开着句柄又不 flush，别人 tail 文件时什么也看不到，进程崩溃时还会丢掉缓冲里的内容。
- **时间戳原样读回**。`json.dumps` 写 float 用的是能原样读回的最短表示，`1767225600 + 1/3` 和 `0.1 + 0.2` 都能往返；先 `round` 或者按固定位数写就回不来了。
- **按 `"\n"` 切，不用 `splitlines()`**。镜像是给人看的，要用 `ensure_ascii=False` 原样写出非 ASCII。这样 U+2028 和 U+0085 就以原字符留在文件里，而 `str.splitlines()` 会在这两个字符处断行，把一行 JSON 切成两半。JSON 会转义 `\n` 和 `\r`，所以按 `"\n"` 切永远是对的，逐行迭代文件对象也一样。
- **文件名可逆且不冲突**。参考实现用 id 的 UTF-8 字节的十六进制作文件名，只含 `0-9a-f`，不会有 `/` 和 `..`，大小写也不会撞。`replace("/", "_")` 会让 `lead/sub01` 和 `lead_sub01` 撞名；`quote()` 保留大小写，在 macOS 默认的文件系统上 `Lead` 和 `lead` 是同一个文件；标准 base64 会编出 `/`，`naïve / id?` 就是一例。

## Part 3 分批规划

参考实现先把每一种方案都算出来，再挑一个。算方案：

```python
alone = costs.prompt + sum(read for _, read in tasks)
plans = [Plan(0, (), alone, (), alone)]
for k in range(1, len(tasks) + 1):
    batches = [tasks[i:i + k] for i in range(0, len(tasks), k)]
    summaries = [costs.summary_base + costs.summary_per_task * len(batch) for batch in batches]
    orchestrator = costs.prompt + sum(summaries)
    contexts = tuple(costs.overhead + costs.brief + sum(read for _, read in batch) + summary
                     for batch, summary in zip(batches, summaries))
```

- 不用 subagent 时，所有读入都在 orchestrator 自己的上下文里：50 + 20 × 2,000 = 40,050。没有别的上下文，总数也是 40,050。
- 用 subagent 时，读入留在各个 subagent 自己的上下文里，orchestrator 只多出交回的摘要：每任务一个是 50 + 20 × 100 = 2,050，五个一批是 50 + 4 × 300 = 1,250。这就是课里说的 only results return to the orchestrator。
- `range(0, n, k)` 切出来的最后一批自然就是剩下的那几个。`n // k` 会把它丢掉，`n // k + 1` 在整除时又多出一个空批。
- 一批只交回一份合并摘要，50 + 50 × 任务数。按每个任务各算一份 100，就把合并省下来的又加了回去。
- 总数把每个上下文都加起来。subagent 的上下文是固定开销 3,000、brief 50、它的读入和它自己写的摘要，所以摘要算两次：subagent 写一次，orchestrator 读一次。每任务一个是 105,050，五个一批是 54,650，和测验 Q12 的答案一样。

挑方案：

```python
fits = [plan for plan in plans
        if plan.orchestrator_tokens <= cap and all(tokens <= window for tokens in plan.subagent_tokens)]
return min(fits, key=lambda plan: (plan.total_tokens, plan.subagents, plan.batch_size))
```

- 不用 subagent 的方案总是最便宜：没有固定开销，也没有摘要。orchestrator 放得下就选它，测试里 cap 正好是 40,050。
- 放不下时，subagent 越少，总数和 orchestrator 的上下文都只降不升，所以挡住大批的只能是 subagent 自己的 window。这就是测验 Q12 最后说的：单个 subagent 的上下文变大以后，还要确认它放得进自己的窗口。window 16,000 时，k = 6 最大的一批是 15,400，k = 7 是 17,450，所以最少要 4 个 subagent；k = 5 和 k = 6 都是 4 个、总数一样，取小批，就是练习 1 的 5 个一组。
- 每个 k 都要试，因为能不能放下不随 k 单调。批的边界随 k 移动：`UNEVEN` 里 k = 2 把两个大模块 c、d 放进同一批，放不下；k = 3 把它们分开，反而放得下。
- 总数相同先取 subagent 少的。brief、固定开销和摘要基数都是 0 时，所有 subagent 方案的总数一样，这时要的是 subagent 最少、还放得下的那个。
- 没有方案放得下时报 ValueError，不返回 None，也不随便挑一个。

最后一段把计划交给 Part 1 的 harness：按 `plan.batches` 的三批调用 `spawn_subagents`，orchestrator 的上下文从 8 变成 20，只多了三份 4 个词的摘要，每个 subagent 的上下文和计划里的一一对应。计划里算的，就是 harness 跑起来以后各个上下文的实际大小。

## Part 4 并行子 agent

参考实现用一个队列收完成的结果：

- 先启动 5 个。每个 subagent 结束时（成功或抛异常）把结果放进队列，放的顺序就是完成的顺序。
- 生成器每从队列拿到一条，就先补启动一个新任务，再把结果写进父会话，然后 `yield` 一个事件。所以最多同时 5 个，一个完成就补一个，结果也是一完成就发出去。
- 失败的 subagent 发 `error` 事件，父会话里写 `error: <类型>: <消息>`，其他照常。
- `done` 里的 token 只数父会话。每个子 agent 在自己的会话里写了 61 个词，这些留在子会话里，orchestrator 只看到每个结果的 7 个词，这就是课里说的上下文隔离。
- 格式由测试的 `parse_sse` 决定：一行 `event:`、一行 `data:`（单行 JSON），再加一个空行。
- `finally` 里取消还在跑的任务，并且 `await asyncio.gather(..., return_exceptions=True)` 等它们真正结束。消费方 `aclose()` 时生成器在 `yield` 处收到 GeneratorExit，会走到这里。

照练习字面写成“每 5 个一组 `gather`”，慢的那个会拖住整组，后面 15 个任务都要等它。用 `asyncio.wait(FIRST_COMPLETED)` 或信号量加队列的写法也能通过。

## Part 5 subagent 树

先由 `list_subkeys` 建出每个会话的父会话，同时检查：一个会话出现在两个父会话下就报错；从所有根出发数到的会话少于会话总数，说明有环，也报错。检查在删除之前做，出错时什么都不删。

- `render_tree` 用显式栈做先序遍历，子节点按 link 的顺序压栈（倒序压入，正序弹出）。再按逆先序算 subtree：自己的轮数加上所有子节点的 subtree。根不存在时报 ValueError。1200 层的链用递归会撞上递归上限。
- `prune_expired` 对每棵树按逆先序计算“这个会话或它下面有没有活着的”。活着的定义是最新一轮在 `ttl_s` 以内，恰好 `ttl_s` 也算活着；没有轮次的会话算空闲，不能对它求 `max()`。整棵子树都空闲的会话过期。删除时只删最上层的过期会话，级联会带走下面的。
- 测试里的几处边界：`other` 第一轮在 100、最新一轮在 900，按最新一轮算才会留下；`nightly` 的最新一轮恰好在 `now - ttl_s`，留下；`lead/docs/draft` 只 link 过，跟着 `lead/docs` 一起删掉。
- `lead` 本身很旧，但孙会话 `lead/tests/unit` 还活着，所以 `lead` 和 `lead/tests` 都留下，`lead` 下面只有 `lead/docs` 连同 `lead/docs/draft` 被删。只看自己的活动、或者只看直接子会话，都会把 `lead` 判成过期，再顺着级联把活着的孙会话一起删掉。

## 这套题证明了什么，没证明什么

通过了说明你能在 harness 这一层代码里调试钩子和上下文隔离的问题，能把会话写成可以 tail、可以重放的 JSONL 镜像，能按上下文隔离算清每种分批方案的 orchestrator 上下文和总 token、选出放得下的最省方案，能用 asyncio 写有并发上限、可取消的流式扇出，也能在不递归的情况下处理很深的 subagent 树。它不涉及真实的 `claude-agent-sdk` 包、真实的模型和工具选择，也不涉及 MCP 服务器、W3C trace context 和 Claude Managed Agents。课里的练习 4 和 5 需要另外动手做；练习 2 的限流钩子是滑动窗口，可以拿第 13 章第 17 课（MCP 网关）的题来练。
