# 面试官手册：FieldShape（11/03）

候选人计时期间不要看。候选人手里只有 README、`fieldshape/` 和 `tests/`。

## 开场（2 分钟）

- 总时长 60 分钟，含开场 2 分钟。请候选人边做边说明想法，可以提问、查官方文档。
- 五关参考时长为 10、11、16、11、10 分钟，合计 58 分钟。记录变绿时间、pytest 次数和提示次数。时间分配未经真人校准。
- 不代写；卡住约 5 分钟后，一次只给一级提示。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | bare list 的元素类型呢？ | "The flat adapter's legacy list means an array of strings. Typed arrays belong to Part 3." |
| 1 | 有 default 就是 optional 吗？ | "No. Only required controls key presence. Defaults are metadata and are never injected." |
| 1 | optional 加 default None 能接受 null 吗？ | "No. Omission is allowed; explicit null still has to satisfy the declared type." |
| 2 | codec 要实现吗？ | "No. The tagged codec is supplied. Persist its complete descriptor, not a compiled schema." |
| 2 | 保存失败怎么办？ | "Propagate the failure and keep the previous snapshot readable and unchanged. Remove temporary files." |
| 2 | 1e0 的原始拼写要保留吗？ | "No. Metadata contains JSON values, not numeric source lexemes." |
| 3 | 要实现全部 JSON Schema 吗？ | "No. Compile only the documented object, typed array and scalar subset, and reject the listed malformed declarations." |
| 3 | array item 的 required=False 是什么？ | "An item wrapper carries scalar constraints. Its required/default annotations do not create optional elements." |
| 3 | minimum 和 minItems 放在哪里？ | "Numeric bounds belong to the scalar; cardinality belongs to that exact array." |
| 3 | 同一个 ModelSpec 可以重用吗？ | "Yes. Compile independently owned output branches and reuse the repaired leaf adapter." |
| 4 | 要剥 fence 或重试吗？ | "No. Parse each completed string as supplied and report either parse failure, schema failure or success." |
| 4 | schema failure 要返回 parsed data 吗？ | "Yes. Keep the raw text, parsed evidence and every validator issue." |
| 5 | a.b 和 x[0] 是路径表达式吗？ | "No. String segments are literal keys. Integer segments are array indices." |
| 5 | 一个 path 有多条错误呢？ | "Keep every issue in input order. Root and parent issues coexist with children." |

## 每关：要看什么、提示、追问

### Part 1 修 flat adapter（目标 10 分钟）

四层缺陷：

1. legacy array 的 items 放了 Python `str` class，没转成 schema fragment。服务先生成 schema，再交给正确 validator；错误到递归 item 消费者调用 `.get` 才报 AttributeError。不能去改坏 validator 以吞掉错误。
2. required 从 `default is None` 推断，忽略显式 required 标志。有默认值仍可 required，optional 默认 None 仍可省略；默认描述不决定 null 合法性。
3. minimum/maximum 用 truthiness 过滤，零边界丢失。端点是 inclusive。
4. 每加一个 field 都重建整份 properties 字典。参考版按字段累积，保留所有字段、声明顺序、required 与每个 fragment 的独立所有权。

18,000 字段的本机三次功能已修慢版约 0.495–0.532 秒，参考版约 0.0047–0.0049 秒；限值 0.055 秒。性能只衡量本地 schema 组装，不能跳过属性或共用可变 fragment 来提速。

提示：H1 "What did the producer put in items?"；H2 "Which object reached the recursive validator?"；H3 指向 flat adapter 的 child descriptor。

追问："Does a default imply optional or nullable?"（都不意味着）；"What work grows when one property is added?"（旧 properties 被反复复制）。

### Part 2 descriptor 快照（目标 11 分钟）

坑：

- 存的是 ModelSpec/ArrayOf/SchemaField 描述，不是编译后的 schema。后者没有 default metadata。
- `has_default` 区分 MISSING 和显式 None；codec 已正确给定。enum 顺序、零边界、嵌套节点、Unicode/CRLF 都应重开后相同。
- 字段声明顺序通过 entry list 保留，不能按名称重排。
- 大整数 metadata 不能先转 float。同一个 store 保存新快照后，load 必须读到新内容，不能沿用第一次读取的缓存。
- 先完整编码，再写临时文件并 replace。编码失败或替换失败不能截断旧快照；失败的临时文件要清理。

提示：H1 "Which information disappears in a compiled schema?"；H2 "When can the destination become visible?"；H3 提醒先编码再 replace。

追问："Does this test establish crash durability on every filesystem?"（不；只测本地失败路径和替换边界，不测断电 fsync）。

### Part 3 递归组合 compiler（目标 16 分钟）

这关是独立 TODO：flat adapter 不能处理 ArrayOf(ModelSpec)、多层 typed arrays 或 nested required。

坑：

- ModelSpec 和 ArrayOf 会交替嵌套；递归到 primitive/legacy list 时真实调用修好的 leaf adapter。
- required 只属于声明它的 object；minItems/maxItems 只属于该 array；数值 bounds/enum 只属于对应 scalar。
- 拒绝合同列明的矛盾或错位约束：minimum>maximum、min_items>max_items、负数/bool array size、container 上的 scalar constraint。不冒充完整 schema solver。
- 一个只读 descriptor 可用于多个位置；输出分支独立。default metadata 不生成 nullable/default，也不注入值。ArrayOf 的 item wrapper 只带 scalar constraints，不描述键是否存在。
- `max_items=0` 是只允许空数组的有效上界，minimum=maximum 也是有效的 inclusive 区间。ModelSpec 名称只是标签，同名而字段不同的对象不能合并。

提示：H1 "What are the possible child node kinds?"；H2 "Which layer owns this constraint?"；H3 提醒 object/array 分别递归，并在 leaf 调已有 adapter。

追问："How does this differ from the flat converter?"（新的是组合树递归及各层约束与矛盾校验）；"Would $ref need more work?"（本题没有引用解析）。

### Part 4 完成抽取的结果回放（目标 11 分钟）

async envelope、source close 和 NDJSON 编码已正确给定。候选人实现完成字符串到事件的分类。

坑：

- parse_error 是 json.loads 没完成解析；schema_error 是有 parsed value 但违反 schema。合法 JSON null 也需要作为数据验证，不能当作 parse_error。
- schema failure 保留 parsed evidence 和全部 typed issues，不能删无效数据、只留第一条或偷偷做类型转换。
- 每个 raw 都保留原文、按到达次序产生一个事件。给定外壳在读取下一条之前 yield，文本里的换行由 JSON 转义。
- 合法 JSON 前后的空白也属于 raw 证据。小数不截断；fence 包住的对象仍然是 parse_error，不从文字中提取 JSON。

提示：H1 "Did JSON parsing succeed?"；H2 "What evidence should a failed validation retain?"；H3 指向 parse 与 validate 两个阶段。

追问："Would retrying belong here?"（不；这里只回放完成结果，不实现13/04已有的 retry engine）。

### Part 5 typed error tree（目标 10 分钟）

validator 和 typed issue adapter 已正确给定，这关只分组。

坑：

- tuple 里的 string 是 literal key，不能解析 dot/bracket；int index 与同拼写 string key 不同。
- 每个节点可同时有自身 issues 和 children；同一个 path 的多条错误全部保留输入顺序。
- 新报告、兄弟节点各自拥有 list/dict，不能共用累积容器，也不能修改给定 issues。
- 空字符串也是 literal key；同一路径的完全相同错误仍要重复保留。不能为了整理报告给输入列表排序。

提示：H1 "Is the path already structured?"；H2 "Can this node have both an error and children?"；H3 指向逐 segment 下沉、到终点追加。

追问："Can this Python tree be dumped directly to a JSON object without a key policy?"（混合 int/string child keys 需要另定 wire policy；本题只生成 Python report）。

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 从错误消费者追到 descriptor 生产者，逐层验证 |
| 代码质量 | 15 | 边界明确、线性组装、独立所有权、不凑测试 |
| 沟通 | 15 | 主动澄清 required/default/null、constraint 所属位置 |
| 生产意识 | 10 | 替换失败、证据保留、子集边界与本地回放限制 |

每项写具体观察证据，没观察到就写“未观察”。
