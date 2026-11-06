# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 23 节 函数调用分派器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（演示，约 1 秒，含真实的退避等待）；在 `code/` 下 `python -m pytest -q` 或 `python -m unittest discover -s tests` ｜ **依赖**：仅标准库（`asyncio`、`inspect`、`json`、`random`、`time`、`dataclasses`、`typing`、`unittest`）

---

## 1. 这份代码在考察什么

第 20 节的循环在 `AWAITING_TOOL` 处交出一个工具调用，第 21 节的注册表知道工具长什么样，第 22 节的传输层负责把消息送到。本节的分派器是"真正去执行"的那一层，讲义称它是"where the harness pays for every promise the schema made"：

1. **每次调用的超时**：`asyncio.wait_for`，超时返回类型化错误而不是让循环挂住。
2. **指数退避 + 抖动的重试**：最多 3 次，只重试 `timeout`（仅幂等工具）和 `transient`。
3. **幂等键去重**：同一 key 的在途调用只执行一次，完成后结果缓存 60 秒。
4. **统一错误信封**：`DispatchError{kind, message, attempts, jsonrpc_code}`。
5. **有界并发**：信号量限制同时执行的 handler 数量。

> 一句话：**把"计时器、重试、幂等、并发"这些与业务无关但决定可靠性的逻辑，全部收敛到一个接缝上，循环、注册表、handler 都不必关心。**

同时要注意代码在几个并发边界上与讲义承诺不符：信号量饱和时幂等去重失效、leader 被取消时 follower 永久挂起、同步阻塞 handler 不受超时约束、预算不随重试扣减。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ERR_*` | 常量 | `-32601`、`-32602`、`-32603` | JSON-RPC 错误码 |
| `TransientError` | 异常 | handler 声明"可重试的失败" | 瞬时故障 |
| `_DispatchedError` | 内部异常 | 把 `DispatchError` 包进 future，让 follower 保留原 kind | 结果共享 |
| `DispatchError` | dataclass + Exception | 统一错误信封，`to_envelope()` 转 JSON-RPC 错误对象 | 错误信封 |
| `DispatchOk` | dataclass | `result + attempts` | 成功结果 |
| `_ToolRecord` / `MiniRegistry` | dataclass / 类 | 精简版注册表：`register`、`get`、`validate` | 第 21 节的替身 |
| `_walk` | 函数 | 极简 schema 校验（4 种类型 + required） | 参数校验 |
| `_InFlight` | dataclass | 在途调用的 future 与开始时间 | 在途表 |
| `Dispatcher` | 类 | `dispatch`（唯一入口）、`_run_with_retries`、`gather_bounded` | 分派器 |
| `_invoke` | 协程函数 | 统一调用同步/异步 handler | 适配层 |
| `_backoff` | 函数 | `0.1 × 4^(n−1) × (1 + U[0, 0.5])` | 指数退避 + 抖动 |
| `_map_exception` | 函数 | 异常 → `DispatchError`（还原 `_DispatchedError`） | 错误映射 |
| `_demo` | 协程函数 | 演示重试成功、超时、schema、缺失、正常、幂等对 | 演示 |

数据流：`dispatch(name, args)` → `registry.get`（失败 → `not_found`）→ `registry.validate`（失败 → `schema`）→ 预算检查（→ `budget_exceeded`）→ 幂等缓存命中 / 等待在途 future → `async with semaphore` → `_run_with_retries`：循环 { `wait_for(_invoke(handler, args))` → 成功返回 / 超时或 Transient 则退避重试 / 其他异常映射为 `internal` } → `DispatchOk` 或 `DispatchError`。

---

## 3. 逐段精讲

### 3.1 错误类型

```python
class TransientError(Exception):
    """Raised by a handler to indicate the failure is worth retrying."""


@dataclass
class DispatchError(Exception):
    kind: str
    message: str
    attempts: int
    jsonrpc_code: int = ERR_INTERNAL

    def __post_init__(self) -> None:
        super().__init__(f"{self.kind}: {self.message}")

    def to_envelope(self) -> dict:
        return {"code": self.jsonrpc_code, "message": self.message,
                "data": {"kind": self.kind, "attempts": self.attempts}}
```

- `TransientError` 是 handler 与分派器之间的约定：抛它表示"这次失败值得重试"。
- `DispatchError` 同时是 dataclass 和 `Exception` 子类。dataclass 生成的 `__init__` 不会调用 `Exception.__init__`，所以用 `__post_init__` 补上，让 `str(err)` 显示 `"timeout: timeout after 10ms"`。副作用：dataclass 默认 `eq=True` 会把 `__hash__` 设为 `None`，于是这个异常**不可哈希**（实测 `hash(DispatchError(...))` 抛 `TypeError`）。
- 虽然它是异常类，`dispatch` 却把它当**返回值**而不是抛出——调用方用 `isinstance(out, DispatchError)` 判断。
- `to_envelope()` 生成 JSON-RPC 错误对象的形状，`data` 里放 `kind` 与 `attempts`，方便经第 22 节传输层直接返回给客户端。
- `kind` 是普通字符串，讲义列出六种：`timeout`、`transient`、`schema`、`not_found`、`internal`、`budget_exceeded`。

```python
class _DispatchedError(Exception):
    def __init__(self, error: "DispatchError") -> None:
        super().__init__(error.message)
        self.error = error
```

- leader 失败时要把错误"放进" future 给 follower；`future.set_exception` 需要异常对象，于是用这个包装类携带原始 `DispatchError`，follower 解包后保留原 `kind`（否则会全部变成 `internal`）。注解里的 `"DispatchError"` 是字符串前向引用，因为此时该类还未定义。

### 3.2 `MiniRegistry` 与 `_walk`

```python
def _walk(schema: dict, value: Any, path: str, errs: list[str]) -> None:
    t = schema.get("type")
    type_ok = True
    if t == "object" and not isinstance(value, dict):
        type_ok = False
    elif t == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
        type_ok = False
    elif t == "string" and not isinstance(value, str):
        type_ok = False
    elif t == "array" and not isinstance(value, list):
        type_ok = False
    if not type_ok:
        errs.append(f"{path or '/'}: expected {t}, got {type(value).__name__}")
        return
    if t == "object":
        for req in schema.get("required", []):
            if req not in value:
                errs.append(f"{path}/{req}: required")
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                _walk(sub, value[k], f"{path}/{k}", errs)
```

- 为了让本节自成一体，代码没有导入第 21 节，而是内置了一个精简版：只认 `object`、`integer`、`string`、`array` 四种类型与 `required`/`properties`；`number`、`boolean`、`enum`、`pattern` 等都**不检查**（实测 `{"type": "number"}` 接受字符串）。
- 错误是字符串列表（`"/id: required"`），不是第 21 节的结构化 `ValidationError`；`dispatch` 用 `"; ".join(errs)` 拼成一条消息。
- `MiniRegistry.register` 对重名**静默覆盖**，与第 21 节"重名必须显式 override"的纪律相反；也没有名字格式检查。真实系统应直接使用第 21 节的注册表。

### 3.3 `Dispatcher.__init__`

```python
    def __init__(self, registry, *, max_attempts=3, concurrency=8,
                 cache_ttl_seconds=60.0, sleep=None) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        self.registry = registry
        self.max_attempts = max_attempts
        self._sem = asyncio.Semaphore(concurrency)
        self._inflight: dict[str, _InFlight] = {}
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = cache_ttl_seconds
        self._sleep = sleep or asyncio.sleep
```

- 参数列表中的 `*` 表示之后的参数**只能用关键字传入**，避免 `Dispatcher(reg, 3, 8)` 这种含义不明的调用。
- **可注入的 `sleep`**：测试传入一个立即返回的假 sleep，重试测试就不需要真的等待退避时间——这是讲义"tests ... do not depend on wall-clock timing"的关键（不过超时测试仍依赖真实的毫秒级 `asyncio.sleep`）。
- `asyncio.Semaphore` 在 Python 3.10+ 可以在事件循环之外创建，首次使用时才绑定循环；测试里先建 `Dispatcher` 再 `asyncio.run(...)` 依赖这一点。
- `_inflight`：key → 在途 future；`_cache`：key → (结果, 完成时间)。

### 3.4 `dispatch`：前置检查与幂等

```python
        try:
            rec = self.registry.get(name)
        except KeyError:
            return DispatchError(kind="not_found", message=f"tool {name!r}", attempts=0,
                                 jsonrpc_code=ERR_METHOD_NOT_FOUND)

        errs = self.registry.validate(name, args)
        if errs:
            return DispatchError(kind="schema", message="; ".join(errs), attempts=0,
                                 jsonrpc_code=ERR_INVALID_PARAMS)

        if budget_tool_calls_remaining is not None and budget_tool_calls_remaining <= 0:
            return DispatchError(kind="budget_exceeded", message="tool_calls remaining is 0", attempts=0)
```

- 顺序很讲究：先做**确定性、零成本**的检查（工具存在、参数合法），再考虑预算与执行；这些失败的 `attempts` 都是 0，handler 一次也没被调用。
- 预算只做"是否为 0"的检查，既不扣减，也不把重试计入（实测预算为 1 时 handler 被执行 3 次）。讲义说"The retry loop respects the budget from the harness"，代码只做到了"第一次尝试前检查"。

```python
        if idempotency_key is not None:
            now = time.monotonic()
            cached = self._cache.get(idempotency_key)
            if cached is not None and now - cached[1] < self._cache_ttl:
                return DispatchOk(result=cached[0], attempts=0)
            inflight = self._inflight.get(idempotency_key)
            if inflight is not None:
                try:
                    res = await inflight.future
                    return DispatchOk(result=res, attempts=0)
                except Exception as exc:
                    return _map_exception(exc, attempts=0)

        async with self._sem:
            return await self._run_with_retries(rec, args, timeout_ms_override, idempotency_key)
```

- `time.monotonic()`：单调时钟，不受系统时间调整影响，适合测量间隔。
- 先查**结果缓存**（60 秒内直接返回），再查**在途表**（等待同一个 future）。复用结果时 `attempts=0`，表示"本次没有执行"。
- follower 等待失败时，`_map_exception` 会从 `_DispatchedError` 中还原 leader 的 `kind` 与 `attempts`——所以失败时 follower 的 `attempts` 是 leader 的次数，成功时却是 0，两者不一致。
- **竞态**：在途登记发生在 `_run_with_retries` 内部（拿到信号量之后），检查却在等待信号量之前。信号量被占满时，两个相同 key 的调用都会通过检查、排队、各执行一次（实测 handler 被调用 2 次）。修复是把登记移到 `async with self._sem` 之前（测验 Q9 有实测通过的改法）。
- 缓存只在读取时判断过期，从不删除旧条目（实测 `cache_ttl_seconds=0` 下 100 个 key 全部留在 `_cache` 中），长期运行会持续增长。失败结果不缓存。

### 3.5 `_run_with_retries`：重试循环

```python
        timeout_ms = timeout_override if timeout_override is not None else rec.timeout_ms
        timeout_s = timeout_ms / 1000.0
        attempt = 0
        last_error: DispatchError | None = None

        loop = asyncio.get_running_loop()
        future: asyncio.Future | None = None
        if idempotency_key is not None:
            future = loop.create_future()
            self._inflight[idempotency_key] = _InFlight(future=future, started_at=time.monotonic())
```

- 超时优先用单次覆盖值，否则用注册记录里的 `timeout_ms`（讲义："The dispatcher overrides it from a per-call override"）。
- `loop.create_future()` 创建一个"空的承诺"，leader 将来通过 `set_result` / `set_exception` 填充，follower `await` 它。

```python
        try:
            while attempt < self.max_attempts:
                attempt += 1
                try:
                    coro = _invoke(rec.handler, args)
                    result = await asyncio.wait_for(coro, timeout=timeout_s)
                except asyncio.TimeoutError:
                    last_error = DispatchError(kind="timeout", message=f"timeout after {timeout_ms}ms",
                                               attempts=attempt)
                    if not rec.idempotent:
                        break
                    if attempt >= self.max_attempts:
                        break
                    await self._sleep(_backoff(attempt))
                    continue
                except TransientError as exc:
                    last_error = DispatchError(kind="transient", message=str(exc), attempts=attempt)
                    if attempt >= self.max_attempts:
                        break
                    await self._sleep(_backoff(attempt))
                    continue
                except Exception as exc:
                    err = _map_exception(exc, attempts=attempt)
                    if future is not None and not future.done():
                        future.set_exception(_DispatchedError(err))
                    return err
                if future is not None and not future.done():
                    future.set_result(result)
                if idempotency_key is not None:
                    self._cache[idempotency_key] = (result, time.monotonic())
                return DispatchOk(result=result, attempts=attempt)

            assert last_error is not None
            if future is not None and not future.done():
                future.set_exception(_DispatchedError(last_error))
            return last_error
        finally:
            if idempotency_key is not None:
                self._inflight.pop(idempotency_key, None)
```

逐分支说明：

| 情况 | 行为 | 返回 |
|------|------|------|
| 成功 | 填充 future、写缓存 | `DispatchOk(result, attempts=第几次)` |
| 超时 + 非幂等 | 立即 `break` | `timeout`，attempts=1 |
| 超时 + 幂等 + 还有次数 | 退避后 `continue` | — |
| `TransientError` + 还有次数 | 退避后 `continue`（**不看幂等标志**） | — |
| 次数用完 | 跳出循环，future 设异常 | 最后一次的 `timeout`/`transient` |
| 其他异常 | 映射为 `internal`，不重试 | `internal`，`-32603` |

- `asyncio.TimeoutError` 在 Python 3.11+ 就是内置 `TimeoutError` 的别名。
- `wait_for` 超时会**取消**内部任务；但取消是协作式的，只在 handler `await` 时生效。同步阻塞 handler（如 `time.sleep(0.2)`）会占住事件循环，超时根本无法触发，实测返回 `DispatchOk("late")`，耗时 0.2 秒。
- `while ... else` 没有使用；循环正常结束意味着"次数用完"，`assert last_error is not None` 是写给类型检查器和读者的不变量。
- `finally` 只删除在途登记。若本任务被外部取消（`CancelledError` 是 `BaseException`，不会被 `except Exception` 捕获），future 永远不会被填充，等待它的 follower 将**永久挂起**（实测）。
- 无 follower 时，`set_exception` 设置的异常没人读取，垃圾回收时 asyncio 打印 `Future exception was never retrieved`（实测）。
- 退避期间仍持有信号量，重试中的调用会占住并发名额。

### 3.6 `_invoke`、`_backoff`、`_map_exception`

```python
async def _invoke(handler: Callable[..., Any], args: dict) -> Any:
    if inspect.iscoroutinefunction(handler):
        return await handler(**args)
    result = handler(**args)
    if inspect.isawaitable(result):
        return await result
    return result
```

- 统一三种 handler：`async def`、普通函数、返回 awaitable 的普通函数（如返回 `asyncio.Future`）。
- `**args` 把字典展开为关键字参数，因此 schema 允许、但 handler 签名不接受的额外键会抛 `TypeError`，最终被归为 `internal`（实测 `{"id": 1, "extra": 2}` → `internal`、`-32603`），而它本应是参数错误。

```python
def _backoff(attempt: int) -> float:
    base = 0.1 * (4 ** (attempt - 1))
    return base * (1 + random.random() * 0.5)
```

- 第 n 次失败后等待 `0.1 × 4^(n−1)` 秒，再乘以 `[1, 1.5)` 的抖动：n=1 → [0.1, 0.15)，n=2 → [0.4, 0.6)。与讲义表格一致。
- 使用全局 `random`，没有固定种子；测试通过注入假 `sleep` 回避了随机性。

```python
def _map_exception(exc: Exception, attempts: int) -> DispatchError:
    if isinstance(exc, _DispatchedError):
        original = exc.error
        return DispatchError(kind=original.kind, message=original.message,
                             attempts=original.attempts, jsonrpc_code=original.jsonrpc_code)
    return DispatchError(kind="internal", message=f"{type(exc).__name__}: {exc}", attempts=attempts)
```

- 两种来源：follower 拿到的包装异常（还原原始错误的副本），以及 handler 抛出的普通异常（归为 `internal`，消息带类名）。

### 3.7 `gather_bounded` 与 `_demo`

```python
    async def gather_bounded(self, calls: Iterable[tuple[str, dict]]) -> list[DispatchOk | DispatchError]:
        return await asyncio.gather(*(self.dispatch(n, a) for n, a in calls))
```

- 并发上限其实由 `dispatch` 内部的信号量保证，这里只是 `gather` 的薄包装；它不支持传入每个调用的幂等键或超时覆盖。`gather` 返回的结果顺序与输入一致。

```python
    out_retry = await disp.dispatch("fetch_user", {"id": 42})    # 第 1 次 Transient，第 2 次成功
    out_timeout = await disp.dispatch("slow", {"n": 1})           # 10ms 超时，handler 睡 50ms
    out_schema = await disp.dispatch("fetch_user", {"id": "x"})   # 类型错误
    out_missing = await disp.dispatch("does_not_exist", {})       # 未注册
    out_ok = await disp.dispatch("noop", {})                      # 同步 lambda
    a, b = await asyncio.gather(
        disp.dispatch("noop", {}, idempotency_key="k1"),
        disp.dispatch("noop", {}, idempotency_key="k1"),
    )
```

- 演示没有注入假 `sleep`，所以 `fetch_user` 与 `slow` 的重试会真的等待退避时间。
- `getattr(out, "attempts", None)`：结果可能是两种类型之一，用 `getattr` 带默认值安全地取字段。
- 幂等对：`noop` 是同步 lambda，第一个调用在让出事件循环之前就执行完并写入缓存，第二个调用命中的是**结果缓存**（实测其 `attempts=0`），并没有演示"等待在途 future"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 返回 `DispatchError` 而不是抛出 | 循环可以统一处理结果，不必层层 `try` | 调用方必须检查类型 |
| 先校验、后执行 | 确定性错误零成本、不重试 | 内置 `_walk` 太简陋；应复用第 21 节注册表 |
| 只重试 timeout（幂等）与 transient | 避免对确定性错误和非幂等写操作重试 | `TransientError` 不检查幂等标志，依赖 handler 自律 |
| 指数退避 + 抖动，次数上限 3 | 给下游恢复时间，打散重试 | 应有整体 deadline，退避期间释放信号量 |
| 可注入 `sleep` | 测试快且确定 | 超时测试仍依赖真实时间 |
| 进程内在途表 + 60 秒缓存 | 实现简单 | 信号量饱和时竞态、leader 取消时挂起、缓存不清理、不跨进程；生产需后端幂等 |
| `asyncio.wait_for` 超时 | 标准库即可 | 管不住同步阻塞 handler；需线程/子进程 |
| 全局信号量 | 一行代码限制扇出 | 应按后端分级限流，并加熔断器（讲义 Going further） |
| 预算只检查一次 | 简单 | 应每次尝试扣减、原子预留 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `async def` / `await` | `async def dispatch(...)`、`await asyncio.wait_for(...)` | 定义与等待协程；`await` 处可能让出事件循环 |
| `asyncio.run` | `asyncio.run(_demo())` | 创建事件循环运行顶层协程 |
| `asyncio.gather` | `await asyncio.gather(*(self.dispatch(n, a) for n, a in calls))` | 并发运行多个协程，结果按输入顺序返回 |
| `asyncio.wait_for` | `await asyncio.wait_for(coro, timeout=timeout_s)` | 超时则取消并抛 `TimeoutError` |
| `asyncio.Semaphore` + `async with` | `async with self._sem:` | 异步上下文管理器，进入时获取、退出时释放 |
| Future | `loop.create_future()`、`future.set_result(...)`、`future.set_exception(...)` | 手动填充的"承诺"，可被多个协程 `await` |
| `asyncio.get_running_loop()` | `_run_with_retries` 中 | 获取当前运行的事件循环 |
| `inspect.iscoroutinefunction` / `isawaitable` | `_invoke` 中 | 区分同步与异步 handler |
| `**kwargs` 展开 | `handler(**args)` | 字典展开为关键字参数 |
| 仅关键字参数 `*` | `def __init__(self, registry, *, max_attempts=3, ...)` | `*` 之后的参数必须以 `name=value` 形式传入 |
| dataclass 继承 Exception | `@dataclass class DispatchError(Exception)` + `__post_init__` | dataclass 生成 `__init__` 后再手动初始化异常基类 |
| 字符串前向引用 | `def __init__(self, error: "DispatchError")` | 引用尚未定义的类 |
| `try / except / finally` | `_run_with_retries` | `finally` 无论成功、失败、取消都会执行 |
| `while` + `continue` / `break` | 重试循环 | `continue` 进入下一次尝试，`break` 放弃 |
| `assert` | `assert last_error is not None` | 声明不变量 |
| `time.monotonic()` | 缓存时间戳 | 单调时钟，适合计算间隔 |
| `random.random()` | `_backoff` 中 | `[0, 1)` 均匀随机数 |
| `getattr(obj, name, default)` | `getattr(out_retry, "attempts", None)` | 属性不存在时返回默认值 |
| `Awaitable` / `Callable` 类型 | `sleep: Callable[[float], Awaitable[None]] | None` | 描述"接收 float、返回可等待对象"的函数 |
| `x or default` | `self._sleep = sleep or asyncio.sleep` | 未注入时使用默认实现 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，`time` 统计约 0.96 秒）：

```text
{
  "retry_then_success": {"attempts": 2, "ok": true},
  "timeout": {"kind": "timeout"},
  "schema": {"kind": "schema"},
  "missing": {"kind": "not_found"},
  "happy": {"result": "ok"},
  "idempotency_pair": [true, true]
}
```

（原输出为多行缩进 JSON，这里压缩了空白。）

逐项解读：

- **retry_then_success**：`flaky_fetch` 第 1 次抛 `TransientError("upstream not ready")`，等待 `_backoff(1)` ≈ 0.1–0.15 秒后第 2 次成功，`attempts=2`。
- **timeout**：`slow` 每次睡 0.05 秒，超时 0.01 秒；幂等，所以重试到第 3 次仍超时，返回 `timeout`。期间真实等待 `_backoff(1) + _backoff(2)` ≈ 0.5–0.75 秒——这就是演示需要约 1 秒的原因。报告里只打印了 `kind`，没有打印 `attempts`（为 3）。
- **schema**：`{"id": "x"}` 不是整数，handler 不执行，`attempts=0`、`-32602`。
- **missing**：未注册的工具 → `not_found`、`-32601`。
- **happy**：同步 lambda 返回 `"ok"`，`_invoke` 统一处理了同步 handler。
- **idempotency_pair**：两个结果都是 `DispatchOk`；第二个命中结果缓存（`attempts=0`）。注意报告没有统计 handler 被调用的次数，所以它并不能证明"只执行了一次"。

额外边界实测（临时脚本，不修改源码）：

| 场景 | 结果 |
|------|------|
| `concurrency=1` 且信号量被占用，两个相同 key 的调用 | handler 执行 **2** 次，结果分别为 1 和 2（去重失效） |
| 信号量空闲，两个相同 key 的异步调用 | handler 执行 1 次，第二个 `attempts=0` |
| 同步 `time.sleep(0.2)`，超时 10ms | `DispatchOk("late")`，耗时 0.201 秒（超时无效） |
| 非幂等工具连续抛 `TransientError` | 仍执行 3 次，返回 `transient` |
| leader 被 `cancel()`，follower 在等待 | follower 永久挂起（0.3 秒超时探测） |
| 参数多出 handler 不接受的键 | `internal`、`-32603`（`TypeError`） |
| `{"type": "number"}` 收到字符串 | 通过校验，返回 `DispatchOk` |
| `cache_ttl_seconds=0`，100 个不同 key | `_cache` 中留下 100 条 |
| 带 key 的调用失败且无 follower | 打印 `Future exception was never retrieved` |
| `budget_tool_calls_remaining=1`，持续 Transient | handler 执行 3 次 |
| `hash({"a": 1})`（讲义的 key 生成式） | `TypeError: unhashable type: 'dict'` |

把幂等登记移到信号量之前、在 `finally` 中给未完成的 future 设置异常、为 future 添加读取异常的回调后（在副本上实测），前两个问题消失，原 12 个测试仍全部通过。

---

## 7. 动手改一改

1. **修复去重竞态**：把 future 的创建与 `_inflight` 登记移到 `async with self._sem` 之前，补一个"`concurrency=1`、信号量被占用时相同 key 只执行一次"的测试（测验 Q9）。
2. **leader 取消时的收尾**：在 `finally` 中为未完成的 future 设置 `_DispatchedError`，follower 使用 `asyncio.shield`；补"leader 取消后 follower 得到错误而不是挂起"的测试（测验 Q10）。
3. **真正的超时**：同步 handler 改用 `asyncio.to_thread` 执行；再写一个用子进程执行并在超时后终止的版本，比较两者在"超时后副作用是否仍会发生"上的区别。
4. **预算与 deadline**：让每次尝试扣减预算（通过回调或传入可变计数器），并增加 `deadline` 参数：退避前若剩余时间不足以完成下一次尝试，直接返回 `timeout`。
5. **熔断器**：为每个工具记录最近窗口内的失败次数，超过阈值后在冷却期内直接返回 `kind="circuit_open"`（讲义 Going further），并为它补测试。
6. **稳定的幂等键与缓存清理**：实现基于 `json.dumps(sort_keys=True)` + `sha256` 的 key 生成函数（测验 Q12）；在写缓存时顺带清理过期条目，或改用有上限的 LRU。

---

## 8. 常见坑

- **以为 `wait_for` 一定能打断 handler**：同步阻塞代码、吞掉 `CancelledError` 的代码都会让超时失效。
- **超时后重试非幂等操作**：可能重复写入或重复扣款。
- **把所有异常都重试**：确定性错误重试只会浪费预算和时间。
- **重试没有抖动**：大量客户端同步重试形成风暴。
- **用 `hash(args)` 生成幂等键**：字典不可哈希，字符串哈希又是进程随机化的。
- **"检查在途"与"登记在途"之间有 `await`**：中间任何让出点都会产生竞态。
- **忘记处理 leader 的取消**：follower 永久等待。
- **在测试中依赖真实的退避时间**：测试变慢且不稳定；注入假 `sleep`。
- **退避期间仍持有信号量**：重试中的调用会挤占其他调用的并发名额。

---

## 9. 测试在验证什么

`tests/test_dispatcher.py` 共 12 个 `unittest` 测试，分 6 组。辅助函数 `run(coro)` 用 `asyncio.run` 执行协程；`_registry_with(name, handler, **opts)` 注册一个 schema 为空对象的工具。重试相关测试注入立即返回的 `fake_sleep`，避免真实退避等待。在 `code/` 下运行 `python -m pytest -q`、`python -m unittest discover -s tests` 或 `python tests/test_dispatcher.py`。

| 测试 | 验证的性质 |
|------|-----------|
| **TestSchemaPath** | |
| `test_unknown_tool` | 未注册工具 → `not_found`、`-32601` |
| `test_schema_failure_returns_invalid_params` | 缺必需参数、类型错误 → `schema`、`-32602` |
| `test_schema_error_does_not_retry` | schema 错误时 handler 一次都不执行 |
| **TestTimeout** | |
| `test_timeout_idempotent_retries` | 幂等工具 5ms 超时、handler 睡 50ms → `timeout`，`attempts=3`，handler 执行 3 次 |
| `test_timeout_non_idempotent_no_retry` | 非幂等工具超时 → handler 只执行 1 次 |
| **TestRetry** | |
| `test_transient_retries_until_success` | 第 1 次 Transient、第 2 次成功 → `DispatchOk`，`attempts=2` |
| `test_transient_exhausts_attempts` | `max_attempts=2` 且始终 Transient → `transient`，`attempts=2` |
| `test_random_exception_no_retry` | `RuntimeError` → `internal`，只执行 1 次 |
| **TestIdempotency** | |
| `test_inflight_dedupe` | 两个相同 key 的调用（第二个在第一个挂起时发起）→ handler 只执行 1 次，结果相同 |
| `test_recent_cache_hit` | 顺序发起两次相同 key 的调用 → 第二次命中缓存，handler 只执行 1 次 |
| **TestConcurrency** | |
| `test_semaphore_bounds_inflight` | 20 个调用、`concurrency=3` → 同时运行的 handler 峰值不超过 3 |
| **TestBudget** | |
| `test_zero_budget_fails_fast` | `budget_tool_calls_remaining=0` → `budget_exceeded` |

实际运行结果（`python3 -m pytest -q`）：

```text
............                                                             [100%]
12 passed in 0.12s
```

测试的盲区：

- `test_inflight_dedupe` 中信号量是空闲的，没有覆盖"信号量饱和时去重失效"的竞态；
- 没有测试 leader 被取消、follower 等待 leader 失败、`Future exception was never retrieved`；
- 没有测试同步阻塞 handler 的超时、非幂等工具上的 `TransientError`、预算随重试扣减；
- 讲义说测试使用 `Counter` 计数且不依赖真实时间，实际用的是普通字典计数，超时测试和并发测试仍依赖毫秒级的真实 `asyncio.sleep`。
