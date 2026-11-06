# 代码讲解 · classifiers.py

> **所属小节**：阶段 19 · 综合项目 · 第 85 节 综合项目 85：内容分类器集成 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md) ｜ 路由器与测试：[main.讲解.md](main.讲解.md)
>
> **运行方式**：本文件是被导入的模块，没有 `__main__`；由 `python3 main.py` 或 `python3 -m unittest tests` 间接运行 ｜ **依赖**：仅标准库（`re`、`math`、`collections`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

`classifiers.py` 实现了本节的三个**输出侧分类器**，以及它们共用的判决结构：

1. **统一接口**：每个分类器都有 `name` 属性、`classify(text) -> ClassifierVerdict` 和 `redact(text) -> str`。路由器只依赖这三样东西（鸭子类型），不关心分类器内部是规则还是模型。
2. **Toxicity**：关键词表 + 词边界正则 + 左侧否定窗口，按命中数分级。
3. **PII**：五种常见形状（email、电话、SSN、信用卡、IPv4）的正则，卡号再用 **Luhn 校验**过滤；按类型和数量分级。
4. **Instruction leakage**：把输出与已知 system prompt 都变成字符 trigram 计数向量，用余弦相似度判断是否在"复述系统指令"。
5. **每个分类器自带 redactor**：打码彼此独立，可以按顺序叠加。

> 一句话：**用三个零延迟、可单测的规则分类器，把"判定 + 打码"做成可插拔的统一接口**；同时它们的漏报和误报也清楚地展示了规则方法的边界。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SEVERITY_ORDER` | 元组常量 | `("none", "low", "medium", "high")`，用下标比较严重程度 | severity 等级 |
| `ClassifierVerdict` | dataclass | `name / severity / score / findings` | 结构化判决 |
| `_max_severity` | 函数 | 两个 severity 取较大者（**本项目中未被使用**） | — |
| `HARASSMENT_TERMS`、`_NEGATION_WINDOW` | 常量 | 10 个骚扰词；否定窗口 20 字符 | 词表 |
| `ToxicityClassifier` | 类 | 正则匹配 + 否定窗口；`redact` 替换为 `[redacted-language]` | 有害语言检测 |
| `_EMAIL_RE` … `_IPV4_RE` | 预编译正则 | 五种 PII 形状 | PII 检测 |
| `_luhn` | 函数 | 信用卡校验位算法 | 降低卡号误报 |
| `PIIClassifier` | 类 | 汇总五种发现并分级；`redact` 逐类替换为标签 | PII 检测与打码 |
| `_trigrams`、`_cosine` | 函数 | 字符 trigram 计数；计数向量余弦 | 文本相似度 |
| `InstructionLeakageClassifier` | 类 | 与 system prompt 的 trigram 余弦分级；`redact` 替换第一行 | system prompt 泄漏 |
| `default_classifiers` | 函数 | 返回三个默认分类器实例 | 工厂函数 |

数据流：模型输出 `text` → 每个分类器 `classify(text)` → `ClassifierVerdict` 列表 → （在 `main.py` 中）路由器取最大 severity → 需要时调用各分类器的 `redact(text)`。

---

## 3. 逐段精讲

### 3.1 判决结构与 severity 顺序

```python
SEVERITY_ORDER = ("none", "low", "medium", "high")


@dataclass
class ClassifierVerdict:
    name: str
    severity: str = "none"
    score: float = 0.0
    findings: list[str] = field(default_factory=list)


def _max_severity(a: str, b: str) -> str:
    return a if SEVERITY_ORDER.index(a) >= SEVERITY_ORDER.index(b) else b
```

- severity 用字符串表示，比较大小时用它在 `SEVERITY_ORDER` 里的**下标**：`none=0 < low=1 < medium=2 < high=3`。
- `ClassifierVerdict(name=self.name)` 就是"什么都没发现"的默认判决：severity `none`、score 0、findings 空。
- `findings` 必须用 `field(default_factory=list)`：如果写 `findings: list[str] = []`，dataclass 会直接报错（可变默认值会被所有实例共享）。
- ⚠️ `_max_severity` 在整个项目里没人调用，`main.py` 的 `Router` 自己写了一个基于 `max(..., key=...)` 的版本。属于死代码。
- ⚠️ severity 没有校验：如果某个自定义分类器返回了 `"critical"`，路由器里的 `SEVERITY_ORDER.index` 会抛 `ValueError`。生产中可以用 `Enum` 或 `Literal["none", "low", "medium", "high"]` 约束。

### 3.2 ToxicityClassifier：词边界正则 + 否定窗口

```python
    def __init__(self, terms: Iterable[str] | None = None) -> None:
        self._terms = [t.lower() for t in (terms if terms is not None else HARASSMENT_TERMS)]
        joined = "|".join(re.escape(t) for t in self._terms)
        self._needle = re.compile(rf"\b({joined})\b", re.IGNORECASE)

    def _negated_at(self, text: str, start: int) -> bool:
        window = text[max(0, start - _NEGATION_WINDOW) : start].lower()
        return bool(re.search(r"\b(not|never|no)\b", window))
```

- 把所有词用 `|` 拼成一个大正则 `\b(moron|idiot|...|good\ for\ nothing)\b`，一次扫描找出所有命中；`re.escape` 让词表里的特殊字符（如空格、点）按字面匹配。
- `\b` 是**词边界**（字母数字与非字母数字之间的位置），所以 `moron` 不会匹配 `oxymoronic`。讲义说"whitespace-bounded matching"，代码实际用的是 `\b`，标点旁边也算边界（`moron,` 能匹配）。
- `_negated_at`：取命中位置**左侧 20 个字符**，只要里面出现完整单词 `not / never / no` 就算被否定。`max(0, ...)` 防止切片起点为负数（负数下标在 Python 里表示"从末尾数"）。

```python
    def classify(self, text: str) -> ClassifierVerdict:
        findings: list[str] = []
        hits = 0
        for m in self._needle.finditer(text):
            if self._negated_at(text, m.start()):
                continue
            findings.append(f"matched '{m.group(0)}'")
            hits += 1
        if not findings:
            return ClassifierVerdict(name=self.name)
        score = min(1.0, 0.4 + 0.2 * hits)
        if hits >= 3:
            sev = "high"
        elif hits == 2:
            sev = "medium"
        else:
            sev = "low"
        return ClassifierVerdict(name=self.name, severity=sev, score=score, findings=findings)
```

| 未被否定的命中数 | severity | score |
|---|---|---|
| 0 | none | 0.0 |
| 1 | low | 0.6（打印为 `0.6000000000000001`） |
| 2 | medium | 0.8 |
| ≥3 | high | 1.0 |

- `hits` 与 `len(findings)` 永远相等，是冗余变量。
- 实测的否定窗口问题：
  - `"You are not stupid, that was a good question."` → none（设计意图，正确）；
  - `"No way, you idiot."` → none（**漏报**：`No` 修饰的不是 `idiot`）；
  - `"You are stupid, not smart."` → low（否定词在右侧，不影响，正确）。
- 实测的词表问题：`"You idiots!"` → none（复数不匹配）；`"You trash   human"`（多个空格）→ none（多词短语只匹配单个空格）。

```python
    def redact(self, text: str) -> str:
        def _sub(match: re.Match) -> str:
            if self._negated_at(text, match.start()):
                return match.group(0)
            return "[redacted-language]"
        return self._needle.sub(_sub, text)
```

- `re.sub` 的替换参数可以是**函数**：每个匹配调用一次，返回值作为替换文本。这里被否定的命中原样返回，其余替换为标签，与 `classify` 的判断保持一致。
- `match.start()` 是匹配在**原字符串**中的位置，`_sub` 是闭包，引用外层的 `text`（原字符串），所以位置是对得上的。

### 3.3 PII 正则与 Luhn 校验

```python
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
```

| 正则 | 匹配什么 | 已实测的误报 / 漏报 |
|---|---|---|
| email | `本地部分@域名.后缀`；`\w` 在 Python 3 中包含 Unicode 字母 | `张三@例子.中国` 也会匹配 |
| phone | 可选国家码 + 可选括号区号 + 3 位 + 4 位，北美格式 | `Order 1234567890 shipped` 被当成电话；`+1 (555) 123-4567` 只匹配到 `1 (555) 123-4567`，打码后剩下 `+` |
| SSN | 严格的 `3-2-4` 位短横格式 | 不带短横的 9 位数字不识别 |
| card | 13–19 位数字，中间可夹单个空格或短横 | 13 位卡号 `4222222222222` 同时被 phone 匹配，findings 里记两次 |
| IPv4 | 4 段 1–3 位数字 | 不校验 0–255：`999.999.999.999`、版本号 `1.2.3.4` 都算 IP |

- `(?:...)` 是**非捕获分组**，只用于组合，不产生 `group(1)`。
- `\b` 只在"单词字符与非单词字符之间"成立。`+` 不是单词字符，所以 `+1` 前面的空格与 `+` 之间没有边界，匹配只能从 `1` 开始——这就是打码后残留 `+` 的原因。

```python
def _luhn(digits: str) -> bool:
    s = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return s % 10 == 0
```

- Luhn 规则：**从右往左**数，每隔一位（倒数第 2、4、6……位）乘 2，若结果 > 9 则减 9，所有位求和，能被 10 整除即合法。
- 代码从左往右遍历，用 `parity = len % 2` 换算出"哪些下标对应从右数的偶数位"：16 位卡号时 parity = 0，下标 0、2、4…… 乘 2。
- 手算 `4111111111111111`：下标 0 的 4 → 8，其余 7 个偶数下标的 1 → 2，共 `8 + 7×2 = 22`；8 个奇数下标的 1 共 8；总和 30，能被 10 整除 → 合法。`1234567890123456` 总和 64 → 不合法。
- 随机数字串大约有 1/10 的概率碰巧通过 Luhn，所以它只是**降低**误报，不是消除。

### 3.4 PIIClassifier：分级与打码

```python
    def classify(self, text: str) -> ClassifierVerdict:
        findings: list[str] = []
        for m in _EMAIL_RE.finditer(text):
            findings.append(f"email '{m.group(0)}'")
        ...
        for m in _CARD_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and _luhn(digits):
                findings.append(f"card '{m.group(0)}'")
        ...
        score = min(1.0, 0.5 + 0.15 * len(findings))
        if any(f.startswith(("ssn", "card")) for f in findings):
            sev = "high"
        elif len(findings) >= 3 or any(f.startswith("email") for f in findings):
            sev = "medium"
        else:
            sev = "low"
```

- `re.sub(r"\D", "", ...)` 删掉所有非数字字符，只留数字给 Luhn。
- **分级规则**：有 SSN 或通过 Luhn 的卡号 → high；否则有 email 或发现总数 ≥ 3 → medium；否则（只有 1–2 个电话 / IP）→ low。
- `str.startswith` 可以接收**元组**，任意一个前缀匹配就返回 True。
- **score 只看数量**：1 处 0.65、2 处 0.8、3 处 0.95、4 处起 1.0，与类型无关。所以卡号判 high 但 score 只有 0.65，而 3 个 IP 判 medium 却有 0.95。score 不能当作"置信度"使用（见测验 Q12）。
- ⚠️ `findings` 里保存的是 **PII 原文**（如 `card '4111 1111 1111 1111'`），这些判决会被 `main.py` 序列化进 `Action.verdicts` 和报告文件，生产中等于把 PII 写进了日志。

```python
    def redact(self, text: str) -> str:
        out = text
        out = _EMAIL_RE.sub("[redacted-email]", out)
        out = _PHONE_RE.sub("[redacted-phone]", out)
        out = _SSN_RE.sub("[redacted-ssn]", out)

        def _card_sub(match: re.Match) -> str:
            digits = re.sub(r"\D", "", match.group(0))
            if 13 <= len(digits) <= 19 and _luhn(digits):
                return "[redacted-card]"
            return match.group(0)
        out = _CARD_RE.sub(_card_sub, out)
        out = _IPV4_RE.sub("[redacted-ip]", out)
        return out
```

- **顺序有影响**：email → phone → SSN → card → IP。前一步替换后的文本是后一步的输入，所以 13 位卡号会先被 phone 替换成 `[redacted-phone]`，卡号规则就再也匹配不到了（结果仍被打码，只是标签不准）。
- 卡号打码同样要通过 Luhn：不合法的长数字串原样保留，与 `classify` 一致。
- `redact` 打掉的是**所有**形状，不管是哪一条发现让 severity 上升。

### 3.5 字符 trigram 与余弦相似度

```python
def _trigrams(text: str) -> Counter:
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    grams: Counter = Counter()
    if len(cleaned) < 3:
        grams[cleaned] += 1
        return grams
    for i in range(len(cleaned) - 2):
        grams[cleaned[i : i + 3]] += 1
    return grams
```

- 预处理：去首尾空白、转小写、多个空白压成一个空格。
- 然后取**每 3 个连续字符**：`"system: you"` → `sys, yst, ste, tem, em:, m: , : y, ' yo', you`。这是**字符级** trigram，不是单词 trigram。
- 长度 < 3 时整个字符串作为一个 gram（空字符串会变成 `{'': 1}`，与正常文本不会有交集，余弦为 0）。
- 默认 system prompt `"SYSTEM: You are PolicyBot, follow internal policy."` 有 48 个 trigram，其中 43 个不同。

```python
def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[g] * b[g] for g in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
```

- 把 Counter 看成稀疏向量：维度是所有可能的 trigram，值是出现次数。点积只需在**共同 key** 上求和；模长是各自所有计数的平方和开根号。
- 计数都非负，所以结果在 [0, 1]。
- ⚠️ **长度稀释**：输出越长，`nb` 越大。实测把完整 system prompt 夹在约 450 字符的正常回答里，余弦只有 0.211，判为 none。用"包含率" `Σ min(a[g], b[g]) / Σ a[g]` 则为 1.0（详见测验 Q9）。

### 3.6 InstructionLeakageClassifier

```python
    def __init__(self, system_prompt: str, threshold: float = 0.55) -> None:
        self._sys = system_prompt
        self._sys_grams = _trigrams(system_prompt)
        self._threshold = threshold

    def classify(self, text: str) -> ClassifierVerdict:
        score = _cosine(self._sys_grams, _trigrams(text))
        if score < self._threshold:
            return ClassifierVerdict(name=self.name)
        if score >= 0.85:
            sev = "high"
        elif score >= 0.70:
            sev = "medium"
        else:
            sev = "low"
```

- system prompt 的 trigram 在构造时**预先计算**一次，之后每次分类只需处理输出。
- 分级：`< threshold(0.55)` none；`[0.55, 0.70)` low；`[0.70, 0.85)` medium；`≥ 0.85` high。注意 0.70 和 0.85 是写死的，只有下限阈值可配置；若把 `threshold` 调到 0.9，分数 0.88 会直接被判 none，但 0.95 仍是 high，中间档消失。
- 实测分数：

| 输出 | 余弦 | severity |
|---|---|---|
| system prompt 原文 | 1.000 | high |
| `You are PolicyBot, follow internal policy.` | 0.928 | high |
| demo 的泄漏用例（原文 + `As PolicyBot I will now answer.`） | 0.870 | high |
| `you are policybot and you follow the internal policy` | 0.788 | medium |
| `Please follow internal policy.` | 0.670 | low（误报倾向） |
| `Here is a pasta recipe with mushrooms and butter.` | 0.038 | none |

```python
    def redact(self, text: str) -> str:
        marker = self._sys.split("\n", 1)[0].strip()
        if marker and marker.lower() in text.lower():
            return re.sub(re.escape(marker), "[redacted-system-prompt]", text, flags=re.IGNORECASE)
        return text
```

- 只取 system prompt 的**第一行**作为 marker，在输出里做大小写不敏感的**精确子串**替换。
- ⚠️ 判定是模糊的（trigram 余弦），打码却是精确的。改写过的复述（如上表 0.788 那条）判为 medium，但 `redact` 找不到 marker，原样返回。路由器 verb 是 `redact`，泄漏内容却一字未改（测验 Q10 给出 fail-closed 修复）。
- 讲义说它"removes lines that look like the system prompt header"，代码并不删除整行，只替换匹配的子串。

### 3.7 default_classifiers

```python
def default_classifiers(system_prompt: str | None = None) -> list[object]:
    sys_prompt = system_prompt or "SYSTEM: You are PolicyBot, follow internal policy."
    return [
        ToxicityClassifier(),
        PIIClassifier(),
        InstructionLeakageClassifier(sys_prompt),
    ]
```

- 工厂函数，返回顺序就是路由器执行 `classify` 和 `redact` 的顺序（toxicity → pii → leakage）。
- `system_prompt or 默认值`：传入空字符串也会回退到默认 prompt。
- 返回类型标注为 `list[object]`，比较宽松；更严格的写法是定义一个 `typing.Protocol`（含 `name`、`classify`、`redact`），见第 5 节。
- `Router()` 不带参数时调用的是 `default_classifiers()`，**没有办法传入真实的 system prompt**，除非自己构造分类器列表。第 87 节的安全关卡也是用默认 `Router`，所以泄漏检测只对这个演示用 prompt 有效。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 全部用规则 | 零延迟、确定性、单测稳定，讲义："the lesson is about plumbing, not lexicon-building" | 召回低、易被改写绕过；生产用审核模型 + 规则组合 |
| 统一的 `classify / redact / name` 接口 | 路由器与分类器解耦，可插拔 | 没有显式 `Protocol`，接口约定只靠文档 |
| severity 用字符串 + 顺序元组 | 简单、易序列化成 JSON | 没有校验；生产可用 `Enum` |
| 否定窗口固定 20 字符 | 实现简单，能处理 "you are not X" | 不懂句法，`No way, you idiot.` 漏报 |
| 卡号用 Luhn 过滤 | 显著减少长数字串误报 | 仍有约 1/10 的随机串通过；电话正则会抢先匹配 13 位卡号 |
| PII 分级看"类型 + 数量" | 高危类型直接 high | 单个电话/IP 只算 low → warn 原样发出；score 只看数量 |
| `findings` 带原文 | 调试方便、可解释 | 把 PII 写进 trace；生产只记类型、位置或哈希 |
| 字符 trigram 余弦检测泄漏 | 无需模型，对大小写、空白不敏感 | 长输出稀释、改写可绕过；可用包含率、滑动窗口、canary token |
| 泄漏打码只替换第一行 | 实现简单 | 与模糊判定不一致，medium 时可能"打码无效" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件第一条 import | 注解延迟求值，旧版本 Python 也能写 `list[str]`、`str \| None` |
| `@dataclass` + `field(default_factory=list)` | `ClassifierVerdict` | 自动生成 `__init__`/`__repr__`；可变默认值必须用工厂函数 |
| 类型注解 | `def classify(self, text: str) -> ClassifierVerdict`、`Iterable[str] \| None` | 只是提示，不在运行时检查 |
| 类属性 | `name = "toxicity"` | 写在类体里，所有实例共享，也可以 `ToxicityClassifier.name` 访问 |
| 条件表达式 | `terms if terms is not None else HARASSMENT_TERMS` | 一行的 if/else |
| 列表推导式 / 生成器表达式 | `[t.lower() for t in ...]`、`"\|".join(re.escape(t) for t in ...)` | 生成器表达式作为唯一参数时可省略外层括号 |
| raw f-string | `rf"\b({joined})\b"` | `r` 让反斜杠不转义，`f` 允许插值 |
| 预编译正则 | `re.compile(..., re.IGNORECASE)` | 复用同一模式时更快；flag 忽略大小写 |
| `finditer` / `match.group(0)` / `match.start()` | `for m in self._needle.finditer(text)` | 逐个返回 Match 对象，`group(0)` 是整段匹配，`start()` 是起始下标 |
| `re.sub` 传函数 | `self._needle.sub(_sub, text)` | 每个匹配调用一次函数，返回值作为替换 |
| 嵌套函数 / 闭包 | `def _sub(match)` 引用外层 `text` | 内部函数可以读取外层变量 |
| 切片与 `max` 防负下标 | `text[max(0, start - 20) : start]` | 负数下标会从末尾数，必须截到 0 |
| `enumerate` | `for i, ch in enumerate(digits)` | 同时拿到下标和元素 |
| `str.startswith(元组)` | `f.startswith(("ssn", "card"))` | 任一前缀匹配即为 True |
| `any(...)` | `any(f.startswith("email") for f in findings)` | 有一个为真就返回 True，短路求值 |
| `collections.Counter` | `grams[cleaned[i:i+3]] += 1` | 缺失 key 默认 0，适合计数 |
| 集合交集 | `set(a) & set(b)` | 两个 Counter 共同的 key |
| `math.sqrt` | `math.sqrt(sum(v * v for v in a.values()))` | 向量模长 |
| 链式比较 | `13 <= len(digits) <= 19` | 等价于两个比较用 and 连接 |
| `str.split(sep, maxsplit)` | `self._sys.split("\n", 1)[0]` | 只切一次，取第一行 |
| `or` 提供默认值 | `system_prompt or "SYSTEM: ..."` | 左边为假值（None、空串）时取右边 |

---

## 6. 运行结果解读

本文件没有入口，下面是通过 `main.py` 运行 demo 时各分类器的实际判决（Python 3.13，结果与仓库中的 `outputs/classifier_report.json` 完全一致）：

| 用例 | toxicity | pii | instruction-leakage |
|---|---|---|---|
| clean response | none 0.0 | none 0.0 | none 0.0 |
| low toxicity `You moron, ...` | **low 0.6**（`matched 'moron'`） | none | none |
| medium pii (email) | none | **medium 0.65**（`email 'help@example.com'`） | none |
| high pii (luhn-valid card) | none | **high 0.65**（`card '4111 1111 1111 1111'`） | none |
| instruction leakage | none | none | **high 0.870**（`trigram overlap with system prompt: 0.87`） |
| negated toxicity `You are not stupid, ...` | none（被否定窗口跳过） | none | none |

逐项解读：

- `0.6000000000000001`：`0.4 + 0.2 * 1` 的浮点误差，0.2 无法用二进制精确表示。
- 卡号用例的 score 只有 0.65（1 处发现），但 severity 是 high——再次说明 score 与 severity 是两套规则。
- 卡号用例中的 `1 Pine St.` 不会被当成 PII：本分类器不识别地址。
- 泄漏用例 0.870 刚刚超过 0.85 的 high 线；如果模型多说一句话，分数就可能掉到 medium，此时 `redact` 能找到 marker（原文里包含第一行），会替换为 `[redacted-system-prompt]`。

额外的边界实测（在副本中运行）：

```text
'No way, you idiot.'               toxicity none            ← 否定窗口漏报
'You idiots!'                      toxicity none            ← 复数漏报
'Card 4222222222222'               pii high 0.8  findings=[phone, card] → redact 结果 'Card [redacted-phone]'
'+1 (555) 123-4567'                pii low       → redact 结果 '+[redacted-phone]'
'version 1.2.3.4'                  pii low       findings=[ip '1.2.3.4']   ← 版本号误报
ToxicityClassifier(terms=[]).classify('hello world')
                                   high 1.0, findings=["matched ''"] × 4  ← 空词表 bug
```

最后一条是一个真实 bug：传入空词表时 `joined` 为空字符串，正则变成 `\b()\b`，在**每个词边界**匹配空串，于是任何文本都判为 high。应在构造时检查 `if not self._terms` 并让 `classify` 直接返回 none。

---

## 7. 动手改一改

1. **修空词表 bug**：在 `ToxicityClassifier.__init__` 中处理 `terms=[]`，并写一个测试确认 `classify("hello world")` 返回 none。
2. **改进否定窗口**：只在否定词与命中词之间没有逗号、句号等分隔符时才算否定（或只看命中词前 3 个单词），验证 `"No way, you idiot."` 变为 low，而 `"You are not stupid"` 仍为 none。再把词表改成支持复数（如 `idiots?`）。
3. **收紧 IPv4 与电话**：IPv4 每段限制在 0–255；电话前面若紧跟 `Order`、`#` 等词则跳过；把 `+` 纳入电话匹配，确认打码后不再残留 `+`。
4. **讲义练习 1**：新增 `CodeInjectionClassifier`（`name = "code-injection"`），检测 `<script`、`eval(`、`os.system(` 等；决定它的 severity 策略（例如 `<script` 直接 high），实现 `redact`，放进 `default_classifiers` 并在 `main.py` 的 demo 中加一个 fixture。
5. **泄漏检测改用包含率**：在 `_cosine` 之外实现 `containment`，让 `classify` 取两者的最大值，验证"长输出夹带完整 system prompt"被判为 high，同时检查 `Please follow internal policy.` 是否因此误报更严重。
6. **进阶：canary token**：给 `InstructionLeakageClassifier` 增加一个 `canary` 参数（随机字符串，嵌入 system prompt），输出中一旦出现 canary 立即 high，`redact` 时删除包含 canary 的整行。

---

## 8. 常见坑

- **忘记 `re.escape`**：词表里有 `.`、`+`、`(` 时，直接拼进正则会改变含义甚至报错。
- **`\b` 和非单词字符**：`\b` 不会出现在 `+`、`(` 前面的空格处，以符号开头的模式要单独处理。
- **把 score 当置信度**：本文件的 score 只由数量决定，用它做阈值过滤会把卡号这类高危发现降级。
- **redactor 顺序**：前一个正则的替换结果会影响后一个正则，标签可能"张冠李戴"（13 位卡号变 `[redacted-phone]`）。
- **在 `findings` 里存原文**：判决对象会被序列化、写日志，PII 随之泄漏。
- **余弦相似度用于"包含"判断**：被检测文本越长分数越低；判断"A 是否出现在 B 中"应该用包含率或滑动窗口。
- **判定与打码不一致**：模糊判定 + 精确打码会出现"判了但没打掉"，需要在路由层做 fail-closed 检查。
- **空输入、空词表等边界**：`_trigrams("")` 返回 `{'': 1}`，空词表会让正则匹配一切；写分类器时要为这些边界补测试。
