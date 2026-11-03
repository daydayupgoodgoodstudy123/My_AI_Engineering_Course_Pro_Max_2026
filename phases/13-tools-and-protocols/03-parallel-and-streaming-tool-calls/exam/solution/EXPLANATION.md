# 参考答案讲解：Fanout（13/03）

计时结束后再看。参考实现在同目录的 `fanout/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修扇出代码

**现象**：解锁后的第一个错误是 `CallBuffer.to_call` 里的 JSONDecodeError，而 `to_call` 本身没有 bug。

**顺着往上找**：打印 `buf.chunks`，里面是 `{"city"`、`{"city`、`: "Zur`、`{"city": "Beng`、`ich"}`，三个调用的片段混在一个缓冲区里。缓冲区是 `on_event` 用 `event.get("id")` 找的，可是讲义说得很清楚：OpenAI 只在一个调用的第一个片段里带 id，之后靠 index 归并。args_delta 和 call_stop 拿到的键都是 None，`defaultdict` 又一声不响地给 None 建了缓冲区，于是错误一直拖到解析时才冒出来。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `on_event`：缓冲区按 `event["index"]` 找。id 和 name 在 call_start 时记到这个 index 的缓冲区里。
2. `replay_and_execute`：每个任务直接产出自己那条 tool message，再按完成顺序收：

   ```python
   tasks.append(asyncio.create_task(answer(buf.to_call(), executors)))
   ...
   return [await task for task in asyncio.as_completed(tasks)]
   ```

   原来的代码拿 `as_completed` 的结果和 `in_flight` 的键 zip。`as_completed` 给出的是按完成先后排好的结果，不告诉你它属于哪个调用；键的顺序却是 call_stop 的顺序。乱序完成时，call_A 就拿到了 Bengaluru 的天气。这就是讲义说的 id 关联陷阱。
3. `answer`：`except Exception` 时返回 `tool_message(call.id, error=error)`。一个工具失败，只是它自己那条消息是错误，别的调用照常回答。只接 `LookupError` 不够，测试里还有一个抛 ConnectionError 的时钟服务。
4. `run_parallel`：先把所有任务建好，再按完成顺序收。原来的 `await asyncio.create_task(...)` 写在循环里，建一个等一个，看上去是并发，其实是串行：250 个 8 ms 的调用要 2.4 秒，修好后约 12 毫秒。

**护栏**：

- 每个调用只执行一次，只能在自己的 call_stop 之后开始，而且要在流还没读完时就开始。每来一个分片就试一下 `json.loads`、能解析就提前执行，正是讲义的 parse-early 陷阱，会挂在 "a call starts only after its call_stop"。先收齐整轮再统一执行，会挂在 "while the rest of the turn is still streaming"，讲义的原话是 "not after all streams end"。
- 回复按完成顺序。换成 `gather` 能修好错配，但顺序成了 call_stop 的顺序。讲义的建议是按完成顺序回复、带上显式 id。
- 一轮里的调用全部同时开始。给 run_parallel 加信号量或者分批跑，上限只要不太小，计时都能过，可测试会数同时在跑的调用有几个，250 个必须都在。要限流，得像 Part 3 那样把上限写进计划里。

## Part 2 调用日志

一条记录是 `struct.pack(">I", len(body)) + body`，其中 body 是状态字节、2 字节 id 长度、id、负载。参考实现打开日志时做三件事：

```python
while pos + LENGTH.size <= len(data):        # 剩下不足 4 个字节：长度本身就是残的
    (size,) = LENGTH.unpack_from(data, pos)
    end = pos + LENGTH.size + size
    if end > len(data):                       # 正文不够：最后一条被截断了
        break
    ...
self._file = open(self._path, "ab")
self._file.truncate(pos)                      # 新记录接在最后一条完整记录后面
```

容易漏的几点：

- **长度按字节**：负载是 UTF-8，`"°C"`、`"Föhn"`、`"🌧"` 都不止一个字节。先 encode，再取 `len`。
- **append 返回时就在文件里**：每次写完 `flush()`。测试在 close 之前就去读文件。
- **为什么要长度前缀**：负载里有 `\n` 和 `\r\n`，按行分隔会切错；文本模式读会把 `\r\n` 变成 `\n`。二进制加长度前缀，内容是什么都能原样读回。
- **先校验再写**：started 只能一次，done 只能在 started 之后、也只能一次。重开后已回答的集合要从文件重建，否则同一个调用会被记两个答案。
- **in_flight 按日志顺序**：参考实现按记录的先后筛出没有答案的 started。拿集合相减会丢掉顺序，测试里 call_C 排在 call_B 前面，按 id 排序也不对。
- **残尾要截掉**：只在读的时候跳过还不够，之后 append 的记录会接在残片后面，下次读就错位了。
- **resume**：只跑 `in_flight()` 里的调用，只写 done。call_A 已经有答案，再跑一次就是讲义说的重复结果；对有副作用的工具来说，就是同一件事做了两遍。

## Part 3 扇出调度

先在模拟之前把输入查完：limit、重复 id、未知依赖，然后在依赖图上查环。参考实现的 `_reject_cycles` 是 Kahn 算法：反复拿掉已经没有依赖的调用，拿不完的就在环上或者环后面。环要在图上查，不能等模拟完看谁还在等：测试里有一个挂在失败调用后面的环，create_file 失败后，write_file 和 read_file 都被当成下游跳过了，模拟结束时什么也没剩下。

然后用离散事件模拟。状态是一个按 `(结束时刻, 声明顺序)` 排的小根堆，加一个先来先服务的等待队列：

1. 有空位就从队头取调用开始，开始时刻是当前时刻。空位一空出来马上能用。
2. 时钟跳到最早的结束时刻，把这一刻结束的调用全部弹出，标成 ok 或 failed。
3. `settle()`：先把失败的下游一层层标成 skipped（循环到没有变化为止，因为声明顺序不一定是拓扑顺序），再把依赖全部 ok 的调用按声明顺序排到队尾。
4. 回到第 1 步，直到队列和堆都空了。图里没有环，所以每个调用最后不是跑过了，就是被跳过了。

最后按声明顺序列出每个调用的 slot。

三个容易错的地方：

- **先来先服务**：tokyo 从 0 就在等，write_file 到 100 才就绪，空位先给 tokyo。真实的 host 用 `asyncio.Semaphore` 限流时也是这样，先排队的先拿到。
- **同一时刻**：a 和 b 同时在 100 结束，要先把两个都处理完、再排下游，下游按声明顺序排：after_b 在前。
- **失败与跳过**：失败的调用跑满了自己的时长，计入 wall_ms 和 serial_ms；跳过的调用不占位置、不计时间。

这组数据里并行是 800 ms，串行是 1800 ms，就是讲义 benchmark 里的 max 和 sum；limit 为 1 时两者相等。

## Part 4 流式结果

关键是读流和出结果要同时进行。参考实现用一个读流的任务往队列里放行，生成器只管从队列里取：

```python
reader = asyncio.create_task(read())          # 读事件；call_stop 时 create_task(run(buf))
while (line := await lines.get()) is not None:
    yield json.dumps(line) + "\n"
```

- call_A 的执行器一结束，`run` 就把这一行放进队列，生成器马上 yield，这时模型还在写 call_B。测试里的“模型”会停下来等这一行，只在两个事件之间检查结果的写法会卡住。
- call_cancel：从缓冲区里 pop 掉，马上放一行 cancelled。
- finish：没收到 call_stop 的调用按 index 顺序各放一行 incomplete，然后等所有正在跑的调用回答完，最后放一个 None 结束。call_D 的参数已经是完整的 JSON，可它没有 call_stop，不执行：讲义说正确的闸门是结束信号，不是“能解析了”。
- `run` 里 `except Exception` 把错误变成这一行的 error，别的调用不受影响。
- 生成器的 finally 里取消读流任务和还在跑的调用，消费方中途退出时不会留下野任务。

`asyncio.wait` 同时等“下一个事件”和正在跑的调用，也是正确的写法。

## Part 5 增量参数解析

逐字符走一个很小的状态机：一个括号栈、是否在字符串里、上一个字符是不是没用完的反斜杠，再加上当前顶层成员的原文。

- 在字符串里：反斜杠把下一个字符吃掉（不管是 `"`、`\\` 还是 `u`），没被吃掉的 `"` 才结束字符串。状态存在对象上，所以反斜杠落在两块之间也没问题。
- 不在字符串里：`{` 和 `[` 入栈；`}` 和 `]` 要和栈顶配对；栈深为 1 时的逗号和最后的 `}` 结束一个顶层成员。
- 成员结束时，对它的原文做一次 `json.loads("{" + text + "}")`。这一步同时完成了解码（`city`、代理对）和这个成员内部的语法检查，所以成员里的错误最迟在它后面的逗号或右括号处报出来。

这样 `members` 里只会有已经定了的值：块在 `"n": 1` 处断开时，n 的逗号还没来，不会被列出来。讲义说数花括号只能当调试用的经验法则，`{"q": "a}b"` 就是反例。

逐字符自己构造值、在字符串右引号处就列出成员，也是正确的做法；测试只检查两种做法结论一致的地方。

## 这套题证明了什么，没证明什么

通过了说明你能在流式 tool call 的代码里调试 id 关联和并发问题，能设计一个可以从崩溃中恢复的二进制日志，能写离散事件模拟来规划有依赖和限流的扇出，能用 asyncio 边读流边输出结果，也能写一个不会被字符串和转义骗过的增量解析器。它不涉及真实的 OpenAI、Anthropic、Gemini 流格式之间的转换（第 13 章第 02 课），不涉及取消竞态和超时（第 29 课），也没有在真实网络和真实限流下测过性能。讲义练习 3 里线程池和 asyncio 的对比、练习 5 读各家文档的部分，需要另外动手做。
