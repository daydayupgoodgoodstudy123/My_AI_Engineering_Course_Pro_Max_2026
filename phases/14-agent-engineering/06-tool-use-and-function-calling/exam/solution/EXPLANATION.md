# 参考答案讲解：ToolCall（14/06）

计时结束后再看。参考实现在同目录的 `toolcall/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修参数校验和超时

**现象**：解锁后的第一个失败是 `a number must be finite before the tool runs`，观察内容是 `execution error: ValueError: cannot convert float NaN to integer`。报错的是测试里的工具 `set_thermostat`，它本身没有 bug。

**顺着往上找**：模型的参数是 JSON 文本，Python 的 json 模块会把 `NaN` 读成 `float('nan')`。`_coerce` 的 number 分支看到 float 就原样收下；`validate` 里的 `nan < 5` 和 `nan > 30` 都是 False，范围检查也放过了它。于是 NaN 一路到了工具手里，在 `round()` 上炸掉。这一关想练的是：观察说"工具出错"，但真正的问题是这个值根本不该到工具那里。

**依次修四处**：

1. number 分支先得到一个 float，再用 `math.isfinite` 检查。json 读出来的 NaN 和 Infinity、字符串 `"nan"`、溢出成无穷大的 `1e999` 都在这里被挡住。只用 `math.isnan` 会放过无穷大；把 NaN 的几种写法列成一张表，会漏掉 `"1e999"`。
2. 字符串只在和 JSON 写法完全一样时才转：integer 用 `-?(?:0|[1-9][0-9]*)`，number 用 JSON 的数字语法，都用 `fullmatch`，字符类写 `[0-9]`。`int()` 和 `float()` 太宽松：会去掉首尾空白，接受 `+` 号、前导零、下划线和任何 Unicode 数字。正则里的 `\d` 和 `str.isdigit()` 同样认 Unicode 数字，照 JSON 语法写、只在首位用 `[1-9]` 也挡不住 `"1٣"`；`re.match` 加 `$` 会放过末尾的换行。
3. 日期交给解析器：`date.fromisoformat(text).isoformat() == text`。`fromisoformat` 负责"这一天存不存在"，和 `isoformat()` 比较负责"写法是不是 YYYY-MM-DD"：Python 3.11 起 `fromisoformat` 还接受 `20260302` 和 `2026-W10-1`，`strptime` 接受不补零的 `2026-2-5`，这两种比较一下就挡掉了。
4. 在线程里运行工具，`join(tool.timeout_s)` 之后线程还活着就回超时观察：

```python
worker = threading.Thread(target=run, name=f"tool-{tool.name}", daemon=True)
worker.start()
worker.join(tool.timeout_s)
if worker.is_alive():
    return ToolResult(call.tool_use_id, False,
                      f"timeout: {tool.name} did not finish within {tool.timeout_s} s")
```

Python 杀不掉线程，所以"超时"只是不再等它。卡住的线程会自己跑完，它的副作用照样发生（测验 Q10）。`run` 要把执行器的异常存下来交回主线程，否则 `flaky` 的 ConnectionError 就丢了。

**护栏**：常见的改坏写法各有一条断言接着。把所有字符串都拒掉，`"5"` 就转不成 5；在 `with ThreadPoolExecutor()` 里等结果，退出 with 块时会等那个卡住的调用，还是 2.5 秒；整个 registry 共用一个单线程的池，卡住的调用占着线程，正常的 `lookup` 也排队超时；闰日 2028-02-29 必须能通过。

## Part 2 用例库

每条用例一个键：键是 id 的 UTF-8 编码，值是 `json.dumps(dataclasses.asdict(case))`。读的时候把 `accepted` 重新组装成 `Call`。

容易漏的几点：

- **键是 bytes**：`keys()` 返回 bytes，要 `decode("utf-8")`。`str(key)` 得到的是 `"b'...'"`；按 Latin-1 解码，`weather/zürich 3` 会变成乱码。
- **键要可逆**：id 里的 `/`、空格和非 ASCII 字符 dbm 都能存，不需要转义。把空格换成下划线这类"清理"会让 `rename report` 和 `rename_report` 撞成同一个键。
- **打开方式**：`"c"` 是没有就新建、有就打开；`"n"` 每次都清空。
- **顺序**：`keys()` 是哈希顺序，`ids()` 要自己排序，`cases()` 跟着 `ids()`。
- **原样存**：每一个可接受答案都用 Part 1 的 `validate` 检查，但只看它报的错误。它返回的参数是强转过的，number 参数上的 200 会变成 200.0，存进去或者写回调用方的 `call.args`，类型就变了。测试里的 `typed()` 把每个值和类型一起比较，因为 Python 里 `200 == 200.0`。
- **先查后写**：所有拒收条件查完了才写入；id 重复报 ValueError，不覆盖；查工具 schema 之前先确认工具在目录里。
- **值是 JSON**：别的工具也要能读这个库，测试会直接打开 dbm 文件检查。

## Part 3 BFCL 式评分

`grade` 按类别选方法：Live 和 Non-Live 看调用（AST 匹配），Multi-Turn 和 Agentic 看重放后的状态，Hallucination 看有没有调用。

AST 匹配把每个调用变成规范形式，再比较多重集合：

```python
args = {name: prop["default"] for name, prop in props.items() if "default" in prop}
args.update(call.args)
for name, value in args.items():
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if number and props[name].get("type") == "number":
        args[name] = float(value)
return call.name, json.dumps(args, sort_keys=True)
```

- 两边都补 default，所以省略 `unit` 等于写了 `"celsius"`，但不等于写了 `"fahrenheit"`。没有 default 的参数，一边有一边没有就对不上。
- 只有 number 参数按数值比较；其余的值连 JSON 类型一起比，`"4"`、4、4.0 是三个不同的值。评分器不做强转，因为它量的是模型写了什么。
- `sort_keys` 让参数顺序无关；`Counter` 让并行调用顺序无关，同时要求条数一致。
- 目录里没有的工具、schema 里没有的参数，规范形式是 None，什么都对不上。
- 规范形式是新建的 dict。可接受答案也经过同一个函数，在 `call.args` 上原地补 default、转 float，用例里的 200 就成了 200.0。

状态式评估从 `copy.deepcopy(case.initial_state)` 开始，通过 `FakeDrive.registry(case.tools)` 按顺序重放。走 registry 有两个作用：只有这条用例提供的工具能跑，参数像运行时一样被校验和强转，所以 `text` 写成数字的 `write_file` 被拒掉，到不了网盘。失败的调用不改变状态，重放继续。只做浅拷贝的话，`files` 字典是共用的，评一次分用例就被改掉了。

同样四个调用（读、写、删、删），在 Multi-Turn 的 `rename report` 上是对的，在 Live 的 `rename_report` 上是错的：状态一样，调用和可接受答案不一样。这就是课里说的 V3 为什么要看 API 的真实状态。

加权：先求每类的正确率，再按 40/30/10/10/10 加权。空的类别是 None，权重去掉后其余的重新归一化。没有 attempt 在每一类都算错，包括 Hallucination：没有回答不等于拒绝调用。`score_run` 里 attempts 缺的用例按 `grade(case, None)` 评，不是 `[]`。

## Part 4 TAP 流水线

```python
tasks = [asyncio.create_task(run_one(case)) for case in cases]
try:
    for number in range(1, len(cases) + 1):
        verdict = await graded.get()
        verdicts.append(verdict)
        yield _tap_line(number, verdict)
finally:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
```

- 每条用例一个 task，`run_one` 在 `async with slots` 里问模型、评分，结果放进队列。task 按列表顺序创建，Semaphore 按先来先得放行，所以"空出一个位置就开始下一条"。
- 编号按从队列里取出的先后，这就是 TAP 要的递增编号。
- 模型或评分抛的异常在 `run_one` 里接住，变成 `error: 类型: 消息` 的错误判定，照样进队列，照样计入分数。测试里评分的异常来自一条目录缺 description 的用例：`FakeDrive.registry` 报 `KeyError: 'description'`。多行的消息用空格接起来，一个用例只占一行。
- 最后写 `# score` 和计划行。分数用 Part 3 的 `summarize`，出错的用例也在里面。
- `finally` 在读者调用 `aclose()` 时也会执行：取消还在跑的 task，并等它们结束，`aclose()` 返回时就不会有 task 还在调模型。

## Part 5 调用链引用

分两遍：

1. **静态检查**：call id 不能重复；递归找出参数里所有以 `$<id>.result` 开头的字符串，解析成 (目标 id, 步骤列表)。格式不对、目标不存在、目标是自己或者后面的步骤，都在执行任何一步之前报 ChainError。
2. **按顺序执行**：每一步先解析参数里的引用，再调 `execute`，结果按 call id 存下来。每一步只执行一次，后面的引用都从存下来的结果里取。

解析一个引用时，每一步都检查类型：

```python
for key, end in steps:
    if isinstance(key, str):
        if not isinstance(value, dict) or key not in value:
            raise ChainError(f"{ref}: nothing at {ref[:end]}", call_id, ref, ref[:end])
    elif not isinstance(value, list) or key >= len(value):
        raise ChainError(f"{ref}: nothing at {ref[:end]}", call_id, ref, ref[:end])
    value = value[key]
return copy.deepcopy(value)
```

- 解析器记下每一步在原文里的结束位置，`ref[:end]` 就是报错时的 `at`。
- 字符串在 Python 里能按下标取，所以要明确要求数组；字段缺失要报错，不能用 `.get()` 变成 None。
- 返回值不再经过 `_resolve`，所以结果里长得像引用的字符串不会被解析。`_resolve` 每次都新建 dict 和 list，传进来的 steps 不会被改动。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试参数校验（NaN、宽松的数字解析、日期、线程超时），用 dbm 原样存取评测用例，实现 AST 匹配、状态式评估和按类别加权，写一个带并发上限、能取消的异步评测流水线，以及解析嵌套的结果引用。它不涉及真实模型和真实的 BFCL 评测脚本：本题的匹配规则、类别分工和权重归一化是对课里描述的简化，不是 BFCL 官方实现。V4 新增的 web search、memory 和格式敏感性类别没有建模，Toolformer 的自监督训练也没有涉及。课里练习 3 的熔断器和练习 5 的 Pydantic 移植需要另外动手做。
