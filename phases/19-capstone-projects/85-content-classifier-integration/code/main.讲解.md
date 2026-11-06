# 代码讲解 · main.py（含 tests.py）

> **所属小节**：阶段 19 · 综合项目 · 第 85 节 综合项目 85：内容分类器集成 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md) ｜ 分类器实现：[classifiers.讲解.md](classifiers.讲解.md)
>
> **运行方式**：`cd code && python3 main.py`；测试 `python3 -m unittest tests -v` 或 `python3 -m pytest -q tests.py` ｜ **依赖**：仅标准库（`json`、`sys`、`dataclasses`、`pathlib`、`typing`）+ 同目录的 `classifiers.py`

---

## 1. 这份代码在考察什么

`main.py` 是本节的**策略路由器（policy router）**：把三个输出侧分类器的判决汇总成一个动作。

1. **取最大 severity**：多个分类器同时触发时，只看最严重的那个。讲义："Block wins. A redact + warn becomes redact. A log + warn becomes warn."
2. **severity → action 映射**：`high → block`（替换为拒答）、`medium → redact`（依次套用各分类器的打码器）、`low → warn`（原文 + 软提示）、`none → log`（原样发出）。
3. **结构化输出**：返回 `Action(verb, output, severity, verdicts, metadata)`，供第 87 节的安全关卡写入 trace。
4. **可复现的演示**：6 个精心构造的 fixture 覆盖四种动作，结果写进 `outputs/classifier_report.json`。

`tests.py` 用 18 个单元测试固定了分类器和路由器的行为，本讲解第 9 节逐个说明。

> 一句话：**分类器负责"看出问题"，路由器负责"决定怎么处理"；二者通过统一的 verdict 结构解耦。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HERE`、`OUTPUTS` | 模块常量 | 定位 `code/` 与 `outputs/` 目录 | 路径管理 |
| `REFUSAL_TEXT` | 字符串常量 | block 时替换输出的拒答文本 | policy refusal |
| `Action` | dataclass | `verb / output / severity / verdicts / metadata` | 路由结果 |
| `Router.__init__` | 方法 | 接收分类器列表，默认 `default_classifiers()` | 可插拔分类器 |
| `Router._max_severity` | 方法 | 判决列表中最大的 severity | 聚合规则 |
| `Router._apply_redactors` | 方法 | 对所有非 none 的分类器按顺序调用 `redact` | 叠加打码 |
| `Router.run` | 方法 | 依次调用每个分类器的 `classify`，再交给 `decide` | 一站式入口 |
| `Router.decide` | 方法 | 根据最大 severity 构造 `Action` | 策略表 |
| `_DEMO_OUTPUTS` | 列表 | 6 个演示用模型输出 | fixture |
| `write_report` | 函数 | 写 `outputs/classifier_report.json` | 产物 |
| `demo` | 函数 | 跑全部 fixture、打印表格、写报告，返回退出码 0 | 演示 |
| `tests.py` | 测试模块 | 18 个 `unittest` 测试 | 回归保护 |

数据流：`fixture["output"]` → `Router.run` → 三个 `classify` → `[ClassifierVerdict × 3]` → `decide` → `_max_severity` → （medium 时 `_apply_redactors`）→ `Action` → 打印 + 序列化进 JSON 报告。

---

## 3. 逐段精讲

### 3.1 导入与常量

```python
from classifiers import (
    SEVERITY_ORDER,
    ClassifierVerdict,
    InstructionLeakageClassifier,
    PIIClassifier,
    ToxicityClassifier,
    default_classifiers,
)

HERE = Path(__file__).parent
OUTPUTS = HERE.parent / "outputs"

REFUSAL_TEXT = "I cannot share that. The response was blocked by an output safety classifier."
```

- `from classifiers import ...` 是同目录导入，要求在 `code/` 目录下运行（或把该目录加入 `sys.path`）。第 87 节就是通过 `sys.path` 注入 + `importlib` 加载本文件的 `Router`。
- ⚠️ `InstructionLeakageClassifier`、`PIIClassifier`、`ToxicityClassifier` 三个名字在本文件中**没有被使用**（只用了 `default_classifiers`），属于多余导入。
- `Path(__file__).parent` 是本文件所在目录；`HERE.parent / "outputs"` 用 `/` 运算符拼路径，得到与 `code/` 并列的 `outputs/`。不管从哪个工作目录启动，报告都写到同一位置。

### 3.2 Action：路由器的输出结构

```python
@dataclass
class Action:
    verb: str
    output: str
    severity: str
    verdicts: list[dict[str, object]] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

- `verb`：`block / redact / warn / log` 之一；`output`：真正要发给用户的文本；`severity`：触发该动作的最大 severity。
- `verdicts` 存的是**字典**（由 `asdict` 转换），而不是 `ClassifierVerdict` 对象，这样 `Action` 可以直接 `json.dumps`。
- 讲义的输出 skill 文件（`outputs/skill-content-classifier-integration.md`）记录的就是这个结构，第 87 节从中读取 `verb` 和 `severity`。

### 3.3 Router 初始化与最大 severity

```python
class Router:
    def __init__(self, classifiers: Iterable[object] | None = None) -> None:
        self._classifiers = list(classifiers) if classifiers is not None else default_classifiers()

    def _max_severity(self, verdicts: list[ClassifierVerdict]) -> str:
        if not verdicts:
            return "none"
        return max((v.severity for v in verdicts), key=lambda s: SEVERITY_ORDER.index(s))
```

- 用 `is not None` 而不是 `or`：显式传入空列表 `Router([])` 时就真的没有分类器（所有输出都是 log），而不会悄悄回退到默认分类器。
- `list(classifiers)` 把任意可迭代对象（如生成器）固定成列表，因为后面要多次遍历。
- `max(..., key=...)`：比较的不是字符串本身（字符串按字母序 `"high" < "low" < "medium" < "none"`，完全不对），而是它在 `SEVERITY_ORDER` 中的下标。
- 空判决列表返回 `"none"`，避免 `max()` 对空序列抛 `ValueError`。
- ⚠️ `Router()` 无法传入真实的 system prompt：默认分类器用的是写死的演示 prompt。要检测自己产品的泄漏，必须 `Router(default_classifiers(my_prompt))`。

### 3.4 叠加打码

```python
    def _apply_redactors(self, text: str, verdicts: list[ClassifierVerdict]) -> str:
        out = text
        for c in self._classifiers:
            for v in verdicts:
                if v.name == getattr(c, "name", "") and v.severity != "none":
                    out = c.redact(out)
                    break
        return out
```

- 外层按**分类器顺序**遍历（toxicity → pii → leakage），内层找与之同名、且 severity ≠ none 的判决；找到就调用该分类器的 `redact`，并 `break`（每个分类器最多打码一次）。
- 每次打码的输入是上一次的输出 `out`，所以多个 redactor 会**叠加**。讲义："Redaction is independent so a toxicity-and-PII output flows through both redactors."
- **low 的分类器也会打码**：只要最大 severity 是 medium，所有非 none 的分类器都执行 redactor。例如 email（medium）+ 一句 `idiot`（low），两者都会被打码（测验 Q11）。
- `getattr(c, "name", "")`：分类器没有 `name` 属性时返回空串，不报错。
- 时间复杂度 O(分类器数 × 判决数)，对 3 个分类器无所谓；用 `{v.name: v for v in verdicts}` 建索引可以变成 O(n)。
- ⚠️ 两种"打码无效"的情况，路由器都不会察觉：
  1. redactor 找不到要替换的内容（instruction leakage 的模糊判定 vs 精确打码，测验 Q10）；
  2. 通过 `decide(text, verdicts)` 传入的判决来自**不在 `self._classifiers` 中**的分类器（名字对不上），对应的 redactor 根本不会被调用。

### 3.5 run 与 decide：策略表

```python
    def run(self, text: str) -> Action:
        verdicts: list[ClassifierVerdict] = []
        for c in self._classifiers:
            v = c.classify(text)
            verdicts.append(v)
        return self.decide(text, verdicts)

    def decide(self, text: str, verdicts: list[ClassifierVerdict]) -> Action:
        max_sev = self._max_severity(verdicts)
        metadata = {
            "verdict_count": len(verdicts),
            "fired": [v.name for v in verdicts if v.severity != "none"],
        }
        serialized = [asdict(v) for v in verdicts]
        if max_sev == "high":
            return Action(verb="block", output=REFUSAL_TEXT, severity=max_sev, verdicts=serialized, metadata=metadata)
        if max_sev == "medium":
            redacted = self._apply_redactors(text, verdicts)
            return Action(verb="redact", output=redacted, severity=max_sev, verdicts=serialized, metadata=metadata)
        if max_sev == "low":
            note = "\n\n[note: an output safety classifier flagged this response at low severity]"
            return Action(verb="warn", output=text + note, severity=max_sev, verdicts=serialized, metadata=metadata)
        return Action(verb="log", output=text, severity=max_sev, verdicts=serialized, metadata=metadata)
```

- `run` 与 `decide` 分开：`run` 是"分类 + 决策"的快捷方式；`decide` 允许调用方传入**外部计算好的判决**（例如并行跑的神经分类器结果，或测试里手工构造的判决）。
- 分类器是**串行**调用的；讲义提到的"与 token streaming 并行"在本节没有实现（第 87 节做了一个简化版的流式中止）。
- `metadata["fired"]` 列出**所有**非 none 的分类器，而不只是导致最终动作的那个。block 时如果 toxicity 是 low、pii 是 high，`fired` 是 `["toxicity", "pii"]`，要知道是谁触发了 block 还得去看 `verdicts`。
- 四个分支的输出：

| 最大 severity | verb | output |
|---|---|---|
| high | block | `REFUSAL_TEXT`（原文完全丢弃） |
| medium | redact | 所有非 none 分类器的 redactor 叠加后的文本 |
| low | warn | **原文** + `\n\n[note: ...]`（不打码） |
| none | log | 原文 |

- ⚠️ warn 分支不打码：单个电话号码（PII low）会原样发给用户（测验 Q8）。
- ⚠️ warn 直接在文本末尾追加提示：如果模型输出是 JSON 或代码，追加后格式就坏了。生产中提示应放在响应的元数据里，由前端渲染。
- `asdict(v)` 递归地把 dataclass 转成字典（`findings` 列表会被复制）。

### 3.6 Demo fixture 与报告

```python
_DEMO_OUTPUTS: list[dict[str, str]] = [
    {"case": "clean response", "output": "Here is a Python function that reverses a linked list ..."},
    {"case": "low toxicity", "output": "You moron, your code is full of bugs."},
    {"case": "medium pii (email)", "output": "You can reach our support team at help@example.com for follow up."},
    {"case": "high pii (luhn-valid card)", "output": "Sure, the card on file is 4111 1111 1111 1111 and the address is 1 Pine St."},
    {"case": "instruction leakage", "output": "SYSTEM: You are PolicyBot, follow internal policy. As PolicyBot I will now answer."},
    {"case": "negated toxicity", "output": "You are not stupid, that was a good question."},
]
```

- 6 个用例对应 4 种动作：log ×2（干净 + 被否定）、warn ×1、redact ×1、block ×2。
- `4111 1111 1111 1111` 是公开的 Visa **测试卡号**，能通过 Luhn。
- 讲义说 demo 会"confirms that block, redact, warn, and log each fire on at least one fixture"，但代码只是打印，**没有断言**；四种动作是否都出现只能靠人眼看。可以在 `demo()` 末尾加 `assert {"block","redact","warn","log"} <= {r["verb"] for r in report}`。

```python
def write_report(actions: list[dict[str, object]]) -> Path:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    path = OUTPUTS / "classifier_report.json"
    path.write_text(json.dumps({"actions": actions}, indent=2) + "\n")
    return path


def demo() -> int:
    router = Router()
    report = []
    print(f"  {'case':28} {'verb':8} {'severity':9} fired")
    for fixture in _DEMO_OUTPUTS:
        action = router.run(fixture["output"])
        fired = ",".join(action.metadata["fired"]) or "-"
        print(f"  {fixture['case']:28} {action.verb:8} {action.severity:9} {fired}")
        report.append({... "input": fixture["output"], "verdicts": action.verdicts, ...})
    path = write_report(report)
    ...
    return 0


if __name__ == "__main__":
    sys.exit(demo())
```

- `mkdir(parents=True, exist_ok=True)`：目录不存在就递归创建，已存在也不报错。
- 每次运行都会**覆盖** `outputs/classifier_report.json`；因为所有分类器都是确定性的，重跑得到的内容逐字节相同（已用 `diff` 验证）。
- `",".join([]) or "-"`：空列表 join 得空串，`or` 回退为 `"-"`。
- `{fixture['case']:28}`：f-string 格式符，左对齐、宽 28 字符。
- `sys.exit(demo())`：把 `demo()` 的返回值作为进程退出码（0 表示成功），方便在 CI 中使用。
- ⚠️ 报告里保存了原始 `input` 和带原文的 `findings`（如 `card '4111 1111 1111 1111'`）。演示无妨，但如果照搬到生产 trace，就是把被拦截的 PII 写进了日志。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 取最大 severity | 简单、可解释、保守（block 优先） | 不能表达"PII 比 toxicity 更重要"；讲义练习 2 要求按分类器加权 |
| severity → action 固定映射 | 四档动作覆盖常见处理方式 | 无法按分类器、按类型细化（如"卡号 always block、自己的邮箱放行"）；可改为可配置的策略表 |
| `run` / `decide` 分离 | 可以接入外部或并行计算的判决，测试方便 | 外部判决的分类器若不在 `self._classifiers` 中，打码会被静默跳过 |
| medium 时所有非 none 的 redactor 都执行 | 讲义要求的"叠加打码" | 不检查打码是否生效；应 fail-closed（打码无效则升级为 block） |
| warn = 原文 + 文字提示 | 实现简单，用户能看到提示 | 低危 PII 原样发出；会破坏结构化输出 |
| block 返回固定拒答 | 不泄漏任何原文 | 用户不知道原因；可附上不含敏感内容的类别说明 |
| `Action.verdicts` 存字典 | 直接 JSON 序列化 | 失去类型信息；findings 含原文 PII |
| 串行调用分类器 | 规则分类器零延迟，无需并发 | 神经分类器时应并发调用（`asyncio.gather` 或线程池）并设超时 |
| 默认 system prompt 写死 | 演示开箱即用 | 真实部署必须传入实际 system prompt |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多行括号 import | `from classifiers import (\n SEVERITY_ORDER, ...)` | 括号内可以换行，便于一行一个名字 |
| `pathlib.Path` | `Path(__file__).parent`、`HERE.parent / "outputs"` | 面向对象的路径操作，`/` 拼接路径 |
| `__file__` | `Path(__file__)` | 当前模块文件的路径 |
| `@dataclass` + `field(default_factory=...)` | `Action` 的 `verdicts`、`metadata` | 可变默认值必须用工厂函数 |
| `dataclasses.asdict` | `[asdict(v) for v in verdicts]` | 递归转为字典，便于 JSON 序列化 |
| 类型注解与联合类型 | `Iterable[object] \| None`、`list[dict[str, object]]` | 配合 `from __future__ import annotations` 使用 |
| `is not None` 判断 | `list(classifiers) if classifiers is not None else ...` | 区分"没传"和"传了空列表" |
| `max` 的 `key` + `lambda` | `max(..., key=lambda s: SEVERITY_ORDER.index(s))` | 按自定义规则比较 |
| 生成器表达式 | `(v.severity for v in verdicts)` | 惰性生成，不建中间列表 |
| `getattr` 带默认值 | `getattr(c, "name", "")` | 属性不存在时返回默认值而不抛异常 |
| `for ... break` | `_apply_redactors` 内层循环 | 找到第一个匹配就跳出内层循环 |
| 列表推导式带条件 | `[v.name for v in verdicts if v.severity != "none"]` | 过滤 + 映射一步完成 |
| 字符串拼接 | `text + note` | 在原文末尾追加提示 |
| f-string 宽度格式 | `{action.verb:8}`、`{'case':28}` | 左对齐填充到指定宽度（字符串默认左对齐） |
| `or` 提供默认值 | `",".join(...) or "-"` | 空串为假值 |
| `json.dumps(indent=2)` | `write_report` | 格式化输出 JSON |
| `Path.mkdir` / `write_text` | `OUTPUTS.mkdir(parents=True, exist_ok=True)` | 建目录、写文件 |
| `sys.exit(返回值)` | `sys.exit(demo())` | 设置进程退出码 |
| `if __name__ == "__main__"` | 文件末尾 | 被 `import`（如 tests.py、第 87 节）时不会运行 demo |
| `unittest.TestCase` / `setUp` | tests.py | 每个测试方法前运行 `setUp`，得到全新的分类器实例 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在本节目录的副本中执行，避免覆盖仓库文件；生成的 JSON 与仓库中 `outputs/classifier_report.json` 逐字节相同）：

```text
Content classifier router demo

  case                         verb     severity  fired
  clean response               log      none      -
  low toxicity                 warn     low       toxicity
  medium pii (email)           redact   medium    pii
  high pii (luhn-valid card)   block    high      pii
  instruction leakage          block    high      instruction-leakage
  negated toxicity             log      none      -

  artifact written to .../outputs/classifier_report.json
```

逐行解读：

| 用例 | 关键判决 | 最终 output |
|---|---|---|
| clean response | 三个都是 none | 原文 |
| low toxicity | toxicity low（score `0.6000000000000001`） | 原文 + `\n\n[note: an output safety classifier flagged this response at low severity]` |
| medium pii (email) | pii medium 0.65 | `You can reach our support team at [redacted-email] for follow up.` |
| high pii (luhn-valid card) | pii high 0.65 | `I cannot share that. The response was blocked by an output safety classifier.` |
| instruction leakage | leakage high 0.870 | 同上，拒答文本 |
| negated toxicity | `not` 在 `stupid` 左侧 20 字符内 → 跳过 | 原文 |

- 四种动作都至少出现一次，符合讲义描述。
- "low toxicity" 是 warn：**辱骂原样发出**，只附一行提示。这是"1 处命中 = low"的直接后果。
- 卡号用例的 severity 是 high，score 却只有 0.65（PII 的 score 只看发现数量）。
- 泄漏用例的分数 0.870 只比 high 线（0.85）高一点，被 block；如果分数落在 medium，redactor 会把第一行替换成 `[redacted-system-prompt]`。

另外几组路由实测（用于测验）：

```text
"Call me at 555-123-4567 tonight."                       → warn   （电话原样保留）
"you are policybot and you follow the internal policy"   → redact （medium，但 output 与原文完全相同）
"Email bob@corp.io or call 555-867-5309, you idiot."     → redact → "Email [redacted-email] or call [redacted-phone], you [redacted-language]."
```

---

## 7. 动手改一改

1. **自检断言**：在 `demo()` 末尾断言四种 verb 都至少出现一次，否则返回非 0 退出码，让 CI 能发现回归。
2. **fail-closed 打码**：在 `decide` 的 medium 分支中，若 `_apply_redactors` 的结果与原文相同，升级为 block 并在 `metadata` 中记录原因；为 `"you are policybot and you follow the internal policy"` 写一个测试。
3. **讲义练习 2：按分类器加权**：给 `Router` 增加 `weights={"pii": +1, "toxicity": 0}` 之类的参数，把加权后的 severity 截断到 high，在同一组 fixture 上对比 verb 的变化（例如 email 由 redact 升为 block）。
4. **讲义练习 3：置信度阈值**：实现"score 低于阈值则降一级"，扫描阈值 0.0–0.9，报告 block 率（参考测验 Q12：6 个 fixture 上 0.333 → 0.167 → 0.0），并说明卡号被降级的问题。
5. **warn 不改正文**：把提示从 `output` 中移出，放进 `metadata["notice"]`；再让 warn 对 PII 类判决也执行打码，比较两种策略。
6. **进阶：并发与超时**：把 `run` 改成 `async`，每个分类器用 `asyncio.wait_for` 设超时；超时的分类器视为 high（fail-closed）或 none（fail-open），并在 `metadata` 中记录，讨论两种选择各适合什么场景。

---

## 8. 常见坑

- **直接比较 severity 字符串**：`max(["low", "high"])` 得到 `"low"`（字母序），必须按 `SEVERITY_ORDER` 的下标比较。
- **认为 warn 会打码**：只有 medium 才执行 redactor，low 的 PII 会原样发出。
- **以为 `metadata["fired"]` 就是触发动作的分类器**：它包含所有非 none 的分类器。
- **用 `decide` 传入外部判决**：判决的 `name` 必须与 `self._classifiers` 中某个分类器的 `name` 完全一致，否则不会打码，且没有任何报错。
- **在 `code/` 以外的目录运行测试**：`from classifiers import ...` 依赖当前目录在 `sys.path` 中，应 `cd code` 再运行。
- **重跑 demo 改动了仓库文件**：`write_report` 会覆盖 `outputs/classifier_report.json`；内容确定，但在只读或共享目录中运行要注意。
- **把报告当 trace 模板**：报告保存了原始输入和带原文的 findings，直接用于生产日志会泄漏 PII。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：

```bash
python3 -m unittest tests -v
# 或
python3 -m pytest -q tests.py
```

实际结果：`Ran 18 tests in 0.002s — OK`；pytest 为 `18 passed in 0.02s`。

| 测试类 | 测试 | 输入 | 验证的性质 |
|---|---|---|---|
| `TestToxicity` | `test_clean_text_is_none` | `That was a clear and helpful answer.` | 干净文本不误报 |
| | `test_single_term_low` | `You are a moron.` | 1 处命中 → low，score > 0 |
| | `test_three_terms_high` | `You moron, you idiot, you worthless person.` | 3 处命中 → high |
| | `test_negation_window_skips` | `You are not stupid, ...` | 否定窗口生效 |
| | `test_redact_replaces_term` | `You are a moron and a scumbag.` | 打码后出现 `[redacted-language]` 且不再含 `moron` |
| `TestPII` | `test_email_is_medium` | `hello@example.com` | email → medium |
| | `test_valid_card_is_high` | `4111 1111 1111 1111` | Luhn 合法的卡号 → high |
| | `test_invalid_card_not_flagged` | `1234 5678 9012 3456` | Luhn 不合法 → 不是 high（实际为 none） |
| | `test_redact_email_and_card` | email + 卡号 | 两种标签都出现 |
| | `test_ip_address_low` | `192.168.1.5` | 单个 IP → low |
| `TestInstructionLeakage` | `test_leaks_system_prompt` | 复述 `Refuse harmful requests. Cite sources.` 的句子 | 改写式复述能被发现（实测 score 0.673，low） |
| | `test_no_overlap_is_none` | pasta 菜谱 | 无关文本 → none |
| `TestRouterDecisions` | `test_clean_is_log` | 俳句请求 | none → log |
| | `test_low_toxicity_is_warn` | `You moron, ...` | low → warn，output 含 `[note` |
| | `test_email_is_redact` | `lee@example.com` | medium → redact，含 `[redacted-email]` |
| | `test_card_is_block` | 卡号 | high → block，output 不含 `4111` |
| `TestRouterAggregation` | `test_block_dominates_redact` | 卡号 + email + `moron` | high 压过 medium 和 low |
| | `test_metadata_lists_fired` | `lee@example.com is great.` | `metadata["fired"]` 含 `pii` |

值得注意的细节：

- `test_invalid_card_not_flagged` 用的是 `assertNotIn("high", v.severity)`——这是**子串检查**（检查字符串 `"high"` 是否出现在 `"none"` 里），碰巧能用，但 `assertNotEqual(v.severity, "high")` 才表达了本意。
- `test_leaks_system_prompt` 接受 low/medium/high 任一结果，断言较宽松；实测只是 low（0.673），离阈值 0.55 不远，换个说法就可能变成 none。
- `setUp` 在每个测试方法前运行，保证每个测试拿到全新的分类器实例。

**测试没有覆盖的地方**（也是本节最容易出问题的地方）：

- medium 判决但 redactor 无效（leakage 改写复述）——路由器返回 redact 却原样输出；
- warn 分支不打码（单个电话）；
- 否定窗口漏报（`No way, you idiot.`）、复数漏报（`idiots`）；
- 长输出夹带完整 system prompt 时的余弦稀释；
- SSN、电话、多处 PII 达到 medium 的分支；
- `ToxicityClassifier(terms=[])` 会把一切判为 high；
- `Router([])`、`decide(text, [])` 等边界，以及 `write_report` 的输出格式。

建议把测验 Q7–Q10 中的反例补成测试：先写成 `expectedFailure` 记录已知缺陷，修复后再改成正常断言。
