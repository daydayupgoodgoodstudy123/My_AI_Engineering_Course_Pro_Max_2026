# 面试官手册：uricatalog（13/10）

候选人计时期间不要看。候选人手里只有 README、`uricatalog/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 无权读的笔记能不能报“存在但没权限”？ | "No. It gets exactly the error a missing note gets, so an error never confirms that a hidden note exists." |
| 1 | 订阅一个不存在或读不了的 URI，要不要拒绝？ | "This server accepts any URI string in the filter. Reads stay authorized and an event carries no content. Tell me what you'd change and why." |
| 1 | resourceSubscriptions 是空数组怎么办？ | "Your call. Say what you chose. The tests don't cover it." |
| 1 | 计时包括打开订阅吗？ | "No. Only delivering the updates is timed." |
| 1 | list_changed 也要改快吗？ | "Not for the tests. Mention it if you change one and not the other." |
| 2 | params 里哪些进键？ | "The uri and the cursor. Ignore anything else in params." |
| 2 | 已经有新鲜的缓存，又来一个 ttlMs 为 0 的结果？ | "Leave the cached entry alone and don't store the new one. The tests don't cover it." |
| 2 | 过期的条目要删吗？ | "You may. The tests only check that get returns None." |
| 2 | 一个缓存文件会给多个用户用吗？ | "Yes. One host serves many users from the same file. That's why private entries carry tenant and user." |
| 2 | 值可以用 pickle 存吗？ | "Prefer JSON. Loading pickle from a file other people can write runs their code. The tests don't check." |
| 3 | 页大小谁定？ | "The server: its page_size. A client never picks it." |
| 3 | 两页之间加了或删了笔记，旧游标还能用吗？ | "Yes. The next page starts after the cursor's last URI, whatever happened in between." |
| 3 | 游标用什么格式？ | "Up to you, as long as nobody can change it without the secret and any instance with the same secret can read it." |
| 3 | 游标会过期吗？ | "Not here." |
| 3 | 调用者一条都看不到时返回什么？ | "An empty resources list and no nextCursor." |
| 4 | 请求 id 谁分配？ | "The client, from self._ids. Listen and read requests share that counter, so their ids never collide." |
| 4 | 最终回复到的时候，重读还没完成？ | "Finish the re-read and log it, then log closed." |
| 4 | 收到 notifications/resources/list_changed 怎么办？ | "No action needed here. The tests don't send one." |
| 4 | 通道关闭时还有读请求在等回复？ | "Fail that read; the subscription is over. The tests don't cover it." |
| 4 | listen 收到的是错误回复，不是确认？ | "Then it never opened. Log closed for it. The tests don't cover it." |
| 4 | 同一个 URI 连着两次更新，要读两次吗？ | "Either is fine. The tests send one update per URI." |
| 5 | 字面段要不要和它的百分号编码形式（%61rchive）等价？ | "Decode each segment once, then compare. The tests don't cover it." |
| 5 | 模板里能写查询参数吗？ | "No. Only whole-segment variables." |
| 5 | 没有变量的模板合法吗？ | "Yes. It's a literal path." |

## 每关：要看什么、提示、追问

### Part 1 修读取、提示词和订阅（目标 10 分钟）

一个测试里叠了 4 个缺陷和 6 个护栏：

1. `handle_prompts_get` 里的 review_note 自己去 catalog 查笔记，只查存不存在，不查授权。bob 用 prompts/get 就能拿到只给 alice 看的 note-3 全文。docstring 写的是只对能用 resources/read 读到这条笔记的人有效。
2. `readable_contents` 对未知 URI 和读不了的笔记都返回空列表，于是 resources/read 回一个 contents 为空的成功结果。docstring 写的是统一抛 -32602，`data` 里带 uri。按 docstring 把 prompt 改成走 `readable_contents` 以后，错误变成 `handle_prompts_get` 里 `contents[0]` 的 IndexError：报错在 prompt，根因在下一层。
3. `accept_filter` 把请求里所有真值字段原样收下，只给 URI 去重排序。未知的 `toolsListChanged` 和 `"promptsListChanged": "yes"` 都进了确认。docstring 要求只认 `SUPPORTED_NOTIFICATIONS`，开关必须恰好是 true。写成 `value == True` 会让 `1` 和 `1.0` 混进确认，测试另开一条流专门查这个。
4. `SubscriptionHub.resource_updated` 每次更新都把每条流的 URI 列表扫一遍（`uri in list`）。100 条流各订 3000 个 URI 时，1200 次更新要 1.2 到 2 秒，限值是 0.1 秒。
5. 护栏：notes://note-1 的更新不能投给只订了 notes://note-10 的流，前缀或子串匹配会挂。
6. 护栏：两个客户端都用 id 17 listen，两个都要收到事件。按 subscription id 建索引，后一个会把前一个覆盖掉。
7. 护栏：每个事件带它自己那条流的 id。为了省事只构造一个事件对象发给所有流，id 23 的流会收到 id 17。
8. 护栏：关闭的流什么都收不到。建了索引却不在 close 时删、也不查 closed，会挂。
9. 护栏：list_changed 只发给接受了这个开关的流；只订 list-changed、没订任何 URI 的流也要能打开、能收到。建索引时直接取 `accepted["resourceSubscriptions"]` 会 KeyError。
10. 护栏：畸形过滤器（resourceSubscriptions 不是字符串数组、没有 notifications）仍是 -32602。重写 `accept_filter` 时顺手把校验删了会挂。

用每条流一个 set 代替列表也能过计时（每次更新还是要看一遍所有流），面试官可以追问规模再大时怎么办。

看什么：是不是先把 bob 拿到的响应打印出来、和 resources/read 的结果对比；会不会读 docstring；IndexError 出来时，是在 prompt 里补个判断了事，还是回到 `readable_contents` 修根因。

提示：
- H1："What does bob get back from prompts/get, and what does resources/read give him for the same URI?"
- H2："Read the docstring of readable_contents, then its last four lines."
- H3：直接指出 prompt 自己查 catalog，以及 `readable_contents` 里的 `return []`。

追问：
- "Why -32602 and not a dedicated not-found code?"（课里说当前 Resources 规范把未知或非法的资源 URI 归为 invalid params，这样客户端能区分“不存在”和“合法的空文档”，也避免回退到更宽的查找）
- "Should the server accept a subscription to a note the caller can't read?"（可以在确认里去掉读不了和不存在的 URI，两者一样处理才不会泄漏存在性；不去掉的话，事件本身不带内容，重读时照样授权，但对方能知道这条笔记什么时候改了）
- "One URI has 50,000 subscribers. What costs now?"（成本从扫描变成扇出本身；按连接批量发送；慢客户端的流要有上限，满了就断开）
- "Why must close() take the stream out of the index?"（不然关掉的流被索引一直引用，内存只增不减，而且要靠 closed 标志兜底）

### Part 2 主机响应缓存（目标 12 分钟）

坑：
- 用分隔符拼键：租户 `a|b` 加用户 `c`，和租户 `a` 加用户 `b|c`，拼出来是同一个键，一个人的私有结果会给另一个人。测试把 128 个 ASCII 字符和几个多字符分隔符都试一遍，换个冷门分隔符也过不了。要用单射的编码：JSON 数组、长度前缀或 repr。
- 每个字段先 `str()` 再编码：游标 None 和字面量 "None" 撞键。
- 私有键只放用户、不放租户：另一个租户里的同名用户会命中。
- 漏了 locale：fr 的请求拿到 en 的结果。
- public 结果也带上用户：跨用户复用不了；反过来全按 public 存，私有结果就泄漏了。
- ttlMs 为 0、没有缓存提示、cacheScope 是 "no-store"，都不存，put 返回 False。课里说 MCP 只定义了 public 和 private，no-store 是主机自己的策略，不是 cacheScope 的值。
- 新鲜度是严格小于：时间到 t + ttlMs 那一刻就过期了，写成 `<=` 会在 31000 毫秒处挂。时钟要用注入的整数毫秒，用 time.time() 也会挂。
- 往返要完全一致。文本里有 CRLF、U+2028、NUL、emoji，还有 JavaScript 服务器把 emoji 截成一半留下的孤立代理项。`json.dumps(..., ensure_ascii=False).encode("utf-8")` 会报 UnicodeEncodeError；默认的 ensure_ascii 把它写成转义，能原样读回。
- put 不能改调用方传进来的 dict。把 expiresAt 塞进 result 会挂。
- dbm.dumb 的键和值读回来都是 bytes。invalidate 里拿 str 去 startswith 会报 TypeError。
- invalidate 只删这个 URI 的 resources/read 结果，所有调用者的都删，别的都留着。按子串匹配会把 note-10 一起删掉；在结果内容里找 URI 会把列表页也删掉。
- 重开以后还要读得到：只放在内存里的 dict 会挂。同一个键写第二次要覆盖第一次。

追问：
- "Ten thousand users share this cache file. What breaks first in dbm.dumb?"（整个索引常驻内存；每次删除都重写 .dir 文件；两个进程同时写会把索引写坏。换 SQLite 或真正的 KV 存储，或者按用户分片）
- "A user loses access to a note. How long can they still see it here?"（最长 ttlMs。这就是 TTL 的代价；敏感内容用 private 加 ttlMs 0，再加主机的 no-store 策略；权限变化时主动失效）
- "The lesson lists scope among the key dimensions. Where would it go?"（同一个用户换一个范围更小的 token，能看到的就少了；把排好序的 scope 集合加进私有键）
- "Why not hash the key with Python's hash()?"（字符串哈希每个进程随机，重启后同一个请求算出不同的键，缓存全部失效）

### Part 3 resources/list 分页（目标 12 分钟）

坑：
- offset 分页：两页之间在游标前面插了两条、删了一条，offset 会让 n02 重复出现。要按 URI 做 keyset：下一页是“上一页最后一个 URI 之后的”。
- 游标指向的那条笔记被删了以后要照样能继续。用 `index()` 找它的位置会报 ValueError。
- 游标状态存在实例内存里：同一个 secret 的另一个实例接不上。课里说列表不能依赖同一连接上的前一次调用。
- 游标不签名：改一个字符就能跳到别处。用写死的密钥签名：另一个 secret 的服务器也会接受。
- 游标不绑定调用者：bob 拿 alice 的游标能接着翻。只绑定用户名：另一个租户的 alice 能接着翻。
- 最后一页不带 nextCursor，null 也不带，正好满页也一样。“满页就发游标”会让客户端多跑一次空请求。
- 先过滤再分页：bob 的第一页要满 3 条。先切片再过滤只剩 2 条。
- 按 URI 排序，不是按 name。两页之间插进来的 n045 名字叫 "Appendix to note 4"，按 name 排它会跑到 n04 前面。
- 结果要确定：同一个请求在两个实例上得到完全相同的一页，游标也相同。游标里放时间戳或随机数会挂。课里说确定的顺序能避免缓存无谓地失效，而缓存键里正好有游标。
- 不是游标的东西（42、列表、空字符串、"garbage"、非 ASCII 字符串）都是 -32602。用 `if cursor:` 判断第一页，空字符串会被当成第一页；只有 None 才是第一页。其他非法输入不能让 AttributeError、TypeError、binascii.Error 漏出去，因为 handle() 只接 RpcError。拿 str 调 `hmac.compare_digest` 遇到非 ASCII 会报 TypeError。
- 列表随调用者变化，所以 cacheScope 是 private。这一行 handler 里已经写好了，可以问候选人为什么课里的示例是 public（那里没有多用户）。

追问：
- "Keyset doesn't give you a snapshot. What does the client see if a note is added mid-listing?"（插在游标后面的会出现，插在前面的这次看不到；要完整视图就靠 notifications/resources/list_changed 触发重新列一遍）
- "The cursor reveals the last URI in base64. Is that a problem?"（发给的就是能看到这个 URI 的调用者，一般没问题；URI 本身敏感就加密；绑定调用者能防止游标被转手）
- "How do you rotate the secret?"（游标里带密钥 id，轮换期间新旧密钥都接受）
- "Lesson 28 says a client must continue when nextCursor is an empty string. Can your server issue one?"（这个格式永远不为空；但客户端不能用真值判断，应该判断字段在不在、是不是 null）

### Part 4 共享通道上的订阅（目标 14 分钟）

这一关用到 Part 2 的缓存（put、get、invalidate）。Part 2 没做完的话，先去做 Part 5。

坑：
- 输出格式由测试的解析代码决定：每个动作一行 JSON，以换行结尾。缺换行、多空行、indent=2 都会挂。
- 回复按 id 找到请求：prompts/list 的回复前后夹着订阅通知，不是发完请求后的下一条消息。
- 事件不带文档：先 invalidate，再 read。read 走缓存，不先失效会读到测试预先放好的旧副本。
- 要先失效再读，不能读完覆盖。note-3 现在读不到了，覆盖式的写法会把旧副本留在缓存里。
- 确认之前的事件、最终回复之后的事件、从来没 listen 过的 subscription id，都记一条 dropped，不处理。
- 确认记录里写服务器接受的过滤器，不是请求里的：c 请求了 note-9，确认里没有。
- a 的最终回复到的时候，a 的重读还没回来。closed 要等 a 前面的事件处理完再写，在读循环里收到就写会把顺序弄反。
- 同一个订阅的事件按到达顺序处理。a 订了 note-1 和 note-4，两个更新连着到，note-1 的读回复被压住。每个更新各开一个 task 并发去读，note-4 会先写进日志，顺序就反了；在 closed 之前把这些 task 都等完也没用。
- 一个订阅的慢重读不能挡住别的订阅。测试把 a 的读回复压住，直到 b 的读请求到达。所有订阅共用一个 worker，或者在重读外面套一把全局锁，都会被这个探针抓到。
- 读循环自己不能等重读：回复要从同一条通道读进来，读循环一等就是自己等自己，测试 1 秒后报 "run() stalled"。
- 最终回复的 id 是订阅的 id，不在 pending 里，拿它去 pending 里 pop 会 KeyError。
- 每个动作发生时就写：第一个读请求到达时，日志里必须已经有 a 的确认。攒到最后一起写会挂。
- 通道关闭后，run() 要等所有订阅都写完 closed 再返回。不等 worker 就返回，这套测试抓不到：通道关闭时每个 worker 只差一步，事件循环会在测试检查之前跑完它们。看代码时注意这一点，可以问候选人“关闭时正好有一个重读在途会怎样”。

追问：
- "Over Streamable HTTP, what changes?"（课里说每个 listen 是一个 POST，响应保持成 SSE 流，关闭响应流就是取消；每条流只有一个订阅，不用按 id 分发，但事件里照样带 id）
- "A burst of 10,000 updates for one URI?"（合并：每个 URI 最多一个读请求在途，后来的更新只标记“还要再读一次”）
- "The connection drops and comes back. What do you trust?"（通知可能丢了。重新 listen，然后把缓存里的东西重新读一遍或直接作废）
- "Why invalidate before reading instead of overwriting after?"（读可能失败，比如权限被撤销；失败时旧副本不能留下）

### Part 5 资源模板路由树（目标 12 分钟）

坑：
- 字面段优先：`notes://projects/archive/decisions/d-1` 要走 archived-decision。
- 优先级看第一个不同的段，不是看谁的字面段多。`notes://projects/roadmap/decisions/latest` 同时匹配 decision（2 个字面段）和 `notes://{workspace}/roadmap/decisions/latest`（3 个字面段），第一个不同的段是 projects 对 {workspace}，所以 decision 赢。用一串正则、按字面段个数排优先级会挂在这里。
- 字面分支走不通时要回到变量分支：`.../archive/notes/n_7` 和 `notes://projects/archive` 都要匹配变量那条。贪心地只走字面分支会返回 None。
- 每个模板用自己的变量名：同一位置一个叫 {project}、一个叫 {slug}。节点上只存一个名字的写法，要么注册时报错，要么返回错的名字。
- 先按 / 切段，再对每段解码一次。整串先解码会让 %2F 变成新的段；解码两次会让 %2541 变成 A；不解码 %41 就匹配不上。
- 变量值是 1 到 64 个 ASCII 字母、数字、- 或 _。`re.match(...$)` 会放过结尾的换行（%0A），`\w` 和 isalnum 会放过 Ü，`{1,65}` 会放过 65 个字符，`{0,64}` 会让空段匹配上。
- 多余或缺少的段都不匹配，末尾的 / 也不能吃掉。
- 注册时，形状完全一样的模板（变量名不同也算）是歧义，要报 ValueError，而且不能覆盖已有的那个。只比较模板字符串查不出来。字面段和变量段在同一位置共存不算歧义，当成歧义拒绝会在注册阶段就挂。
- 畸形模板都要 ValueError：同一个变量出现两次、半段变量 v{n}、括号不配对、空段、末尾 /、变量名不是标识符、不是 notes:// 开头。

追问：
- "Why a tree and not a list of regexes?"（查找代价跟深度有关，跟模板数量无关；优先级就是遍历顺序；歧义在注册时就能发现）
- "Where does authorization happen once a URI matches?"（匹配之后。变量作为类型化参数交给存储查询，课里说不要把 URI 尾部拼进文件路径或 SQL）
- "Someone wants {path} to match several segments. What do you check?"（多段变量要单独定规则；课里提醒 file:// 资源要在解析符号链接和相对段之后再检查目录边界）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看实际响应、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、并发、权限撤销、断线重连 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
