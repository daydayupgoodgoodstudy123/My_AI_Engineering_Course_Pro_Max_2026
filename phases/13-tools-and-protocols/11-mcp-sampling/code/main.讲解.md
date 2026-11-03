# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 11 节 MCP 模型输入：Sampling 迁移与无状态 MRTR ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试 `python3 -m unittest discover tests -v` ｜ **依赖**：仅标准库（`base64`、`hashlib`、`hmac`、`json`、`time`、`copy`、`dataclasses`、`typing`），无需网络、无需真实模型

---

## 1. 这份代码在考察什么

这份代码在一个文件里同时扮演 **MCP 服务端**（`dispatch` / `tools_call`）和**客户端驱动**（`run_mrtr` + `fake_host_model`），演示一个需要两次模型调用的工具 `summarize_repo` 如何在 2026-07-28 的无状态协议下完成：

1. **每请求元数据校验**：`_meta` 中的版本与能力，错误码 `-32602` / `-32022` / `-32021`。
2. **发现**：`server/discover` 与（因为广告了 `tools` 而必须实现的）`tools/list`。
3. **MRTR 两轮**：第一轮返回 `input_required`，嵌入 `sampling/createMessage` 让客户端模型挑文件；第二轮再嵌入一次让模型写摘要；第三次请求得到 `complete`。
4. **签名状态**：`requestState` 用 HMAC-SHA256 保护，绑定主体、方法、参数摘要、过期时间与阶段。
5. **校验模型输出**：把模型返回当不可信输入，做 JSON 解析、类型检查与白名单过滤。

> 一句话：**把"服务端需要客户端的模型"这件事，从隐式的会话回调改写成显式、有界、可验证的多次独立请求**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 常量 `PROTOCOL_META` 等 | 字符串 | `_meta` 中保留键的名字 | 无状态信封 |
| `SERVER_SECRET` | bytes | HMAC 密钥（演示用，硬编码） | 状态完整性 |
| `FAKE_REPO` | 字典 | 6 个假文件，充当可读文件白名单 | 确定性工作 |
| `TOOLS` | 列表 | `summarize_repo` 的描述符与 `inputSchema` | `tools/list` |
| `McpError` | dataclass 异常 | `code/message/data` | 结构化错误 |
| `request_meta` / `_server_meta` / `complete` | 函数 | 构造请求 `_meta`、服务端身份、`complete` 结果 | 信封与结果类型 |
| `validate_request_meta` | 函数 | 版本与能力校验，返回 `meta` | `-32602` / `-32022` |
| `server_discover` / `tools_list` | handler | 发现与工具列表，带缓存提示 | 发现 |
| `_b64` / `_unb64` / `_arguments_digest` | 辅助函数 | base64url 编解码、参数规范化摘要 | 规范化序列化 |
| `seal_request_state` / `verify_request_state` | 函数 | 签发与校验 `requestState` | HMAC 绑定 |
| `_sampling_request` / `_input_required` | 函数 | 构造嵌入的 `sampling/createMessage` 与 `input_required` 结果 | MRTR 结果 |
| `_sampling_text` | 函数 | 从 `inputResponses` 中安全取出文本 | 响应校验 |
| `tools_call` | handler | 三阶段状态机：无 state → pick → summarize | MRTR 服务端 |
| `dispatch` | 函数 | JSON-RPC 分派、通知处理、错误包装 | 协议入口 |
| `fake_host_model` | 函数 | 确定性的"客户端模型" | host 侧 |
| `run_mrtr` | 函数 | 客户端驱动循环：满足输入请求并用新 id 重试 | MRTR 客户端 |
| `main` | 函数 | 打印 discover、请求 id 列表与最终结果 | 演示 |

数据流：`main()` → `dispatch(server/discover)` → `run_mrtr()`：`dispatch(id=1)` → `tools_call` 无 state → `input_required{pick_files}` → `fake_host_model` → `dispatch(id=2, inputResponses, requestState)` → `verify_request_state` → 校验 picks → `input_required{summary}` → `fake_host_model` → `dispatch(id=3)` → `complete{content, structuredContent}`。

---

## 3. 逐段精讲

### 3.1 常量与工具描述符

```python
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"
SERVER_SECRET = b"lesson-11-demo-secret-change-in-production"
```

- 把长键名收成常量，避免拼写错误；测试也复用这些常量。
- ⚠️ `SERVER_SECRET` 是硬编码的演示密钥，变量名本身就在提醒"生产中要换"。生产中应从密钥管理服务读取，多实例共享同一密钥（或带 key id 支持轮换），否则 A 实例签的 state 到 B 实例验不过。

`TOOLS` 中 `inputSchema` 是一个 `type: object` 的 JSON Schema，`audience` 是可选字符串（`required: []`）。
- ⚠️ `audience` 在整个流程中**只参与参数摘要**，两轮 prompt 都没有用到它——它在本例中的唯一作用是演示"参数被绑定进 state"。

### 3.2 `McpError`：用 dataclass 定义异常

```python
@dataclass
class McpError(Exception):
    code: int
    message: str
    data: dict[str, Any] | None = None
```

- `@dataclass` 自动生成 `__init__(code, message, data=None)`，比手写构造函数更短。
- 与第 10 节的 `RpcError` 相比，这里 `data` 为 `None` 时 `dispatch` 不输出 `data` 字段（`if exc.data is not None`）。
- 小细节：实测 `str(McpError(-32602, "x"))` 是 `"(-32602, 'x')"`（异常的 `args` 是全部构造参数），因此日志里打印时最好用 `exc.message`。

### 3.3 每请求元数据校验

```python
def validate_request_meta(params: dict[str, Any]) -> dict[str, Any]:
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise McpError(-32602, "missing request _meta")
    requested_version = meta.get(PROTOCOL_META)
    if not isinstance(requested_version, str):
        raise McpError(-32602, "missing protocol version")
    if requested_version != PROTOCOL_VERSION:
        raise McpError(-32022, "unsupported protocol version",
                       {"supported": [PROTOCOL_VERSION], "requested": requested_version})
    capabilities = meta.get(CAPABILITIES_META)
    if not isinstance(capabilities, dict):
        raise McpError(-32602, "missing client capabilities")
    return meta
```

- 与第 10 节结构一致，但**返回 `meta`**，让 `tools_call` 继续检查具体能力。
- 每个 handler 都自己调用一次（`server_discover`、`tools_list`、`tools_call`），没有任何"握手后免检"。
- `clientInfo` 不检查，也不用于身份——讲义："`clientInfo` and `serverInfo` are display and diagnostics metadata."

### 3.4 发现与工具列表

```python
def tools_list(params: dict[str, Any]) -> dict[str, Any]:
    validate_request_meta(params)
    return complete(
        tools=sorted(deepcopy(TOOLS), key=lambda tool: tool["name"]),
        ttlMs=60_000,
        cacheScope="public",
    )
```

- `sorted(..., key=lambda tool: tool["name"])`：按名字确定性排序（只有一个工具，但写法为扩展做好准备）。
- **`deepcopy` 很关键**：如果直接返回 `TOOLS` 里的字典，调用方修改返回值（例如把 `audience.type` 改成 `integer`）会污染全局描述符，下一个请求就拿到被改过的 schema。测试 `test_tools_list_returns_independent_descriptors` 正是在验证这一点。
- discover 缓存 5 分钟、tools/list 缓存 1 分钟，都是 `public`。

### 3.5 规范化摘要与 base64url

```python
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def _arguments_digest(arguments: dict[str, Any]) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
```

- **urlsafe** 字母表用 `-`、`_` 代替 `+`、`/`，适合放进 URL 或 HTTP 头；去掉 `=` 填充让 token 更短。
- `_unb64` 中 `-len(value) % 4` 计算需要补几个 `=`：长度 214 时 `-214 % 4 = 2`，补两个。
- `_arguments_digest` 用**规范化 JSON**（键排序、无空格）求 SHA-256：同一参数无论键顺序如何，摘要都一样（实测 `{"b":1,"a":2}` 与 `{"a":2,"b":1}` 摘要相等）。这是"绑定参数"的基础。

### 3.6 签发与校验 `requestState`

```python
def seal_request_state(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(SERVER_SECRET, body, hashlib.sha256).digest()
    return f"{_b64(body)}.{_b64(signature)}"
```

- token 格式：`base64url(body).base64url(HMAC-SHA256(secret, body))`，与 JWT 的"内容.签名"思路相同（但更简化，没有 header）。
- 签名 32 字节 → 43 个字符（实测）。

```python
def verify_request_state(token, *, principal, arguments, now=None):
    try:
        body_part, signature_part = token.split(".", 1)
        body = _unb64(body_part)
        supplied = _unb64(signature_part)
    except (ValueError, TypeError) as exc:
        raise McpError(-32602, "invalid requestState encoding") from exc
    expected = hmac.new(SERVER_SECRET, body, hashlib.sha256).digest()
    if not hmac.compare_digest(supplied, expected):
        raise McpError(-32602, "requestState integrity check failed")
    try:
        state = json.loads(body)
    except json.JSONDecodeError as exc:
        raise McpError(-32602, "invalid requestState payload") from exc
    if state.get("principal") != principal: ...       # 主体
    if state.get("method") != "tools/call": ...       # 方法
    if state.get("argumentsDigest") != _arguments_digest(arguments): ...  # 参数
    if int(state.get("expiresAt", 0)) < (int(time.time()) if now is None else now): ...  # 过期
    return state
```

检查顺序是有讲究的：

1. **先验签名，再解析 JSON**：没通过签名的数据不进入 `json.loads`，减少解析攻击面。
2. `hmac.compare_digest`：常量时间比较，防计时攻击。
3. 然后依次比对**主体**（来自 `dispatch` 的 `principal` 参数，代表认证后的身份，而不是 `clientInfo`）、**方法**、**参数摘要**、**过期时间**。
4. 所有失败都是 `-32602`，讲义："Reject a bad signature, expired value, changed principal, or changed arguments with `-32602`."

细节：

- `token.split(".", 1)`：没有点号时解包成两个变量会抛 `ValueError`（实测 `"abc"` → `invalid requestState encoding`）。
- `urlsafe_b64decode` 默认会**丢弃非字母表字符**，所以 `"###.###"` 解码成空字节串，最后在签名比对处失败（实测 `integrity check failed`）——结果仍然安全。
- `now` 参数是**依赖注入**：测试可以传 `now=11` 构造"已过期"场景，而不必真的等待。
- 过期判断是 `expiresAt < now`，所以 `now == expiresAt` 时仍有效（实测 `now=10` 通过）。
- `from exc`：保留原始异常链，便于调试。
- ⚠️ 没有绑定**工具名**（只有一个工具时无碍，见测验 Q12）；没有 **nonce**，同一 state 在过期前可重放（实测同一第一轮 state 重试两次都成功）。

### 3.7 构造嵌入的 sampling 请求

```python
def _sampling_request(prompt: str, *, intelligence: float) -> dict[str, Any]:
    return {
        "method": "sampling/createMessage",
        "params": {
            "messages": [{"role": "user", "content": {"type": "text", "text": prompt}}],
            "systemPrompt": "Return only the requested value.",
            "modelPreferences": {
                "costPriority": round(1.0 - intelligence, 2),
                "intelligencePriority": intelligence,
            },
            "maxTokens": 400,
        },
    }
```

- 嵌入请求和旧版 `sampling/createMessage` 的 `params` 形状一样，只是不再作为独立 JSON-RPC 请求发出，而是放进 `inputRequests[key]`。
- 挑文件时 `intelligence=0.2`（便宜模型就够），写摘要时 `0.8`（需要更强的综合能力）。
- ⚠️ `costPriority = 1 - intelligence` 让两者加和为 1，但讲义明确说它们**相互独立、不必加和为 1**——这只是代码的偷懒写法。
- 没有显式写 `includeContext`；讲义建议在遗留 Sampling 流程里保持 `"none"`，显式写上更清楚。
- `systemPrompt` 要求"只返回所需值"，配合服务端对返回值的严格解析。

`_input_required` 把它包成：`{"resultType": "input_required", "inputRequests": {key: ...}, "requestState": seal_request_state(state), "_meta": ...}`。

### 3.8 安全地取出模型输出

```python
def _sampling_text(input_responses: Any, key: str) -> str:
    if not isinstance(input_responses, dict):
        raise McpError(-32602, "inputResponses must be an object")
    response = input_responses.get(key)
    if not isinstance(response, dict):
        raise McpError(-32602, f"missing input response: {key}")
    content = response.get("content")
    if not isinstance(content, dict) or content.get("type") != "text":
        raise McpError(-32602, f"invalid sampling response: {key}")
    text = content.get("text")
    if not isinstance(text, str) or not text.strip():
        raise McpError(-32602, f"empty sampling response: {key}")
    return text
```

- 一层层地"剥洋葱"：每一层都先检查类型再取值，任何一层不符都返回 `-32602`。
- 用 `key` 定位响应：本轮请求的键是 `pick_files`，下一轮是 `summary`，客户端带错键（例如在 summarize 阶段只带 `pick_files`）会得到 `missing input response: summary`。

### 3.9 `tools_call`：三阶段状态机

```python
    state_token = params.get("requestState")
    if state_token is None:
        state = {"phase": "pick", "principal": principal, "method": "tools/call",
                 "argumentsDigest": _arguments_digest(arguments),
                 "expiresAt": int(time.time()) + 300}
        prompt = ("Choose three representative files and return a JSON array. Files: "
                  + json.dumps(sorted(FAKE_REPO)))
        return _input_required("pick_files", prompt, state, intelligence=0.2)
```

- **阶段 0（无 state）**：创建初始状态（5 分钟有效），把排序后的文件清单放进 prompt，返回第一轮 `input_required`。
- 在此之前已经检查过：工具名必须是 `summarize_repo`、`arguments` 必须是字典、能力中必须有 `sampling`（否则 `-32021`）——**每一轮都会重新检查**，因为每一轮都是独立请求。

```python
    if state["phase"] == "pick":
        raw_picks = _sampling_text(responses, "pick_files")
        try:
            picks = json.loads(raw_picks)
        except json.JSONDecodeError as exc:
            raise McpError(-32602, "pick_files must return JSON") from exc
        if not isinstance(picks, list) or not all(isinstance(item, str) for item in picks):
            raise McpError(-32602, "pick_files must return a string array")
        picked = [name for name in picks if name in FAKE_REPO][:3]
        if not picked:
            raise McpError(-32602, "pick_files returned no known files")
        combined = "\n\n".join(f"{name}: {FAKE_REPO[name]}" for name in picked)
        next_state = {**state, "phase": "summarize", "picked": picked,
                      "expiresAt": int(time.time()) + 300}
        prompt = "Summarize these files in two sentences:\n\n" + combined
        return _input_required("summary", prompt, next_state, intelligence=0.8)
```

- **阶段 pick**：把模型输出当不可信输入——JSON 解析、类型检查、**白名单过滤**（只保留 `FAKE_REPO` 中真实存在的文件名，`../../etc/passwd` 被过滤），最多 3 个。这对应讲义"Validate every sampling response before using it as a filename"。
- 服务端自己读取文件内容（确定性工作），拼成第二轮 prompt。
- `next_state = {**state, ...}`：继承主体、方法、参数摘要，更新阶段、加入**已验证的** `picked`，并刷新过期时间。
- ⚠️ 没有去重：`["README.md"] * 3` 会得到三个相同的 `picked`（实测）。

```python
    if state["phase"] == "summarize":
        summary = _sampling_text(responses, "summary")
        return complete(
            content=[{"type": "text", "text": summary}],
            structuredContent={"picked": state["picked"], "summary": summary},
            isError=False,
        )
```

- **阶段 summarize**：取出摘要，返回最终的 `complete`。`content` 是给模型/人看的文本，`structuredContent` 是机器可读的结构化结果，`isError: False` 表示工具执行成功（这是工具层面的错误标志，与 JSON-RPC 的 `error` 不同）。
- `picked` 从**签名过的 state** 中读出，而不是相信客户端这一轮的说法。
- 摘要文本不做内容校验（实测任意文本都被接受）——在本例中这是客户端自己模型的输出，客户端本来就能控制。

### 3.10 `dispatch`：协议入口

- 方法分派用 `if/elif`，只支持 `server/discover`、`tools/list`、`tools/call`，其余 `-32601`。
- `principal` 是关键字参数，默认 `"user-42"`，模拟"传输层认证后得到的主体"。测试和演示都用默认值；用 `principal="user-7"` 重试会得到 `requestState principal mismatch`（实测）。
- 通知（无 `id`）：仍然**执行** handler（可能产生副作用），但成功和失败都返回 `None`。讲义：HTTP 适配器对已接受的通知返回 `202 Accepted`、无 body。

### 3.11 客户端侧：`fake_host_model` 与 `run_mrtr`

- `fake_host_model` 按 prompt 中是否含 `"Choose three"` 返回固定的文件数组或固定摘要，让演示完全确定。讲义："Replace only `fake_host_model` when connecting a real host."
- `run_mrtr`：只要结果是 `input_required`，就为每个 `inputRequests` 键调用模型，`request_id += 1`，用 `{**base_params, "inputResponses": ..., "requestState": ...}` 重试。`base_params` 保证方法与原参数不变。
- ⚠️ 这是一个**没有任何安全护栏的客户端**：没有最大轮数、没有能力/方法检查、没有审批、没有字节/token 上限。讲义 Safety Invariants 要求的这些都应在客户端实现（见测验 Q11）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 状态放在签名的 `requestState` 中 | 协议层无会话，任何实例都能处理任一轮 | token 随轮次变大；需要密钥管理与轮换 |
| HMAC 而非加密 | 实现简单，只需完整性 | 客户端可读到 `picked` 等内容；需要保密时用 AEAD |
| 绑定主体/方法/参数摘要/过期 | 防跨主体移植、换参数、长期重放 | 未绑定工具名、无 nonce，过期前可重放 |
| 先验签名再解析 JSON | 不解析不可信字节 | 无 |
| `now` 参数注入 | 测试过期无需等待 | 无 |
| 模型输出白名单过滤 | 防止路径穿越、幻觉文件名 | 未去重；摘要不校验内容/长度 |
| 每轮重新校验版本与能力 | 无状态：每轮都是独立请求 | 少量重复开销 |
| `tools/list` 返回 `deepcopy` | 防止调用方篡改全局描述符 | 每次复制一份 |
| 客户端与服务端放在同一文件 | 一眼看全流程 | 客户端没有轮数上限、审批、预算 |
| `costPriority = 1 - intelligence` | 写法简洁 | 容易误导读者以为两者必须互补 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 继承 `Exception` | `class McpError(Exception)` | 用数据类自动生成构造函数，同时可以被 `raise` |
| 可选字段默认值 | `data: dict[str, Any] \| None = None` | dataclass 字段带默认值必须放在无默认值字段之后 |
| 仅限关键字参数 `*` | `def request_meta(*, sampling: bool = True)`、`verify_request_state(token, *, principal, ...)` | `*` 之后的参数必须用 `name=value` 传，避免位置传错 |
| `**kwargs` | `def complete(**fields)` | 收集任意关键字参数 |
| 字典展开合并 | `{**state, "phase": "summarize", ...}`、`{**base_params, "inputResponses": ...}` | 复制旧字典并覆盖/新增键 |
| 条件表达式 | `{"sampling": {}} if sampling else {}`、`int(time.time()) if now is None else now` | 一行的 if/else |
| `lambda` 作为排序键 | `sorted(..., key=lambda tool: tool["name"])` | 匿名函数 |
| `copy.deepcopy` | `deepcopy(TOOLS)` | 递归复制嵌套结构 |
| 元组解包 + `split` | `body_part, signature_part = token.split(".", 1)` | 最多分割一次；个数不符抛 `ValueError` |
| 多异常捕获 | `except (ValueError, TypeError) as exc` | 一次捕获多种异常 |
| 异常链 `raise ... from exc` | `raise McpError(...) from exc` | 保留原始异常作为 `__cause__` |
| `bytes` 与 `str` | `json.dumps(...).encode()`、`.decode("ascii")` | 签名作用在字节上 |
| `hmac` / `hashlib` | `hmac.new(SECRET, body, hashlib.sha256).digest()`、`hmac.compare_digest` | 消息认证码与常量时间比较 |
| `base64.urlsafe_b64encode` | `_b64` | URL 安全的 base64 |
| 负数取模 | `-len(value) % 4` | Python 的 `%` 结果与除数同号，用来算补齐数 |
| f-string | `f"{_b64(body)}.{_b64(signature)}"`、`f"missing input response: {key}"` | 字符串插值 |
| 字典推导式 | `{key: fake_host_model(req) for key, req in pending["inputRequests"].items()}` | 为每个输入请求生成响应 |
| 列表推导式 + 切片 | `[name for name in picks if name in FAKE_REPO][:3]` | 过滤后取前 3 个 |
| `all()` + 生成器 | `all(isinstance(item, str) for item in picks)` | 全部元素满足条件 |
| `str.join` + 生成器 | `"\n\n".join(f"{name}: {FAKE_REPO[name]}" for name in picked)` | 拼接多行文本 |
| `while` 循环 + 链式 `.get` | `response.get("result", {}).get("resultType")` | 键可能缺失时安全取值 |
| `tuple` 返回值注解 | `-> tuple[dict[str, Any], list[int]]` | 函数返回两个值 |
| `if __name__ == "__main__":` | 文件末尾调用 `main()` | 被测试导入时不会执行演示 |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出（完整）：

```text
discover: {
  "resultType": "complete",
  "supportedVersions": ["2026-07-28"],
  "capabilities": {"tools": {}},
  "ttlMs": 300000,
  "cacheScope": "public",
  "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "mrtr-demo", "version": "1.0.0"}}
}
independent request ids: [1, 2, 3]
final: {
  "resultType": "complete",
  "content": [{"type": "text", "text": "This repository demonstrates a stateless MCP server and client retry loop. Each MRTR round carries all required state without a protocol session."}],
  "structuredContent": {
    "picked": ["README.md", "server.py", "docs/intro.md"],
    "summary": "This repository demonstrates ... without a protocol session."
  },
  "isError": false,
  "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "mrtr-demo", "version": "1.0.0"}}
}
```

（为节省篇幅把多行 JSON 压成了单行，内容与实际输出一致。）

逐项解读：

- **discover**：只广告 `tools` 能力，缓存 5 分钟 public。
- **`[1, 2, 3]`**：两轮 `input_required` + 一次 `complete`，三个独立请求、三个不同 id。
- **`picked`** 来自签名状态，与 `fake_host_model` 返回的三个文件一致，均在白名单中。
- **`content` 与 `structuredContent`** 同时给出：前者是文本，后者是结构化数据。

中间过程（自己打印第一轮结果可见，已实测）：

- 第一轮 prompt：`Choose three representative files and return a JSON array. Files: ["LICENSE", "README.md", "client.py", "docs/intro.md", "server.py", "tests/test_server.py"]`（已排序）；`modelPreferences` 为 `{"costPriority": 0.8, "intelligencePriority": 0.2}`。
- 第一轮 `requestState` 长 268 字符，body 解码为 `{"argumentsDigest":"a7581292...","expiresAt":...,"method":"tools/call","phase":"pick","principal":"user-42"}`——明文可读。

---

## 7. 动手改一改

1. **（讲义练习 1）** 让 `fake_host_model` 在挑文件时返回 `"not json"`，确认得到 `-32602 pick_files must return JSON`；再试 `{"a": 1}` 和 `["../../etc/passwd"]`，观察三种不同的错误信息。
2. **（讲义练习 2）** 在第一次调用和重试之间把 `audience` 改成 `executive`，确认 `arguments mismatch`，并解释为什么"签名没被改"也挡不住。
3. **（讲义练习 5）** 写一个测试：`expiresAt = 100`、`now = 101` 被拒绝，`now = 100` 被接受，明确边界语义。
4. **（修 bug）** 给 `picked` 加保持顺序的去重，并把工具名 `name` 写进 state、在 `verify_request_state` 中比对；补两个测试。
5. **（讲义练习 3）** 增加第三轮 `critique`：把第二轮的 `summary` 写进签名 state，第三轮请求模型批评摘要；同时在 `run_mrtr` 里加 `MAX_ROUNDS = 3` 的客户端上限，并写测试证明第 4 轮会被拒绝。
6. **（讲义练习 4，进阶）** 去掉 Sampling：写一个 `ServerModelAdapter`（接口 `complete(prompt, *, intelligence) -> str`），`tools_call` 直接调用它并一次性返回 `complete`。列出从客户端转移到服务端的责任：API 密钥、预算与限流、审批（如需）、计费、日志与追踪、模型选择与回退。

---

## 8. 常见坑

- **重试复用原 id**：每一轮都是新请求，必须用新的 JSON-RPC id。
- **客户端解析或修改 `requestState`**：只能原样回显，改一个字节都会签名失败。
- **只签名 `phase`**：不绑定主体、参数、过期时间，state 就能被跨用户、跨参数、长期重放。
- **用 `clientInfo` 当身份**：它是客户端自报的诊断信息，主体必须来自认证层。
- **把模型输出直接当文件名/URL**：必须解析、类型检查、白名单过滤。
- **以为 HMAC 能保密**：HMAC 只防篡改，body 是明文 base64。
- **客户端循环不设上限**：恶意服务端可以无限返回 `input_required` 消耗模型额度。
- **在 `tools/list` 等方法上返回 `input_required`**：MRTR 只允许出现在 `tools/call`、`prompts/get`、`resources/read`。
- **返回全局描述符的引用**：调用方一改，全局 schema 就被污染，要 `deepcopy`。
- **把 model preferences 当成必须加和为 1 的权重**：它们是独立提示。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m unittest discover tests -v`。实际结果：**Ran 13 tests ... OK**。

`tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按文件路径加载 `main.py`，模块名设为 `lesson11_main` 并注册进 `sys.modules`——这样多个课程的 `main.py` 同时被测试时不会因同名模块互相覆盖。辅助函数 `tool_request(request_id, sampling=...)` 生成一个标准的 `tools/call` 请求。

| 测试 | 验证的性质 |
|------|-----------|
| `test_discovery_is_complete_and_cacheable` | discover 结果为 `complete`、版本正确、`ttlMs=300000`、含 serverInfo |
| `test_tools_list_is_deterministic_cacheable_and_described` | tools/list 为 `complete`、`ttlMs=60000`、`public`、按名排序、`inputSchema.type == "object"` |
| `test_tools_list_returns_independent_descriptors` | 修改第一次返回的描述符不影响第二次（`deepcopy` 生效） |
| `test_initial_call_returns_embedded_sampling_request` | 首次调用返回 `input_required`，`pick_files` 的方法是 `sampling/createMessage`，`requestState` 是字符串 |
| `test_client_driver_uses_fresh_ids_and_finishes` | `run_mrtr` 的 id 为 `[1, 2, 3]`，最终 `complete`、`isError` 为假、`picked` 有 3 个 |
| `test_unsupported_protocol_version_is_rejected` | `2025-11-25` → `-32022`，`data` 完全相等 |
| `test_missing_request_metadata_is_rejected` | 删掉 `_meta` → `-32602` |
| `test_non_string_protocol_version_is_invalid_params` | 版本为 `None` → `-32602` |
| `test_sampling_capability_is_required` | 无 sampling 能力 → `-32021`，`data` 为 `{"requiredCapabilities": {"sampling": {}}}` |
| `test_notification_never_receives_a_json_rpc_response` | 无 `id` 的请求返回 `None` |
| `test_request_state_tampering_is_rejected` | 改掉 token 第一个字符 → `-32602` |
| `test_request_state_is_bound_to_original_arguments` | 重试时改 `audience` → `-32602` |
| `test_expired_request_state_is_rejected` | `expiresAt=10`、`now=11` → 抛 `McpError(-32602)` |

测试盲区（可作为练习补上）：

- 没有测试非法 JSON / 非数组 / 未知文件名的模型输出（讲义练习 1）。
- 没有测试主体不匹配（`principal="user-7"`）、重放、重复文件名。
- 没有测试客户端轮数上限——因为代码里根本没有这个上限。
- 篡改测试改的是 body 的第一个字符；如果改的是签名部分，结果同样应为 `-32602`，可以再补一条。
