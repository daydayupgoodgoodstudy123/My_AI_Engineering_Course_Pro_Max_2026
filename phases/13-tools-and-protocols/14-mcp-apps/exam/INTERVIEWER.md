# 面试官手册：AppBridge（13/14）

候选人计时期间不要看。候选人手里只有 README、`appbridge/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | URI 不认识、客户端也没声明扩展，先报哪个？ | "Your call. The tests don't cover it. Tell me which order you picked and why." |
| 1 | tools/list 的内容随能力变化，还能标 public 吗？ | "Yes. It varies by declared capability, not by user. A shared cache has to key on the declared extensions, but that cache isn't in this server." |
| 1 | 扩展声明是一个带设置的对象，算声明吗？ | "Yes. Any object under extensions is a declaration." |
| 1 | 可以在 replace 的时候就审查吗？ | "Yes, as long as replace and withdraw never raise and the next review reflects the change." |
| 2 | 索引用什么格式？ | "Your call, as long as a fresh AppCache on the same folder sees everything." |
| 2 | 摘要对不上的 blob 要删掉吗？ | "Treat it as a miss. Storing the resource again has to repair it." |
| 2 | public 的条目存的时候带了 principal？ | "Ignore the principal. A public entry is for anyone." |
| 2 | 要处理 ttlMs 吗？ | "No. Expiry is a change event in Part 5." |
| 2 | URI 要规范化吗？ | "No. Use the URI exactly as the server lists it." |
| 3 | 默认端口、主机名大小写要归一化吗？ | "No. Exact string match only. The tests don't send default ports or mixed case." |
| 3 | `wss://` 的连接能用 `https://` 的条目吗？ | "No. Compare origins exactly as written." |
| 3 | View 能撤回自己挂起的调用吗？ | "Not in this host. The tests don't cover it." |
| 3 | 对已经被拒绝的调用 approve，要报错吗？ | "Your call. It must never make the call runnable." |
| 4 | View 在 initialized 之前就发 tools/call？ | "Proxy it. Answers never wait. The tests don't cover it." |
| 4 | 要的尺寸太大，按比例缩小吗？ | "No. Cap each dimension on its own." |
| 4 | View 在 tools/call 里带了自己的 `_meta`？ | "Drop it. The host sends its own metadata, and only the name and arguments." |
| 4 | 收到第二个 `ui/notifications/initialized`？ | "Ignore it. The tests don't cover it." |
| 5 | 一批事件之间互相影响吗？ | "No. Read every event against the state you were given." |
| 5 | 到期的条目已经不在缓存里了？ | "Ignore it. The tests don't cover it." |
| 5 | 工具会绑定到别的服务器的 URI 吗？ | "No. A tool binds to a resource of its own server." |

## 每关：要看什么、提示、追问

### Part 1 修 UI 绑定与回退（目标 10 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. `_apps_enabled` 在 clientCapabilities 的顶层找 `io.modelcontextprotocol/ui`，而声明在 `extensions` 下面。错误不在这里报出来：测试看到的是，Apps 宿主读 `tools/list` 刚给出的 URI，拿到 `-32602 Unknown resource URI`。URI 没错，是 `_read` 的条件把“没声明扩展”也算成了“不认识这个 URI”，而 `_apps_enabled` 把一个正确声明的宿主判成了没声明。
2. `_tool` 写成了 `apps or APPS_EXTENSION in self.extensions`。docstring 写的是服务端提供 Apps、客户端也声明了才带绑定，课里叫 Both peers opt in。服务端自己总是提供，所以 `or` 让每个客户端都拿到 `_meta.ui`。练习 1 测的就是这一条。
3. `_read` 把缺扩展并进了 `-32602`。docstring 和课里 Fallback 一节都要求 `-32021`，data 里 `requiredCapabilities.extensions` 写明缺哪个扩展；只有不认识的 URI 才是 `-32602`。
4. `AppMount.review` 每次都重新审查：把 1 MB 的 HTML 重新编码、算 sha256、再查一遍 CSP。宿主每处理一个 View 动作就调一次，2000 次本机实测 0.7 到 2.0 秒，限值 0.05 秒；修好以后 0.4 到 3 毫秒。

护栏：

- 声明必须是 extensions 下面的一个对象。用 `in` 会把名字列表 `["io.modelcontextprotocol/ui"]` 和 `true` 都当成声明；用 `is not None` 会放过 `true`；用真值判断会把正确的空对象 `{}` 当成没声明；反过来写成 `== {}`，带设置的声明 `{"com.example/preview": true}` 又被当成没声明；对 extensions 直接 `.get`，遇到列表报 AttributeError；写 `capabilities["extensions"]`，遇到没有 extensions 的客户端报 KeyError。名字列表这一条来自本课自己的测试。
- 不能修过头：不认识的 URI 仍然是 `-32602`；没有扩展的宿主拿到的是同一个工具，只是没有 `_meta.ui`，不是空列表。
- 审查结果可以缓存，但要随变化失效。`replace` 换上 CSP 更窄的新版本，下一次动作要用新的审查；换上没准入的版本，`review()` 要报 ReviewError，不能退回上一版的审查（课里：A stale iframe must not keep broader permissions）；`withdraw` 撤回摘要后，下一次动作就要被拒。永久缓存、按 URI 缓存、新版本审查不过就继续用旧版本、只在 replace 时清缓存、为了提速只对前 4 KB 算摘要，都会被抓住。

看什么：是不是先找到 `-32602` 是哪一行抛的，再想“为什么一个声明了扩展的宿主被当成没声明”；会不会打印 `meta[CLIENT_CAPABILITIES_META]` 看实际结构；修计时之前有没有先说清楚“审查结果什么时候会变”。

提示：

- H1："The URI came straight from tools/list. Why would the server call it unknown?"
- H2："Print what _apps_enabled sees for the Apps host."
- H3：直接指出 extensions 那一层。

追问：

- "Why bind the UI in tools/list instead of returning HTML from tools/call?"（调用之前就能预取、缓存和做安全审查；结果保持纯数据，文本宿主和模型一样能用；课里 Declare the UI on the tool definition 一节）
- "tools/list says public but differs by capability. What does a shared cache have to do?"（缓存键要带上声明的扩展；只按方法缓存的话，先来的客户端决定了后来的客户端看到什么）
- "Unknown URI and no extension at once. Which error first?"（两种顺序都说得通；先查能力，就不会向没声明扩展的客户端透露这个 UI 资源存不存在）
- "Why is keeping the old review a bug when the new version fails?"（旧版本的 CSP 和权限可能更宽；新版本审查通过之前，View 不该在任何审查下运行）

### Part 2 App 资源缓存（目标 12 分钟）

坑：

- blob 要按字节读写。`read_text()` 默认按 universal newlines 读，会把 `\r\n` 和单独的 `\r` 都变成 `\n`，读回来摘要对不上，表现为没命中。`print()` 多写的换行、`strip()`、`utf-8-sig` 的 BOM 都会改字节。测试的 HTML 里有 `\r\n`、单独的 `\r`、U+2028 和非 ASCII 字符。
- 摘要是 HTML 的 UTF-8 字节的 sha256 十六进制，不是整个 content 的 JSON。
- 读 blob 时校验摘要。测试把 blob 换成一段偷 cookie 的脚本，必须当作没命中。缓存里放的是会执行的代码，这一步是安全边界。
- 去重不能只看文件在不在。blob 坏了以后再存一次，要能把它修好。
- 缺了 blob 是没命中，不是 FileNotFoundError。
- 键是 URI、服务器名字、版本和摘要，private 再加 principal。少了版本，2.1.0 会命中 2.0.0 的条目；少了名字，另一台服务器会命中；少了摘要，同一个 URI 的新版本会盖掉旧版本。
- public 的条目谁都能拿，存的时候带了 principal 也一样；private 的条目只给它自己的 principal，None 也不行。把 principal 一律放进键，或者一律不放，都会挂；只按调用者的 principal 查也会挂。
- principal 是 private 条目键的一部分，不是条目的一个属性。测试把同一份 HTML 给 alice 和 bob 各存一次，CSP 不同：只在条目里记一个 owner、键里不带 principal，后存的会盖掉先存的，alice 就拿不到自己的那份。
- `_meta` 原样往返：CSP 列表的顺序、空列表、`com.example/build` 这种别的键都要保留。把 CSP 排序成规范形式、只存 `_meta.ui`，都会挂。
- 索引要落盘。只放在内存里，新开的 AppCache 看不到。
- private 缺 principal、MIME 不是 `text/html;profile=mcp-app`、URI 不是 `ui://`，都报 ValueError。
- 最后一段是端到端检查：从本课的服务端读出 App（Part 1 要先修好），以 alice 的身份存进缓存，bob 从新开的缓存里拿到同一份，交给 AppMount 审查通过。

追问：

- "Two host processes share this folder?"（blob 是内容寻址的，两个进程写同一个 blob 写的是同样的字节，临时文件加 rename 就够；索引是读、改、写，要加文件锁，或者一个条目一个文件）
- "When can a blob be deleted?"（没有任何索引条目引用它的时候；引用计数，或者定期扫描）
- "Why key on the server version when the digest already pins the bytes?"（同样的 HTML 在不同版本下，CSP 和权限元数据可能不同；版本也是准入的一部分）
- "Why never serve a private entry across principals, even for the same URI?"（课里：HTML 或者它的策略元数据可能因人而异）

### Part 3 宿主策略引擎（目标 12 分钟）

坑：

- `connectDomains` 只管 fetch、XHR 和 WebSocket，`resourceDomains` 只管脚本、样式、图片和字体。两张表合起来查，“能加载字体”就变成了“能上传数据”（课里：permission to load a font or script should not grant arbitrary data upload）。反过来也一样。
- 源要精确相等。`startswith` 会放过 `https://api.notes.example.evil.test` 和 `https://api.notes.example@evil.test`；只比主机名会放过 `http://`；`startswith(origin + "/")` 会拒掉没有路径的 `wss://live.notes.example`；按 `/` 切出前三段，会把 `https://api.notes.example?since=...` 切错。用 `hostname` 拼源会丢掉端口，`https://api.notes.example:8443` 就混成了列出的 `https://api.notes.example`。用 `urlsplit` 取 scheme 和 netloc 拼起来最直接，端口原样留在 netloc 里。
- 缺了 csp，或者缺了其中一张表，都按空处理，不能 KeyError。
- 设备只有 permissions 里写了才允许，不能“声明了任何一种就全开”。
- postMessage 只认固定的那一个源，字符串精确相等：末尾带斜杠、加了后缀、`null`、空字符串都不行。构造时传 `"*"` 报 ValueError。
- 按钮点击是意图，不是批准：`user_gesture=True` 的调用不经 approve 就不能 run。
- 一个调用只能 run 一次。
- 撤销一个 capability，它下面所有挂起的调用都拒绝，包括已经批准、还没执行的，按 id 从旧到新返回；别的 capability 下的调用不受影响。
- 被撤销拒绝的调用永远是拒绝的，之后重新 grant 也不能复活。只在 run 的时候查一下 capability 的写法过不了这一条；连 run 时都不查的写法会让已批准的调用在撤销后照样执行。
- 撤销以后再 request 要立即 Refused；从来没广告过的 capability 也一样。

追问：

- "connectDomains lists one API. What can a malicious script inside the App still do?"（把它拿到的任何数据发到那个 API；精确匹配只解决发到哪，不解决发什么。所以默认留空、不在 iframe 里放 bearer token、尽量由宿主代理窄操作、限制请求和响应大小、记录每个外发请求是哪个用户动作触发的）
- "Exercise 4 moves the script to a CDN. What changes?"（resourceDomains 加上 CDN 的源；供应链风险是 CDN 上的脚本变了，而审查过的 HTML 摘要不会变）
- "Why check at action time and not only at ui/initialize?"（App 打开期间能力会被撤销：换账号、策略变化、服务器被隔离、宿主收窄同意）
- "How should the View treat Refused?"（当成正常结果，不要反复重试直到宿主让步）

### Part 4 Apps 桥生命周期（目标 14 分钟）

坑：

- 输出格式由测试决定：每一帧是 (目标源, 消息)，测试按有没有 method 把消息分成回答和通知。回答带 View 用的 id；通知不带 id，带一个 `"id": null` 就不再是通知了。
- `ui/initialize` 要马上回答。View 要等到这个回答才发 `ui/notifications/initialized`，把回答也扣下来，真实环境里就是死锁，测试里表现为回答出来得太晚。
- id 0 是合法的 id，课里的 View 就用 0 发 `ui/initialize`。用 `if message.get("id")` 判断是不是请求，0 会被当成通知。
- 宿主自己发起的通知（工具结果、主题变化、告诉 View 的尺寸）在 `ui/notifications/initialized` 之前排队，之后按发生顺序发出。测试记下每一帧出来时桥已经从 inbox 拉了几个事件，所以先读完整个 inbox、提前发、晚一拍发都看得出来。
- 前缀：核心的 `notifications/initialized` 已经删除，只有 `ui/notifications/initialized` 开闸；用 `endswith` 判断会被前者骗过。核心的 `initialize` 请求也不是 Apps 握手，回 `-32601`。
- 尺寸按每一维分别封顶，不按比例缩放。测试要的是 1200×700，上限 800×600，两维都要截到上限；高度误用宽度的上限会得到 700。通知里只带变化的字段，不发整份 context。
- `ui/initialize` 的回答带的是此刻的上下文。最后一段在 View 初始化之前先来了一次主题变化，回答里的 theme 要是 dark；用构造时传进来的 `host_context` 回答会挂。原地改 `host_context` 也不行，它是调用方的对象。
- tools/call 变成一个新的核心请求：id 来自 `core_ids`，元数据和路由头是宿主自己的（`make_request`），只带 View 的 name 和 arguments。View 塞进来的 `_meta`（自称 2025-11-25）和 `principal` 都不能转发。
- 核心响应回来时，用核心 id 在在途表里找到 View 的 id，再用 View 的 id 回给 View。两个响应乱序到达；重复的响应要忽略，所以找到以后要从在途表里删掉。用 View 的 id 当核心 id，或者用核心 id 回 View，都会挂。
- 不是 JSON-RPC 2.0 对象的消息（一个字符串、一个没有 jsonrpc 的对象），以及 View 发来的响应（有 id 没有 method），都忽略：不能崩，也不能回答。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。
- 最后一段把桥接到本课的服务端。服务端会校验 `_meta` 和路由头，转发 View 原始消息的写法在这里会拿到错误。

追问：

- "Isn't ui/initialize just the old session coming back?"（不是。它只连接一个 iframe 和一个宿主帧，不协商 MCP 协议版本，不创建服务端状态，不签发会话；桥触发的每个核心请求仍然自带完整的元数据）
- "Where would user approval sit in this bridge?"（Part 3 的策略：转发 tools/call 之前先 request，等用户 approve，执行的时候再查一次）
- "The View posts a thousand size changes a second?"（合并成最新的一次，按帧或者节流发出；封顶本来就在宿主）
- "A core response never comes back?"（在途表要有超时，超时给 View 回一个错误；View 卸载时清掉它的在途请求）

### Part 5 缓存失效传播（目标 12 分钟）

坑：

- 四种事件对应课里的四种失效条件：ttlMs 到期、`_meta.ui.resourceUri` 绑定变化、服务器版本或准入的描述符 pin 变化、已确认订阅的资源变更通知。
- 资源用 (server, uri) 标识。同一个 URI 字符串在 notes 和 tasks 两台服务器上是两个资源，只按 URI 匹配会把另一台服务器拖进来；订阅也要按 (server, uri) 匹配。
- 到期只丢那一个条目，以及从它挂载的 View。按资源处理会把 bob 的副本也丢掉；按摘要（共享的 blob）处理会把另一台服务器上内容相同的条目丢掉。
- 变更通知只在有已确认的订阅时才算数。
- 绑定从 A 改到 B：A、B 两个资源都失效，从它们的条目挂载的 View、绑定到它们的工具的 View 都要重挂，这个工具自己的 View 也重挂。只看新的或只看旧的都会漏。
- 服务器变化：它的全部资源都失效，既包括缓存里有条目的（legacy，已经没有工具绑定它），也包括有工具绑定的（stats，缓存里没有条目）。只看一边都会漏。
- 资源失效时，要重挂绑定到它的工具的 View，不只是从被丢条目挂载的 View：v7 挂载时用的条目早就被驱逐了，只顺着条目找不到它。
- 结果排序、去重。测试里 dict 的插入顺序是乱的；一批事件里同一个条目出现两次，也只输出一次。
- 第一次绑定的工具没有旧资源。用 `state.bindings[(server, tool)]` 取旧 URI 会 KeyError，要用 `.get`。
- 未知的事件类型报 ValueError。
- 只读 state，不改它。把绑定事件写回 `state.bindings`，下一次规划就会按新绑定算；测试在最后比较 state 和原样。

追问：

- "Why remount a View when only its cache entry expired?"（课里：重新取回、重新审查之后才能重挂；没审查过的新版本不能在旧的权限下跑）
- "Change events keep arriving while you remount. What then?"（给每个 (server, uri) 记一个代数，重挂前再比一次，过时的重挂直接放弃）
- "The server bumps its version but the HTML is identical. Still remount?"（是。版本和描述符 pin 是准入的一部分，CSP 和权限元数据可能变了；摘要不变可以复用 blob，审查要重做）
- "How would you check this against a real host?"（把订阅确认、绑定变化、版本变化记成事件日志，回放成这套事件，比较计划）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读断言消息和 traceback、打印实际数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出缓存键、外泄路径、撤销、背压和超时、失效的传播 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
