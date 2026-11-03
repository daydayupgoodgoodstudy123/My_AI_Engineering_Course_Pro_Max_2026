# 参考答案讲解：multipeer（13/08）

计时结束后再看。参考实现在同目录的 `multipeer/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修路由和响应关联

**现象**：解锁后的第一个失败是 `tools/call` 请求 `_meta` 里的版本：notes 收到的是 2026-07-28，测试要 2027-01-01。发请求的代码本身没有错。

**顺着往上找**：请求里的版本来自 `peer.selection.protocol_version`，它是 `discover()` 存下的，`discover()` 又调用 `modern_selection`，最后落到 `mutual_version`。docstring 说返回两边都有的最高版本，循环却返回对方列表里第一个双方都支持的版本。notes 按从旧到新列版本，于是拿到了最旧的那个。这一关想练的还是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `mutual_version`：先求交集，再取 `max`。版本是 YYYY-MM-DD 格式的日期字符串，字典序就是时间先后。
2. `call`：发给后端的是路由表里记的 `route.local_name`。规范名只给模型看，`notes/search` 对 notes 来说是不存在的工具。不要从规范名里截出本地名：网关 hub 的本地名 `notes/search` 本身就带 `/`，截掉最后一个 `/` 之前的部分只剩 `search`。
3. `_result`：peer 的 era 是 legacy 时，缺失的 `resultType` 补成 `"complete"`；现代结果缺这个字段仍然报错。本课原文是 "Clients must treat a missing resultType from a legacy server as complete"。
4. `PendingCalls`：改成以 `(type(id), id)` 为键的 dict，`add`、`resolve`、`drain` 都是 O(1) 或一次遍历。

**护栏**：常见的提速写法是 `self._waiting[request["id"]]`。Python 里 `True == 1` 而且 `hash(True) == hash(1)`，`1.0` 也一样，所以 id 为 true 的响应会领走请求 1。JSON 里 true 和 1 是两种类型，按 JSON-RPC 的关联规则不能匹配。键里带上类型（或者先用 `valid_id` 把 id 限定为 int 和 str）就没有这个问题。以 `str(id)` 为键会让 1 和 "1" 撞车；先 pop 再比较类型，会把真正的请求 1 弄丢。另一个护栏是 sloppy peer：去掉 `resultType` 检查，或者不分 era 一律补 `"complete"`，都会在那里挂掉。

## Part 2 固定 peer 配置

参考实现用 `configparser.ConfigParser(interpolation=None)`，每个 peer 一个 section，section 名就是 peer 名。

- **插值**：默认的 BasicInterpolation 把 `%` 当成插值语法。读到 `%PORT%` 时报 InterpolationSyntaxError，写 `50%` 时报 `invalid interpolation syntax`。关掉插值后，值都按字面处理。
- **argv**：写用 `shlex.join`，读用 `shlex.split`，引号、空格、空字符串参数都能原样往返。运维手写的文件也按 shell 的引用规则来写。
- **类型**：布尔值用 `getboolean`（认 yes/no、on/off、true/false），超时用 `getint` 并要求大于 0，`argv` 和 `legacy_revisions` 转成 tuple。dataclass 的相等比较会揪出任何类型差异。
- **只认固定的 peer**：`[DEFAULT]` 里的设置会被每个 section 继承，`allow_legacy = true` 放在那里，就等于本课说的通配符，所以整个拒绝。名字或端点里有 `*` 也拒绝。同名 section 默认抛 DuplicateSectionError，参考实现把 `configparser.Error` 统一转成 ValueError；`strict=False` 会把两段合并，让 allow_legacy 落到另一个命令上。
- **缺文件**：`ConfigParser.read()` 读不到文件不会报错，只返回空列表。参考实现先 `open` 再 `read_file`，路径写错时直接 FileNotFoundError。
- 协商出的 era 不写进配置。它只在一次传输的生命周期里有效，进程重启或端点变了就要重新协商。

## Part 3 era 协商

`negotiate` 就是本课 stdio 兼容探测的决策表：

| discover 的结果 | 动作 |
|---|---|
| DiscoverResult | 现代，取双方最高版本 |
| -32022 | 现代：从 `data.supported` 选最高共同版本，用新 id 重试一次；没有共同版本或重试失败就失败 |
| -32020、-32021 | 现代：失败，请求要先修正 |
| 超时、断开、空响应、其他错误码 | 含糊：不在 allowlist 上就失败；在的话做一次有界的 initialize 探测 |

legacy 探测只发一次 `initialize`：请求 `legacy_revisions[0]`，用 peer 自己的 `probe_timeout_ms`，请求里没有 `_meta`。然后按本课的五项检查验证：JSON-RPC 2.0 且 id 相同；有 result、没有 error；`protocolVersion` 在配置的修订集合里；`capabilities` 是对象；`serverInfo` 的 name 和 version 都是非空字符串。全部通过才发 `notifications/initialized`（通知，没有 id），返回 legacy 的 Selection。

实现时把“发一条请求、把超时、断开、空响应都当作沉默”写成一个小函数 `_ask`，返回 None 或者 `decode_response` 的结果，决策表的每一行就都很短了。几个容易错的地方：

- allowlist 只给探测的许可，不决定 era。收到 -32020/-32021/-32022 之后，peer 已经证明自己是现代的，再发 initialize 就是降级。
- -32601 不是 legacy 的证据。其他错误码也一样，测试用 -32602 检查这一点。
- 超时和断开要变成 ProtocolError（fail closed），不能让 TimeoutError 原样抛给调用方。
- 修订要和配置比，不能和内置常量 2025-11-25 比。
- `capabilities` 是对象就行，空对象 `{}` 也算；`serverInfo` 的 name 和 version 要检查类型，不能只看真值。

## Part 4 stdio 进程池

每个 peer 进程对应一个 `_Link`：进程本身、一张 PendingCalls、选中的版本、工具列表、是否存活，以及一个读取任务。

```python
request = modern_request(next(self.ids), method, params, version, self.capabilities)
link.pending.add(request, future)
link.process.stdin.write(json.dumps(request).encode("utf-8") + b"\n")
...
line = await link.process.stdout.readline()     # 读取任务
_, future = link.pending.resolve(json.loads(line))
future.set_result(message)
```

- 一行一个紧凑的 JSON 对象，以 `\n` 结尾，这是测试按 `split(b"\n")` 解析的格式。
- 响应由读取任务按 id 分给等待的 future，所以 files 倒序回答也没关系，一个 peer 不回答也挡不住别的 peer。
- 读到 `b""` 说明进程退出：标记失效，`drain()` 出所有在途请求，每个都设成 TransportLost。
- `call` 捕获 TransportLost：工具在运维给这个 peer 的 `retry_safe` 名单里（同名工具在另一个 peer 上安全不算数），就再调用 `_link` 一次（重启、server/discover、tools/list），然后用新 id 发一次；否则直接抛出。`readOnlyHint` 是服务器在 tools/list 里的自我描述，不能决定能不能重试。
- `_link` 用每个 peer 一把锁保护“检查存活、必要时重启”，同时到来的重试只会启动一个新进程。新进程的版本由新的 discover 决定，旧的 Selection 跟旧进程一起丢掉，所以重启后的请求带的是 2027-01-01。
- id 在整个池里递增，重试的请求绝不会和丢失的那次同号。

## Part 5 命名空间合并

按排序后的 peer 名逐个处理，peer 内部的工具也排序：

- 本地名不含 `/`、而且还没人用：拿裸名。
- 已经有人用：prefix-on-collision 下变成 `<peer>/<tool>`；reject-on-collision 下记下冲突（两个 peer 名都写上），最后一起报错。
- 本地名含 `/`（这个 peer 本身是网关）：无论哪种策略都加前缀。

peer 名不能含 `/`，同一个 peer 不能把一个名字列两次。这样规范名要么不含 `/`、就是本地名，要么在第一个 `/` 处拆成 peer 和本地名，两个工具不可能得到同一个规范名，也就谈不上覆盖。课里的代码把网关的 `notes/search` 当裸名，轮到 notes 的 `search` 加前缀时撞车，只能报 "canonical collision"，于是一个 server 就能让整个合并失败；要是写成直接赋值，就成了本课禁止的静默覆盖。

## 这套题证明了什么，没证明什么

通过了说明你能在多 peer 客户端的代码里顺着调用链调试，能用 configparser 做精确往返的配置并拒绝通配的授权，能按本课的决策表实现 fail closed 的 era 协商，能写出按 id 分发、崩溃后只安全重试的异步 stdio 客户端，能设计单射的命名空间合并。它没有涉及真实的子进程和 Streamable HTTP 传输（第 09 课），没有涉及 `subscriptions/listen`、按 `cacheScope` 和授权上下文缓存工具列表（本课练习 3 和练习 5），也没有涉及 `input_required` 之后的重试（第 11 课）。这些需要另外动手。
