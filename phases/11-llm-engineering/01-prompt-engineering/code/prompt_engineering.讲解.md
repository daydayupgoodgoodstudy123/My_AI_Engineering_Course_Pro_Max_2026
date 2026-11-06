# 代码讲解 · prompt_engineering.py

> **所属小节**：阶段 11 · LLM 工程 · 第 01 节 Prompt Engineering：技术与模式 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python prompt_engineering.py`（无参数） ｜ **依赖**：仅 Python 标准库（`json`、`time`、`hashlib`、`re`）；**不调用任何真实 API**，所有模型回复都是模拟的，无需 API key、无需网络。同目录的 `main.ts` 是同一套逻辑的 TypeScript 版本。

---

## 1. 这份代码在考察什么

讲义的 "Build It" 部分要求搭一个**prompt 测试 harness**。这份代码就是它的完整实现，分五层：

1. **模式库**（`PROMPT_PATTERNS`）：讲义中的 10 种 prompt 模式，每种是"模板 + 变量列表 + 推荐 temperature + 说明"的结构化数据。
2. **构建器**（`build_prompt` / `build_multi_turn`）：填变量、校验缺失、组装成 system + user。
3. **多厂商请求格式化**（`format_*_request`）：同一个 prompt 转成 OpenAI、Anthropic、Google 三种请求体，体现讲义"三家对 system 的处理方式不同"。
4. **模拟调用与测试**（`simulate_llm_call` / `run_prompt_test`）：用固定文本代替真实 API 响应。
5. **打分与对比**（`score_response` / `compare_models` / `run_test_suite`）：按长度、关键词、禁用语、格式打分，排序并统计"胜者"。

对应讲义的核心观点："把 prompt 当作可测试的工程对象"——模式化、参数化、可跨模型比较、用指标说话。

> 一句话：**这是一个"能跑通的骨架"，而不是一个"能比较模型的评测"**。模拟响应让所有模型得分完全相同，排名只由字典顺序决定；打分器本身也有若干误判。读懂这些问题，正是本节"诊断 prompt 与评测"能力的练习。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROMPT_PATTERNS` | 字典（10 项） | 每个模式的 `name / template / variables / temperature / description` | 10 种 prompt 模式 |
| `MODEL_CONFIGS` | 字典（3 项） | 模型键 → 厂商、模型 ID、`max_tokens`、上下文窗口 | 多模型 |
| `build_prompt` | 函数 | 校验变量 → `str.format` 渲染 → 返回 system/user/temperature/metadata | prompt 组装 |
| `build_multi_turn` | 函数 | 生成 OpenAI 风格的多轮 `messages`（未被调用） | 多轮对话、prefill |
| `format_openai_request` 等 3 个 | 函数 | 转换为各家请求体 | 跨厂商差异 |
| `FORMATTERS` | 字典 | 厂商名 → 格式化函数（分派表） | 策略模式 |
| `simulate_llm_call` | 函数 | 睡 10ms，返回写死的回复、token 数、延迟 | 模拟 API |
| `run_prompt_test` | 函数 | 对每个模型：格式化 → 模拟调用 → 收集结果 | 多模型测试 |
| `score_response` | 函数 | 计算各项指标并取平均为 `composite_score` | 规则式评测 |
| `compare_models` | 函数 | 给每个模型打分并按分数降序排序 | 模型对比 |
| `TEST_SUITE` | 列表（5 项） | persona / few_shot / CoT / template_fill / guardrail 五个测试 | 测试用例 |
| `run_test_suite` / `run_pattern_catalog_demo` / `run_single_prompt_demo` | 函数 | 三个演示入口 | 演示 |

数据流：`TEST_SUITE[i]` → `build_prompt` → `run_prompt_test`（`FORMATTERS[provider]` → `simulate_llm_call`）→ `compare_models`（`score_response`）→ 打印排名 → 统计每个测试的第一名。

---

## 3. 逐段精讲

### 3.1 模式库：把 prompt 当数据

```python
PROMPT_PATTERNS = {
    "persona": {
        "name": "Persona Pattern",
        "template": (
            "You are {role} with {experience}.\n"
            "Your communication style is {style}.\n"
            "You prioritize {priority}.\n\n"
            "{task}"
        ),
        "variables": ["role", "experience", "style", "priority", "task"],
        "temperature": 0.7,
        "description": "Activates a specific expert distribution in the model's training data",
    },
    ...
```

- 括号里相邻的字符串字面量会被 Python **自动拼接**，便于把长模板分行书写。
- `{role}` 等是 `str.format` 的命名占位符。
- 每个模式自带推荐 temperature，与讲义的表格一致：确定性任务（few_shot、template_fill、boundary）用 0.0；推理/分解/护栏用 0.3；critique、audience_adapt 用 0.5；persona、meta_prompt 用 0.7。
- 把模板做成数据而不是散落在代码里的字符串，好处是可以统一校验、统计、版本化，也方便 A/B 测试。
- 注意 `guardrail` 与 `boundary` 两个模式把规则和用户输入（`{question}`、`{user_input}`）写在**同一个模板**里——它们最终都会进入 user 消息（见 3.3）。

### 3.2 模型配置

```python
MODEL_CONFIGS = {
    "gpt-4o": {"provider": "openai", "model": "gpt-4o", "max_tokens": 2048, "context_window": 128_000},
    "claude-3.5-sonnet": {"provider": "anthropic", "model": "claude-sonnet-5", ..., "context_window": 1_000_000},
    "gemini-1.5-pro": {"provider": "google", "model": "gemini-2.5-pro", ..., "context_window": 1_000_000},
}
```

- `128_000` 中的下划线是数字分隔符，只为可读性。
- ⚠️ 字典的**键**（显示名）与实际发送的 `model` 字段不一致：键叫 `claude-3.5-sonnet`，请求里却是 `claude-sonnet-5`；键叫 `gemini-1.5-pro`，请求里是 `gemini-2.5-pro`。打印结果和模拟回复文本用的都是旧名字。讲义表格里列的又是另一批型号（GPT-5、Claude Opus 4.7、Gemini 3 Pro 等）。接入真实 API 前应统一命名，否则日志与实际调用的模型对不上。
- `context_window` 在代码里没有被使用（没有做长度检查）。

### 3.3 构建器

```python
def build_prompt(pattern_name, variables, system_override=None):
    pattern = PROMPT_PATTERNS.get(pattern_name)
    if not pattern:
        raise ValueError(f"Unknown pattern: {pattern_name}. Available: {list(PROMPT_PATTERNS.keys())}")

    missing = [v for v in pattern["variables"] if v not in variables]
    if missing:
        raise ValueError(f"Missing variables for {pattern_name}: {missing}")

    rendered = pattern["template"].format(**variables)
    system = system_override or f"You are an AI assistant using the {pattern['name']}."
    return {
        "system": system,
        "user": rendered,
        "temperature": pattern["temperature"],
        "pattern": pattern_name,
        "metadata": {...},
    }
```

- `dict.get` 找不到时返回 `None`，配合 `if not pattern` 给出带可选列表的友好报错。
- 列表推导式找出缺失变量，**先校验再渲染**，比让 `format` 抛 `KeyError` 更清楚。
- `format(**variables)`：`**` 把字典展开为关键字参数。只解析**模板**中的花括号，变量值里的花括号不会被再解析（所以 few-shot 的 JSON 示例作为变量传入是安全的）；但如果模板本身含字面量 `{"a": 1}`，会抛 `KeyError: '"a"'`，需要写成 `{{"a": 1}}`（测验 Q10，已实测）。
- 多余变量被静默忽略，却被记入 `metadata["variables_used"]`。
- `system_override or 默认值`：传入空字符串 `""` 也会回退到默认值（`or` 判断的是真假值，不是 `None`）。
- ⚠️ **设计问题**：渲染后的整段模板全部进入 **user**，system 只是一句 "You are an AI assistant using the Persona Pattern."。于是：
  - persona 模式中，"DevOps engineer" 的角色写在 user 里，与 system 的 "AI assistant" 身份并存；
  - guardrail/boundary 模式中，规则与用户问题在同一条 user 消息中，没有分隔、没有信任边界，最容易被注入覆盖。
  - 讲义自己说 system message 是 "highest-priority context"。更合理的做法是让模式区分 system 模板与 user 模板，并用 XML 标签包裹用户内容（测验 Q11 给出了重构示例）。

```python
def build_multi_turn(pattern_name, turns, system_override=None):
    ...
    messages = [{"role": "system", "content": system}]
    for role, content in turns:
        messages.append({"role": role, "content": content})
```

- 生成 OpenAI 风格的 messages 列表；`for role, content in turns` 对元组解包。传入 `("assistant", "{")` 作为最后一轮，就构成了讲义所说的 assistant prefill。
- ⚠️ 这个函数在主流程中没有被调用；它产出的 `{"role": "system"}` 消息只适用于 OpenAI 格式——Anthropic 的 system 是顶层参数，不能放在 messages 里。

### 3.4 三家请求格式化与分派表

```python
def format_openai_request(prompt):
    return {
        "model": MODEL_CONFIGS["gpt-4o"]["model"],
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
        "temperature": prompt["temperature"],
        "max_tokens": MODEL_CONFIGS["gpt-4o"]["max_tokens"],
    }

def format_anthropic_request(prompt):
    return {
        "model": ...,
        "system": prompt["system"],
        "messages": [{"role": "user", "content": prompt["user"]}],
        ...
    }

def format_google_request(prompt):
    return {
        "model": ...,
        "contents": [
            {"role": "user", "parts": [{"text": f"{prompt['system']}\n\n{prompt['user']}"}]},
        ],
        "generationConfig": {"temperature": ..., "maxOutputTokens": ...},
    }

FORMATTERS = {"openai": format_openai_request, "anthropic": format_anthropic_request, "google": format_google_request}
```

| 厂商 | system 放在哪 | 参数命名 |
|------|-------------|---------|
| OpenAI | `messages` 中 `role: "system"` | `temperature`、`max_tokens` |
| Anthropic | 顶层 `system` 字段 | `max_tokens` 必填 |
| Google（本代码） | 拼进第一条 user 文本的开头 | `generationConfig.maxOutputTokens`（驼峰） |

- ⚠️ Google 的写法与讲义 Use It 一节不一致：讲义说 Gemini 把 `system_instruction` 当作**配置字段**，示例也是 `GenerateContentConfig(system_instruction=...)`。拼接进 user 会让 system 指令失去特殊地位。
- ⚠️ 每个格式化函数都写死了 `MODEL_CONFIGS["gpt-4o"]` 这样的键，同一厂商想测第二个模型就要改函数。更好的做法是把 `config` 作为参数传进来（`main.ts` 中的 `formatOpenAI(p, cfg)` 就是这样做的）。
- `FORMATTERS` 是"字符串 → 函数"的**分派表**：`run_prompt_test` 只需 `FORMATTERS[config["provider"]](prompt)`，新增厂商不用改 if/else。

### 3.5 模拟调用

```python
def simulate_llm_call(model_name, request):
    time.sleep(0.01)
    prompt_hash = hashlib.md5(json.dumps(request, sort_keys=True).encode()).hexdigest()[:8]
    simulated_responses = {
        "gpt-4o": {
            "response": (f"[GPT-4o response {prompt_hash}] This is a simulated response. ..."),
            "tokens_used": {"prompt": 150, "completion": 45, "total": 195},
            "latency_ms": 850,
            "finish_reason": "stop",
        },
        ...
    }
    return simulated_responses.get(model_name, {"response": "Unknown model", "tokens_used": {}, "latency_ms": 0})
```

- `json.dumps(..., sort_keys=True)` 让字典序列化结果稳定，`md5(...).hexdigest()[:8]` 取前 8 位十六进制作为"请求指纹"，同样的请求总得到同样的指纹——这是做**请求缓存**、**去重**时的常用技巧。
- 三家的 `finish_reason` 取值不同（`stop` / `end_turn` / `STOP`），模拟了真实 API 的差异；接入真实 API 时需要统一映射。
- token 数与延迟是**写死的常量**，与 prompt 长度无关；回复文本也与任务无关。
- `.get(model_name, 默认值)`：未知模型返回占位结果而不是抛异常。

### 3.6 多模型测试

```python
def run_prompt_test(prompt, models=None):
    if models is None:
        models = list(MODEL_CONFIGS.keys())
    results = {}
    for model_name in models:
        config = MODEL_CONFIGS[model_name]
        formatter = FORMATTERS[config["provider"]]
        request = formatter(prompt)
        start = time.time()
        response = simulate_llm_call(model_name, request)
        wall_time = (time.time() - start) * 1000
        results[model_name] = {..., "wall_time_ms": round(wall_time, 1), "request_payload": request}
    return results
```

- `models=None` 再在函数内赋默认值，是避免"可变默认参数"陷阱的标准写法。
- 同时记录了两种延迟：`api_latency_ms`（模拟值）和 `wall_time_ms`（实测墙钟，约 10ms 的 sleep）。接入真实 API 后，应记录墙钟时间并区分首 token 延迟与总延迟。
- 串行调用；真实场景应并发（`asyncio` 或线程池）并加超时、重试、限流（第 11 节）。
- 保存 `request_payload` 便于复现与调试——这是好习惯。

### 3.7 打分器

```python
def score_response(response_text, criteria):
    scores = {}
    if "max_words" in criteria:
        word_count = len(response_text.split())
        scores["word_count"] = word_count
        scores["length_compliant"] = word_count <= criteria["max_words"]
    if "required_keywords" in criteria:
        found = [kw for kw in criteria["required_keywords"] if kw.lower() in response_text.lower()]
        scores["keyword_coverage"] = len(found) / len(...) if criteria["required_keywords"] else 1.0
    if "forbidden_phrases" in criteria:
        ...
        scores["no_violations"] = len(violations) == 0
    if "expected_format" in criteria:
        ...  # json / bullet_points / numbered_list
    total = 0
    count = 0
    for key, value in scores.items():
        if isinstance(value, bool):
            total += 1.0 if value else 0.0
            count += 1
        elif isinstance(value, float) and 0 <= value <= 1:
            total += value
            count += 1
    scores["composite_score"] = round(total / count, 3) if count > 0 else 0.0
    return scores
```

- 汇总规则：**布尔值**算 0/1，**[0,1] 内的浮点数**原样计入，其他（`word_count` 这样的整数、列表）不计入。`isinstance(value, bool)` 必须放在前面检查——`bool` 是 `int` 的子类。
- 所有指标**等权平均**，没有主次之分。
- ⚠️ 已实测的误判（测验 Q9）：
  - 关键词是**子串**匹配：`"API"` 命中 "capital"、`"key"` 命中 "monkey"；
  - JSON 检查只看 `json.loads` 是否成功：`"42"` 判为合法；带 `Output:` 前缀（few-shot 示例本身就是这种写法）或 ```` ```json ```` 围栏的回答判为非法；
  - `bullet_points` 只认以 `-`、`*`、`1` 开头的行：`2. xxx` 不算，`100 users…` 却算；
  - 没有任何标准时返回 0.0，而不是"不适用"；
  - 形式指标无法判断内容对错：思维链测试中一个**答错**的回答也能拿满分 1.0（测验 Q12）。
- `numbered_list` 分支使用 `re.MULTILINE`，让 `^` 匹配每一行的行首。

### 3.8 对比与排序

```python
def compare_models(test_results, criteria):
    comparison = {}
    for model_name, result in test_results.items():
        scores = score_response(result["response"], criteria)
        comparison[model_name] = {"scores": scores, "tokens": result["tokens"], "latency_ms": result["api_latency_ms"]}
    ranked = sorted(
        comparison.items(),
        key=lambda x: x[1]["scores"]["composite_score"],
        reverse=True,
    )
    return comparison, ranked
```

- `comparison.items()` 产生 `(模型名, 数据)` 元组；`lambda x: x[1][...]` 取出分数作为排序键。
- `sorted` 是**稳定排序**：分数相同的项保持原有顺序，`reverse=True` 也不会打乱并列项的相对顺序。
- ⚠️ 本次运行中三个模型在每个测试里都**并列**，于是排名完全由 `MODEL_CONFIGS` 的插入顺序决定，gpt-4o 永远第一。

### 3.9 测试套件与汇总

```python
    model_wins = {}
    for result in all_results:
        if result["rankings"]:
            winner = result["rankings"][0][0]
            model_wins[winner] = model_wins.get(winner, 0) + 1
    for model, wins in sorted(model_wins.items(), key=lambda x: x[1], reverse=True):
        print(f"  {model}: {wins} wins out of {len(all_results)} tests")
```

- `dict.get(key, 0) + 1` 是计数的惯用写法（也可用 `collections.Counter`）。
- ⚠️ "取第一名计一胜"在并列时会制造虚假的胜者。输出 `gpt-4o: 5 wins out of 5 tests` 完全是平局 + 稳定排序的产物，不包含任何关于模型能力的信息。
- `TEST_SUITE` 只覆盖 5 种模式；讲义练习 1 要求补齐 meta_prompt、decomposition、critique、audience_adapt、boundary 五个。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 模式写成结构化字典 | 统一管理、可校验、可版本化 | 单一 `template` 无法区分 system/user；生产中拆成两段并纳入 prompt 版本管理 |
| `str.format` 渲染 | 标准库、零依赖 | 模板中的字面花括号需转义；复杂逻辑可用 Jinja2 |
| 渲染结果全部进 user | 实现简单 | 角色与规则失去 system 的优先级，guardrail 易被注入 |
| 每厂商一个格式化函数 + 分派表 | 隔离 API 差异 | 写死模型键；Google 未用 `systemInstruction` |
| 模拟 API | 无 key、无费用、可离线运行 | 无法比较模型，所有分数并列；真实接入需替换 `simulate_llm_call`（讲义练习 2） |
| 规则式打分、等权平均 | 透明、确定、便宜 | 子串误判、格式过严或过松、不判断对错；生产中加 schema 校验、答案比对、LLM-as-judge |
| 取第一名计胜 | 直观 | 并列时失真；应报告平局或用次级指标并说明 |
| 推荐 temperature 绑定在模式上 | 讲义的经验值 | 应在评测中按任务调参，而非固定 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 相邻字符串自动拼接 | `("You are {role} with {experience}.\n" "Your communication ...")` | 括号内多个字面量会在编译期拼成一个字符串 |
| `str.format` 命名占位 | `pattern["template"].format(**variables)` | `{name}` 被同名关键字参数替换；字面 `{` 需写成 `{{` |
| `**` 字典解包 | `format(**variables)` | 把字典展开为关键字参数 |
| f-string 嵌套引号与表达式 | `f"{prompt['system']}\n\n{prompt['user']}"`、`f"{'=' * 60}"` | 花括号内可以写任意表达式；内外引号需不同 |
| f-string 格式符 | `{model_name:<25}`、`{score:>8.3f}`、`{tokens:>8}` | 左对齐宽 25、右对齐宽 8 保留 3 位小数 |
| 数字分隔符 | `128_000`、`1_000_000` | 下划线只为可读性 |
| 嵌套字典字面量 | `PROMPT_PATTERNS`、`MODEL_CONFIGS` | 配置即数据 |
| `dict.get` 带默认值 | `PROMPT_PATTERNS.get(pattern_name)`、`model_wins.get(winner, 0)` | 键不存在时返回 `None` 或指定默认值 |
| 列表推导式 + 条件 | `[v for v in pattern["variables"] if v not in variables]` | 过滤出缺失项 |
| `or` 提供默认值 | `system_override or f"..."` | 左边为假值（`None`、`""`）时取右边 |
| 函数作为字典的值 | `FORMATTERS = {"openai": format_openai_request, ...}` | 分派表；`FORMATTERS[p](prompt)` 直接调用 |
| `None` 作为默认参数 | `def run_prompt_test(prompt, models=None)` | 避免可变默认参数陷阱 |
| `try / except` 多异常 | `except (json.JSONDecodeError, TypeError):` | 用元组同时捕获多种异常 |
| `raise ValueError(...)` | `build_prompt` 中 | 参数不合法时主动报错 |
| `str.startswith(tuple)` | `line.startswith(("-", "*", "1"))` | 传元组表示"以其中任一开头" |
| 正则 `re.findall` + `re.MULTILINE` | `re.findall(r"^\d+\.", text, re.MULTILINE)` | 原始字符串 `r"..."` 避免反斜杠转义；`^` 匹配每行开头 |
| `isinstance` 与 bool/int 关系 | `isinstance(value, bool)` 放在 float 判断前 | `bool` 是 `int` 的子类 |
| 三元表达式 | `round(total / count, 3) if count > 0 else 0.0` | 一行内的条件取值 |
| `sorted` + `lambda` | `sorted(d.items(), key=lambda x: x[1]["scores"]["composite_score"], reverse=True)` | 按自定义键排序；稳定排序 |
| `hashlib` + `json.dumps(sort_keys=True)` | `hashlib.md5(...encode()).hexdigest()[:8]` | 生成稳定的请求指纹 |
| `time.time()` 计时 | `(time.time() - start) * 1000` | 秒转毫秒 |
| 元组解包遍历 | `for role, content in turns:`、`for model_name, data in ranked:` | 每个元素是二元组 |
| `json.dumps(..., indent=4)` | 打印 metadata | 美化输出 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时（如单独测试 `score_response`）不运行演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`python3 prompt_engineering.py`，约 0.23 秒；无需网络）。输出分三段：

**① 模式目录**：逐个打印 10 个模式的名称、说明、变量与推荐 temperature，例如：

```text
  [few_shot] Few-Shot Pattern
    Provides concrete examples to anchor the output format and style
    Variables: examples, input
    Recommended temp: 0.0
```

**② 单个 prompt 构建与测试**：

```text
  System message:
    You are an AI assistant using the Persona Pattern.     ← system 只有模式名
  User message:
    You are a senior DevOps engineer at Netflix with 8 years of infrastructure automation.   ← 角色在 user 里
  ...
  [gpt-4o]
    Response: [GPT-4o response 1b9e3322] This is a simulated response. ...
    Tokens: {'prompt': 150, 'completion': 45, 'total': 195}
    Latency: 850ms
  [claude-3.5-sonnet]
    Response: [Claude 3.5 Sonnet response fc7dc3c5] ...       ← 不同厂商请求体不同，指纹不同
```

**③ 测试套件**（节选）：

```text
  Test: Persona: Technical Writer
  gpt-4o                       0.667      195      850ms
  claude-3.5-sonnet            0.667      185      720ms
  gemini-1.5-pro               0.667      197      900ms
  ...
  Test: Few-Shot: Sentiment Analysis        → 三个模型都是 0.000
  Test: Chain-of-Thought: Math Problem      → 都是 0.500
  Test: Template Fill: Resume Extraction    → 都是 0.000
  Test: Guardrail: Scoped Assistant         → 都是 0.500

  SUMMARY: MODEL RANKINGS ACROSS ALL TESTS
  gpt-4o: 5 wins out of 5 tests
```

逐项解读：

- **Persona 0.667**：长度合规（True=1）、无禁用语（True=1）、关键词覆盖 0.0（模拟回复不含 "rate limit"、"API"、"requests"），平均 `2/3`。
- **Few-Shot 0.000**：JSON 解析失败（0）+ 无 "sentiment"（0）。
- **CoT 0.500**：关键词 0 + 长度合规 1。
- **Template Fill 0.000**：只有关键词一项且为 0。
- **Guardrail 0.500**：关键词 0 + 无禁用语 1。
- **汇总**：每个测试三者并列，稳定排序让 gpt-4o 永远排第一，所以"5 胜"毫无意义。要让 harness 真正有用，需要按讲义练习 2 接入真实 API，并修正打分器与平局处理。

---

## 7. 动手改一改

1. **补齐测试（讲义练习 1）**：为 meta_prompt、decomposition、critique、audience_adapt、boundary 各写一个 `TEST_SUITE` 用例，至少包含一个"越界问题应返回固定拒答"的 boundary 用例。
2. **修正打分器**：关键词按词边界匹配（符号类关键词保留子串匹配）、JSON 去掉 `Output:` 前缀与代码块围栏并要求是对象、列表正则 `^(\-|\*|\d+[.)])\s+`、无标准时返回 `None`（参考测验 Q9）。为这些修正写单元测试。
3. **处理平局**：在 `run_test_suite` 中检测最高分是否并列，并列时打印 "tie"，不计入任何模型的胜场；或者以 token 数、延迟作为次级排序键并在输出中注明。
4. **拆分 system/user**：给每个模式增加 `system_template` 与 `user_template`，规则和角色进 system，用户内容用 `<question>…</question>` 包裹；同时把 Google 格式化改成 `systemInstruction` 字段（参考测验 Q11）。
5. **注入测试（讲义练习 3）**：写 10 条 "Ignore previous instructions…" 类输入，对 guardrail 模式的新旧两种组织方式分别构造请求，设计一个检测"是否泄露规则/是否越界回答"的打分函数。
6. **接入真实 API（讲义练习 2）**：用环境变量读取 key，替换 `simulate_llm_call`，记录真实 token 用量、墙钟延迟与 `finish_reason`，同一 prompt 每个模型跑 5 次，报告均值与方差。

---

## 8. 常见坑

- **模板里直接写 JSON 示例**：`str.format` 会把 `{"a": 1}` 当占位符，抛 `KeyError`；改用变量传入或写成 `{{ }}`。
- **用模拟数据下结论**：模拟回复与任务无关，任何"哪个模型更好"的结论都是假的。
- **平局时取第一名**：稳定排序 + 字典顺序 = 永远是第一个模型赢。
- **子串匹配关键词**：短关键词（`api`、`key`）极易误判，评测分数虚高。
- **只看形式不看对错**：长度、关键词都满足的错误答案也能得满分。
- **few-shot 示例带 `Output:` 前缀，却用严格 JSON 解析**：示例格式与解析器的期望必须一致。
- **把规则和用户输入拼在一起**：没有信任边界，注入风险最高。
- **显示名与真实模型 ID 不一致**：日志里的 "claude-3.5-sonnet" 实际请求的是另一个模型，排查问题时会被误导。
- **`system_override=""` 想清空 system**：`or` 会回退到默认值；需要显式判断 `is None`。
