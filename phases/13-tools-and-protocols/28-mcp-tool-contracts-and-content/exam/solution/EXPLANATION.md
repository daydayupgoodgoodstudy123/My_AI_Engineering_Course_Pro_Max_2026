# 参考答案讲解：contractkit（13/28）

计时结束后再看。参考实现在同目录的 `contractkit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修发现与调用

**现象**：解锁后的第一个错误是 `call` 里的 `ContractViolation: tool is not admitted: tag_catalog`，而 tag_catalog 的 descriptor 本身没有问题，`client.rejections` 里也没有它。

**顺着往上找**：把服务器收到的 tools/list 打印出来，只有一次，没有游标。第一页返回的 nextCursor 是空字符串，`discover_tools` 用 `if not cursor` 判断结束，空字符串是假值，于是第二、三页从来没读过。课里专门写了这一条：空字符串是合法游标，只有字段缺失或为 null 才结束。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `discover_tools`：改成 `if cursor is None: break`。缺失和显式的 null 都由 `result.get("nextCursor")` 得到 None，空字符串照常原样发回去。
2. `validate_tool_result`：删掉“必须是 dict”的检查，改成判断 `"structuredContent" in result`，再按 schema 校验 `result["structuredContent"]`。课里说 structuredContent 可以是对象、数组、字符串、数字、布尔或 null。判断键在不在而不是判断值是不是 None，null 结果才不会被当成缺失，缺失也不会被当成 null 放过。
3. 同一个函数：去掉 `or result.get("isError")`。发布了 outputSchema，每个 complete 结果都要给出符合 schema 的 structuredContent，包括 `isError: true` 的结果；错误标志只是给执行结果分类。route_report 的 `accepted: false` 就是在 schema 内表达失败的写法。
4. `call`：不再每次调 `admitted()`。`discover_tools` 末尾把 `self.admitted()` 的结果存进 `self.tools`，`call` 直接查这个 dict。原来每次调用都把 2000 个 descriptor 重新校验一遍，167 次调用要 1.1 到 1.6 秒；改完不到 1 毫秒。

**护栏**：提速时最容易出这几种错，测试都会抓住：

- 直接在 `self.catalog` 里按名字找工具，被拒的 broken_route 就能调用了。
- 把参数校验或结果校验一起删了，包括结果里每个内容块的校验。课里说校验发生在三个位置：descriptor 在发现之后，参数在执行之前，结果在使用之前。只有第一个是一次性的。
- 缓存了 admitted 的结果却不随重新发现更新，下架的工具还能调用；rejections 不清空，也会留着上一次的记录。

## Part 2 内容块容器

参考实现的每条记录是 `tag`（1 字节）、meta（4 字节大端长度加 UTF-8 JSON 对象）、body（4 字节大端长度加负载）。meta 是去掉 type 和负载字段之后的块，body 是 text 的 UTF-8 字节，或者 image、audio、blob 解码后的字节。

- **物理 codec 已给定**：`_pack_record` 和 `_read_records` 负责 MCB1 字段长度、UTF-8 meta 与截断检查，pack/unpack 真实调用它们；`_text` 负责严格文本解码。golden 和全部 codec 错误修法继续覆盖这些护栏。
- **本地负载配置**：`PayloadLimits` 的 image、audio、resource 分别限制单块已解码负载；嵌入文本先转 UTF-8。`_check_limit` 在 pack 和 unpack 都执行，不相信写入方的限额。None 不设限，0 不等于缺省，恰好等于限制通过。普通 text 和 resource_link 不在这个媒体/嵌入负载策略里，链接不跟随，metadata 不计负载。数值由调用者配置，不是 MCP 规定。
- **规范 base64**：打包时 `b64decode(validate=True)` 之后再 `b64encode` 一次，必须和原文完全相同，否则拒绝。`QR==` 和 `AAB=` 能解码，但字节还原回去是 `QQ==` 和 `AAA=`，存进去就再也给不回原文。读回时用 `base64.b64encode`：标准字母表、带填充、不换行。`encodebytes` 会插换行，`urlsafe_b64encode` 用 `-` 和 `_`。
- **不改调用方的数据**：meta 是新 dict，嵌套的 resource 也要先复制再 pop。嵌入资源用 `"text" in resource` 区分 text 和 blob，空字符串的 text 也是 text。
- **resource_link 原样保存**：整个链接留在 meta 里，有 mimeType 就有，没有就没有。容器不跟随链接；课里说链接只是这次调用返回的引用，以后读取时要重新授权。
- **读的时候严格**：每取一段都检查剩余长度，循环一直读到末尾，所以多出来的一个字节也会被当成一条读不完整的记录而拒绝。meta 先按 UTF-8 解码再交给 `json.loads`；直接把 bytes 交给它，会按 BOM 把 UTF-16 也认下来。JSON、UTF-8 的错误都转成 ContractViolation，最后对重建的每个块再跑一遍 `validate_content_block`。

## Part 3 参数头

客户端调用已给定的 `argument_text` 把值按声明类型变成文本，`encode_header_value` 决定明文还是哨兵，`build_parameter_headers` 按 bindings 顺序组装头部，审计只记头名和哪些用了哨兵。

```python
def encode_header_value(text):
    if text and all("!" <= c <= "~" for c in text) and not text.startswith("=?base64?"):
        return text
    return "=?base64?" + base64.b64encode(text.encode("utf-8")).decode("ascii") + "?="
```

- 明文的条件是课里的原话：非空、全部是 `!` 到 `~` 的可见 ASCII、不像哨兵。`isprintable()` 会放过空格和非 ASCII。
- 看起来像哨兵的原值再编码一次，接收方才能还原出字面文本，而不是把它当成传输语法解码。
- `argument_text` 的严格类型、布尔小写和安全范围是给定 primitive 的护栏；候选人不重写它。绑定参数通过键是否存在区分缺省与 false、0、空字符串，不能用真值跳过，也不能给缺省参数补默认头。

服务器端 `check_parameter_headers`：先把收到的头按小写名分组，再按 bindings 顺序逐个判断。

- 多个问题先按 bindings 选第一个；同一绑定 duplicated 先于 unexpected。未声明的头不解码，畸形值也不进入 checked 审计。
- 遍历的是 bindings，不是收到的头，所以 checked 事件按 bindings 顺序列出规范头名，和头到达的顺序、大小写无关。
- 有 body 参数却没有头是 missing；两份以上是 duplicated（只差大小写的也算）；有头却没有 body 参数是 unexpected；`decode_header_value` 拒绝的是 malformed；解码后的文本和 `argument_text(body 值)` 不完全相同，或者 body 值根本没有头部形式，是 mismatched。
- 解码要求完全规范的哨兵：先检查长度，`=?base64?=` 的前缀和后缀共用了一个问号，不是空串的编码；后缀必须在；base64 必须规范；字节必须是 UTF-8；只解一次。
- 拒绝时审计写一条 `{"event", "header", "reason"}`，然后抛 HeaderRejected，`http_tool_call` 回 HTTP 400 和 `-32020`，dispatch 不会被调用。课里说值和它的编码形式都不进审计，编码不是加密。

## Part 4 补全防抖

```python
def type(self, value):
    self._pending = (value, self._clock())

def poll(self):
    if self._pending is None:
        return
    value, typed_at = self._pending
    if self._clock() - typed_at < self.idle_ms:
        return
    request_id = next(self._ids)
    params = {"ref": self.ref, "argument": {"name": self.argument, "value": value}}
    self._send(json.dumps(make_request(request_id, "completion/complete", params)))
    self._latest = (request_id, value)
    self._pending = None
```

- 每次按键都刷新时间戳，所以只有停下来满 idle_ms 才发，快速连续输入只发最后一个值。每次停顿都发，不拿最新请求的值去重。
- `_latest` 记着最新请求的 id 和值。`receive` 只认这个 id：旧请求的答案先到也好、后到也好，都丢掉；没发过的 id 也丢掉。最新请求的错误答案把建议清空。
- 显示时截到 100 个，保持服务器的顺序；服务器说 hasMore 或者客户端截过（超过 100 个，正好 100 个不算），hasMore 就是 true；total 只用服务器给的。课里的示例服务器把 hasMore 写死为 false，客户端不能信。
- id 从注入的计数器里取，每个请求都是 make_request 造出来的，带完整 `_meta`。协议是无状态的，每个请求都要自带元数据。

## Part 5 注解位置审计

```python
def _annotated(node, parts):
    if isinstance(node, dict):
        if "x-mcp-header" in node:
            yield parts, node
        for key, child in node.items():
            yield from _annotated(child, (*parts, key))
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from _annotated(child, (*parts, index))
```

把 inputSchema 和 outputSchema 当普通 JSON 遍历，每个对象、每个数组都进去，不管键是什么。课里说要遍历整棵 schema 树，而不只是校验器认识的那些属性。

- **不跟 $ref**：每个注解都在它写下的地方被找到一次。被引用两次的定义只报一次，没被引用的定义也会报，自己引用自己的定义也不会让遍历无限递归。课里说解析引用不会让被引用的节点变成顶层的直接属性。
- **按顺序判断**：在 outputSchema 里是 output；路径不是恰好 `("inputSchema", "properties", 名字)` 是 placement；然后是头名、类型、重复、敏感名。每个注解最多一条 finding，取第一条适用的，所以头名重复的 password 报 duplicate，不报 sensitive。敏感名按整个名字比较，tokenizer 不算。
- **类型**：先判断是不是字符串，再查集合，`["string", "null"]` 才不会在 frozenset 里报 TypeError。
- **重复**：`taken` 按 properties 的顺序记录小写头名，后出现的那个是 duplicate。
- **路径**：JSON Pointer，每段先替换 `~` 再替换 `/`，最后按路径排序。

## 这套题证明了什么，没证明什么

通过了说明你能在一个 MCP 客户端里找出让分页提前结束、让合法结果被拒、让错误结果绕过输出契约的缺陷，并把 descriptor 校验放回发现阶段而不丢掉每次调用的参数和结果校验；能使用给定物理 codec 映射内容块、按规范 base64 往返，并对媒体和嵌入资源执行调用方配置的本地负载上限；能实现 `x-mcp-header` 的编码规则和服务器端的精确比对；能写一个按时间驱动、丢弃过期答案的防抖客户端；能用一次完整的树遍历审计注解位置并给出 JSON Pointer。它没有用真实的 Streamable HTTP 或官方 SDK，JSON Schema 也只是课里的小子集，没有覆盖课里 completion 的服务器端授权与限流、生产媒体类型/音频时长策略或统一部署的负载配置，也没有覆盖 Practice Lab 里的 `search_evidence` 工具，这些需要另外动手做。
