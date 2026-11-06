# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 50 节 研究假设生成器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，打印 JSON） ｜ **依赖**：仅 Python 标准库（`hashlib`、`json`、`math`、`re`、`dataclasses`、`typing`）；`str | None`、`list[str]` 等写法需要 Python 3.10+（文件已 `from __future__ import annotations`，注解本身在 3.7+ 也能解析）。

---

## 1. 这份代码在考察什么

这是"自主研究循环"（第 50–57 课）的第一块：把一个种子问题变成一个**有序的假设队列**。代码约 300 行，演示了讲义里的五个要点：

1. **结构化输出**：模型回复必须是 `<hypothesis><text>…<variables>…<metric>…[<baseline>…]</hypothesis>`，解析成带类型字段的 `Hypothesis`。
2. **Temperature ramp**：`n_passes` 轮，温度从 `t_min` 等间距升到 `t_max`。
3. **新颖性过滤**：用零依赖的 hashed embedding 计算与已接受假设的最小余弦距离，低于阈值丢弃。
4. **排名**：`0.4·novelty + 0.3·specificity + 0.3·testability`。
5. **确定性**：`MockLLM` 按 `(prompt 签名, 温度桶)` 查脚本，同样的输入永远得到同样的队列，便于测试。

> 一句话：**生成要发散（升温），入队要收敛（去重 + 排名），全程要可复现（mock + 稳定哈希）**。同时要看清"新颖性 = 与之前幸存者的词袋距离"这个定义有多粗糙——它是本节最值得讨论的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HASH_DIM = 128` | 常量 | 哈希 embedding 的维度 | feature hashing |
| `TAG_RE` | 预编译正则 | 匹配带标签的假设块（baseline 可选） | 结构化输出 |
| `Hypothesis` | dataclass | 一条假设及其分数；`to_dict` 做取整输出 | 假设记录 |
| `ParserError` | 异常类 | 回复不合 schema 时抛出 | 解析门控 |
| `_tokenise` / `hashed_embed` | 函数 | 小写英数分词 → md5 桶 + 符号 → L2 归一化 | 文本向量 |
| `cosine_distance` | 函数 | `1 − dot`（点积截断到 [−1, 1]） | 距离 |
| `parse_response` | 函数 | 正则提取并校验字段 | 解析器 |
| `temperature_bucket` | 函数 | 连续温度 → 4 个离散桶 | mock 的温度模拟 |
| `MockLLM` | 类 | 按 `(sha1 前 10 位, 桶)` 查脚本，`seed` 选第几条 | 可复现的假模型 |
| `GeneratorConfig` | dataclass | 轮数、温度范围、阈值、权重、种子；`schedule()` | 配置 |
| `GenerationLog` | dataclass | 每轮的温度、种子、接受 id 或拒绝原因、原文摘录 | 可观测性 |
| `HypothesisGenerator` | 类 | 三个子分数、新颖性、`run()` 主循环 | 生成器 |
| `build_demo_scripts` / `_demo` | 函数 | 4 个桶各 1 条脚本，跑 4 轮并打印 | 演示 |

数据流：`_demo` → `HypothesisGenerator.run(seed_prompt)` → 对 `schedule()` 中每个温度：`MockLLM.sample` → `parse_response`（失败记 `parse:` 日志）→ `hashed_embed(text)` → `_novelty`（低于阈值记 `duplicate`）→ 构造 `Hypothesis` 并 `_score` → 加入幸存者 → 全部轮次后按 `(-rank_score, id)` 排序 → 返回 `(queue, logs)` → 打印 JSON。

---

## 3. 逐段精讲

### 3.1 带标签的回复与正则

```python
TAG_RE = re.compile(
    r"<hypothesis>\s*"
    r"<text>(?P<text>.*?)</text>\s*"
    r"<variables>(?P<variables>.*?)</variables>\s*"
    r"<metric>(?P<metric>.*?)</metric>\s*"
    r"(?:<baseline>(?P<baseline>.*?)</baseline>\s*)?"
    r"</hypothesis>",
    re.DOTALL,
)
```

- 相邻的字符串字面量会被 Python 自动拼接成一个长正则，便于逐行注释与阅读。
- `(?P<name>...)` 是**命名分组**，之后用 `match.group("text")` 取值。
- `.*?` 是**非贪婪**匹配：遇到第一个 `</text>` 就停，避免跨标签吞掉内容。
- `(?:<baseline>...)?`：`(?:...)` 是不捕获的分组，后面的 `?` 让整个 baseline 段可选；没有时 `group("baseline")` 返回 `None`。
- `re.DOTALL` 让 `.` 也匹配换行，模型回复跨行时仍能解析。
- ⚠️ 标签必须**严格按此顺序**出现。我们实测把 `<metric>` 放在 `<variables>` 前面会得到 `ParserError: no hypothesis block found`。真实 LLM 的输出顺序不一定稳定，生产中可以对每个标签单独 `search`。

### 3.2 `parse_response`：宽进严出

```python
    match = TAG_RE.search(raw)
    if match is None:
        raise ParserError("no hypothesis block found")
    text = match.group("text").strip()
    if not text:
        raise ParserError("empty text")
    metric = match.group("metric").strip()
    if not metric:
        raise ParserError("empty metric")
    raw_vars = match.group("variables").strip()
    variables = [v.strip() for v in raw_vars.split(",") if v.strip()]
    if not variables:
        raise ParserError("empty variables")
    baseline = match.group("baseline")
    baseline_ref = baseline.strip() if baseline and baseline.strip() else None
```

- `search` 而不是 `match`：允许标签块前后有多余文字（模型常会加一句"Here is my hypothesis:"）。
- 每个必填字段都检查非空，失败抛 `ParserError`（继承 `ValueError`，调用方可以按需捕获）。
- 变量按逗号切分，列表推导式里的 `if v.strip()` 过滤掉 `"a,,b"` 中的空项。
- baseline 为空串或缺失都规范化成 `None`。
- 由于这里拒绝了空 metric，后面 `_testability_score` 的 0.0 分支对解析出来的假设永远走不到（测验 Q6）。

### 3.3 Hashed embedding 与余弦距离

```python
def hashed_embed(text: str, dim: int = HASH_DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in _tokenise(text):
        h = hashlib.md5(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if (h[4] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    dot = max(-1.0, min(1.0, dot))
    return 1.0 - dot
```

- 这是 **feature hashing（哈希技巧）**：不需要词表，每个词用 md5 的前 4 字节决定落在哪一维，第 5 字节的最低位决定加 +1 还是 −1。带符号是为了让碰撞的词在期望上互相抵消而不是只会叠加。
- 用 `hashlib.md5` 而不是内置 `hash()`：`hash(str)` 每个进程随机加盐，结果不可复现（测验 Q4 有实测）。md5 在这里只是"稳定的散列函数"，与安全性无关。
- L2 归一化后，两个向量的点积就是余弦相似度，`1 − dot` 即余弦距离。
- `max(-1.0, min(1.0, dot))` 把浮点误差导致的 1.0000000002 截回 1，避免出现负距离。
- ⚠️ 带符号哈希让点积可以为负，距离范围是 `[0, 2]` 而不是讲义说的 `0..1`。实测同桶异号的两个单词 `w0`、`w4` 距离为 2.0，排名分可达 1.4（测验 Q5）。
- ⚠️ 128 维会碰撞：实测 `memory` 与 `w7` 落在同一桶且同号，距离为 0，会被误判为重复。
- ⚠️ `_tokenise` 只认 `[a-z0-9]+`，中文得到零向量；`norm == 0` 时直接返回零向量，它与任何向量距离都是 1.0，于是相同的中文假设也能反复入队（测验 Q9）。

### 3.4 温度桶与 `MockLLM`

```python
def temperature_bucket(temperature: float) -> int:
    if temperature < 0.35:
        return 0
    if temperature < 0.65:
        return 1
    if temperature < 0.95:
        return 2
    return 3


class MockLLM:
    def __init__(self, scripts: dict[tuple[str, int], list[str]]) -> None:
        self._scripts = dict(scripts)

    @staticmethod
    def prompt_signature(prompt: str) -> str:
        return hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10]

    def sample(self, prompt: str, temperature: float, seed: int) -> str:
        key = (self.prompt_signature(prompt), temperature_bucket(temperature))
        bank = self._scripts.get(key)
        if not bank:
            return "<noise>untagged drift</noise>"
        return bank[seed % len(bank)]
```

- 用 4 个桶把连续温度离散化，模拟"温度不同 → 回复不同"。区间是左闭右开：0.35 属于桶 1。
- prompt 用 sha1 前 10 位做签名，脚本字典的键是 `(签名, 桶)` 元组——元组可以作为字典键。
- `dict(scripts)` 做浅拷贝，外部修改传入的字典不会影响 mock。
- 找不到脚本时返回不带 `<hypothesis>` 标签的噪声，必然解析失败——专门用来覆盖"解析失败"路径（测试 `test_unknown_prompt_falls_back_and_drops`）。
- `bank[seed % len(bank)]`：seed 决定选哪一条。⚠️ demo 每个桶只有 1 条，`seed % 1` 恒为 0，seed 实际不起作用；讲义"不同 seed 产生不同草稿"只有在 bank 有多条时才成立。
- `@staticmethod`：不需要 `self`，测试里直接 `MockLLM.prompt_signature(SEED_PROMPT)` 就能算出键。

### 3.5 `GeneratorConfig.schedule()`

```python
    def schedule(self) -> list[float]:
        if self.n_passes <= 0:
            return []
        if self.n_passes == 1:
            return [self.t_min]
        step = (self.t_max - self.t_min) / (self.n_passes - 1)
        return [self.t_min + i * step for i in range(self.n_passes)]
```

- 等间距且**包含两个端点**，所以除以 `n_passes − 1`；单轮时除数为 0，单独返回 `[t_min]`。
- 默认 6 轮：`[0.2, 0.4, 0.6, 0.8, 1.0, 1.2]`，对应桶 `[0, 1, 1, 2, 3, 3]`——两对温度落在同一个桶里。demo 用 `n_passes=4, t_max=1.1` 得到 `[0.2, 0.5, 0.8, 1.1]`，恰好各占一个桶。
- 所有可调参数（含三项权重、阈值、种子）都集中在这个 dataclass 中，讲义说下游课程可以改权重而不用 fork 代码。

### 3.6 三个子分数与排名分

```python
    def _specificity_score(self, h: Hypothesis) -> float:
        target = max(1, self._cfg.target_variable_count)
        return min(1.0, len(h.variables) / target)

    def _testability_score(self, h: Hypothesis) -> float:
        if h.metric and h.baseline_ref:
            return 1.0
        if h.metric:
            return 0.5
        return 0.0

    def _score(self, h: Hypothesis) -> float:
        return (
            self._cfg.w_novelty * h.novelty_score
            + self._cfg.w_specificity * self._specificity_score(h)
            + self._cfg.w_testability * self._testability_score(h)
        )
```

- specificity：变量数除以目标数（3），封顶 1。`max(1, ...)` 防止目标被配成 0 时除零。
- testability：有 metric 和 baseline 得 1，只有 metric 得 0.5。
- 线性加权求和；默认权重和为 1，若 novelty ≤ 1，总分在 `[0, 1]`。
- ⚠️ specificity 只数个数：把 metric 自己也写进 variables 会被计数（demo 假设 1 的 `validation_loss` 既是变量又是 metric），随便列 3 个名字就能满分（测验 Q11）。

### 3.7 新颖性与主循环 `run`

```python
    def _novelty(self, candidate: list[float], survivors: list[list[float]]) -> float:
        if not survivors:
            return 1.0
        return min(cosine_distance(candidate, s) for s in survivors)

    def run(self, seed_prompt: str) -> tuple[list[Hypothesis], list[GenerationLog]]:
        ...
        for pass_index, temperature in enumerate(self._cfg.schedule()):
            seed = self._cfg.base_seed + pass_index
            raw = self._llm.sample(seed_prompt, temperature, seed)
            try:
                parsed = parse_response(raw)
            except ParserError as exc:
                logs.append(GenerationLog(pass_index, temperature, seed, None, f"parse:{exc}", raw))
                continue
            vec = self._embed(parsed["text"])
            novelty = self._novelty(vec, survivor_vecs)
            if novelty < self._cfg.novelty_threshold:
                logs.append(GenerationLog(pass_index, temperature, seed, None, "duplicate", raw))
                continue
            hypothesis = Hypothesis(id=next_id, ..., novelty_score=novelty)
            hypothesis.rank_score = self._score(hypothesis)
            survivors.append(hypothesis)
            survivor_vecs.append(vec)
            logs.append(GenerationLog(pass_index, temperature, seed, next_id, None, raw))
            next_id += 1
        survivors.sort(key=lambda h: (-h.rank_score, h.id))
        return survivors, logs
```

- 每一轮的结局只有三种：解析失败、重复、接受，都会写一条 `GenerationLog`——日志条数恒等于轮数（测试 `test_demo_path_produces_queue` 断言了这一点）。
- 解析失败用 `continue` 跳过，**不会中断循环**；这是 agent 循环的基本素养。
- `seed = base_seed + pass_index`：每轮不同的种子，整体仍然由 `base_seed` 决定。
- `id` 只分配给被接受的假设，所以队列中的 id 连续（1、2、3、4），被拒绝的草稿没有 id。
- 只和**已接受**的向量比较，第一个被接受的假设 novelty 恒为 1.0。这让排名依赖生成顺序：demo 中假设 1 只有 2 个变量却排第 3，正是因为它白拿了 1.0 的新颖性；倒序生成时它会掉到最后（测验 Q10 给了对称重排的修正）。
- 排序键 `(-rank_score, h.id)`：分数降序，同分时按 id 升序，保证顺序确定。
- ⚠️ 讲义 "How to read the code" 说 `run` "returns a sorted queue"，实际返回 `(queue, logs)` 二元组。
- `embedder` 通过构造函数注入（默认 `hashed_embed`），测试或生产可以替换——依赖注入的典型用法。

### 3.8 demo 脚本

```python
def build_demo_scripts() -> dict[tuple[str, int], list[str]]:
    seed_prompt = "Investigate attention sparsity in small transformers"
    sig = MockLLM.prompt_signature(seed_prompt)
    return {
        (sig, 0): ["<hypothesis><text>Lowering attention head count from 8 to 4 ...</text>..."],
        (sig, 1): ["...Top-k sparse attention with k equal to 16 ..."],
        (sig, 2): ["...Routing attention through a learned gate ..."],
        (sig, 3): ["...Block sparse attention with block size 32 ..."],
    }
```

- 四条假设分别对应温度桶 0–3，内容从"保守的消融实验"逐渐走向"更大胆的结构改动"，用来示意温度升高的效果。
- 四条文本两两之间的距离（实测）：1–2 0.8498、1–3 0.7579、1–4 0.8536、2–3 0.9364、2–4 0.7435、3–4 1.0——都远高于 0.25，所以 demo 中没有重复。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| XML 风格标签 + 正则解析 | 对任何模型都能用，易读 | 标签顺序固定、嵌套/转义不处理；生产用 JSON schema 结构化输出或 tool calling |
| 解析失败只记日志、不抛到外层 | 一条坏回复不拖垮循环 | 没有重试；可回传错误让模型修正一次 |
| Temperature ramp | 前保守、后发散 | 温度 ≠ 科学新颖性；可配合"已有假设作负例"的 prompt |
| 4 个温度桶的 mock | 让温度对输出"有影响"且确定 | 多个温度落同一桶会重复（默认 6 轮就有 2 次重复） |
| md5 哈希 embedding（128 维） | 零依赖、跨进程确定 | 只认字面、会碰撞、中文为零向量、距离可达 2；生产换句向量模型 |
| 只与已接受者比较新颖性 | 在线过滤，O(n) | 顺序依赖、首个白拿 1.0；可在结束后对称重排或用 MMR |
| 固定阈值 0.25 | 简单 | 不同领域距离分布不同；需要用标注数据调 |
| 三项线性加权 | 透明、可配置 | 子分数易被刷（变量个数）；权重需用下游结果校准 |
| 固定 `n_passes` | 成本可预测 | 可能产出不足或浪费采样；可改为"凑够 K 个或预算耗尽" |
| 返回 `(queue, logs)` | 可观测、可调试 | 讲义描述为只返回队列 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，`str | None` 等写法不会在定义时报错 |
| PEP 604 联合类型 | `baseline_ref: str | None` | 等价于 `Optional[str]` |
| 内置泛型 | `list[str]`、`dict[tuple[str, int], list[str]]` | 3.9+ 可直接用内置类型做泛型 |
| `@dataclass` + 默认值 | `novelty_score: float = 0.0` | 有默认值的字段必须排在无默认值字段之后 |
| 自定义异常 | `class ParserError(ValueError)` | 继承内置异常，docstring 即可作为类体 |
| 正则命名分组 | `(?P<text>.*?)`、`match.group("text")` | 按名字取分组 |
| 非贪婪量词 | `.*?` | 尽量少匹配 |
| 非捕获可选组 | `(?:<baseline>...)?` | 分组但不编号，整体可选 |
| `re.DOTALL` | `re.compile(..., re.DOTALL)` | `.` 匹配换行 |
| 相邻字符串自动拼接 | `r"<hypothesis>\s*" r"<text>..."` | 编译期拼成一个字符串 |
| `hashlib` | `hashlib.md5(tok.encode("utf-8")).digest()` | 返回 16 字节摘要；`hexdigest()` 返回十六进制字符串 |
| 字节转整数 | `int.from_bytes(h[:4], "big")` | 大端序解释 4 个字节 |
| 位运算 | `h[4] & 1` | 取最低位判断奇偶 |
| 生成器表达式 | `sum(x * y for x, y in zip(a, b))`、`min(... for s in survivors)` | 不建中间列表 |
| 列表推导式带过滤 | `[v.strip() for v in raw_vars.split(",") if v.strip()]` | 去空项 |
| 条件表达式 | `baseline.strip() if baseline and baseline.strip() else None` | 一行 if-else |
| `@staticmethod` | `def prompt_signature(prompt)` | 不需要实例即可调用 |
| 元组作字典键 | `self._scripts.get((sig, bucket))` | 元组不可变、可哈希 |
| `or` 提供默认值 | `config or GeneratorConfig()` | `None` 时用默认配置 |
| 函数作为参数 | `embedder: Callable[[str], list[float]] = hashed_embed` | 依赖注入 |
| `enumerate` | `for pass_index, temperature in enumerate(...)` | 同时拿下标和值 |
| `try / except ... as exc` + `continue` | 解析失败分支 | 捕获后记录并进入下一轮 |
| 排序键为元组 | `key=lambda h: (-h.rank_score, h.id)` | 先按分数降序，再按 id 升序 |
| `round` | `round(self.temperature, 3)` | 输出时取整，避免 0.30000000000000004 |
| `json.dumps(..., indent=2)` | `_demo` | 美化输出 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试 import 时不运行 demo |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（输出为 JSON，以下为节选整理）：

```text
queue_size: 4
queue（按 rank_score 降序）:
  id=2  temp=0.5  novelty=0.8498  rank=0.9399  Top-k sparse attention with k equal to 16 ...
  id=3  temp=0.8  novelty=0.7579  rank=0.9032  Routing attention through a learned gate ...
  id=1  temp=0.2  novelty=1.0     rank=0.9     Lowering attention head count from 8 to 4 ...
  id=4  temp=1.1  novelty=0.7435  rank=0.8974  Block sparse attention with block size 32 ...
logs:
  pass 0  temp 0.2  seed 0  accepted_id 1  reject_reason null
  pass 1  temp 0.5  seed 1  accepted_id 2  reject_reason null
  pass 2  temp 0.8  seed 2  accepted_id 3  reject_reason null
  pass 3  temp 1.1  seed 3  accepted_id 4  reject_reason null
```

逐项解读：

- **温度表** `[0.2, 0.5, 0.8, 1.1]` 各落一个桶，4 轮全部接受，没有解析失败和重复。
- **novelty**：id 1 是第一个，恒为 1.0；id 2 只与 id 1 比较（0.8498）；id 3 取与 1、2 的较小值 `min(0.7579, 0.9364) = 0.7579`；id 4 取 `min(0.8536, 0.7435, 1.0) = 0.7435`。
- **rank 手算**：
  - id 2：`0.4×0.8498 + 0.3×1 + 0.3×1 = 0.9399`；
  - id 3：`0.4×0.7579 + 0.6 = 0.9032`；
  - id 1：`0.4×1.0 + 0.3×(2/3) + 0.3×1 = 0.9`（只有 2 个变量）；
  - id 4：`0.4×0.7435 + 0.6 = 0.8974`。
- **四条假设的排名分非常接近**（0.90 ± 0.04），排序几乎完全由 novelty 决定，而 novelty 又取决于生成顺序。实测倒序生成时 id 1 那条会从 0.9 降到 0.8032 并排到最后。
- **`raw_excerpt`** 只保留前 80 个字符，避免日志过大。

用默认配置 `GeneratorConfig()`（6 轮）跑同样的脚本（我们额外运行）：

```text
pass 0 temp 0.2 accepted 1
pass 1 temp 0.4 accepted 2
pass 2 temp 0.6 duplicate      ← 0.6 与 0.4 同在桶 1，脚本相同，距离 0
pass 3 temp 0.8 accepted 3
pass 4 temp 1.0 accepted 4
pass 5 temp 1.2 duplicate      ← 1.2 与 1.0 同在桶 3
```

讲义说"默认 6 轮足够填满队列"，在 demo 脚本下其实有 1/3 的采样被浪费。

---

## 7. 动手改一改

1. **默认配置实验**：用 `GeneratorConfig()` 跑 demo，确认第 2、5 轮被判重复；再给每个桶加第二条脚本，观察 `seed` 开始生效。
2. **对称重排**：实现测验 Q10 的 `rerank_symmetric`，并把 novelty 截断到 `[0, 1]`；验证倒序生成与正序生成得到相同排名。
3. **零向量处理**：在 `run` 中检测 `hashed_embed` 返回全零时直接拒绝（`reject_reason="unembeddable"`），并补一个中文用例的测试。
4. **结构化去重**：在 embedding 比较之前，先比较 `(frozenset(variables), metric, baseline_ref)`，完全相同的直接判重。
5. **新的 specificity**：实现测验 Q11 的 `specificity_v2`（排除因变量、要求文本含数值），对比 demo 排名变化。
6. **预算化生成**：实现测验 Q12 的 `run_until(k, max_samples)`，再加"连续 3 次重复即早停"的规则，并在日志中输出停止原因。

---

## 8. 常见坑

- **用内置 `hash()` 做哈希 embedding**：每个进程结果不同，队列不可复现。
- **以为 novelty 在 [0, 1]**：带符号哈希下距离可到 2，排名分可超过 1。
- **以为 seed 一定让输出不同**：mock 中 bank 只有 1 条时 seed 无效；真实模型同温度不同 seed 也可能输出相似内容。
- **轮数多于温度桶数**：必然产生重复，白白浪费采样。
- **把因变量写进 variables**：specificity 被虚高。
- **只靠词袋判断重复**：相反结论被误杀（实测距离 0.095），同义改写被漏放（0.592）。
- **非英文文本**：分词器丢掉所有字符，零向量永远"新颖"。
- **标签顺序不固定的模型输出**：正则按固定顺序匹配，会整条解析失败。
- **把第一个假设的高 novelty 当作质量信号**：它只是"第一个被看到"。

---

## 9. 测试在验证什么

`tests/test_generator.py` 用 `unittest` 编写，通过 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加入搜索路径后 `from main import ...`。共 5 个测试类、18 个用例：

| 测试类 | 用例 | 验证的性质 |
|-------|------|-----------|
| `TestParser` | `test_parses_full_block` | 四个字段都能正确提取，变量按逗号切分并去空白 |
| | `test_baseline_optional` | 缺 baseline 时 `baseline_ref` 为 `None` |
| | `test_rejects_unparseable` | 无标签纯文本抛 `ParserError` |
| | `test_rejects_empty_variables` | 变量只有空白时抛 `ParserError` |
| `TestEmbedding` | `test_unit_norm` | embedding 的 L2 范数为 1 |
| | `test_distance_self_zero` | 自身距离为 0 |
| | `test_distance_disjoint_high` | 完全不同的词组距离 > 0.5 |
| `TestTemperatureRamp` | `test_schedule_endpoints` | 4 轮 0.2 → 1.1，首尾端点精确 |
| | `test_schedule_one_pass` | 1 轮时只返回 `t_min` |
| | `test_schedule_zero_passes` | 0 轮返回空列表 |
| | `test_bucket_boundaries` | 0.2/0.5/0.8/1.1 分别落在桶 0/1/2/3 |
| `TestGenerator` | `test_demo_path_produces_queue` | demo 4 轮全接受，日志 4 条无拒绝，id 为 1–4 |
| | `test_queue_sorted_by_rank_desc` | 队列按 `rank_score` 降序 |
| | `test_duplicate_rejected` | 4 个桶都返回同一条文本：只保留 1 条，其余 3 条日志为 `duplicate` |
| | `test_parser_failure_logged` | 桶 0 返回纯文本：第一条日志以 `parse:` 开头，队列只有 1 条 |
| | `test_unknown_prompt_falls_back_and_drops` | 空脚本：所有轮次都走噪声回退并解析失败，队列为空 |
| | `test_specificity_weight_changes_rank` | 只用 specificity 权重时分数在 [0, 1] |
| `TestDeterminism` | `test_two_runs_identical` | 两个独立生成器对同一输入产生完全相同的 `to_dict()` 结果 |

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q tests
..................                                                       [100%]
18 passed in 0.02s

$ python3 -m unittest discover -s tests
Ran 18 tests in 0.002s
OK
```

几点观察：

- `test_specificity_weight_changes_rank` 名字说"权重改变排名"，实际只检查分数在 [0, 1]，而且把 `w_novelty` 设为 0，恰好避开了 novelty 可能 > 1 的问题（测验 Q5）。
- `test_bucket_boundaries` 没有测边界值本身（0.35、0.65、0.95）。
- 确定性测试是在同一进程内跑两次；跨进程的确定性依赖 md5/sha1，测试没有直接覆盖，但这正是选择 `hashlib` 的原因。
- 值得补充的测试：中文/零向量输入、同桶多条脚本时 seed 生效、生成顺序对排名的影响、`rank_score` 上界。
