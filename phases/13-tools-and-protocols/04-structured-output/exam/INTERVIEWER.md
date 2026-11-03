# 面试官手册：InvoiceKit（13/04）

候选人计时期间不要看。候选人手里只有 README、`invoicekit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 数组下标在 loc 里是字符串还是整数？ | "An int. loc is typed, like Pydantic's: str for a member, int for an index." |
| 1 | enum 里 5.0 和 5 算相等吗？true 和 1 呢？ | "5.0 equals 5. true is not 1. JSON compares values, and a boolean is not a number." |
| 1 | 能把索引缓存在 schema 字典里吗？ | "Please don't. Schemas are shared, and the same dict goes to the provider." |
| 1 | 错误的先后顺序能改吗？ | "Keep the order the validator gives today." |
| 1 | `__REFUSAL__` 出现在回复中间，算拒答吗？ | "No. Only a reply that starts with it. Anything else is parsed as JSON." |
| 2 | 能一份结果存一个文件吗？ | "No. One snapshot file. Other jobs read it." |
| 2 | 只存原始回复、读的时候重新解析可以吗？ | "No. Store what the pipeline decided. The validator will change; old results must not." |
| 2 | 金额能存成浮点数吗？ | "No. An amount comes back with exactly the digits it had." |
| 2 | 要不要 fsync？ | "Yes, please. The tests can't see it, but tell me why it matters." |
| 2 | 同一个文档再存一次，排到最后吗？ | "No. It keeps its place." |
| 3 | "Here is your JSON:" 后面的 JSON 能截出来用吗？ | "No. That reply is a parse error. Feed it back." |
| 3 | 总额允许差一分钱吗？要不要四舍五入到分？ | "No tolerance and no rounding. Exact, as decimals." |
| 3 | max_retries 算不算第一次？ | "No. One attempt, then up to max_retries retries." |
| 3 | 重试都用完了返回什么？ | "The last result as it is, and how many attempts it took." |
| 3 | 拒答能换个提示词再试吗？ | "No. A refusal is final here." |
| 4 | 输出里能有空格吗？ | "No. Compact JSON, one way to write each value." |
| 4 | 属性顺序有要求吗？ | "The order in properties, and every property is there." |
| 4 | 要不要采样？ | "No. Greedy: the first candidate that is allowed." |
| 4 | 对象的右括号出来以后还要问模型吗？ | "No. Nothing can follow it, so stop." |
| 4 | 一个 token 会不会跨过好几段语法？ | "Yes. Tokens don't line up with JSON syntax." |
| 5 | discriminator 是 JSON Schema 的关键字吗？ | "No, it's OpenAPI's. We only use propertyName." |
| 5 | 没选中的分支，错误要不要也报？ | "No. Only the branch the kind picks." |
| 5 | 整数算不算 number？ | "Yes. That's why 1 matches both discount branches." |

## 每关：要看什么、提示、追问

### Part 1 修校验器和回复分类（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `_at` 往 loc 里放的是 `str(step)`，数组下标变成了字符串 `"0"`，路径打印成 `$.line_items.0.sku`。错误不在 `validate` 里报：`feedback` 调用 `lookup`，`lookup` 拿 `"0"` 去索引列表，报 `TypeError: list indices must be integers or slices, not str`。报错的地方离根因两层。
2. 数组分支在第一个出错的元素处就 return，第 3 行的两个错误丢了。docstring 写的是 every error。
3. `process_model_output` 先 `json.loads` 再判断 `__REFUSAL__` 前缀。拒答文本根本解析不了，那个判断成了死代码，拒答被归成 `parse_error`（Expecting value）。课里说 refusal 要作为单独的结果处理，而且不能重试；归成 parse error，到 Part 3 就会被拿去重试。
4. enum 用 `_same_json` 逐个比较，是线性扫描。5,000 个 SKU、3,000 行，本机约 1.1 秒（机器负载高时 3 到 5 秒），限值 0.1 秒。
5. 护栏一：enum 比的是 JSON 值。`set(enum)` 是最顺手的提速写法，但 enum 里有对象（付款条件），报 `unhashable type: 'dict'`；就算只放可哈希的成员，`False == 0`、`True == 1` 也会让 false 和 true 混进去。课里原来的 `value not in enum` 在这里只要约 30 毫秒，能过计时，但同样挂在 false 和 true 上。用 `repr` 或 `json.dumps` 当键也不行：对象的键顺序不同就不相等，Decimal 也没法 `json.dumps`。
6. 护栏二：不能把索引塞进 schema 字典里缓存，测试会检查 schema 没被改过。

计时分不出来的一种写法：字符串改用列表自带的 `in`（在 C 里逐个比较，而字符串只会和字符串相等），其他值仍走 `_same_json`。语义是对的，这里约 30 毫秒，能过 0.1 秒的限值，可它仍是线性扫描，机器很忙时可能超时。遇到这种写法，问一句 50,000 个 SKU 时怎么办。

看什么：是不是先读 traceback，发现 `lookup` 本身没错，再顺着 loc 往回找；是不是先 `print(result.errors)` 看实际的 loc；每改一处就重跑。

提示：
- H1："Print result.errors. What is the type of each step in loc?"
- H2："Which function builds loc for an array element? Compare it with ValidationError's docstring."
- H3：直接指出 `_at` 的 `str(step)`、数组分支的 return、`process_model_output` 里两步的顺序，以及 enum 的线性扫描。

追问：
- "Why is True == 1 a problem here, and where else does it bite?"（bool 是 int 的子类；set 和 dict 按 hash 加相等查找，True 和 1 会撞在一起；课里的校验器在类型检查里已经排除了 bool）
- "Your enum cache is keyed by id(). What can go wrong?"（列表被释放后 id 会被复用，缓存项要持有列表本身；缓存之后有人改了 enum，结果会过期；缓存要有上限）
- "pattern uses re.match. Is that what JSON Schema means?"（规范是不锚定的搜索；Python 的 `$` 还会放过结尾的换行，code/main.讲解.md 的表里列了这几处差异）
- "Strict mode guarantees the schema. Why validate at all?"（不是每家都有 strict；schema 表达不了业务规则；服务端再查一遍是兜底）

### Part 2 结果快照（目标 12 分钟）

坑：
- 解析时用了 `parse_float=Decimal`，payload 里的金额是 Decimal，`json.dump` 直接报 `Object of type Decimal is not JSON serializable`。
- `default=str` 存成字符串，读回来就是字符串。反过来把“像数字的字符串”都转回 Decimal 也不行：violation 的 payload 里本来就有模型加了引号的 `"49.99"` 和 `"2"`，必须原样还是字符串。Decimal 要么打标记（参考答案用 `{"$decimal": "120.00"}`），要么写成 JSON 数字再用 `parse_float=Decimal` 读。
- `default=float` 再用 `parse_float=Decimal` 读，120.00 会变成 120.0。`Decimal("120.0") == Decimal("120.00")`，所以 `==` 查不出来，测试用 `exact()` 比较每一位；`normalize()` 会变成 `1.2E+2`，也一样挂。
- 错误的 loc 要读回成 tuple。读回 list 的话，`ValidationError` 不相等。
- 原始回复要一个字符一个字符地存：拒答理由里的破折号、回复结尾的换行。
- 只存原始回复、读的时候重新跑 `process_model_output` 不行：po-0452 是 Part 3 的总额检查判出来的 violation，重新解析会变成 ok。存下来的是当时的结论，校验器以后会改。
- 文档 id 故意不是按字母顺序给的。按 id 建字典再 `sort_keys=True`，顺序就错了。同一个文档再存一次要留在原位：dict 赋值会保留位置，先 pop 再插入就排到最后了。
- 原子写：临时文件放在同一个目录，写完用 `os.replace` 换上去。测试把 `os.replace` 和 `os.rename` 换成会抛错的函数，模拟保存到一半进程挂了：直接覆盖写文件的实现不会抛错（DID NOT RAISE）；失败后临时文件要删掉；内存里的状态不能先改。测试还记下了 `os.replace` 收到的临时文件路径，临时文件写进系统临时目录的实现会挂在 "the temporary file is written next to the snapshot"：/tmp 常常在另一个文件系统上，跨文件系统时 `os.replace` 根本换不过去，直接报 EXDEV。候选人写 `from os import replace` 的话，测试换不掉这个名字，要提醒他按 docstring 调用 `os.replace`。
- 文件还不存在时，store 是空的，不能报 FileNotFoundError。未知的 id 要报 KeyError，不能返回 None；保存失败要把异常抛给调用方，不能吞掉。

追问：
- "What does fsync buy you, and what else would you fsync?"（不 fsync 的话，断电后 rename 可能已经落盘、数据还没有；严格做法还要 fsync 目录）
- "A million results?"（每次 put 都重写整个快照是 O(n)；换成追加写的日志加定期快照，或者 SQLite）
- "Two workers write the snapshot at once?"（后写的覆盖先写的，丢更新；文件锁、单写者队列，或者换数据库）
- "Why store Decimal as text instead of a JSON number?"（读这个文件的其他程序，比如 JavaScript，会把数字解析成双精度浮点，金额就不准了）
- "The model writes {"$decimal": "1"} in a field. What does your snapshot give back?"（打标记的写法会把它读成 `Decimal('1')`。测试不查这一点。参考实现把形状像标记的对象改存成 `{"$object": [[键, 值]]}`，键值对列表不会被 object_hook 解开；把 Decimal 写成 JSON 数字、读的时候用 `parse_float=Decimal` 的写法本来就没有这个歧义）

### Part 3 带重试的提取（目标 10 分钟）

坑：
- `max_retries=3` 是最多 4 次尝试。`range(max_retries)` 少一次。
- 第一次调用的 note 是 None。之后每次只带上一次尝试的 `feedback()`：沿用第一次的反馈、或者把历次反馈拼在一起，测试都会查出来。
- 拒答是终态：第一次就拒答，或者失败一次之后拒答，都马上结束，不再调用模型。
- "Here is your JSON:" 开头的回复是 parse error，要反馈给模型重试。截出花括号之间的部分看着省事，但这样存下来的不是模型说的话，模型的问题也被藏起来了。课里把 leaked prose 列为直接要 JSON 的六种失败之一。
- 业务规则只在 schema 通过以后检查。在 violation 上算总额，缺了 `unit_usd` 的那一行会报 KeyError。
- 总额要精确比较 Decimal：浮点算出来是 219.98000000000002；`Decimal(49.99)` 带进来的是二进制展开；quiz Q10 的参考写法允许 0.01 的误差，这里要求精确，差一分钱就是错；`quantize` 到分会把 0.375 变成 0.38，每行先 `quantize` 再相加也一样；按字符串比较，220 和 220.00 就不相等了。把容差改小也过不去：0.3751 对 0.375 会查出半分钱以内的容差；`math.isclose` 是相对误差，2,500 万的发票差一分钱它也放过。
- 总额检查判出的 violation 要带着错误和 payload，反馈里才会有 `$.total_usd: expected 219.98, ... (value: 219.99)`。消息里的期望值原样打印，0.375 不能写成 0.38。
- 重试用完以后，返回最后一次的结果。

追问：
- "Why not retry a refusal?"（拒答是模型的判断，重试只会浪费钱，或者逼出编造的内容；课里说 Phase 14 · 09 把拒答当安全信号）
- "The feedback echoes what the model wrote. Any risk?"（文档里的内容可能被模型抄进字段，再回到提示词里，是一条注入路径；反馈要限长，只带前 N 个错误）
- "What would you put on a dashboard?"（三种失败各占多少、每份文档平均重试几次、拒答率、放弃率、总额不符的比例）
- "The provider now has strict mode. What code goes away?"（parse error 和 violation 那两支；拒答和总额检查还要留着）

### Part 4 约束解码（目标 16 分钟）

坑：
- 输出是 bytes，每个选中的 token 一块，按 UTF-8 编码。产出 str 时，测试报 "decode yields raw bytes"。
- 带引号的 JSON 字符串字面量互相不是前缀，所以把 `"EUR"`、`"ABC-12"` 这样整个当一段来匹配最稳。把引号和内容拆开，就会掉进两个前缀陷阱：内容 EU 只是 EUR 的前缀，不能接收右引号；ABC-1 已经是一个完整成员，但 ABC-12 还能接着写，不能强迫它马上闭合。
- 一个 token 会跨过好几段语法，比如 `R","line":{"sku":"ABC-1`、`²"}`、`,"unit":"pcs"}}`，要逐个字符走状态机。只看 token 的第一个字符，会让 `cur":"USD"` 混进来。
- `json.dumps(member)` 默认把 ² 转成 `\u00b2`，模型给的 `²"}` 就被屏蔽了，输出变成 "m"。docstring 写了非 ASCII 字符按原样写。
- EOS 只在输出完整时允许。对象的右括号出来以后什么都不能再跟，直接结束，不再问模型（测试会核对每一次调用）。单独一个整数时，有数字以后 EOS 才允许；`0` 已经完整，而且后面不能再跟数字。
- 整数不能有前导零（05、07），minimum 0 也排除了负数。
- 整数至少要有一位数字。在 `"qty":` 后面，模型给的 `,"unit":"m²"}}` 想把数量跳过去，要屏蔽掉。整数遇到非数字就结束、却不查有没有写过数字的实现，会放出 `"qty":,`。
- 没有一个候选合法时抛 ValueError。悄悄结束或者硬选第一个，都会把不合法的输出交出去。
- 选中一个 token 就要马上产出。测试只拉一块，然后检查模型只被调用了一次。
- 属性按 properties 的顺序，不是字母序；不允许空白。
- 每一步取第一个合法的候选，不是最长的那个。

追问：
- "A real vocabulary has 100k tokens. You can't walk each one every step. How do you scale this?"（按状态预先算好允许的 token 集合，用 token 前缀树一起走；课里说 outlines 这类库就是从 schema 建确定性有限自动机再屏蔽 logits）
- "Byte-level tokenizers can split ² across two tokens. What changes?"（状态机要在字节上走，允许停在半个字符中间）
- "Can the decoder enforce total = sum of lines?"（跨字段的算术不是有限状态能表达的，这类规则还要像 Part 3 那样事后检查）
- "Masking forced the model onto a token it scored low. What does that cost?"（输出分布被扭曲，内容质量可能下降；所以要留拒答的出口）
- "After a bare 0, does your decoder ask the model again?"（测试不查这一点，再问一次输出也一样。`0` 后面不能再跟数字，docstring 说这时不再问模型，参考实现直接结束；多问一次就是多一次前向计算）

### Part 5 判别式 oneOf（目标 12 分钟）

坑：
- 有 discriminator 时，按 kind 选分支，只报这个分支的错误。把每个分支都校验一遍再合并，连正确的数据都会报错；挑错误最少的分支，未知 kind 时报的是别的分支的错误。
- 未知 kind 报在 `.kind` 上；缺 kind 报 `missing required field`，也在 `.kind` 上；不是对象的元素（"USB cable"）报 `expected object`，在元素自己的路径上。先读 `value[tag]` 再判断类型，字符串会走到 `"kind" in "USB cable"` 这条岔路上。
- 选中的分支要带着当前的 loc 去校验，路径才会是 `$.line_items[3].parts[1].hours`。
- bundle 的 parts 里又是一层判别式 oneOf，靠 validate 的递归自然就能处理。
- 没有 discriminator 时要恰好匹配一个分支。整数也是 number，所以 discount 为 1 时两个分支都匹配，是错的；-1 一个都不匹配；5 只匹配整数分支。写成“匹配一个以上就行”是 anyOf 的语义。
- 一个分支都不匹配时只报一条，不要把每个分支的错误都列出来。

追问：
- "Why does a discriminator give better feedback to the model?"（知道模型想写的是哪一种，只把那一种的错误告诉它；没有 discriminator 时只能说“哪个都不像”或者把所有分支的错误都倒出来）
- "How would you make the discount branches disjoint?"（加标签字段，或者让两个分支的取值范围不重叠）
- "Bundles inside bundles?"（用 `$defs` 加 `$ref` 写成递归 schema；递归跟着数据走，数据是有限的 JSON，所以一定会停）
- "Exercise 2 says strict mode has subtle rules for this. How would you check before shipping?"（照课里说的去读 OpenAI 的 structured outputs 指南，再用真实请求验证 schema 能被接受）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出金额精度、崩溃安全、拒答处理、词表规模、失败率监控 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
