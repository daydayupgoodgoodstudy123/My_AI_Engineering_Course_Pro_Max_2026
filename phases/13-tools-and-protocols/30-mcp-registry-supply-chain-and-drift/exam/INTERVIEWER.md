# 面试官手册：regadmit（13/30）

候选人计时期间不要看。候选人手里只有 README、`regadmit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | Registry 没给状态时，registry_status 返回什么？ | "An empty string. A version with no status is never eligible." |
| 1 | verified_namespace 要不要转小写再比？ | "No. The verifier hands you the exact string. Compare it exactly." |
| 1 | 工具列表里两个工具同名怎么办？ | "Keep both. The server sent both, so both count, and their order must not change the digest." |
| 1 | append 要不要每次先验证整条链？ | "No. head() verifies before anything is anchored. append only links to the newest entry." |
| 2 | 锚点存在哪里？ | "Not in the ledger file and not next to it. The tests keep it and hand it back to you." |
| 2 | 文件最后一行只写了一半？ | "Treat it as a broken ledger. The tests don't cover it." |
| 2 | 会不会有两个进程同时写？ | "No. One writer per ledger. Tell me what you'd add for two." |
| 2 | 锚定以后账本又长了，旧锚点还算数吗？ | "Yes. The anchored entry is still there, with the same hash." |
| 3 | 同一个版本再 admit 一次？ | "decide doesn't know about earlier decisions. The tests don't cover it." |
| 3 | 一条记录同时有 package 和 remote？ | "That's fine. The evidence says which one will run. Join that one." |
| 3 | 好几个控制都没过，报哪个？ | "All of them, each once, in CONTROLS order." |
| 3 | 记录里 package 的 version 写着 latest？ | "The tests don't cover it. Tell me what you'd do." |
| 3 | serverInfo 和记录对不上，要不要拒？ | "No. It's the server's own report. Keep it as evidence. It decides nothing." |
| 4 | 观测到的版本没有 pin？ | "Record it as unknown. Nothing else changes." |
| 4 | deprecated 之后又变回 active？ | "The quarantine stays." |
| 4 | 一次观测里两层都变了？ | "Report both, in the documented order." |
| 4 | 健康检查要不要在这里做？ | "No. Rollback asks for one when it needs it." |
| 4 | 观测里带的探针请求头要不要记下来？ | "No. Only what the docstring lists as evidence." |
| 5 | 回滚到当前已经 active 的版本？ | "Not tested. A no-op that still gets recorded is fine." |
| 5 | 能回滚到更新的版本吗？ | "Yes. Any admitted version that is still eligible. It restores a route; it doesn't have to go back in time." |
| 5 | 没有 active 版本时，from 写什么？ | "None." |
| 5 | 被拒的回滚要不要记？ | "Yes. Every decision goes into the ledger." |

## 每关：要看什么、提示、追问

### Part 1 修证据和账本（目标 10 分钟）

一个测试里叠了 5 个缺陷，外加几个护栏：

1. `registry_status` 写成了 `api_meta.get("status", "active")`：既读错了位置（平铺的 `_meta.status`，不是官方块），又默认 active。三个版本全显示 active，测试在上一层的 `listed_version` 里看到。
2. `listed_version` 把自己的局部变量 `namespace`（记录名字里 `/` 前面那段）传给了 `namespace_matches`，而不是 `verified_namespace`。每条记录都给自己作保，`org.attacker/inventory` 也在 `com.example` 里面。
3. `normalized_tools` 为了排序先按名字建了一个字典，同名的描述符只剩最后一个。服务器在已经钉住的 `inventory_get` 前面再塞一个同名、带 `destructiveHint` 的描述符，字典里留下的还是原来那个，摘要不变。经过 `toolset_digest` 报出来。课里说只规范列表顺序，新工具就要改变 pin。
4. `AdmissionLedger.head` 返回最新条目的 `previousHash`，不是它的 `entryHash`。`append` 通过 `head()` 拿链头，所以第 2 条链到了 GENESIS；错误晚一次追加才出现：第 3 次 `append` 里 `head()` 报 `LedgerError: ledger does not verify`，而 `verify()` 本身没有错。
5. `append` 从 `head()` 拿序号和链接，`head()` 每次都从创世条目验证整条链，每次追加 O(n)，填满账本是平方级。1000 次追加在本机 1.3 到 1.6 秒，修好后约 7 毫秒，限值 0.1 秒。

护栏：
- 1000 条的账本改掉第 401 条以后，`verify()` 必须是 False，`head()` 必须报 LedgerError。为了提速只验最后一个链接、让 `head()` 不验证，或者让 `head()` 记住上次验到的长度、长度没变就跳过，都会挂。
- 命名空间：修第 2 处时直接写 `namespace = verified_namespace` 也能让 `in_namespace` 变对，但 `Listing.namespace` 应该是记录自己声称的命名空间，被拒的准入要把它记成 claimedNamespace。测试断言 `org.attacker/inventory` 的 namespace 仍是 `org.attacker`。
- 状态：Registry 没给状态是空串（默认 active 会挂）；平铺的 `_meta.status` 不算（拿它兜底会挂）；发布者在记录自己的 `_meta` 里写官方状态也不算（把两个 `_meta` 合并会挂）。
- 工具集：新加的注解和 `title` 字段都是变化（把描述符砍成几个固定字段会挂，只多保留 annotations 也不够）；两个同名描述符换顺序摘要不变（只按名字排序会挂）；没有名字的工具也要有摘要（`tool["name"]` 会 KeyError）；最后是一个写死的摘要，必须和已经存下的 toolsetDigest 一致（只按规范 JSON 排序、把描述符里的列表也排序，都会挂）。

看什么：是不是先读断言给出的实际值再找函数；遇到 LedgerError 会不会把每条的 `previousHash` 和上一条的 `entryHash` 打出来对；改第 5 处时会不会为了快而动 `verify()`。

提示：
- H1："Which function first produced something the test didn't expect?"
- H2："Print each entry's previousHash next to the entryHash of the entry before it. Where does the link come from?"
- H3：直接指出 `head()` 返回的是 `previousHash`，而 `append` 每次都通过 `head()` 拿链头。

追问：
- "Why is the status beside the record and not inside server.json?"（发布记录不可变，状态会变，归 Registry 管；放进记录里，就等于让发布者自己给自己定状态）
- "What does namespace_for_domain prove?"（只证明控制 example.com 可以对应 com.example；com.example.docs 要单独验证。GitHub 认证走另一条路，最后都归一成一个精确的命名空间字符串交给准入）
- "head() is O(n). Is that a problem?"（锚定是周期性的，不是每次追加都做；账本很长时，从上一个锚定过的链头往后验证就行）
- "Is a new readOnlyHint annotation really drift?"（是。注解影响宿主要不要让用户确认、模型怎么选工具，课里说 cosmetic metadata can alter agent behavior）

### Part 2 账本文件和锚点（目标 11 分钟）

坑：
- 格式由测试决定：每行一个条目、以换行结尾，读回来和内存里逐字段一致；每一行的 entryHash 都要等于其余九个字段的 `digest()`。
- 重开时整条链要验证：改了某一行的 time 但没动哈希，必须报 LedgerError。验不过就当成空账本打开，等于把证据扔了。
- 只靠链本身发现不了截尾：删掉最后两行，剩下的链照样自洽，测试先断言了这一点；带上锚点打开才报错。
- 能写文件的人可以改掉一条，再把后面的哈希全部重算，链照样自洽；锚点里 (5, hash) 那一条对不上。只比长度会放过这种重写。
- 锚点不要求等于当前链头：锚定以后账本还会长，旧锚点要继续成立。按下标取锚定条目前先判断范围，否则截尾时报的是 IndexError，不是 LedgerError。
- 文件不存在是空账本，但带着锚点打开必须报错：整个文件被删掉也是截尾。
- 重开以后接着编号：新条目的 sequence 是 6，previousHash 是锚定的那个哈希。每打开一次就从 1 重新编号，链就断了。
- 锚点不能代替整链验证：改了中间一行的 time 但没动哈希，锚定的第 5 条照样对得上，带着锚点打开也必须报错。

可以接受的写法：
- 锚点核对写成“链里有没有一条的 entryHash 等于锚定的哈希”，不按序号找。序号本身在哈希覆盖的字段里，哈希对上了序号也就对上了，结果和按下标找一样。
- 写文件时 `ensure_ascii=False`，只要用 UTF-8 写、UTF-8 读，读回来照样逐字段一致。

追问：
- "Where do the anchors live in production?"（签名的发布元数据、一次写入的存储、透明日志；记 sequence 和 hash 两样；定期锚定，重大操作前后各锚一次）
- "What does the anchor not protect?"（最后一个锚点之后追加的条目只有链本身护着，锚得越勤，窗口越小；它也不证明追加的人有权限，追加本身要鉴权、要限制谁能写）
- "Two processes append to the same file?"（两个进程读到同一个链头，各写一条，链就分叉了。要么一个账本只有一个写者，要么交给一个追加服务排队写）
- "The process dies halfway through a line."（最后一行是半截 JSON，参考答案报 LedgerError，要人来处理；也可以定义成截掉半行，但截掉之前要先和锚点核对。测试没覆盖）

### Part 3 七项准入控制（目标 14 分钟）

坑：
- version：requested 必须精确，而且和记录的 version 逐字符相同。`^1.0` 不能按语义版本去匹配 1.0.0；记录自己写着 latest、^1.4、>=1.4.0 也不行，只查 `^` 不够；2026-11-01 这种不是语义版本的写法照样是精确版本，课里说 semver 是推荐，不是要求。
- Registry 版本和包版本是两回事：测试里有一条 1.0.1 的新记录，引用的还是 1.0.0 的包。requested 和记录的 version 比，证据的 version 和 package 的 version 比，混用任何一边都会挂。
- status 和 namespace 直接用 Part 1 的 `listed_version`，不要再自己解析一遍。
- source：package 要 registryType、identifier、version 三个一起连接，再比 transport。本课代码先按 identifier 找第一个，记录里 npm 包排在前面时就连到了错的包。remote 两边都先规范化 URL 再比，再比 transport。只有 remote 的记录完全合法：先读 `record["packages"]` 会 KeyError，要求必须有 package 会把它拒掉。所有权（`verified is True`）package 和 remote 都要查。
- digest：64 位十六进制，并且 digestFrom 是 fetch 或 package-service。制品自己报的不算，没写来源的也不算：这是白名单，不是黑名单。
- live：2026-07-28 可以在 supportedVersions 的任何位置；没有 supportedVersions 是 protocol 失败，没有 capabilities 是 capabilities 失败，都不能 KeyError；空对象 `{}` 也算声明了能力，按真假判断会挂；描述只有空白不算描述。
- 类型要查：supportedVersions 写成字符串 `"2026-07-28"` 时 `in` 会做子串匹配，必须先确认是列表；capabilities 写成名字列表 `["tools", "resources"]` 不算，必须是对象；`verified` 要 `is True`，字符串 `"false"` 按真假判断是真的；工具的 name 只有空白也不算。
- remote 两边都规范化以后再比，证据里写成 `https://mcp.example.com:443/mcp` 也要连上。两边都不是 HTTPS 时 `normalize_https_remote_url` 都返回 None，不能让 None 等于 None 连上：测试里有一条 http 的 remote。
- serverInfo 只进 reportedServerInfo。命名空间按记录的 name 和 verified_namespace 判，pin 的 server 和 version 也来自记录；`_meta` 外面的 serverInfo 别名不提升。
- reasons 里每个控制只出现一次，按 CONTROLS 的顺序，按名字排序会挂。source 没过时 digest 照样要查，用 `elif` 把 digest 接在 source 后面，就少报一项。
- pin 逐字段精确：toolsetDigest 要用 `toolset_digest`（测试里的 TOOLS 不是按名字排好的）；source 是记录里声明的那一项加上 kind，不能混进校验器的字段；provenance 少了 registrySource，provenanceDigest 就对不上。
- 最后一段经过给定的 AdmissionController：批准的记 pin，拒绝的记原因，`^1.1` 被拒也照样进账本。

提示：
- H1："Take the docstring's controls one at a time. Which one does this case fail?"
- H2："Which fields must the evidence agree on with the record before the digest even matters?"
- H3：直接指出 package 按三个字段一起连接，remote 先规范化 URL，digestFrom 用白名单。

追问：
- "Why compare with the record's version at all, if the Registry rejects ranges?"（取到的记录必须就是批准的那一个；latest 会移动；镜像或者别的 Registry 不一定守这条规矩）
- "digestFrom says package-service. What did the verifier have to check?"（包服务对这个摘要的签名或证明，以及签名的是谁。没有验证过的服务结果只是另一个声明）
- "Why keep serverInfo at all?"（排障。serverInfo 和记录对不上本身就是一个告警信号，但它不决定任何事）
- "The record's package version is latest, but the digest is pinned. Admit it?"（摘要钉住了这次的字节，Part 4 的 artifact 检查会发现变化；但这个坐标随时会变，变了以后分不清是正常发布还是被篡改。更稳的是把浮动的包版本也拒掉。测试没覆盖）
- "Where would two-person approval for destructive tools go?"（课里的 Practice Lab：在 tools 之后再加一个控制，引用签名的审批证据，绑定 record、package、toolset 三个摘要，pin 里不存可变的人名）

### Part 4 分层对账流（目标 13 分钟）

坑：
- 每一层只和 pin 里对应的那个摘要比：记录摘要变了是 registry-integrity，状态不是 active 是 registry-status，sourceDigest 变了是 source-integrity，`live_failures` 有结果或者工具集摘要变了是 runtime-drift。一次观测可以同时有两层，按文档顺序都报。
- 工具列表只换了顺序不是漂移：要用 `toolset_digest`，直接 digest 原始列表会误报。
- deprecated 和 deleted 一样隔离、停止新流量，只隔离 deleted 不对。
- 只有当前 active 的版本才从路由表里摘掉：隔离 1.0.0 时 1.1.0 还在跑，路由不能动。
- 隔离是粘住的：之后干净的观测照样是 quarantined。
- deleted 的版本 pin 要留着，它是证据。
- 没有 pin 的版本记成 unknown，不改任何状态，也不能 KeyError。
- 工具列表里有 None 是漂移，toolsetDigest 记 None，不能在 `toolset_digest` 里崩掉。
- 证据只记观测到的摘要和状态：观测里带着探针请求的 Authorization 头和 tools/call 的参数，整个塞进账本就泄漏了。课里：Redact at collection time and store only the minimum proof。
- live 检查用传进来的 `required_capabilities`，不用默认值：测试另起一个要求 tools 和 resources 的对账，只有 tools 的服务器要判成 runtime-drift。
- 先记账，再输出：verdict 的 seq 是账本条目的序号，探针在第一条 verdict 出来时检查账本里已经有这一条。
- 判完一条就输出一条，不能先把整个流读完：探针在第一条 verdict 出来时最多被拉走一条观测。
- 输出格式由测试的解析代码决定：所有块拼起来以换行结尾，按 `\n` 切开，每行一个 JSON。

提示：
- H1："Which digest in the pin is this observation about?"
- H2："What does the route table look like before and after this verdict?"
- H3：直接指出要同时用 `toolset_digest` 和 `live_failures`，摘路由之前先看 active 的是不是这个版本。

追问：
- "A deleted version disappears from the default listing. How does your sync see it at all?"（要用 deleted 视图或者增量视图。没出现在默认列表里，不等于被删，更不等于安全；本地历史要留着）
- "Why quarantine a version nobody routes to?"（这样回滚以后就不会选到它）
- "The endpoint times out for five minutes. Is that drift?"（不是。可用性是健康问题，不是完整性问题，超时不该隔离；回滚时的健康检查会处理它）
- "A deprecated version becomes active again. Lift the quarantine?"（不自动解除。要人看过，发新版本重新准入，或者往账本里写一条明确的解除记录）

### Part 5 按账本回滚（目标 12 分钟）

坑：
- fold 只认三种条目：approved 的准入（记 pin，切路由）、检查事件的 quarantined（隔离；如果是 active，就摘掉路由）、activated 的回滚（切路由）。rejected 的准入和回滚什么都不改。测试的历史里有一条被拒的回滚和一条被拒的准入，只看事件名不看结果，路由就会切到 0.9.0 或 1.3.0。
- 任何检查事件都能隔离，不只是 registry-sync。
- 摘路由只摘这个服务器的：billing 的 1.2.0 被隔离，inventory 的 1.2.0 照常跑。
- 准入按 (server, version) 找：inventory 准入过 1.1.0，不等于 billing 也准入过 1.1.0。只按版本号找，billing 回滚到 1.1.0 就会被当成准入过。
- 规则有顺序：没有批准的准入是 unknown，被隔离是 quarantined，当前健康检查失败是 unhealthy。健康检查只在前两条都通过时才问，测试会记录问了谁。
- 每次回滚决定都追加进账本，被拒的也要；之前的条目一个字节都不能改。
- from 是账本折叠出来的当前路由：回滚以后再回滚，from 是上一次回滚切到的那个版本；billing 当时没有 active 版本，from 是 None。
- 回滚可以选更新的版本，只要它准入过、现在仍然合格。

提示：
- H1："If all you had was the ledger, which entries would tell you what is active right now?"
- H2："Print the fold after each rollback. Does the next rollback start from it?"
- H3：直接指出 fold 要同时看事件和结果，rollback 先 fold 再按顺序判。

追问：
- "Why rebuild from the ledger instead of keeping a dict?"（课里的 Operational Rule：make rollback choose evidence rather than memory。内存里的表会丢、会被改，账本能校验、能锚定）
- "The fold gets slow on a long ledger."（在锚定过的链头处存状态快照，从最近的快照往后折叠；快照本身也要能用账本复核）
- "A quarantined version passes admission again. What should happen?"（测试没覆盖。按这里的规则，fold 会把它切成 active，而 `state_of` 仍然说它是 quarantined，两者矛盾。合理的做法是准入时就拒掉被隔离的版本，或者要求一条显式解除隔离的账本记录。课里说记录变了就该是新版本）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和断言里的实际值、打印数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 安全和生产意识 | 10 | 追问里答出：状态和命名空间归谁管、哈希链只防改不防截尾、锚点要放在另一个信任域、范围和 latest 不是 pin、摘要必须由可信的一方算、隔离要粘住、回滚只追加 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
