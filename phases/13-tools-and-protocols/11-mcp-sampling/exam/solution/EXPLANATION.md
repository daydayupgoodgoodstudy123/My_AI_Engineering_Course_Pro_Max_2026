# 参考答案讲解：mrtrkit（13/11）

计时结束后再看。参考实现在同目录的 `mrtrkit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 MRTR 两轮

**现象**：第一轮正常返回 `input_required`，原样重试却得到 `-32602 requestState arguments mismatch`，而参数一个字都没改。

**顺着往上找**：报错在 `verify` 里，比较的是状态里存的 `binding` 和这次请求算出来的 `_binding(params)`。把两次的 `canonical(params)` 打印出来就能看到：重试的 params 多了 `inputResponses` 和 `requestState`。`_binding` 的 docstring 说只绑定工具名和参数，代码却把整个 params 都算了进去，所以两轮的摘要永远不同。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修五处**：

1. `_binding` 只摘要 `{"name": ..., "arguments": ...}`，仍然用 `canonical` 排序键，键的顺序不影响结果。
2. `_caller` 返回传输层认证过的 `principal`。原代码优先用 `clientInfo.name`，而课里说得很清楚：clientInfo 和 serverInfo 只是展示和诊断用的元数据，不能当身份。user-7 用同一个客户端，就能接着用 user-42 的 requestState。
3. `_offered` 只认第 1 轮列给模型的名字：

   ```python
   offered = set(self.listing())
   picked: list[str] = []
   for name in picks:
       if name in offered and name not in picked:
           picked.append(name)
   return picked[:3]
   ```

   原代码只问“这个路径是不是文件”，`../secrets.txt` 和绝对路径（`Path(repo) / "/abs"` 会丢掉 repo）都能读到仓库外面。只过滤 `..` 挡不住绝对路径；`resolve()` 以后检查在仓库内，也会放过 `docs/../server.py` 这种列表里没有的写法；只跳过带 `..` 的名字和绝对路径，会放过 `./LICENSE`。白名单最简单，也最贴近课里的要求：模型输出当文件名用之前先校验。
4. 去重要在截断之前做，并保持模型给的顺序。用 `set` 去重会打乱顺序，先截到三个再去重会少选。
5. 密钥在 `__init__` 里派生一次。PBKDF2 跑 600,000 次迭代约 45 ms，原代码在每次 `seal` 和 `verify` 里都派生，24 次重试就要 1 秒多。

**护栏**：

- 测试按 PBKDF2(secret, `KDF_SALT`, 600000) 自己算一遍签名。调小迭代次数，或者给每个副本随机生成密钥，都过不了。随机密钥还违背了“任何知道口令的副本都能接着处理”；反过来，口令不同的服务器必须拒绝，所以密钥要跟着实例或口令走，不能缓存在类上。
- 改了 arguments 的重试必须被拒，所以不能靠删掉绑定检查来让第 1 个缺陷消失。
- 想靠缓存验证结果提速，会跳过过期检查。测试把时钟拨到 expiresAt 那一秒（仍有效），再拨一秒（必须拒绝）。只按 token 缓存的话，连参数和主体检查都跳过了。

## Part 2 版本化签名令牌

参考实现：

```python
HEADER = struct.Struct(">BBQI")   # version, key id, expiresAt, payload length
payload = json.dumps(state, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
body = HEADER.pack(VERSION, keyring.current, expires_at, len(payload)) + payload
mac = hmac.new(keyring.keys[keyring.current], body, hashlib.sha256).digest()
token = base64.urlsafe_b64encode(body + mac).decode("ascii").rstrip("=")
```

`open_state` 按这个顺序检查：只允许 base64url 字母表里的字符（`urlsafe_b64decode` 自己不查，带 `+`、`/` 的标准 base64 写法它照样解码）；补回 `=` 后解码（`binascii.Error` 是 ValueError 的子类，一起转成 StateError）；长度至少是头部加 MAC；版本必须是 1；密钥 id 必须在 ring 里；总长度必须正好是头部长度加负载长度加 32；用这把密钥重算 HMAC，`hmac.compare_digest` 比较；最后才看过期，`now > expiresAt` 才算过期。

容易错的几处：

- **长度按字节**。`ensure_ascii=False` 以后，`"设计"` 是 6 个字节、2 个字符。按 `len(str)` 写长度，自己封的令牌自己都打不开。
- **canonical 不能直接复用**。`protocol.canonical` 用的是默认的 `ensure_ascii=True`，会把非 ASCII 写成 `\u8bbe` 这样的转义，和这里约定的格式不同。`allow_nan=False` 会查遍整个结构，只在顶层手工查 NaN 会放过嵌套列表里的 `inf`。
- **HMAC 覆盖头部**。只签负载，攻击者就能改过期时间或者密钥 id 而不被发现。测试把每个字节的最低位和最高位各翻一次，都必须被拒。
- **错误类型**。短输入直接交给 `struct.unpack_from` 会抛 struct.error，未知密钥 id 用 `keys[key_id]` 会抛 KeyError。调用方只接 StateError；漏出别的异常，服务器就没法把它当成一个普通的坏令牌，回 -32602。
- **轮换**。新令牌用 `current` 签，ring 里还有更早的密钥（2）和预先下发、准备下一次轮换用的密钥（9）。用 id 最大的那把去签，或者打开时总用 `current`，都会错。
- **精确往返**。JSON 能原样还原 Python 的 float（包括 `0.1 + 0.2` 和次正规数）、大整数和 `-0.0`，前提是不经过别的格式。测试用 `exact()` 比较，`2` 和 `2.0` 不算相等。

## Part 3 客户端 MRTR 驱动

拆成三个函数：

- `screen`：方法闸门（只有 tools/call、prompts/get、resources/read 可以要输入）、轮数上限、每个输入请求的能力和 includeContext。能力看的是这次请求 `_meta` 里自己声明的 `clientCapabilities`；`FULFILS` 里没有的方法（比如 elicitation/create）一律拒绝。includeContext 缺省就是 `"none"`。
- `retry_request`：`{**params, "inputResponses": answers, "requestState": state}`，新建一个字典，调用方的 params 不动。
- `drive`：

  ```python
  round_no += 1
  requests = screen(method, params, result, round_no, max_rounds)
  for key, request in requests.items():
      if not approve(key, request):
          raise HostError("denied", key)
  answers = {key: model(request["params"]) for key, request in requests.items()}
  response = send(retry_request(next(ids), method, params, answers, result["requestState"]))
  ```

顺序是这一关的核心：先整轮检查，再整轮审批，最后才调模型。任何一步拒绝，模型都没有被调用，也没有花钱。轮数上限在审批之前，第 4 个 input_required 直接停，模型只被调用 3 轮。上限数的是轮，不是输入请求：一轮有两个请求也只算一轮。

screen 对一轮里的每个请求都要检查，测试里要上下文的、主机不认识的，都放在第二个请求上。几个常见的错：用第一轮的 id 或第一轮的 requestState 重试；把上一轮的答案也带上；把 requestState strip 或者当 JSON 解析后重新序列化（测试故意给了一个长得像 JSON、末尾还有空格的 state）；把 modelPreferences 归一化。课里说这三个优先级互相独立，不是概率分布，客户端可以忽略，但不该改了再交给模型。

## Part 4 并发审批与预算

参考实现是一个事件驱动的 async generator，不开后台任务：

1. 先输出表头，再给每个交互发第一个请求，把各自要问的那一轮登记到 `waiting[(名字, 轮次)]`。
2. 逐个读审批。对应的轮次在等，就当场决定；还没轮到，就存进 `early`。
3. 决定一轮：拒绝写 denied；预算不够写 over_budget；否则扣预算、写 approved，然后调模型、发重试，把下一轮登记进 `waiting`。如果下一轮的审批早就到了（在 `early` 里），接着决定它。
4. `waiting` 空了就结束，不再读审批；审批流结束时，还在等的轮次全部 denied。

```python
cost = round_cost(requests)
have = left.get(it.principal, Budget(0, 0))
if not approved:
    yield _row(..., "denied", 0); return
if cost.tokens > have.tokens or cost.bytes > have.bytes:
    yield _row(..., "over_budget", 0); return
left[it.principal] = Budget(have.tokens - cost.tokens, have.bytes - cost.bytes)
yield _row(..., "approved", cost.tokens)
```

用任务、future 和队列也能写对（一个交互一个任务，一个分发审批的任务，主生成器从队列里取行）。不管哪种写法，要点都一样：

- 预算按 principal 记，同一个用户的所有交互共用；一轮在被批准时扣，字节和 token 都扣。
- 先看决定再看预算：没被批准的轮次记 denied，不管预算还剩多少。
- id 来自同一个 `ids`，request_id 写的是提出这一轮的那个请求。
- 每行都用 `csv.writer` 写，交互名里的逗号和引号才会被正确转义；一个 chunk 一条记录。
- 行在决定时就 yield 出去。测试里的“用户”看到前面的行才给下一个审批，所以攒到最后、按顺序一个交互一个交互地跑、丢掉提前到的审批，都会卡住，3 秒后报 `the run stalled`。
- 日志只写方法、输入键、决定和花费，不写 prompt。课里的要求是记录发起的方法和输入请求的键，但不记敏感的 prompt 内容。

## Part 5 阶段图

`plan` 用带记忆的深度优先搜索同时做环检测和最长路径：

```python
def longest(name):
    if name == DONE:
        return 0
    if name in on_path:
        raise ValueError(...)          # back on the current path: a cycle
    if name not in rounds_from:
        on_path.add(name)
        rounds_from[name] = 1 + max(longest(t) for t in phases[name].then.values())
        on_path.discard(name)
    return rounds_from[name]
```

`on_path` 只记当前这条路径，`rounds_from` 记已经算完的阶段。只用一个集合的话，菱形（两条路径汇到 summarize）会被误判成环。DIAMOND 有 4 个阶段，一次运行只经过 3 个，所以轮数也不能拿阶段个数凑。搜索结束后，`rounds_from` 里没有的阶段就是从起点到不了的。不能用“没有阶段指向它”代替：一个只指向自己的旧阶段有入边，却从起点走不到。返回值是最长的一次运行要几轮，超过 `max_rounds` 就拒绝，让流程和主机的轮数上限对得上（课里练习 3：整个流程最多三轮）。广度优先的层数给的是 3，不是 4。

`advance` 只信服务器刚验证过的状态：

- 阶段从 `state["phase"]` 取，不认识就是 -32602；
- `set(responses) == {phase.ask}`，多一个、少一个都是 -32602；
- `handle` 拿到的是之前各轮校验过的 `data`，返回 `(value, outcome)`；记下的是 value，不是原始文本；
- outcome 不在 `then` 里，是服务器自己的流程写错了，和 `plan` 一样抛 ValueError；
- 下一轮 `round + 1`，到 DONE 时轮数不变；`data` 用 `{**state["data"], phase: value}` 新建，传进来的状态不改。

无状态服务器分不出“重放上一轮的 requestState”和“网络重试”。它能挡住的是陈旧的 requestState 配上新一轮的答案：键对不上。真正的一次性消费需要服务器记住用过的 nonce，那是第 12 课的内容。

## 这套题证明了什么，没证明什么

通过了说明你能在 MRTR 服务器里顺着调用链找到绑定和身份的错误，知道模型输出当文件名之前要走白名单，能设计并精确实现一个带版本和密钥 id 的签名令牌，能写出把客户端当信任边界的驱动循环，能在 asyncio 里让多个交互共享预算、按决定顺序流式输出 CSV，也能检查并运行一个阶段图。

它不涉及真实的模型调用、真实的传输层认证和密钥管理，也不涉及认证加密（AEAD）、一次性 nonce 存储（第 12 课）、Tasks 扩展（第 13 课），以及课里推荐的另一条路：新服务器直接集成模型提供方。把 Sampling 换成服务端模型适配器（课里练习 4），需要另外动手做。
