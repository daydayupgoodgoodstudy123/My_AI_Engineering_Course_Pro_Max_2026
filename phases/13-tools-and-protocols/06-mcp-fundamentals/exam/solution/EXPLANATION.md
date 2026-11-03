# 参考答案讲解：MCPCore（13/06）

计时结束后再看。参考实现在同目录的 `mcpcore/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修无状态请求

**现象**：解锁后的第一个失败是 "a request for an unsupported version is refused with -32022"，服务器把一个 `2027-01-01` 的请求当成正常请求回答了。

**顺着往上找**：`validate_request` 的版本检查没有问题。打印 `future` 会看到它的 `_meta` 里写的是 `2026-07-28`。`make_request` 直接拿调用者的 `search` 当 params，再往里写 `_meta`；`today` 用同一份 `search` 构造时，把 `future` 的 `_meta` 覆盖了。`future` 和 `today` 用的是同一个 params 对象。报错的是服务器，根因在构造请求的地方。

**依次修五处**：

1. `make_request` 用 `copy.deepcopy(params)`，再往副本里写 `_meta`。只复制一层（`dict(params)`）不够：`arguments` 仍然和调用者共用，调用者改了 query，请求也跟着变。先写调用者的 dict、最后再 deepcopy 整个请求也不行，调用者的 params 已经多出了 `_meta`。
2. `request_meta` 每次给一个新的 `{}`，不用模块级的 `NO_CAPABILITIES`。显式传进来的 capabilities 也要复制，否则请求和调用者共用一个 dict。
3. 删掉 `dispatch` 里“记住上一个请求的 capabilities、缺了就补上”的那一段。缺 capabilities 就是 -32602，`validate_request` 本来就这样判断。不要把缺失当成 `{}`：空对象是“不支持任何可选能力”的合法声明，缺失说明请求坏了。
4. `tools/list` 按名字排序。
5. 用 dict 按名字索引工具，在 `register` 里维护。只在 `__init__` 里建一次索引，或者把排好序的列表缓存起来，后注册的工具就调不到、列不出，测试最后两条断言专门查这个。只去掉排序、保留线性扫描也不够，20000 个工具时仍然超过限值。

参考实现把注册表直接换成 `dict[name, (definition, handler)]`，`tools/list` 时按 `sorted(self._tools)` 逐个 deepcopy。

**这和协议的关系**：课里说服务器不能从先前的请求推断版本和 capabilities。第 1、2 处是客户端一侧的同类问题：一个请求里改的东西，通过共享的对象漏进了别的请求。第 3 处是服务器一侧的推断，也就是 legacy 时代按连接协商留下的习惯。

## Part 2 transcript 库

参考实现只有一张表：

```sql
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY,
    direction TEXT NOT NULL,
    raw BLOB NOT NULL,
    method TEXT,
    id_json TEXT
)
```

- raw 用 BLOB，bytes 原样存、原样读。测试里有行尾带 `\r` 的行、有 `\u00e9` 转义的行，还有一行不是合法的 UTF-8。
- id 存成 JSON 文本：`json.dumps(7)` 是 `7`，`json.dumps("7")` 是 `"7"`，`json.dumps(None)` 是 `null`，`2**64 + 1` 原样是那一串数字。只有没有 id 时才存 SQL NULL，读回时变成 `NO_ID`。
- 这一列要声明成 TEXT。SQLite 的类型亲和性会把 INTEGER 或 NUMERIC 列里像数字的文本转成数字：整数 id 的 JSON 文本 `7` 变成整数 7，超过 64 位的变成 REAL，精度丢失。直接绑定 Python int 则在超过 2^63−1 时报 OverflowError。
- `entries()` 用 `ORDER BY seq`。测试先记 seq 4，再记 seq 3。seq 是整数列，存成 TEXT 会让 `10` 排到 `2` 前面。
- `with_id(value)` 用 `WHERE id_json = ?`，参数是 `json.dumps(value)`，同样 `ORDER BY seq`。null 能找到（不会写出 `= NULL`），7 和 "7" 也分得开。超过 64 位的那对 id 是先记 seq 11、再记 seq 10 的，按插入顺序返回就会错。

写库用 `with self._db:` 自动提交，建表写 `IF NOT EXISTS`，关闭后重开才读得到。

## Part 3 请求生命周期

骨架就是课里 One request lifecycle 的顺序：

```text
解析（-32700）→ 是一个对象（-32600）→ 不经 HTTP 的通知到此为止，不回
→ jsonrpc 和 method（-32600）→ params、_meta、版本的类型、capabilities 的类型、clientInfo（-32602）
→ HTTP 头与 body（-32020）→ 版本支持（-32022）→ 经 HTTP 的通知到此为止，不回
→ 方法要求的 capabilities（-32021）→ 方法（-32601）
```

容易错的地方：

- **-32020 先于 -32022**：课里写着 "A mismatch is -32020 even when one of the two version values is unsupported"。测试两个方向都查：头不支持而 body 支持，头支持而 body 不支持。只有两边一致时才轮到版本支持。Mcp-Method 和 Mcp-Name 也在版本之前比较，测试里这两行的版本两边一致但不受支持。
- **类型先于头**：版本不是字符串时，头里写什么都不重要，是 -32602。
- **复用现成的 `validate_request`**：它把类型检查和版本检查写在一起，中间插不进头的比较。要么拆成两段，要么像参考实现那样把检查序列重写一遍。
- **通知**：不经 HTTP 时，`"id" not in message` 要在所有字段检查之前判断，否则坏的通知会收到 -32602 或 -32600。经 HTTP 时，通知和请求一样检查到版本为止，出错时 id 是 null；都通过了就返回 None，不查 -32021 和 -32601。第 09 课的传输层就是这样做的：头不对回 400 和 -32020，接受了回 202、没有 body。
- **HTTP 与否看 `headers is not None`**：`{}` 是一个头都没带的 HTTP 请求，照样要比较，结果是 -32020。
- **Mcp-Name**：查 `NAME_PARAMS` 决定和哪个参数比较，缺了 Mcp-Name 也算不一致。
- **-32022 的 data**：`{"requested": version, "supported": list(SUPPORTED_VERSIONS)}`，`wire.py` 里的 `unsupported_version` 已经这样写了。直接放 `SUPPORTED_VERSIONS`，调用方一改，服务器以后宣称支持的版本就变了。
- **版本精确匹配**：不按日期比大小。

## Part 4 无状态追踪器

```python
pending: dict[str, str] = {}
async for message in messages:
    kind, era, method, detail = _label(message, pending)
    yield f"[{kind}/{era}] {method}: {detail}\n"
```

`_label` 按 docstring 分成请求、通知、响应和其他四种：

- pending 是一个按 id 查的 dict，键用 `json.dumps(id)`。响应按 id 找请求，不按到达顺序：测试里 tools/call 和 tools/list 的回答是倒着到的。
- 每个请求都进 pending，invalid 的也一样；通知不进。响应用 `pending.pop`，配上就删，所以第二个响应和没人问过的响应都是 orphan，method 写 `?`。
- 错误的 era 只看错误码：-32020、-32021、-32022 是 modern，其余是 unknown，回答 initialize 的 -32601 也是 unknown。
- 结果的 era：有 resultType 是 modern，值不限于 complete，tasks 扩展的 `"task"` 也算；没有的话，回答 initialize 的是 legacy，其余是 invalid。legacy 看的是它回答的请求，不看结果里有没有 protocolVersion：重复发来的 initialize 结果是 orphan，标 invalid。追踪器不记“这条连接已经是 legacy 了”，每条消息只看它自己，以及它回答的那个请求。
- 每条消息一到就 yield，所以第一行出来时只拉取了 1 条消息。

本课 `code/main.py` 的 `trace_message` 有两处不合 Ship It 的规则（本课测验 Q12 也指出了）：所有错误都标 unknown，所有缺 resultType 的结果都标 legacy。参考实现改掉了这两处，并把响应的 method 换成它回答的那个请求的 method。

## Part 5 嵌套 capability

```python
def missing_capabilities(required, declared):
    missing = {}
    for key, needs in required.items():
        have = declared.get(key) if isinstance(declared, dict) else None
        if not isinstance(have, dict):
            missing[key] = copy.deepcopy(needs)
            continue
        below = missing_capabilities(needs, have)
        if below:
            missing[key] = below
    return missing
```

- 沿着 required 递归，键原样比较，不拼路径，`io.modelcontextprotocol/tasks` 里的点和斜杠就没有影响。
- 声明的值必须是对象。`{}` 满足一个空的要求，但不满足带子键的要求。
- 子树里缺的部分非空时才放进结果，已满足的部分不会出现。
- 整棵缺失的子树用 `deepcopy` 复制，结果和需求表不共享对象。

在 `check_request` 里，这一步放在版本检查之后、方法检查之前，只对出现在 `required` 里的方法调用，data 是 `{"requiredCapabilities": missing}`。data 只放缺的部分：notes/sync 的请求声明了 tasks 和 conflicts，data 里只剩 attachments。第 13 课里，tasks 扩展缺失时的 data 正是 `{"requiredCapabilities": {"extensions": {"io.modelcontextprotocol/tasks": {}}}}`。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里追查跨请求的共享状态，能按协议规定的顺序检查请求，能为 JSON-RPC 的 id 和原始字节设计存储，能写一个逐条输出的流式追踪器，也能处理嵌套的 capability 对象。它不涉及真实的 stdio 或 HTTP 传输、Streamable HTTP 的状态码和 SSE、legacy 适配器、鉴权（课里第 7 步），也没有用官方 SDK。这些在第 07、08、09、16 课里动手做。
