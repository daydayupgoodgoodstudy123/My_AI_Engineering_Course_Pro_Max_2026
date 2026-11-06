# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 25 节 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`datetime`、`hashlib`、`json`、`re`），不调用任何 LLM 或 vault

---

## 1. 这份代码在考察什么

这份约 125 行的代码实现了讲义中的两个组件：

1. **带一致性 tokenization 的 PII 脱敏器**（`Scrubber`）：用正则找出 SSN、邮箱、电话，把每个不同的值映射成稳定的占位符（`[SSN_001]`），同一个值在后续 prompt 中仍然得到同一个占位符——讲义练习 1 要验证的正是这一点。
2. **Audit log 记录**（`AuditEntry` + `audit_log_call`）：每次调用生成一条 JSON，字段与讲义一致：时间、用户、租户、模型、prompt 哈希、响应哈希、token 数、成本、guardrail 触发；不记录原始 prompt。

它对应讲义的"PII / PHI scrubbing"第 2、3 步（掩码、一致性）和"Audit log"字段清单。没有实现的部分：NER、反向映射、vault、出口控制、真正的不可变存储。

同时它有几处值得指出的问题：电话正则漏掉左括号和加号、同一号码不同写法得到不同占位符、所谓"immutable audit log"只是 `json.dumps`、哈希不加密钥且截断到 48 位、`input_tokens` 实际是单词数。

> 一句话：**演示"同一个 PII 值 → 同一个占位符"和"audit log 只存哈希"两条原则**，同时也展示了正则脱敏在边界上有多容易出错。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SSN` / `EMAIL` / `PHONE` | 预编译正则 | 识别三类 PII | 静态正则过滤 |
| `Scrubber` | dataclass | `tokens`（值 → 占位符）、`counter`（各类计数）；`scrub()` 依次替换 | 一致性 tokenization |
| `Scrubber._token_for` | 方法 | 查表；没有则生成 `[KIND_NNN]` 并登记 | 稳定占位符 |
| `AuditEntry` | dataclass | 10 个审计字段 | Audit log schema |
| `hash_short` | 函数 | SHA-256 取前 12 个十六进制字符 | prompt/响应哈希 |
| `audit_log_call` | 函数 | 把 `AuditEntry` 序列化成一行 JSON | 审计记录 |
| `main` | 函数 | 脱敏 3 条 prompt → 打印 token 表 → 再次脱敏并为每条生成审计记录 | 演示入口 |

数据流：原始 prompt → `Scrubber.scrub`（SSN → EMAIL → PHONE 三轮替换）→ 脱敏文本 → `hash_short` → `AuditEntry` → `audit_log_call` → 打印 JSON。

---

## 3. 逐段精讲

### 3.1 三个正则

```python
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
```

- `r"..."` 是原始字符串，反斜杠不会被 Python 转义，写正则的标准做法。`re.compile` 预编译，多次使用更快。
- **SSN**：`ddd-dd-dddd`，两端 `\b` 防止匹配更长数字的一部分。只认带连字符的格式，`123 45 6789`、`123456789` 都漏检（已实测）。
- **EMAIL**：`[\w.+-]+` 本地部分 + `@` + 域名 + `.` + 顶级域。足够演示，但不区分大小写归一化。
- **PHONE**：可选的 `+1` 国家码，可选括号的区号，三段数字之间允许 `-`、`.`、空白。
  - ⚠️ **开头的 `\b` 是 bug 的来源**：`\b` 是单词字符与非单词字符之间的位置。`(202) 555-0150` 前面是空格，空格和 `(` 都是非单词字符，它们之间没有 `\b`，正则只能从 `2` 开始匹配，`\(?` 匹配空串，于是左括号残留在输出中：`phone ([PHONE_002].`。同理 `+1 202 555 0150` 会残留 `+`。
  - 修复：开头改为负向后顾 `(?<!\w)`，区号改为 `(?:\(\d{3}\)|\d{3})`（测验 Q9 有完整代码与验证）。
  - ⚠️ 10 位的订单号 `4155550199` 也会被当成电话（误报）。

### 3.2 `Scrubber`：一致性 tokenization

```python
@dataclass
class Scrubber:
    tokens: dict = field(default_factory=dict)
    counter: dict = field(default_factory=lambda: {"SSN": 0, "EMAIL": 0, "PHONE": 0})
```

- dataclass 的可变默认值必须用 `field(default_factory=...)`：如果写成 `tokens: dict = {}`，dataclass 会直接报错（防止所有实例共享同一个字典）。
- `tokens` 保存"原始值 → 占位符"的映射——**它本身就是一张明文 PII 表**，生产中必须加密存储、按租户隔离、设置过期。

```python
    def _token_for(self, kind: str, value: str) -> str:
        if value in self.tokens:
            return self.tokens[value]
        self.counter[kind] += 1
        placeholder = f"[{kind}_{self.counter[kind]:03}]"
        self.tokens[value] = placeholder
        return placeholder
```

- 先查表：见过的值直接返回旧占位符，这就是"一致性"。
- 新值：该类计数加 1，生成 `[SSN_001]` 格式（`:03` 表示宽度 3、左侧补零）。
- ⚠️ **键是原始字符串**，没有归一化：`(202) 555-0150`、`202-555-0150`、`202.555.0150` 会得到三个不同占位符；`JANE.DOE@EXAMPLE.COM` 与 `jane.doe@example.com` 也不同。一致性因此被破坏。
- ⚠️ 键只用 `value`，没有带上 `kind`；当前三种正则的值形状互不相同，暂不冲突，但扩展更多实体类型时应以 `(kind, value)` 为键。
- ⚠️ **顺序编号**泄露"见过多少个不同 SSN"；单个全局实例被所有用户共享，不同租户的同一值得到同一占位符，可被用来跨租户关联。讲义示例 `[SSN_TOKEN_A3F]` 更像带密钥的哈希，测验 Q10 给出了 HMAC + 租户密钥的写法。

```python
    def scrub(self, text: str) -> str:
        text = SSN.sub(lambda m: self._token_for("SSN", m.group(0)), text)
        text = EMAIL.sub(lambda m: self._token_for("EMAIL", m.group(0)), text)
        text = PHONE.sub(lambda m: self._token_for("PHONE", m.group(0)), text)
        return text
```

- `pattern.sub(func, text)`：第一个参数可以是函数，每次匹配时以 `Match` 对象调用它，用返回值替换；`m.group(0)` 是整个匹配文本。
- 顺序是 SSN → EMAIL → PHONE。先替换的结果会影响后面的匹配：占位符里没有 10 位连续数字，所以电话正则不会误伤 `[SSN_001]`。
- 没有 NER：人名、地址、信用卡号等都不会被识别（讲义："Static regex filters catch basic patterns; NER catches more. Use both."）。

### 3.3 `AuditEntry` 与哈希

```python
@dataclass
class AuditEntry:
    timestamp: str
    user: str
    tenant: str
    model: str
    prompt_hash: str
    response_hash: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    guardrail_trips: list


def hash_short(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]
```

- 字段与讲义 Audit log 清单一一对应（讲义还要求"model + version"，这里只有一个 `model` 字符串）。
- `s.encode()` 默认按 UTF-8 编码为字节，`hexdigest()` 得到 64 个十六进制字符，`[:12]` 截断为 12 个（48 位）。
- ⚠️ **不加密钥**：脱敏后的 prompt 常来自固定模板，攻击者可以枚举候选文本计算 SHA-256 来确认记录内容。应使用 HMAC，密钥放 vault。
- ⚠️ **截断**：按生日问题估算，1,000 万条记录出现至少一次碰撞的概率约 16.3%（已计算）。审计取证场景建议保留完整哈希。
- 哈希的是**脱敏后**的文本：这意味着两条 PII 不同但模板相同的 prompt 会得到相同哈希——对审计"有没有发过这条内容"来说足够，但不能用来区分具体用户数据。

### 3.4 `audit_log_call`

```python
def audit_log_call(entry: AuditEntry) -> str:
    return json.dumps({
        "timestamp": entry.timestamp,
        ...
        "guardrail_trips": entry.guardrail_trips,
    })
```

- 手动把 dataclass 字段逐个放进字典再 `json.dumps`。等价且更简洁的写法是 `json.dumps(dataclasses.asdict(entry))`。
- ⚠️ docstring 说"Appends to an immutable audit log on every call"，但函数只返回字符串，`main` 只是打印。没有写入、没有序号、没有哈希链、没有 WORM 存储，任何人都可以修改或删除。测验 Q11 给出了哈希链实现：每条记录包含上一条的哈希，篡改任意一条都能被 `verify()` 发现。

### 3.5 `main`：两轮遍历

```python
    for i, raw in enumerate(prompts, 1):
        scrubbed = scrubber.scrub(raw)
        ...
    for value, placeholder in scrubber.tokens.items():
        masked = value[:3] + "***" if len(value) > 6 else "***"
        print(f"  {masked} → {placeholder}")
```

- `enumerate(prompts, 1)` 从 1 开始编号。
- 打印 token 表时只显示前 3 个字符。⚠️ 这仍然泄露了 SSN 前 3 位、电话区号、邮箱前缀；脱敏工具自己的日志也必须遵守"不输出 PII"。

```python
    for i, raw in enumerate(prompts, 1):
        scrubbed = scrubber.scrub(raw)
        response = f"toy response for prompt {i}"
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            user=f"user_{i:03}",
            tenant="tenant_01",
            model="anthropic/claude-3.7-sonnet",
            prompt_hash=hash_short(scrubbed),
            response_hash=hash_short(response),
            input_tokens=len(scrubbed.split()),
            output_tokens=len(response.split()),
            cost_usd=0.0012,
            guardrail_trips=[],
        )
        print(audit_log_call(entry))
```

- 第二轮重新脱敏同样的 3 条 prompt：因为 `scrubber` 保留了状态，得到的占位符与第一轮完全相同，这本身就是一致性的演示。
- `datetime.utcnow()` 返回不带时区的时间，再手动拼 `"Z"`。⚠️ 该方法自 Python 3.12 起已弃用（本次在 Python 3.13 下用 `-W default` 运行会打印 DeprecationWarning），应改为 `datetime.now(timezone.utc).isoformat()`。
- ⚠️ `input_tokens=len(scrubbed.split())` 是按空白切分的**单词数**，不是 tokenizer 的 token 数；`cost_usd` 是常量。真实系统应使用 provider 返回的 `usage` 字段。
- 使用关键字参数构造 dataclass，字段多时可读性更好、不易错位。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用正则 | 无依赖、可解释 | 漏检人名/地址/其他格式，误报订单号；生产用 Presidio 等 NER + 正则 + 校验规则 |
| 顺序编号占位符 | 可读、易演示 | 泄露数量与顺序，重启后不一致；用 HMAC(租户密钥, 归一化值) |
| 全局单例 `Scrubber` | 演示跨 prompt 一致性 | 跨租户共享映射；按租户/会话隔离，映射表加密存储并设 TTL |
| 原始值作字典键 | 实现最简 | 格式不同即不一致；先归一化 |
| 只存哈希不存原文 | 符合讲义与 skill 的 hard reject | 不加密钥可被字典攻击；用 HMAC 并保留完整长度 |
| `json.dumps` 代替日志存储 | 演示字段 | 不是不可变日志；用哈希链 + WORM 存储 + 权限分离 |
| 单词数代替 token 数、固定成本 | 无需 tokenizer | 计费与审计不准确；使用 provider 返回的 usage |
| 不实现反向映射 | 简化 | 面向用户的回答会出现占位符；见讲义练习 5 的取舍讨论 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 原始字符串 | `r"\b\d{3}-\d{2}-\d{4}\b"` | 反斜杠按字面保留，写正则必备 |
| `re.compile` | `SSN = re.compile(...)` | 预编译正则对象 |
| 正则元素 | `\b`、`\d{3}`、`(?:...)`、`?`、`[-.\s]` | 单词边界、重复次数、非捕获分组、可选、字符集 |
| `pattern.sub(func, text)` | `SSN.sub(lambda m: ..., text)` | 用函数的返回值替换每个匹配 |
| `m.group(0)` | `m.group(0)` | 整个匹配到的字符串 |
| `field(default_factory=...)` | `tokens: dict = field(default_factory=dict)` | dataclass 中可变默认值的正确写法 |
| `lambda` | `lambda: {"SSN": 0, ...}`、`lambda m: ...` | 匿名函数 |
| 私有方法约定 | `def _token_for(...)` | 下划线前缀表示"内部使用"，Python 不强制 |
| f-string 补零 | `f"[{kind}_{n:03}]"`、`f"user_{i:03}"` | 宽度 3，不足补 0 |
| `str.encode` | `s.encode()` | 字符串 → UTF-8 字节，哈希函数需要字节 |
| `hashlib` | `hashlib.sha256(b).hexdigest()[:12]` | 计算 SHA-256 并取十六进制前 12 位 |
| `json.dumps` | `json.dumps({...})` | 字典 → JSON 字符串 |
| `datetime` | `datetime.utcnow().isoformat()` | ISO 8601 时间字符串（`utcnow` 已弃用） |
| `enumerate(..., 1)` | `for i, raw in enumerate(prompts, 1)` | 带序号遍历，从 1 开始 |
| 条件表达式 | `value[:3] + "***" if len(value) > 6 else "***"` | 三元表达式 |
| 关键字参数构造 | `AuditEntry(timestamp=..., user=..., ...)` | 字段多时更清晰 |
| `dict.items()` | `for value, placeholder in scrubber.tokens.items()` | 遍历键值对，保持插入顺序 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13.16）的输出（节选，时间戳与哈希中的时间因运行时刻不同而变化，但哈希只依赖文本，是固定的）：

```text
[prompt 1]
  raw:      My SSN is 123-45-6789 and my email is jane.doe@example.com. Phone 415-555-0199.
  scrubbed: My SSN is [SSN_001] and my email is [EMAIL_001]. Phone [PHONE_001].

[prompt 2]
  raw:      Please contact 123-45-6789 regarding account jane.doe@example.com.
  scrubbed: Please contact [SSN_001] regarding account [EMAIL_001].        ← 一致性：与 prompt 1 相同

[prompt 3]
  raw:      New user: bob@example.com, SSN 987-65-4321, phone (202) 555-0150.
  scrubbed: New user: [EMAIL_002], SSN [SSN_002], phone ([PHONE_002].      ← 左括号残留

Scrubber token table (6 entries):
  123*** → [SSN_001]
  jan*** → [EMAIL_001]
  415*** → [PHONE_001]
  987*** → [SSN_002]
  bob*** → [EMAIL_002]
  202*** → [PHONE_002]                                                    ← 实际存储的值是 "202) 555-0150"

AUDIT LOG — one entry per scrubbed call
{"timestamp": "...Z", "user": "user_001", "tenant": "tenant_01", "model": "anthropic/claude-3.7-sonnet",
 "prompt_hash": "ce2e3bf0d6cb", "response_hash": "10d9c68e9050", "input_tokens": 11, "output_tokens": 5,
 "cost_usd": 0.0012, "guardrail_trips": []}
……（user_002：prompt_hash d9752c2e752c，input_tokens 6；user_003：e67ccddf647c，input_tokens 7）
```

逐项解读：

- **讲义练习 1 的答案**：prompt 1 与 prompt 2 都提到 `123-45-6789` 和 `jane.doe@example.com`，二者都被替换为 `[SSN_001]`、`[EMAIL_001]`，一致性成立。LLM 看到 prompt 2 时能知道"联系的人就是 prompt 1 中的那个人"。
- **prompt 3 的 bug**：`phone ([PHONE_002].` 中残留的左括号说明正则边界写错；且 token 表中的值是 `202) 555-0150`，如果后续 prompt 写成 `202-555-0150`，会得到新的 `[PHONE_003]`，一致性破裂。
- **token 表打印**：`123***` 暴露了 SSN 前 3 位。
- **audit log**：`input_tokens` 11 / 6 / 7 是脱敏后文本的单词数；`output_tokens` 都是 5（"toy response for prompt i" 共 5 个单词）。prompt_hash 只依赖脱敏文本，因此是确定的；这也意味着它可以被字典攻击（见 3.3 节）。
- **弃用警告**：默认运行不显示；加 `-W default` 运行时会出现 `DeprecationWarning: datetime.datetime.utcnow() is deprecated`。

---

## 7. 动手改一改

1. **（讲义练习 1）** 再加一条 prompt："Call me at 202-555-0150 or (202) 555-0150"，观察两种写法是否得到同一占位符（原代码不会）。
2. 修复 `PHONE` 正则（开头改 `(?<!\w)`、区号用 `(?:\(\d{3}\)|\d{3})`），并在 `_token_for` 里用归一化后的值作键，让上一题的两种写法得到同一占位符。
3. 把占位符改为 `[KIND_<HMAC前6位>]`，每个租户一个密钥；为两个租户各建一个 `Scrubber`，验证同一 SSN 在两个租户下占位符不同。
4. 实现反向映射：`unscrub(text)` 把 LLM 输出中的占位符替换回原值；考虑 LLM 改写占位符（如写成 "SSN_001" 不带方括号）时如何容错（讲义练习 5）。
5. 把 `audit_log_call` 改为写入 JSONL 文件的哈希链日志，`prompt_hash` 改用 HMAC，并写 `verify()` 检查篡改（参考测验 Q11）。
6. 进阶：安装 Presidio（需要 spaCy 模型），与正则结果合并，统计在一组包含人名、地址、信用卡号的测试文本上两种方法各自的漏检与误报。

---

## 8. 常见坑

- **`\b` 与非单词字符**：以 `(`、`+` 开头的模式前面不能用 `\b`，否则匹配起点会被推后、留下残余字符。
- **不做归一化就谈一致性**：格式、大小写、空白不同都会产生新的占位符。
- **映射表也是 PII**：只脱敏 prompt、却把映射表明文放在内存/日志里，等于把 PII 换了个地方存放。
- **调试输出泄露**：`value[:3] + "***"` 这类"部分遮盖"仍可能泄露敏感片段。
- **不加盐/不加密钥的哈希**：低熵或模板化内容的哈希可以被枚举还原。
- **把 JSON 字符串当作审计日志**：不可变性来自存储与流程（WORM、哈希链、权限分离），而不是数据格式。
- **单词数 ≠ token 数**：计费、限流、审计都要用 provider 返回的真实 usage。
- **`datetime.utcnow()`**：已弃用且返回 naive datetime，跨系统比较时间时容易出错。
