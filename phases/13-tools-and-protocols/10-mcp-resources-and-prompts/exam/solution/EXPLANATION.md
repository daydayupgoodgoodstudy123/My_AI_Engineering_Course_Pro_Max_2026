# 参考答案讲解：uricatalog（13/10）

计时结束后再看。参考实现在同目录的 `uricatalog/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修读取、提示词和订阅

**现象**：解锁后第一个失败是 bob 调 prompts/get 拿 review_note 去看 note-3，得到的是成功结果，消息里就是 alice 的薪资笔记全文。

**顺着往下找**：`handle_prompts_get` 自己去 `self.catalog.get(uri)` 查笔记，只判断存不存在。`readable_contents` 的 docstring 写明了 resources/read 和所有嵌入资源的 prompt 都要经过它，这样两边用同一套授权。课里说 prompt 的 URI 参数要和直接读资源过同样的授权检查，prompt 不能变成绕开资源访问的旁路。

**依次修四处**：

1. review_note 改成调 `self.readable_contents(uri, caller)`，用返回的第一项的 text。改完再跑，错误变成 `contents[0]` 的 IndexError：bob 读不了 note-3，`readable_contents` 却返回了空列表。报错在 prompt，根因在下一层。
2. `readable_contents` 在找不到笔记、或者调用者读不了时，抛 `RpcError(-32602, "Unknown or invalid resource URI", {"uri": uri})`。课里说未知 URI 不是一次成功的空读取，客户端要能把“不存在”和“合法的空文档”分开。读不了的笔记和不存在的笔记给完全相同的错误，错误本身就不会透露一条隐藏笔记存在。
3. `accept_filter` 重写成按 `SUPPORTED_NOTIFICATIONS` 逐个字段取：两个 list-changed 开关只有值恰好是 `True` 才接受，`"yes"` 不算；`resourceSubscriptions` 去重排序；`toolsListChanged` 这类未知字段丢掉。课里说确认里的过滤器只包含服务器接受的子集，`notifications` 是允许列表，没请求的通知类型不能发。
4. `SubscriptionHub` 加一个从 URI 到流的索引。`open` 时登记，`close` 时删除，`resource_updated` 只看这个 URI 下的流。原来每次更新都对每条流做一次 `uri in list`，100 条流各 3000 个 URI、1200 次更新要 1.2 到 2 秒；改成索引后约 1 毫秒。

**护栏**：改成索引时最容易出这几种错，测试都会抓住：

- 按前缀或子串找流，notes://note-1 的更新会发给只订了 notes://note-10 的流。
- 用 subscription id 当索引的键。subscription id 就是 listen 请求的 id，只在一个客户端的通道里唯一，两个客户端都用 17，后一个会把前一个顶掉。参考实现用流对象本身当键（dict 当有序集合用，投递顺序就是打开顺序）。
- 只构造一个事件对象发给所有流，事件里的 subscriptionId 全是第一条流的。
- close 时不从索引里删，关掉的流还会收到事件。
- 建索引时直接取 `accepted["resourceSubscriptions"]`，只订 list-changed 的流一打开就 KeyError。
- 重写 `accept_filter` 时把 -32602 的校验也删了。

每条流各用一个 set 也能过计时，但每次更新仍要看一遍所有流，规模再大还是会慢。

## Part 2 主机响应缓存

参考实现把每个结果存成一条 JSON：`{"expiresAt": 存入时刻 + ttlMs, "result": 原样的结果}`。键也是 JSON 数组：`[scope, method, uri, cursor, locale]`，私有结果再加 `tenant, user`。

- **键必须单射**：用 `|` 之类的分隔符拼，租户 `a|b` 加用户 `c` 和租户 `a` 加用户 `b|c` 会变成同一个键，一个用户的私有笔记就给了另一个用户。课里说缓存键要包含所有会改变可见内容的维度，这只是一半；另一半是这些维度编码以后不能互相串。JSON 数组、长度前缀、repr 都可以；先 `str()` 再编码不行，None 和 "None" 会撞。
- **两种作用域**：put 按结果自己的 cacheScope 选键；get 先查这个调用者的私有键，再查公共键。课里说 MCP 只定义了 public 和 private，所以 "no-store" 不存；ttlMs 为 0 或者没有缓存提示也不存。
- **时间**：时钟是注入的整数毫秒，存入时刻 t、ttlMs 为 n 的结果在 t + n 之前新鲜，到 t + n 就过期。过期时刻存成绝对值，重开以后照样按原来的时刻过期。
- **原样读回**：结果是服务器发来的任意 JSON。文本里那个 U+D83E 孤立代理项，是 JavaScript 服务器把 emoji 截成一半时会出现的东西，Python 的 json 能读进来。`json.dumps` 默认 `ensure_ascii=True`，会把它写成转义，存进 dbm 的是纯 ASCII，能原样读回；关掉 ensure_ascii 再 `encode("utf-8")` 会报 UnicodeEncodeError。put 也不能往调用方的 dict 里加字段。
- **dbm.dumb**：键和值读回来都是 bytes，`json.loads` 能直接吃 bytes。`invalidate` 遍历 `self._db.keys()`，把键解析回数组，删掉方法是 resources/read、URI 完全相等的条目，不管是谁的。按子串匹配会把 note-10 一起删掉。dbm.dumb 覆盖已有的键时只改内存里的索引，`close()` 才把索引写回 .dir 文件，所以重开前要 close。

## Part 3 resources/list 分页

`list_page` 先过滤出调用者读得到的笔记，按 URI 排序；有游标就只留 URI 大于游标里 `after` 的；取前 `page_size` 条；后面还有才发 nextCursor。

游标是 `base64url(JSON 载荷) + "." + HMAC-SHA256 十六进制摘要`，载荷是 `{"after": 本页最后一个 URI, "tenant": ..., "user": ...}`。

- **keyset，不用 offset**：测试在第一页和第二页之间，在游标前面加了两条、删了一条（正是第一页的最后一条），在后面加了一条、删了一条。offset 会让 n02 再出现一次；keyset 只看“最后一个 URI 之后”，不受前面变化的影响，游标指向的笔记被删了也照样能继续。用 `index()` 去找这个 URI 的位置会报 ValueError。
- **无状态**：游标自己带着位置和调用者，任何拿着同一个 secret 的实例都能接着翻。把随机令牌映射到位置存在实例内存里，第二页换一个实例就接不上了。课里说列表不能依赖同一连接上的前一次调用。
- **签名和绑定**：HMAC 让别人改不了游标；载荷里的租户和用户必须等于这次请求的调用者，bob 拿到 alice 的游标也用不了。比较摘要用 `hmac.compare_digest`，先把两边都编码成 ASCII bytes，非 ASCII 的垃圾输入也只会变成 -32602。
- **排序键是 URI**：按 name 排，插进来的 "Appendix to note 4" 会排到 n04 前面。
- **确定**：同一个请求得到同一页，游标也一样（`sort_keys=True`，没有时间戳和随机数）。课里说确定的顺序是为了避免缓存无谓地失效，而主机缓存的键里正好有游标。
- **最后一页**：看过滤后剩下的条数是否大于页大小，大于才发 nextCursor。正好满页也没有 nextCursor，也不写成 null。
- **错误**：所有解析失败都转成 `RpcError(-32602)`。第一页只认 `cursor is None`，空字符串不是这个服务器签发的游标，也是 -32602。`handle()` 只接 RpcError，别的异常会直接冒出去。

## Part 4 共享通道上的订阅

`run()` 里只有一个读循环，它从不等待别的事：

```python
while (message := await channel.receive()) is not None:
    if "method" not in message:        # 回复
        id 是某个订阅的 -> 这个订阅结束：往它的队列里放结束标记
        id 在 pending 里 -> set_result
    else:                              # 通知，按 _meta 里的 subscriptionId 分
        确认且还没开始 -> 状态改成 open，建队列和 worker
        状态是 open    -> 放进它的队列
        其他           -> 写一条 dropped
```

每个订阅一个 worker，按顺序处理自己的队列：确认就写 acknowledged，记录服务器接受的过滤器；resources/updated 先 `cache.invalidate(uri)` 再 `await self.read(uri)`，成功写 reread，RpcError 写 unreadable；遇到结束标记写 closed 后退出。通道关闭后，给还开着的订阅放结束标记，让还在等回复的请求失败，再等所有 worker 结束。

- **为什么读循环不能自己等重读**：重读的回复也要从这条通道读进来，读循环一等就是在等它自己。
- **为什么每个订阅一个 worker**：测试把 a 的读回复压住，直到 b 的读请求到达。所有订阅排一个队，或者在重读外面套一把锁，b 的请求就发不出去。
- **为什么一个订阅只用一个 worker 按顺序处理**：a 订了两条笔记，两个更新连着到。每个更新各开一个 task，note-1 的回复被压住时 note-4 会先写进日志。docstring 要求每个订阅按顺序处理自己的消息。
- **为什么结束标记放进队列**：a 的最终回复到达时，a 的重读还没回来。放进队列，closed 就排在 a 前面的事件之后。
- **为什么先失效再读**：事件不带文档，课里说客户端要用 resources/read 重新读、接受当前授权。读走缓存，不先失效就读到旧副本；note-3 现在读不到了，先失效才不会把旧副本留下。
- **为什么要记 dropped**：课里说服务器在任何事件之前先发确认。确认之前的事件、最终回复之后的事件、没人 listen 过的 id，都不属于某个订阅的有效期。

## Part 5 资源模板路由树

注册时，模板拆成段：`{name}` 是变量，其他必须是合法的字面段。树的每个节点有一个字面子节点表和最多一个变量子节点；终点节点记录模板名和这个模板自己的变量名列表。形状完全相同的模板会走到同一个终点，那就是歧义：先沿着形状查一遍，已经有模板就报 ValueError，什么都不改。

匹配时先按 `/` 切段，每段 `unquote(..., errors="strict")` 一次，然后深度优先：先试字面子节点，走不通再试变量子节点（值要 `fullmatch` 1 到 64 个 ASCII 字母、数字、- 或 _），找到的第一个终点就是赢家。这个顺序恰好实现了“在第一个不同的段上是字面量的那个模板赢”（不是“字面段多的赢”：`notes://projects/roadmap/decisions/latest` 归 decision，不归字面段更多的 `notes://{workspace}/roadmap/decisions/latest`），失败时回溯也让 `.../archive/notes/n_7` 能回到 `{project}` 那条分支。

- `%2F` 只有在切段之后解码才不会变成新的段；整串先解码，`alpha%2Fdecisions%2Fd-1` 会被路由到 project alpha 的 decision d-1。
- 只解码一次，`%2541` 才是 `%41` 而不是 `A`。
- `re.fullmatch` 而不是 `re.match` 加 `$`：后者会放过结尾的换行。字符集写成 `[A-Za-z0-9_-]`，`\w` 会放过非 ASCII 字母。
- 递归深度受树的深度限制，URI 里有再多段，走到叶子就停了。

课里说模板不会放宽校验：要解析变量、检查长度和字符集、做授权，用类型化参数构造存储查询。这一关做的是前三步，授权放在匹配之后。

## 这套题证明了什么，没证明什么

通过了说明你能在 MCP 服务器里让 prompt 和资源读取走同一套授权，正确处理未知 URI 和订阅确认，写出按 URI 索引的投递；能按缓存提示设计单射的缓存键并持久化；能写无状态、签名、按调用者绑定的 keyset 分页；能在一条共享通道上分发多个订阅而不互相阻塞；能把资源模板编译成带回溯的路由树。它没有用真实的 Streamable HTTP、SSE 帧或官方 SDK，没有涉及 tools、prompt 注入的防御，也没有测缓存键里的 scope 维度和密钥轮换。课里的 Interactive Lab（把项目管理里的五种能力分到 tool、resource、prompt）需要另外做。
