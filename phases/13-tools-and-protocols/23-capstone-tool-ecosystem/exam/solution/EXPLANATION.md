# 参考答案讲解：ResearchOps（13/23）

计时结束后再看。参考实现在同目录的 `researchops/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修一次研究流程

**现象**：解锁后第一个错误是 `ProtocolError: -32021 Missing required client capability`，抛在 `_settle` 调用的 `unwrap` 里。`_settle` 是轮询 `tasks/get` 的地方，而 `get_task` 发出的请求明明声明了 Tasks 扩展。

**顺着往上找**：`_settle` 抛错时还一次都没轮询，它手里的响应是 `call_tool` 发出的 `tools/call generate_report` 的回答。这个请求的 `_meta` 由 `Agent.request` 生成，`tasks = method.startswith("tasks/")` 只给任务方法声明扩展。本课说得很清楚：哪个 `tools/call` 变成任务由服务器决定，客户端必须在可能收到任务句柄的同一个请求里声明 `io.modelcontextprotocol/tasks`，否则服务器回 `-32021`，`requiredCapabilities` 就是缺的那个能力对象。这一关想练的是：先弄清楚一个错误回答的是哪个请求。

**依次修四处**：

1. `Agent.request`：`tools/call` 和 `tasks/*` 都声明扩展。按工具名特判（只给 `generate_report` 声明）不对，客户端事先不知道哪个调用会变成任务，测试会检查每一个 `tools/call`。
2. `call_tool`：把自己的 `span` 交给 `_settle`，而不是调用方的 `parent`。修之前 20 个 `tasks/get` 都挂在根 span 下，trace id 却全都一样。这正是本课那句话：共享 trace id 证明不了父子关系。
3. `Gateway.handle`：`missing = required - grant.scopes`，非空就拒绝。原来的 `required & grant.scopes` 是“有一个就行”。拒绝的调用不转发给服务器，同样记进审计。
4. `_settle`：`await self.sleep(task["pollIntervalMs"] / 1000)`。原来的 `time.sleep` 绕过了注入的 sleep，测试里要真等 1.2 秒；在 async 代码里，它还会把整个事件循环卡住。

**护栏**：服务器给的间隔先是 40 ms，然后升到 80 ms，再降回 40 ms。测试要求每次 `tasks/get` 之前恰好等当时的 `pollIntervalMs`，所以删掉等待、一直用句柄上的间隔、只增不减、把毫秒当秒、先轮询后等待都会挂。另外测试直接问服务器：没声明扩展的 `generate_report` 必须还是 `-32021`，靠删掉服务器检查来“修好”的写法过不去。

## Part 2 论文目录

参考实现一行一篇论文，`add` 用追加模式写，只有文件不存在或为空时才先写表头：

```python
with open(self.path, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if new_file:
        writer.writerow(COLUMNS)
    writer.writerow([paper.arxiv_id, paper.title, json.dumps(list(paper.authors), ensure_ascii=False),
                     str(paper.year), paper.source])
```

读的时候 `csv.reader` 解析，id、标题、来源原样保留，作者 `tuple(json.loads(...))`，年份 `int(...)`。

容易漏的几点：

- **`newline=""`**：csv 模块要求读写都这样打开文件。少了它，读的时候通用换行模式会把标题里的 `\r\n` 和 `\r` 改成 `\n`。
- **id 是文本**：`2401.01230` 经过 float 会丢掉尾零，`0912.0410` 会丢掉前导零。不要对格子做类型推断，也不要每格都 `json.loads`。
- **作者可逆**：名字里本身就有逗号和分号，空列表也要能还原。JSON 数组是最省事的可逆编码。读回来用 tuple，和 dataclass 的类型一致。
- **年份是 int**：`QUOTE_NONNUMERIC` 会把它读成 2024.0，相等比较发现不了，测试专门检查类型。
- **一个表头**：重新打开后追加，不能再写表头。测试最后用 csv.reader 数行。
- **重复 id 查文件**：另一个 `Catalog` 对象加过的 id 也算。

## Part 3 有上限的研究任务

参考实现分三段。第一段是带一次重试的 `tools/call`，每次发送前查预算：

```python
for _ in range(2):
    if job.tool_calls >= budget.tool_calls:
        job.status = "over_budget"
        return None
    job.tool_calls += 1
    result = unwrap(agent.request("tools/call", {"name": name, "arguments": arguments}))
    if not result.get("isError"):
        return result
job.status = "failed"
```

第二段是委托：只取前 `budget.delegations` 条命中，`asyncio.gather` 让它们同时在飞，每个委托自己捕获 `DelegationFailed` 返回 None。`gather` 的结果和输入同序，所以 summaries 天然是搜索顺序；没委托的和失败的都进 missing，同样按搜索顺序。报告照常生成，参数里带上 missing。

第三段是轮询，每次等待之前先查 ttl，再查等待预算：

```python
while task["status"] == "working":
    ttl = task.get("ttlMs")
    if ttl is not None and (agent.clock() - arrived) * 1000 >= ttl:
        job.status = "expired"
        return
    interval = task["pollIntervalMs"]
    if waited_ms + interval > budget.wait_ms:
        job.status = "over_budget"
        return
    await agent.sleep(interval / 1000)
    waited_ms += interval
    task = agent.get_task(task["taskId"], parent=parent)
    job.polls += 1
```

- `arrived` 是拿到句柄时的时钟读数。测试里写手花了 0.5 秒假时间，从任务开始算会提前过期。
- 先查 ttl 再查等待预算，ttl 用 `>=`。测试的第二个过期场景里，等了两次 250 ms 以后 ttl（500 ms）刚好到，下一次等待也会超出 600 ms 的预算，答案是 `expired`。
- 等待预算是“不开始一次会超出预算的等待”，测试用 649、650、700 ms 三个预算卡住比较符号和检查时机。
- 完成的任务快照里就有 `result`，直接用；当前扩展没有 `tasks/result`，服务器会回 `-32601`。

## Part 4 报告流

检索结果在读任何摘要之前就完整了，先发出去。然后维护一个 `arrived` 字典和一个指针 `sent`，每来一条摘要，就把从 `sent` 开始所有已经到了的节依次放出去：

```python
async for summary in summaries:
    arrived.setdefault(summary.arxiv_id, summary.text)
    while sent < len(order) and order[sent] in arrived:
        yield _paper_section(order[sent], titles[order[sent]], arrived[order[sent]])
        sent += 1
```

流结束后，剩下的论文（一直没来的）输出占位节，最后是结论。失败的（text 为 None）和没来的都算 missing，按论文顺序从 `order` 里挑出来，不按到达顺序。

- 标题用 `" ".join(title.split())` 折成一行，arXiv 的标题常带换行。
- 摘要逐行检查，去掉前导空格后以 # 开头的，在这个 # 前面加反斜杠。`C# and F#` 这种不在行首的不动。
- 测试按 CommonMark 的 ATX 标题规则切节，还记下每个标题发出去时已经拉了几条摘要：`[0, 3, 3, 3, 4, 4, 4]`。第三条摘要到了以后，前三节要一起放出去。

## Part 5 证据声明图

先把每个边界缺什么算出来：不在 run 里或者是模拟的，缺全部证据；真实的，缺 evidence 里没有的那几项。telemetry 例外，真实的 telemetry 的两项证据只从 collector 收到的 span 判断；模拟的 telemetry 列了 span 也不看：

```python
def _one_tree(spans):
    if not spans or len({s["traceId"] for s in spans}) != 1:
        return False
    ids = {s["spanId"] for s in spans}
    roots = [s for s in spans if s["parentSpanId"] is None]
    return len(roots) == 1 and all(s["parentSpanId"] in ids for s in spans if s["parentSpanId"] is not None)
```

然后对声明做带记忆的深度优先：边界直接贡献它缺的项，声明贡献它依赖的声明缺的项，用集合去重。环用当前路径检查，不能用全局 visited：测试里 "every hop is traced" 被两条路径引用，全局集合会把它误判成环。最后按 BOUNDARIES 里的位置排序，声明按给定顺序返回。

测试里的主运行，span 全都是同一个 trace id，但 d 的父 span 没被收到，所以 "every hop is traced" 不成立，依赖它的声明也都缺这一项。authorization 是模拟的，虽然报了两项 evidence，也一项都不算。

## 这套题证明了什么，没证明什么

通过了说明你能在一个组合了网关、无状态 MCP 请求、任务轮询和 trace 的流程里顺着错误码找到根因，能把论文 fixture 无损地存进 CSV，能写出带预算、部分失败和 ttl 兜底的并发编排，能按固定顺序流式输出 Markdown，并能沿依赖图判断哪些声明本地已经证明。它和本课的 `code/main.py` 一样，只是协议形状的模拟：不涉及真实的 MCP 传输、OAuth 授权服务器、A2A Agent Card 和远程调用、浏览器里的 MCP App、OpenTelemetry SDK 和 collector，也不涉及沙箱。本课 Use It 一节列的那八次升级，每一次都要跨过真实边界的集成测试，需要另外动手做。
