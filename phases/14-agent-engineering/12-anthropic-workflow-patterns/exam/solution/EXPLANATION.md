# 参考答案讲解：Workflows（14/12）

计时结束后再看。参考实现在同目录的 `workflows/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修四种模式

**现象**：解锁后第一个错误是测试替身报的 `Unscripted: no reply scripted for 'Summarize this ticket for a person to pick up: ...'`。traceback 一路是 `route` → triage 处理器 → `prompt_chain` → 模型替身，而 `prompt_chain` 本身在这里没有错。

**顺着往上找**：triage 是 default 处理器。一张退款工单为什么会走 default？打印分类器的原始输出，是 `'Refund\n'`。`route` 直接拿它去查 `handlers`，查不到，就落到了 default。docstring 写的是先去掉首尾空白、再转小写。这一关想练的是：报错的地方往往不是出错的地方，要先问“这个 prompt 是谁发的”。

**依次修六处**：

1. `route`：`label = (await classifier(input_text)).strip().lower()`。
2. `prompt_chain`：`template.replace("{text}", current)`。原来的 `str.format` 会把 JSON 示例里的 `{"order": ...}` 当成格式字段，报 `KeyError: '"order"'`；docstring 要求除了 `{text}` 以外原样发出去。
3. `route` 没有 default 时抛 `UnknownRoute`，消息里写出标签。原来返回 `(label, "no handler for ...")`，调用方会把这句话当成处理结果。
4. `evaluator_optimizer` 轮数用完时返回 `Refined(None, rounds)`。课里的写法两条出口都返回 `candidate`，被拒的稿子和通过的稿子长得一样（测验 Q9）。
5. `max_iter < 1` 抛 `ValueError`。原来 `range(0)` 一轮都不跑，`return` 时 `candidate` 还没赋值，报 `UnboundLocalError`。写成 `if not max_iter` 只拦得住 0，负数照样混过去。
6. `parallel_vote`：边回来边计票，某个答案超过 n 的一半就收场，收拾干净再返回。原来的 `gather` 要等齐所有票：测试里 7 票的那次投票，10 毫秒时 yes 已经有 4 票，可有两个调用卡了 2 秒，整次投票跟着等了 2 秒；过半就收场以后约 10 毫秒。

   ```python
   calls = [asyncio.ensure_future(llm(prompt)) for _ in range(n)]
   try:
       counts = Counter()
       for reply in asyncio.as_completed(calls):
           answer = await reply
           counts[answer] += 1
           if counts[answer] * 2 > n:
               return answer, counts
   finally:
       for call in calls:
           call.cancel()
       await asyncio.gather(*calls, return_exceptions=True)
   votes = [call.result() for call in calls]  # 没有过半：按提交的顺序重新计票
   ```

**护栏**：

- 收场以后不留尾巴。`cancel()` 只是请求，被取消的调用要等下次运行时才收到 CancelledError，测试替身收到以后还要三轮事件循环才关掉连接。所以取消以后要 `await asyncio.gather(*calls, return_exceptions=True)`，等它们真正结束：只 cancel 不等，或者只给一轮 `sleep(0)`，返回时它们还在跑；不加 `return_exceptions=True`，CancelledError 会从 `parallel_vote` 里冒出来。取消和等待放在 finally 里，某个调用抛了异常、或者 `parallel_vote` 自己被取消时，其余的调用也会被收掉。
- 过半是超过 n 的一半，不是超过已经回来的票数的一半，也不是正好一半。2 比 2 没有多数，要等齐 4 票再按平票规则裁决。
- 不加超时丢票。有了多数，剩下的票改变不了结果，所以不用再等；没有多数，每一票都要等。测试里 2 比 2 的那次，0.25 秒才回来的那张 no 决定了平票。
- counts 是过半那一刻已经回来的全部票，包括输掉的那些，测试里就是最先回来的那张 no。
- 平票取最先提交的那一票。as_completed 那份 Counter 是按回来的顺序插入的；没有过半时按 `calls` 的顺序重新计一遍，`most_common` 平票时保留先插入的，课里原来的平票规则就照样成立。直接用按回来顺序记的那份，测试的三方平票会选到最快回来的 unsure。遍历 `asyncio.wait` 返回的 done 集合收票也不行，集合的顺序取决于对象地址。
- 300 个调用全部同时在飞，不加限流。这次投票分成 140、120、40，没有答案过半，要等齐 300 票，一个接一个 await 约 2 秒。测试数了同时在飞的调用数，用 Semaphore 把上限设成 50，时间上过得去，这一条过不去。
- 只替换 `{text}`，别的花括号原样保留。先试 `str.format`、失败再 replace 的写法，碰到 `{{agent_name}}` 不会失败，而是悄悄把它变成 `{agent_name}`；`re.sub` 会把上一步输出里的 `C:\Users` 当成替换模板里的转义；`replace(..., 1)` 只换第一个。
- 规范化只做两件事：去首尾空白（tab 也算）、转小写。再多做一点，比如子串匹配或者取第一个词，"refund request" 就会被送进退款链。

## Part 2 XML 审计记录

参考实现的文档长这样：

```xml
<?xml version='1.0' encoding='utf-8'?>
<run id="run-0007" pattern="routing">
  <step name="classify">
    <input>Label this ticket as refund, bug or sales: I want my money back</input>
    <output>Refund
</output>
  </step>
  <step name="lookup">
    <input>order A-981</input>
    <output encoding="base64">G1szMm1zaGlwcGVkG1swbQA=</output>
  </step>
  ...
  <branch>refund</branch>
  <output encoding="base64">...</output>
</run>
```

- **XML 装不下的值才编码**：XML 1.0 不允许 tab、换行、回车以外的控制字符；元素文本里的回车会被解析器换成换行。参考实现用一个正则判断值里有没有这两类字符，有就存 UTF-8 的 base64，并加 `encoding="base64"`；其余的值原样放进元素文本，`&`、`<` 由 ElementTree 转义，读回来自动还原。换成自己设计的转义也可以，但转义符本身也要转义：grep 那一步的彩色输出里，真的 ESC 和源码里字面的 `\x1b` 在同一个值里。
- **None 和空串**：None 就是不写这个元素；空串写一个空元素，读回来 `.text` 是 None，要当成 ""。
- **顺序和重复**：每个步骤一个 `<step>` 元素，按顺序写，名字放在属性里。属性能装任何文本，名字重复也没关系；名字当标签名的话，"refund/extract" 这种就成了非法 XML。
- **不改值的排版**：`ET.indent` 只改有子元素的元素的文本和各元素的尾部，叶子元素的文本不动，所以缩进后值不变。读的时候不能 strip。
- **文件和 id**：`<run_id>.xml`，run id 只能是 ASCII 字母、数字、`-`、`_`，用 `fullmatch` 和写明的字符类检查：`^...$` 会放过结尾的换行，`\w` 会放过非 ASCII 字母。文件不存在时把 FileNotFoundError 换成 KeyError。

把值都放在属性里也可以：ElementTree 会把属性里的回车、换行、tab 写成字符引用，读回来不变，只剩控制字符需要编码。

## Part 3 编排者-工作者

每一轮：

```python
subtasks, done = _parse_plan(await planner(task, list(results)), workers)
new = [s for s in dict.fromkeys(subtasks) if s not in ran]   # 先去重，再去掉跑过的
batch = new[:max_subtasks]                                     # 然后才截
dropped.extend(new[max_subtasks:])
outputs = await asyncio.gather(*(workers[s.worker](s.task) for s in batch))
```

- `Subtask` 是 frozen dataclass，可以哈希，`dict.fromkeys` 去重时保留第一次出现的位置，去重的键就是 (worker, task)。
- `ran` 只记真正跑过的子任务。被截掉的进 `dropped`，不进 `ran`，所以下一轮还能再要，测试里 docs 那条就是第一轮被截、第二轮跑的。
- `gather` 让同一轮的子任务同时跑，并且按 batch 的顺序返回输出；结果按这个顺序追加，所以综合时的顺序是编排者要的顺序，和谁先跑完无关。
- `_parse_plan` 先把整份计划检查完：必须是 JSON 对象，`subtasks` 是列表，`done` 是真正的布尔值，每个子任务都有字符串的 worker 和 task，worker 都存在。任何一条不满足就抛 PlanError，这时还没有任何子任务开始。
- 每一轮传给编排者的是 `results` 的副本，也就是到目前为止的全部结果，不只是上一轮的。
- 跑完这一轮再看 done；到了 max_rounds 就退出循环，不再要计划。一轮里没有新的子任务时什么也不跑，但循环照常进入下一轮，编排者下一份计划还可能要新的。最后不管有没有结果，都调用一次综合。

## Part 4 路由流

结构是三部分：每张工单一个任务，一个拉取任务，加上 async generator 本身。

```python
async def handle(ticket, arrived):
    label = (await classifier(ticket.text)).strip().lower()
    async with gates[label]:                 # 每条路由自己的 Semaphore
        output = await handlers[label](ticket.text)
    ...
    lines.put_nowait(json.dumps(record, ensure_ascii=False) + "\n")

async def intake():
    async for ticket in tickets:            # 来一张就开一个任务，拉取循环从不等闸门
        spawn(handle(ticket, time.perf_counter()))
    await asyncio.wait(in_flight)           # 源结束后，等在途的工单做完
    lines.put_nowait(None)
```

- 分类和闸门都只在工单自己的任务里等，拉取循环从不等，所以退款路由满了，销售工单照样马上进来、马上处理；分类器慢的时候，几张工单也是同时在分类。
- 每张工单做完就把它的那一行放进队列，generator 从队列里取，所以输出是完成顺序；第一张做完时后面的工单还没到，第一行就已经发出去了。
- 未知路由直接生成 error 行；handler 抛的异常也在任务里接住，变成 `"RuntimeError: issue tracker is down"` 这样的 error 行，别的工单不受影响。
- ms 用工单被拉进来那一刻的时间算，包括等闸门的时间。
- generator 的 finally 取消拉取任务和所有在途任务，再等它们结束。消费方提前 `aclose()` 时，GeneratorExit 从 yield 处抛出，finally 照样会跑。拉取任务一定要取消：关闭以后再拉进来的工单没有人处理，等于丢了。

## Part 5 成本上界

逐类型递归，返回 `Bounds(min_calls, max_calls, worst_ms)`：

| 类型 | 最少调用 | 最多调用 | 最坏延迟 |
|---|---|---|---|
| llm / tool | 1 / 0 | 1 / 0 | ms |
| chain | 各步最少之和 | 各步最多之和 | 各步之和 |
| route | 分类器 + 分支最少中的最小 | 分类器 + 分支最多中的最大 | 分类器 + 分支延迟中的最大 |
| parallel（sections） | 之和 | 之和 | 最大 |
| parallel（n 份） | n × 最少 | n × 最多 | 一份的延迟 |
| evaluator-optimizer | 提议 + 评估（1 轮） | m × (提议 + 评估) | m × (提议 + 评估) |
| orchestrator | 规划 + 综合 | r × (规划 + k × 最多的 worker) + 综合 | r × (规划 + 最慢的 worker) + 综合 |

测试的客服流程里，route 的最少、最多和最坏延迟分别来自 spam（1 = 只有分类器）、sales（1 + 35 = 36）和 refund（300 + 6150 = 6450）。orchestrator 里调用最多的 worker 是 pricing（4 次），最慢的是 legal（1800 毫秒），两个上界要分别取。sales 每轮 4 个槽位、只有 3 个 worker，最多调用仍然是 2 × (1 + 4 × 4) + 1 = 35：同一个 worker 一轮可以领几个不同的任务。

n、max_rounds、max_subtasks、max_iter 四个计数都经过 `_count`，小于 1 就报 ValueError。用 `value < 1` 而不是 `not value`，负数才拦得住。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着调用链找到根因，能让并发投票在过半时立即收场、取消并等待还在跑的调用，同时不改变平票规则，能设计一种审计员读得懂、又能逐字往返的 XML 记录，能写有上限的编排者-工作者循环并保住综合顺序，能写按路由限流、按完成顺序输出的异步流，能对嵌套的工作流规格算出精确的成本上界。它不涉及真实的 LLM 调用、提示词质量、分类器的准确率，也不涉及课里 Use It 一节提到的框架（LangGraph、AutoGen、CrewAI、Claude Agent SDK）。练习 2 里卡住的调用进了 Part 1，可没有答案过半时整次投票的截止时间只在追问里；练习 1 的置信阈值、练习 3 的 top-2 也只出现在追问里，需要另外动手做。
