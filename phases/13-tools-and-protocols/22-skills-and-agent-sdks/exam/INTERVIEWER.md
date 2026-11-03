# 面试官手册：SkillPack（13/22）

候选人计时期间不要看。候选人手里只有 README、`skillpack/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | U+2028、换页符算换行吗？ | "Only \n ends a line, with an optional \r before it. The tests don't send the others." |
| 1 | 文件开头带 BOM 呢？ | "Reject it, as the lesson does: the first line must be exactly ---. The tests don't send one." |
| 1 | 数字开头的名字合法吗？ | "Yes. 2fa-helper is a valid name." |
| 1 | macOS 的目录不区分大小写，目录名还要精确比较吗？ | "Yes. Compare exactly. The name is the skill's identity." |
| 2 | 写之前要不要先校验名字和描述？ | "No. The writer writes what it's given. Validation is Part 3." |
| 2 | 用单引号还是双引号？ | "Double quotes, written by json.dumps with ensure_ascii=False." |
| 2 | 字段按什么顺序写？ | "As given." |
| 2 | user-invocable: false 要加引号吗？ | "No. A runtime extension keeps its host's YAML type." |
| 2 | 能写 \|- 吗？ | "No. The parser only reads \| and >." |
| 2 | metadata 是空的 map 怎么办？ | "ValueError. A bare metadata: line reads as null in YAML." |
| 3 | 名字同时有两个问题？ | "Report the first one, in name_issue's order." |
| 3 | 语法错误时还要报扩展字段吗？ | "No. One issue, frontmatter-syntax." |
| 3 | allowed-tools 里两个工具之间有两个空格？ | "Fine. Only whitespace other than spaces is a problem." |
| 3 | allowed_runtime_extensions 一定是 set 吗？ | "Any iterable of field names." |
| 4 | 校验失败，后面什么都没发生，这个会话算失败吗？ | "No. The host did the right thing. That session is ok." |
| 4 | 同一个阶段出现两次？ | "Not in the tests. A stage only needs the stage NEEDS names to have happened." |
| 4 | 不认识的阶段？ | "Not in the tests. Tell me what you would do." |
| 4 | 流结束时还没结束的会话？ | "One line each, in the order the sessions opened, then the plan." |
| 4 | 还开着的会话最后一个事件是没验证的工具调用？ | "It never ended, so session not ended, unless it already had a problem. The tests don't send one." |
| 4 | 计划行能放在最前面吗？ | "No. N isn't known until the stream ends." |
| 5 | "call the x skill" 也算引用吗？ | "No. Only invoke the \`name\` skill." |
| 5 | 一个引用后面跟了两个护栏？ | "Both cover that same reference. The tests don't send that." |
| 5 | 护栏写在下一段里还算吗？ | "Yes. It covers the nearest reference before it. The tests don't put one there." |
| 5 | 依赖缺失的技能还要安装吗？ | "Yes. Install it and report the edge. Skills don't import each other." |
| 5 | 会有环吗？ | "No cycles in this data." |
| 5 | ~~~ 也算代码块吗？ | "Only \`\`\` fences." |

## 每关：要看什么、提示、追问

### Part 1 修 frontmatter 和命名（目标 12 分钟）

一个测试里叠了 5 个缺陷和几道护栏：

1. `line_content` 只去掉 `\n`，`\r\n` 里的 `\r` 留在了行里。错误不在这里报出来：测试看到的是 `parse_frontmatter` 抛出 `SKILL.md must begin with an exact --- line`，可文件第一行明明就是 `---`。打印 `repr` 才看得到 `'---\r'`。
2. `decode_scalar` 处理单引号时只去掉两头的引号，没有把 `''` 还原成 `'`。docstring 写了 `''` 代表一个 `'`，这是 YAML 单引号标量的转义规则，本课 `code/main.py` 的 `_decode_scalar` 也是这么做的。
3. `NAME_PATTERN` 写成了 `[a-z0-9-]+`，连字符开头、结尾、连续两个都放过。本课的规则是小写字母和数字，组与组之间用单个连字符：`[a-z0-9]+(?:-[a-z0-9]+)*`。
4. `name_issue` 用 `lower()` 比较名字和目录，`Release-Readiness` 目录也算匹配。docstring 写的是 exactly。
5. `split_lines` 每切出一行，就把剩下的文本整个复制一遍（`rest = rest[cut:]`），是 O(n²)。2.6 MB、5 万行的 SKILL.md，本机实测 1.0 到 1.9 秒，限值 0.1 秒；改成按位置切以后，中位数 5 到 9 毫秒。

护栏：

- 修 CRLF 不能把缩进也去掉。用 `line.strip()` 的话，`>` 块和 metadata 下面的缩进行变成了顶层行，第一条断言就报 `malformed top-level line 4`。只在比较 `---` 时去掉 `\r` 也不行，description 里会留下 `\r`。把行尾写成 `line[:-2] if ... else line[:-1]`，没有换行的最后一行会被砍掉一个字符，结束行就是最后一行时报 `needs a closing --- line`。
- 名字规则不能修过头：`2fa-helper`（数字开头，本课测验第 2 题的解析明确允许）、`v2`、`a`、`skill-contract-reviewer`（两个连字符）、64 个字符都合法。本课 CoderPad 版的题面要求字母开头，这里不是。用 `re.match` 代替 `fullmatch` 会放过 `release-`；写成 `^...$` 再配 `re.match`，`$` 能匹配末尾换行前的位置，会放过 `"release-readiness\n"`（双引号的 name 能写出这个值）；用 `isalnum()` 加 `islower()` 会放过 `café-notes`。
- 提速不能改变语义。用 `text.find("\n---\n")` 找结束行，CRLF 文件和“结束行就是最后一行、后面没有换行”的文件都会出错；按固定的 4 个字符切出正文，CRLF 文件的正文开头会多一个 `\n`；`text.split("\n")[:-1]` 会丢掉没有换行的最后一行；改用 `partition` 仍然每行复制一次剩余文本，照样慢。
- 测试不拦 `line.rstrip()`：它会把 `--- ` 也当成结束行，和 docstring 的 exactly 不一致，追问时可以问。
- 测试不拦 `splitlines(keepends=True)`。它也是线性的，但会在 U+2028、换页符、单独的 `\r` 处断行，和 docstring 说的“只有 `\n` 结束一行”不一致。用它的候选人，追问第一条。

看什么：是不是先读报错、再打印实际收到的那一行，而不是盯着 `parse_frontmatter` 的条件改；修名字规则时有没有先列出合法和不合法的例子；修性能之前有没有先找到是哪一行慢（`cProfile`，或者按函数分别计时）。

提示：

- H1："The file starts with ---. What does the parser actually compare?"
- H2："Print repr() of the first line that reaches the check."
- H3：直接指出 `line_content` 只处理了 `\n`。

追问：

- "Your fix uses splitlines(). What does it do with a U+2028 inside a description?"（会在那里断行，后半截变成一行没有冒号的顶层行，报 malformed。YAML 1.2 也只把 `\n` 和 `\r` 当换行）
- "Why compare the name with the directory exactly, when macOS folders ignore case?"（Linux 上两个只差大小写的目录可以同时存在；大小写不敏感的比较会让两个包都自称 release-readiness。讲义：目录才是部署单元）
- "The lesson's parser strips the body. This one keeps it as written. Why would a host care?"（宿主可能对正文算摘要来缓存或锁版本；strip 会把只差首尾空行的两个版本当成同一个。反过来，如果在解析前把 CRLF 统一成 LF，正文也就不是原样了，测试不查这一点，问候选人怎么取舍）
- "Where else does a 2.6 MB SKILL.md hurt?"（激活时整个正文进入模型上下文。讲义说 Disclosure 只在需要时才读 references；大块内容应该放进 references 里，而不是塞进正文）

### Part 2 写回 SKILL.md（目标 12 分钟）

坑：

- 什么时候要加引号，规则全在 docstring 里，一条一条照做：空字符串、首尾有空白、以 YAML 指示符开头、含 `": "` 或 `" #"`、以 `:` 结尾、含 `isprintable()` 拒绝的字符。本课测验第 7 题：`description: Use when: deploying` 本课的解析器读得了，PyYAML 会抛 ScannerError。
- 只有 `" #"` 才开始注释，`C# release notes` 不用引号；只有 `": "` 才是键值分隔，`Bash(git:*) Read` 不用引号。见到 `#` 或 `:` 就加引号，精确文本那条断言会挂。
- 指示符要按 docstring 的整张表来：只照着解析器拒绝的 `[ { & * !` 写，或者只记开括号，`] closing`、`} closing`、`, and more` 会写成 plain，精确文本对不上。
- 核心字段和 metadata 的值在可移植合同里是字符串。YAML 会把 `22`、`1.0`、`.5`、`+1` 读成数字，把 `true`、`~`、`null` 读成布尔值或 null；YAML 1.1 的解析器（例如 PyYAML）还会把 `2026-10-30` 读成日期，把 `yes`、`no`、`on`、`off` 读成布尔值。所以这些都要加引号。本课自己的 `SKILL.md` 就写成 `lesson: "22"`，第一条断言就是把它原样写回来。词要整词匹配、不分大小写：`No`、`NULL` 加引号，`Yesterday's null results` 不加。
- 运行时扩展字段的类型归宿主管：`user-invocable: false`、`disable-model-invocation: true` 保持原样。加了引号，宿主读到的就是字符串 `"false"`。
- 带换行的值写成 `|` 块，每行缩进两格，空行保持为空行。但这个解析器会去掉块里每行的前导空白和整个值的首尾空白，`\r\n` 也会被当成换行，所以行首有空白、以换行开头或结尾、含 `\r`、有制表符的值都要退回双引号。metadata 的值从不写成块：嵌套映射读不了块。写成 `>` 会把换行变成空格。
- 双引号用 JSON 的写法，`ensure_ascii=False`。`json.dumps` 默认把 `東京` 写成 `東京`，读得回来，但精确文本对不上。`repr()` 和 YAML 的单引号写法也都不对。
- 字段按给定的顺序写，正文紧跟在结束行后面，一个字符都不改。在 `---` 后面多加一个空行、strip 正文、按字段名排序，第一条断言就挂。
- 这个子集装不下的就报 ValueError：`allowed_tools`（解析器不认下划线，本课测验第 12 题）、工具列表、两层的 metadata、metadata 以外的字段给了映射、不是字符串的值、带空格的 metadata 键、空的 metadata。

追问：

- "Why not quote everything? It's always safe."（安全但难读，diff 噪音大，人会手改这些文件；本课自己的 SKILL.md 也是能不加就不加）
- "A real host parses this with a full YAML library. How would you test the writer against one?"（拿 `yaml.safe_load` 对拍：同一份输入，本课的子集和真实 YAML 读出来必须一样。这里只能用标准库，所以规则写死在 docstring 里）
- "In standard YAML a \| block keeps one final line break. What does that mean here?"（默认的 clip 会保留末尾一个换行，真实宿主读到的 description 末尾多一个 `\n`，严格说应该写 `|-`；本课的子集不认 `|-`，测验第 9 题讲过。这是子集和真实 YAML 的一处差别，要能说出来）
- "What happens if user-invocable is written as "false" in quotes?"（宿主读到的是非空字符串；按真值判断的宿主会把它当成 true。讲义：frontmatter 是会改变系统行为的元数据）

### Part 3 有序问题码（目标 10 分钟）

坑：

- frontmatter 解析失败只报 `frontmatter-syntax` 一条，不能拿半个字段表接着校验。讲义 Validation order matters：先做便宜的结构检查，次生错误不能盖住第一个真正坏掉的不变量。
- name 只报一条，由 Part 1 的 `name_issue` 决定。不要在外面再单独查一次目录。
- 长度按字符算：1024 个汉字的 description、500 个汉字的 compatibility 都合法。边界是 64/65、1024/1025、500/501（本课练习 2）。
- 空白算缺失：`description: " "`、`compatibility: "  "` 和 `''`、只有空行的正文。正文现在原样保留，`if not body` 判断不出 `"\n\n"`。
- compatibility、metadata、allowed-tools 只在出现时才检查。
- allowed-tools 是用空格分隔的字符串：空的、只有空白的、用制表符或换行分隔的（`|` 块写出来的 `Read\nGrep`）都是 `allowed-tools-shape`。`.split()` 会把换行也当成分隔符，放了过去。
- 顺序固定：`body-required` 在 `unsupported-runtime-field` 前面，扩展字段按字段名排序，一个字段一条。
- `allowed_runtime_extensions` 可以是任何可迭代对象。测试传的是 `iter([...])`，在循环里直接对它做 `in`，第一次就把迭代器耗完了，要先转成 set。
- 报告里 `runtime_extensions` 列出所有非核心字段，包括宿主允许的；`core_fields` 和 `runtime_extensions` 都排序；`body` 原样。
- 最后一段把 Part 2 写出来的文件交给校验器，带一个允许的扩展，必须通过。

追问：

- "Why stop at the syntax error instead of reporting everything you can find?"（解析失败以后，剩下的字段是猜出来的，报出来的问题会误导作者；先让作者修第一个坏掉的地方）
- "This lesson has two validators, main.py and check_skill.py, and they drifted. How do you stop that?"（一个库、两个入口，同一批样例对拍。本课测验第 10 题）
- "The host allows user-invocable. What should the report still show?"（valid，但 runtime_extensions 里仍然列出它，便携包和带扩展的包要分得开，本课练习 3）
- "The package passed. Can the agent run its scripts now?"（不能。合同清单最后一句：通过只说明结构上能加载，不授予文件系统、网络、密钥、子进程或工具权限）

### Part 4 生命周期 TAP 检查（目标 14 分钟）

坑：

- 输出格式由测试决定：每个会话一行 TAP 结果，`ok N - name` 或 `not ok N - name # 原因`，最后是计划行 `1..N`，每行以 `\n` 结尾。测试把输出拼起来按 `\n` 切开，最后一段必须是空串，其余每段都要符合 TAP 行的格式。少了换行、多一个空行，格式那条断言就挂。
- 会话一结束（收到 `ended`）就输出这一行。测试记下每一行出来时已经拉取了几个事件：先读完整个流、在第一次出问题时就输出、晚一拍输出，都看得出来。计划行只能放最后，N 要等流结束才知道。
- 编号按会话结束的顺序，不按开始的顺序。
- 状态按 skill 分开，不同 skill 的事件交错到达。同一个 skill 在 `ended` 以后可以开新会话（重装后重新发现），旧会话的状态要清掉：incident-summary 第一次校验失败，第二次通过，第二个会话是 ok。用可变默认参数初始化 `seen` 集合，会让所有会话共用一份状态。
- 校验失败本身不算失败：宿主没有激活它，生命周期是对的，所以 incident-summary 的第一个会话是 `ok`。失败的是校验失败以后又发生了别的阶段，原因写 `<stage> after failed validation`，而且这条要先于顺序检查：deploy-helper 校验失败后直接被激活（用户敲了 `/deploy-helper`），原因是 `activated after failed validation`，不是 `activated before selected`。“校验失败以后”指任何阶段，不只是激活：测试最后单独发一个校验失败后又被 cataloged 的会话，原因是 `cataloged after failed validation`。讲义：Validation 在进入目录之前就拒绝坏包。只拦 activated 及以后的阶段，这一条会挂。
- 每个阶段只要求 NEEDS 里写的那个阶段已经发生，不要求 STAGES 里紧挨着的前一个：changelog-style 没加载资源就调用工具，这是允许的。
- 工具调用之后必须有 verified。只看“验证过没有”不够：changelog-style 先 verified，后来又调了一次 write_file，最后这次调用没有被验证。
- 流结束时还开着的会话也要各出一行，按开启的顺序，不按名字，也不按最后一个事件的顺序。原因是它自己的第一个问题，没有问题才写 `session not ended`。
- 没有任何会话时输出 `1..0`。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要看出来这里需要 async generator。

追问：

- "TAP allows the plan first. Why is it last here?"（N 要等流结束才知道；放前面就得先读完整个流，结论就不是实时的了）
- "The host crashes and never sends ended. What should CI do?"（流结束时把开着的会话报成 not ok；再加超时，超过时间没有 ended 就判失败）
- "Which line in this report worries you most, and why?"（activated after failed validation：一个没通过校验的包进了模型上下文。讲义：Validation 在进入目录之前拒绝坏包；而且激活不等于授权，工具调用还要过宿主的权限）
- "Where does verified come from?"（独立于模型说法的检查。讲义：Verification checks the produced artifact independently of the model's claim）

### Part 5 工作流依赖边（目标 12 分钟）

坑：

- 只看正文，不看 frontmatter：deploy-gate 的 description 里有 invoke the `deploy-gate` skill，扫整个文件会多出一条指向自己的边，参考实现的轮次计算会无限递归。
- 名字要在反引号里：`"invoke the release-notes skill"` 不算。
- 短语可以跨行：release-risk-review 里 invoke the 和 `` `changelog-style` `` 分在两行，If that skill is 和 unavailable 也分在两行。一行一行匹配会漏。
- 句首的 Invoke、句中的 if 都要认：incident-triage 的护栏是小写的 if。
- 代码块里的都不算：skill-contract-reviewer 在列表项里放了一个缩进三格的 ```` ```markdown ```` 示例，里面既有引用也有护栏。只认行首的 ```` ``` ````、只认单独一行的 ```` ``` ````、不处理代码块，都会多出一条边。
- 一个依赖只算一条边：deploy-gate 引用了两次 release-readiness。
- 护栏只覆盖它前面最近的那个引用：release-risk-review 先引用 security-scan、再引用 changelog-style，后面只有一个护栏，它覆盖的是 changelog-style，所以 security-scan 那条边没有护栏。写成“一个护栏覆盖前面所有的引用”或者“护栏覆盖后面的引用”都会挂。
- 一条边只要有一次引用没有护栏，就是 unguarded：deploy-gate 第一次引用有护栏，第二次没有。
- 安装顺序按轮次：第一轮是在集合里没有依赖的技能，之后每一轮是依赖全在前面轮次里的技能，同一轮按名字排。每次取最小的可用名字（用堆的 Kahn）、深度优先后序、按依赖个数分轮、按最近的依赖分轮，结果都不一样。
- 缺失的依赖不挡安装。技能之间不是 import，第二个技能要经过运行时的发现、资格检查和激活，缺了就按护栏停下并报告。所以 incident-triage 和 release-risk-review 照常安装，缺失的边单独列出来。把它们挡在安装顺序外面，或者推到最后一轮，都会挂。
- 本题保证没有环，环检测是 25 课的内容。
- 测试不拦两种偷懒写法：反引号里随便什么文字都当成名字（docstring 只说名字在反引号里，这里的数据都是合法名字），以及用 `text.split("---", 2)` 取正文。后者在 description 里出现 `---` 时会切错，追问时问候选人为什么要用 Part 1 的解析器。

追问：

- "Two missing dependencies, one with a stop clause and one without. Which one fails CI?"（没有护栏的那条：运行到那一步，行为没有定义。有护栏的可以只给警告）
- "Why not let one skill import another?"（讲义：第二个技能仍然要经过发现、资格、激活、权限和上下文处理；写成可观察的边，宿主才有机会执行策略，也才能测试）
- "How would you find cycles here?"（DFS 三色标记，或者 Kahn 结束时还剩下节点；留给 25 课）
- "The body names an MCP tool that the host doesn't have. Same treatment?"（同样要写回退或明确失败，不能悄悄换成权限更大的工具。本课练习 5）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读报错、打印实际数据（尤其是 `repr`）、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 YAML 子集和真实 YAML 的差别、校验器漂移、生命周期的边界、缺失依赖的处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
