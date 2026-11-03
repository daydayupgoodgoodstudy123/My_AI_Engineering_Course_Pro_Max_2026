# 测验 · MCP 模型输入：Sampling 迁移与无状态 MRTR（MCP Model Input: Sampling Migration and Stateless MRTR）

> **阶段 13 · 工具与协议 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义为机器翻译，部分句子有缺漏（例如"model preferences 不需要加和为 1"一句），以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Sampling 已被弃用 | 2026-07-28 修订中 Sampling 对新设计是 deprecated，并且移除了"服务端向客户端发请求"的通道；新服务端默认**直接集成模型提供方** |
| 2 | 两种架构选择 | 直接集成：服务端拥有模型选择、凭据、预算、重试、可观测性；兼容迁移：仅当"必须用客户端的模型与凭据"是真实产品需求时才用 MRTR 承载 Sampling，并写好移除计划 |
| 3 | MRTR（Multi Round-Trip Requests） | 服务端不能在处理请求时回调客户端，而是返回 `resultType: "input_required"`，把 `sampling/createMessage` 嵌在 `inputRequests` 里；客户端完成后**用新的 JSON-RPC id 重试原方法** |
| 4 | 重试契约 | 重复原方法和原参数，只附上**本轮**的 `inputResponses`，并**逐字节回显** `requestState`；它是新请求，不是会话延续 |
| 5 | MRTR 适用方法 | 只允许出现在 `tools/call`、`prompts/get`、`resources/read` 上 |
| 6 | `requestState` 的保护 | 视为攻击者可控；用 HMAC（或需要保密时用认证加密）绑定**已认证主体、原方法、参数摘要、短期过期时间、当前阶段与已验证的中间值**；任一不符返回 `-32602` |
| 7 | 错误码 | 版本缺失/非字符串 `-32602`；版本不支持 `-32022`（`data` 含 `supported`、`requested`）；缺少 sampling 能力 `-32021`（`data.requiredCapabilities = {"sampling": {}}`） |
| 8 | 模型偏好只是提示 | `costPriority`、`speedPriority`、`intelligencePriority` 相互独立，不是概率分布，不需要加和为 1；客户端拥有模型策略，可以忽略；`includeContext` 保持 `"none"` |
| 9 | 客户端是信任边界 | 需要时向用户展示请求并审批；**限制 MRTR 轮数**防止恶意服务端制造模型花费循环；校验每个 sampling 响应；限制字节与 token；模型输出不进入授权决策 |
| 10 | 通知与发现 | 无 `id` 的信封是通知，不回任何响应（HTTP 上返回 `202` 无 body）；广告了 `tools` 就必须实现 `tools/list`，其描述符要确定、可缓存 |

### 核心技能（能动手做到）

- [ ] 判断一个需要 LLM 的 MCP 工具应该"直接集成模型"还是"用 MRTR 兼容 Sampling"，并说出理由与移除计划
- [ ] 画出 `summarize_repo` 的三次请求（id 1→2→3）与两轮 `input_required` 的消息序列
- [ ] 读懂 `seal_request_state` / `verify_request_state`：token 格式、签名、五项绑定检查的顺序
- [ ] 指出代码中 `requestState` 可重放、`picked` 可重复、客户端驱动没有轮数上限等简化
- [ ] 跑通 `main.py` 与 13 个单元测试，并完成讲义练习 1、2、5（非法 JSON、改参数、过期）
- [ ] 说出把 Sampling 换成服务端模型适配器后，审批、计费、可观测性责任如何转移

---

## 二、基础自测（选择题）

**Q1.** 讲义认为，一个**新建**的 MCP 服务端需要 LLM 推理（如总结仓库）时，默认应该：

- A. 用 2025-11-25 的会话式 `sampling/createMessage`，在连接上直接回调客户端
- B. 每次都返回 `input_required`，让客户端模型完成全部推理
- C. 直接集成模型提供方，由服务端负责模型选择、凭据、预算、重试与可观测性
- D. 让客户端在 `clientInfo` 里声明使用哪个模型

**Q2.** 第一轮返回 `input_required` 后，客户端发起的重试请求必须满足：

- A. 新的 JSON-RPC id、相同的方法与原参数、本轮的 `inputResponses`、逐字节回显的 `requestState`
- B. 与第一次请求相同的 JSON-RPC id，表示同一会话
- C. 解析 `requestState`，把其中的 `phase` 改成下一阶段后再发回
- D. 只发送 `inputResponses`，原参数可以省略，因为服务端已经记住了

**Q3.** 在本节代码中，客户端的 `clientCapabilities` 为 `{}`（未声明 sampling）时调用 `summarize_repo`，返回：

- A. `input_required`，但 `inputRequests` 为空
- B. `-32602 missing client capabilities`
- C. `-32022 unsupported protocol version`
- D. `-32021`，`data` 为 `{"requiredCapabilities": {"sampling": {}}}`

**Q4.** 关于 `modelPreferences` 中的 `costPriority`、`intelligencePriority`，下列说法正确的是：

- A. 它们是概率分布，必须加和为 1，否则客户端会拒绝
- B. 它们是相互独立的提示，不需要加和为 1，客户端可以忽略
- C. 服务端通过它们强制指定客户端使用的模型
- D. `intelligencePriority` 越高，`maxTokens` 自动越大

**Q5.** 下列哪个方法**不允许**返回 `resultType: "input_required"`？

- A. `tools/call`
- B. `prompts/get`
- C. `resources/read`
- D. `tools/list`

**Q6.** `verify_request_state` 依次检查：编码、HMAC 签名、principal、method、参数摘要、过期时间。客户端在重试时把 `arguments` 从 `{"audience": "developer"}` 改成 `{"audience": "executive"}`，但 `requestState` 原样回显。结果是：

- A. `-32602 requestState arguments mismatch`，因为签名体中的 `argumentsDigest` 与新参数的 SHA-256 摘要不符
- B. 成功，因为 HMAC 签名没有被修改
- C. `-32602 requestState integrity check failed`
- D. 成功，并按 executive 受众重新生成摘要

**Q7.** 本节 `requestState` 用的是 HMAC-SHA256 签名、body 只做 base64url 编码。讲义对此的评价是：

- A. HMAC 同时提供完整性和保密性，客户端无法读出状态内容
- B. HMAC 只保证完整性；如果客户端不应读到状态内容，应改用认证加密（authenticated encryption）
- C. 状态在客户端，所以根本不需要签名
- D. 应该把签名密钥一并放进 `requestState`，便于其他实例验证

**Q8.** 运行 `main.py` 打印 `independent request ids: [1, 2, 3]`。它说明了什么？

- A. 服务端为同一个会话分配了三个子会话
- B. 第 2、3 次请求是第 1 次请求的流式分片
- C. 每一轮 MRTR 都是一个独立的完整请求：两轮 `input_required` 加最终 `complete`，共三次请求、三个不同 id
- D. 客户端失败重试了两次

---

## 三、动手 / 代码题

**Q9.** `requestState` 的 token 由 `seal_request_state` 生成：

```python
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def seal_request_state(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(SERVER_SECRET, body, hashlib.sha256).digest()
    return f"{_b64(body)}.{_b64(signature)}"
```

1. 签名部分（点号之后）有多少个字符？为什么？
2. 第一轮 state 的 body 解码后是什么样子？客户端能不能读到？能不能改？
3. 为什么 `json.dumps` 要加 `sort_keys=True, separators=(",", ":")`？`_arguments_digest({"b":1,"a":2})` 与 `_arguments_digest({"a":2,"b":1})` 相等吗？
4. `verify_request_state` 用 `hmac.compare_digest` 而不是 `==`，原因是什么？

**Q10.** 在第一轮拿到 `requestState` 后，分别用以下 `pick_files` 文本重试，结果各是什么？（请先推理，再对照答案。）

```text
(a) not json
(b) {"a": 1}
(c) ["../../etc/passwd"]
(d) ["README.md", "README.md", "README.md"]
(e) ["LICENSE", "server.py", "client.py", "README.md"]
```

其中哪一个暴露了代码的一个小缺陷？如何修？

**Q11.** 下面是客户端驱动 `run_mrtr` 的核心循环：

```python
    while response.get("result", {}).get("resultType") == "input_required":
        pending = response["result"]
        fulfilled = {
            key: fake_host_model(input_request)
            for key, input_request in pending["inputRequests"].items()
        }
        request_id += 1
        ...
        response = dispatch({... "params": retry_params})
```

对照讲义"Safety Invariants"，这个客户端循环缺少哪些保护？请改写它，加入：最大轮数、只处理已声明能力的方法、审批钩子、每轮字节上限。

**Q12.** 用同一个第一轮 `requestState` 连续重试两次（第一次选 `["README.md"]`，第二次选 `["LICENSE"]`），两次都会成功返回 `input_required`；拿到第二轮 state 后，用任意 `summary` 文本重试也都会成功。

1. 这说明 `requestState` 缺少什么性质？在本例中危害大吗？在什么场景下危害会变大？
2. 给出两种修复思路，并说明它们与"无状态"原则如何兼容。
3. 代码只绑定了 `method == "tools/call"` 和参数摘要，没有绑定**工具名**。如果服务端以后再加一个参数结构相同的工具，会出现什么问题？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 MCP 的 MRTR？它和旧版 Sampling 的"服务端回调客户端"有什么本质区别？

**Q14.**（原理深挖）`requestState` 为什么必须被视为攻击者可控？请说出要绑定的五类信息，以及每一项防的是什么攻击。

**Q15.**（工程实践）你要把一个依赖 Sampling 的旧 MCP 工具迁移到 2026-07-28，给出迁移方案：直接集成还是 MRTR？如果选 MRTR，怎么设计轮次、预算和移除计划？

**Q16.**（场景设计）设计一个 MCP 客户端（host）对嵌入式 sampling 请求的安全策略：一个恶意服务端可能做哪些事？你在客户端如何防御？

**Q17.**（追问型）服务端是无状态的，那多轮之间的中间结果（例如第一轮选出的文件）放在哪里？为什么不放在服务端内存或 Redis 里？放在 `requestState` 里又有什么代价？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："New server: integrate with a model provider directly. This is the current default." A 是 2025-11-25 的旧行为，2026-07-28 已移除服务端到客户端的请求通道，只能放在特定版本的兼容适配器里；B 是兼容路径而不是默认，且只在"必须用客户端模型与凭据"时使用；D 错，`clientInfo` 只是展示与诊断信息。

### Q2 — 答案：A

讲义："It is a new request that repeats the original method and arguments, adds only the current round's `inputResponses`, and echoes `requestState` byte for byte." B 错，重试必须用新 id（代码 `run_mrtr` 中 id 为 1、2、3）；C 错，客户端不得解析或修改 `requestState`，一旦改动 HMAC 校验就失败；D 错，服务端没有会话记忆，原参数还要参与 `argumentsDigest` 校验。

### Q3 — 答案：D

`tools_call` 中：

```python
    if "sampling" not in capabilities:
        raise McpError(
            -32021,
            "missing required client capability",
            {"requiredCapabilities": {"sampling": {}}},
        )
```

测试 `test_sampling_capability_is_required` 断言了完全相同的 `data`。B 是 `clientCapabilities` 根本不是字典时的错误（`{}` 是合法字典）；C 与版本无关；A 不对，服务端不会发出客户端没声明能力的嵌入请求（讲义"Capability gate"）。注意：检查只看键是否存在，`{"sampling": null}` 也能通过（已实测）。

### Q4 — 答案：B

讲义："They are not a probability distribution and do not need to sum to one. The client may ignore them because the client owns model policy." 有意思的是，本节代码 `_sampling_request` 用 `costPriority = round(1.0 - intelligence, 2)` 生成，两轮分别是 0.8/0.2 和 0.2/0.8，**恰好加和为 1**——这只是代码的写法，不是协议要求，不要因此误以为必须互补。C、D 都不是协议行为。

### Q5 — 答案：D

讲义："MRTR is allowed only on `tools/call`, `prompts/get`, and `resources/read`. A server must not return `input_required` from unrelated methods." `tools/list` 是发现类方法，应确定、可缓存（代码中 `ttlMs=60_000`、`public`），绝不能要求客户端补输入。本节代码只在 `tools/call` 上实现了 MRTR。

### Q6 — 答案：A

签名覆盖的是 body 本身，客户端没改 body，所以 HMAC 校验通过（排除 C）；principal、method 也一致；到参数检查时，`_arguments_digest({"audience": "executive"})` 与签名体里的摘要不同，于是抛 `requestState arguments mismatch`。测试 `test_request_state_is_bound_to_original_arguments` 验证了这一点。B、D 忽略了参数绑定——如果不绑定参数，攻击者可以拿一个低权限参数换来的 state 去配一个高风险参数。

### Q7 — 答案：B

讲义："Use HMAC when confidentiality is not required. Use authenticated encryption when the client must not read the state." 实测第一轮 body 解码就是明文 JSON（含 `principal`、`argumentsDigest`、`expiresAt`、`phase`），第二轮还会出现 `picked` 列表。A 错，HMAC 不加密；C 错，讲义要求把它当作攻击者可控值；D 是严重错误，密钥一旦给客户端就能伪造任意状态，多实例应通过密钥管理共享密钥。

### Q8 — 答案：C

`run_mrtr` 每次重试都 `request_id += 1`，第一次请求得到 `input_required(pick_files)`，第二次得到 `input_required(summary)`，第三次得到 `complete`。这正是讲义 checkpoint："Request ids are `[1, 2, 3]`, proving each MRTR round is independent." A、B 都暗含"会话/流"，与无状态设计相反；D 错，没有失败。

### Q9 — 参考答案

1. **43 个字符**。SHA-256 摘要 32 字节，base64 每 3 字节编码为 4 字符：`ceil(32/3)*4 = 44`，末尾 1 个 `=` 被 `rstrip("=")` 去掉，剩 43。已实测：签名部分长度 43；对 `expiresAt=10` 的测试 state，body 160 字节、编码后 214 字符。
2. 第一轮 body（实测）：

   ```text
   {"argumentsDigest":"a7581292...c03c8b","expiresAt":<当前时间+300>,"method":"tools/call","phase":"pick","principal":"user-42"}
   ```

   客户端**能读**（只是 base64url），**不能改**：改了 body 而不改签名，`compare_digest` 失败；想重新签名需要 `SERVER_SECRET`。实测把 `principal` 改成 `admin` 并保留原签名，得到 `requestState integrity check failed`。
3. 规范化（canonical）序列化：同一个字典无论键的插入顺序如何，都产生**同一串字节**，签名和摘要才稳定；`separators` 去掉空格，避免不同实现的空白差异。实测两种键顺序的摘要相等（`True`）。
4. `compare_digest` 是常量时间比较，避免攻击者通过响应时间差逐字节猜出正确签名（timing attack）。

### Q10 — 参考答案

已逐个实测：

| 输入 | 结果 | 原因 |
|------|------|------|
| (a) `not json` | `-32602 pick_files must return JSON` | `json.loads` 抛 `JSONDecodeError`（讲义练习 1） |
| (b) `{"a": 1}` | `-32602 pick_files must return a string array` | 是合法 JSON，但不是字符串列表 |
| (c) `["../../etc/passwd"]` | `-32602 pick_files returned no known files` | 只保留 `FAKE_REPO` 中存在的名字（白名单），路径穿越被过滤 |
| (d) 三个 `README.md` | `input_required`，`picked = ["README.md","README.md","README.md"]` | 没有去重 |
| (e) 四个合法文件 | `input_required`，`picked = ["LICENSE","server.py","client.py"]` | `[:3]` 截断，保留模型给出的前三个 |

(d) 暴露了缺陷：提示词要求"三个有代表性的文件"，但重复项会被原样接受，第二轮 prompt 里同一文件内容重复三次，浪费 token 也降低摘要质量。修复：

```python
        seen: list[str] = []
        for name in picks:
            if name in FAKE_REPO and name not in seen:
                seen.append(name)
        picked = seen[:3]
```

（保持顺序的去重；也可以用 `list(dict.fromkeys(...))`。）这道题也说明了讲义的原则："Validate every sampling response before using it as a filename, URL, or tool input"——代码对 (a)(b)(c) 做得很好，(d) 是遗漏。

### Q11 — 参考答案

缺少的保护：没有最大轮数（服务端若一直返回 `input_required` 会无限循环，形成模型花费循环）；不检查嵌入请求的 `method` 是否是客户端声明过的能力；没有审批（向用户展示服务端要求模型做什么）；没有字节/token 上限；没有日志（记录方法与 input key 而非敏感内容）。

```python
MAX_ROUNDS = 3
MAX_PROMPT_BYTES = 8_000
ALLOWED_METHODS = {"sampling/createMessage"}      # 与 clientCapabilities 一致

def run_mrtr_safely(approve=lambda key, req: True):
    base_params = {"name": "summarize_repo", "arguments": {"audience": "developer"},
                   "_meta": main.request_meta()}
    request_id, rounds = 1, 0
    response = main.dispatch({"jsonrpc": "2.0", "id": request_id,
                              "method": "tools/call", "params": base_params})
    while response.get("result", {}).get("resultType") == "input_required":
        rounds += 1
        if rounds > MAX_ROUNDS:
            raise RuntimeError("MRTR round budget exceeded")
        fulfilled = {}
        for key, req in response["result"]["inputRequests"].items():
            if req.get("method") not in ALLOWED_METHODS:
                raise RuntimeError(f"undeclared input request: {req.get('method')}")
            size = len(json.dumps(req["params"]).encode())
            if size > MAX_PROMPT_BYTES:
                raise RuntimeError(f"input request too large: {size} bytes")
            if not approve(key, req):
                raise RuntimeError(f"user declined {key}")
            fulfilled[key] = main.fake_host_model(req)
        request_id += 1
        response = main.dispatch({"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                                  "params": {**base_params, "inputResponses": fulfilled,
                                             "requestState": response["result"]["requestState"]}})
    return response, rounds
```

正常流程下 `rounds == 2`，在 3 轮上限之内；若服务端返回第 4 轮就会被中止。要点：上限必须在**客户端**执行，因为客户端才是嵌入式 sampling 的信任边界。

### Q12 — 参考答案

1. 缺少**一次性（single-use / 防重放）**。同一个 state 在 300 秒内可无限次使用；第二轮 state 也可以配任意 `summary`。本例中危害有限：最终结果只是"客户端自己的模型给出的摘要"，客户端本来就能控制它；state 也绑定了 principal，别人拿不走。危害变大的场景：状态推进带副作用（例如第二轮之后执行写操作、扣费、发消息），或者中间值影响授权与资源访问（讲义硬性拒绝：未签名/不受控的 state 影响业务逻辑）。
2. 修复思路：
   - **短过期 + nonce 记录**：state 中加入随机 `nonce`，服务端在共享存储里记录"已使用的 nonce"直到过期。这引入了少量服务端存储，但它是**防重放的去重表**，不是协议会话——任何实例都能查，不依赖连接。
   - **幂等设计**：让每一轮的处理是纯函数（相同输入产生相同输出），副作用放在最后一步并用幂等键保护，这样重放无害。
   - 另外可把"上一轮输出的摘要"写进下一轮 state，形成链式绑定，防止跨分支拼接。
3. state 会在两个工具之间"串用"：拿工具 A 的第一轮 state 去调用工具 B，只要参数结构和值相同，principal、method、摘要都对得上，B 会接受 A 的状态并进入 B 的 `pick`/`summarize` 分支。修复：在 state 里加入 `"tool": params["name"]`，验证时比对；更一般地，把"方法 + 目标（工具名/URI/prompt 名）+ 参数"一起做摘要。

### Q13 — 参考回答要点

- **定义**：MRTR 是 2026-07-28 的无状态重试模式。服务端在处理 `tools/call`、`prompts/get`、`resources/read` 时若需要客户端输入（sampling、elicitation、roots），返回 `resultType: "input_required"`，把子请求放进 `inputRequests`，并附 `requestState`；客户端满足后用新 id 重试原请求，带上 `inputResponses` 和原样的 `requestState`。
- **与旧 Sampling 的区别**：旧版是服务端在一个**活动连接/会话**上主动向客户端发 `sampling/createMessage` 请求并等待；新版服务端从不主动发请求，控制流始终是"客户端请求—服务端响应"，状态显式地放在 `requestState` 中。
- **好处**：协议层无会话，任何实例都能处理任何一轮；循环显式、有界、可审计；客户端完全掌控是否、何时、用什么模型满足请求。
- 加分点：Sampling 本身已被弃用，新设计应直接集成模型；官方 SDK 可以为旧对端做兼容 shim，但不能借此加入新的会话依赖。

### Q14 — 参考回答要点

`requestState` 经过客户端往返，客户端（或中间人、或另一个用户）可以篡改、重放、移植。需要绑定：

| 绑定项 | 防御的攻击 |
|-------|-----------|
| 已认证主体（不是 `clientInfo`） | 把 A 用户的 state 拿给 B 用户用（跨主体移植） |
| 原方法 | 把 `tools/call` 的 state 用到 `resources/read` 上 |
| 原参数摘要 | 用低风险参数拿到 state，再换成高风险参数完成 |
| 短期过期时间 | 长期重放旧 state |
| 当前阶段与已验证的中间值 | 跳阶段、伪造"已验证"的中间结果（如被选中的文件） |

- 完整性用 HMAC，需要保密时用认证加密（AEAD）；比较签名用常量时间函数；所有失败统一返回 `-32602`。
- 加分点：加入 nonce 防重放；把工具名/目标资源也绑进去；密钥轮换时在 state 里带 key id。
- 常见误区：只签名 `phase` 字符串（讲义："Signing a raw phase name is not enough"）；用 `clientInfo.name` 当 principal。

### Q15 — 参考回答要点

- **先决策**：能否直接集成模型？默认是能。只有"必须使用用户在 host 中的模型与凭据"（例如费用由用户承担、模型由企业 host 统一管控）才保留 Sampling 兼容路径。
- **直接集成**时，服务端承担：模型选择、API 密钥、预算与限流、重试、审批（若有）、计费与可观测性；对客户端只返回普通 `complete` 结果。
- **MRTR 方案**：
  - 轮次表：每轮写清 `inputRequests` 键、方法、期望的响应 schema、校验规则、预算（如 `pick_files` → JSON 字符串数组，≤3 个、必须在白名单内；`summary` → 非空文本、≤N 字节）；
  - 每个请求 `_meta` 带版本与能力；缺 sampling 能力返回 `-32021`；
  - `requestState` 绑定主体、方法、工具名、参数摘要、阶段、过期；
  - `includeContext: "none"`，只传最少显式上下文；
  - 总轮数上限（如 3）、token 与字节预算。
- **移除计划**：写明触发条件与日期，例如"当 80% 客户端支持服务端直连模型的计费方案后，于某季度移除 Sampling 路径"；2025-11-25 的会话式 Sampling 只放在版本适配器中。

### Q16 — 参考回答要点

- **恶意服务端可能**：无限返回 `input_required` 消耗用户的模型额度；在 prompt 中注入指令，诱导模型输出敏感信息或恶意文件名/URL；请求超大 `maxTokens`；请求 `includeContext` 把用户对话上下文泄露给服务端；发起客户端未声明的输入请求类型。
- **客户端防御**：
  - 轮数上限、每轮 token/字节上限、总花费上限；
  - 只响应已声明能力对应的方法，其余拒绝；
  - 按策略向用户展示服务端要模型做什么，并请求批准；
  - 忽略或降级 `includeContext`，坚持 `"none"`；
  - 模型输出只作为数据返回给服务端，不进入客户端自己的授权决策；
  - 日志记录来源方法与 input key，不记录敏感 prompt 内容；
  - 客户端可以忽略 `modelPreferences`，按自身策略选模型。
- 加分点：服务端那一侧同样要校验模型返回（本节对 `pick_files` 做了 JSON 解析、类型检查、白名单过滤）。

### Q17 — 参考回答要点

- **放在哪**：放在下一轮的 `requestState` 里（本节第二轮 state 中含 `picked`），由客户端原样带回，服务端验证签名后取出。
- **为什么不放服务端内存**：内存状态要求下一轮请求落到同一实例（会话粘性），破坏水平扩展；实例重启就丢；协议层也不再有会话 ID 可以关联。
- **为什么不首选 Redis**：可以用，但这等于重新引入了服务端会话存储，需要清理、容量规划、跨区域复制；对于少量中间值，签名后的 state 更简单。大的中间结果（例如完整文档）则不适合塞进 state。
- **代价**：state 变大，每轮都在网络上往返；HMAC 下客户端可读（需要保密就用认证加密）；无法天然防重放（需要 nonce 表或幂等设计）；需要密钥管理与轮换。
- 加分点：讲义 Tasks 扩展（第 13 节）在需要长时间运行时改用服务端持久任务存储，这是"状态放 state"与"状态放服务端"之间的另一个取舍点。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：JSON-RPC 请求、通知与错误码。
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：`tools/list` 与 `tools/call` 的基本结构。
- [阶段 13 · 10 MCP Resources 与 Prompts](../../10-mcp-resources-and-prompts/docs/zh.md)：`_meta` 信封、`server/discover`、`-32022` 与缓存提示。
- [阶段 13 · 04 Structured Output](../../04-structured-output/docs/zh.md)：要求模型返回 JSON 数组并做校验的思路。

### 本节被哪些后续内容用到
- [阶段 13 · 12 显式作用范围与无状态 Elicitation](../../12-mcp-roots-and-elicitation/docs/zh.md)：同样的 MRTR 机制用于 elicitation，并讨论 roots 的弃用。
- [阶段 13 · 13 MCP Tasks 扩展](../../13-mcp-async-tasks/docs/zh.md)：新增 `resultType: "task"`，处理长时间运行的工作。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：MRTR 状态被篡改、重放的攻击面。
- [阶段 13 · 21 LLM 路由层](../../21-llm-routing-layer/docs/zh.md)：服务端直接集成模型时如何做路由、预算与回退。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：轮数、预算与超时控制。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：嵌入 prompt 中的注入风险。

### 延伸关键词
`MRTR` · `input_required` · `inputRequests / inputResponses` · `requestState` · `HMAC-SHA256` · `AEAD` · `canonical JSON` · `constant-time compare` · `replay / nonce` · `-32021` · `modelPreferences` · `includeContext` · `direct model integration` · `capability gate`
