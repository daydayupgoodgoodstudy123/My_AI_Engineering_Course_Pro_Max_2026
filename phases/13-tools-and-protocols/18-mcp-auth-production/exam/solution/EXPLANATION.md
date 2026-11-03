# 参考答案讲解：tokengate（13/18）

计时结束后再看。参考实现在同目录的 `tokengate/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 JWKS 缓存和受众检查

**现象**：解锁后的第一个错误是 `refresh_jwks` 里的 `KeyError: 'https://stranger.example.net'`，而 `refresh_jwks` 本身没有错。

**顺着往上找**：`refresh_jwks` 被要求去抓一个这台服务器根本连不上的签发者的 JWKS。是 `validate` 把 token 里的 `iss` 原样交给了它，中间没有和受保护资源元数据的 `authorization_servers` 比较。连得上的 lab 签发者更危险：它签的 token 会被验签通过、被接受。讲义 Failure modes 里叫 "iss not pinned"：攻击者自己搭一个授权服务器就能签 token。这一关想练的是：报错的位置往往不是出 bug 的位置，在 `refresh_jwks` 里把 KeyError 吞掉只会把症状藏起来。

**依次修四处**：

1. `validate` 在抓任何东西之前先查 `iss`：必须是字符串，而且在 `prm.authorization_servers` 里，否则 401 `iss not allowed`。
2. `aud` 去掉默认值。`claims.get("aud", self.prm.resource)` 把缺 `aud` 的 token 当成发给本服务器的，正是讲义说的 "treat absence as wildcard"。比较要精确：`/notes/admin` 是同一个 origin 上另一个 MCP 服务器，`/notes/` 也不是同一个 canonical URI。
3. `refresh_jwks` 把条目写在 `jwks_uri` 下面，`validate` 按 issuer 读，于是缓存永远不命中，每个请求都抓一次 JWKS。假抓取每次 5 ms，200 次验证约 1.2 秒；改成 `self.jwks_cache[issuer] = entry` 后只要 2 到 3 毫秒。
4. 缓存没命中时，起始代码调用 `self.idps[issuer].rotate_key()`，再看一遍旧条目。资源服务器不持有授权服务器的私钥，它能做的只有 refresh。rotate 造出来的新 kid 和 token 的 kid 对不上，所以新钥匙签的 token 永远找不到；每个随机 kid 还会让授权服务器多造一把钥匙。改成 `entry = self.refresh_jwks(issuer)`，然后再查一次。

**护栏**：

- 新钥匙签的 token 一次刷新后必须通过，旧钥匙在重叠期内照样能用，而且不再抓取。把 JWKS 永久缓存、或者改成“缓存超过五分钟才刷新”，都会在这里挂掉。
- 随机 kid 每个最多抓一次，只刷新这个 token 自己的签发者，授权服务器的钥匙数不变；partners 换钥匙以后，它的新 token 也要能刷新到。“刷新三次直到找到”“先 rotate 再 refresh”“刷新所有签发者”“永远刷新第一个签发者”（本课测验 Q9 指出的讲义代码问题）都过不去。
- 刷新是替换：授权服务器退役 k1 之后，下一次定时刷新就让它失效。把新旧钥匙合并的写法会让退役的钥匙一直有效。
- 两个签发者都有 kid `k1`，缓存必须按签发者分开；`fetched_at` 要记下这次抓取的时间，Part 3 的陈旧窗口靠它。
- 白名单是第一道检查：未列入的签发者发来 kid 不是字符串的 token，报的也是 `iss not allowed`。白名单加在起始代码的 kid 检查后面就不对。

## Part 2 内省缓存

参考实现一张表，主键是 `(issuer, token_sha256, resource)`，响应整个存成 JSON 文本，`expires_at` 用 REAL：

```sql
CREATE TABLE IF NOT EXISTS introspection (
    issuer TEXT NOT NULL,
    token_sha256 TEXT NOT NULL,
    resource TEXT NOT NULL,
    response TEXT NOT NULL,
    expires_at REAL NOT NULL,
    PRIMARY KEY (issuer, token_sha256, resource)
)
```

几个要点：

- **不存 token**：键里放 `sha256(token.encode()).hexdigest()`。讲义说 "Never use the clear token as a log or cache label"，“前 8 位方便排查”也不行。测试扫描每一列，还读整个数据库文件。
- **三个分量都在键里**：同一个 token 字符串，对另一个资源或另一个签发者的结果不能拿来用。
- **正向条目**取 `exp`、`now + max_age`、`now + revocation_window` 三者最早的那个；否定条目只活 `negative_ttl` 秒，免得新签发的 token 被当成 inactive 太久；算出来已经过期的不存。判断要写成 `max_age is not None` 和 `response.get("active") is True`：max_age 0 表示签发者不许复用，`"active": "false"` 这样的字符串不是正向结果。
- **原样往返**：JSON 文本能保住整数、布尔、浮点、未知字段和 scope 的顺序。测试比较的是 sort_keys 的 JSON 文本，所以 `1700000600` 变成 `1700000600.0`、`true` 变成 `1` 都会被发现，dict 的 `==` 是发现不了的。
- **替换**：`INSERT OR REPLACE` 配主键，同一个键再存一次就替换。这里替换正是想要的行为，不涉及行号。
- **连接是 autocommit**（题目给的），每条语句自己提交，两个副本马上能看到对方写的东西。
- **lookup** 是读穿缓存：活着的条目直接返回（否定的也算，垃圾 token 不会一直去打授权服务器），命中时不再存一遍，否则过期时间会随读取往后推；没有就调一次 `introspect()`，带着 max_age 存下来；`introspect()` 抛异常就原样抛出，什么都不存。把失败存成 inactive，会把一次运维故障变成持续几秒的授权拒绝。

## Part 3 验证方式和依赖故障

`check` 按 docstring 的顺序走：

1. 时钟先读出来，必须是有限的数，否则 `Outcome.error("clock unavailable")`。NaN 和什么比都是 False，`exp <= now` 永远不成立，不查的话过期 token 全部放行。无穷大也读不出时间，所以用 `math.isfinite`，不只是 `math.isnan`。这一步对 opaque token 也要做。
2. 解析不出 JWT 的就是 opaque token，交给 `opaque_issuer` 内省。
3. JWT 按 `iss` 找签发者配置。iss 必须是字符串，否则拿列表去查 dict 会报 unhashable。**配置决定走哪条路**：partners 配的是内省，它发的 JWT 也要内省；被撤销的 JWT 在本地验签是能通过的。
4. 内省：`self.introspection.lookup(...)`，带上配置里的 `cache_max_age`。`Unavailable` 是运维错误：既不是 active（失败放行），也不是 inactive（那是授权拒绝）。然后逐项查 active、类型、aud（缺 aud 和 JWT 路径一样要拒绝）、exp、scope（按空格拆开比较，不做子串匹配）。partners 的时钟慢 90 秒，它说 active 的 token 在我们这里已经过期；要用自己的时钟判断，而不是放宽 skew。
5. JWT：先查 alg 在这个签发者配置的算法里（`none` 在抓 JWKS 之前就拒绝；不能写死 HS256），再查类型（`type(exp) is int`，因为 `isinstance(True, int)` 为真）。然后看缓存的年龄：超过 `refresh_interval + stale_window` 是 503 `jwks stale`（陈旧窗口从错过的那次刷新算起，不是从抓取算起）；否则交给 Part 1 的 `validate`，里面那次刷新抛出 `Unavailable` 就是 503 `jwks unavailable`。最后按 `validate` 之后的缓存年龄决定 health：超过 `refresh_interval` 是 degraded，`validate` 里刷新成功了就是 ok。

这正好是讲义的故障表：

| 情况 | 结果 |
|---|---|
| 定时刷新失败，已知 kid 还在陈旧窗口内 | allow，health degraded，不再去问挂掉的授权服务器 |
| 未知 kid，唯一一次刷新失败 | error 503 `jwks unavailable` |
| 超过陈旧窗口 | error 503 `jwks stale` |
| 内省不可用 | error 503 `introspection unavailable`；缓存里还活着的结果照样能用 |
| 时钟或 claim 类型不对 | 时钟是 error 503，claim 是 refuse 401 `malformed` |

两类结果分开：运维错误是 503，没有 `WWW-Authenticate`（凭证根本没被判断过）；授权拒绝是 401 或 403，带 `error`、`resource_metadata`，403 还带要申请的 `scope`。

## Part 4 事件回放和 CSV

```python
yield _record(COLUMNS)
async for event in events:
    clock.now = event["t_ms"] / 1000
    if event["type"] == "refresh":
        try:
            gate.server.refresh_jwks(event["issuer"])
        except Unavailable:
            pass
    elif event["type"] == "request":
        outcome = gate.check(event["token"], event["scope"])
        yield _record((event["t_ms"], _kid(event["token"]), outcome.decision, outcome.reason, outcome.health))
    else:
        raise ValueError(...)
```

- **CSV 用 csv 模块写**。kid 是攻击者能控制的。测试里的 kid 是 `k2",allow,ok,ok\n0,k2`，手工用逗号拼接时，日志里会多出一条伪造的 allow 记录。csv 模块会加引号、把引号写成两个、把换行留在引号里，读回来还是原样的 kid。讲义说证据要记录是什么驱动了判定，kid 就是其中之一，所以要原样记，不能“清洗”。
- **一判定就输出**：探针显示第一行出来时只拉取了一个事件。
- **先设时钟再处理**，定时刷新也一样，否则 `fetched_at` 记错，后面的 health 跟着错。用 `/` 不用 `//`：不足一秒的部分会影响内省缓存什么时候过期。
- **定时刷新失败**不让回放停下，也不写行；health 列会显示出来。刷新事件只刷新它指定的那个签发者。
- 时间线把整个课讲到的东西串了起来：授权服务器轮换以后，新旧 token 都能通过；退役的钥匙在下一次定时刷新后失效；授权服务器宕机时先是 degraded，过了陈旧窗口变成 `jwks stale`；恢复后回到 ok；opaque token 在授权服务器那边被撤销（RFC 7009）后，缓存里的结果最多再用 60 秒，之后被拒绝。这就是讲义说的 "Revocation is a freshness contract"。

## Part 5 DCR 重定向 URI

参考实现自己拆 URI，不依赖 `urlsplit` 在不同版本上的宽松行为：

1. 先查原字符串：必须是 str，不能有空白、控制字符和 DEL。`urlsplit` 会悄悄删掉制表符和换行，还会去掉开头的空格，所以要在解析之前查。`str.isprintable()` 不够，普通空格是可打印的。
2. 不能有 `#`。`parsed.fragment` 对 `cb#` 是空串，用真值判断会漏掉。
3. scheme 按 RFC 3986 必须字母开头，比较时转小写。
4. 有 authority 就检查（authority 在 `/`、`?` 或 `#` 处结束，`http://127.0.0.1:7333?flow=desktop` 没有路径）：不能有 `@`（`http://@host` 的 `parsed.username` 是空串）；端口必须是 1 到 5 位 ASCII 数字、不超过 65535（`host:` 的 `parsed.port` 是 None；`str.isdigit()` 和 `\d` 会接受阿拉伯-印度数字）；方括号要闭合，里面是 IPv6 主机。
5. web 只要 https 加非空主机；native 还可以用主机名正好是 localhost、127.0.0.1 或 ::1 的 http，或者由至少两段组成的私有 scheme，每段字母数字开头结尾，中间可以有连字符。

`registration_error` 先查 `application_type`：DCR 必须声明 native 或 web，没有默认值（OpenID Connect 注册里默认 web 的规则在这里不适用）。然后 `redirect_uris` 必须是非空列表，每一个都要合规。

## 这套题证明了什么，没证明什么

通过了说明你能在资源服务器这一侧把讲义的生产规则落到代码里：按白名单信任签发者，精确比较受众，让 JWKS 缓存在轮换中只刷新、不轮换，把内省结果按摘要缓存、受撤销窗口约束，按配置固定验证方式，把每一种依赖故障都归到声明好的结果里，把判定原样记成可解析的证据，以及按 native 和 web 的规则检查重定向 URI。

它没有考客户端那一侧：CIMD、预注册和 DCR 的选择顺序，RFC 9207 的 `iss` 校验，PKCE，按签发者隔离的凭据。本课讲义讲了这些，要练需要另外动手。它也不涉及真正的非对称签名（这里用 HS256 和 oct 钥匙，生产上 JWKS 只放公钥）、HTTP 传输和负载均衡后面的多副本。讲义要求撤销承诺“通过负载均衡测”，这一步要在真实部署上另外做。
