# 参考答案讲解：VoiceBot（06/12）

计时结束后再看。参考实现在同目录的 `voicebot/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修工具调度

**现象**：解锁后的第一个错误是 `check_arguments` 里的 `AttributeError: 'str' object has no attribute 'items'`，而那里本身没有 bug。

**顺着往上找**：传进来的 `args` 是字符串 `'{"seconds": 60}'`。`parse_arguments` 确实把它解析成了 `decoded`，最后却 `return args`，把原字符串交了出去。更隐蔽的是，`check_arguments` 先做的必填检查 `"seconds" not in args` 对字符串是子串匹配，结果为假，没有报错，直到 `args.items()` 才挂。

**依次修四处**：

1. `parse_arguments` 返回解析出来的 dict。
2. `_lookup` 和 `parse_arguments` 抛的 ToolError 要在 dispatch 里接住，变成错误结果。未知工具的错误里列出真实的工具名，LLM 才能改对。
3. `JSON_TYPES` 的键 `"int"` 改成 `"integer"`。原来 `.get(kind, object)` 对整数参数返回 `object`，什么都能过，`"300"` 一直走到 `Timers.set_timer` 里的 `self._clock() + seconds` 才报 TypeError，再被 catch-all 包成一条不提参数名的错误结果。参考实现顺便把布尔值排除在整数之外（Part 5 会考）。
4. 同步工具放进工作线程：

```python
if inspect.iscoroutinefunction(tool.fn):
    value = await tool.fn(**args)
else:
    value = await asyncio.to_thread(tool.fn, **args)
```

麦克风、VAD 和打断检测都跑在同一个事件循环上。课里 Pitfalls 说同步 TTS 会阻塞事件循环，阻塞式的 HTTP 工具也一样：原来的写法让循环停了 2 秒，这 2 秒里用户说什么都听不到。

**两个护栏**：

- 把所有工具都扔进 `to_thread` 是最顺手的改法，但异步工具在线程里只会返回一个协程对象，没人 await，`json.dumps` 报 `Object of type coroutine is not JSON serializable`。
- `except Exception` 要留着。第 3 处的错误被它包成了结果，看着像是它在“藏 bug”，但工具出错交回 LLM 正是课里要求的（"Tools fail. LLM must get back the error"）。改窄以后，天气服务一挂，整轮对话就断了。

## Part 2 会话库

参考实现只有一张表：`seq` 自增主键负责顺序，`at` 记时间，整条消息用 `json.dumps` 存成文本。JSON 能原样还原这一关在意的东西：`None`、嵌套的 dict 和 list、字符串里的每个字节、emoji。

容易漏的几点：

- **原样**：同一个会话里可能混着两家提供方的格式（主模型超时后切到备用模型很常见）。OpenAI 的参数是 JSON 文本，Anthropic 的是 dict；tool_calls 旁边的 `content` 是 `None`；还有 `is_error` 这样的额外键。只存固定几列、把参数统一成 dict、丢掉 `None`，都会让读回来的消息和存进去的不一样。
- **commit 和重开**：`with self._db:` 自动提交；建表写 `IF NOT EXISTS`。
- **过期**：从最后一条消息算，`now - last >= ttl_s` 就算过期。从第一条消息算，正在进行的对话会被中途清掉。
- **重新开始**：过期会话再来消息时，先删掉旧对话再插入。
- **真的删除**：SQLite 删除一行只是把它标成空闲，字节还留在文件里。参考实现在连接上打开 `PRAGMA secure_delete = ON`，删除时把这些字节清零；每次删除后 VACUUM 也行。测试直接读数据库文件找 "Okafor" 和 "Baker"。课里 Pitfalls 的第一条就是 "Logging PII forever"。
- **每条删除路径都算**：会话重新开始时删掉的旧对话，测试当场就读一次文件，所以只在 purge 或 close 里 VACUUM 不够。secure_delete 是连接级的设置，不写进文件，参考实现每次打开都设一遍。

## Part 3 语音工具循环

```python
for step in range(max_steps):
    reply = await llm(messages, box.specs())
    messages.append(reply)
    calls = reply.get("tool_calls") or []
    if not calls:
        return speakable(reply.get("content") or "")
    if step == max_steps - 1:
        messages.extend(answer(call, error=STEP_LIMIT) for call in calls)
        break
    for call in calls:
        result = await box.dispatch(call)
        messages.append(result)
        if not json.loads(result["content"])["ok"]:
            failures[call["name"]] += 1
    if max(failures.values(), default=0) >= 2:
        break
messages.append({"role": "assistant", "content": FALLBACK})
return FALLBACK
```

- 这就是课里 Step 4 的 `continue_streaming(result)`：工具结果回到 LLM，由下一次调用生成要念的话。课里的 `main.py` 一次就拿到了回复，省掉了这次往返，延迟预算也就少算了它。
- 上限数的是 LLM 调用。最后一次回复还要工具时不执行，但这条回复照样进历史，每个调用都补一条错误结果；历史里留着没回答的 tool_call，下一轮请求会被提供方拒绝。先判断“有没有工具调用”，再判断“是不是最后一步”：第 max_steps 次回复如果已经是回答，就照常念出来，端到端那段用 `max_steps=3` 正好考到这一点。
- 课里的规则是 "retry once, then gracefully degrade"：同一个工具第一次失败，错误交回 LLM；第二次失败就停，念 FALLBACK，并把它记成 assistant 的回复。失败按工具名计数，两个不同的工具各失败一次不算重复失败。
- 历史里存 LLM 的原始回复，speakable 只用在要念的那份文字上。每次请求都带上 `box.specs()`，否则模型根本不知道有哪些工具。
- `speakable` 逐行处理：先认标题和列表标记（`-`、`*`、`+` 或 `1.` 后面必须跟空白），再去掉链接地址、反引号和星号，最后合并空白。`-3°C` 和 `2.5 m/s` 不是列表，误删负号会让助手把零下三度念成三度。
- 最后一段把前三关串起来：用户说 "set a five minute timer"，模型先写成 `minutes=5`，拿到点名参数的错误后改成 `seconds=300`，念出 "Done. Your timer is set for five minutes."，整轮存进会话库，计时器在 1300 秒响。这就是课后练习 3 要验证的事。

## Part 4 延迟报告

```python
async for event in events:
    turns.setdefault(event["turn"], []).append(event)
    if event["type"] == "turn.end":
        ends[event["turn"]] = event["ms"]
    newest = event["ms"] if newest is None else max(newest, event["ms"])
    for turn in sorted(t for t, end in ends.items() if end + max_delay_ms <= newest):
        del ends[turn]
        yield _report(turn, turns.pop(turn))
for turn in sorted(turns):
    yield _report(turn, turns[turn])
```

- 事件来自 VAD、STT、LLM、TTS 好几个组件，到达顺序不可靠，所以一轮的所有指标都按事件里的 ms 算：首音取最小的 tts.audio，打断后的时长取 barge-in 之后最大的 tts.audio。
- “最多晚到 max_delay_ms”给出了水位线：收到一个 ms 为 M 的事件后，所有 ms ≤ M − max_delay_ms 的事件都已经到了。turn.end 是一轮的最后一个事件，水位线越过它，这一轮就不会再有事件。一收到 turn.end 就出报告，会漏掉还在路上的音频或 barge_in。
- 一轮完成就 `yield`，第一份报告出来时只拉取了 10 个事件。
- 静音幻觉用 VAD 判断：没有 vad.start 的轮是 STT 在静音上出的字，也就是课里第 3 种故障（"Always VAD-gate"）。按文字过滤，用户真说的 "Thank you." 也会被当成幻觉，这是 Pitfalls 里的 "Overzealous hallucination filters"。
- 第 3 轮打断之后没有再开始新的一段音频，记 0；第 4 轮 LLM 没被取消，又播了 900 ms，这是课里第 2 种故障。第 11 课（实时音频处理）要求打断后 100 ms 内停下。只取“打断时或之后”的音频，否则第 3 轮会算成 -150。
- 格式由测试的解析代码决定：`event:` 一行、`data:` 一行，再空一行。

## Part 5 参数校验

递归 `visit(node, value, path)`：

- 先把 `$ref` 换成 `$defs` 里的定义，按需解析，所以自己引用自己的 step 也能查完；先展开全部引用会无限递归。
- `type` 可以是一个名字或一个列表。类型不对就记一条 "type" 然后返回，下面的都不查。
- `enum` 比较时布尔值和数字分开，因为 Python 里 `True == 1`。
- 值是 dict 时，先查 `required`（指针指向缺的属性），再逐个属性：有定义就递归，没定义且 `additionalProperties` 为 false 就记 "unexpected"；没写 `additionalProperties: false` 的对象允许别的属性。值是 list 时按下标递归 `items`。
- 属性名按 RFC 6901 转义：先把 `~` 换成 `~0`，再把 `/` 换成 `~1`，顺序不能反。

要一次返回全部问题：语音里模型每改一次参数，用户就多等一次 LLM 往返。

## 这套题证明了什么，没证明什么

通过了说明你能在异步代码里调试工具调度、把对话原样存进 SQLite 并真正删除过期的转写、写出有步数上限和降级的工具循环、处理乱序到达的事件流，以及递归地校验嵌套参数。它不涉及真实的 STT、LLM、TTS 模型和网络，不涉及麦克风采集和 VAD 本身，所以课里第 1 种故障（第一个词被截掉）这里测不到，要在第 11、14 课的采集和 VAD 代码里练。真正的流式 LLM 输出、播放中的取消和 800 ms 的端到端实测，需要按课里的 Use It 一节接上真实组件另外去跑。
