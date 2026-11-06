# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 22 节 通过换行分隔的 stdio 传输 JSON-RPC 2.0 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（演示，用 `io.BytesIO` 模拟 stdin/stdout，不启动子进程）；在 `code/` 下 `python -m pytest -q` 或 `python -m unittest discover -s tests` ｜ **依赖**：仅标准库（`io`、`json`、`dataclasses`、`typing`、`unittest`）

---

## 1. 这份代码在考察什么

第 21 节有了工具注册表，但模型客户端与工具服务端通常是两个进程。本节手写两者之间的"线"：

1. **JSON-RPC 2.0 信封**：request / notification / success / error 四种形状，以及 batch。
2. **换行分帧**：一行一个 JSON，`\n` 就是消息边界。
3. **五个标准错误码**：`-32700`、`-32600`、`-32601`、`-32602`、`-32603`，以及它们的触发条件。
4. **流不被污染**：坏的一行只得到一条错误响应，循环继续读到 EOF。
5. **分层**：传输层不认识任何工具，只把 `(method, params)` 交给调用方提供的 `handler`。

> 一句话：**亲手实现一次"每个分帧层都在付出什么"——解析、校验信封、分派、错误映射、序列化、刷新输出——这正是 MCP stdio 传输的底层形状。**

同时要注意：讲义说演示中 handler 会在处理中途发两条进度 notification，代码里并没有这个演示；另外有两类输入能让 `serve` 崩溃（非法 UTF-8、不可序列化的结果），与"不污染流"的承诺不符。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ERR_*` 常量 | 模块常量 | 五个标准错误码 | 错误码表 |
| `JsonRpcError` / `MethodNotFound` / `InvalidParams` | 异常类层级 | handler 用来表达特定错误码，`code` 是类属性 | 异常 → 错误码映射 |
| `Request` | dataclass | 解析后的请求：`method`、`params`、`id`、`is_notification` | 请求对象 |
| `_is_valid_envelope` | 函数 | 检查 `jsonrpc`、`method`、`params`、`id` 的类型 | 信封校验 |
| `parse_request` | 函数 | 一行文本 → `(Request, None)` 或 `(None, 错误信封)` | 解析 |
| `_err_envelope` / `_ok_envelope` / `_notification_envelope` | 函数 | 构造三种出站信封 | 信封构造 |
| `StdioTransport` | 类 | 包装一对字节流：`read_line`、`write_response`、`write_error`、`write_notification` | 传输 |
| `Handler` | 类型别名 | `Callable[[str, Any], Any]` | 分派接口 |
| `_handle_one` | 函数 | 调用 handler，把结果/异常转成响应信封，notification 返回 `None` | 分派 + 错误映射 |
| `_process_batch` | 函数 | 逐个处理 batch 元素，收集非 notification 响应 | batch |
| `_write_raw` | 函数 | 序列化任意对象（dict 或 list）为一行并 flush | 出站分帧 |
| `serve` | 函数 | 主循环：读行 → 解析 → batch/单条 → 写响应，直到 EOF | 服务循环 |
| `_demo` | 函数 | 用 BytesIO 喂入 7 行，打印服务端的全部响应 | 演示 |

数据流：`stdin.readline()` → `decode` + `strip` → `json.loads` → 是数组？→ `_process_batch` → `_handle_one` × N → `_write_raw(数组)`；否则 → `parse_request` → `_handle_one` → `_write_raw(对象)` → `stdout.write` + `flush`。

---

## 3. 逐段精讲

### 3.1 错误码与异常层级

```python
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603


class JsonRpcError(Exception):
    code: int = ERR_INTERNAL

    def __init__(self, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.data = data


class MethodNotFound(JsonRpcError):
    code = ERR_METHOD_NOT_FOUND


class InvalidParams(JsonRpcError):
    code = ERR_INVALID_PARAMS
```

- 错误码挂在**类属性** `code` 上，子类只需覆盖这一行。想要服务端自定义错误（`-32000～-32099`）时，再写一个子类即可（实测 `code = -32001` 的子类能带 `data` 正确返回）。
- `super().__init__(message)` 让 `str(exc)` 仍然是消息文本；`data` 用来携带结构化附加信息。
- handler 只需"抛对的异常"，不需要知道 JSON-RPC 信封长什么样——这是讲义"The transport never sees a tool registry"的另一面：registry/handler 也不必看见传输细节。

### 3.2 信封校验

```python
def _is_valid_envelope(msg: Any) -> bool:
    if not isinstance(msg, dict):
        return False
    if msg.get("jsonrpc") != "2.0":
        return False
    if not isinstance(msg.get("method"), str):
        return False
    if "params" in msg and not isinstance(msg["params"], (dict, list)):
        return False
    if "id" in msg:
        rid = msg["id"]
        if isinstance(rid, bool):
            return False
        if not isinstance(rid, (int, str, type(None))):
            return False
    return True
```

- 必须是对象；`jsonrpc` 必须**恰好**是字符串 `"2.0"`；`method` 必须是字符串。
- `params` 可以省略，出现时必须是对象（按名传参）或数组（按位置传参）。`"params": null` 或标量都会被判为 Invalid Request（实测）。
- `id` 可以是整数、字符串或 `null`。`bool` 需要先排除，因为 `isinstance(True, int)` 为真——与第 21 节的 bool 特判是同一个坑。浮点 id（如 `1.5`）被拒绝，比规范（"SHOULD NOT contain fractional parts"）更严格。
- 多余的键（如 `"foo": 1`）不会导致失败。

### 3.3 `parse_request` 与信封构造

```python
def parse_request(raw: str) -> tuple[Request | None, dict | None]:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, _err_envelope(None, ERR_PARSE, f"parse error: {exc}")
    if not _is_valid_envelope(msg):
        rid = msg.get("id") if isinstance(msg, dict) else None
        return None, _err_envelope(rid, ERR_INVALID_REQUEST, "invalid request envelope")
    is_notif = "id" not in msg
    return Request(method=msg["method"], params=msg.get("params"),
                   id=msg.get("id"), is_notification=is_notif), None
```

- 返回"二选一"的元组：成功时错误为 `None`，失败时请求为 `None`——一种不用异常的错误传递风格，调用方先检查 `err`。
- **notification 判定**：`"id" not in msg`，看的是键是否存在而不是值，所以 `"id": null` 的消息是 request（会得到 `id: null` 的响应，实测）。
- **回显 id 的问题**：信封非法时取 `msg.get("id")` 放进错误响应。若 id 本身就是非法类型（`true`、对象），它会被原样回显（实测 `"id": true`、`"id": {"a": 1}`）。规范要求检测 id 出错时响应 id 为 `null`。
- 一个信封非法、但又没有 id 的消息（发送者可能想发 notification）会得到 `id: null` 的错误响应——服务端无法确认它是合法 notification，所以按规范回错误。

```python
def _err_envelope(rid, code, message, data=None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rid, "error": err}
```

- `data` 为 `None` 时不写该键（规范中 `data` 是可选成员）。`_notification_envelope` 同理，`params` 为 `None` 时省略。

### 3.4 `StdioTransport`

```python
class StdioTransport:
    def __init__(self, stdin: BinaryIO, stdout: BinaryIO) -> None:
        self._in: BinaryIO = stdin
        self._out: BinaryIO = stdout

    def read_line(self) -> bytes | None:
        line = self._in.readline()
        if not line:
            return None
        return line

    def _write(self, obj: dict) -> None:
        encoded = json.dumps(obj, separators=(",", ":"))
        self._out.write((encoded + "\n").encode("utf-8"))
        self._out.flush()
```

- 操作的是**字节流**（`BinaryIO`），读写时自己做 UTF-8 编解码。真实场景传入 `sys.stdin.buffer` / `sys.stdout.buffer`，演示与测试传入 `io.BytesIO`——讲义说两者的 `.readline()` / `.write()` 契约相同。
- `readline()` 在 EOF 时返回 `b""`，`if not line` 把它转成 `None`；一行空行返回 `b"\n"`，不是 EOF。最后一行没有 `\n` 也能读到（实测可正常处理）。
- `readline()` 没有长度上限：一个没有换行的超长输入会被整段读进内存，生产中应传入 `size` 上限或用分块读取。
- `separators=(",", ":")` 去掉多余空格，输出更紧凑；`json.dumps` 默认 `ensure_ascii=True`，中文会被写成 `\uXXXX`，字符串中的换行写成 `\n`——这保证了"一个对象一行"。
- 每次写完 `flush()`：管道两端是不同进程，不刷新的话消息可能停在缓冲区里，客户端一直等不到响应。

### 3.5 `_handle_one`：分派与错误映射

```python
def _handle_one(handler: Handler, transport: StdioTransport, req: Request) -> dict | None:
    try:
        result = handler(req.method, req.params)
    except MethodNotFound as exc:
        return None if req.is_notification else _err_envelope(req.id, exc.code, exc.message, exc.data)
    except InvalidParams as exc:
        return None if req.is_notification else _err_envelope(req.id, exc.code, exc.message, exc.data)
    except JsonRpcError as exc:
        return None if req.is_notification else _err_envelope(req.id, exc.code, exc.message, exc.data)
    except Exception as exc:
        return None if req.is_notification else _err_envelope(
            req.id, ERR_INTERNAL, "internal error",
            {"exception": type(exc).__name__, "detail": str(exc)},
        )
    if req.is_notification:
        return None
    return _ok_envelope(req.id, result)
```

- 前三个 `except` 分支完全相同：`MethodNotFound`、`InvalidParams` 都是 `JsonRpcError` 的子类，只保留 `except JsonRpcError` 一个分支效果一样。写成三个是为了在阅读时把讲义中的映射表"摆出来"。
- `except Exception` 兜底：其他异常一律 `-32603`，`data.exception` 是类名（讲义要求），`data.detail` 是异常消息（讲义未提，可能泄露内部路径等信息）。
- notification 无论成功失败都返回 `None`——**错误也被吞掉**，而且没有任何日志。
- 参数 `transport` 从未使用。讲义说 handler 可以在请求进行中通过 `write_notification` 发进度，但 `Handler` 的签名拿不到 transport；需要用闭包注入（见第 7 节练习 2 / 测验 Q10）。

### 3.6 `_process_batch`

```python
def _process_batch(handler, transport, items: list) -> list | None:
    out: list = []
    for raw in items:
        if not isinstance(raw, dict) or not _is_valid_envelope(raw):
            rid = raw.get("id") if isinstance(raw, dict) else None
            out.append(_err_envelope(rid, ERR_INVALID_REQUEST, "invalid request envelope"))
            continue
        is_notif = "id" not in raw
        req = Request(method=raw["method"], params=raw.get("params"),
                      id=raw.get("id"), is_notification=is_notif)
        resp = _handle_one(handler, transport, req)
        if resp is not None:
            out.append(resp)
    if not out:
        return None
    return out
```

- 每个元素独立校验与处理，一个元素出错不影响其他元素（实测 `[1, 合法请求, {"foo": 1}]` 得到三条响应）。
- 顺序处理、按输入顺序输出。规范允许任意顺序与并发处理，客户端必须按 id 匹配而不能依赖顺序。
- 全是 notification → `out` 为空 → 返回 `None` → 不写任何东西（规范要求，不能返回 `[]`）。
- 这里重复了 `parse_request` 中构造 `Request` 的逻辑，以及"回显非法 id"的问题。

### 3.7 `serve`：主循环

```python
def serve(handler: Handler, transport: StdioTransport) -> None:
    while True:
        line = transport.read_line()
        if line is None:
            return
        text = line.decode("utf-8").rstrip("\n").strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            transport.write_error(None, ERR_PARSE, f"parse error: {exc}")
            continue
        if isinstance(parsed, list):
            if not parsed:
                transport.write_error(None, ERR_INVALID_REQUEST, "empty batch")
                continue
            batch_out = _process_batch(handler, transport, parsed)
            if batch_out is not None:
                _write_raw(transport, batch_out)
            continue
        req, err = parse_request(text)
        if err is not None:
            _write_raw(transport, err)
            continue
        resp = _handle_one(handler, transport, req)
        if resp is not None:
            _write_raw(transport, resp)
```

- **EOF 即返回**：`read_line` 返回 `None` 时结束。真实 stdio 服务端中，客户端关闭管道就是"请结束"的信号。
- **空行跳过**：`.strip()` 同时去掉 `\r`，兼容 CRLF 输入（实测）。`rstrip("\n")` 其实已被 `strip()` 覆盖，是冗余的。
- **先解析一次判断是否为数组**，单条消息再交给 `parse_request` **解析第二次**——功能正确但重复工作。
- **"不污染流"的边界**：`JSONDecodeError` 被捕获，但以下情况在 `try` 之外，会让 `serve` 抛异常退出（实测）：
  - `line.decode("utf-8")` 遇到非法 UTF-8 字节 → `UnicodeDecodeError`；
  - `_write_raw` 中 `json.dumps` 遇到 set、datetime 等不可序列化的结果 → `TypeError`。
- `float("nan")` 结果不会崩溃，但会输出 `NaN`——这不是合法 JSON；`json.loads` 也默认接受输入中的 `NaN`。
- 两个 JSON 对象写在同一行会得到 `-32700 Extra data`（实测）——换行分帧要求严格的"一行一条"。

### 3.8 `_write_raw` 与 `_demo`

```python
def _write_raw(transport: StdioTransport, obj: Any) -> None:
    encoded = json.dumps(obj, separators=(",", ":"))
    transport._out.write((encoded + "\n").encode("utf-8"))
    transport._out.flush()
```

- 与 `StdioTransport._write` 几乎一样，只是接受数组（batch 响应）。它直接访问了 `transport._out` 私有属性；更整洁的做法是让 `_write` 接受 `Any` 并公开。

```python
    stdin = io.BytesIO()
    for r in requests:
        stdin.write((json.dumps(r) + "\n").encode("utf-8"))
    stdin.write(b"{not json\n")
    stdin.seek(0)
    stdout = io.BytesIO()
    transport = StdioTransport(stdin, stdout)
    serve(handler, transport)
    stdout.seek(0)
    lines = [json.loads(line) for line in stdout.read().decode("utf-8").splitlines() if line]
```

- 先往 BytesIO 写入全部请求，再 `seek(0)` 回到开头供 `serve` 读取——这是"用内存流模拟管道"的固定套路；读输出前同样要 `seek(0)`（或直接 `getvalue()`）。
- 演示 handler 覆盖了四种结果：正常（`math.add`）、`InvalidParams`、`MethodNotFound`、内部异常（`boom`），再加 notification、batch 与坏 JSON。
- 演示中没有讲义描述的"handler 中途发两条进度 notification"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 换行分隔 JSON | 最简单的分帧，`readline` 即可，便于调试 | 需防超长行；要求严格一行一条；LSP 等用 `Content-Length` 头 |
| 操作字节流并自己编解码 | 与真实管道一致，编码可控 | 非法 UTF-8 未处理会导致崩溃，需捕获 `UnicodeDecodeError` |
| 每条消息后 `flush` | 跨进程及时可见 | 高吞吐时开销略大，可批量 flush 但需注意延迟 |
| 错误码挂在异常类属性上 | handler 只需抛对异常 | 三个相同的 `except` 分支可合并 |
| 内部错误返回类名与消息 | 便于调试 | `detail` 可能泄露内部信息；生产只在调试模式返回 |
| notification 失败静默 | 规范要求 | 应写 stderr 日志或计数指标 |
| batch 顺序处理 | 简单、确定性 | 无并发；慢请求阻塞整个 batch |
| 传输层不知道方法 | 分层清晰，handler 背后接注册表 | handler 拿不到 transport，无法发进度通知 |
| BytesIO 演示 | 无需子进程、可确定性测试 | 不覆盖真实管道的阻塞、部分读、进程退出等问题 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `ERR_PARSE = -32700` | 大写命名表示常量 |
| 异常类层级 + 类属性 | `class MethodNotFound(JsonRpcError): code = ERR_METHOD_NOT_FOUND` | 子类覆盖类属性；`except 父类` 能捕获子类 |
| `super().__init__(message)` | `JsonRpcError.__init__` | 调用父类构造函数，让 `str(exc)` 等于消息 |
| 类型注解默认值 | `code: int = ERR_INTERNAL` | 类级别带注解的属性 |
| `BinaryIO` | `def __init__(self, stdin: BinaryIO, stdout: BinaryIO)` | 来自 `typing`，表示二进制文件类对象 |
| 元组返回值 | `-> tuple[Request | None, dict | None]` | 二选一的结果，调用处 `req, err = parse_request(text)` 解包 |
| `isinstance` 与元组 | `isinstance(msg["params"], (dict, list))` | 第二个参数可以是类型元组 |
| `type(None)` | `isinstance(rid, (int, str, type(None)))` | 判断是否为 `None` 的另一种写法 |
| `in` 判断键 | `"id" not in msg` | 判断字典是否含某键（与值是否为 None 无关） |
| 条件表达式 | `None if req.is_notification else _err_envelope(...)` | 一行内的 if/else |
| 多个 `except` 分支 | `except MethodNotFound ... except Exception` | 按顺序匹配，第一个匹配的分支生效 |
| `type(exc).__name__` | `{"exception": type(exc).__name__}` | 取异常类名 |
| 字节与字符串转换 | `line.decode("utf-8")`、`(encoded + "\n").encode("utf-8")` | I/O 层面是字节，处理层面是字符串 |
| `str.strip` / `rstrip` | `.rstrip("\n").strip()` | 去掉首尾空白（含 `\r`、`\n`） |
| `json.dumps(separators=...)` | `separators=(",", ":")` | 紧凑输出 |
| `json.JSONDecodeError` | `except json.JSONDecodeError as exc` | 解析失败的异常，消息里含行列位置 |
| `io.BytesIO` | `stdin = io.BytesIO()`、`stdin.seek(0)` | 内存中的二进制流；写完需回到开头再读 |
| `splitlines()` + 推导式 | `[json.loads(line) for line in ... .splitlines() if line]` | 按行拆分并过滤空行 |
| `while True` + `return` | `serve` 主循环 | 直到 EOF 才退出 |
| 类型别名 | `Handler = Callable[[str, Any], Any]` | 描述 handler 的签名 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `_demo()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13）输出（已压缩空白）：

```text
{"server_responses": [
  {"jsonrpc": "2.0", "id": 1, "result": 5},
  {"jsonrpc": "2.0", "id": 2, "error": {"code": -32602, "message": "a and b required"}},
  {"jsonrpc": "2.0", "id": 3, "error": {"code": -32601, "message": "method 'missing'"}},
  {"jsonrpc": "2.0", "id": 4, "error": {"code": -32603, "message": "internal error",
                                         "data": {"exception": "RuntimeError", "detail": "intentional"}}},
  [{"jsonrpc": "2.0", "id": 10, "result": {"text": "hi"}},
   {"jsonrpc": "2.0", "id": 11, "result": 2}],
  {"jsonrpc": "2.0", "id": null, "error": {"code": -32700,
     "message": "parse error: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"}}
]}
```

逐项解读：

- **7 行输入、6 行输出**：第 5 行是 notification（`log`），没有响应；batch 只占一行输出（一个数组）。
- **id 1**：`2 + 3 = 5`。
- **id 2**：缺少 `b`，handler 抛 `InvalidParams` → `-32602`。
- **id 3**：未知方法 → handler 抛 `MethodNotFound` → `-32601`。
- **id 4**：`RuntimeError` → `-32603`，`data` 带类名与消息。
- **batch**：三个元素中的 notification 被跳过，响应数组只有 id 10 和 11。
- **坏 JSON**：`-32700`，`id: null`，消息里带有 `json` 模块给出的位置信息（第 1 行第 2 列），并且它是最后一行——如果它在中间，后面的行同样会被正常处理（测试 `test_parse_error_then_continue`）。

额外边界实测（临时脚本，不修改源码）：

| 输入 / 场景 | 结果 |
|------------|------|
| `b"\xff\xfe\n"` 后跟合法请求 | `serve` 抛 `UnicodeDecodeError` 退出，合法请求无响应 |
| handler 返回 `{1, 2}` 后跟合法请求 | `serve` 抛 `TypeError` 退出 |
| handler 返回 `float("nan")` | 输出 `"result":NaN`（非法 JSON） |
| handler 返回 `"中文\n换行"` | 一行：`"中文\n换行"` |
| `"id": true` / `{"a": 1}` / `1.5` | `-32600`，id 被原样回显 |
| `"id": null` 的请求 | 正常执行，响应 `id: null` |
| `"params": null` 或 `5` | `-32600` |
| `[1, 合法请求, {"foo": 1}]` | 一行数组：`-32600`、`-32601`、`-32600` |
| 以 `\r\n` 结尾的请求 | 正常处理 |
| `42`、`"x"`、`null` 单独成行 | 各得到一条 `-32600` |
| 一行里两个 JSON 对象 | `-32700 Extra data` |
| 最后一行没有 `\n` | 正常处理 |
| 自定义 `code = -32001` 的异常 | `{"code": -32001, "message": "rate limited", "data": {...}}` |

---

## 7. 动手改一改

1. **让流真正不被污染**：捕获 `UnicodeDecodeError`（返回 `-32700`）、在 `_write_raw` 中捕获序列化错误并降级为 `-32603`，同时使用 `allow_nan=False`（测验 Q9 有实测通过原测试的代码）。为两种情况各补一个测试。
2. **进度通知**：实现 `serve_with_notify`，让 handler 通过注入的 `notify` 在处理中途发送 `progress`，并写测试断言"两条 notification 在最终响应之前"——这才是讲义描述的 asymmetric flow。
3. **安全的 id 回显**：实现 `_safe_id`，非法 id 一律回 `null`；给 `test_boolean_id_rejected` 补上对 `id` 的断言。
4. **合并重复代码**：把三个相同的 `except` 合成一个；让 `serve` 只解析一次 JSON，把已解析对象传给新的 `parse_message(obj)`；去掉对 `transport._out` 的直接访问。
5. **长度上限与日志**：`read_line` 增加 `max_bytes` 参数，超长行返回 `-32600`（或断开）；notification 处理失败时把错误写到 `sys.stderr`。
6. **真实子进程**：写一个 `if "--stdio" in sys.argv: serve(handler, StdioTransport(sys.stdin.buffer, sys.stdout.buffer))` 入口，再用 `subprocess.Popen` 从另一个脚本驱动它，观察忘记 `flush` 或在 handler 中 `print()` 时会发生什么。

---

## 8. 常见坑

- **往 stdout 打日志**：stdio 服务端的 stdout 是协议通道，`print()` 会插入非协议文本，客户端解析出错。日志写 stderr。
- **忘记 flush**：消息停在缓冲区，客户端一直阻塞等待。
- **漂亮打印 JSON**：`json.dumps(obj, indent=2)` 会产生多行，破坏换行分帧。
- **用 `"id": null` 发请求**：服务端会响应，但响应与 parse error 的 `id: null` 无法区分。
- **把 `True` 当 id**：Python 中 `True == 1`，id 匹配表可能把两者混为一谈。
- **给 notification 回响应**：违反规范，客户端无处安放。
- **空 batch 返回 `[]`**：规范要求返回单个 `-32600` 错误对象。
- **以为捕获了 `JSONDecodeError` 就万事大吉**：解码（UTF-8）和编码（序列化）两端都可能抛异常。

---

## 9. 测试在验证什么

`tests/test_transport.py` 共 15 个 `unittest` 测试，分 5 组。辅助函数 `_drive(requests, handler)` 把请求（字典或原始字节）编码成多行写入 BytesIO，运行 `serve`，再把输出逐行 `json.loads` 返回。`echo_handler` 支持 `echo`（原样返回 params）和 `addone`（缺 `n` 抛 `InvalidParams`），其他方法抛 `MethodNotFound`。在 `code/` 下运行 `python -m pytest -q`、`python -m unittest discover -s tests` 或 `python tests/test_transport.py`。

| 测试 | 验证的性质 |
|------|-----------|
| **TestErrorCodes** | |
| `test_parse_error` | 坏 JSON → `-32700`，`id` 为 `None` |
| `test_invalid_request_wrong_version` | `jsonrpc: "1.0"` → `-32600` |
| `test_invalid_request_no_method` | 缺 `method` → `-32600` |
| `test_method_not_found` | 未知方法 → `-32601`，且 `id` 正确回显为 1 |
| `test_invalid_params` | `addone` 缺参数 → `-32602` |
| `test_internal_error_carries_exception_name` | handler 抛 `ValueError` → `-32603`，`data.exception == "ValueError"` |
| `test_boolean_id_rejected` | `id` 为 `True` / `False` → `-32600`（未检查响应 id 是否为 null） |
| **TestNotifications** | |
| `test_notification_no_response` | notification 不产生任何输出 |
| `test_notification_handler_exception_silent` | notification 调用未知方法也不产生输出 |
| **TestBatches** | |
| `test_batch_mixed_returns_only_non_notifications` | 3 个元素（中间是 notification）→ 输出一行数组，含 id 1 和 3 两条响应 |
| `test_batch_all_notifications_silent` | 全是 notification → 无输出 |
| `test_empty_batch_invalid_request` | `[]` → 一条 `-32600` 错误（单个对象） |
| **TestStreamDoesNotPoison** | |
| `test_parse_error_then_continue` | 坏行之后的合法请求仍得到正常结果 |
| `test_empty_lines_skipped` | 前导空行被跳过，只有一条响应 |
| **TestNotificationHelper** | |
| `test_write_notification_no_id` | `write_notification` 输出含 `jsonrpc`、`method`，且没有 `id` 键 |

实际运行结果（`python3 -m pytest -q`）：

```text
...............                                                          [100%]
15 passed in 0.02s
```

测试的盲区：

- 讲义说测试覆盖"the asymmetric flow where a handler writes a notification mid-call"，实际只测了单独调用 `write_notification`；
- 没有测试非法 UTF-8、不可序列化结果、NaN、超长行——这正是 `serve` 会崩溃或输出非法 JSON 的地方；
- 没有检查非法 id 的回显、`"id": null` 请求、batch 内非法元素的响应 id；
- 讲义提到的"-32603 data 中带异常名"已测，但 `detail` 字段没有被约束。
