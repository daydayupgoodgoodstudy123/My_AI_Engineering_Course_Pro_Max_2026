# 参考答案讲解：CrewFlow（14/15）

计时结束后再看。参考实现在同目录的 `crewflow/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 crew 和 Flow

**现象**：解锁后的第一个错误是 `memory.py` 的 `embed` 里报 `AttributeError: 'dict' object has no attribute 'lower'`，调用它的是 `recall_long_term`，而这两处都没有 bug。

**顺着往上找**：`embed` 拿到的是一个 dict，那是 editor 的输出，一份结构化的 Brief（课里练习 5 的 `output_pydantic=Brief`）。它怎么进的长期记忆？`SequentialCrew.kickoff` 对每个任务都调了 `write_long_term`，不管任务是不是 persistent。写入时没有报错，因为原来的 `write_long_term` 只是把记录存起来，到查询时才嵌入。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. **只有 persistent 的任务写长期记忆**。`kickoff` 里加 `if task.persistent:`。这就是课里 Pitfalls 说的 “Memory always-on”：每次运行都写，向量库越来越大，检索越来越吵，写入要限定在事实确实需要长期保留的任务上。只让 `embed` 接受 `str(text)`，报错是没了，但 draft 也留在了长期记忆里，下一条断言正好查这个。
2. **context 按列出的顺序拼**。课里 Four primitives 说 context 列出上游任务，它们的输出传进来；docstring 写明按 context 列出的顺序，用一个空行连接。原代码先按 context 的顺序排好 `reads`，拼的时候却遍历 `outputs.items()`，挑出名字在 `reads` 里的输出，顺序就成了任务跑的顺序。outline、research、draft 这个 crew 里，draft 的 context 是 `[research, outline]`，拿到的却是 outline 在前。draft 的模型是按输入作答的 `KeyedLLM`，剧本里没有这段输入，报 `Unscripted`。报错在 `llm.py` 的替身里，那里没有 bug，要回到 crew.py 看输入是怎么拼出来的。改成沿着 `reads` 取：`"\n\n".join(outputs[name] for name in reads)`。
3. **有 context 的任务只读 context**。课里 Sequential 那句 “Output of task N is available as context to task N+1” 说的是没写 context 的任务读什么，原代码却给每个任务都先插上上一个任务，只在 context 已经列了它时才不插。第一个 crew 的 edit 自己就把 draft 列进了 context，看不出问题。corrections 的 context 是 `[fact_check]`，fact_check 没发现问题时返回空串，corrections 应该读到空串，却读到了 draft 加空串，把 draft 的正文当成了要改的问题清单。条件改成只在没有 context 时才插：`if i and not reads:`。
4. **一个 topic 可以有多个监听者**。`listen` 里的 `self._listeners[topic] = [fn]` 改成 `setdefault(topic, []).append(fn)`。`kickoff` 本来就是先进先出的队列，修好 `listen` 以后 archive_sources 和 write 都会跑，结束分支的步骤也照样记进 trace。

参考实现写成 `if task.context:` 拼 context、否则读上一个任务的输出，按对象而不是按任务名取输出，效果和上面两处修法一样。

**起始代码里已经对的两处**：空串原样传下去，代码里没有拿真假值判空的 `or`；第一个 agent 运行之前，按任务在 crew 里的位置检查每一个 context，必须是声明在它前面的任务，否则报 ValueError，写出两个任务的名字，不在这个 crew 里的任务也一样。重写 `kickoff` 时这两点都不能丢：照课里的代码写成 `joined or prior`，fact_check 的空串又会换成 draft，corrections 的替身照样报 Unscripted；把检查挪进循环，researcher 已经花掉了一次调用，测试会查替身有没有被调用过。

**计时**：原来的 `recall_long_term` 每次查询都把全部长期记录重新嵌入一遍。这里的嵌入是特征哈希，每个词算一次 sha256，一条 3,000 词的笔记约 1.2 毫秒，而一次 64 维的点积只要几微秒。改成在 `write_long_term` 里嵌入一次，和文本一起存下来，30 次查询从约 2.1 秒降到约 3 毫秒。第一次查询不计时，所以第一次用到时才嵌入、按文本缓存起来的写法也能过。

**护栏**：

- 修第 3 处时不能把回退一起删掉：没有 context 的任务读上一个任务的输出，第一个任务读 `inputs["topic"]`。
- context 用一个空行（`"\n\n"`）连接，顺序按 context 列出的顺序。倒过来或者按任务名排序，第一个 crew 的 edit 读反；按任务跑的顺序，或者让有 context 的任务读此前全部输出，outline 那个 crew 读反。
- 短期记忆在每次 kickoff 开始时清空，只放这一次运行的输出；长期记忆跨 kickoff 保留，第二次 kickoff 的 research 也在里面。
- 把向量按角色缓存会让两次 kickoff 的 research 共用一个向量，“which vector databases” 的召回顺序就错了。

## Part 2 实体记忆

参考实现每个实体一个 dbm 键，值是这个实体全部事实的 JSON：

```python
def remember(self, entity, facts):
    if not entity:
        raise ValueError("an entity needs a name")
    if not facts:
        return
    known = self.recall(entity)
    known.update(facts)
    self._db[entity.encode("utf-8")] = json.dumps(known)
```

`recall` 用 `self._db.get(...)` 取出来再 `json.loads`，没有就返回 `{}`；`entities` 把键按 UTF-8 解码后排序。

容易漏的几点：

- **打开方式**：`dbm.open(path, "c")`。`"n"` 每次打开都会清空，第二次 kickoff 什么都看不到；`"w"` 在文件不存在时直接报错。
- **合并而不是覆盖**：第二次记 Acme Labs 只给了 seats 和 renewal，plan 必须还在。
- **键是 bytes**：读回来要按 UTF-8 解码，`str(key)` 和 Latin-1 都会把 `株式会社ネコ` 弄坏。
- **值原样往返**：结尾的换行、CRLF、两头的空格、引号、等号、反斜杠，JSON 都能存准；`key=value` 行或者 strip 都不行。
- **按名字精确查**：课里说 entity 记忆 “keyed by entity, not by similarity”。按前缀扫描或者统一小写，Acme 会拿到 Acme Labs 的事实。查 `acme` 或者末尾带空格的 `Acme `，都应该什么也没有。
- **排序不能省**：gdbm 和 ndbm 按哈希顺序返回键，dbm.dumb 按插入顺序。Python 3.13 起新文件默认用 dbm.sqlite3，它按字节序返回键，碰巧和 `sorted()` 一样，在那上面忘了排序测试看不出来，换个后端就错了。
- **交出去的是副本**：每次都从 JSON 读，自然是新的 dict。如果加了内存缓存，就要拷一份再给。
- **文件格式**：别的工具也读这个文件，所以每个实体一个键、值是 JSON 对象。一事实一个键、额外的索引键、pickle、JSON 列表都会在最后的检查里挂掉。

## Part 3 经理路由

每一轮先调一次 manager，发给它的是 `ManagerView`：全部任务；此前每一次专家调用的（角色，输出），按先后排列，被拒的草稿也在内，改派的那一轮记在实际跑的专家名下；此前每次被拒的 pick 的理由。同时记下这次调用的账：任务数，和此前所有输出的字符数。

manager 回 `"done"` 就结束；回的名字不是专家就报 ValueError；否则检查被挑中的专家能不能跑：

```python
def blocker(i):
    if i == 0:
        return None
    upstream = roles[i - 1]
    if upstream not in latest:
        return f"{roles[i]} needs {upstream}'s output first"
    needed, got = self.specialists[i].min_paragraphs, paragraphs(latest[upstream])
    return f"{roles[i]} needs {needed} paragraphs from {upstream}, got {got}" if got < needed else None
```

不能跑就记下理由，从它的上游开始往前找第一个能跑的专家，让它在这一轮里跑。往前找的路上遇到的其他专家不算被拒，它们的阻塞原因不记进 refusals。writer 重做时读的是 researcher 的输出，不是自己被拒的草稿；editor 最后读到的是最新的那份。

几个容易错的地方：

- **段落**：逐行扫描，只含空白的行是空行，连续的非空行算一段。`"\r"` 被 `strip()` 去掉，所以 CRLF 不用单独处理。只按 `"\n\n"` 切，碰到只有空格的空行和 CRLF 就数错了。
- **规则由代码执行**：manager 只是提议，三段的门槛是 Specialist 上的 `min_paragraphs`，由 crew 检查。测试另有一个门槛是 2 段的 reviewer，写死 editor 和 3 过不了。
- **轮数**：被拒的那一轮也算一轮，说 done 的那一轮也算。所以完成的运行里 manager 调用次数总是专家调用次数加一，这里是 5 和 4。
- **manager 税**：这组数据里 manager 一共带了 610 个字符的此前输出，专家自己读的输入一共只有 233 个字符。课里说 manager 调用 “carries the full task list plus prior outputs”，每一轮都比上一轮多，总量是平方级的。

## Part 4 Flow 事件日志

参考实现给每个步骤开一个 asyncio 任务，任务结束时把（步骤、结果、异常、耗时）放进一个队列；生成器从队列里按完成顺序取，每取一个就输出一行，同时给它 emit 的 topic 的每个监听者开新任务。用一个计数器记还有几个步骤没完成，归零时结束：

```python
launch(self._start, payload)
pending = 1
try:
    while pending:
        step, result, error, ms = await finished.get()
        pending -= 1
        ...
        for listener in self._listeners.get(topic, []):
            launch(listener, out)
            pending += 1
        yield logfmt([...]) + "\n"
finally:
    for task in running: task.cancel()
```

- **同时开始，完成就输出**：测试的消费者每读到一行才放行下一个步骤，所以一个一个 await、按层 gather、按层 `as_completed`、先跑完再一起输出，都会等不到下一行。
- **分支结束**：返回 None、或者 emit 了没人监听的 topic，只结束这一条分支，其他分支照常跑。
- **logfmt**：值为空，或者含空格、双引号、等号、反斜杠、换行、回车、制表符时，加双引号并转义这五种字符。`json.dumps` 看起来差不多，但会把非 ASCII 字符写成 `\u` 转义。
- **出错**：任务里捕获异常放进队列，生成器先输出 `error=` 那一行，再抛出原来的异常；`finally` 取消还在跑的步骤并等它们结束。用 TaskGroup 的话要把 ExceptionGroup 拆开。
- **耗时**：在包装步骤的任务里计时，从步骤开始运行算起，四舍五入到整数毫秒。

## Part 5 运行比对

先把一组兄弟节点变成以（名字、出现序号）为键的有序字典，再递归：

- 好的那次的每个节点：坏的那次没有就记 missing，不再往下；有就用 `!=` 比 output（`""` 和 None 不一样），不同记 changed，然后接着比子节点。
- 同一层里只有坏的那次才有的节点记 extra，排在这一层好的节点之后，按坏的那次的顺序。哪怕它在坏的那次里出现得更早（triage 那个用例），也不插到前面去。
- 所有差异按遇到的先后放进一个列表，最后再按种类拆成三个列表；first 就是列表里的第一个。

```python
for key, node in mine.items():
    path = prefix + f"{key[0]}[{key[1]}]"
    other = theirs.get(key)
    if other is None:
        found.append(("missing", path))
        continue
    if node.output != other.output:
        found.append(("changed", path))
    walk(node.children, other.children, path + "/")
```

这样对齐，第二个 intake 插进来只算一个 extra，后面的步骤不会跟着错位；同名的 review 和 revise 按第几次出现一一对应；只有一边有的子树只报一次。课里说 Crew 直接上生产时 “on-call cannot diff a bad run against a good one”，Flow 给每个步骤固定的名字，这棵树才对得齐。

## 这套题证明了什么，没证明什么

通过了说明你能在一个 CrewAI 形状的代码库里顺着调用链调试 context 传递、记忆写入范围和 Flow 的监听者注册，能把实体事实精确地存进 dbm 并跨 kickoff 读回，能实现一个带门槛、会拒绝和改派、会记 manager 税的层级 process，能写出并发执行、完成即输出 logfmt 的异步 Flow，也能把两次运行的 trace 树对齐并找出第一个分叉点。

它没有涉及真实的 CrewAI API 和真实的 LLM：manager 的决定、专家的输出都是脚本，`expected_output` 和 backstory 没有被用来生成内容，嵌入是特征哈希而不是真实的 embedding 模型，Contextual 记忆、`@tool` 和 `BaseTool`、`output_pydantic` 的校验和重试也都没有考到。练习 1、4、5、6、7 需要另外动手做；编排者和 supervisor 的更多形态在本章 12 课和 28 课。
