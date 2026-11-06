# 代码讲解 · first_api_call.py

> **所属小节**：阶段 00 · 环境搭建与工具 · 第 04 节 APIs 与密钥 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`export ANTHROPIC_API_KEY="sk-ant-..."`（可选 `export LLM_MODEL=<模型 id>`），然后 `python first_api_call.py`（无命令行参数） ｜ **依赖**：标准库 `os`、`json`、`urllib.request`；可选第三方包 `anthropic`（SDK 部分）；真实调用需要 **Anthropic API key 和网络**

---

## 1. 这份代码在考察什么

这份脚本用**两种方式**完成同一件事——问 Claude "用一句话解释什么是神经网络"：

1. **SDK 方式**：`anthropic.Anthropic().messages.create(...)`，几行代码搞定，看到的是封装好的对象。
2. **原始 HTTP 方式**：只用标准库 `urllib` 手动拼 URL、请求头、JSON 请求体，看到的是 API 的"真面目"。
3. **密钥从环境变量读取**：代码中没有任何密钥字面量，这是本节最重要的安全习惯。
4. **模型可配置**：`LLM_MODEL` 环境变量决定用哪个模型，默认是讲义中的不带日期的 Sonnet 别名。
5. **token 用量**：两种方式都打印 `input_tokens` / `output_tokens`，建立"API 按 token 计费"的直觉。

> 一句话：**SDK 让你写得快，原始 HTTP 让你看得懂——把两者对照着看，以后调试任何 LLM API 都不慌。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MODEL` | 模块级常量 | 从 `LLM_MODEL` 读取模型 id，未设置时用默认值 | 配置外置 |
| `call_with_sdk()` | 函数 | 用官方 Python SDK 发请求，打印回答与 token 用量 | SDK 封装 |
| `call_raw_http()` | 函数 | 用 `urllib` 手工发 POST 请求，解析 JSON | 原始 HTTP、请求/响应结构 |
| `if __name__ == "__main__":` | 入口 | 依次调用两种方式 | — |

数据流（两种方式相同）：环境变量（密钥、模型）→ 组装请求（endpoint + 认证头 + JSON 请求体）→ `POST /v1/messages` → JSON 响应 → 取出 `content[0].text` 与 `usage`。

---

## 3. 逐段精讲

### 3.1 导入与模型配置

```python
import os
import json
import urllib.request

MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-5")
```

- `os.environ` 是一个类似字典的对象，保存当前进程的环境变量。`.get(key, default)` 在变量不存在时返回默认值，不会抛 `KeyError`。
- 讲义说明：`LLM_MODEL` 用来选择 Anthropic 模型 id，默认值是**不带日期的 Sonnet 别名**。把模型 id 外置为环境变量，换模型不需要改代码。
- `MODEL` 在模块加载时计算一次，两个函数共用，保证两种方式问的是同一个模型。
- 注意 `anthropic` **没有**在顶部导入，因为它是可选依赖（见 3.2）。

### 3.2 SDK 方式

```python
def call_with_sdk():
    try:
        import anthropic
    except ImportError:
        print("Install the SDK: pip install anthropic")
        return

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": "What is a neural network in one sentence?"}]
    )
    print(f"SDK response: {response.content[0].text}")
    print(f"Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
```

- **函数内导入 + `except ImportError`**：没装 SDK 时给出安装提示并返回，而不是让整个脚本崩溃。
- `anthropic.Anthropic()` **不传任何参数**：SDK 会自动从环境变量 `ANTHROPIC_API_KEY` 读取密钥。这就是"代码里不出现密钥"的标准姿势。⚠️ SDK 只读**环境变量**，不会自动读取 `.env` 文件。
- `messages.create(...)` 的三个参数对应 Messages API 的请求体：
  - `model`：模型 id；
  - `max_tokens`：本次最多生成多少个 token（**输出上限**，也是成本上限之一）；
  - `messages`：对话列表，每条是 `{"role": ..., "content": ...}`，这里只有一条用户消息。
- 返回值是**带类型的对象**：用属性访问 `response.content[0].text`、`response.usage.input_tokens`。`content` 是"内容块"列表，纯文本问答时第一个块就是文本块。
- ⚠️ **刻意的简化（也是一个真实缺陷）**：这里只处理了"没装 SDK"，没有处理"没有密钥"和"API 报错"。实测（anthropic 1.13.0）：装了 SDK 但没设密钥时，`messages.create` 抛出 `TypeError: "Could not resolve authentication method..."`，异常没被捕获，**脚本直接终止，后面的原始 HTTP 演示也不会运行**。修复方法见测验 Q8。

### 3.3 原始 HTTP 方式：先拿密钥

```python
def call_raw_http():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable first")
        return
```

- 自己发 HTTP 时没人帮你读密钥，只能手动从环境变量取。
- `if not api_key` 同时覆盖了"变量不存在（`None`）"和"变量是空字符串"两种情况。
- 这一步做了 SDK 版本没做的**前置检查**，所以没有密钥时这里能优雅退出。

### 3.4 组装请求：URL、请求头、请求体

```python
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "What is a neural network in one sentence?"}],
    }).encode()
```

对应讲义中"每个 API 调用都有"的四要素：

| 要素 | 本代码中 |
|------|---------|
| Endpoint（URL） | `https://api.anthropic.com/v1/messages` |
| API key（认证） | 请求头 `x-api-key` |
| 请求体（你要什么） | `body`：`model` + `max_tokens` + `messages` |
| 响应体（你得到什么） | 下一节的 `result` JSON |

- `Content-Type: application/json`：告诉服务器请求体是 JSON。
- `x-api-key`：Anthropic 用这个头携带密钥，而不是很多 API 常用的 `Authorization: Bearer ...`。
- `anthropic-version: 2023-06-01`：API 版本头，让服务器按指定版本的协议解析请求。
- `json.dumps(...)` 把 Python 字典序列化成 JSON **字符串**；`.encode()` 再把字符串编码成 UTF-8 **字节**——HTTP 请求体在网络上传输的是字节，`urllib` 的 `data` 参数要求 bytes。
- 请求体与 SDK 版本的参数**一模一样**，这正是"SDK 只是 HTTP 的封装"的直接证据。

### 3.5 发送请求并解析响应

```python
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print(f"Raw HTTP response: {result['content'][0]['text']}")
        print(f"Tokens used: {result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out")
```

- `urllib.request.Request` 把 URL、请求体、请求头、方法打包成一个请求对象；`method="POST"` 显式指定方法（有 `data` 时默认也是 POST，写明更清楚）。
- `urlopen(req)` 真正发出请求，返回响应对象。用 `with` 语句保证用完后连接被关闭。
- `resp.read()` 读出响应体字节，`json.loads` 直接接受 bytes 并解析成字典。
- 与 SDK 版本对比：这里用**字典下标** `result['content'][0]['text']`，SDK 用**属性** `response.content[0].text`——数据结构完全相同，只是 SDK 把 JSON 包装成了对象。
- f-string 里用了单引号 `'content'`，因为外层是双引号。
- ⚠️ **刻意的简化**：
  - **没有错误处理**：密钥错误时服务器返回 401，`urlopen` 会抛 `urllib.error.HTTPError`（`HTTP Error 401: Unauthorized`）；网络问题抛 `URLError`。脚本会直接崩溃，服务器返回的错误详情也没被打印。
  - **没有超时**：`urlopen` 默认不设超时，网络异常时可能长时间挂起。
  - **没有重试**：429 / 5xx 这类暂时性错误不会自动重试（SDK 默认会重试）。
  - 改进写法见测验 Q9、Q10。

### 3.6 入口：两种方式依次演示

```python
if __name__ == "__main__":
    print("=== API Calls ===\n")
    print("1. Using the SDK:")
    call_with_sdk()
    print("\n2. Using raw HTTP:")
    call_raw_http()
```

- 先 SDK 后原始 HTTP，方便对比两次的回答和 token 用量（两次是独立请求，回答文字可能略有不同）。
- 两个函数**顺序执行、没有隔离**：前一个抛出未捕获异常，后一个就不会执行（见 3.2 的实测）。

### 3.7 对照：同目录下的 TypeScript 版本

同目录的 `first_api_call.ts`（不在本讲解范围内）做了两件 Python 版没做的事：自带一个最小的 `.env` 解析器（并且进程环境变量优先于文件），以及 `MOCK=1` 时返回固定的假响应、完全不联网，并在请求失败时捕获异常、以退出码 1 结束。读完 Python 版可以对照看看，作为改进 Python 版的参考。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 密钥只从环境变量读 | 代码可安全提交、共享 | 本地需要 export；生产用密钥管理服务注入 |
| `LLM_MODEL` 环境变量 + 默认值 | 不改代码即可换模型 | 默认别名可能随时间指向不同模型版本；需要稳定性时固定带日期的模型 id |
| SDK 与原始 HTTP 并列 | 对照学习：封装 vs 本质 | 实际项目选一种即可，通常用 SDK |
| 原始 HTTP 只用标准库 | 零依赖，看清每一个字节 | 生产常用 `httpx`/`requests`，支持连接池、超时、重试 |
| SDK 设为可选依赖 | 没装也能跑原始 HTTP 部分 | 但 SDK 部分缺少密钥检查，反而会让整个脚本崩溃 |
| 不做错误处理/超时/重试 | 保持最短的"happy path" | 生产必须区分 4xx/5xx、设置超时、对 429/5xx 退避重试 |
| `max_tokens=256` | 一句话回答足够，控制成本 | 按任务设定，过小会截断回答 |
| 直接取 `content[0]` | 纯文本问答时足够 | 有工具调用等其他内容块时应按 `type` 过滤 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import` 子模块 | `import urllib.request` | 导入包中的子模块，用 `urllib.request.Request` 访问 |
| 函数内导入 | `try: import anthropic` | 可选依赖的常见写法 |
| `try / except ImportError` | `except ImportError:` | 没装包时给出提示而不是崩溃 |
| 不带值的 `return` | `return` | 提前结束函数 |
| `os.environ.get` | `os.environ.get("LLM_MODEL", "claude-sonnet-5")` | 读环境变量，带默认值，不存在不报错（对比 `os.environ["X"]` 会抛 `KeyError`） |
| 真值判断 | `if not api_key:` | `None` 和空字符串都为假 |
| 字典字面量 | `headers = {"Content-Type": "application/json", ...}` | 键值对，最后一项后的逗号是合法的（方便增删行） |
| 嵌套的列表与字典 | `[{"role": "user", "content": "..."}]` | 与 JSON 结构一一对应 |
| 关键字参数 | `client.messages.create(model=MODEL, max_tokens=256, ...)` | 按名字传参，可读性好 |
| `json.dumps` / `json.loads` | `json.dumps({...})`、`json.loads(resp.read())` | Python 对象 ↔ JSON 字符串；`loads` 也接受 bytes |
| `str.encode()` | `json.dumps(...).encode()` | 字符串 → 字节（默认 UTF-8） |
| 方法链 | `json.dumps({...}).encode()` | 前一个调用的结果直接调用下一个方法 |
| 属性访问 vs 下标访问 | `response.usage.input_tokens` vs `result['usage']['input_tokens']` | SDK 对象用属性，原始 JSON 字典用下标 |
| `with` 上下文管理器 | `with urllib.request.urlopen(req) as resp:` | 离开代码块时自动关闭连接 |
| f-string 中的引号 | `f"...{result['content'][0]['text']}"` | 外层双引号，内部字典键用单引号 |
| `"\n"` 转义 | `print("\n2. Using raw HTTP:")` | 输出前先空一行 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

**实际运行 1**（在临时副本中，系统 Python 未安装 `anthropic`，且未设置 `ANTHROPIC_API_KEY`；不需要网络）：

```text
=== API Calls ===

1. Using the SDK:
Install the SDK: pip install anthropic

2. Using raw HTTP:
Set ANTHROPIC_API_KEY environment variable first
```

- SDK 部分走 `except ImportError` 分支；原始 HTTP 部分走 `if not api_key` 分支。
- 两段都优雅退出，进程退出码为 0。这是"什么都还没配"时的预期结果。

**实际运行 2**（在一个装了 `anthropic` 1.13.0 的临时虚拟环境中，仍未设置密钥）：

```text
=== API Calls ===

1. Using the SDK:
Traceback (most recent call last):
  ...
TypeError: "Could not resolve authentication method. Expected one of api_key, auth_token, or credentials to be set. Or for one of the `X-Api-Key` or `Authorization` headers to be explicitly omitted"
```

- SDK 在构造请求头时发现没有任何认证方式，抛出 `TypeError`（具体文字随 SDK 版本可能不同）。
- 异常未被捕获，**`2. Using raw HTTP:` 根本没有打印**，退出码为 1。这就是 3.2 节提到的缺陷。

**未实际运行：设置了有效密钥的真实调用**（原因：需要 API key 和网络）。预期输出结构：

```text
=== API Calls ===

1. Using the SDK:
SDK response: <一句话的回答>
Tokens used: <输入 token 数> in, <输出 token 数> out

2. Using raw HTTP:
Raw HTTP response: <一句话的回答>
Tokens used: <输入 token 数> in, <输出 token 数> out
```

- 两次的输入 token 数应该相同（同一个模型、同一条消息）；输出 token 数和回答文字可能略有差异，因为是两次独立生成。

**未实际运行：故意用错误密钥**（讲义练习 3）。预期：SDK 部分抛出 `anthropic.AuthenticationError`（401）并终止脚本；若单独运行原始 HTTP 部分，则抛出 `urllib.error.HTTPError: HTTP Error 401: Unauthorized`。

---

## 7. 动手改一改

1. **补上 SDK 的密钥检查**：在 `anthropic.Anthropic()` 之前检查 `ANTHROPIC_API_KEY`，再用 `try/except anthropic.APIError` 包住调用，让两段演示互不影响。
2. **加载 `.env`**：安装 `python-dotenv`，在文件开头 `from dotenv import load_dotenv; load_dotenv()`；或者不引入依赖，仿照 TS 版写一个 10 行的 `.env` 解析器（跳过空行和 `#` 注释，按第一个 `=` 切分，环境变量优先）。
3. **给原始 HTTP 加错误处理和超时**：捕获 `HTTPError` 并打印 `exc.code` 和 `exc.read()` 的内容，再故意用错误密钥运行，读懂服务器返回的错误 JSON。
4. **加一个 `MOCK=1` 模式**：返回一个与真实响应结构相同的假字典，让脚本在没有密钥、没有网络时也能完整演示解析逻辑。
5. **更稳的文本提取**：写 `extract_text(content_blocks)`，只拼接 `type == "text"` 的块。
6. **用 `curl` 复现同一个请求**：把 URL、三个请求头和 JSON 请求体写成一条 `curl` 命令，对比返回的 JSON 与 SDK 对象。

---

## 8. 常见坑

- **以为写了 `.env` 就生效了**：这个脚本和 SDK 都只读进程环境变量；`.env` 需要 `source` 或 dotenv 加载。
- **`.env` 没进 `.gitignore`**：一次 `git add .` 就把密钥提交了；泄露后第一件事是吊销并轮换密钥。
- **在终端/日志里打印完整密钥**：确认是否设置时只看前几位，如 `echo $ANTHROPIC_API_KEY | head -c 10`。
- **请求头写成 `Authorization: Bearer`**：Anthropic 用的是 `x-api-key`，写错会得到 401。
- **忘了 `.encode()`**：`urllib.request.Request` 的 `data` 必须是 bytes，传 str 会在发送时报 `TypeError`。
- **一个函数的异常拖垮整个脚本**：未捕获的异常会终止进程，后面的代码都不会执行；每个独立的演示/任务应各自处理异常。
