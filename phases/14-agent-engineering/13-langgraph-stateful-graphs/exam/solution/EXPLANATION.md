# 参考答案讲解：StateGraph（14/13）

计时结束后再看。参考实现在同目录的 `stategraph/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修暂停与恢复

**现象**：解锁后的第一个错误是 `resume` 抛出的 `PausedAtNode: human_gate`。人已经批准了，`human_gate` 这一次返回的也是 `{}`，没有要求暂停，运行时却又停了。

**顺着往上找**：是否暂停，`_loop` 看的是 `state.get(PAUSE)`。恢复时的 state 来自检查点，而检查点是在 `pop(PAUSE)` 之前写下的，带着第一次暂停时的标记。节点的 update 合并进来以后，旧标记还在，于是又停了一次。报错发生在恢复时，出错的却是更早那次写检查点。课里 `main()` 恢复前手动 `pop("_pause_reason")`，绕开的就是这个问题。

**依次修四处**：

1. 先把暂停标记从 update 里取出来，再写检查点。标记是节点给运行时的信号，既不进检查点，也不进 state。
2. `_position` 返回 `graph.next_node(here, state)`，不是 `here`。最后一个检查点对应的节点已经完成，恢复从下一步开始（课里说 resume picks up from step N+1）。下一步用应用过 patch 的 state 来选：批准了就走 send；没批准时 gate 自己的边把流程送回 gate，再停一次。找恢复位置时要跳过 HUMAN 记录，人的修改不是节点。
3. `next_node` 每步只调一次 router，再按标签找边；标签没有对应的边，或者节点根本没有出边，抛 GraphError。原来每条条件边各调一次 router，router 是 LLM 时既贵，前后几次的回答还可能不一样；返回 None 又让 `_loop` 静默结束，调用方分不清是跑完了还是走丢了。
4. 记录里只放这一步写了什么（`Record` 的 docstring 就是这么规定的），读的时候按 reducer 从第 0 步一直折叠到最后一步。原来每一步都把整个 state 交给 `put` 去 deepcopy，1500 篇文档的工具状态加上越来越长的消息列表，800 步要 2 到 3 秒；改完以后约 6 到 10 毫秒。

**护栏**：最省事的提速是去掉 `put` 里的 deepcopy，或者换成 `dict(...)`。Notebook 节点每一步交回的都是同一个还在增长的列表，检查点不自己拷贝一份，历史里每一步都会变成最后的样子。真正的 checkpointer 写盘时值就固定了，内存替身必须和它一样。另一个方向是只存 update、读的时候不折叠，这就是课里说的 Checkpoints too small：恢复后的 state 里只剩最后一步写的东西，send 找不到 ticket。

## Part 2 SQLite 检查点

参考实现用两张表：`steps(session, step, node, calls)` 一步一行，`writes(session, step, channel, value)` 一个通道一行。没写任何通道的一步（暂停的 gate）只有 steps 里的那一行，照样是一个检查点。

值用带类型标签的 JSON。标量原样写，list 写成 JSON 数组，其余容器都写成只有一个键的对象，键名就是类型：`{"tuple": [...]}`、`{"set": [...]}`、`{"frozenset": [...]}`、`{"bytes": "<base64>"}`、`{"dict": [[k, v], ...]}`。dict 也打标签有两个好处：键可以是任何可哈希的值，7、"7"、(2, 3)、None、True 互不相同；编码里出现的每个 JSON 对象都是标签，用户自己写的 `{"tuple": [1]}` 不会被认错。读回时先还原里面的元素，再放进 set 或者当作键，这时 tuple 已经是可哈希的了。

容易漏的几点：

- 不认识的类型抛 TypeError，不要用 `default=str` 把它变成字符串。
- set 不排序。里面混着不同类型，排序本身就会报错。
- 写 None 也是一次写入，不能跳过。
- 先把所有值编码好，再在一个事务里插入。只要有一个值编码失败，这一步就一行都不留。
- 同一步不能写两次：在同一个事务里查 `MAX(step)`，新的一步不在它之后就报 ValueError。
- 测试还把每个值编码出来的 JSON 当成普通数据，再 dumps、loads 一遍。普通 dict 原样写成 JSON 对象、靠形状认标签的编码，不管标签长什么样，都会把这份数据认成标签。
- 测试的对照组是同一个图在 InMemoryCheckpointer 上跑出来的记录。SQLite 文件关闭再打开以后，读出的记录要和它逐个类型一致，新建的 Runner 还要能在这个文件上接着恢复。

## Part 3 录制与重放

`NodeContext` 的三种调用都走 `_effect(op, args, live)`：

- 没有录制时调用 `live()`，把 `(op, args, 结果的深拷贝)` 追加到 `calls`。调用抛异常就不记。
- 有录制时，第 i 次调用的 op 和参数必须和录制的第 i 条相同，返回录制结果的深拷贝；超出录制就报 ReplayMismatch。节点返回以后，`finish()` 检查录制有没有用完。

`Runner.replay` 按步号把记录走一遍：START 和 HUMAN 照记录合并；节点步用这一步之前的 state 和带录制的 context 重跑节点，去掉暂停标记后和检查点里的 writes 比较，不一样就报 ReplayMismatch，消息里写上 `step <n>`。整个过程不写检查点，也不碰 World。节点拿的必须是这一步之前的 state：review 写的 asked_at 是第一次问人的时间，state 里已经有了就不再读时钟；先把这一步的 writes 合并进去再重跑，review 少读一次时钟，`finish()` 就会报录制没用完。

两处深拷贝都省不得。quote 节点直接改 API 返回的 dict：录制时不拷贝，录到的是改过的值；重放时不拷贝，录制本身会被节点改掉，第二次重放就对不上。只核对调用也不够：pay_wall_clock 的调用和原来一模一样，只是自己读了 `time.time()`；quote_double_discount 是代码改了，调用没变。这两种只有比较 update 才发现得了。pay_unstamped 少写了 paid_at，只比较节点这次写了的通道也发现不了，所以要拿整个 update 和检查点比。课里说 Resume assumes node inputs produce the same state update，重放检查的就是这个假设。

录制跟着检查点一起写下，崩溃那次尝试什么都没留下，重跑的节点重新抽随机数、重新调接口。这是本题的选择：录制里只有完成了的步骤；代价是崩溃前已经发生的副作用会再发生一次，面试官手册的追问里讨论了另一种做法。

## Part 4 节点增量 SSE

`stream_updates` 是一个 async generator。它自己再写一遍执行循环，复用 runner 的 `_begin`、`_position` 和 `_commit`：

```python
update = target(state, ctx)
if inspect.isawaitable(update):
    update = await update
update = dict(update or {})
reason = update.pop(PAUSE, None)
state = runner._commit(session, graph, step, node, state, update, calls)
yield _event("updates", {"node": node, "update": update}, step)
if reason:
    yield _event("interrupt", {"node": node, "step": step, "reason": reason})
    return
```

- 先写检查点再 yield，START 和 HUMAN 也一样。客户端收到事件时这一步一定已经写下，它在两个事件之间断开也不会丢步。
- 一步一个事件。生成器只在被拉取时往前走，所以事件和节点执行是交错的。
- id 用步号，START 和 HUMAN 也发。恢复以后的流接着上次的步号，客户端凭 Last-Event-ID 就知道该从哪一步补。
- data 里只有这一步写的东西，客户端按 reducer 应用。暂停原因单独放在 interrupt 事件里，发完流就结束。

## Part 5 嵌套子图

`_loop` 遇到子图节点时调用 `_subgraph(ns, node, step, ...)`：

- 子图的命名空间是 `f"{ns}|{node}:{step}"`。带上父命名空间，三层的路径才唯一；带上步号，同一个子图节点在循环里第二次运行时才不会撞上第一次的检查点。
- 命名空间里还没有检查点，就从父图 state 的拷贝开始，写成子图的 START 步；已经有了，说明会话上次停在这里，用 `_position` 从子图里的下一个节点接着跑。
- 子图里暂停时，PausedAtNode 原样穿过父图的 `_loop`，父图不给这个节点写检查点。
- 子图跑完以后，把 START 之后各步写的东西按子图的 reducer 折叠起来，作为这个节点交给父图的 update。要是交出整个最终 state，子图从父图那里继承来的消息会再追加一遍。

恢复时，`_position` 先用 `_stopped_in` 看下一步是不是一个已经有检查点的子图。是的话，patch 原样交给它，一层一层往里传，直到真正暂停的那一层写成 HUMAN 步。人的修改就落在暂停的那个子图里，子图结束时再随它的 update 交回父图。

## 这套题证明了什么，没证明什么

通过了说明你能在一个状态图运行时里调试暂停和恢复，知道检查点该存什么、怎样从增量还原完整的 state，能把 Python 的 state 原样存进 SQLite，能用录制让随机数、时钟和外部调用可以重放，能写按步推送的 SSE 流，也能处理嵌套子图的命名空间和恢复。它不涉及 LangGraph 本身的 API（课里提到的 `create_react_agent`、`create_supervisor` 等），不涉及并行分支的合并、多个进程同时写一个会话，也不涉及崩溃前已经发生的副作用怎样去重。课里的练习 3（并行边和 reducer）和练习 4（移植到 `create_supervisor`）需要另外动手做。
