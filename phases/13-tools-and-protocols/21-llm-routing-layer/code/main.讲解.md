# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 21 节 LLM 路由层：LiteLLM、OpenRouter、Portkey ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py` ｜ **依赖**：纯标准库（`json`、`re`、`time`、`dataclasses`、`typing`），供应商全部是本地桩函数，不需要任何 API key 或网络

---

## 1. 这份代码在考察什么

这份约 150 行的代码实现了一个最小的 LLM 路由网关，覆盖讲义"Use It"列出的四个看点：

1. **`ROUTES`**：别名 → 按优先级排列的具体模型列表（fallback chain）。
2. **Fallback 循环**：供应商抛"5xx"（这里用 `RuntimeError` 模拟）时尝试下一个。
3. **成本追踪**：token 用量 × 每百万 token 单价。
4. **PII 脱敏**：转发前把 SSN、16 位卡号替换为 `[REDACTED]`。

四个场景依次演示：正常请求、主供应商宕机触发 fallback、输入含 PII、链上全部宕机。

> 一句话：**把"应用只认别名，网关负责选模型、兜底、记账、脱敏"这件事压缩成一个 `route()` 函数**。它的默认值、异常处理和消息改写都过于宽松——未知别名零成本放行、tool-calling 字段被丢弃、超时不触发 fallback——这些是测验 Q9–Q12 的重点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PRICES` | 字典常量 | 模型 → (输入单价, 输出单价)，单位：美元 / 百万 token（演示用假价格） | 价格表 |
| `OUTAGE` | 全局集合 | 被"宕机"的模型名，用于故障注入 | 故障模拟 |
| `provider_call` | 函数 | 供应商桩：宕机则抛 `RuntimeError`，否则返回 OpenAI 形状的响应 | 后端供应商 |
| `ROUTES` | 字典常量 | `smart` → 3 个模型，`fast` → 2 个模型 | 模型别名、fallback chain |
| `PII_PATTERNS` / `redact_pii` | 正则列表 / 函数 | SSN 与 16 位数字脱敏 | 网关级 guardrail |
| `Invocation` | dataclass | 一次路由调用的完整记录：尝试过的模型、token、成本、是否脱敏、响应、错误 | 请求级审计记录 |
| `route` | 函数 | 脱敏 → 取链 → 依次尝试 → 记账 | 路由核心 |
| `demo` | 函数 | 4 个场景 | 演示 |

数据流：`demo` → `route(alias, messages)` → `redact_pii` 逐条处理消息 → `ROUTES.get(alias)` 得到链 → 循环 `provider_call(model)`，失败 `continue`，成功则读 `usage`、查 `PRICES` 算成本并返回 `Invocation` → 全部失败则 `error = "all providers failed"`。

---

## 3. 逐段精讲

### 3.1 价格表与故障注入

```python
# cost per 1M tokens (input, output); fake rates for demo
PRICES = {
    "openai/gpt-4o":           (5.0, 15.0),
    "openai/gpt-4o-mini":      (0.15, 0.60),
    "anthropic/claude-sonnet": (3.0, 15.0),
    "anthropic/claude-haiku":  (0.80, 4.0),
    "google/gemini-pro":       (1.25, 5.0),
}

OUTAGE: set[str] = set()
```

- 价格以"每百万 token"计，输入、输出分开——输出通常更贵，这里 gpt-4o 输出是输入的 3 倍。注释写明是 **fake rates**，不要当作真实报价。
- 讲义开头说"Claude Sonnet costs 3x what Haiku costs"，按这张表 sonnet 与 haiku 的比值是 `3.0 / 0.80 = 15 / 4 = 3.75` 倍（已计算）——量级一致，数值不同，都是示意。
- 模型名用 `provider/model` 形式，这也是很多网关（如讲义提到的 LiteLLM、OpenRouter）表示模型的常见写法。
- `OUTAGE` 是**模块级可变全局变量**：`demo()` 在场景 4 把 `fast` 链全部加进去后没有清理，运行结束时 `OUTAGE == {'openai/gpt-4o-mini', 'anthropic/claude-haiku'}`（已实测）。

### 3.2 供应商桩 `provider_call`

```python
def provider_call(model: str, messages: list[dict]) -> dict:
    if model in OUTAGE:
        raise RuntimeError(f"simulated 5xx from {model}")
    time.sleep(0.01)
    last = messages[-1]["content"]
    out_toks = max(20, len(last) // 3)
    return {
        "id": f"resp_{model.replace('/', '_')}",
        "model": model,
        "choices": [{"message": {"role": "assistant",
                                 "content": f"[{model}] echoed: {last[:60]}"}}],
        "usage": {"prompt_tokens": len(last) // 4, "completion_tokens": out_toks},
    }
```

- 返回值模仿 OpenAI Chat Completions 响应：`id`、`model`、`choices[0].message`、`usage.prompt_tokens / completion_tokens`。网关只依赖这个统一形状，所以"翻译各家格式"在桩里被省略了。
- token 估算：输入按"4 字符 ≈ 1 token"、输出至少 20。注意只看**最后一条消息**，多轮对话的历史不计入输入 token——真实计费是整段上下文。
- 回复把最后一条消息截断到 60 个字符回显，便于观察脱敏是否生效。
- `id` 只由模型名构成，同一模型的所有响应 id 相同——演示可以，真实系统要唯一。

### 3.3 别名与 fallback chain

```python
ROUTES = {
    "smart": ["openai/gpt-4o", "anthropic/claude-sonnet", "google/gemini-pro"],
    "fast":  ["openai/gpt-4o-mini", "anthropic/claude-haiku"],
}
```

- 每条链跨越不同供应商：一个供应商整体故障时还有别的选择（技能文件："Any fallback chain with only one provider. One failure domain defeats the purpose."）。
- 链的顺序就是"静态优先级"策略。讲义列出的负载均衡、成本感知、延迟感知、任务感知策略都没有实现。
- 讲义写的是 `on 5xx: ... on 5xx: refuse`——链尾失败就拒绝，对应 `inv.error = "all providers failed"`。

### 3.4 PII 脱敏

```python
PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{16}\b"),               # credit card
]

def redact_pii(text: str) -> tuple[str, bool]:
    redacted = False
    for pat in PII_PATTERNS:
        if pat.search(text):
            text = pat.sub("[REDACTED]", text)
            redacted = True
    return text, redacted
```

- `re.compile` 预编译正则，模块加载时只编译一次。
- `\b` 是单词边界：`\d` 属于"单词字符"，所以 `"SSN123-45-6789x"` 中 SSN 前后紧贴字母，`\b` 不成立，不会匹配（已实测未脱敏）。
- 先 `search` 再 `sub` 扫描了两遍，可以用 `pat.subn(...)` 一次拿到替换次数。
- 已实测的覆盖情况：

| 输入 | 结果 | 说明 |
|------|------|------|
| `SSN 123-45-6789` | 脱敏 | 命中 SSN 正则 |
| `4111111111111111` | 脱敏 | 16 位连续数字 |
| `order 1234567890123456` | 脱敏 | **误报**：订单号 |
| `4111 1111 1111 1111` | 未脱敏 | **漏报**：带空格的卡号 |
| `ssn 123456789` | 未脱敏 | 漏报：无横线 |
| `a@b.com 555-123-4567` | 未脱敏 | 邮箱、电话不在规则中 |

- 只脱敏**输入**；讲义提到的输出过滤（"Scrub completions for leaks"）与策略拒绝没有实现。

### 3.5 `Invocation`：每次调用一条审计记录

```python
@dataclass
class Invocation:
    alias: str
    chosen_model: str = ""
    attempts: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    redacted: bool = False
    response: dict | None = None
    error: str | None = None
```

- 一次请求的所有可观测信息集中在一个对象里：用了哪个别名、尝试了哪些模型、最终选中谁、花了多少钱、是否脱敏、结果或错误。网关的成本归因、fallback 使用率告警都可以从这样的记录聚合出来。
- 缺少：每次失败的原因（`attempts` 只有模型名）、耗时、调用方身份（团队/key）、请求 id。

### 3.6 `route`：网关核心

```python
def route(alias: str, messages: list[dict]) -> Invocation:
    inv = Invocation(alias=alias)
    # redact pii on inputs
    new_msgs = []
    for m in messages:
        txt, r = redact_pii(m["content"])
        if r:
            inv.redacted = True
        new_msgs.append({"role": m["role"], "content": txt})
    chain = ROUTES.get(alias, [alias])
    for model in chain:
        inv.attempts.append(model)
        try:
            resp = provider_call(model, new_msgs)
            inv.chosen_model = model
            inv.response = resp
            u = resp["usage"]
            inv.input_tokens = u["prompt_tokens"]
            inv.output_tokens = u["completion_tokens"]
            in_rate, out_rate = PRICES.get(model, (0, 0))
            inv.cost_usd = (u["prompt_tokens"] * in_rate +
                            u["completion_tokens"] * out_rate) / 1_000_000
            return inv
        except RuntimeError as e:
            continue
    inv.error = "all providers failed"
    return inv
```

按顺序看：

1. **脱敏**在选模型之前完成——无论最终发给哪个供应商，内容都已处理。
2. **取链**：`ROUTES.get(alias, [alias])`——别名不存在时把别名本身当模型名。
3. **尝试**：先把模型加入 `attempts` 再调用，所以失败的模型也会出现在记录里。
4. **成功即返回**：读取 `usage`，按 `(输入 × 输入单价 + 输出 × 输出单价) / 10⁶` 算成本。
5. **失败**：只捕获 `RuntimeError`，丢弃异常对象，继续下一个。
6. **链尾**：全部失败时记录错误并返回（不抛异常）。

⚠️ 已实测的问题：

- **未知别名零成本放行**：`route("evil/free-model", ...)` 直接调用该"模型"，`PRICES.get` 返回 `(0, 0)`，4000 字符的请求成本记为 `$0.0`（同样请求走 `smart` 是 `$0.024995`）。成本追踪与预算可被绕过（测验 Q9）。
- **破坏 tool calling**：新消息只保留 `role` 和 `content`，`tool_calls`、`tool_call_id`、`name` 全被丢弃；`content` 为 `None`（带工具调用的 assistant 消息）或列表（多模态）时 `re.search` 抛 `TypeError`（测验 Q10）。
- **只认 `RuntimeError`**：`TimeoutError` 等其他异常直接冒出 `route()`，不会 fallback；同时 4xx 与 5xx 不分，都会 fallback（测验 Q12）。
- **无重试预算、无退避、无熔断、无超时**：讲义说"Retries count against a budget"，代码没有；宕机期间每个请求都先撞一次宕机的供应商。
- **讲义描述与实现的差距**：讲义说网关"accepts OpenAI-shaped requests, translates to per-provider stubs"，实际 `route` 接收的是 `(alias, messages)`，所有供应商共用同一个桩，没有翻译层。

### 3.7 `demo`：四个场景

```python
    print("\n--- scenario 2: openai/gpt-4o OUTAGE -> falls back to Claude ---")
    OUTAGE.add("openai/gpt-4o")
    inv = route("smart", [{"role": "user", "content": "same request"}])
    ...
    OUTAGE.clear()
    ...
    print("\n--- scenario 4: all providers down ---")
    OUTAGE.update(ROUTES["fast"])
    inv = route("fast", [{"role": "user", "content": "help"}])
```

- 场景 2 之后 `OUTAGE.clear()` 恢复；场景 4 之后**没有**恢复。
- 场景 3 用 `fast` 别名，命中 `gpt-4o-mini`。
- banner 打印 `PHASE 13 LESSON 20`，本节是第 21 节；`outputs/skill-routing-config-designer.md` 的 front matter 也写着 `lesson: 20`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 供应商为同一个桩函数 | 不需要 key 和网络 | 没有协议翻译；生产网关最复杂的部分就是各家格式（工具调用、流式事件、system prompt）的翻译 |
| 用 `RuntimeError` 代表 5xx | 演示 fallback | 无法区分可重试/不可重试；生产按状态码与异常类型分类 |
| 静态优先级链 | 最容易理解 | 无负载均衡与健康感知；生产加熔断、加权、延迟感知 |
| 未知别名回退为模型名 | 方便直接写模型名 | 绕过治理与计费；生产对未知别名 fail closed |
| 未知价格记 0 | 不报错 | 成本被低估；生产要求每个可路由模型都有价格 |
| 正则脱敏两条规则 | 简单直观 | 漏报与误报都明显；生产用正则 + 校验（如 Luhn）+ 实体识别模型，并做输出过滤 |
| 重建消息只保留 role/content | 代码短 | 丢失 tool calling 字段；生产必须透传未知字段 |
| 全局 `OUTAGE` | 演示故障注入 | 状态泄漏到后续调用；生产/测试用实例级状态 |
| token 只按最后一条消息估算 | 桩的简化 | 低估多轮对话的成本；以供应商返回的 usage 为准 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 字典字面量对齐 | `"openai/gpt-4o":           (5.0, 15.0),` | 多余空格只为对齐，可读性更好 |
| 元组值与解包 | `in_rate, out_rate = PRICES.get(model, (0, 0))` | 一次取出两个值 |
| 集合类型注解 | `OUTAGE: set[str] = set()` | 空集合必须写 `set()`，`{}` 是空字典 |
| `set.add` / `update` / `clear` | 故障注入 | 增加一个 / 合并多个 / 清空 |
| `raise RuntimeError(...)` | 模拟 5xx | 抛出异常 |
| `try/except ... continue` | fallback 循环 | 捕获后跳到下一次循环 |
| `except X as e` 未使用 `e` | `except RuntimeError as e:` | 可以写成 `except RuntimeError:`；更好的做法是记录 `e` |
| `dict.get(key, default)` | `ROUTES.get(alias, [alias])` | 缺键时的默认值（本例中的默认值正是问题所在） |
| `str.replace` | `model.replace('/', '_')` | 生成 id |
| 切片 | `last[:60]` | 截断字符串 |
| `max` | `max(20, len(last) // 3)` | 设下限 |
| 正则 `re.compile` / `search` / `sub` | `PII_PATTERNS` | 预编译、查找、替换；`\b` 单词边界、`\d{16}` 恰好 16 位数字 |
| 原始字符串 `r"..."` | `r"\b\d{3}-\d{2}-\d{4}\b"` | 反斜杠不转义，正则必备 |
| 返回元组 | `-> tuple[str, bool]` | 同时返回结果和标志 |
| `@dataclass` + `field(default_factory=list)` | `attempts: list[str] = field(default_factory=list)` | 每个实例独立的列表 |
| `X \| None` | `response: dict \| None = None` | 可选值 |
| 数字下划线 | `1_000_000` | 便于阅读 |
| f-string 格式符 | `f"${inv.cost_usd:.6f}"` | 保留 6 位小数 |
| 未使用的导入 | `json`、`Callable` | 导入了但没用到，可删除 |

---

## 6. 运行结果解读

实际运行 `python3 code/main.py`：

```text
========================================================================
PHASE 13 LESSON 20 - LLM ROUTING GATEWAY             ← 笔误，应为 21
========================================================================

--- scenario 1: smart route, primary available ---
  chosen  : openai/gpt-4o
  attempts: ['openai/gpt-4o']
  tokens  : in=2 out=20
  cost    : $0.000310
  reply   : [openai/gpt-4o] echoed: explain MCP

--- scenario 2: openai/gpt-4o OUTAGE -> falls back to Claude ---
  chosen  : anthropic/claude-sonnet
  attempts: ['openai/gpt-4o', 'anthropic/claude-sonnet']
  cost    : $0.000309

--- scenario 3: PII in input gets redacted pre-dispatch ---
  redacted: True
  reply   : [openai/gpt-4o-mini] echoed: contact me at SSN [REDACTED] please

--- scenario 4: all providers down ---
  attempts: ['openai/gpt-4o-mini', 'anthropic/claude-haiku']
  error   : all providers failed
```

逐项解读：

- **场景 1**：`"explain MCP"` 11 个字符 → 输入 `11 // 4 = 2`、输出 `max(20, 3) = 20`；成本 `(2 × 5 + 20 × 15) / 10⁶ = $0.000310`。输出 token 贡献了 300/310 的成本。
- **场景 2**：`attempts` 记下了失败的 gpt-4o 和成功的 sonnet；`gemini-pro` 没被尝试。`"same request"` 12 个字符 → 输入 3、输出 20；按 **sonnet** 的价格 `(3 × 3 + 20 × 15) / 10⁶ = $0.000309`——成本按实际服务的模型归因，这正是讲义练习 1 要确认的"cost is attributed correctly"。
- **场景 3**：供应商回显的内容里 SSN 已经是 `[REDACTED]`，证明脱敏发生在转发之前。
- **场景 4**：链上两个模型都尝试过，返回错误而不是抛异常；调用方据此决定降级或报错。
- 运行结束后 `OUTAGE` 仍包含 `fast` 链的两个模型（见 3.1）。

---

## 7. 动手改一改

1. **（练习 1）** 修正 banner；在场景 4 末尾加 `OUTAGE.clear()`；给 `Invocation` 增加 `errors: list[tuple[str, str]]`，记录每次失败的模型与原因。
2. **（治理）** 未知别名与无价格模型一律拒绝（测验 Q9），并写一个启动时自检：`ROUTES` 中每个模型都必须在 `PRICES` 中。
3. **（tool calling）** 按测验 Q10 改写脱敏循环：透传 `tool_calls`、`tool_call_id` 等字段，支持 `content` 为 `None` 或多模态列表，并对工具调用参数做脱敏。
4. **（练习 2）** 实现 SHA-256 精确缓存（测验 Q11），对同一请求调用 10 次，确认成本从 `$0.0034` 降到 `$0.00034`。
5. **（练习 3）** 加一个简单的任务分类器：以 `code` 开头的 prompt 走 `smart`，以 `summarize` 开头的走 `fast`，其余走默认别名。
6. **（练习 4 进阶）** 为每个团队设置月度预算：请求前按 `max_tokens` 预扣最大成本，完成后按实际 usage 结算；加入错误分类、熔断器和"最多尝试 2 个模型"的重试预算（测验 Q12），统计 fallback 使用率。

---

## 8. 常见坑

- **未知别名默认放行**：任何 `dict.get(..., 默认值)` 在安全或计费路径上都要问一句"默认值会不会绕过控制"。
- **未知价格当 0**：成本报表看起来很好，实际在超支。
- **网关改写消息时丢字段**：tool calling、多模态、`name` 等字段必须原样透传。
- **把所有错误都 fallback**：4xx 换供应商只会重复失败；反过来，只捕获一种异常会让超时直接失败。
- **没有重试预算和熔断**：大面积故障时请求数和延迟成倍增加。
- **只脱敏输入、只用两条正则**：输出也可能泄露 PII；卡号、电话、邮箱格式多样。
- **缓存键只用最后一条消息**：多轮对话中同一句话含义不同。
- **全局可变状态**：故障注入、熔断状态应放在实例里，避免测试之间互相影响。
- **fallback 忽略合规**：备用供应商/区域可能不满足数据驻留要求。
