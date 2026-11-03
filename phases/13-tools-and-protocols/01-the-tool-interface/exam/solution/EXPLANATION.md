# 参考答案讲解：ToolLoop（13/01）

计时结束后再看。参考实现在同目录的 `toolloop/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 tool loop

**现象**：解锁后的第一个错误是 `model.py` 里的 `KeyError: 'call_1'`，而模型替身本身没有 bug。

**顺着往上找**：替身在第 2 轮开头按 call id 去 history 里找自己上一轮调用的结果。history 里确实有一条 tool 消息，但它的 id 是 `call_3f9a…` 这样的随机值。这条消息由 `tool_message` 生成，它照抄了课里 `fake_decide` 生成 call id 的那一行，给每条 tool 消息另造了一个 uuid，而 docstring 写的是 carrying the call's id。报错在下一轮、在另一个文件里，根因在上一轮的 observe。这正是课里说 id 存在的理由：宿主要靠它把结果和具体的调用对上。

**依次修四处**：

1. `tool_message`：`"id": call["id"]`。
2. `validate`：先排除 bool，再判断 int 和 float。Python 的 bool 是 int 的子类，`isinstance(True, (int, float))` 为真，`True + 2 == 3`。课的 quiz Q5 考的就是这一点。
3. `run_loop`：`range(1, max_turns + 1)`。原来少给模型一轮，正好在第 5 轮作答的请求被报成触发了断路器。
4. `Registry`：按名字建一个字典。原来重名检查、`get` 和 `in` 都扫列表，装 7000 个工具是 O(n²)，本机 0.7 到 1 秒，改完 1 到 2 毫秒。字典保持插入顺序，所以 `describe()` 和迭代的顺序都不变。

**护栏**：
- 断路器不能删。一直要调工具的替身必须恰好在第 5 轮停下，`stop` 是 `max_turns`。删掉断路器，替身会在第 101 次被问时报错。
- 轮次从 1 数。改成 `range(max_turns)` 也能跑满 5 轮，但 turn 从 0 开始，第 5 轮作答的请求报的 `turns` 是 4。
- 最后一轮要的调用要真的执行。不执行、只回一条错误结果，history 的形状一样，测试数的是执行器跑了几次。
- 修 bool 不能改成“只收 float”：35 是合法的 number。
- 不能去改替身、把 KeyError 吞掉：替身读到的结果会变成 None，下一条断言就挂。
- 重名检查不能为了提速删掉。只把重名检查换成 set、`get` 还在扫的修法，会被那 3500 次 `get` 抓住。

## Part 2 会话日志

参考实现每次 append 先用 `json.dumps(message, ensure_ascii=False, allow_nan=False)` 生成一整行，编码成 UTF-8 一次写入，然后 flush，最后把这一行再解析一次放进内存，保证内存里的和磁盘上的完全一样。打开时按字节读整个文件，只解析最后一个换行之前的部分。

容易漏的几点：

- **NaN 和 Infinity**：`json.dumps` 默认会写出 `NaN`、`Infinity`，Python 自己读得回来，可这不是标准 JSON。课里说结果必须可序列化，这里的意思是别的读者也能读。`allow_nan=False` 会在写之前抛 ValueError。
- **不要用 `json.dump(obj, f)`**：它边编码边写，遇到 NaN 时前半行已经写进缓冲区，下一次 append 接在后面，那一行就坏了。先在内存里生成整行，再一次写入。
- **flush**：句柄一直开着时，不 flush 的话写入都停在 Python 的缓冲区里，进程死了就没了。测试在不关闭的情况下用第二个实例读同一个文件。
- **非 ASCII 原样写**：`ensure_ascii=False`。日志是给人用 tail 和 grep 看的，写成 `Z\u00fcrich` 就搜不到了。
- **崩溃留下的半行**：判断标准是最后一行有没有换行。崩溃可能切在一个多字节字符中间，所以先按字节切出完整的行，再逐行解码。整行 JSON 完整、只差换行，也算没写完。
- **截断**：丢掉半行之后用 `os.truncate` 把文件截到最后一个换行，位置按字节算。只在读的时候跳过半行，下一次 append 会接在它后面。
- **其他读不出来的行**是损坏，不是崩溃造成的，报 ValueError。崩溃只会留下一段没有换行的尾巴；中间的坏行，或者最后一行换行还在、内容却解析不了，都属于损坏。

## Part 3 Rule of Two

“一次用户请求”就是一次 `run_request` 调用：从用户的消息开始，经过所有模型轮次，直到循环停下。参考实现在循环外面放两个布尔量 `untrusted` 和 `sensitive`，整个请求只初始化一次。

对每个调用：

1. 先 `rejection()`：工具不存在或参数不合法的调用不运行，也不问用户。
2. 算出“如果它运行，请求会带着什么”：`untrusted or tool.reads_untrusted`，`sensitive or tool.touches_sensitive`。调用自己的标志也算在内。
3. 只有 consequential 的调用，并且三项都会凑齐时，才问 `confirm(call)`。只有两项不问；不是 consequential 的调用从来不问。
4. 被拒绝的调用不运行，结果是 `BLOCKED`，照样写一条带自己 id 的 tool 消息，然后继续处理这一轮剩下的调用。它的标志不算进请求，因为它没有运行。
5. 运行的调用才更新 `untrusted` 和 `sensitive`，包括用户同意后运行的调用。参数不合法、被拦下的调用都没有运行，不更新。

几个容易错的地方：污点每轮清零（第 1 轮读网页、第 2 轮读通讯录、第 3 轮发邮件，三项分在三轮）；用户同意一次就不再问，或者把污点清掉（测试里三封邮件依次是同意、拒绝、同意）；把“已经做过有后果的动作”当成第三项去拦后面的纯工具；把污点放在模块级变量里，带进下一个请求；把确认写成单独的分支，只在不需要确认的分支里更新污点。最后这一种最危险：用户同意 forward_inbox 之后，它读进来的邮件没有算进请求，后面的发信就不再问了。

这样写会把 `run_loop` 的循环体再写一遍。也可以让 `run_loop` 接收一个钩子，或者把有后果的工具的执行器包一层再交给 `run_loop`。测试只看行为，几种写法都能通过。

## Part 4 trace 流

格式沿用课里 `run_loop` 打印的那几种行，只有三处不同：没有耗时；值都写成紧凑 JSON（`separators=(",", ":")`，`ensure_ascii=False`）；课里的 `ERROR` 和 `VALIDATION ERRORS` 两种行合成一种 `ERROR` 行，后面是没运行的调用拿到的错误结果。

```python
for call in decision["tool_calls"]:
    yield f"TURN {turn} DECIDE : call {call['name']} id={call['id']}\n"
    yield f"           args = {_json(call['arguments'])}\n"
    result = rejection(registry, call)
    if result is not None:
        yield f"           ERROR : {_json(result)}\n"
    else:
        result = await _execute(registry.get(call["name"]), call["arguments"])
        yield f"TURN {turn} EXECUTE: {call['name']} -> {_json(result)}\n"
    history.append(tool_message(call, result))
```

- 每一步一发生就 yield，所以第一条 DECIDE 和它的 args 行到达时，还没有任何执行器开始。
- 工具不存在和参数不合法走同一个分支，都写 ERROR 行，后面是 JSON 的错误结果。
- history 里的 tool 消息和 `run_loop` 的一样，content 是结果本身，不是 trace 行里那段 JSON 文本。
- 模型要 await。执行器的返回值如果是 awaitable 也要 await，而且 await 要放在 try 里面，异步工具抛的异常才会变成错误结果。
- 执行器抛异常也算跑过，所以写 EXECUTE 行。
- 最终答案之后直接 `return`。断路器那一行只在循环正常走完时写一次。
- 值用 JSON 写，答案里的换行就成了 `\n` 两个字符，一步永远只占一行。

## Part 5 组合工具

`visit(name)` 带备忘：每个工具只算一次，不管有多少条路径通到它。递归会先算被调用者，所以目录按什么顺序排都行。测试把 handle_strike 放在最前面，它调用的 cancel_trip 排在后面，按列表顺序一遍算完的写法会在这里报错。

- `actions` 是所有被调用者的 actions 的并集，再加上自己（如果本身声明为 consequential），排序后去重。菱形里的 charge_card 只出现一次。它不在第一个有后果的工具那里停：handle_strike 经过 cancel_trip，actions 里还有 charge_card 和 send_email。
- 本身声明为 consequential 的工具，路径就是 `(name,)`。
- 否则按名字顺序检查被调用者，取第一个有路径的，接在自己后面。从同一个工具出发的路径在第二个位置就分开了，比的是被调用者的名字，所以这样取出来的就是字典序最小的路径，不需要把所有路径都列出来。它不一定最短：wrap_up 经过 archive_receipts 的那条比经过 send_email 的那条长。
- 先检查所有 `calls` 是否都在列表里，缺的就报 ValueError，写出名字。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的工具宿主里调试，能把会话历史安全地落盘，能按一次请求实现 Rule of Two，能写出逐行流式的异步生成器，也能在调用图上做传播。它不涉及真实的模型调用和三家 provider 的请求格式（第 02 课），不涉及并行调用和流式参数（第 03 课），也不涉及受约束解码和完整的 JSON Schema（第 04 课）。这里的 Rule of Two 只看工具自己声明的标志，没有追踪数据实际流到了哪个参数，也没有防备声明本身被篡改。
