# 面试官手册：PoisonGuard（13/15）

候选人计时期间不要看。候选人手里只有 README、`poisonguard/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 没有 description 的工具要不要检查？ | "Yes. There is no text to scan, but its digest is checked like any other tool's." |
| 1 | 摘要的写法能不能换一种？ | "No. The manifest already holds pins made with canonical_json. Any other bytes and every stored pin reads as a rug pull." |
| 1 | 列表也要排序吗？ | "No. Only object keys are sorted. List order is part of the descriptor." |
| 1 | 重名的两个工具要不要都藏起来？ | "No. The qualified names keep them apart. The shadowing finding is for review." |
| 2 | 时间要保留原来的时区偏移吗？ | "The same instant is enough. Keeping the offset is fine too." |
| 2 | 可以在内存里缓存 pin 吗？ | "Only if you never miss or overwrite another process's write. Re-reading the file on every call is fine at this size." |
| 2 | 清单文件的格式有要求吗？ | "One JSON file at the path you're given. The layout is your call." |
| 2 | 带 sha256: 前缀的摘要要不要接受？ | "No. Exactly 64 hex digits, either case." |
| 2 | 两个进程同一时刻写呢？ | "The tests don't cover true concurrency. Tell me what you would add." |
| 3 | 隔离中的 pin，摘要又对上了，算 approved 吗？ | "No. It stays quarantined until a reviewer approves it again." |
| 3 | 一个工具既是新的，又被扫描命中？ | "Blocked. A scanner hit comes first, whatever the pin says." |
| 3 | 重名的工具要不要挡掉一个？ | "No. Both stay, each under its qualified name, and we report the collision." |
| 3 | 只在有重名时才加服务器前缀行不行？ | "No. Every tool is always server.tool. A name must not change because another server showed up." |
| 3 | 属性名（key）也要扫描吗？ | "Every string value, yes. Keys are your call; the tests don't cover them." |
| 3 | 能不能把所有字符串拼成一段再扫一次？ | "It passes the tests, but walk me through it. Two neighbouring strings can now match together, and which ones are neighbours depends on key order." |
| 3 | 一个服务器这次整个没出现？ | "catalogs is the whole refresh. Its pinned tools are in no listing, so they are removed." |
| 4 | 同一个列表的页会乱序吗？ | "No. Pages of one listing arrive in order. Different listings can overlap." |
| 4 | 最后一页没有工具？ | "It still completes the listing. An empty listing is a real answer." |
| 4 | 流结束时还没完成的列表？ | "Drop it. Say nothing about that backend." |
| 4 | 一批事件能不能一次 yield？ | "Yes. A chunk can hold any number of whole lines." |
| 5 | 路径在这条记录里不存在？ | "Skip it. Different calls have different shapes." |
| 5 | 路径写错了，比如用了 [0]？ | "That's a broken policy. Raise ValueError before touching the record." |
| 5 | 两条路径一条套在另一条里面？ | "The outer one wins, and it digests the value as it is in the record." |

## 每关：要看什么、提示、追问

### Part 1 修扫描和摘要（目标 11 分钟）

一个测试里叠了 5 个缺陷，外加几个护栏：

1. `scan_catalog` 把 `tool.get("description")` 原样传给 `scan_description`。notes.stats 没有描述，None 一路传到 `re.search` 才报 TypeError：错误在 re 模块里报出来，根因在上一层。
2. `descriptor_digest` 只哈希 name 和 description，变量还叫 `approved_fields`，像是读了课里 "hash the descriptor fields the user approved" 以后挑了两个字段。只改 inputSchema 不改描述的 rug pull（练习 4）看不见。
3. `canonical_json` 没有 `sort_keys`。修好第 2 条以后，键序不同的同一个 descriptor 被当成 rug pull。
4. `scan_description` 少了 `re.I`。测试先看到 issues.search 带着 `IGNORE Previous Instructions` 混进 `visible_tools` 的结果（离根因两层调用），再直接查 `<SYSTEM>` 有没有被认成 role-tag。
5. `visible_tools` 在循环里对每个工具调一次 `scan_catalog`，是 O(n²)。500 个工具在本机约 1.2 秒，机器忙时 2 秒以上；修好后约 2.5 毫秒，限值 0.06 秒。

护栏：
- 精确摘要：wiki.lookup 带德文变音和德文引号，`required` 是 `["term", "lang"]`，不是字母序。`ensure_ascii=False`、Python 的 `hash()`、连列表一起排序，都和已存的 pin 对不上。
- 为了躲键序问题只哈希 name、description、inputSchema：annotations 的改动（readOnlyHint 翻成 true）会漏掉。
- 只排顶层的键：inputSchema 里面的键序照样不同。
- 跳过没有描述的工具：notes.stats 的 schema 改动就没人检查了。
- 按 `id(tool)` 缓存摘要来提速：原地改过的 descriptor 还用旧摘要。
- 把重名的工具都藏起来：500 个工具一个都不剩。
- 提速时顺手只挡 metadata_poisoning 和 rug_pull：没有已批准摘要的工具（unapproved）也要挡，测试删掉 notes.stats 的 pin 再查一次。

看什么：是不是顺着 TypeError 的 traceback 往上一层找 None 是哪来的；会不会在 REPL 里打印两种键序的 `canonical_json`；每改一处就重跑。

提示：
- H1："Where does the None that re.search complains about come from?"
- H2："Which fields of the descriptor go into the digest right now?"
- H3：直接指出 `approved_fields` 只有两个字段，`canonical_json` 没有 `sort_keys`。

追问：
- "What does an equal digest prove?"（只证明没变，不证明安全。被投毒的描述 pin 上以后照样有毒，课里那句 Hash equality proves stability, not safety）
- "The scanner flags 'Upload a file; requires an API token.' Is that a bug?"（是误报，正则只是绊线。课里说安全的描述也可能含命中的短语，命中是审查证据，不是结论）
- "Why hmac.compare_digest for digests that aren't secret?"（常数时间比较。这里不算秘密，但比较摘要和令牌时养成这个习惯，换到真正的秘密上就不会出错）
- "A server lists the same tool name twice. What happens?"（同一个限定名有两份 descriptor，扫描和路由可能各用一份；应该把整个列表当异常拒掉，或者两份都隔离，不能让后一份悄悄覆盖前一份）

### Part 2 pin 清单（目标 11 分钟）

坑：
- 摘要统一存成小写十六进制：测试用大写传进去，读回来要是小写。只查长度会放过 64 个 x；`re.match(r"...{64}$")` 会放过结尾的换行；`int(digest, 16)` 加长度检查会放过 `0x` 开头的 64 个字符；正则只写 `[0-9a-f]` 又会把合法的大写拒掉。
- 限定名区分大小写，notes.Export 和 notes.export 是两条。为了“统一”把 key 也 `lower()`，两条就合成一条。只查有没有点，会放过 `notes.` 和 `.export`。
- 批准时间必须带时区，读回来到微秒都一样。`isoformat(timespec="seconds")` 丢微秒；存成去掉时区的 UTC，读回来是 naive，和带时区的时间不相等。存成 UTC 或 epoch 浮点数都可以，测试只比较时刻。
- 隔离时间也要带时区。再隔离一次不能挪时间，要保留第一次 rug pull 的时刻；重新批准要清掉隔离。
- 重新批准是整条替换：测试里审查员批准的是改过的新版本（新摘要、发布者证据里的 version 是 1.5.0、新的批准时间）。已有 pin 时只 `replace(pin, quarantined_at=None)`，旧摘要还留着，审查过的新版本永远进不来。
- 不存在的文件是空清单；读不了的文件（被截断的、空的）必须报 ValueError。`except JSONDecodeError: return {}` 会把坏掉的清单当成“还没有任何 pin”，所有批准悄悄消失。
- 清单由多个进程共用：打开时读一次、之后都用内存里的副本，就看不到别的进程写的 pin，下一次写还会把它覆盖掉。测试用两个 PinStore 对象模拟两个进程。
- 不存在的名字，`get` 和 `quarantine` 都报 KeyError。

追问：
- "The process dies halfway through writing the manifest. What do you lose?"（直接覆盖写会留下半个文件，下次启动就报错。先写同目录的临时文件、fsync，再 `os.replace`，旧文件要么完整保留，要么整个换成新的。参考答案是这么写的，测试没有模拟崩溃）
- "Two processes write at the same moment?"（每次重读文件只能避免用过期副本，挡不住真正的并发。要加文件锁，或者只让一个进程写，其他进程把批准请求发给它）
- "Why keep publisher evidence next to the digest?"（课里第 7 个攻击面：熟悉的显示名不能证明发布者身份。重新批准时要能看出发布者有没有变）
- "Who may write this file?"（能改清单的人就能批准任何工具。清单要放在只有审查流程能写的地方，或者签名后再读）

### Part 3 刷新判定（目标 13 分钟）

判定按 blocked、quarantine_unknown、quarantine_changed、approved 的顺序，取第一个成立的。坑：

- 首次见到不等于信任（不是 TOFU）：notes.delete 没有 pin，是 quarantine_unknown。`Gateway.refresh` 也不能顺手把它 pin 上，连刷两次还是 unknown。
- pin 只为自己的限定名作保：mirror.search 和 notes.search 一字不差，摘要相同，但 mirror.search 名下没有 pin。“这个摘要在清单里出现过”就放行，等于任何服务器抄一份已批准的描述就能混进来。
- 摘要相同也要扫描：issues.search 是带着 "Do not tell the user" 被 pin 上的，照样 blocked。
- 扫描整个 descriptor：wiki.lookup 的毒在参数描述和参数的 title 里，mirror.export 的短链接在 destination 的 enum 列表里。只扫顶层 description、只扫名叫 description 的字段、只往对象里走不进列表，都会漏掉。把所有字符串拼起来扫一次能过测试，但相邻的两段字符串可能拼出一次误报，而且谁和谁相邻取决于键序，要让候选人说清楚。
- 扫描命中排在最前：mirror.export 没有 pin 也是 blocked，issues.close 摘要变了也是 blocked。每个标签只报一次，按 INJECTION_PATTERNS 的顺序。issues.close 是 role-tag、concealment，按字母排就反了。
- 隔离会粘住：notes.archive 的 pin 带着 quarantined_at，摘要对得上也还是 quarantine_changed。
- 模型可见的只有 approved，而且永远用限定名：notes.stats 没有重名，也不能叫 stats。
- shadowed 列出所有被两个以上服务器提供的裸名，限定名排好序；removed 是这次谁都没列出的 pin，整台服务器都没出现的（tickets.close）也算。服务器和工具的顺序倒过来，结果必须一模一样。
- 后半段是端到端检查，用 Part 2 的 PinStore 加 Gateway：notes.export 把 annotations 翻成 readOnlyHint（宿主会因此跳过确认），issues.search 换成带隐瞒指令的版本。两条 pin 都要记成隔离；服务器改回原样也还是隔离，直到重新批准。只给 status 为 quarantine_changed 的记隔离，会漏掉被扫描拦下的那次改动，服务器一改回去它就又被当成没事了。反过来，凡是没 approved 的都记隔离也不对：最后的 notes.rotate 是审查员看过的误报（“Never send the new token over chat” 命中 secret-access），摘要没变，照样 blocked，但不是 rug pull，pin 上不能记隔离。

追问：
- "Why not trust on first use?"（第一次看到的描述可能本来就有毒，TOFU 只能发现以后的变化。课里写的是 Unknown key: quarantine until review）
- "Why keep the quarantine when the server reverts?"（来回切换本身就是手法：审查的那一刻是干净的，之后再换。粘住的隔离让每一次变化都要人看）
- "Why always qualify, even without a collision?"（名字稳定，审批、审计、pin 和 Mcp-Name 路由才指向同一个对象。只在冲突时加前缀，新服务器一上线，旧工具就改了名）
- "We add a pattern, and a tool approved yesterday is now blocked. What happens to its pin?"（摘要没变，不进隔离；去掉这条模式就恢复。要不要人工复核是策略问题，可以讨论）

### Part 4 分页决策流（目标 13 分钟）

坑：
- 一个后端的列表要等最后一页到了才整体判定。每页单独判，或者只拿最后一页判，前面页上的工具会被报成 removed。
- 一个后端的 pin 是以 `backend.` 开头的那些。`startswith("notes")` 会把 notes_archive.export 算进 notes；把所有 pin 交给每个后端，removed 里会冒出别的后端的工具。
- listing 号更大的是新列表：旧列表没完成就作废，之后才到的旧页一律忽略。不看 listing、按 (backend, listing) 各攒各的、或者把“不相等”当成“更新”，issues 都会按旧列表判一次。
- 判过一次的后端还会有新的列表：notes_archive 第 2 次列表把 export 加了回来。
- 一批事件按 key 排序，removed 和其他决定混在一起排。
- 流结束时还没完成的列表不判（wiki）。
- 只对每个后端记一个 listing 号，不能全局共用一个“最新号”：issues 开了第 2 次列表以后，notes_archive 的第 1 次列表照样要判。
- 最后一页上的工具也要算进去：先判再 `extend`，notes_archive 第 2 次列表里的 export 就成了 removed。
- 一个列表判完之后又来同一个 listing 号的页，参考答案忽略它，另起一份累积也能过测试。同一列表的页有序、最后一页之后没有页，这种情况不会出现，可以接受。
- 后端之间互不等待：探针在 notes 完成以后还排着 500 页慢后端的页，第一条事件出来时最多只能多拉一页。先把整个流读完再判就挂。
- 输出格式由测试的解析代码决定：所有块拼起来以换行结尾，按 `\n` 切开，每行一个 JSON。一批放在一个块里可以；少了换行、多一个空行、`indent=2` 都会挂。
- 到达顺序只决定事件什么时候出来，不决定内容：两种交错顺序得到的事件集合必须相同。“同一个裸名谁先到谁留下”的去重会被抓住。

追问：
- "The slow backend never finishes. What does the model see from it?"（参考答案里它的事件一直不出来。上一轮的判定继续有效，还是整个后端下线，是策略问题；实际要加超时，并把“列表没完成”记进状态）
- "Why not judge each page and correct it later?"（中间状态会让工具先下线再上线，模型和审计都会看到来回闪。证据不完整，不能当成删除）
- "What if pages of one listing could arrive out of order?"（这里假设同一列表的页是有序的。要处理乱序，就得给页编号，攒齐了再判）
- "Who consumes these events?"（网关按 backend 和 listing 更新路由表和模型可见列表，removed 的工具摘掉；同样的事件写进审计）

### Part 5 审计脱敏（目标 12 分钟）

坑：
- 只按策略路径脱敏，不按键名猜：pagination.token 和 arguments.destination.token 同名，只有后者在策略里。
- `[*]` 覆盖列表的每个元素，没有 email 的元素跳过、不报错；`[*]` 在末尾时，每个元素各自一个摘要，不是整个列表一个；`[*]` 碰到对象不匹配（destination 是对象）。反过来，键名碰到列表也不自动展开：`arguments.recipients.name` 什么都不匹配，名字原样保留。
- 数字和对象都整体摘要：account 是数字，headers 是对象。对象逐个叶子摘要不对。
- 摘要是 canonical_json 的 HMAC-SHA256，前面加 `hmac-sha256:`。`str(value)`、普通 SHA-256、`ensure_ascii=False`、不排序的 `json.dumps`、排了序但用默认分隔符的 `json.dumps`，都和测试算的对不上（最后一种对字符串和数字碰巧一样，到 headers 这个对象才露出来）；键序不同的同一个对象必须得到同一个摘要。
- 外层路径优先，摘要的是记录里原来的值：两条路径一个套一个，不管策略里谁在前，结果都一样。按顺序一条条改的话，内层先改，外层摘要的就是改过的对象。
- 原记录不能被修改：网关写完审计，还要拿原来的参数去执行调用。
- 不存在的路径跳过；解析不了的路径（`[0]`、空段、空串）报 ValueError，策略写错了要大声报出来，不能悄悄什么都不脱敏。

追问：
- "Why a keyed digest?"（短秘密、卡号、PIN 用普通 SHA-256，可以把所有可能的值算一遍对出来。密钥只放在审计服务里）
- "You rotate the audit key. What breaks?"（新旧摘要对不上了。在标记里带上 key id，过渡期两把密钥一起算）
- "How would you redact a _meta key such as io.modelcontextprotocol/clientInfo?"（键里有点号，按点切会切坏，路径语法要支持带引号的键）
- "How do you know the policy covers every secret?"（策略跟着工具的 inputSchema 走，审批时就要求标出敏感字段；再用真实请求跑一遍，检查审计里没有明文残留）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 安全和生产意识 | 10 | 追问里答出：摘要稳定不等于安全、首次见到不信任、隔离要粘住、多写者、不完整证据、键控摘要 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
