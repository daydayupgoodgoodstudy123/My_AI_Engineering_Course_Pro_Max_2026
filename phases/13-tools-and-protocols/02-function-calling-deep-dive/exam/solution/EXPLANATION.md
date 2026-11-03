# 参考答案讲解：FCBridge（13/02）

计时结束后再看。参考实现在同目录的 `fcbridge/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修三家翻译

**现象**：解锁后的第一个错误是测试里假 Anthropic 抛出的 `ProviderError: anthropic rejected the request: 400 tool_choice.type: 'required' is not one of 'auto', 'any', 'tool', 'none'`。报错的是 provider，不是我们的代码。

**顺着往上找**：请求由 `Bridge.ask` 调 `tool_fields` 组装，`tool_fields` 再调 `tool_choice_anthropic`。docstring 写的是 `{"type": "any"}`，代码却把三种简单模式合成了一句 `if tc.mode in ("auto", "none", "required")`，照抄了 OpenAI 那一版。课里的对比表把同一个意思叫成三个名字：OpenAI 是 required，Anthropic 是 any，Gemini 是 ANY。这一关想练的是：报错的位置往往不是出 bug 的位置，先打印出被拒收的那个请求，再找是谁生成了那个字段。

**依次修四处**：

1. `tool_choice_anthropic`：required 返回 `{"type": "any"}`。
2. `_gemini_schema`：这是课里代码原样的缺陷（测验 Q4、Q9），只在 type 是字符串时才转大写，WEATHER 的 `["string", "null"]` 原样发出去，假 Gemini 拒收。type 是列表时，去掉 "null" 后必须正好剩一个类型，写成大写，再加 `nullable: true`；剩两个就是 Gemini 子集写不出来的联合类型，报 ValueError。在构建期报错，比线上被 provider 拒收好。
3. `parse_openai`：`json.loads(raw) if raw else {}`。无参数的工具会收到空串，它表示没有参数；`raw_arguments` 仍然是 `""`，Part 2 要原样存下来。
4. `schema_depth`：原来的循环里 `if schema_depth(sub) > deepest: deepest = schema_depth(sub)` 对每个子 schema 算两次，每多一层嵌套工作量就翻倍。文件夹树每层是“对象 → 数组 → 对象”两跳，10 层要调用 157 万次，本机 0.3 到 0.6 秒；改好以后是 49 次。每个子 schema 算一次：

```python
own = 1 if "object" in _types(schema) else 0
return own + max((schema_depth(sub) for sub in _subschemas(schema)), default=0)
```

**三个护栏**：

- FLEET 有一个名叫 type 的属性。最顺手的修法是“遇到 type 键就当类型处理”，结果在 `{"type": "string", "enum": [...]}` 这个属性上报 `'dict' object has no attribute 'upper'`。properties 下面的键是属性名，不是关键字。参考实现单独处理 properties，只递归它的值；保留 `isinstance` 判断、只额外处理列表，也能过。plate 写成 `["null", "string"]`，取列表第一个元素当类型会得到 NULL。
- 非法 JSON 仍然要报错。把 JSONDecodeError 吞成 `{}`，工具就会在没有参数的情况下被调用。课里 Errors and repair 一节说的是解析失败后把错误交回模型、再调一次。
- 深度要准确。8 层只有 OpenAI（5）拒收，12 层 OpenAI 和 Anthropic（实践上限 10）都拒收，Gemini 在表里没有深度上限。为了提速把递归截在 OpenAI 的上限，两个都会报 6，Anthropic 那条检查就永远不会触发。

## Part 2 规范会话库

参考实现只有一张表：`(conversation_id, position)` 是主键，`kind` 记回合的种类，整个回合用 `json.dumps(asdict(turn))` 存成一段 JSON 文本。OpenAI 的 arguments 原文在这段 JSON 里是一个字符串值，JSON 字符串能逐字符还原，所以空格、转义和空串都不会变。

```python
(position,) = db.execute(
    "SELECT COALESCE(MAX(position) + 1, 0) FROM turns WHERE conversation_id = ?", (conversation_id,)
).fetchone()
```

容易漏的几点：

- **原文**：课里的对比表写着 OpenAI 的参数是字符串，另外两家是对象。下一轮请求要把这段文本原样发回 OpenAI，所以要存原文，不能存解析后的 args 再生成。测试里的原文有逗号前的空格和大写的 `\u00E3`，`json.dumps` 和紧凑格式都会改掉它们；SQLite 的 `json()` 也会去掉空格。
- **对象**：Anthropic 和 Gemini 的调用读回来 `raw_arguments` 仍是 None。所有 provider 共用一个“参数文本”列，读回时会把它们也变成文本。
- **按 JSON 比较**：Python 里 `1 == True`、`140 == 140.0`，dataclass 的 `==` 看不出类型变了。SQLite 没有布尔类型，把 `is_error` 放进 INTEGER 列，读回来是 1，发给 Anthropic 时就成了 `1`。测试用 JSON 文本比较，`sort_keys=True` 改掉的键序也逃不过。
- **位置**：每个会话从 0 开始。replace 只改内容不改位置，参考实现用 UPDATE。如果用 DELETE 加 INSERT 或者 `INSERT OR REPLACE`，被替换的行会拿到新的 rowid，按 rowid 排序时，脱敏后的那条结果就跑到了会话末尾。按显式的 position 排序就不受影响。UPDATE 要同时按 conversation_id 和 position 找行，只按 position 会把 standup 里同一位置的回合也换掉。
- **调用的顺序**：一个回合里的调用在 JSON 列表里本来就有先后。把调用拆到另一张表时要存一个序号并按它排序；主键用 `call_id`、再按主键查，读回来是 id 的字母序，测试里两个并行调用的顺序就反了。
- **常规**：`with self._db:` 自动提交；建表写 `IF NOT EXISTS`；未知 provider 报 ValueError，不存在的位置报 KeyError，不存在的会话返回 `[]`。

## Part 3 三家请求

`render` 先查上限，再拼 `tool_fields` 和三种消息列表。先把连续的工具结果归成一组：

```python
def _grouped(conversation):
    out = []
    for turn in conversation:
        if isinstance(turn, ToolResult):
            if out and isinstance(out[-1], list):
                out[-1].append(turn)
            else:
                out.append([turn])
        else:
            out.append(turn)
    return out
```

- **归组**：OpenAI 每个结果一条 role=tool 消息；Anthropic 把一组结果放进同一条 user 消息的 tool_result 块里；Gemini 放进同一条 user content 的 functionResponse 里。课文 Parallel calls 一节说的 "a batched tool-role message containing one entry per tool_call_id"，落到消息上是每个 tool_call_id 一条（测验 Q11）。
- **字符串还是对象**：OpenAI 的 arguments 是文本，来自 OpenAI 的调用发回原文，别家的调用发 `json_text(args)`；Anthropic 的 input 和 Gemini 的 args 都是对象，来自 OpenAI 的调用也用解析后的 args。会话可以在几家之间切换，这正是 canonical 模型的用处。原文是空串时也原样发回：判断要写成 `is not None`，`raw or json_text(args)` 会把空串换成 `"{}"`。
- **细节**：Anthropic 的 text 块在 tool_use 前面，只有失败的结果带 `is_error`；Gemini 的模型回合 role 是 model，调用和结果都带 id；OpenAI 没有调用的回合不带 tool_calls 键。
- **上限**：工具数 128 / 64 / 64，含上限；Gemini 的 tools 只有一个对象，数的是里面的函数声明。参数文本按实际发出的 UTF-8 字节数，含 8192。`json_text` 不写 `\u` 转义：测试里那条笔记的参数文本是 8192 字节、2742 个字符，按字符数会放过多一个字节的版本，按 `\u` 转义去量是 16367 字节，又会把刚好合规的那条拒掉。只有 OpenAI 有这个上限，而且是每个调用各自的上限：同一回合里还有一条短笔记，加在一起量就会误拒。深度直接调 `check_depth(provider, tools)`，按各家自己的上限、含上限查。
- 最后一段把 Part 2 串起来：存进库、重开、再渲染，三家的请求逐字节不变。

## Part 4 一致性探针

```python
async def answer(provider):
    try:
        calls = await asyncio.wait_for(bridge.ask(provider, tools, prompt, choice), timeout_s)
    except asyncio.TimeoutError:
        return provider, None, "timeout"
    except Exception:
        return provider, None, "error"
    if len(calls) != 1:
        return provider, None, "error"
    return provider, calls[0], "ok"

for arrival in asyncio.as_completed([answer(p) for p in providers]):
    provider, call, status = await arrival
    yield record(...)
```

- 三家同时发，`as_completed` 按完成顺序交回结果，每到一个就 yield 一条记录。测试在前两条记录到达时检查最慢的那家还没回复。
- 每家的失败在 `answer` 里变成一条记录，不会打断整个流：拒答没有调用，一次回复两个调用，坏 JSON，429，都是 error。error、timeout 和汇总记录的 call_id、name、arguments_json 都留空。
- `wait_for` 给每家单独计时，从发出请求算起，超时会取消那个请求。`as_completed(..., timeout=)` 是整个探针一个总时限，到点直接抛 TimeoutError。在 `asyncio.wait(..., return_when=FIRST_COMPLETED)` 的循环里每次都传 `timeout=timeout_s`，等于每来一个回复就重新计时，晚到的那家会被放过。
- 记录用 `csv.writer` 写：arguments_json 是 JSON，里面有引号和逗号，必须按 CSV 的规则加引号、把引号写成两个。
- 汇总比较工具名和解析后的参数。id 本来就不同（`call_`、`toolu_`、UUID），OpenAI 的原文键序也和别家不同，所以既不能比 id，也不能比文本。有两家不一致就是 different；三家都回答且一致才是 same，两家一致、一家超时是 incomplete。这就是课里 `main()` 末尾那段等价性检查，只是改成了并发、流式，并且要处理失败。

## Part 5 strict 编译器

`_compile(node, defs)` 每次都返回一份新的 dict：

- 遇到 `$ref` 就取出定义，和 `$ref` 旁边的键合并，再递归编译。每一处引用编译一次，所以 billing、shipping、ship_to 各有一份自己的地址。
- 递归 properties、items、anyOf，其余的值 `copy.deepcopy`。浅拷贝的 enum 列表和输入共用，加 None 时会加到输入里。
- 对象节点：给每个原本可选的属性加 null，再把 required 设成全部属性（按 properties 的顺序），`additionalProperties: false`。这一步在子节点编译完之后做，所以 shipping 是在内联以后才变成 `["object", "null"]`。
- 可空的写法照 WEATHER 的 units：type 里没有 "null" 才加；只有 anyOf 没有 type 的，加一个 `{"type": "null"}` 分支。类型允许 null 又有 enum 的，enum 里要有 None。WEATHER 自己的 units 就缺这个 None（测验 Q7），null 会被 enum 拒掉，“可选”名存实亡。
- 编译完再量深度。org_chart 的每一层都藏在 `$defs` 里，内联前只有 1 层，内联后 6 层，超过 OpenAI 的 5，报 LimitError。
- 返回的工具标成 `strict=True`。ORDER 本身是 `strict=False`，正因为它原样过不了 strict 才要编译；`dataclasses.replace(tool, input_schema=...)` 会把 False 带过来。新加的 null 一律放在最后，docstring 写明了这一点。

## 这套题证明了什么，没证明什么

通过了说明你能在别人的翻译代码里顺着 provider 的报错找到根因，把 OpenAI 的参数原文和别家的参数对象分开存住，把一段跨 provider 的对话渲染成三家的请求并守住各家的上限，并发地比较三家的回答并流式输出，以及递归地把 schema 改写成 strict 模式要的样子。它不涉及真实的 HTTP、SDK 和 API key，不涉及流式的 tool call 增量和并行执行（第 03 课），也没有考 Gemini 的 VALIDATED 模式、`responseSchema`、Anthropic 的 `disable_parallel_tool_use` 和 refusal 的具体字段。题里的上限数字来自课文，接真实 provider 之前要对照各家当前的文档再核对一遍。
