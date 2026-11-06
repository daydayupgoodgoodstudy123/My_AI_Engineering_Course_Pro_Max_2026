# 参考答案讲解：ActorRT（14/14）

计时结束后再看。参考实现在同目录的 `actorrt/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 runtime

**现象**：解锁后的第一个失败是死信不对。死信队列里只有一条，是 checklist 的 start 消息，原因却是 reviewer 抛的 `TypeError: snippet 1 is not text`；reviewer 自己那条 review 不在死信里，snippet 2 也没有被审。ReviewerAgent 和 ChecklistAgent 都没有 bug。

**顺着往上找**：start 的 handler 只是在循环里给 reviewer 发 review，它自己不会抛 TypeError。reviewer 的异常能落进 checklist 的 handler，说明 reviewer 是在 checklist 的 handler 里面被调用的。根源在 `Runtime.send`：在 handler 里调用时，它不入队，直接调用收件人的 `receive`。这就是 v0.2 的 `agent_a.chat(agent_b)`：A 被阻塞到 B 返回，B 的异常顺着调用栈传回 A，runtime 只能在最外层接住，记到 A 正在处理的那条消息上，A 的 handler 也断在了半路。课里说 In v0.4, `send(agent_b, msg)` puts the message in agent_b's inbox and returns. The runtime delivers later。故障隔离就是从这里来的：发件人不在收件人的调用栈上（测验 Q3）。

**依次修四处**：

1. **send 只入队**。去掉直接调用 `receive` 的分支，消息一律进队列，由 `run_until_idle` 按发送的顺序一条一条投递。reviewer 的异常这时在 runtime 里被接住，记在 review 那条消息上；checklist 的 handler 正常跑完，snippet 2 照常送审。只在 send 里给直接调用包一层 try/except 不够：死信对了，可 reviewer 还在 checklist 的 handler 里同步跑，max_messages 管不住它，第 2 处的 outbox 也拦不住它。测试用 `run_until_idle(max_messages=1)` 检查：处理完 start 以后，两条 review 必须还在队列里，reviewer 一个 verdict 都还没给。
2. **handler 发的消息等它返回再入队**。send 在 handler 里调用时先放进 outbox：

   ```python
   self._outbox = []
   try:
       actor.receive(message, self)
   except Exception as e:
       self._dead_letter(message, f"{type(e).__name__}: {e}")
       return
   finally:
       sent, self._outbox = self._outbox, None
   for queued in sent:
       self._enqueue(queued)
   ```

   抛异常时 outbox 整个丢掉，原消息进死信，这就是测验 Q11 第 2 问说的“先收集，成功后由 runtime 统一提交”。`finally` 保证失败以后 outbox 也会复位，否则之后从外面 send 的消息会掉进一个没人提交的列表。这一处要等第 1 处修好才看得出来：同步投递时，splitter 转发的 gamma 在它抛异常之前就已经送到了。
3. **checklist 等每条 snippet 都有 verdict 再下结论**：`len(self.results) == len(self.snippets)`。原代码写死了 3，而且只要已到的都 ok 就先宣布 True。部分运行时、某条 review 抛异常永远回不来时、4 条 snippet 时，它都会给出错误结论（测验 Q9）。review 回不来时 consensus 一直是 None：故障被隔离了，也被藏起来了。
4. **订阅按 topic 建索引**：`dict[topic, dict[name, None]]`。原代码 subscribe 在一个列表里查重，publish 每次扫描全部订阅，8000 个订阅加 20000 次发布本机约 1.3 到 1.6 秒，限值是 0.1 秒；按 topic 查表约 3 毫秒。内层的 dict 当有序集合用：重复订阅不会重复投递，顺序是第一次订阅的顺序。

**护栏**：

- **深拷贝起始代码已经做对了**，改 send 时不能弄丢。时机必须是 send 被调用的那一刻：测试在 send 之后往自己的列表里追加了一条，Batcher 发出一对之后马上清空缓冲区接着用，送达时才拷贝、handler 返回时才拷贝，接收方都会看到改过的内容。publish 对每个订阅者各调用一次 send，所以每个订阅者各有一份：只拷一次、让所有订阅者共用，checklist 的 `pop("id")` 会让 audit 报 KeyError；浅拷贝挡不住嵌套的 issues 列表，reviewer 存的 issues 会被 checklist 排了序；以为排了队就不用拷贝、把拷贝删掉，也是 audit 的 KeyError。课里说 two actors cannot share memory，在 actor 模型里这一条要由 runtime 保证，不能指望每个 actor 自觉。
- **按发送的顺序投递**。先处理最新的消息，或者把 handler 发出的消息插到队首，reviewer 的 verdict 顺序和 max_messages 那一段已到的 verdict 数都会变。
- **丢弃以一次 handler 调用为单位**。reviewer 审完 snippet 0、它发出的两条 verdict 还排在队列里时 snippet 1 失败；Splitter 那一段也一样，第一批的 alpha、beta 还在队列里时第二批失败。按发送者清队列、按 mid 清队列，都会把成功调用发出的消息一起丢掉。
- 索引用 set 会打乱顺序，用 list 会重复投递。只给 publish 建了索引、subscribe 还在列表里查重，8000 次订阅本身就要 0.2 到 0.3 秒。

## Part 2 收件箱日志

日志是只追加的二进制记录，每条一个 13 字节的头（类型、mid、长度）加 payload：

```python
HEADER = struct.Struct(">cQI")

def _append(self, kind, mid, payload):
    self._file.write(HEADER.pack(kind, mid, len(payload)) + payload)
    self._file.flush()
```

打开时用 `a+b`，先 `seek(0)` 读出全部内容，逐条解析完整的记录，再重放：M 加进待处理，A 和 D 把它移出去，D 同时记进死信；下一个 mid 是出现过的最大 mid 加 1。runtime 在三个地方写日志：`_enqueue`（消息真正入队时写 M）、`_dead_letter`（写 D）、handler 返回并提交完 outbox 之后（写 A）。

容易漏的几点：

- **M 在提交时写，不在 send 时写**。失败的 handler 发出的 alpha 拿到了 mid 5，但从来没有入队，日志里也不能有它，否则重启以后它会被投递出去。这和 Part 1 的 outbox 是同一件事。
- **A 写在最后**。handler 返回、它发出的消息都写进日志以后才写 A。顺序反过来，两次写之间崩溃，重启后这条消息算处理过了，它发出的消息却没了；在调用 handler 之前写 A 更糟，handler 中途崩溃时消息直接丢掉。现在的顺序下，最坏情况是重启后再处理一次，也就是 at-least-once，handler 要能承受重复。
- **只捕获 Exception**。测试用一个 BaseException 模拟进程在 handler 里死掉：它必须穿过 `run_until_idle` 往外走，日志里那条消息没有 A，重启后还在。
- **每条都 flush**。测试在日志还开着时直接读文件，缓冲区里的数据它看不到。flush 只是交给操作系统，要扛住断电还得 fsync。
- **下一个 mid 看整个日志**。只看待处理消息，全部处理完以后会从 1 重来；按 M 的条数算，跳过的 mid 5 会让新消息和 mid 7 撞车；取最后一条记录的 mid 也不行，第一次重启时最后一条是 A3，m4、m6、m7 还在队列里。
- **截掉残缺的尾巴**。进程死在追加的中途，文件末尾会留下半条记录。读的时候丢掉它，写新记录之前把文件截回最后一条完整记录。只跳过不截断，新记录接在残片后面，下次从残片那里开始读歪。用 `a+b` 打开，截断以后的写入自动落在新的末尾；用 `r+b` 打开再截断，写指针还在旧的末尾，新记录前面会多出一段零字节。
- **恢复不是重发**。待处理消息原样放回队列，带着原来的 mid，不再写一遍 M；死信也直接放回列表，不再写一遍 D。打开日志不往里写任何东西。
- **body 原样往返**。标准库 json 默认就能分清 `True` 和 `1`、`-0.0` 和 `0.0`，也能存 `2**64 + 1` 和 `0.1 + 0.2`；`sort_keys=True` 会改掉键的顺序。D 的原因按 UTF-8 文本存，`no actor 'büro'` 测的是长度按字节算。

## Part 3 群聊编排

team 本身就是 manager actor，所有交互都是消息：

```python
def _next_turn(self, runtime):
    if len(self._messages) >= self.max_messages:
        self._stop_reason = "max_messages"
        return
    last = self._messages[-1][0] if len(self._messages) > 1 else None
    speaker, reason = self.select(last)
    self._selections.append((speaker, reason))
    self._waiting = speaker
    runtime.send(self.name, speaker, "speak", [list(m) for m in self._messages])
```

收到任务时记下 `("user", task)` 再选第一位；收到正在等的那个人的 said，记下来，含终止词就停，否则选下一位。别人的 said 一律忽略。上限在选人之前检查，所以任务本身也能占满 max_messages：`max_messages=1` 时没有人发言。

`run()` 发出任务，然后反复跑 runtime，直到聊天停下或者 runtime 空闲：

```python
self.runtime.send("user", self.name, "task", task)
while self._stop_reason is None and not self.runtime.run_until_idle():
    pass
```

`run_until_idle()` 每次最多处理 runtime 的 max_messages 条（默认 100），返回 False 只说明这一次到了上限，聊天还在进行。一个 60 条消息的聊天要 119 条 runtime 消息，只调一次会停在第 50 条。空闲了还没停才是 stalled：某个参与者失败了，它的 speak 在死信队列里，manager 永远等不到回答。

选人：

```python
def _after(self, last):
    if last is None:
        return self.participants[0]
    return self.participants[(self.participants.index(last) + 1) % len(self.participants)]

def select(self, last):                      # SelectorGroupChat
    choice = self.selector(list(self._messages), list(self.participants)).strip()
    if choice not in self.participants:
        return self._after(last), "unknown"
    if choice == last and not self.allow_repeated_speaker:
        return self._after(last), "repeat"
    return choice, "selector"
```

RoundRobinGroupChat 的 select 就是 `self._after(last), "rotation"`。回退永远从最后一个发言者往后数，所以“选择者给了坏答案”和“固定轮转”在同一个位置接上。名字要整串相等：`the reviewer` 这种带了多余字的回答算未知名字，按子串在回答里找名字会把它当成选中了 reviewer。

终止词用 `re.compile(rf"\b{re.escape(stop_word)}\b")`，区分大小写：`APPROVE!`、`Looks good. APPROVE!` 算，`APPROVED`、`DISAPPROVE`、`approve` 不算。终止在每条消息之后检查，先查终止词再查上限；任务本身不查，它是指令，常常就写着终止词。

回退、终止这些细则是这套题自己定的，课里只说了 RoundRobin 固定轮转、Selector 按上下文挑下一位；真实框架的具体行为以它的文档为准。

## Part 4 跨主机帧

课里说 Inbox + transport is the same abstraction whether the actor is in-process or on another host。这里的做法是给对端的每个 actor 在本机注册一个替身 RemoteActor：发给它的消息照常入队、照常投递，它的 handler 把消息编成帧写到链路上。对端的 `serve()` 把帧解出来，用自己的 `send` 投递。Part 1 的 ChecklistAgent 和 ReviewerAgent 一行不改就能分在两台主机上跑。

读端是一个跨块保留的缓冲区，逐帧往外取：

```python
def __iter__(self):
    while len(self._buffer) >= LENGTH.size:
        (size,) = LENGTH.unpack_from(self._buffer)
        end = LENGTH.size + size
        if len(self._buffer) < end:
            return
        payload = bytes(self._buffer[LENGTH.size:end])
        del self._buffer[:end]
        if size:
            yield _fields(payload)
```

`serve()` 先把已经在等的帧发出去，然后每读一块就 feed 进去，每取出一帧就 send、`run_until_idle()`、把这期间写出的帧逐个 yield，最后 `close()` 检查有没有剩下半帧。

- 长度是 payload 的字节数，`ensure_ascii=False` 时一定要先 encode 再量。
- 心跳（长度 0）跳过；空字符串、null 的 body 是正常消息。
- 帧是逐个解析、逐个投递的，所以坏帧前面的帧都已经投递完、回复也发出去了，ValueError 才冒出来，坏帧后面的帧不再投递。先 `list(reader)` 把一整块全解析出来再投递，坏帧会连累前面的好帧。
- 坏帧要按 docstring 检查到底：是 JSON 对象，sender、recipient、topic 都是字符串，有 body。只看键在不在，`"topic": null` 的帧会被投递出去。
- 流结束时缓冲区里还有字节就是断在帧中间，哪怕只剩 1 到 3 个字节、连长度头都不完整。
- mid 是各自主机的编号。帧里的 mid 让对方能去重，但本机投递时要拿本机的 mid。
- 测试的探针记录每个回复出来时读了多少字节、reviewer 给出了几个 verdict，用来确认回复是在引起它的那一帧之后马上发出的，而不是攒到一块读完或者整个流读完。

## Part 5 spawn 树

runtime 记下每个 actor 的孩子（按 spawn 顺序）、顶层 actor 和已停止的集合。停止是后序遍历，孩子从最后 spawn 的开始：

```python
def visit(node):
    for child in reversed(self._children[node]):
        visit(child)
    if node not in self._stopped:
        self._stopped.add(node)
        order.append(node)
        self.actors[node].on_stop(self)
```

- 停止的 actor 留在 `actors` 里，只是进了 `_stopped`。投递时先查名字在不在，再查是否已停止，这样死信原因分得开（`no actor 'nobody'` 和 `stopped`），名字也不会被重用。
- 发给已停止 actor 的消息不在 stop 时挪走，轮到它时才进死信，所以死信的顺序就是投递的顺序。
- 已停止 actor 之前发出的消息照常投递。在 handler 里停止自己不是失败，这次 handler 发出的消息照常提交。
- 树是 handler 用 grow 消息一层一层长出来的，spawn 的时间顺序（pool、ingest、index、parse、fetch、shard-0、shard-1、tokenize）和先序不同，所以“按 spawn 时间倒序停”会在 ingest 那棵子树上露馅：它先停 tokenize，正确的顺序是 fetch、tokenize、parse、ingest。
- 级联停止跳过已经停止的部分：on_stop 只调一次，stop 只返回这次新停的名字。

## 这套题证明了什么，没证明什么

通过了说明你能在 actor runtime 里查出同步调用造成的错位死信和失败 handler 的副作用，能把收件箱做成崩溃后可恢复的日志，能在 runtime 上实现两种群聊的选人和终止规则，能写出按任意分块到达都正确的长度前缀帧收发，也能处理 spawn 树和级联停止。

它没有涉及真正的并发（每个 actor 一个 asyncio 队列，测验 Q10），没有真实的模型调用、网络连接和重连，也没有 OpenTelemetry 的 span（练习 4，本章 23 课）。AutoGen 和 Microsoft Agent Framework 的真实 API 要另外动手对照（练习 5）。
