# 参考答案讲解：ReactLoop（14/01）

计时结束后再看。参考实现在同目录的 `reactloop/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 agent loop

**现象**：解锁后的第一个错误是 `record` 里的 `KeyError: 'tool_calls'`。模型直接作答时回复里没有这个键。

**依次修四处**：

1. **没有工具调用就停**。`record` 改用 `reply.get("tool_calls", [])`，`run` 在记录完回复后加上停止条件：这一轮没有工具调用，正文就是答案，停止原因是 `no_tool_calls`。这是课里五要素第 3 条列出的停止条件，也是练习 2 要补的那条路径。原代码只认 finish。
2. **推理项要跟着回传**。修好第 1 处后，第二个场景在第二轮报 `ProviderError: missing reasoning item for assistant turn 1`，报错的位置在模型替身里，但那里没有 bug。顺着往上找：替身检查的是请求里每个 assistant 消息的 `reasoning`，这个字段是 `record` 填的，而 `record` 只存了可读的 `thinking`，漏了不透明的 `reasoning`。课里说推理内容在独立通道上，并且要跨轮传回去；在生产环境里它是加密的，客户端看不懂，只负责原样带回。
3. **先绑定参数，再运行工具**。原来的 `dispatch` 把整个调用包在 `except TypeError` 里，`int(None)` 这种工具内部的错误也被报成 `bad args`，模型会以为是自己参数写错，换着参数一直重试。用 `inspect.signature(fn).bind(...)` 先检查参数：绑定失败才是参数错，绑定成功之后工具抛出的任何异常都是工具自己的错误。
4. **每个 observation 只格式化一次**。原来的 `messages()` 每一轮都把历史里所有工具结果重新格式化，再用 `replace` 拷出新的 Message。1000 步的任务要做五十万次格式化，本机约 1.7 到 1.9 秒。改成在 `act` 里格式化一次，把字符串存进工具消息的 `content`，`messages()` 直接返回历史的拷贝，约 9 毫秒。这样做还有一个好处：历史里存的就是模型当时读到的 observation，转录（Part 2）里能直接看到。

**护栏**：

- 正文和工具调用同时出现时不能停。“有正文就停”的写法会把 “Let me work out the tax first.” 当成答案。
- `"tool_calls": []` 也是没有工具调用。只判断键在不在的写法会多问一轮，替身报 `no scripted reply left`。
- 没有正文的回复照样结束，答案是空字符串。
- finish 是循环自己的停止条件，不交给注册表执行。
- `bind_partial` 不检查缺少的参数，`kv_set(key="tax")` 会被当成工具错误。按 TypeError 的消息里有没有 “argument” 来猜也不行：`int() argument must be ...` 正好包含这个词。
- 自己对着签名检查参数，容易只查一半：只查缺了哪些参数，会放过多给的 `warehouse="north"`；只比参数个数，会放过写错名字的 `item="A-1"`；只检查 dict 形式的参数，ReAct 文本给的位置参数 `["A-1", "north"]` 就漏了。`bind` 把这几种情况一起处理了。
- 为了提速只缓存格式化好的视图、历史里不存 observation，或者存了 observation 却丢了原始结果，都会被最后两条断言抓住。

## Part 2 转录快照

参考实现先把每条消息 `asdict`，把 `reasoning` 换成标准 base64 文本（没有就保留 None），整体 `json.dumps` 成一个字符串，然后：

```python
fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
except BaseException:
    os.unlink(tmp)
    raise
```

读的时候反过来：`ToolCall(**call)` 重建工具调用，`base64.b64decode(..., validate=True)` 还原推理项。

容易漏的几点：

- **推理项是不透明的字节**。替身给的推理项以 `rs\x80` 开头，不是合法的 UTF-8：`.decode()` 直接报错，`errors="replace"` 不报错但改了字节。改过的字节读回来对不上，接着跑时新的替身会拒绝这段对话。
- **格式和 trace viewer 共用**。hex、latin-1、URL-safe base64、`base64.encodebytes`（每 76 个字符加一个换行）都能往返，但 viewer 读的是标准 base64。测试用 `b"\xfb\xff\x00rs"` 钉住了 `+` 和 `/`：`+/8AcnM=`。没有推理项要写 null，写成空的 base64 读回来就成了 `b""`。
- **半个 emoji**。快递接口按 UTF-16 截断备注，留下一个单独的高位代理 `\ud83d`。默认的 `json.dumps` 把它写成 `\ud83d` 转义，能原样往返。`ensure_ascii=False` 写 UTF-8 时报 UnicodeEncodeError；再加 `errors="surrogatepass"` 能往返，但文件不再是合法的 UTF-8，viewer 读不了。
- **整体替换**。临时文件要建在目标所在的目录里：`os.replace` 在同一个文件系统内是一次原子的改名，跨文件系统会直接报 OSError。`write_text` 或者直接 `json.dump` 到目标文件，是在原来的文件上改写：已经打开旧快照的读者会读到新内容，进程中途崩溃时还会留下半截文件。
- **失败的保存不留痕迹**。工具返回了 set，JSON 存不了，保存要报错，旧快照原样保留，目录里也不能多出临时文件。先 `json.dumps` 成字符串再建临时文件，这两点就都满足了。`default=str` 会把 set 悄悄写成字符串，看起来成功了，其实丢了信息。
- 61 位的订单号、`-0.0`、`0.1 + 0.2` 这些值，标准库的 json 本来就能存准。测试里的 `exact()` 区分 `-0.0` 和 `0.0`、`1` 和 `1.0` 和 `True`，防的是自己做了多余的转换。

## Part 3 ReAct 文本

`parse_step` 逐行扫描 completion：

- 遇到以 `Observation:` 开头的行就停，这一行和后面的内容都丢掉。观察只能由运行时写，模型自己编的观察不能进 prompt，更不能被拿来行动。
- 遇到第一个以 `Action:` 开头的行也停，后面的行不管是不是第二个 Action 都丢掉。前面的行去掉开头的 `Thought:` 就是 thought，可以跨多行；行中间出现的 `Action:`、`Observation:` 都不算。
- 动作行读 `name(` 之后，用 `json.JSONDecoder().raw_decode` 一个一个读双引号字符串，中间只允许逗号和空格，最后必须是 `)`，后面不能再有内容。JSON 的转义规则正好覆盖 `\"`、`\\`、`\n`、`\u00e9`，还会把 `\ud83d\ude9a` 这样的代理对拼成一个字符，原样的非 ASCII 字符也不受影响。读之前先确认下一个字符是 `"`，否则 `raw_decode` 会把 `42` 也当成参数读进来。
- finish 必须恰好一个参数。

常见的错法都在参数上：`split(",")` 会把 `"office rent, Paris (France)"` 拆开；`\(([^)]*)\)` 遇到参数里的括号就断；`ast.literal_eval` 接受单引号和尾逗号；`json.loads("[...]")` 接受数字；`unicode_escape` 会把 `東京` 弄坏；按 Python 字符串字面量解码，代理对会变成两个单独的代理。

`run_react` 每一步把 `step.text`（completion 切到动作行为止）和运行时的 Observation 接到 prompt 后面。Observation 是 `observe(工具结果)`：搜索工具返回的是列表，经过 `to_observation` 才是 JSON，直接写进 f-string 是 Python 的 repr。读不出动作时回填固定的 FORMAT_ERROR，循环继续，模型下一步可以自己改正，这正是练习 3 要的效果。端到端那段里，模型第一步就编了一个 “9000 EUR” 的观察，参考实现把它丢掉，换成搜索工具返回的真实结果。

## Part 4 推理通道 SSE

`stream_run` 和 `run` 的控制流一样，只是改成从替身的 `stream()` 读：

```python
async for kind, value in loop.model.stream(loop.messages()):
    if kind == "thinking":
        yield _event("reasoning", value)
    else:
        reply = value
message = loop.record(reply)
```

之后按 `run` 的规则停止，或者对每个工具调用先发 action，再执行，再发 observation。

- **换行**：SSE 的行尾只有 CR、LF、CRLF 三种，参考实现用 `re.compile(r"\r\n|\r|\n")` 切，CRLF 要排在 CR 前面。`split("\n")` 会让安装进度里单独的 CR 留在 data 行中间，浏览器会把它当成换行，后半截变成一个无效字段被丢掉。`splitlines()` 会在 U+2028 上切开（菜单里正好有），空字符串还会切出零行，事件没有 data 就不会被派发。`[\r\n]+` 把连续的换行当成一个，最终答案里的空行就没了。
- **`data: ` 后面的空格**：客户端会去掉冒号后的一个空格。不写这个空格，`  1. read the menu` 这样的缩进就会少一格。
- **通道分开**：thinking 只出现在 reasoning 事件里；跟工具调用一起来的正文（“Checking the menu.”、“Fertig.”）不是答案，不发；final 恰好一次，finish 和“没有工具调用”两条路都要发。
- **发生即发出**：每片 thinking 一到就 yield，动作在工具执行前发出。测试用替身的 `sent` 计数和工具执行次数检查每个事件发出的时刻。
- **历史一致**：`loop.record(reply)` 把推理项存进历史，第二轮替身才不会报错。测试最后用同一个脚本跑一遍 `run()`，两份历史必须完全相同。

## Part 5 嵌套观察

递归 `_render(value, depth, ..., path)`，`path` 是当前这条路径上容器的 id 集合：

- 在 `path` 里就写 `[cycle]`；空容器写 `{}` 或 `[]`；深度超过 `max_depth` 写 `{…}` 或 `[…]`。
- 否则把自己的 id 放进 `path`，dict 按 `sorted()` 后的前 `max_items` 个键、list 和 tuple 按前 `max_items` 项递归，返回前在 `finally` 里把 id 移出去。剩下的写成 `… k more`。
- 标量和字符串用 `json.dumps(..., ensure_ascii=False)`，键也一样。手写成 `f'"{key}"'` 的话，`C:\Users` 这样的键里的反斜杠不会转义。

两个最容易错的地方：

- **环和共享**。`path` 必须在返回时移除。用一个从头到尾不清空的 seen 集合，同一个作者第二次出现就被写成 `[cycle]`，可那只是共享，不是环。
- **预算**。结果是字符串时原样输出，但同样受预算限制。预算按字符计，`TRUNCATED` 也算在内：`text[: budget - len(TRUNCATED)] + TRUNCATED`，结果正好 `budget` 个字符；没超过就不截。

最后一段把格式化器接到 loop 上。页面树里每个子页面都有指回父页面的引用，默认的 `to_observation` 会报 `Circular reference detected`，整个循环就崩了。课里说每个错误都要变成 observation 字符串而不是崩溃，换成这个格式化器后，模型读到的是带 `[cycle]` 的、长度可控的字符串。

## 这套题证明了什么，没证明什么

通过了说明你能在一个 agent 循环里调试停止条件、推理项回传和工具错误的归类，能把转录存成可回放、可接着跑的快照，能严格地解析 ReAct 文本，能把运行过程按 SSE 推给前端，也能把嵌套的工具结果变成确定、有长度上限的 observation。

它没有涉及真实的模型 API、真实的加密推理项格式和 token 计数，也不涉及工具调用 id 的关联、并行调用、回合上限和参数类型校验，这些在第 13 章 01、03 课。课里讲的信任边界（工具输出里的指令）和级联失败，分别在本章 27 课和 26 课。
