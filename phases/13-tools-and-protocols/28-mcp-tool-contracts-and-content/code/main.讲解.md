# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 28 节 MCP Tool Contracts 与内容 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试：`python3 -m unittest discover tests -v`（在 `code/` 目录下） ｜ **依赖**：仅标准库（`base64`、`json`、`re`、`dataclasses`、`typing`）；服务端与客户端在同一进程内直接调用，不开网络端口

---

## 1. 这份代码在考察什么

这份代码在一个文件里同时实现了 MCP 工具边界的**服务端**和**客户端**，演示讲义的"五道关卡"如何落到代码：

| 关卡 | 负责方 | 代码 |
|------|-------|------|
| Discover | 服务端提供、客户端遍历 | `ContractServer.tools_list`（确定性排序 + 空串游标）、`ContractClient.discover_tools`（不透明游标循环） |
| Admit | 客户端 | `validate_tool_descriptor` → `validate_header_annotations`（全树遍历 + 敏感字段策略） |
| Invoke | 客户端 + 传输 | `build_parameter_headers`、`encode_parameter_header_value` |
| Execute | 服务端 | `validate_request_meta`、`streamable_http_tool_call` → `validate_parameter_headers`、`tools_call`（参数校验 + 两层错误） |
| Consume | 客户端 | `validate_tool_result` → `validate_content_block` + `validate_json_schema` |

外加一个授权与限流的 `completion/complete`。

考察的核心概念：JSON Schema 作为运行时边界、`structuredContent` 不限于对象、五种内容块、`x-mcp-header` 的位置/类型/敏感性规则、头部值的精确编码与服务端一致性校验、不透明游标、补全的授权，以及协议错误与工具执行错误的分层。

> 一句话：**协议契约不是文档，而是一串在各自边界上会失败的检查；每个检查都要在"拥有它的那一层"失败。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROTOCOL_VERSION`、`*_META`、`HEADER_TOKEN`、`BASE64_SENTINEL_*`、`JS_SAFE_INTEGER_*`、`MAX_TOOL_LIST_PAGES`、`SENSITIVE_NAMES` | 常量 | 协议版本、元数据键、HTTP token 正则、哨兵、安全整数、分页上限、敏感名单 | 协议参数 |
| `ContractViolation` | 异常 | 契约违规（客户端/边界使用） | 校验失败 |
| `McpError` | dataclass 异常 | 带 JSON-RPC code 的协议错误 | 协议错误层 |
| `request_meta` / `server_meta` / `complete` / `validate_request_meta` | 函数 | 每个请求的 `_meta`；complete 结果封装；元数据校验 | 无状态请求 |
| `_matches_type` / `validate_json_schema` | 函数 | JSON Schema 子集校验器 | Schema 运行时边界 |
| `iter_header_annotation_nodes` / `validate_header_annotations` / `validate_tool_descriptor` | 函数 | 描述符准入 | Admit |
| `_validate_base64` / `validate_content_block` / `validate_tool_result` | 函数 | 结果消费校验 | Consume |
| `_descriptor` / `TOOLS` | 函数 / 列表 | 4 个工具描述符（含 1 个故意不安全的） | 教学数据 |
| `ContractServer` | 类 | `server/discover`、`tools/list`、`tools/call`、`completion/complete`、`dispatch` | 服务端 |
| `make_request` | 函数 | 构造带 `_meta` 的 JSON-RPC 请求 | 客户端请求 |
| `MISSING` / `_read_path` / `_parameter_text` / `_is_plain_visible_ascii` | 哨兵对象 / 辅助函数 | 读取参数、渲染为文本 | 参数头 |
| `encode_parameter_header_value` / `decode_parameter_header_value` | 函数 | 明文或 base64 哨兵编码/解码 | 头部值编码 |
| `build_parameter_headers` / `validate_parameter_headers` | 函数 | 客户端构造、服务端校验 `Mcp-Param-*` | 头部一致性 |
| `streamable_http_tool_call` | 函数 | 模拟 HTTP 层：先做一致性闸门，再 JSON-RPC 分发 | HTTP 400 / -32020 |
| `ContractClient` | 类 | 发现、调用、补全 | 客户端 |
| `main` | 函数 | 演示并打印 10 行结果 | 演示 |

数据流（`main()`）：`ContractServer()` → `ContractClient.discover_tools()`（两页，准入 3 个、拒绝 1 个）→ `call("tag_catalog")`（数组输出）→ `call("evidence_bundle")`（五种内容块）→ `build_parameter_headers(route_report, region="europe-λ")`（base64 编码）→ `streamable_http_tool_call`（头名全部小写，校验通过，HTTP 200）→ `complete_environment("")`（analyst 补全）→ 打印。

---

## 3. 逐段精讲

### 3.1 常量与两种异常

```python
HEADER_TOKEN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
BASE64_SENTINEL_PREFIX = "=?base64?"
BASE64_SENTINEL_SUFFIX = "?="
JS_SAFE_INTEGER_MIN = -(2**53) + 1
JS_SAFE_INTEGER_MAX = 2**53 - 1
SENSITIVE_NAMES = {"api_key", "apikey", "authorization", "password", "secret", "token"}


class ContractViolation(ValueError):
    """Raised when a descriptor or result violates the enforced contract."""


@dataclass
class McpError(Exception):
    code: int
    message: str
    data: dict[str, Any] | None = None
```

- `HEADER_TOKEN` 是 HTTP 字段名的 `tchar` 集合（字母数字加 `!#$%&'*+-.^_`|~`），不含空格、冒号、CR/LF——所以 `"Region\r\nInjected"` 这种头部注入在准入时就被拒（测试 `test_malformed_x_mcp_header_is_rejected`）。
- `2**53 - 1 = 9007199254740991`：IEEE 754 双精度能精确表示的最大连续整数，JavaScript 的 `Number.MAX_SAFE_INTEGER`。
- **两种异常对应两类失败**：`ContractViolation` 表示"契约被违反"（准入、消费、HTTP 闸门）；`McpError` 带 JSON-RPC `code`，在 `dispatch` 中被转成 `{"error": {...}}` 响应。
- `@dataclass` 修饰异常类：自动生成 `__init__`、`__repr__`、`__eq__`。副作用：`eq=True` 会把 `__hash__` 设为 `None`，实例不可哈希（实测 `hash(McpError(...))` 抛 `TypeError`），一般不影响使用。

### 3.2 无状态请求元数据

```python
def request_meta() -> dict[str, Any]:
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CAPABILITIES_META: {"completions": {}},
        CLIENT_INFO_META: {"name": "contract-client", "version": "1.0.0"},
    }

def validate_request_meta(params: dict[str, Any]) -> None:
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise McpError(-32602, "missing request _meta")
    ...
    if version != PROTOCOL_VERSION:
        raise McpError(-32022, "unsupported protocol version",
                       {"supported": [PROTOCOL_VERSION], "requested": version})
```

- 每个请求都自带协议版本、客户端能力、客户端信息（`io.modelcontextprotocol/...` 命名空间键），服务端不依赖会话状态。缺失返回 `-32602`（invalid params），版本不符返回 `-32022` 并在 `data` 里告诉对方支持哪些版本。
- `complete(**fields)` 把每个结果包成 `{"resultType": "complete", ..., "_meta": server_meta()}`。

### 3.3 JSON Schema 子集校验器

```python
def validate_json_schema(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ContractViolation(f"{path}: schema must be an object")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractViolation(f"{path}: value is not in enum")
    expected = schema.get("type")
    if expected is not None:
        if not isinstance(expected, str) or not _matches_type(value, expected):
            raise ContractViolation(f"{path}: expected {expected}")
    if isinstance(value, dict):
        ...  # required、properties 递归、additionalProperties: false
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate_json_schema(item, schema["items"], f"{path}[{index}]")
    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            raise ContractViolation(...)
```

- 支持讲义列出的子集：7 种类型、`required`、`additionalProperties: false`、`items`、`enum`、`minLength`。错误消息带 JSON 路径（`$.report`、`$[0]`），便于定位。
- `_matches_type` 中 `integer`/`number` 都显式排除 `bool`——因为 Python 里 `isinstance(True, int)` 为真。
- **`type` 写成列表（如 `["string","null"]`）时直接判失败**——对不支持的写法 fail closed。
- ⚠️ **未知关键字静默放行**：`maximum`、`pattern`、`oneOf`、`$ref` 等都不检查（实测 `{"a": 5}` 通过 `maximum: 3`、`"x"` 通过 `oneOf: [{"type":"integer"}]`）。讲义承认"This is not a replacement for a complete production validator"，这也是 Practice Lab 要求"`limit` is bounded by application validation"的原因。
- ⚠️ 两处与 JSON Schema 2020-12 的细微差异：`enum` 用 Python 的 `in` 比较，`True in [1]` 为真（实测 `True` 能通过 `enum: [1]`）；`1.0` 被判为非 `integer`（JSON Schema 中零小数部分的数算整数）。

### 3.4 `x-mcp-header` 的全树遍历与准入

```python
def iter_header_annotation_nodes(node, path=()):
    found = []
    if isinstance(node, dict):
        if "x-mcp-header" in node:
            found.append((path, node))
        for key, child in node.items():
            if isinstance(child, (dict, list)):
                found.extend(iter_header_annotation_nodes(child, (*path, key)))
    elif isinstance(node, list):
        for index, child in enumerate(node):
            if isinstance(child, (dict, list)):
                found.extend(iter_header_annotation_nodes(child, (*path, index)))
    return found
```

- 递归遍历**所有**字典和列表，不管键是 `properties`、`oneOf`、`items`、`$defs` 还是别的，只要某个字典含 `x-mcp-header` 键就记录"路径 + 节点"。讲义："Walk the entire schema tree, not just the properties your validator happens to understand."
- 路径用元组记录，如 `("properties", "region", "oneOf", 0)`。

```python
    for schema_path, property_schema in iter_header_annotation_nodes(input_schema):
        if (len(schema_path) != 2 or schema_path[0] != "properties"
                or not isinstance(schema_path[1], str)):
            raise ContractViolation("x-mcp-header is allowed only on a direct inputSchema property")
        property_name = schema_path[1]
        header_name = property_schema["x-mcp-header"]
        if not isinstance(header_name, str) or not HEADER_TOKEN.fullmatch(header_name):
            raise ContractViolation(...)
        lowered = header_name.lower()
        if lowered in seen:
            raise ContractViolation("x-mcp-header names must be unique ignoring case")
        seen.add(lowered)
        if property_schema.get("type") not in {"string", "integer", "boolean"}:
            raise ContractViolation(...)
        if property_name.lower() in SENSITIVE_NAMES or lowered in SENSITIVE_NAMES:
            raise ContractViolation("sensitive arguments must not be mirrored to headers")
        headers.append(((property_name,), header_name))
```

- **位置规则**：路径必须恰好是 `("properties", <名字>)`，这就是"直接顶层属性"的语法定义。语法判断、不做 `$ref` 解析，所以 `$defs` 里的注解即使被引用也会被拒。
- **名称规则**：HTTP token、忽略大小写唯一。
- **类型规则**：只允许三种原始类型，`number` 被排除（浮点数的文本表示不唯一）。
- **部署策略**：属性名或头名（小写后）**恰好**等于敏感名单中的词就拒绝——这是讲义说的"A client can turn that advice into a hard admission rule"。
- ⚠️ 精确匹配太窄：`access_token`、`user_password`、`credential` 都能被准入（实测）。见测验 Q11。
- ⚠️ `property_schema.get("type")` 若是列表，`list not in set` 会抛 `TypeError`（列表不可哈希），这不是 `ContractViolation`，会让 `discover_tools` 整体崩溃（见 3.10 与测验 Q10）。
- 小副作用：一个**名叫** `x-mcp-header` 的普通属性（`{"properties": {"x-mcp-header": {...}}}`）也会被当成注解拒绝——fail-closed 的代价。

```python
def validate_tool_descriptor(tool):
    if not isinstance(tool.get("name"), str) or not tool["name"]: ...
    input_schema = tool.get("inputSchema")
    if not isinstance(input_schema, dict) or input_schema.get("type") != "object": ...
    output_schema = tool.get("outputSchema")
    if output_schema is not None and not isinstance(output_schema, dict): ...
    if output_schema is not None and iter_header_annotation_nodes(output_schema):
        raise ContractViolation("x-mcp-header is not allowed in outputSchema")
    validate_header_annotations(tool)
```

- `inputSchema` 必须是 `type: object` 的 schema；`outputSchema` 可选，但里面不能出现任何头部注解（它描述的是输出，不参与请求路由）。

### 3.5 内容块与结果校验

```python
def validate_content_block(block):
    block_type = block.get("type")
    if block_type == "text":
        if not isinstance(block.get("text"), str): ...
    elif block_type in {"image", "audio"}:
        _validate_base64(block.get("data"), f"{block_type}.data")
        if not isinstance(block.get("mimeType"), str): ...
    elif block_type == "resource_link":
        if not all(isinstance(block.get(field), str) for field in ("uri", "name")): ...
    elif block_type == "resource":
        resource = block.get("resource")
        if not isinstance(resource, dict) or not isinstance(resource.get("uri"), str): ...
        if "text" not in resource and "blob" not in resource: ...
    else:
        raise ContractViolation(f"unknown content block type: {block_type}")
```

- 五种类型逐一校验，未知类型拒绝（fail closed）。
- `base64.b64decode(value, validate=True)`：`validate=True` 时遇到非 base64 字符会报错，而不是默认的"静默丢弃"。
- 简化：讲义表格要求图片"Validate media type and size"、音频"duration limits"、内嵌资源"Enforce payload and content limits now"——代码只检查 `mimeType` 是字符串，没有白名单和大小上限；`blob` 也没有校验是否为合法 base64。demo 中的 `iVBORw0KGgo=`（PNG 文件签名的 8 字节）和 `UklGRg==`（`RIFF`）只是合法的 base64 片段，不是完整媒体。

```python
def validate_tool_result(tool, result):
    if result.get("resultType") != "complete": ...
    content = result.get("content")
    if not isinstance(content, list) or not content: ...
    for block in content:
        validate_content_block(block)
    output_schema = tool.get("outputSchema")
    if output_schema is not None:
        if "structuredContent" not in result:
            raise ContractViolation("outputSchema requires structuredContent")
        validate_json_schema(result["structuredContent"], output_schema)
        if not any(block.get("type") == "text" for block in content):
            raise ContractViolation("structured results require compatibility text")
```

- 不看 `isError`：**错误结果同样必须满足输出 schema**（讲义核心规则之一）。
- `structuredContent` 交给通用校验器，可以是数组、布尔等任意 JSON 值——`tag_catalog` 返回数组、`blocked_secret_route` 返回布尔。
- 讲义说结构化结果"should also include serialized JSON in a text block"（SHOULD），代码把它变成了硬性要求；但并不检查文本内容是否真的等于 `structuredContent` 的序列化——因为"The text is not the validation source"。

### 3.6 工具描述符 `TOOLS`

| 工具 | inputSchema | outputSchema | 作用 |
|------|-------------|--------------|------|
| `tag_catalog` | 无参（`additionalProperties: false`） | 字符串数组 | 证明 `structuredContent` 不限于对象 |
| `evidence_bundle` | 无参 | `{artifact: string, blockCount: integer}` | 返回五种内容块 |
| `route_report` | `region`（`x-mcp-header: Region`）+ `report`（`minLength: 1`） | `{region, accepted}` | 头部路由 + 在 schema 内表达失败 |
| `blocked_secret_route` | `token`（`x-mcp-header: Token`） | 布尔 | 故意不安全，应被客户端拒绝 |

- 用 `_descriptor(...)` 工厂函数生成，保证四个描述符字段一致。
- `blocked_secret_route` 是"教学数据"：讲义"It proves that one rejected tool does not prevent valid tools from loading."——注意服务端本身**并不拒绝**它（直接调用照样返回 `true`），拒绝发生在客户端准入。

### 3.7 服务端 `ContractServer`

```python
    def tools_list(self, params):
        validate_request_meta(params)
        ordered = sorted(TOOLS, key=lambda tool: tool["name"])
        has_cursor = "cursor" in params
        cursor = params.get("cursor")
        if not has_cursor:
            page = ordered[:2]
            next_cursor: str | None = ""
        elif cursor == "":
            page = ordered[2:]
            next_cursor = None
        else:
            raise McpError(-32602, "invalid cursor")
        ...
        if next_cursor is not None:
            fields["nextCursor"] = next_cursor
```

- 按名字排序保证"重复调用顺序一致"（讲义 Verify It 第一条）。排序后第一页是 `blocked_secret_route`、`evidence_bundle`，第二页是 `route_report`、`tag_catalog`（实测）。
- **故意**用 `""` 作为第一页的 `nextCursor`，最后一页省略该字段。用 `"cursor" in params` 而不是 `params.get("cursor")` 来区分"没带游标"和"带了空串游标"——后者正是本节的陷阱。
- 非法游标返回 `-32602`。

```python
    def tools_call(self, params):
        validate_request_meta(params)
        tool = next((item for item in TOOLS if item["name"] == name), None)
        if tool is None:
            raise McpError(-32602, "unknown tool")           # 协议错误
        ...
        try:
            validate_json_schema(arguments, tool["inputSchema"])
        except ContractViolation as exc:
            return complete(content=[{"type": "text", "text": str(exc)}], isError=True)
        ...
        if name == "route_report":
            if arguments["report"] == "unavailable":
                return complete(
                    content=[{"type": "text", "text": "Report source is unavailable."}],
                    structuredContent={"region": arguments["region"], "accepted": False},
                    isError=True,
                )
```

- **两层错误**：未知工具 → `McpError` → JSON-RPC error；参数不合法或业务失败 → complete 结果 + `isError: True`。
- `route_report` 的 `unavailable` 分支是讲义推荐写法：失败也在 schema 内表达（`accepted: False`）。
- ⚠️ **参数校验失败分支违反了自己的输出契约**：只返回文本、没有 `structuredContent`，而四个工具都声明了 `outputSchema`。实测漏传 `report` 时，客户端 `call` 抛 `outputSchema requires structuredContent`（测验 Q9）。

```python
    def completion_complete(self, params, *, principal):
        validate_request_meta(params)
        self.completion_calls[principal] = self.completion_calls.get(principal, 0) + 1
        if self.completion_calls[principal] > 3:
            raise McpError(-32029, "completion rate limit exceeded")
        ...
        allowed = {
            "analyst": ["development", "staging"],
            "operator": ["development", "production", "staging"],
        }.get(principal, [])
        matches = [item for item in allowed if item.startswith(prefix)]
        return complete(completion={"values": matches[:100], "total": len(matches), "hasMore": False})
```

- `principal` 是仅限关键字参数，模拟"调用者身份由传输/认证层给出"，而不是请求体里自己声明的。
- 先按调用者取允许列表、再按前缀过滤——授权在前、匹配在后，无权的值根本不参与匹配。
- ⚠️ 三处简化（测验 Q12）：计数器没有时间窗口（是终身配额而非速率）；在校验 `ref`/`argument` **之前**计数，无效请求也消耗配额（实测 3 次错误请求后第 4 次直接 `-32029`）；`hasMore` 写死为 `False`，截断到 100 个后也不会变成 `True`。

```python
    def dispatch(self, request, *, principal="analyst"):
        is_notification = "id" not in request
        ...
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except McpError as exc:
            if is_notification:
                return None
            ...
            return {"jsonrpc": "2.0", "id": request_id, "error": error}
```

- JSON-RPC 规则：没有 `id` 的是通知，不返回任何响应（成功或失败都不返回）。测试 `test_idless_notification_receives_no_json_rpc_response`。
- 未知方法 `-32601`（method not found）。

### 3.8 参数头：渲染、编码、解码

```python
def _parameter_text(value, expected_type):
    if expected_type == "string" and isinstance(value, str):
        return value
    if expected_type == "boolean" and isinstance(value, bool):
        return "true" if value else "false"
    if expected_type == "integer" and isinstance(value, int) and not isinstance(value, bool):
        if not JS_SAFE_INTEGER_MIN <= value <= JS_SAFE_INTEGER_MAX:
            raise ContractViolation("mirrored integer is outside the JavaScript safe range")
        return str(value)
    raise ContractViolation(f"mirrored value does not match declared {expected_type} type")
```

- 把 JSON 值渲染成**唯一**的文本：布尔小写（Python 的 `str(True)` 是 `"True"`，不能直接用）、整数十进制、超出安全范围直接拒绝而不是舍入。

```python
def encode_parameter_header_value(value: str) -> str:
    sentinel_looking = value.startswith(BASE64_SENTINEL_PREFIX)
    if _is_plain_visible_ascii(value) and not sentinel_looking:
        return value
    payload = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"{BASE64_SENTINEL_PREFIX}{payload}{BASE64_SENTINEL_SUFFIX}"
```

- 明文条件：非空 + 每个字符都在 0x21–0x7E + 不以哨兵前缀开头。其它一律编码：Unicode、空串、空格、制表符、控制字符、CR/LF、首尾空白、像哨兵的文本。**不修剪、不规范化**原值。
- 实测：`"europe-λ"` → `=?base64?ZXVyb3BlLc67?=`；`""` → `=?base64??=`；`"=?base64?SGVsbG8=?="` → `=?base64?PT9iYXNlNjQ/U0dWc2JHOD0/PQ==?=`（再编码一次，接收方才能还原字面文本）。

```python
def decode_parameter_header_value(value: str) -> str:
    if value.startswith(BASE64_SENTINEL_PREFIX):
        if not value.endswith(BASE64_SENTINEL_SUFFIX):
            raise ContractViolation("parameter header uses a malformed base64 sentinel")
        payload = value[len(BASE64_SENTINEL_PREFIX) : -len(BASE64_SENTINEL_SUFFIX)]
        raw = base64.b64decode(payload, validate=True)
        decoded = raw.decode("utf-8")
        if base64.b64encode(raw).decode("ascii") != payload:
            raise ContractViolation("parameter header base64 is not canonical")
        return decoded
    if not _is_plain_visible_ascii(value):
        raise ContractViolation("plain parameter header is not visible ASCII")
    return value
```

- 严格解码：base64 必须合法、UTF-8 必须合法、并且**重新编码后必须与原载荷相同**——拒绝非规范的 base64（例如多余的填充变体），防止"同一个值有多种头部写法"造成的解析分歧。
- 明文分支同样要求可见 ASCII。
- ⚠️ 外壳规范性漏检：`"=?base64?="` 同时满足"以前缀开头"和"以后缀结尾"（两者共用中间的 `?`），切片得到空载荷，被解码为 `""`（实测）。应先检查 `len(value) >= len(前缀) + len(后缀)`。

### 3.9 构造与校验 `Mcp-Param-*`

```python
def build_parameter_headers(tool, arguments, audit_log):
    ...
    for path, name in validate_header_annotations(tool):
        value = _read_path(arguments, path)
        if value is MISSING:
            continue
        rendered = _parameter_text(value, property_schema["type"])
        header_name = f"Mcp-Param-{name}"
        encoded = encode_parameter_header_value(rendered)
        headers[header_name] = encoded
        if encoded != rendered:
            encoded_names.append(header_name)
    audit_log.append({"event": "parameter_headers_built",
                      "headerNames": sorted(headers),
                      "encodedHeaderNames": sorted(encoded_names)})
```

- 构造前再调用一次 `validate_header_annotations`——不假设描述符已经准入过。
- `MISSING = object()` 是一个独一无二的哨兵对象，用来区分"参数不存在"和"参数值为 `None`"。
- 审计事件只有头名和"哪些被编码了"，没有值。

```python
def validate_parameter_headers(tool, arguments, headers, audit_log):
    normalized: dict[str, list[tuple[str, str]]] = {}
    for supplied_name, supplied_value in headers.items():
        normalized.setdefault(supplied_name.casefold(), []).append((supplied_name, supplied_value))
    for path, suffix in validate_header_annotations(tool):
        expected_name = f"Mcp-Param-{suffix}"
        supplied = normalized.get(expected_name.casefold(), [])
        body_value = _read_path(arguments, path)
        if body_value is MISSING:
            if supplied:
                raise ContractViolation("recognized parameter header has no body argument")
            continue
        if not supplied:
            raise ContractViolation("recognized parameter header is missing")
        if len(supplied) != 1:
            raise ContractViolation("recognized parameter header is duplicated")
        decoded = decode_parameter_header_value(supplied[0][1])
        expected = _parameter_text(body_value, properties[path[0]]["type"])
        if decoded != expected:
            raise ContractViolation("recognized parameter header does not match the body")
```

- **服务端一半**：用 `casefold()` 把头名归一，再按"已识别"的头逐个检查：多余（body 没有该参数却有头）、缺失、重复（大小写不同的两个同名头）、畸形（解码失败）、不一致。
- 比较的是"解码后的头文本"与"body 值按同一规则渲染的文本"，所以 `region: 5`（类型不对）也会在这里被拒（实测 reason 为 "mirrored value does not match declared string type"）。
- 未声明的 `Mcp-Param-Foo` 不是"已识别"的头，会被忽略。

```python
def streamable_http_tool_call(server, request, headers, audit_log, *, principal="analyst"):
    if request.get("method") == "tools/call":
        ...
                try:
                    validate_parameter_headers(tool, arguments, headers, audit_log)
                except ContractViolation as exc:
                    return 400, {"jsonrpc": "2.0", "id": request.get("id"),
                                 "error": {"code": -32020,
                                           "message": "parameter headers do not match request body",
                                           "data": {"reason": str(exc)}}}
    return 200, server.dispatch(request, principal=principal)
```

- 模拟 HTTP 层：一致性闸门在 JSON-RPC 分发**之前**；失败返回 `(400, JSON-RPC error -32020)`，`data.reason` 只含类别，不含值。
- 成功或非 `tools/call` 请求返回 `(200, dispatch 结果)`——注意 JSON-RPC 层的错误（如未知工具）在 HTTP 上仍是 200。
- 对 `blocked_secret_route` 调用会得到 400，原因是"sensitive arguments must not be mirrored"（实测）——服务端闸门复用了同一个准入函数。

### 3.10 客户端 `ContractClient`

```python
    def discover_tools(self):
        cursor: str | None = None
        seen_cursors: set[str] = set()
        for _ in range(self.max_list_pages):
            params = {}
            if cursor is not None:
                params["cursor"] = cursor
            self.cursor_trace.append(cursor)
            response = self.server.dispatch(make_request(request_id, "tools/list", params))
            ...
            for tool in result["tools"]:
                try:
                    validate_tool_descriptor(tool)
                except ContractViolation as exc:
                    self.rejections.append({"tool": tool.get("name", "<unknown>"), "reason": str(exc)})
                    continue
                self.tools[tool["name"]] = tool
            next_cursor = result.get("nextCursor")
            if next_cursor is None:
                return self.tools
            if not isinstance(next_cursor, str): raise ...
            if next_cursor in seen_cursors:
                raise ContractViolation("tools/list returned a repeated or cyclic nextCursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise ContractViolation(f"tools/list exceeded the page limit of {self.max_list_pages}")
```

- 游标判断用 `is None`，`""` 会被继续使用；字段缺失与显式 `null` 都表示结束。
- **防御三件套**：页数上限（默认 100，构造函数用 `type(...) is not int` 拒绝 `True` 之类）、游标类型检查、重复/循环游标检测（只比较"是否见过"，不解析游标内容，仍然尊重不透明性）。
- 准入：每个描述符单独 `try`，坏的进 `rejections`，好的进 `self.tools`。
- ⚠️ 只捕获 `ContractViolation`：描述符不是字典、或头部属性 `type` 是列表时会抛 `AttributeError`/`TypeError`，整个发现过程崩溃（实测），与讲义"Reject the bad descriptor and admit valid tools independently"不符（测验 Q10）。

```python
    def call(self, name, arguments):
        if not self.tools:
            self.discover_tools()
        tool = self.tools.get(name)
        if tool is None:
            raise ContractViolation(f"tool is not admitted: {name}")
        response = self.server.dispatch(make_request(20, "tools/call", {...}), principal=self.principal)
        if response is None or "error" in response:
            raise ContractViolation("tools/call returned a protocol error")
        validate_tool_result(tool, response["result"])
        return response["result"]
```

- 只调用已准入的工具；消费前校验结果。
- ⚠️ 没有在发送前按 `inputSchema` 校验参数；讲义 Build It 列出"The client implements: argument and result validation"，代码只做了结果校验。

### 3.11 `main()`

- `build_parameter_headers` 用 `"europe-λ"` 触发 base64 编码；传给 `streamable_http_tool_call` 时把头名全部小写，演示服务端"忽略大小写识别"。
- 打印的 `audit event` 是 `audit_log[0]`（构造事件）；服务端校验事件在 `audit_log[1]`，未打印。
- `complete_environment("")` 以默认 `principal="analyst"` 调用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 自写 JSON Schema 子集 | 只用标准库，展示"在哪里校验" | 未知关键字静默放行；生产用完整的 2020-12 校验器（如 `jsonschema`） |
| 服务端客户端同进程 | 便于观察每道闸门 | 不覆盖真实 HTTP 解析、连接与超时 |
| 语法遍历全树找注解 | fail closed，不依赖 `$ref` 解析 | 名为 `x-mcp-header` 的普通属性也被拒 |
| 敏感名单精确匹配 | 简单、无误伤 | `access_token` 等变体漏网；可改子串规则或路由字段白名单 |
| 结构化结果强制带文本块 | 兼容旧客户端 | 比规范（SHOULD）更严 |
| 头部值规范编码 + 规范性重编码检查 | 消除解析分歧 | 哨兵外壳长度未检查（`=?base64?=` 漏网） |
| HTTP 闸门在分发前 | 网关与源站必须看到同一个值 | 需要服务端知道工具描述符 |
| 空串游标 + 页数上限 + 循环检测 | 演示不透明游标并防无限分页 | 超过 100 页的合法目录会直接报错，需按部署调整上限 |
| 补全按 principal 过滤 | 补全不成为枚举后门 | 限流是终身配额、`hasMore` 写死 |
| 参数校验失败返回 `isError` 文本 | 让模型可修复 | 违反自己声明的 outputSchema |
| 准入只捕获 `ContractViolation` | 代码简洁 | 意外异常会拖垮整个发现过程 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | 文件开头 `"""Phase 13 Lesson 28 ..."""` | 说明来源与依赖 |
| `typing.Any` | `dict[str, Any]` | 任意类型，适合 JSON 值 |
| 联合类型 | `str \| None`、`dict[str, Any] \| None` | 可空 |
| `@dataclass` 异常 | `class McpError(Exception)` | 用字段描述错误；实例不可哈希 |
| 自定义异常继承 | `class ContractViolation(ValueError)` | 调用方可 `except ValueError` 一并捕获 |
| 幂运算 | `2**53 - 1` | 整数任意精度，不会溢出 |
| 正则 `fullmatch` | `HEADER_TOKEN.fullmatch(header_name)` | 整个字符串必须匹配 |
| `**kwargs` 收集与展开 | `def complete(**fields)`、`{"resultType": "complete", **fields, ...}` | 关键字参数收集成字典；字典展开合并 |
| 仅限关键字参数 | `def completion_complete(self, params, *, principal)` | `*` 后的参数必须写名字 |
| 递归 + 元组路径 | `iter_header_annotation_nodes(child, (*path, key))` | 用 `*path` 解包旧元组再追加 |
| `next(生成器, 默认值)` | `next((item for item in TOOLS if ...), None)` | 取第一个匹配，没有就返回 `None` |
| `sorted(key=lambda ...)` | `sorted(TOOLS, key=lambda tool: tool["name"])` | 按字段排序 |
| 切片 | `ordered[:2]`、`value[len(P):-len(S)]` | 取前 N 个；去掉前后缀 |
| `dict.setdefault` | `normalized.setdefault(name.casefold(), []).append(...)` | 不存在时先插入默认值再返回 |
| `str.casefold()` | `supplied_name.casefold()` | 比 `lower()` 更彻底的大小写折叠 |
| 哨兵对象 | `MISSING = object()`；`if value is MISSING` | 区分"不存在"与 `None` |
| `isinstance` 排除 `bool` | `isinstance(value, int) and not isinstance(value, bool)` | `bool` 是 `int` 子类 |
| `ord()` 与链式比较 | `0x21 <= ord(character) <= 0x7E` | 字符码点范围判断 |
| `all()` / `any()` | `all(0x21 <= ord(c) <= 0x7E for c in value)` | 短路求值 |
| `base64` 模块 | `b64encode(...)`、`b64decode(payload, validate=True)` | 编码/严格解码 |
| `bytes.decode` / `str.encode` | `value.encode("utf-8")`、`raw.decode("utf-8")` | 文本与字节互转 |
| 异常链 | `raise ContractViolation(...) from exc` | 保留原始原因 |
| 多异常捕获 | `except (ValueError, UnicodeDecodeError, base64.binascii.Error)` | 元组列出 |
| 类继承覆盖方法（测试中） | `class ExplicitNullCursorServer(main.ContractServer)` + `super().tools_list(params)` | 在测试里改写服务端行为 |
| 字典推导式 | `{name.lower(): value for name, value in headers.items()}` | 构造小写头名字典 |
| `type(x) is not int` | `ContractClient.__init__` | 精确类型判断 |
| 返回元组 | `return 400, {...}` | 一次返回状态码和响应体 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，退出码 0）：

```text
visible tools: evidence_bundle, route_report, tag_catalog
rejected tools: blocked_secret_route
cursor trace: ['<first>', "''"]
array structuredContent: ['contracts', 'mcp', 'stateless']
content block types: ['text', 'image', 'audio', 'resource_link', 'resource']
mirrored header names: ['Mcp-Param-Region']
encoded parameter value: True
HTTP parity status: 200
audit event: {'event': 'parameter_headers_built', 'headerNames': ['Mcp-Param-Region'], 'encodedHeaderNames': ['Mcp-Param-Region']}
analyst completions: ['development', 'staging']
```

逐行解读：

1. **visible tools**：3 个工具被准入，跨两页（第一页 `blocked_secret_route` + `evidence_bundle`，第二页 `route_report` + `tag_catalog`）。
2. **rejected tools**：`blocked_secret_route` 因属性名 `token` 命中敏感名单被拒；其它工具不受影响。
3. **cursor trace**：第一次请求不带游标，第二次带 `''`——证明客户端没有把空串当作结束。
4. **array structuredContent**：数组通过了 `{"type": "array", "items": {"type": "string"}}` 的校验。
5. **content block types**：五种内容块全部通过 `validate_content_block`。
6. **mirrored header names**：只有 `Mcp-Param-Region`；`report` 没有注解，不镜像。
7. **encoded parameter value: True**：`"europe-λ"` 含非 ASCII，头部值为 `=?base64?ZXVyb3BlLc67?=`。
8. **HTTP parity status: 200**：头名被改成全小写 `mcp-param-region` 后，服务端仍能识别并解码，与 body 一致，通过闸门并分发。
9. **audit event**：只有头名和"被编码的头名"，没有 `europe-λ`，也没有编码后的值。
10. **analyst completions**：没有 `production`。

---

## 7. 动手改一改

1. **讲义 Interactive Lab 1–3**：把 `tag_catalog.outputSchema.type` 改成 `"object"`，运行 demo，观察 `client.call("tag_catalog", {})` 抛出 `$: expected object`；再改回来。
2. **修复参数错误分支**：给每个工具定义"失败时的合规 `structuredContent`"，在参数校验失败时返回它，并补一个测试：漏传 `report` 时客户端 `call` 能拿到 `isError: True` 且不抛异常（参考测验 Q9）。
3. **让准入永不崩溃**：在 `discover_tools` 中用一个 `admit()` 包装，把任何意外异常转成拒绝记录；测试服务端返回 `"oops"` 和 `type` 为列表的描述符时，其它工具仍被准入（测验 Q10）。
4. **讲义 Interactive Lab 8**：对 `region` 依次尝试 `"münchen"`、`"eu\nwest"`、`" eu-west "`、`"=?base64?SGVsbG8=?="`，打印编码结果并用 `decode_parameter_header_value` 证明逐字还原；再补上哨兵外壳长度检查，让 `"=?base64?="` 被拒。
5. **改进补全**：实现滑动窗口限流、先校验后计数、`hasMore = len(matches) > 100`，并加一个"150 个候选"的测试（测验 Q12）。
6. **讲义 Practice Lab**：新增 `search_evidence` 工具（`query`、`limit`、`region`），输出为 `{uri, title, score}` 数组，每条结果附一个 `resource_link`；在处理函数里手动限制 `limit`（因为本校验器不支持 `maximum`），并按调用者过滤 URI。

---

## 8. 常见坑

- **用 truthiness 判断游标**：`if not next_cursor: break` 会把 `""` 当作结束，丢掉最后几页。
- **把 `structuredContent` 当成字典**：数组、布尔、`null` 都合法；`result["structuredContent"]["x"]` 这类代码会在合法输出上崩溃。
- **错误结果省略结构化输出**：声明了 `outputSchema`，`isError: true` 也要给出合规的 `structuredContent`。
- **只在 `properties` 里找注解**：`oneOf`、`items`、`$defs` 中的 `x-mcp-header` 必须被发现并拒绝。
- **把 `str(True)` 当头部值**：Python 得到 `"True"`，协议要求小写 `true`。
- **修剪或规范化头部值**：任何改动都会让服务端的一致性比较失败，或者更糟——让网关与源站看到不同的值。
- **在审计里记录头部值**：即使是 base64 编码后的值也不行，编码不是加密。
- **准入只捕获自定义异常**：畸形描述符可能触发 `TypeError`/`AttributeError`，必须统一兜底。
- **补全不做授权**：补全接口会变成枚举隐藏资源名的后门。
- **把注解当策略**：工具注解（如"只读""破坏性"提示）只是服务端自述的提示，授权和审批必须在注解之外执行。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：`python3 -m unittest discover tests -v`。实际结果：**34 个测试全部通过**（`Ran 34 tests in 0.003s, OK`）。测试用 `importlib.util.spec_from_file_location` 按路径加载 `main.py`（注册为 `lesson28_main`），运行后会产生 `__pycache__`，已删除。

| 分组 | 测试 | 验证的性质 |
|------|------|-----------|
| 发现与元数据 | `test_discovery_declares_tools_and_completions`、`test_every_request_requires_its_own_metadata` | `server/discover` 声明 tools 与 completions 能力；缺 `_meta` 的请求返回 `-32602` |
| 分页 | `test_empty_string_cursor_is_followed_and_order_is_stable`、`test_explicit_null_cursor_stops_pagination`、`test_repeated_cursor_is_rejected_before_another_request`、`test_cyclic_cursor_chain_is_rejected`、`test_unique_cursor_stream_is_bounded_by_page_limit` | 空串游标被跟随、两个客户端看到同样顺序；显式 `null` 结束；重复游标在第 2 次请求后立即报错（不会发第 3 次）；`a→b→a` 循环被发现；无限不同游标在 `max_list_pages=3` 时停止且恰好请求 3 次 |
| 准入 | `test_sensitive_header_descriptor_is_rejected`、`test_malformed_x_mcp_header_is_rejected`、`test_x_mcp_header_inside_one_of_is_rejected`、`test_x_mcp_header_inside_items_is_rejected`、`test_x_mcp_header_inside_ref_definition_is_rejected` | 敏感字段被拒且原因含 "sensitive"；含 CRLF 的头名被拒；`oneOf`、`items`、`$defs` 中的注解被拒 |
| 结构化输出 | `test_array_structured_content_is_valid_and_has_text_mirror`、`test_client_rejects_nonconforming_structured_output`、`test_error_result_cannot_omit_required_structured_output`、`test_error_result_cannot_return_nonconforming_structured_output` | 数组合法且文本块可解析为同一数组；对象违反数组 schema；错误结果缺 `structuredContent` 或不合规都被拒 |
| 内容块 | `test_all_current_content_block_types_are_validated` | 五种内容块按顺序出现并通过校验 |
| 头部值编码 | `test_visible_ascii_parameter_value_stays_plain`、`test_unicode_parameter_value_uses_exact_base64_utf8_sentinel`、`test_newline_parameter_value_is_encoded_instead_of_rejected`、`test_padded_parameter_value_is_encoded_without_trimming`、`test_sentinel_looking_parameter_value_is_encoded_again`、`test_safe_integer_boundaries_are_mirrored`、`test_unsafe_integer_values_are_rejected` | 可见 ASCII 保持明文；Unicode、换行、首尾空格、哨兵样文本都编码且能逐字还原；安全整数上下界可镜像，越界 ±1 被拒 |
| HTTP 一致性闸门 | `test_case_insensitive_header_name_and_encoded_value_match_body`、`test_missing_recognized_header_is_http_400_and_json_rpc_32020`、`test_mismatched_recognized_header_is_http_400_and_json_rpc_32020`、`test_duplicated_recognized_header_is_rejected`、`test_recognized_header_without_body_argument_is_rejected` | 头名大小写互换（`swapcase`）仍通过且审计记录规范头名；缺失/不一致 → 400 + `-32020`；重复头、无 body 参数的头被拒 |
| 审计 | `test_header_audit_records_names_without_values`、`test_encoded_values_remain_redacted_from_client_and_server_audits` | 审计含头名、不含原值；客户端与服务端审计中既没有原值也没有编码后的值 |
| 补全 | `test_completion_is_authorized_and_rate_limited` | analyst 补全不含 `production`；第 4 次调用触发限流（客户端表现为 `ContractViolation`） |
| 错误分层与通知 | `test_protocol_errors_and_tool_errors_stay_separate`、`test_idless_notification_receives_no_json_rpc_response` | 未知工具 → JSON-RPC `-32602`；`unavailable` → `isError: True` 且 `structuredContent = {"region": "eu-west", "accepted": False}`；无 `id` 的通知不返回响应 |

测试没有覆盖的点（也就是本讲解指出的问题）：参数校验失败时的错误结果违反输出 schema、畸形描述符导致发现过程崩溃、客户端不校验参数、`=?base64?=` 被接受、敏感名单只做精确匹配、补全计数无时间窗口且无效请求也计数、`hasMore` 写死。
