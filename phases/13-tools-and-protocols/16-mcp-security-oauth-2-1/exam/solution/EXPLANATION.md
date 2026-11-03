# 参考答案讲解：oauthflow（13/16）

计时结束后再看。参考实现在同目录的 `oauthflow/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修发现和授权码流程

**第一个错误**是 `HttpError: 404 for https://notes.example.com/.well-known/oauth-protected-resource`。URL 里没有 `/mcp`。`urljoin(resource, "/.well-known/oauth-protected-resource")` 的第二个参数是绝对路径，会把资源路径整个替换掉。RFC 9728 的写法是把 well-known 前缀插在主机和资源路径之间：

```python
parts = urlsplit(resource)
path = "" if parts.path == "/" else parts.path
return urlunsplit((parts.scheme, parts.netloc, RESOURCE_WELL_KNOWN + path, parts.query, ""))
```

讲义说，丢掉 `/mcp` 会拿到同一 origin 上另一个受保护资源的元数据。测试里的归档服务器 `/archive/mcp` 和笔记服务器同 origin，授权服务器却不同，正好是这种情况。

**第二个错误**是 `TokenError: invalid_grant: PKCE verification failed`，在第 6 步换 token 时才出现，报错的地方和出错的地方隔了好几层。顺着往回找：

- 假授权服务器的 `token()` 用 verifier 重新算一遍 S256，再和第 3 步收到的 `code_challenge` 比较。
- verifier 是客户端自己生成的，原样发了回去。所以有问题的只能是 challenge。
- `s256` 用了 `base64.urlsafe_b64encode`，却没去掉末尾的 `=`。SHA-256 摘要是 32 字节，base64url 编码后总是 43 个字符加一个 `=`。

RFC 7636 的 S256 是不带填充的 BASE64URL，补上 `.rstrip("=")` 就好。测试在第一次登录之后还用 RFC 7636 附录 B 的向量检查了一遍，这样标准 base64 字母表（`+` 和 `/`）的写法也过不了。

**第三处**是 `iss`。`check_response` 把两边都做了 `rstrip("/")` 和 `lower()` 再比较。讲义要求逐字比较：不做大小写折叠，不改尾斜杠，不去默认端口，不做百分号解码。测试用四个伪造值逐一覆盖这四种规范化，第五个伪造值是空字符串：它也算出现了，要拒绝。另外两条要注意：

- `iss` 出现了就要检查，即使服务器没有声明 `authorization_response_iss_parameter_supported`。测试会给归档服务器伪造一个 `iss`。
- `iss` 没出现时不能拒绝。归档服务器本来就不发 `iss`。

`check_response` 先确认 state，再查 `iss`，都通过了才去读 code。

**第四处**是性能。`McpClient.discovery` 每次调用都重新抓两份元数据，200 次调用就是 400 次网络往返。按资源缓存：

```python
found = self._discovered.get(resource)
if found is None:
    found = self._discovered[resource] = discover(self.net, resource)
return found
```

缓存键必须是完整的资源 URL，不能只用 origin。按 origin 缓存，`/archive/mcp` 会拿到 `/mcp` 的授权服务器，换来的 token 也给错了资源。token 本来就按 `(issuer, resource)` 存，这一点不用改。

## Part 2 按 issuer 隔离的凭据库

参考实现把整个 vault 存成一个 JSON 对象：

```json
{"clients": {"<issuer>": {...}},
 "tokens": {"<issuer>": {"<resource>": {...}}},
 "used_refresh_tokens": {"<issuer>": {"<resource>": ["<sha256>", ...]}}}
```

- **精确分键**：issuer 直接当 JSON 的键，不做任何规范化。`https://auth-one.example` 和 `https://auth-one.example/` 是两个 issuer，各有各的记录。token 嵌套两层，键就是 `(issuer, resource)`。资源换到新的 issuer 以后，按新 issuer 查什么也查不到，旧 issuer 的东西就不会被交出去。
- **原样读回**：用 `dataclasses.asdict` 存，读回时用 `ClientRecord(**data)` 和 `TokenRecord(**data)` 重建。scope 保持服务器给的字符串，`expires_at` 是 int，没有的值是 null。
- **权限从创建起就是 0600**：每次写都先用 `tempfile.mkstemp` 在同一目录建临时文件，它本来就以 0600 创建；写完 fsync，再 `os.replace` 换上去，替换后的文件保留 0600。先写再 chmod 有一个窗口，别的用户可以在这时打开文件并保留句柄，之后改权限也收不回这个句柄。测试把 `os.chmod` 换成了直接报错的函数。
- **轮换和重用**：
  - `rotate` 先看交上来的刷新 token 是否已经用过。为了不在文件里留明文，用过的值存的是 SHA-256 指纹。
  - 已经用过的，就是重用：删掉这个 `(issuer, resource)` 的记录，再抛 RefreshReuse。
  - 没用过、又不是当前值的，抛 ValueError。测试交的是另一个 issuer 那条记录的刷新 token，所以只能在这一个 `(issuer, resource)` 里找。
  - 服务器发了新的刷新 token，旧的记为已用；没发，或者原样发回同一个，当前这个继续有效。
  - 用过的指纹写在文件里，换一个进程重新打开也认得出重用。

## Part 3 增量授权与注册顺序

**解析挑战**用一个小的扫描器：跳过空白和逗号，读一个 token；后面紧跟 `=` 就是参数，否则是新挑战的 scheme。参数值以 `"` 开头时按 quoted-string 读，`\` 转义下一个字符，逗号和空格都是普通字符；否则读到空白或逗号为止。最后只返回 scheme 是 bearer（不分大小写）的那个挑战的参数。按逗号切、用正则找 `name="value"`，碰到测试里那个头都会出错：它前面有一个 Basic 挑战，realm 里有逗号和转义引号，`error` 没带引号。

**升级的 scope**是“已批准的”和“挑战要求的”的并集，排好序：

```python
" ".join(sorted(set(granted.split()) | set(challenged.split())))
```

已批准的要用 `TokenRecord.scope`，也就是服务器实际批下来的，不是自己请求过的。测试里服务器在请求 `notes:read` 时多给了 `notes:write`。挑战要求的 scope 不在 `scopes_supported` 里也照样请求，讲义说挑战对当前操作是权威的。

**call_with_step_up**只恢复一次：

- 403，而且是带 scope 的 `insufficient_scope` 挑战：用并集跑一次新流程，然后重试。用户拒绝时异常往外抛，原来的 token 留着，它对已批准的操作还有效。
- 401：token 已经不被接受。先把它删掉，再用它原来的 scope 跑新流程，然后重试。
- 其他情况，或者重试又失败了，原样抛 McpError。

**Registrar**照 docstring 的顺序：

1. 先看 vault 里有没有这个精确 issuer 的预注册客户端。
2. 再看服务器是否声明支持 CIMD。
3. 然后才是 DCR，而且要 `allow_dcr` 为真、元数据里有 `registration_endpoint`。以前注册过就复用，否则注册一次，按精确 issuer 存进 vault。
4. 都不行就抛 NeedClientInfo。

CIMD 排在 DCR 前面是每次都成立的：服务器后来支持了 CIMD，以前注册的 DCR 客户端也不再用。CIMD 被服务器拒绝时，`login` 把 AuthorizationError 原样抛出，不去走 DCR。讲义说，静默降级会把一次安全校验失败变成一条更弱的注册路径。

## Part 4 回环重定向与表单编码

`begin` 调用 Part 1 的 `client.start` 得到参数，用 `urlencode` 接在授权端点后面。端点本身带着 query 时，用 `&` 接在它后面。

`serve` 的骨架是同时等两类事情：“下一个重定向”和“所有还在进行的换 token 请求”。

```python
done, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
```

- 重定向到了，就同步处理，能立刻下结论的直接 yield：
  1. 先按 state `pop` 出流程，pop 在任何 await 之前，所以重复的回调只会落空。后面几步拒绝了这个重定向，流程也已经关了。
  2. 再看是否过期。
  3. 再逐字比较 `iss`。
  4. 再看是不是 error 重定向。
  5. 最后才用 code 建一个换 token 的任务。
- 换 token 任务完成，就 yield 它的结果。token 端点答复错误时结果是 denied，带服务器的 error 和 error_description，不交给 `client.store`。
- 来源结束以后，等剩下的任务都完成再结束。`finally` 里取消没完成的任务，调用方中途不读了也不会漏。

换 token 的请求体是 `urlencode(client.token_form(pending, code)).encode("ascii")`，Content-Type 是 `application/x-www-form-urlencoded`。授权码里有 `+`、`/`、`=`、`&`、`%`、空格，回调里收到的是百分号编码过的形式。`parse_qs` 解码一次，`urlencode` 再编码一次，正好原样还原。手拼 `k=v` 或者不解码直接转发，服务器拿到的就不是原来的码。

`iss` 不对时，结果里只有我们自己的 reason，不带响应里的任何东西。测试里那个伪造的重定向，`iss` 是客户端也在用的归档服务器，description 里藏着钓鱼链接。

## Part 5 重定向链与 SSRF 规则

`fetch_json` 是一个循环，每一跳都要做下面这些事：

1. 是不是访问过的 URL（环）。
2. 是不是 https，有没有主机名。
3. 当场解析主机名；IP 字面量不用解析。应答为空就拒绝，应答里每个地址都要通过 `public_address`。
4. 从总预算里算出剩下的时间，用刚检查过的地址连接（`connect_to`），超时转成 FetchBlocked。
5. 如果是重定向，检查次数，用 `urljoin` 相对当前这一跳的 URL 解析 Location，进入下一跳。

最后一跳要求：

- 状态码 200。
- 媒体类型是 `application/json`：取分号前的部分，转小写，精确比较。
- 正文一块一块读，超过 `max_bytes` 就停；正好 `max_bytes` 不算超。
- 内容是合法的 JSON，而且是对象；解析失败也转成 FetchBlocked。

`public_address` 用 `ip.is_global and not ip.is_multicast`。`is_private` 不包括 100.64.0.0/10 共享地址段；`is_global` 又把组播地址算成全局地址，两个都要处理。

`resolve_cimd`：

1. 先检查 client_id 本身是不是带路径的 https URL，不是就不发请求。
2. 抓到文档以后，文档里的 client_id 必须和最初那个 URL 逐字相等，经过重定向也一样。
3. 再检查 client_name 是非空字符串，redirect_uris 是非空的字符串列表。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着一个离根因很远的报错找到问题，能按讲义的规则做 issuer 和资源的隔离、写一个按时间到达的并发回调处理，也能把 SSRF 的每一条规则落到每一跳上。它不涉及资源服务器一侧的 token 校验（JWKS、受众、内省，在第 18 课），不涉及真实的浏览器、TLS、HTTP 库和系统钥匙串，也没有考加密存储和多进程并发刷新。讲义里的 `server/discover`、`tools/list` 和无状态请求的头部校验，也需要回到 `code/main.py` 另外跑。
