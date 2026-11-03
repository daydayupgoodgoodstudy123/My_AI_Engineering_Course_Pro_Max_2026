# 面试官手册：ToolLint（13/05）

候选人计时期间不要看。候选人手里只有 README、`toollint/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 参数只算 required 里的，还是 properties 全算？ | "Every property. Optional ones are parameters too." |
| 1 | 1024 是字符还是字节？ | "Characters. Python's len of the string is what we want." |
| 1 | 重复名按什么顺序报？ | "Order of first appearance. One finding per name, and the name is the path." |
| 2 | 合法的版本号长什么样？ | "Exactly MAJOR.MINOR.PATCH in ASCII digits, no leading zeros. No v prefix, no pre-release tag, no whitespace." |
| 2 | 1.10.0 发了之后还能发 1.9.1 吗？ | "Yes, patches on older lines are normal. Order by version number, not by time." |
| 2 | 同一个版本能重发吗？ | "No. Releases are immutable. ValueError." |
| 2 | blob 文件坏了怎么办？ | "Refuse to load that release. ValueError." |
| 2 | 没有清单再引用的 blob 要清理吗？ | "Not today." |
| 3 | 放宽类型（string 变成 string 或 number）算兼容吗？ | "Not here. The lesson says loosening needs a new version too. Breaking." |
| 3 | 能不能把改名识别出来？ | "No guessing. A rename is a removal plus an addition." |
| 3 | enum、嵌套属性、描述要不要比？ | "Not today. Presence, type and required, on the top-level properties." |
| 3 | deprecated 标在哪？ | "A top-level \"deprecated\": true on the tool descriptor." |
| 3 | schema 里可以没有 properties 吗？ | "Yes, for a tool with no parameters. Treat it as no parameters." |
| 4 | 没改过的工具还要查重复名吗？ | "Yes. It just isn't linted again." |
| 4 | 重复名那一行放在哪？ | "Right before the second copy's own findings. Once per name." |
| 4 | 一条 finding 都没有时输出什么？ | "The summary with zeros, then PASS." |
| 4 | warn 会让构建失败吗？ | "No. Only block fails the build." |
| 5 | 什么算一次引用？ | "The word use, then a tool name with an underscore. Backticks are fine." |
| 5 | 引用了别的命名空间的工具呢？ | "It's an edge, but it doesn't link anything inside a namespace." |
| 5 | 注册表里没有、前缀也对不上任何工具的名字要报吗？ | "Yes. Anything that isn't in the registry is an unknown tool." |
| 5 | 名字里没有下划线的工具呢？ | "No namespace, so no group check." |

## 每关：要看什么、提示、追问

### Part 1 修 linter（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 组护栏：

1. `lint_tool` 把 `schema.get("required")` 当作参数表交给 `lint_name`。课里的 BAD_REGISTRY 没有 required 列表，传进去的是 None。错误不在 `lint_tool` 报出来，而是在下一层 `lint_name` 的 `m.group(2) not in params` 报 TypeError。只改成 `schema.get("required", [])` 不够：`notes_export_for_user` 的 `user` 是可选参数，照样会被当成写进名字的参数值。`required or properties` 这种兜底也不行，那个工具有一个必填的 `format`。参数就是 input schema 的全部 properties。
2. `lint_description` 用 `len(desc.encode())`，按 UTF-8 字节算长度。600 个汉字加一段英文的描述只有 696 个字符，却有 1,896 个字节，被判成超过 1024。课里写的是 "Stay under 1024 characters"。
3. `duplicate_names` 把每一次出现都列出来，一个名字出现 3 次就报 3 条。
4. 同一行用 `names.count(name)`，是 O(n²)：2 万个名字大约 2 秒，测试的限值是 0.1 秒。
5. 护栏：重复名按第一次出现的顺序列，每个名字一条，finding 的 path 就是那个名字。`sorted(set(...))`、`list(set(...))`、按第二次出现的顺序列、按出现次数排（`Counter.most_common()`，测试里后出现的 `notes_list` 次数更多），或者只报一条“registry has duplicate tool names”，都会挂。为了提速只 lint 每个名字的第一个工具，第二个副本的 finding 就丢了，也会挂。边界上 1024 个字符不报、1025 个报；只数 ASCII 字符的写法在 1100 个汉字那一条上挂。

看什么：是不是读 traceback 时注意到 `lint_tool` 那一行；是不是先 `print(repr(params))` 看实际传了什么；每改一处就重跑。

提示：
- H1："What does lint_name receive as params for get_weather_in_tokyo?"
- H2："Which parameters does notes_export_for_user have, and which of them are required?"
- H3：直接指出 `schema.get("required")`。

追问：
- "Why does the lesson care about characters at all?"（课里说 OpenAI 在 strict 模式下截断过长的描述；按字节数会误伤非英文描述，按字符数也只是近似，真正的上限要看各家文档）
- "get_weather_for_city_by_zip takes city and zip. What does the rule say?"（正则从最左边的 `_for_` 开始取后缀，得到 `city_by_zip`，不是参数名，会被报；这是启发式规则，需要能豁免）
- "The lesson's skill output warns when a registry has more than 64 tools. Where would that check go?"（注册表级规则，放在 `lint_registry` 里，和重复名同一层）

### Part 2 内容寻址的发布库（目标 13 分钟）

坑：
- 版本按语义版本排：1.10.0 在 1.9.0 之后，1.2.10 在 1.9.0 之前。按字符串排、把点去掉当整数排都会错。
- 补丁可以晚发：1.9.1 和 1.2.10 在 1.10.0 之后才发布，`versions()` 和 `history()` 仍然按版本号排，不按发布时间，也不按目录列出的顺序。
- 版本格式：恰好三段 ASCII 数字、没有前导零。`int()` 会接受 `"02"`，也会接受末尾带换行的 `"0\n"`；正则用 `$` 结尾同样会放过末尾的换行（从 VERSION 文件读出来的版本号常带这个换行），要用 `fullmatch`。
- 内容寻址：blob 的文件名就是它的字节的 SHA-256，字节就是 `encode_descriptor()` 的输出。用默认的 `json.dumps`（`ensure_ascii=True`）写 blob，中文描述的字节就不一样了，文件名和内容对不上。同一个 descriptor 跨版本只存一份，测试数 `blobs/` 里有几个文件。
- 往返：`maximum: 50` 和 `50.0` 在 Python 里相等（`50 == 50.0`），字节不同，摘要也不同。“和上一版的 descriptor 相等就复用它的摘要”这种优化，会把 1.10.0 里的 50.0 读回成 50。测试用 `encode_descriptor` 比较读回的结果，int 和 float 的区别躲不过去。
- 清单要保持发布顺序，`json.dumps(manifest, sort_keys=True)` 会把工具顺序打乱。
- 读 blob 时校验摘要，校验的是读到的字节。测试先在一个 blob 末尾加一个换行，再把它改成另一段合法的 JSON，两次 `load` 都必须报 ValueError。先 `json.loads` 再用 `descriptor_digest` 重算，校验的是重新编码后的内容，多出来的换行查不出来。改坏的 JSON 本身就会报 JSONDecodeError（它是 ValueError 的子类），所以测试特意不用坏 JSON。把 descriptor 缓存在内存里的写法发现不了篡改。
- 发布不可变：同一版本再发一次、同一版本里两个同名工具、格式不对的版本号，都是 ValueError；被拒绝的发布不能留下 blob 或清单，所以先校验再写。测试里这三种被拒的发布都带着一个新的 descriptor（`notes_browse`），版本存不存在、格式对不对，只要有一项放到写 blob 之后才查，`blobs/` 里就会多一个文件。用 `open(path, "xb")` 排他创建清单可以防并发，但它抛的是 FileExistsError，要转成 ValueError。
- 未知版本报 KeyError，不是 FileNotFoundError，也不是空列表。
- 用 `Path(version).with_suffix(".json")` 拼清单路径，1.9.0 和 1.9.1 都会变成 `1.9.json`。

追问：
- "Two CI jobs publish at the same time. What can go wrong, and what would you change?"（两个人同时写同一个版本；先写 blob、最后写清单，清单用临时文件加 `os.replace`，或者用排他方式创建）
- "Some blobs aren't in any manifest any more. How do you clean them up safely?"（从所有清单出发标记，再清扫；不要和发布同时进行）
- "encode_descriptor sorts keys. What does that buy, and what does it give up?"（键顺序不同的同一个 descriptor 得到同一个摘要；读回来的键顺序是排过序的，不再是作者写的顺序）
- "The quiz suggests pinning a third-party server's descriptor hashes to catch drift. How is that different from this store?"（这里记录的是我们自己发布了什么；pin 是检查对方现在给的描述和当初审核过的是否一样，测验 Q16 提到的防护，第 15 节展开）
- "The docstring says ASCII digits. Isn't `\d` the same as `[0-9]`?"（不一样。Python 的 str 正则里 `\d` 匹配所有 Unicode 十进制数字，`int()` 也认，`1.1٢.0` 会被当成 1.12.0；用 `[0-9]` 或 `re.ASCII`。测试没有覆盖这一条）

### Part 3 破坏性变更分类（目标 12 分钟）

坑：
- 放宽类型也算破坏。课里明说 "Loosen (string to string-or-number) requires a new version"，很多 API 兼容性检查器会把放宽当成兼容。
- 可选变必填是破坏，必填变可选是安全的。新加的参数要看它是不是必填，必填的只报一条 added required，不要再报一条 made required。删掉参数是破坏，带着它的旧调用会失败。
- 类型按集合比较：`"string"` 和 `["string"]` 一样，`["string", "number"]` 和 `["number", "string"]` 一样。没有 type 表示接受任何类型，给它加上 type 就是改了类型。直接比较 `prop != new_prop` 会把只改了描述的参数也报出来。
- 没有 required 列表就是什么都不用填（BAD_REGISTRY 里的 schema 就没有），没有 properties 就是没有参数（`notes_count` 就没有），用 `schema["required"]` 或 `schema["properties"]` 去读都会 KeyError。
- 删除工具：只有上一版标了 `deprecated: true` 的才安全。在新版里找这个标记是错的，工具已经不在新版里了。
- 已经 deprecated 的工具在下一版仍然 deprecated，不要再报一次 "deprecated"。
- 改名就是删除加新增，不按 schema 相同去猜。课里的做法是先加 `get_weather_v2`、把旧的标成 deprecated，下一版再删。被删工具的参数不要逐个再报 removed，新工具的参数也不要逐个报 added。
- 一个参数可以同时改类型又变成必填，比如改成 strict 模式的写法：全部字段都 required，原来可选的改成可空。两条都要报，写成 elif 链只会报一条。
- 输出按 path 排，同一个 path 再按 change 排，不先按 breaking / safe 分组。
- 最后一段是端到端：给好的 `ToolRegistry` 用 Part 1 的 lint、Part 2 的库和这里的 diff 组成发布闸门。补丁版本 1.0.1 和它下面的 1.0.0 比，不和最新的 2.0.0 比。

追问：
- "An enum value is added or removed. Breaking or safe?"（删值是收紧，旧调用可能失败；加值按本课放宽的规则也要新版本；本题不要求）
- "What about nested object properties?"（要递归比较；本题和课里的 linter 一样只看顶层）
- "Why give the tool a new name instead of bumping the release's major version?"（模型按名字选工具、按名字发调用；同一个名字背后的合同变了，旧的 prompt、评测集和调用记录都会对不上）
- "How does the model learn that get_weather is deprecated?"（在描述里写明，并指向 get_weather_v2，正好是 Part 5 检查的那种引用）

### Part 4 分页注册表的流式检查（目标 13 分钟）

坑：
- 每一行就是 `str(finding)`：severity 按课里的宽度 5 补齐，是 `[warn ]` 和 `[nit  ]`。自己拼 f-string 会写成 `[warn]`。行尾不带换行。
- 重复名在第二次出现时报一次，放在这个副本自己的 finding 前面；第三次出现不再报。每页单独调用 `lint_registry`，只能在页内找到重复，而且会把重复放在页首。重复按名字判断，不按摘要：投毒的 `notes_list` 和正常的 `notes_list` 内容不同，名字相同，也是重复。
- 空页不是结束。
- 第二个副本照样要 lint，它的 finding 一条不少。
- summary 统计输出过的每一行，duplicate 也算在内。最后一行是结论：只有 block 才 FAIL（练习 4：fail the build on severity block findings），只有 warn 是 PASS。duplicate 也是 block：baseline 那一段唯一的 block 就是重复名，结论是 FAIL。空注册表也要有 summary 和 PASS，照搬课里 `report()` 的 "PASS : no findings" 会挂。
- baseline：摘要和上一版清单一致的工具不再 lint，但仍然参与重复名检查；不在 baseline 里的新工具要 lint；按名字而不按摘要比较，会把改过的工具漏掉。也不要把 baseline 里的名字预先当成“见过”，那样没改过的工具第一次出现就被报成重复。测验 Q15 的参考答案说 CI “只对本次 PR 改动的工具报告”，就是这个用法。
- 及时输出：第一行要在拉取第二页之前出来。先把所有页读完，或者为了判断哪一页是最后一页而预读一页，测试都会抓到。一页之内先攒齐再输出，测试分不出来，可以接受。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要看得出这里需要 async generator。

追问：
- "50,000 tools. What does lint_stream keep in memory?"（见过的名字和各级计数就够了，不必留着所有 finding）
- "CI wants an exit code. Where does it come from?"（看最后一行的结论；或者在 `lint_stream` 外面包一层，遇到 block 时退出码为 1）
- "The source fails on page 7. What should the log show?"（已经输出的行保留，不能再输出 summary 和 PASS，异常往上抛，让 CI 失败）
- "Linting only what changed: what can go wrong?"（规则本身改了，旧工具不会被重新检查；可以把规则版本也放进 baseline）

### Part 5 描述的交叉引用图（目标 12 分钟）

坑：
- 引用是 "use" 加一个带下划线的工具名，可以有反引号，名字后面的标点不算。用 `split()` 会得到 `` `notes_get`. `` 和 `weather_forecast.` 这样的词。
- "use when"、"use for"、"use this" 不是引用。"reuse notes_cache" 里的 use 不是一个单词。句首大写的 "Use notes_list" 是引用。随便哪个带下划线的词都算，会把 `notes_cache` 也算进来。
- 同一个工具提到两次只算一条边，指向不存在的工具也只报一次。
- 工具名可以有数字和多个下划线：`geo_lookup` 指向 `maps_route_v2`。`[a-z]+_[a-z]+` 会把它截成 `maps_route`，字符集里没有数字会截成 `maps_route_v`。
- 悬空引用就是注册表里没有的名字，不管它在哪个命名空间。`maps_route_v2` 的 maps 前缀在注册表里一个工具都没有，照样要报。测验 Q11 的 `lint_cross_refs` 只查和已有工具同前缀的名字，照搬会漏掉它；只查本工具自己的命名空间也会漏。
- 自引用单独报，不算悬空引用。`weather_forecast` 的描述写着 "use weather_forecast instead"，是典型的复制粘贴错误。图里要保留这条自环，测试会检查。
- 命名空间是第一个下划线之前的部分，`notes_purge_all` 属于 `notes`。按最后一个下划线切，它会自成一组。
- 只有同一个命名空间里两个工具之间的引用才把它们连起来，方向不限。经过别的命名空间绕过去（`weather_alerts` → `geo_lookup` → `weather_now`）不算；指向不存在的工具也不算，否则 `notes_archive` 和 `notes_purge_all` 会被一个不存在的 `notes_trash` 连到一起。
- 课里的 GOOD_REGISTRY：`notes_search` → `notes_list` 只有一个方向，也算连上了；按有向可达去算会把它们拆成两块。
- 输出顺序：先是逐个工具的 finding（注册表顺序，每个工具内按引用出现的顺序），再是分组的 finding（按前缀排）。每块里的名字排序，各块按第一个名字排。

追问：
- "notes_* has 40 tools. Is 'one connected piece' still a useful rule?"（组大了以后连通很容易达到，也说明不了什么；更有用的是找出描述最像的成对工具，看它们是否互相指向）
- "The quiz's lint_cross_refs only flags unknown names that share a prefix with an existing tool. Why might you want that?"（测验的写法不要求前面有 use，描述里带下划线的参数名，比如 note_id，也会被当成工具名，限定同前缀能少报误报；代价是漏掉 `maps_route_v2` 这种指向别的服务的引用。这里要求 use 后面紧跟名字，误报已经少了）
- "What changes if the whole pattern gets re.IGNORECASE?"（工具名那一段也不分大小写了，`use MAX_RESULTS` 这类常量会被当成引用。参考答案只让 use 不分大小写：`(?i:use)`。测试没有覆盖这一条）
- "A deprecated tool should point at its replacement. How would you check that?"（`deprecated: true` 的工具，描述里至少要引用一个没有弃用的工具）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发发布、垃圾回收、弃用流程、CI 退出码、启发式规则的误报 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
