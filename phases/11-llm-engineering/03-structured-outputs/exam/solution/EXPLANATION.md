# 参考答案讲解：FieldShape（11/03）

计时结束后再看。参考实现在同目录的 `fieldshape/`，所有输入都是本地数据。

## Part 1 修 flat adapter

items 需要 schema dict，不能直接放 Python str class。正确 validator 递归到 array item 才碰到 `.get` 报错；根因是上游 adapter，不能让消费者忽略它。

required 由显式标志决定。default 是描述信息，None 也只是一种元数据；optional 键可以省略，但显式 null 仍不能冒充 string。minimum/maximum 用存在性保留 0。

性能缺陷在每个 field 都复制旧 properties，累积成二次工作。参考版用一次字典累积，并为每个 fragment/enum 保留独立对象。18,000 字段本机三次功能已修慢版约 0.495–0.532 秒，快版约 0.0047–0.0049 秒；0.055 秒限值两边余量都超过 8 倍。这里只测本地 schema 组装 CPU 时间。

## Part 2 descriptor 快照

tag codec 保留 ModelSpec、ArrayOf、primitive 与 SchemaField，以及字段顺序和 has_default。编译 schema 会丢 metadata，不能替代 descriptor。JSON values 保留通常值语义，不宣称保留 1e0 的原拼写。

先完成编码，在同目录临时文件写好后 os.replace；finally 清掉临时文件。编码或替换失败保留旧文件。测试没有模拟进程断电，也没证明所有文件系统的 crash durability。

JSON 大整数 metadata 不经过 float，CRLF 原样保留。同一个 store 在成功替换后也必须重新读到最新完整快照，第一次 load 的缓存不能代替磁盘内容。

## Part 3 递归组合编译

P1 的 flat adapter 仍然只认识 primitive 和 legacy list[str]。P3 新增 node 递归：ModelSpec 编译每个字段并收集该层 required；ArrayOf 编译 item 并留住该层 minItems/maxItems；叶子调用已有 adapter。

数值 bounds 与 enum 留在对应 scalar，不能上移到 array；nested required 不能拿根对象那一份。编译前拒绝明确列出的反向 bounds、反向 cardinalities 和错位约束。这是有限子集检查，不是完整 JSON Schema satisfiability solver。

同一个 descriptor 在多处出现时分别递归生成输出，调用方改一处 schema 不影响另一处或原 descriptor。数组元素 wrapper 的 required/default 不表示可缺的元素，default 不写成 nullable 或注入值。

`max_items=0` 不能被 truthiness 丢掉；minimum=maximum 是有效的 inclusive 区间。ModelSpec 的 name 不是引用注册表的键，同名但声明不同的对象必须按各自字段编译。

## Part 4 完成抽取回放

先 json.loads。JSONDecodeError 产生 parse_error；解析成功再调用正确 validator，有 issues 为 schema_error，没有为 ok。无效数据仍然保留 raw、parsed data 与完整 issue 证据；null 是成功解析的值，应交给 schema 判断。

raw 包括 JSON 前后的空白；成功或 schema failure 的小数证据都不截断。fence 包住的 JSON 仍是 parse_error，不能套用 source 中提取 JSON block 的便利函数来改变本题合同。

async envelope 与 NDJSON 编码给定正确：一条 raw 处理后先 yield，再拉下一条。编码保留 Unicode 并转义文本换行。它是本地完成消息回放，不是模型 token streaming，也不实现重试或 constrained decoding。

## Part 5 typed issue 分组

tuple path 已经消除了 dotted string 的歧义。逐 segment 建 children，末端 append issue，根路径就是 root。string key 和 int index 保留本来类型；父 issues 与 children 并存，同位置多条错误不覆盖。

空字符串也是合法的 literal key。完全相同的重复错误仍逐条保留；输入顺序就是证据顺序，不先排序或去重。

输出是 Python report，不定义混合 key 的 JSON wire。给定 validator 负责验证数据，候选人只组织其证据，不重新实现 oneOf 或 discriminator。

## 这套题证明了什么，没证明什么

通过说明你能修复 flat schema producer、持久化 descriptor、编译 source-native typed object/array 组合、区分完成抽取的 parse/validation 结果并组织 typed errors。它没有调用真实 LLM、测量抽取准确率、实现 provider strict schema、token-prefix DFA、retry engine、完整 JSON Schema 或引用解析。60 分钟的难度与时间分配尚未经过真人校准。
