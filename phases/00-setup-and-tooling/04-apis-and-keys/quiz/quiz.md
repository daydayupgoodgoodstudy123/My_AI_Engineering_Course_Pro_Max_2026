# 测验 · APIs 与密钥（APIs & Keys）

> **阶段 00 · 环境搭建与工具 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/first_api_call.py](../code/first_api_call.py) ｜ 代码讲解：[code/first_api_call.讲解.md](../code/first_api_call.讲解.md)
>
> **用法**：学完讲义、跑过 `first_api_call.py`（有没有 API key 都可以先跑一次）后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | API 调用的四要素 | endpoint（URL）、API key（认证）、请求体（你要什么）、响应体（返回 JSON） |
| 2 | 密钥绝不写进代码 | 用环境变量 `export ANTHROPIC_API_KEY=...`，或写在 `.env` 里并把 `.env` 加入 `.gitignore` |
| 3 | SDK 自动读环境变量 | `anthropic.Anthropic()` 不传参数时从 `ANTHROPIC_API_KEY` 读密钥；它**不会**自动读取 `.env` 文件 |
| 4 | 原始 HTTP 请求 | `POST https://api.anthropic.com/v1/messages`，请求头 `x-api-key`、`anthropic-version: 2023-06-01`、`Content-Type: application/json` |
| 5 | 请求体结构 | `model`、`max_tokens`、`messages=[{"role": "user", "content": "..."}]` |
| 6 | 响应体结构 | `content` 是内容块列表，文本在 `content[0].text`；`usage` 里有 `input_tokens` / `output_tokens` |
| 7 | 用环境变量选模型 | `os.environ.get("LLM_MODEL", "claude-sonnet-5")`：不改代码就能换模型，未设置时用默认别名 |
| 8 | Token 是计费单位 | 输入与输出 token **分别计数、分别计费** |
| 9 | 常见错误码 | 401 密钥错误/缺失、403 无权限、400 请求格式错、429 限流（等待后重试）、5xx 服务端问题 |
| 10 | SDK vs 原始 HTTP | SDK 是在 HTTP 之上的封装；理解原始请求有助于调试 |

### 核心技能（能动手做到）

- [ ] 用 `export` 设置 `ANTHROPIC_API_KEY`，并用 `echo $ANTHROPIC_API_KEY | head -c 10` 只看前缀确认已设置（不要把完整密钥打印到终端或日志）
- [ ] 写一个包含 `.env` 的 `.gitignore`，并用 `git check-ignore -v .env` 验证
- [ ] 在没有 SDK、没有密钥的情况下运行 `first_api_call.py`，解释每一行输出
- [ ] 用标准库 `urllib` 发出一次 Messages API 请求，并从响应 JSON 中取出文本和 token 用量
- [ ] 故意用错误的密钥调用，读懂 401 错误信息；用 `urllib.error.HTTPError` 打印状态码和错误响应体
- [ ] 为 429 / 5xx 实现带指数退避的重试

---

## 二、基础自测（选择题）

**Q1.** 直接用 HTTP 调用 Anthropic Messages API 时，API key 放在哪个请求头里？

- A. `Authorization: Bearer sk-ant-...`
- B. `Content-Type: application/json`
- C. `anthropic-version: 2023-06-01`
- D. `x-api-key: sk-ant-...`

**Q2.** 你在项目根目录创建了 `.env` 文件，里面写着 `ANTHROPIC_API_KEY=sk-ant-...`，但**没有** `export`，也没有用任何 dotenv 库。运行 `python first_api_call.py`，原始 HTTP 部分会打印：

- A. 模型的回答
- B. `Set ANTHROPIC_API_KEY environment variable first`
- C. `HTTP Error 401: Unauthorized`
- D. `Install the SDK: pip install anthropic`

**Q3.** 请求频繁时 API 返回 HTTP 429，正确的理解和做法是：

- A. 密钥已被永久吊销，需要换新账号
- B. 触发了限流，应等待一段时间后重试（通常用指数退避）
- C. 请求体格式错误，需要检查 JSON
- D. 服务器宕机，与你无关

**Q4.** 关于 token 计费，讲义的说法是：

- A. 只按输出 token 计费
- B. 按请求次数计费，与 token 无关
- C. 输入 token 和输出 token 分别计数、分别计费
- D. 输入输出 token 合并按字数计费

**Q5.** 代码中 `MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-5")` 这样写的主要好处是：

- A. 让程序运行得更快
- B. 不改代码就能通过环境变量切换模型，未设置时使用默认别名
- C. 让 API key 更安全
- D. 让 SDK 自动选择最便宜的模型

**Q6.** 请求返回 400 Bad Request，最可能的原因是：

- A. 网络断开
- B. API key 错误
- C. 请求体有问题，例如缺少必填字段 `max_tokens`、模型名拼错、消息格式不对
- D. 请求太频繁

**Q7.** 讲义中 "Streaming（流式输出）" 指的是：

- A. 把多个请求合并成一个批量请求
- B. 模型边生成边返回，不必等完整结果
- C. 把 API key 加密后传输
- D. 把响应压缩后再返回

---

## 三、动手 / 代码题

**Q8.**（预测输出 + 找 bug）在一台**已经安装了 `anthropic` SDK、但没有设置 `ANTHROPIC_API_KEY`** 的机器上运行 `python first_api_call.py`。下面是 `__main__` 部分：

```python
if __name__ == "__main__":
    print("=== API Calls ===\n")
    print("1. Using the SDK:")
    call_with_sdk()
    print("\n2. Using raw HTTP:")
    call_raw_http()
```

(a) 会输出什么？会不会打印 `Set ANTHROPIC_API_KEY environment variable first`？
(b) 这暴露了 `call_with_sdk` 的什么问题？请给出一个最小修复。

**Q9.**（补全代码）`call_raw_http` 在密钥错误、网络断开时会直接抛异常崩溃，也没有设置超时。请改写它的请求部分：(1) 设置 30 秒超时；(2) 捕获 `urllib.error.HTTPError`，打印状态码和服务器返回的错误响应体；(3) 捕获 `urllib.error.URLError`，打印网络错误原因。

**Q10.**（扩展）写一个函数 `post_with_retry(req, max_retries=3)`：遇到 429 或 5xx 时按 1、2、4 秒指数退避重试（如果响应头里有 `retry-after` 则优先使用它），其他 4xx 错误立即抛出；成功时返回解析后的 JSON。并说明为什么 401 不应该重试。

---

## 四、面试高频题

**Q11.**（基础必考）在本地开发和生产环境中，你分别如何管理 LLM API 密钥？说说你见过或想到的反模式。

**Q12.**（原理深挖）官方 SDK 在原始 HTTP 之上帮你做了哪些事？什么时候你会选择绕过 SDK 直接发 HTTP？

**Q13.**（工程实践）你的 LLM 应用上线后经常遇到 429 和偶发的 5xx，你会如何设计重试与限流策略？

**Q14.**（场景设计）产品要求同时支持 Anthropic 和 OpenAI，并能随时切换或做降级。你会如何设计这一层？

**Q15.**（追问型）"`response.content[0].text` 这种写法在生产里有什么隐患？你如何统计和控制一次调用的成本？"

---

## 五、参考答案与解析

### Q1 — 答案：D

Anthropic 的 API 用 `x-api-key` 头携带密钥，而不是很多 API 常用的 `Authorization: Bearer ...`。`anthropic-version` 指定 API 版本，`Content-Type` 声明请求体是 JSON。这三个头在本节代码里都出现了。

### Q2 — 答案：B

`.env` 只是一个普通文本文件。`first_api_call.py` 用 `os.environ.get("ANTHROPIC_API_KEY")` 读取**进程环境变量**，并不会去解析 `.env`；SDK 也一样只读环境变量。所以密钥为空，打印 `Set ANTHROPIC_API_KEY environment variable first`。要让 `.env` 生效，可以在 shell 里 `set -a; source .env; set +a`，或在代码里用 `python-dotenv` 的 `load_dotenv()`。（对照：本节的 TypeScript 版自带一个最小 `.env` 解析器，Python 版没有。）

### Q3 — 答案：B

429 Too Many Requests 是限流，是用来防止滥用、保证公平使用的。正确做法是等待后重试，通常配合指数退避；A 的"永久吊销"、D 的"服务器宕机"（那是 5xx）都不对；C 对应的是 400。

### Q4 — 答案：C

讲义 Key Terms：在 API 语境下，token 是计费单位，输入与输出 token 分别计数和计费。代码也分别打印了 `usage.input_tokens` 和 `usage.output_tokens`。

### Q5 — 答案：B

`os.environ.get(key, default)` 在变量不存在时返回默认值，不会抛 `KeyError`。这样换模型只需要 `export LLM_MODEL=...`，代码无需修改，也便于在不同环境（开发/测试/生产）使用不同模型。它与密钥安全无关（C 错）。

### Q6 — 答案：C

课程配套的排错提示词写明：400 表示请求体格式有误，检查必填字段、模型名拼写和消息格式。A 通常表现为连接错误/超时，B 是 401，D 是 429。

### Q7 — 答案：B

讲义解释：streaming 是"逐步拿到响应，而不是等待完整响应"。用户体验上可以更早看到内容；排错提示词还提到，超时问题可以通过减小 `max_tokens` 或改用流式来缓解。

### Q8 — 参考答案

(a) 输出（以 anthropic SDK 1.13.0 实测，报错文字随版本可能不同）：

```text
=== API Calls ===

1. Using the SDK:
Traceback (most recent call last):
  ...
TypeError: "Could not resolve authentication method. Expected one of api_key, auth_token, or credentials to be set. ..."
```

**不会**打印 `2. Using raw HTTP:`，更不会打印 `Set ANTHROPIC_API_KEY environment variable first`——SDK 那一步抛出的异常没有被捕获，整个脚本以退出码 1 终止，后面的代码根本没机会执行。（对比：没装 SDK 时两段都会运行，各自打印一行提示。）

(b) 问题：`call_with_sdk` 只处理了"SDK 没安装"，没有处理"没有密钥"和"调用失败"，与 `call_raw_http` 的防御程度不一致；一个函数的异常让另一个演示也跑不了。

最小修复（在创建客户端之前检查密钥，并兜住 SDK 的异常）：

```python
def call_with_sdk():
    try:
        import anthropic
    except ImportError:
        print("Install the SDK: pip install anthropic")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY environment variable first")
        return

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": "What is a neural network in one sentence?"}]
        )
    except anthropic.APIError as exc:
        print(f"SDK call failed: {type(exc).__name__}: {exc}")
        return
    print(f"SDK response: {response.content[0].text}")
    print(f"Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
```

`anthropic.APIError` 是 SDK 中 API 相关错误（如 `AuthenticationError`、`RateLimitError`、`APIConnectionError`）的公共基类。

### Q9 — 参考答案

```python
import json
import os
import urllib.error
import urllib.request

MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-5")


def call_raw_http():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable first")
        return

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

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as exc:          # 服务器返回了 4xx/5xx
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {detail}")
        return
    except urllib.error.URLError as exc:           # DNS 失败、连接被拒、超时等
        print(f"Network error: {exc.reason}")
        return

    print(f"Raw HTTP response: {result['content'][0]['text']}")
    print(f"Tokens used: {result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out")
```

要点：
- **先捕获 `HTTPError` 再捕获 `URLError`**：`HTTPError` 是 `URLError` 的子类，顺序反了子类分支永远不会执行。
- `HTTPError` 对象本身可以 `.read()` 出服务器返回的错误 JSON，里面通常有错误类型和说明，这是调试 401/400 的关键信息——原代码直接崩溃时这些信息只会出现在异常栈里。
- `urlopen` 默认没有超时，网络异常时可能长时间卡住；生产代码一定要显式设置。
- 打印错误时**不要**把请求头（含密钥）一起打出来。

### Q10 — 参考答案

```python
import json
import time
import urllib.error
import urllib.request

RETRYABLE = {429, 500, 502, 503, 504}


def post_with_retry(req, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE or attempt == max_retries:
                raise
            retry_after = exc.headers.get("retry-after")
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            print(f"HTTP {exc.code}, retry {attempt + 1}/{max_retries} in {delay:.0f}s")
            time.sleep(delay)
```

要点：
- 退避时间 `2 ** attempt` 依次为 1、2、4 秒；生产中还会加随机抖动（jitter），避免大量客户端在同一时刻一起重试。
- 服务器给了 `retry-after` 就听服务器的。
- **401 不该重试**：密钥错误是确定性的，重试一百次也是 401，只会白白浪费时间并可能触发更严格的风控。同理 400（请求体错误）、403（无权限）都应立即失败并修正请求。
- 只重试"暂时性"错误：限流（429）和服务端错误（5xx）。
- `urllib.request.Request` 对象可以被重复 `urlopen`，因为请求体是 bytes，可以多次发送。

### Q11 — 参考回答要点

- **本地开发**：环境变量或 `.env` 文件 + `.gitignore`；代码里只出现变量名（`os.environ.get("ANTHROPIC_API_KEY")`），不出现密钥值；确认密钥只看前几位（`head -c 10`）。
- **生产环境**：用云平台的密钥管理服务（Secret Manager、Vault、K8s Secret 等）在运行时注入环境变量；不同环境用不同的密钥；按最小权限分配；定期轮换；设置用量上限和告警。
- **反模式**：密钥硬编码在代码或 notebook 里；提交 `.env`；把密钥写进前端/移动端代码（任何用户都能拿到）；在日志、错误信息、异常栈里打印完整请求头；多个服务共用一个密钥，出事后无法定位和单独吊销。
- **泄露后**：第一时间吊销并轮换，再清理历史（见第 02 节）。
- **加分点**：前端需要调用 LLM 时，应该经过自己的后端代理，由后端持有密钥并做鉴权与限流。

### Q12 — 参考回答要点

- **SDK 做的事**：
  - 从环境变量读取密钥并注入认证头、加上 API 版本头；
  - 把参数序列化为 JSON、把响应解析为带类型的对象（`response.content[0].text` 而不是 `result["content"][0]["text"]`）；
  - 把 HTTP 状态码映射为具体异常类（如 `AuthenticationError`、`RateLimitError`）；
  - 内置超时与自动重试（例如 Anthropic Python SDK 默认会对连接错误、429、5xx 等重试 2 次）；
  - 流式输出的事件解析等。
- **何时用原始 HTTP**：调试（确认到底发出了什么、收到了什么）；运行环境装不了 SDK 或语言没有官方 SDK；需要访问 SDK 尚未支持的新功能；追求极少依赖。讲义原话："这就是 SDK 在底层做的事，理解原始 HTTP 调用有助于调试。"
- **加分点**：提到可以用 `curl` 复现请求，与 SDK 行为对比来定位问题。
- **常见误区**：认为 SDK 和 HTTP 是两种"不同的 API"——它们访问的是同一个 endpoint。

### Q13 — 参考回答要点

- **区分错误类型**：429、5xx、连接错误/超时是暂时性的，可重试；400/401/403 是确定性的，不重试。
- **重试策略**：指数退避 + 随机抖动；遵守 `retry-after`；设置最大重试次数与总超时预算，避免请求堆积。
- **从源头降速**：客户端并发上限（信号量）、令牌桶限速、请求排队；按 token 而不只是按请求数控制速率（很多限流同时限制每分钟请求数和每分钟 token 数）。
- **降低请求量**：缓存相同请求的结果；合并/批处理；精简 prompt。
- **降级**：主模型持续失败时切到备用模型或返回友好提示。
- **可观测性**：记录每次请求的状态码、重试次数、延迟、token 用量，设置告警。
- **加分点**：提到重试的**幂等性**——对有副作用的操作（例如 agent 调用了外部工具）重试要格外小心。

### Q14 — 参考回答要点

- **统一接口**：定义自己的 `chat(messages, model, max_tokens, ...) -> Response` 抽象，内部为每个提供商写适配器，把各家不同的 SDK、endpoint、请求/响应 schema 转换成统一格式（讲义提到：各家都是"密钥 + 模型 id"的模式，但 SDK、endpoint、schema 各不相同）。
- **配置驱动**：提供商、模型、密钥都从环境变量/配置读取，延续本节 `LLM_MODEL` 的做法，切换无需改代码。
- **降级与路由**：主提供商失败（重试耗尽、5xx）时自动切换到备用；按任务复杂度或成本路由到不同模型。
- **差异处理**：system prompt 的位置、工具调用格式、流式事件格式、token 统计方式都可能不同，需要在适配层抹平；为每个适配器写契约测试。
- **加分点**：提到业界有 AI 网关/路由层的方案，可以集中处理密钥、限流、日志和成本统计。
- **常见误区**：在业务代码各处直接调用不同厂商 SDK，导致切换时要改几十个文件。

### Q15 — 参考回答要点

- **`content[0].text` 的隐患**：`content` 是一个**内容块列表**，第一个块不一定是文本（例如启用工具调用或其他内容类型时），也可能为空；直接取下标会 `IndexError` 或 `AttributeError`/`KeyError`。稳妥的写法是遍历所有块、按 `type == "text"` 过滤后拼接。
- **成本统计**：每次响应都带 `usage.input_tokens` 和 `usage.output_tokens`（本节代码就打印了），把它们与模型 id 一起记录到日志/指标系统，按"输入单价 × 输入 token + 输出单价 × 输出 token"汇总；按用户、功能维度聚合。
- **成本控制**：设置合理的 `max_tokens` 上限；精简 prompt 和上下文；缓存重复请求；简单任务用更小的模型；设置预算告警和硬上限。
- **加分点**：指出输入 token 往往被长上下文、历史对话、RAG 检索结果撑大，是 agent 类应用成本的大头。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：Python/Node 环境与虚拟环境，用于安装 `anthropic` SDK。
- [阶段 00 · 02 Git & 协作](../../02-git-and-collaboration/docs/zh.md)：`.gitignore` 的用法，是把 `.env` 排除在版本控制之外的基础。

### 本节被哪些后续内容用到
- [阶段 11 · 01 提示工程](../../../11-llm-engineering/01-prompt-engineering/docs/zh.md)：从这里开始大量调用 LLM API。
- [阶段 11 · 11 缓存与成本](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：基于 `usage` 的成本核算与缓存优化。
- [阶段 13 · 02 函数调用深入](../../../13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md)：响应 `content` 中出现非文本内容块的典型场景。
- [阶段 13 · 03 并行与流式工具调用](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)：streaming 的完整用法。
- [阶段 14 · 01 Agent 循环](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：在循环中反复调用 API，重试与限流变得关键。
- [阶段 17 · 16 模型路由](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)、[阶段 17 · 19 AI 网关](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：多提供商切换与集中治理（Q14 的延伸）。
- [阶段 17 · 25 安全、密钥与审计](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：生产级密钥管理。

### 延伸关键词
`环境变量 / .env / python-dotenv` · `x-api-key` · `HTTP 状态码 401/403/429/5xx` · `指数退避 + jitter` · `retry-after` · `SSE 流式输出` · `Secret Manager` · `token 计费` · `AI Gateway`
