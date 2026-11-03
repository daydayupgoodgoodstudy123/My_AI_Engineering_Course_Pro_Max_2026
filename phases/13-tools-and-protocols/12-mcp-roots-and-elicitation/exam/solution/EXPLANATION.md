# 参考答案讲解：scopegate（13/12）

计时结束后再看。参考实现在同目录的 `scopegate/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修范围和重放代码

**现象**：解锁后的第一个错误是 `NoteBook.matching` 返回了三条候选，多出来的 note-2 在 `file:///work/notes-evil/` 下面。`matching` 本身没有 bug。

**顺着往下找**：`matching` 用 `uri_within_workspace` 判断一条笔记在不在工作区里，那里最后一行是 `candidate_path.startswith(workspace_path)`。`/work/notes-evil/q3-report.md` 确实以 `/work/notes` 开头，可它们是两个不同的目录。这一关想练的是：报错的位置往往不是出 bug 的位置，候选列表错了，根因在两层之下的路径比较。

**依次修四处**：

1. 按路径分量比较：`posixpath.commonpath([workspace_path, candidate_path]) == workspace_path`。工作区本身也算在里面，根工作区 `file:///` 包含一切。`startswith(ws + "/")` 会把工作区本身和根工作区算错。
2. `file_uri_parts` 先解码、再规范化：`posixpath.normpath(unquote(parsed.path))`。原来的顺序是先 `normpath` 再 `unquote`，`%2e%2e` 和 `%2f` 在规范化的时候还是普通字符，解码以后才变成 `..` 和 `/`，这时已经没人处理它们了；`commonpath` 只比较分量，不解析 `..`，于是 `/work/notes/../private.md` 被当成在工作区里。课里两个反例（前缀混淆和编码穿越）就是这两处。
3. `supports_form_elicitation`：`{"elicitation": {}}` 为了兼容仍然表示只支持 form，`{"form": {}}` 显式支持 form，只声明 `{"url": {}}` 不支持 form。原来的 `elicitation.get("form", {})` 用默认值把“空声明等于 form”的规则写进了每一种声明里，只声明了 url 的客户端也通过了。
4. `ReplayStore` 每次 claim 都用字典推导式重建整张表，n 个未过期的 nonce 每次都要全扫一遍，1 万次 claim 是平方级，本机在负载下要 1.4 到 2.4 秒。参考实现另外维护一个按过期时间排序的最小堆，每次只弹出已经过期的，claim 的均摊代价是 O(log n)，1 万次只要几毫秒。

**护栏**：最常见的提速写法是“满了就淘汰最旧的”，它会忘掉还没过期的 nonce，被淘汰的确认就能再执行一次；讲义说的是有界存储满了就拒绝。第二种是按插入顺序从头清理，假设先插入的先过期；测试里 `late` 先插入、晚过期，`early` 后插入、先过期，按插入顺序清理到 `late` 就停了，`early` 永远腾不出位置。过期的判断和 state 一致，`expires_at <= now` 就算过期。操作抛异常时 nonce 不能记下，这一点原代码就是对的，提速时不要改坏。

包含性也有几种过度修复：反复解码直到不再变化（`%252e%252e` 解码一次是名字叫 `%2e%2e` 的目录，解码两次才是 `..`）、拒绝所有带 `%` 的路径（`q3%20plan.md` 是合法笔记）、拒绝所有 `..`（`drafts/../q4-plan.md` 规范化以后仍在工作区里）、不再比较主机（`file://nas/...` 是另一台机器上的文件）。

## Part 2 SQLite 重放库

一个文件、两张表：`notes`（已经给出）和 `claims(nonce TEXT PRIMARY KEY, expires_at REAL NOT NULL)`。每个进程打开自己的 NoteDB，各用各的连接。

```python
def claim_and_delete(self, nonce, *, expires_at, note_id, workspace_uri):
    with self._db:                       # 一个事务：认领和删除一起提交，或者一起回滚
        self._claim(nonce, expires_at)   # 条件写，主键冲突就是“已消费”
        row = self._db.execute("SELECT uri FROM notes WHERE note_id = ?", (note_id,)).fetchone()
        if row is None:
            raise McpError(-32602, "selected note no longer exists")
        if not uri_within_workspace(workspace_uri, row[0]):
            raise McpError(-32602, "selected note is outside workspace")
        self._db.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
```

`_claim` 先用注入的时钟判断过期，再执行 `INSERT ... ON CONFLICT (nonce) DO NOTHING`，rowcount 不是 1 就抛“已消费”。INSERT 是这个事务的第一条写语句，执行时拿到写锁，之后的查和删都在同一个写事务里，别的进程插不进来。

要点：

- **条件写，不要先查再写**。测试用第三个连接 `BEGIN IMMEDIATE` 占住写锁，让两个重试都在查完、写之前排队，锁一放开，先查后写的实现要么撞上主键报 IntegrityError，要么（用了 `INSERT OR IGNORE`）两个都删了。捕获 IntegrityError 再转成 McpError，或者先 `BEGIN IMMEDIATE` 再查，也都对。
- **同一个事务**。删除前的检查失败时，`with` 回滚，认领也一起撤销，这条确认还能用来删别的候选。在 `claim_and_delete` 里调用自带 `with` 的 `claim()` 看起来更省事，但 Python sqlite3 的连接上下文管理器嵌套时内层一退出就 commit，认领就提前提交了。
- **先认领，再重查**。先 SELECT 笔记再 INSERT nonce 的话，SELECT 跑在拿到写锁之前（Python sqlite3 默认只在第一条写语句前 BEGIN），检查完到删除之间别的进程还能改这条笔记。测试里用一个已经用过的 nonce 去删已经不在的笔记，必须报“已消费”，先查笔记的写法会报“不存在”。
- **重查用 Part 1 的包含性检查**。SQL 的 `LIKE ws || '%'` 是字符串前缀，会把 notes-shared 当成在里面。
- **精度**。过期时间原样存成 REAL，读回来一模一样。存成整数秒的话，1000.5 变成 1000，在 1000 这一刻就被 prune 掉，可这条 state 还有半秒有效期，同一条确认就能再用一次。存成 TEXT，读回来是字符串，prune 的比较也变成字符串比较。
- **decline 也要提交**，另一个进程马上就要看到；过期的 state 什么都不写，decline 走的 `claim()` 也要查过期。
- **prune** 只删 `expires_at <= now` 的行。state 过期以后签名校验自己就会拒绝，这些行留着也没用了；还没过期的行一行都不能动。

## Part 3 破坏性删除表单

`offer` 用 `NoteBook.matching` 找出标题匹配、在工作区里的笔记，再用 `self.grants.allowed(principal, note.uri, "delete")` 过滤，按 NoteBook 顺序得到候选 id。没有候选就返回 `isError: true` 的 complete 结果，工作区外的同名笔记不会出现在任何地方。有候选就返回 input_required，里面是一个 form 模式的 `elicitation/create`：扁平 schema，note_id 是带 enum 的 string，confirm 是 boolean，两个都 required。`seal_state` 把 phase、candidateIds、`secrets.token_hex(16)` 生成的 nonce 和过期时间一起签进 requestState。

`resume` 的顺序是：

1. `open_state` 验签，检查 principal、参数和过期，再检查 phase。
2. 取出 `delete_choice`。cancel 直接返回 complete、deleted false，不碰 nonce。
3. decline 用一个空操作消费 nonce，返回 complete、非错误的拒绝结果。这是终局，同一个 state 再来 accept 会得到“已消费”，也不会再弹一次表单。
4. accept 先校验内容：content 是对象，note_id 是字符串且在签名的 candidateIds 里，confirm `is True`。`== True` 会放过 1，`if confirm:` 会放过 "true"。缺 content 不等于同意。这些错误都在认领之前抛出，不消费 nonce。
5. 在 `replay.claim_and_consume` 的操作里重查实时记录：笔记还在，还在工作区里，principal 还能删，然后删除。

候选集合必须从签过名的 state 里取。重试时重新搜索，表单展示之后才加进来的 note-15 就能被选中；不验签就解码 state，客户端可以往候选集合里加 note-99。删除要放在 claim 的操作里：先删再认领的话，认领失败时笔记已经没了。每次提示一个新的 nonce，拿参数摘要当 nonce，第二次用同样参数提示时，一开始就是“已消费”。

## Part 4 URL 模式带外流程

服务端 `ReportConnector` 已经写好，要补的是 `browser_callback`：

```python
flow = self.flows.get(flow_id)
if flow is None or flow.status != "pending" or browser_user != flow.principal:
    return False
flow.status = "completed"
self.connected.add(flow.principal)
return True
```

讲义说服务端必须把浏览器里的用户绑定到发起 MCP 操作的同一个 principal。不检查的话，mallory 在自己的浏览器里完成了 alice 的流程，alice 的 MCP 身份就连到了 mallory 的第三方账号。未知的流程返回 False，不要抛 KeyError；已经完成或已经 decline 的流程不能再完成。

客户端 `drive_url_elicitation` 是一个 async generator，主循环是：

- 服务端回 complete：输出 complete，停。
- 回 input_required：取出唯一的 URL 模式请求。这个 URL 还没问过，就先输出 show_url，再 `consent(url, message)`；用户 accept 才 `open_url(url)` 并输出 open。问过的 URL 不再问、不再开。
- accept：等下一个 tick，再用新的 id、最新的 requestState（测试每个 tick 把时钟往前拨，服务端每次签出的 state 都不同，回显第一次的会挂）和 `{key: {"action": "accept"}}` 重试，输出 retry。ticks 用完了就停（在 async generator 里让 StopAsyncIteration 冒出来，Python 会把它变成 RuntimeError）。
- decline 或 cancel：不等 tick，立刻带着原样的 action 重试一次，输出 retry 和 refused，停。
- 错误响应变成 McpError 抛出。

accept 只说明用户同意打开，外部流程完成之前服务端会一直回 input_required，所以要一直等 tick、一直重试，直到服务端自己说 complete。URL 和 message 原样交给 consent，不能只给域名，也不能去掉 query；开之前一定先问，并且不预取。每个动作发生时就 yield 一行，测试会数输出每一行时拉了几个 tick。URL 模式的回答里只有 action，第三方凭据从浏览器直接交给连接页面，永远不进 inputResponses。

服务端在客户端没声明 `elicitation.url` 时回 -32021，`requiredCapabilities` 是 `{"elicitation": {"url": {}}}`，和讲义里 form 模式的错误同一个形状。

## Part 5 嵌套工作区授权

先按主机分开，再把授权 URI 用 `file_uri_parts` 规范化，按路径分量挂到树上；每个节点记录“每个 principal 在这个工作区上的权限集合”。查询时同样规范化目标 URI，从根往下走，走到哪一层这个 principal 有授权，就记下那一层的集合，最后留下最深的那个：

```python
def _deciding(node, parts, principal, inherited):
    here = node.grants.get(principal, inherited)
    child = node.children.get(parts[0]) if parts else None
    return here if child is None else _deciding(child, parts[1:], principal, here)
```

根工作区 `file:///` 的授权挂在主机这一层的根节点上，同样参与比较；用 dirname 往上找、到 `/` 就停的写法会漏掉它。拿到集合以后：空集合（没有任何授权）拒绝；有 deny 拒绝；有 delete 读和删都允许；只有 read 只允许读。

几个容易写错的地方：最浅的授权不能管住一切；路径上方的 deny 不能盖住更具体的 delete（archive/keep）；“最深的、有授权的节点”要按 principal 算（q4 上只有 bob 的授权）；同一个工作区上的授权要合起来看，不能后写的覆盖先写的，测试会按正序和倒序各建一次树。授权 URI 和目标 URI 用同一套规范化，`%70rivate`、`./shared`、`%61rchive`、`archive%2F2019.md`、`%2e%2e` 都靠它。非法的授权和不认识的 action 报 ValueError，不悄悄跳过。

最后把 GrantTree 交给 NotesServer：`tools_call` 先确认 principal 能删工作区本身，`offer` 只列能删的笔记，`resume` 删除前再查一次。表单展示后多了一条 deny，删除就会被拒绝。

## 这套题证明了什么，没证明什么

通过了说明你能顺着一个多出来的候选找到两层之下的路径比较错误，知道编码穿越为什么要先解码再规范化；能把重放存储改成有界、按过期时间清理的结构；能用 SQLite 的条件写把 nonce 认领和删除放进同一个事务；能把 form 模式的确认、accept/decline/cancel 三个分支和删除前的重查写对；能写出先征得同意、再打开、再一直重试到服务端完成的 URL 模式客户端；也能实现按路径分量、最具体规则生效的嵌套授权。

它没有证明的：包含性检查是词法的，没有碰真实文件系统，符号链接、硬链接和检查与使用之间的竞态都没测，讲义的练习 4 要另外做；“两个进程”是用一个进程里的两个线程、两个连接模拟的，进程级的锁在这里也能通过，跨机器的部署要换成数据库或 Redis；requestState 的签名和字段绑定用的是现成的 `seal_state`/`open_state`，第 11 课专门考这部分；没有真实的浏览器、OAuth 和 HTTP 回调，URL 模式的完成是测试直接调用 `browser_callback` 模拟的。
