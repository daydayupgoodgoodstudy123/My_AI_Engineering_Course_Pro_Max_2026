# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 24 节 SAM 3 与开放词表分割（Open-Vocabulary Segmentation） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`numpy` + 标准库（`abc`、`dataclasses`、`typing`、`json`）；**不加载真实的 SAM 3 模型**，无需 GPU、无需联网

---

## 1. 这份代码在考察什么

这份代码刻意**不跑 SAM 3**，而是把"模型之外"的那一圈工程代码单独拿出来练。真实项目里，模型调用往往只有几行，真正容易出 bug 的是它周围的胶水层：

1. **提示构造**：用户输入的是一句话（"cats, dogs and balloons"），SAM 3 要的是一个个短名词短语——`split_concepts` 就是这道边界。
2. **输出压缩**：高分辨率 mask 很大，用游程编码（RLE，Run-Length Encoding）压成字符串，并用 decode 往返验证无损。
3. **后端无关的接口**：用抽象基类 `OpenVocabSeg` 定义 `detect(image, concept)`，SAM 3、Grounded SAM 2、YOLO-World + SAM 2 都可以藏在它后面。
4. **可测试性**：用一个确定性的 `StubOpenVocabSeg` 代替真实模型，让整条流水线在没有权重的情况下也能跑通、能写测试。
5. **多概念编排**：SAM 3 一次前向只处理一个概念，多概念就循环调用再合并。

> 一句话：**模型会换，接口和数据契约不该跟着换**——这份代码练的是"把模型当成可替换零件"的工程习惯。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ConceptDetection` | `@dataclass` | 一条检测结果：概念、实例 ID、框、分数、mask 的 RLE | 统一输出契约（框 + 标签 + 分数 + mask + ID） |
| `split_concepts(sentence)` | 函数 | 把一句话拆成多个概念提示 | 概念提示（concept prompt） |
| `rle_encode(binary_mask)` | 函数 | 二值 mask → `"0x100;1x50;..."` 字符串 | mask 压缩传输 |
| `rle_decode(rle_str, shape)` | 函数 | 字符串 → 二值 mask | 往返验证 |
| `OpenVocabSeg` | 抽象基类 | 规定 `detect(image, concept)` 接口 | 后端可替换 |
| `StubOpenVocabSeg` | 子类 | 固定返回两个矩形实例 | 测试替身（stub） |
| `run_multi_concept(model, image, utterance)` | 函数 | 拆概念 → 逐个 detect → 合并 | 多概念编排 |
| `main()` | 演示入口 | 依次演示拆分、RLE 往返、Stub 多概念检测 | — |

数据流：`user_utterance` →（`split_concepts`）→ 概念列表 →（对每个概念 `model.detect`）→ `ConceptDetection` 列表（mask 已是 RLE）→ 打印摘要。

---

## 3. 逐段精讲

### 3.1 输出契约：`ConceptDetection`

```python
@dataclass
class ConceptDetection:
    concept: str
    instance_id: int
    box: tuple
    score: float
    mask_rle: str
```

- `@dataclass` 根据类型注解自动生成 `__init__`、`__repr__`、`__eq__`，省去样板代码。
- 字段设计对应讲义所说的"三种模型都返回同样的结构（框 + 标签 + 分数 + mask + ID）"：只要后端都转换成这个结构，下游就**不需要按模型分支**。
- `box` 约定是 `(x1, y1, x2, y2)`（讲义中的注释），这里类型只写了 `tuple`。
- `mask_rle` 用字符串而不是 `np.ndarray`：可以直接 `json.dumps`，适合当 API 响应体。
- ⚠️ 简化：`box: tuple` 没有约束元素个数与类型；生产中可以写成 `tuple[float, float, float, float]`，或用 pydantic 做校验。

### 3.2 `split_concepts`：从"一句话"到"概念列表"

```python
def split_concepts(sentence):
    normalised = sentence
    for sep in [" and ", " or ", "&", ";"]:
        normalised = normalised.replace(sep, ",")
    if "," in normalised:
        parts = [p.strip() for p in normalised.split(",")]
        return [p for p in parts if p]
    return [sentence.strip()]
```

- 思路是"**先归一化，再切分**"：把所有分隔符统一替换成逗号，最后只按逗号切一次。检测分隔符和执行切分用的是同一套规则，不会出现"检测到了却没切"的情况。
- `" and "`、`" or "` 两边带空格：只匹配独立的单词，避免误伤 `hand`、`door`、`color` 这类包含 `and`/`or` 子串的词。
- `[p for p in parts if p]` 过滤空串，比如 `"cats,,dogs"` 或结尾多余的逗号。
- **为什么这样设计**：讲义 Build It · Step 1 中的版本用 `if sep in sentence` 做子串判断，且只把 `"and "` 换成逗号，结果 `"hand holding a mug"` 会被拆成 `['h', 'holding a mug']`，`;` 和 `or` 也切不开。`main.py` 的写法正是对它的修正（详见测验 Q9）。
- ⚠️ 启发式的局限：
  - `"black and white cat"` → `['black', 'white cat']`（语义被拆坏）；
  - `"Cats AND dogs"` 大小写不匹配，不会被拆；
  - 纯空白输入 `"   "` 会返回 `['']`，即一个空概念——调用方最好再检查一次。
  - 本节的 `outputs/skill-concept-prompt-designer.md` 给出了更完整的规则（去掉"find / show me"等填充词、引号内不拆分、限制最大概念数）。

### 3.3 `rle_encode`：游程编码

```python
def rle_encode(binary_mask):
    flat = binary_mask.flatten().astype("uint8")
    if flat.size == 0:
        return ""
    runs = []
    prev = int(flat[0])
    count = 0
    for v in flat:
        iv = int(v)
        if iv == prev:
            count += 1
        else:
            runs.append((prev, count))
            prev, count = iv, 1
    runs.append((prev, count))
    return ";".join(f"{v}x{c}" for v, c in runs)
```

- `flatten()` 默认按**行优先**（C order）展平成一维；RLE 作用在这条一维序列上，所以上一行末尾和下一行开头的同值像素会合并成一段。
- 循环逻辑：`prev` 记当前段的值、`count` 记长度；遇到不同的值就把上一段写入 `runs`，开新段。循环结束后**别忘了**把最后一段 append 进去（这是手写 RLE 最常见的漏写点）。
- `count = 0` 起步、第一次循环时 `flat[0] == prev` 所以 `count` 变成 1——用这种方式避免对第一个元素做特判。
- `int(v)`：把 `np.uint8` 转成 Python `int`，让 f-string 和比较都不受 NumPy 标量类型影响。
- `flat.size == 0` 的保护：讲义版本没有这一行，空 mask 会在 `flat[0]` 处抛 `IndexError`。
- 输出格式 `"值x长度"`，例如 `[[0,0,1],[1,1,0]]` → `'0x2;1x3;0x1'`。
- ⚠️ 简化：
  - 用 Python 循环逐像素处理，1024×1024 的 mask 有约 100 万次迭代，较慢；生产中用 `np.diff` 找变化点做向量化。
  - 字符串里显式写出值（`0x`/`1x`）是为了可读；COCO RLE 等标准格式只存计数（默认从 0 开始交替），并且是**列优先**展平——和这里不兼容，混用会得到转置/错位的 mask。

### 3.4 `rle_decode`：往返验证

```python
def rle_decode(rle_str, shape):
    if not rle_str:
        return np.zeros(shape, dtype=np.uint8)
    flat = np.zeros(int(np.prod(shape)), dtype=np.uint8)
    idx = 0
    for part in rle_str.split(";"):
        v, c = part.split("x")
        v = int(v)
        c = int(c)
        flat[idx:idx + c] = v
        idx += c
    return flat.reshape(shape)
```

- 先分配一个全 0 的一维数组，再按段用切片赋值 `flat[idx:idx + c] = v` 一次填一整段（这是 NumPy 的向量化写法，比逐像素快）。
- `reshape(shape)` 按行优先还原，正好和 `flatten()` 对称。
- `shape` 需要调用方提供：RLE 字符串本身不包含宽高信息，所以真实 API 里通常会把 `size` 和 `counts` 一起返回。
- ⚠️ 没有校验"各段长度之和是否等于 `prod(shape)`"：如果字符串被截断，会静默返回一个尾部全 0 的 mask。

### 3.5 抽象接口与 Stub

```python
class OpenVocabSeg(ABC):
    @abstractmethod
    def detect(self, image: np.ndarray, concept: str) -> List[ConceptDetection]:
        ...


class StubOpenVocabSeg(OpenVocabSeg):
    """Pipeline-testable stand-in for SAM 3 / Grounded SAM 2."""

    def detect(self, image, concept):
        h, w = image.shape[:2]
        mask_a = np.zeros((h, w), dtype=np.uint8)
        mask_a[int(h * 0.3):int(h * 0.8), int(w * 0.2):int(w * 0.5)] = 1
        # ...
        return [
            ConceptDetection(
                concept=concept,
                instance_id=0,
                box=(w * 0.2, h * 0.3, w * 0.5, h * 0.8),
                score=0.89,
                mask_rle=rle_encode(mask_a),
            ),
            # ... 第二个实例 mask_b，score=0.74
        ]
```

- `ABC` + `@abstractmethod`：`OpenVocabSeg` 不能直接实例化；任何子类如果没实现 `detect`，在实例化时就会报 `TypeError`——把"忘了实现接口"提前到构造时暴露。
- 这是经典的**策略模式 / 依赖倒置**：上层只依赖抽象的 `detect`，真实的 `SAM3OpenVocabSeg`（讲义说它会包装 `transformers` 里的 SAM 3 模型与 processor）或 Grounded SAM 2 实现可以随时替换。
- Stub 的特点是**确定性**：同样的输入永远返回同样的两个实例，适合写单元测试、联调前后端、压测下游。
- 框和 mask 是一致的：mask 切片 `[int(h*0.3):int(h*0.8), int(w*0.2):int(w*0.5)]` 正好对应框 `(w*0.2, h*0.3, w*0.5, h*0.8)`。注意框的格式是 `(x, y)` 顺序，而数组切片是 `[行(y), 列(x)]` 顺序——这是 CV 代码里最常见的坐标混淆点，这里写对了。
- `image.shape[:2]` 取前两维 `(h, w)`，兼容灰度图 `(h, w)` 和彩色图 `(h, w, 3)`。
- ⚠️ Stub 不看 `concept` 内容，任何概念都返回同样两个实例；实例 ID 每次都从 0 开始。

### 3.6 多概念编排

```python
def run_multi_concept(model: OpenVocabSeg, image: np.ndarray, user_utterance: str):
    concepts = split_concepts(user_utterance)
    out = []
    for c in concepts:
        out.extend(model.detect(image, c))
    return out
```

- 对应讲义："SAM 3 一次前向只接受一个概念；多概念查询要循环或批处理"。
- 参数类型注解写的是抽象类型 `OpenVocabSeg`，表达"任何实现了该接口的后端都可以"。
- `out.extend(...)` 把列表展开追加，结果是一个平铺的检测列表，每条都带 `concept` 标签。
- ⚠️ 两个工程隐患：
  1. **实例 ID 冲突**：每个概念的 ID 都从 0 开始，`oranges` 和 `apples` 都有 ID 0 和 1，下游若只用 `instance_id` 作键会互相覆盖（测验 Q11 给出了全局 ID 的改法）。
  2. **串行调用**：N 个概念就是 N 次前向；生产中应批处理并限制最大概念数。

### 3.7 `main()`：三段演示

- `[split_concepts]`：4 个例句，`{s!r:45s}` 先取 `repr`（带引号），再左对齐补到 45 宽，方便对齐查看。
- `[rle encode/decode roundtrip]`：`np.random.default_rng(0)` 生成固定种子的随机 16×16 mask，编码后解码，计算逐像素绝对差之和；`astype(int)` 是为了避免 `uint8` 相减时下溢回绕（`0 - 1` 在 `uint8` 下会变成 255）。
- `[multi-concept detection on stub]`：240×320 的全黑图 + `"oranges, apples"`，打印每条检测的摘要；`mask_len` 是 RLE 的段数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不加载真实模型，用 Stub | 无需权重、GPU、许可审批就能跑通和测试流水线 | Stub 不反映真实精度；接真实模型后要另做评测 |
| 抽象基类统一 `detect` 接口 | 后端（SAM 3 / Grounded SAM 2 / YOLO-World+SAM 2）可替换，下游不改 | 不同后端的能力差异（如 YOLO-World 不出 mask）需要在接口层约定降级方式 |
| `dataclass` 作为输出契约 | 结构清晰、可 `asdict` 后转 JSON | 不做字段校验；生产常用 pydantic |
| 规则式 `split_concepts` | 简单、零依赖、可解释 | 会拆坏 "black and white cat"；生产结合 LLM/小模型抽取与引号保护 |
| 字符串 RLE（`值x长度`） | 人眼可读、易调试，往返可验证 | 不兼容 COCO RLE；Python 循环慢，应向量化 |
| 每个概念单独调用 | 对齐 SAM 3"一次一个概念"的事实 | 延迟随概念数线性增长；需要批处理、限流、全局 ID |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 + 条件过滤 | `[p for p in parts if p]` | 一行完成"遍历 + 过滤"；空串为假值被过滤 |
| `str.replace` / `split` / `strip` / `join` | `normalised.replace(sep, ",")`、`";".join(...)` | 字符串的替换、切分、去空白、拼接 |
| 元组解包 | `v, c = part.split("x")`、`prev, count = iv, 1`、`h, w = image.shape[:2]` | 一次给多个变量赋值 |
| 切片 | `image.shape[:2]`、`flat[idx:idx + c] = v` | 取前两个元素；NumPy 切片赋值一次填一段 |
| 生成器表达式 | `";".join(f"{v}x{c}" for v, c in runs)`、`tuple(round(x, 1) for x in d.box)` | 不建中间列表，按需产出 |
| f-string 格式符 | `f"{s!r:45s}"`、`f"{v}x{c}"` | `!r` 先调用 `repr()`；`:45s` 左对齐补齐到 45 字符 |
| 类型注解 | `image: np.ndarray`、`-> List[ConceptDetection]` | 只是给人和工具看的提示，运行时不强制检查 |
| `typing.List` | `List[ConceptDetection]` | 旧式泛型写法；Python 3.9+ 也可以直接写 `list[ConceptDetection]` |
| `@dataclass` | `class ConceptDetection` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| 抽象基类 | `class OpenVocabSeg(ABC)` + `@abstractmethod` | 定义接口；没实现抽象方法的子类无法实例化 |
| `...`（Ellipsis） | 抽象方法体 `...` | 占位符，等价于 `pass` |
| 继承 | `class StubOpenVocabSeg(OpenVocabSeg)` | 子类实现父类规定的接口 |
| `list.extend` vs `append` | `out.extend(model.detect(image, c))` | `extend` 把列表元素逐个加入；`append` 会把整个列表当作一个元素 |
| NumPy 随机数生成器 | `np.random.default_rng(0).random((16, 16))` | 新式 RNG，固定种子可复现 |
| `json.dumps` | `json.dumps(summary)` | 字典 → JSON 字符串；元组会被序列化为 JSON 数组 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

在临时副本中实际运行（Python 3.13 + NumPy 2.5），输出如下：

```text
[split_concepts]
  'cats, dogs and balloons'                     -> ['cats', 'dogs', 'balloons']
  'yellow school bus'                           -> ['yellow school bus']
  'striped red umbrella; green hat'             -> ['striped red umbrella', 'green hat']
  'one large boat or small boat'                -> ['one large boat', 'small boat']

[rle encode/decode roundtrip]
  mask shape (16, 16)  rle length 575  roundtrip diff 0

[multi-concept detection on stub]
  4 detections
    {"concept": "oranges", "id": 0, "box": [64.0, 72.0, 160.0, 192.0], "score": 0.89, "mask_len": 241}
    {"concept": "oranges", "id": 1, "box": [176.0, 60.0, 272.0, 180.0], "score": 0.74, "mask_len": 241}
    {"concept": "apples", "id": 0, "box": [64.0, 72.0, 160.0, 192.0], "score": 0.89, "mask_len": 241}
    {"concept": "apples", "id": 1, "box": [176.0, 60.0, 272.0, 180.0], "score": 0.74, "mask_len": 241}
```

逐段解读：

- **拆分**：逗号、`and`、`;`、`or` 四种分隔符都被正确处理；没有分隔符的 `"yellow school bus"` 保持为一个整体概念。
- **RLE 往返**：`roundtrip diff 0` 证明编码是无损的。但 `rle length 575` 个字符 > 256 个像素：随机噪声 mask 每段很短，RLE 反而膨胀。真实分割 mask 是大块连通区域，压缩效果才好。
- **Stub 检测**：
  - 2 个概念 × 每个 2 个实例 = 4 条检测；
  - 框 `[64.0, 72.0, 160.0, 192.0]` 就是 `(0.2w, 0.3h, 0.5w, 0.8h)`，其中 w=320、h=240；`json.dumps` 把元组输出为 JSON 数组 `[...]`；
  - `mask_len` 241：mask 有 120 行，每行贡献"一段 1 + 一段 0"共 2 段，再加开头的一段 0，`1 + 120×2 = 241`；
  - 注意 `oranges` 和 `apples` 的 ID 都是 0、1——这就是 3.6 中提到的 ID 冲突隐患。

---

## 7. 动手改一改

1. **修边界**：让 `split_concepts("   ")` 返回空列表而不是 `['']`；再让它对 `" AND "`、`" Or "` 也大小写不敏感（提示：用 `re.split(r"\s+(?:and|or)\s+|[,;&]", s, flags=re.I)`）。
2. **引号保护**：支持 `'"black and white cat", dog'` → `['black and white cat', 'dog']`，即引号内不拆分。
3. **向量化 RLE**：用 `np.flatnonzero(np.diff(flat))` 找变化点，重写 `rle_encode`，与原实现对比结果和 1024×1024 mask 上的耗时。
4. **加校验**：让 `rle_decode` 在各段长度之和不等于 `prod(shape)` 时抛 `ValueError`。
5. **全局 ID 与过滤**：实现测验 Q11 的 `run_multi_concept_global`，用 `dataclasses.replace` 生成新对象。
6. **第二个后端**：写一个 `BoxOnlyStub(OpenVocabSeg)` 模拟 YOLO-World（只出框，`mask_rle` 用框填充的矩形 mask 生成），验证 `run_multi_concept` 无需修改就能切换后端。

---

## 8. 常见坑

- **子串匹配误伤**：用 `"and" in sentence` 判断分隔符，会命中 `hand`、`sandwich`；分隔词两边要带空格或用正则 `\b` 单词边界。
- **坐标顺序混淆**：框是 `(x1, y1, x2, y2)`，数组索引是 `[y, x]`（行在前）。写反了 mask 会和框错位，而且在正方形图上看不出来。
- **RLE 格式不兼容**：本文件是行优先、显式写值；COCO RLE 是列优先、只存计数。混用会得到转置或错位的 mask。
- **漏掉最后一段**：手写 RLE 时忘记循环结束后 `runs.append((prev, count))`，最后一段会丢失。
- **`uint8` 相减下溢**：`mask - restored` 在 `uint8` 下 `0 - 1 = 255`，必须先 `astype(int)` 再相减（代码里已这样做）。
- **跨概念 ID 冲突**：多概念合并时用 `instance_id` 单独做键会互相覆盖，应使用 `(concept, instance_id)` 或全局 ID。
