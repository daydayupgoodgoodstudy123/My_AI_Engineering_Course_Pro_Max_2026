# 参考答案讲解：Handoffs（14/16）

计时结束后再看。参考实现在同目录的 `handoffs/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 runner

**现象**：解锁后的第一个错误是 `tracing.preview` 里的 `AttributeError: 'dict' object has no attribute 'split'`，而 `preview` 本身没有 bug。

**顺着往上找**：`preview` 是 `_call_tool` 给 tool span 记结果时调用的，拿到的是 `lookup_customer` 返回的 dict。`_call_tool` 的 docstring 说模型读到的是文本：字符串原样，其他结果转成 JSON。它却把原始结果直接交了出去，span 和模型拿到的都是 dict。这一层想练的是：报错的位置往往不是出 bug 的位置。

**依次修五处**：

1. **工具结果转成文本**。`_call_tool` 里非字符串的结果用 `json.dumps(result, ensure_ascii=False)` 转一次，span 和 ToolItem 都用转好的文本。只把 `preview` 改成能接受任何类型，报错是没了，可模型收到的仍然是 dict，测试的第一条断言就会抓住。
2. **交接复制整段对话**。不折叠时，原代码把目标 agent 的视图换成了 `[state.request]`，billing 只看到用户这一句，不知道客户是谁。课里讲 handoff 的第一步是 copy the conversation context：目标 agent 读到的就是前一个 agent 读到的全部，再加上这次交接。删掉这个 else 分支即可。改成 `list(state.new_items)` 也不对，session 里更早的消息会丢掉。
3. **输出护栏用最后一个 agent 的**。原代码循环的是 `agent.output_guardrails`，也就是入口 triage 的。triage 自己的回答很短，挂了 60 字上限，billing 69 个字的正常回答就被拦下了。课里写得很清楚：output guardrails 只在最后一个 agent 上运行。改成 `current.output_guardrails`。
4. **hop 用完时报错**。agent 循环是 `for _ in range(self.max_handoffs + 1)`。最后一个 agent 还要交接时循环自然结束，final 还是空串，输出护栏对空串放行，run 静静地返回 `""`，这就是测验 Q6 里跑出来的现象。加上 `else: raise HandoffLimitExceeded(...)`。工具调用发生在 `_turns` 里面，不占交接次数；模型调用的总数由 `max_turns` 管。
5. **PII 规则只编译一次**。`PiiGuard.check` 对每条规则调用 `re.search(pattern, text)`，这本身没错，re 模块会缓存编译结果，但只缓存 512 个。600 条规则轮着用，缓存每次都不命中，每次检查都要重新编译 600 个模式，120 次 run 约 1.3 秒。在 `__init__` 里 `re.compile` 一次，检查时直接用编译好的对象，约 5 毫秒。规则少于 512 条时完全看不出问题，这是它的危险之处。

**护栏**：

- 恰好 `max_handoffs` 次交接必须成功，多一次必须报错，一条不回头的长链也一样。只拦“交回之前的 agent”的写法能拦住乒乓，却拦不住 triage → billing → refunds 在上限为 1 时的情形。
- 空回答不是 drift。按 `final == ""` 判断超限，会把一个老老实实回答了空串的 agent 当成循环，这正是测验 Q9 说的“调用方分不清空回答和交接循环”。
- 3 次工具调用加 1 次交接、上限为 1 时必须成功。照课里的代码把每一步都算一次 hop，会在这里挂掉。
- 字符串结果原样交给模型，不能统一 `json.dumps`（会多出引号）。反过来，只给 dict 做 `json.dumps`、其余用 `str()` 也不对：`open_tickets` 返回元组 `(77,)`，模型该读到的是 JSON 的 `[77]`。
- reason 写按规则顺序第一条命中的规则。为了提速把 600 条合成一个交替正则，正则取的是文本里最靠左的匹配，`DE-482-913-775` 在 `ATPX4821933` 前面，于是报成 `de_national_id`，而按顺序应该是 `at_passport`。`functools.lru_cache(maxsize=128)` 和 re 自己的缓存一样会反复失效，照样慢。

## Part 2 SQLite 会话库

参考实现只有一张表：`seq` 自增主键负责顺序，`session_id` 分开各个会话，`kind` 记 item 的类型，`body` 是 `dataclasses.asdict(item)` 的 JSON 文本。读回时按 kind 找到类，`cls(**json.loads(body))`。

这一关的三个坑都在会话库本身：

- **重复要保留**。用户说两次 “Danke!” 就是两条 item，不能靠 UNIQUE 去重：`INSERT OR IGNORE` 会丢掉第二条，`INSERT OR REPLACE` 会删掉第一条、只留下第二条。`pop_item` 也一样，要按 seq 删最新的那一行。按内容删会把两条一样的消息都删掉；按内容找到一行再删，找到的是旧的那条，剩下的顺序就错了。
- **limit**。取最新的 N 条，再按从旧到新排：`ORDER BY seq DESC LIMIT ?` 之后倒过来。`ORDER BY seq LIMIT ?` 取到的是最旧的，不倒过来就是从新到旧。`WHERE session_id = ?` 要和 LIMIT 写在同一层查询里：先在全表取最新的 N 条再过滤，插在中间的别的会话会占掉名额。
- **参数化查询**。session id 是邮箱，`o'brien@example.com` 拼进 SQL 文本就是语法错误。SQL 里转义单引号要写两个，反斜杠不算，`\'` 照样报错。换成双引号也不行：SQLite 找不到同名的列时，会把双引号里的内容当成字符串，o'brien 碰巧能过，可邮箱的本地部分本身就能带双引号，`"ann lee"@example.com` 一拼就坏。把引号去掉更糟，o'brien 会和另一位客户 `obrien@example.com` 读到同一段对话。每条 SQL 都用 `?` 传 session id，不用自己转义。测试对 o'brien 调用了 `add_items`、`get_items`（带和不带 limit）、`pop_item` 和 `clear_session`，哪一条用单引号拼了字符串都会报错。

顺带检查的几点：

- **工具参数原样读回**。存法写在类的 docstring 里：`json.dumps` 按插入顺序写，不排序键，`json.loads` 读回。Python 的 json 保留 dict 的键顺序，也分得清 `10`、`10.0` 和 `True`，`2**64 + 1` 和 `0.1 + 0.2` 都能原样还原。不要 `sort_keys`：模型下一轮读到的是它自己写过的参数，逐字节不变才不会打乱提示词，也方便对照调试。`exact()` 还会查出读回的普通 dict，和存的时候 strip 掉的换行。
- **limit=0** 返回空列表。`rows[-limit:]` 在 0 时会返回全部，`if limit:` 也会把 0 当成没给。
- **整批写入**。先把所有 item 校验并序列化，再用 `with self._db:` 加 `executemany` 在一个事务里插入。有一个不是 item，就在写库之前抛 TypeError。
- **pop_item 和 clear_session 都只碰自己的 session**。删除同样放在 `with self._db:` 里提交，测试清空 session 以后会关掉重开再看一次。

最后一段是 runner 和 session 一起用：runner 先读 `get_items()`，run 成功后把 `new_items` 交给 `add_items()`。关掉连接再重开，下一次 run 读到的还是完整的对话。

## Part 3 交接折叠

```python
latest = max(i for i, item in enumerate(conversation) if isinstance(item, UserMessage))
lines = []
for item in conversation[:latest]:
    lines.extend(item.lines if isinstance(item, HistorySummary) else [summary_line(item)])
return ([HistorySummary(tuple(lines))] if lines else []) + conversation[latest:]
```

- 找的是最后一条用户消息的位置。用 `conversation.index(msg)` 会找到第一条内容相同的消息。
- 它前面的全部折成一个摘要，放在最前面；它和它后面的这一轮内容（工具结果、刚发生的交接）原样保留。目标 agent 要用这一轮查到的东西。
- 已有摘要的行原样接上，不再套一层，所以 `nest(nest(x)) == nest(x)`。同一个 run 里第二次折叠交接时，前一个 agent 读到的视图里已经有摘要了，这一点正好用上。
- 前面没有东西就不放摘要。返回新列表，不改传进来的那个。

runner 里交接上限是按 run 算的：参考实现数的是这个 run 里 agent 循环转了几圈，和 session 里存了多少次交接无关，计数也不放在 Runner 上跨 run 累加。折叠的是当前 agent 读到的整段视图（session 里的历史加上这一轮），不是这次 run 的 `new_items`。session 里存的是 `new_items`，也就是全部原始 item；折叠只改变下一个 agent 读到的东西。课里提到的取舍在这里能看清楚：摘要更短、焦点更清楚，但会丢细节，所以工具那一行保留了参数，最新的用户消息一字不改。

## Part 4 trace processor

分发放在 `Trace.end` 里：`Tracing` 持有 processor 列表，新建 trace 时把这个列表本身（不是拷贝）交给它，每个 span 结束时按加入的顺序逐个调用 `on_span_end`。

- span 在结束时才发出去，所以顺序就是结束的顺序：子 span 在父 span 前面，run 在最后。
- `Trace.span` 在 finally 里结束 span，被护栏拦下的 run 同样会导出 guardrail span 和带 `error` 属性的 run span。
- 列表是共享的，run 中途加进来的 processor 会收到之后结束的每个 span。

`NdjsonSpanWriter` 每个 span 写一行 `json.dumps(record) + "\n"`，然后 `flush()`。测试在工具调用中途从磁盘读文件，不 flush 的话那几行都还在缓冲区里。

`BackgroundProcessor` 用 `queue.Queue(maxsize=max_queue)` 和一个 daemon worker 线程：

```python
def on_span_end(self, span):
    try:
        self._queue.put_nowait(span)
    except queue.Full:
        self.dropped += 1   # 参考实现在锁里加
```

worker 从队列里取一个 span，交给慢 processor，交完再取下一个。worker 手里那个 span 已经不在队列里，所以不占 max_queue。测试让慢 processor 卡在第一个 span（2 号）上，队列里排进 4、5、6，后面 6 个 span 被丢掉并计数。`shutdown()` 往队列尾部放一个停止标记，再 `join()`：队列是先进先出的，worker 遇到标记时，前面排队的 span 都已经交出去了。

## Part 5 交接图

构图时从给定的 agent 出发，沿 handoff 把目标也加进来，按名字建索引：测试里只传 triage 一个 agent，也要建出它能到的整张图。同一个名字遇到第二个不同的对象就报 ValueError，模型分不清两个同名的 `transfer_to_<name>`。未知的名字，`reachable` 和 `path_to_tool` 都报 KeyError。

- `reachable`：带 visited 集合的遍历，入口自己也算，结果排序。
- `path_to_tool`：按层做 BFS。每一层对每个新节点只留按名字比较最小的那条链（`chain < following[target]` 比较的是整条列表），这一层里有谁拥有这个工具，就返回其中最小的那条链。只看链上的某一个名字都不够：到 issue_refund 的两条链里，最后一个名字 escalations 比 refunds 小；到 ledger 的两条链 `[triage, billing, vat_desk, ledger]` 和 `[triage, support, accounts, ledger]`，倒数第二个名字 accounts 比 vat_desk 小。两次都要从入口起逐个比较，billing 那条更小。
- `audit`：对可达的每个 agent 检查三件事。没有输出护栏的要报，因为任何可达的 agent 都可能给出最终回答，入口也一样；入口以外的 agent 上的输入护栏永远不会运行，因为输入护栏只在第一个 agent 上运行；内置工具要报，因为工具护栏只在 function tool 上运行，内置工具需要单独的策略。最后排序。

## 这套题证明了什么，没证明什么

通过了说明你能在一个 Agents SDK 形状的运行时里调试交接、护栏范围和 hop 上限，能看出 re 缓存造成的性能悬崖，能把会话历史精确地存进 SQLite，能实现 `nest_handoff_history` 式的历史折叠，能写不拖慢 run 的 trace processor，也能在交接图上做可达性、最短路径和护栏缺口的分析。

它没有涉及真实的 OpenAI Agents SDK、Responses API 和真实模型的调用，路由决定都是测试写好的。护栏的并行和阻塞两种模式没有考：课里的练习 3 要比较两种模式在会触发和不会触发的提示上的延迟，需要另外动手跑。对流式输出逐行做输出护栏检查在本章 05 课。span 里的 GenAI 语义约定和内容捕获规则在本章 23 课，Langfuse、Phoenix、Opik 这类后端在 24 课。
