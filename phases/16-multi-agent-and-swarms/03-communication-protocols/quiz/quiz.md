# 测验 · 通信协议（Communication Protocols）

> **阶段 16 · 多智能体与集群 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.ts](../code/main.ts)（TypeScript，本节无单独代码讲解，代码要点见第三部分与第五部分解析）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提示**：本节中文讲义是机器翻译，质量较差（例如把 ACP 译成"非加太"、把 ANP 译成"国家警察局"），遇到看不懂的地方请直接对照英文版。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个协议是"分层"而非竞争 | MCP 解决 agent 调工具；A2A 解决 agent 之间协作；ACP 解决可审计；ANP 解决跨组织的去中心化身份与信任 |
| 2 | MCP | Anthropic 提出，client-server、JSON-RPC；agent（client）`list tools` → `call tool`。是 **agent-to-tool**，不负责 agent 之间对话 |
| 3 | A2A Agent Card | 放在 `GET /.well-known/agent-card.json`；包含 skills（id、tags、输入/输出 MIME）、`supportedInterfaces`（JSON-RPC / REST / gRPC 多绑定）、`securitySchemes`（调用前就知道需要什么认证） |
| 4 | A2A Task 生命周期 | submitted → working →（input-required / auth-required）→ completed / failed / canceled / rejected；终态不可变，后续追问在同一 `contextId` 下**新建** task |
| 5 | A2A 传输 | JSON-RPC 2.0（`SendMessage`）、轮询 `GET /tasks/{id}`、或 `POST /message:stream` 用 SSE 推送 `statusUpdate` / `artifactUpdate` |
| 6 | ACP | IBM / BeeAI，OpenAPI 3.1 的 REST/JSON（讲义特别强调**不是** JSON-LD）；用 Run 而非 Task，三种模式 sync / async（立即 202，再轮询）/ stream；正在并入 A2A |
| 7 | TrajectoryMetadata | ACP 的核心卖点：每个响应附带推理步骤与 tool 调用（tool_name、tool_input、tool_output），给受监管行业提供可证明的推理链；另有 CitationMetadata 做来源标注 |
| 8 | ANP 与 `did:wba` | 社区协议；DID `did:wba:example.com:user:alice` 解析为 `https://example.com/user/alice/did.json`；签名密钥（secp256k1）与加密密钥（X25519，用于 HPKE / RFC 9180）分离；`humanAuthorization` 密钥需要人类显式批准 |
| 9 | ANP 信任模型与元协议 | 信任是双边、逐次验证的（域名 TLS + DID 签名 + 最小信任原则），**没有** web-of-trust 或 PageRank 式传播；元协议用自然语言协商数据格式，最多 10 轮，状态 negotiating / rejected / accepted / timeout |
| 10 | 生产中的坑 | Schema 漂移、状态机违规（终态后继续 yield）、DID 解析失败时应 fail closed、轨迹日志膨胀、发现阶段的惊群效应（thundering herd） |

### 核心技能（能动手做到）

- [ ] 读懂一张 A2A Agent Card，判断某个远程 agent 能否处理给定 MIME 类型和技能标签的请求
- [ ] 画出 A2A 的 Task 状态机，说出哪些状态是终态、终态之后追问应该怎么做
- [ ] 用 async generator 实现一个"按事件推进"的 TaskManager，并能解释终态后 `break` 的意义
- [ ] 用 Node `crypto` 生成 Ed25519 密钥对、签名、验签，并说清楚**签什么**才能防篡改和防重放
- [ ] 指出本节 `ProtocolGateway` 把审计与任务执行分成两次独立调用带来的问题，并给出改法
- [ ] 按"是否用工具 → 是否 agent 互通 → 是否需要合规审计 → 是否跨组织"的决策树为一个系统选协议组合

---

## 二、基础自测（选择题）

**Q1.** 一个 agent 需要查询公司数据库，同时把"写代码"这件事委托给另一个团队维护的 coding agent。按讲义的分层，最合适的组合是：

- A. 查数据库用 MCP，委托 coding agent 用 A2A
- B. 两件事都用 MCP，因为 coding agent 也可以包装成一个 tool
- C. 两件事都用 ANP，因为它是最底层的身份协议
- D. 查数据库用 ACP，委托 coding agent 用 MCP

**Q2.** 按讲义中 A2A v1.0 的规范，客户端 agent 去哪里获取远程 agent 的能力描述？

- A. `POST /message:send` 的响应头里
- B. `GET /agents`
- C. `/.well-known/agent.yml`
- D. `GET /.well-known/agent-card.json`

**Q3.** 一个 A2A task 已经处于 `TASK_STATE_COMPLETED`，用户又想追问一个相关问题。正确的做法是：

- A. 把这个 task 的状态改回 `working`，继续在同一个 task 里追加消息
- B. 发送 `cancel` 再重新提交原 task
- C. 在同一个 `contextId` 下创建一个新的 task
- D. 必须换一个新的 `contextId`，因为上下文随 task 一起终止

**Q4.** 关于 ACP（Agent Communication Protocol），下列说法与讲义一致的是：

- A. ACP 使用 JSON-LD 描述消息语义，因此天然支持链接数据
- B. ACP 是基于 OpenAPI 3.1 的 REST/JSON API，最大特色是每个响应可以携带 TrajectoryMetadata（推理步骤与 tool 调用记录）
- C. ACP 用 W3C DID 做身份认证，并用 HPKE 端到端加密
- D. ACP 只支持同步阻塞调用，不支持流式

**Q5.** 关于 ANP 的信任是如何建立的，正确的是：

- A. 双边、逐次验证：通过 HTTPS 拉取对方域名上的 DID 文档、用其中公钥验签，再按最小信任原则授予权限
- B. 通过 gossip 在网络中传播信任分数，类似 PageRank
- C. 由一个中心化的注册中心为所有 agent 颁发证书
- D. 通过背书图（endorsement graph）累积其他 agent 的推荐

**Q6.** DID `did:wba:example.com:user:alice` 会被解析到哪个地址？

- A. `https://did.wba.org/example.com/user/alice`
- B. `https://example.com/.well-known/agent-card.json`
- C. `https://alice.example.com/did.json`
- D. `https://example.com/user/alice/did.json`

**Q7.** 在本节 `main.ts` 的 `TaskManager.processTask` 中，如果 handler 先 `yield` 了一个 `completed` 的 `statusUpdate`，之后又 `yield` 一个 `artifactUpdate`，会发生什么？

```typescript
for await (const event of handler(task, message)) {
  if (TERMINAL_STATES.includes(task.status.state)) break;
  if (event.kind === "statusUpdate") { task.status = event.status; }
  if (event.kind === "artifactUpdate") { /* 追加或合并 artifact */ }
  this.emit(task.id, event);
}
```

- A. artifact 被正常追加，状态被改回 `working`
- B. 循环在处理该 artifact 事件前 `break`，这个 artifact 被丢弃，task 保持 `completed`
- C. 抛出异常，task 变为 `failed`
- D. artifact 被追加，但不会通知订阅者

**Q8.** ACP 的 Run 以 `async` 模式提交时，服务端的行为是：

- A. 阻塞直到完成，在响应里返回完整结果
- B. 建立 SSE 连接，边执行边推送事件
- C. 立即返回 202，客户端再轮询 `GET /runs/{id}` 获取状态
- D. 返回一个 DID 文档，客户端用它订阅结果

---

## 三、动手 / 代码题

**Q9.** 讲义正文（Step 3、Step 6）里的代码与 `code/main.ts` 有两处差异：

```typescript
// 讲义版 TaskManager.sendMessage：不 await
this.processTask(task, handler, message).catch((err) => { ... });
return task;

// 讲义版 ProtocolGateway.delegateTask：先审计，后执行任务
const audit = await this.auditRunner.run(targetAgent, [message], sessionId);
const task = await this.taskManager.sendMessage(targetAgent, message);
```

```typescript
// code/main.ts：await 任务处理，并且先执行任务、后审计
await this.processTask(task, handler, message).catch((err) => { ... });
...
const task = await this.taskManager.sendMessage(targetAgent, message);
const audit = await this.auditRunner.run(targetAgent, [message], sessionId);
```

已知 demo 中 `researcher` 的 TaskManager handler 会往闭包数组 `researchTrajectory` 里 push 两条轨迹，而 AuditableRunner 的 handler 只是返回这个数组（`run` 内部会 `structuredClone` 一份快照）。

1. 如果按**讲义版**运行，第 3、4 步会分别打印出什么 `Task state`、`Artifacts`、`Trajectory steps`？为什么？
2. `code/main.ts` 版本的输出是什么？它"修好"了问题吗，还是只是让 demo 看起来对了？
3. 从设计上说，ACP 式审计应该怎样和 A2A task 结合，才能保证审计记录的就是**那一次**真实执行？

**Q10.** 阅读 ANP 风格的签名与网关验证：

```typescript
const signature = signPayload(coderIdentity, message.id);
...
if (!this.identityRegistry.verify(fromDid, signature, message.id)) {
  return { error: "Identity verification failed" };
}
```

1. 攻击者截获了一条合法消息和它的签名，把 `message.parts` 改成"删除生产数据库"，网关还能验签通过吗？（实际运行结果：能，`tampered still verified: true`。）
2. 除了篡改，这种方案还挡不住哪类攻击？
3. 给出一个改进后的"签什么"方案（写出要签名的 payload 包含哪些字段），并说明网关侧要增加哪些检查。

**Q11.** `createIdentity` 生成 DID 文档的片段如下：

```typescript
const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
const publicKeyDer = publicKey.export({ format: "der", type: "spki" }).toString("base64");
...
verificationMethod: [
  { id: keyId,    type: "Ed25519VerificationKey2020",  controller: did, publicKeyDer },
  { id: encKeyId, type: "X25519KeyAgreementKey2019",   controller: did, publicKeyDer },
],
authentication: [keyId],
keyAgreement: [encKeyId],
humanAuthorization: [],
```

1. 讲义强调 ANP 的"Key separation is enforced"。这段代码做到了吗？
2. 把一把 Ed25519 公钥标成 `X25519KeyAgreementKey2019` 有什么问题？
3. 修改代码，使签名密钥和密钥协商密钥真正分离，并让 `requiresHumanAuth` 对某个高风险操作返回 `true`。

**Q12.** `ProtocolGateway.discoverAndDelegate` 的实现如下：

```typescript
discoverAndDelegate(fromDid, signature, skillTag, message) {
  const candidates = this.registry.discoverBySkillTag(skillTag);
  if (candidates.length === 0) {
    return Promise.resolve({ error: `No agents found with skill tag: ${skillTag}` });
  }
  return this.delegateTask(fromDid, signature, candidates[0].name, message);
}
```

请找出至少三处与讲义所描述的协议语义不一致或在生产中会出问题的地方，并给出改进思路（提示：`sessionId`、`contextId`、MIME 类型、候选选择、发现阶段的缓存）。

---

## 四、面试高频题

**Q13.**（基础必考）MCP、A2A、ACP、ANP 分别解决什么问题？为什么说它们不是互相竞争的关系？请举一个同时用到其中三个的系统例子。

**Q14.**（原理深挖）A2A 的 Task 为什么要设计成"终态不可变 + 同一 contextId 下新建 task"？如果允许终态 task 被重新打开，会带来哪些问题？

**Q15.**（工程实践）你负责一个金融场景的多 agent 系统，监管要求"每个回答都能追溯到具体用了哪个工具、输入输出是什么"。你会怎么设计审计链路？如何避免轨迹日志膨胀？

**Q16.**（场景设计）你的 agent 需要和一家合作伙伴公司的 agent 互相调用（双方没有共享基础设施）。请设计身份验证、授权与故障处理方案，并说明 DID 文档拉取失败时应该 fail open 还是 fail closed。

**Q17.**（追问型）面试官问："既然有了 A2A，直接让 agent 之间互相传字符串不行吗？什么时候你会说'这个系统根本不需要协议'？"

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义的分层：MCP 是 agent-to-tool（"MCP is agent-to-tool communication. It doesn't help agents talk to each other"），A2A 是 agent-to-agent 的协作与委托。查数据库是用工具，委托另一个团队的 agent 是 agent 间协作。

- B：把另一个 agent 包成 tool 技术上可行，但会丢掉 A2A 的 task 生命周期、流式进度、`input-required` 交互、Agent Card 发现与安全声明，不是讲义推荐的分层。
- C：ANP 解决的是跨组织、无中心信任下的身份，不负责工具调用；同团队/同组织内也未必需要。
- D：ACP 是可审计的 agent 运行协议，不是工具协议；MCP 也不负责 agent 间委托。

### Q2 — 答案：D

讲义："Served at `GET /.well-known/agent-card.json`"。

- A：`/message:send` 是提交消息/任务的端点，不负责发现。
- B、C：`GET /agents` 和 `/.well-known/agent.yml` 是 **ACP** 的发现方式（ACP 定义了 Runtime、Open、Registry、Embedded 四种发现）。
- 注意：本节自带的 `quiz.json` 写的是 `/.well-known/agent.json`，那是 A2A 早期版本的路径，与讲义正文的 v1.0 不一致，以讲义正文为准。

### Q3 — 答案：C

讲义："Once a task reaches a terminal state, it's immutable. No further messages. Follow-ups create a new task within the same `contextId`." `contextId` 是"会话/上下文"的标识，task 是"一次工作单元"。

- A：违反终态不可变。
- B：已完成的 task 无法取消（代码中 `cancelTask` 对终态直接返回 `false`，实测 `cancel completed: false`）。
- D：说反了，正是要复用 `contextId` 来保持上下文连续。

### Q4 — 答案：B

讲义："Unlike what many summaries claim, ACP does **not** use JSON-LD. It's a straightforward REST/JSON API defined via OpenAPI." 其差异化能力是 TrajectoryMetadata。

- A：讲义明确否定。值得注意的是，本节自带的 `outputs/prompt-protocol-selector.md` 仍写着 "JSON-LD structured messaging"，与讲义正文矛盾。
- C：DID + HPKE 是 ANP 的特征。
- D：ACP 的 Run 有 sync / async / stream 三种模式。

### Q5 — 答案：A

讲义："ANP does **not** use a web-of-trust or endorsement graph. Trust is bilateral and verified per-interaction"，信任来自域名 TLS、DID 签名、最小信任原则三个来源，"There's no gossip-based trust propagation or PageRank scoring"。

- B、D：讲义明确否定（`outputs/prompt-protocol-selector.md` 写的 "trust graphs" 同样与正文矛盾）。
- C：中心化颁证正是 ANP 想避免的模型。

### Q6 — 答案：D

`did:wba` 的解析规则：把方法名后的冒号分隔片段还原为域名 + 路径，再拼上 `did.json`。讲义："The DID `did:wba:example.com:user:alice` resolves to `https://example.com/user/alice/did.json`"。B 是 A2A Agent Card 的位置；A、C 是虚构的地址。也正因为 DID 文档托管在 agent 自己的域名上，域名级 TLS 才成为信任来源之一。

### Q7 — 答案：B

第一次循环把 `task.status` 设为 `completed` 并 emit；下一次拿到 `artifactUpdate` 时，先检查 `TERMINAL_STATES.includes(task.status.state)`，为真就 `break`，该事件既不入库也不通知。实测（用一个先 yield completed、再 yield artifact 的 handler）：`task state completed artifacts after completed: 0`。这就是讲义 What Goes Wrong 里的 "State machine violations ... The `TaskManager` above enforces this with the `break` after terminal states"。

- A：终态不可变，不会改回 working。
- C：`break` 不会抛异常。
- D：artifact 根本没有被追加。

补充：静默丢弃并不理想——生产中至少应记录一条警告日志，否则 handler 的 bug 很难被发现。

### Q8 — 答案：C

讲义 Run 模式表：`async` — "Returns 202 immediately. Poll `GET /runs/{id}` for status."；A 是 `sync`；B 是 `stream`；D 混入了 ANP 的概念。

### Q9 — 参考答案

1. **讲义版输出**（已把 `main.ts` 改回讲义写法实际运行）：`Task state: working`、`Artifacts: 0`、`Trajectory steps: 0`。原因有两层：
   - 先审计：`auditRunner.run` 调用时 TaskManager 的 handler 还没运行，`researchTrajectory` 是空数组，`structuredClone` 拍下的就是空快照，所以轨迹为 0。
   - 不 await：`sendMessage` 中 `processTask` 同步执行到 `task.status = working` 和第一个 `for await`，随后控制权回到调用方，`sendMessage` 立即返回；此时 handler 的事件还在微任务队列里，所以状态是 `working`、artifact 为 0。
2. **`main.ts` 版输出**：`Task state: completed`、`Artifacts: 1`、`Trajectory steps: 2`、`researcher: completed (0ms)`。它只是通过"先 await 任务、后审计"让 demo 读到了已被填好的闭包数组，并没有从结构上解决问题：
   - 审计 handler 与任务 handler 是**两次独立的执行**，审计记录的 `output`（一条写死的文本消息）并不是任务产出的 artifact；
   - 轨迹靠一个跨请求共享的闭包数组传递，第二次委托时数组里会累积 4 条，审计会把上一次的轨迹也算进来；
   - `await processTask` 也让 `sendMessage` 失去了"先返回 submitted task、再异步推进"的 A2A 语义，调用方拿不到中间状态（除非提前 `subscribe`，但调用方此时还不知道 task id）。
3. **正确结合方式**：审计应当**包裹**任务执行，而不是并列。例如由 TaskManager 在 `processTask` 里为每个 task 创建一个 AuditEntry（`runId` 关联 `task.id`、`sessionId` 关联 `contextId`），handler 通过参数拿到一个 `trajectory.record(...)` 回调，每条轨迹实时写入该 entry；task 进入终态时把最终 artifacts 写入 `output` 并封存（status、completedAt）。这样一次执行只产生一份、且只属于自己的审计记录。

### Q10 — 参考答案

1. **能通过**。签名只覆盖 `message.id`（一个随机 UUID），消息正文 `parts`、`role`、`timestamp` 都不在签名范围内，改正文不影响验签。实测：`tampered still verified: true`。
2. **重放攻击**：同一个 `(id, signature)` 可以被任意次数重放；签名也没有绑定接收方（audience），可以把发给 A 的签名转发给 B 使用。另外签名里没有时间信息，无法设过期窗口。
3. **改进方案**：
   - 签名 payload 使用规范化（canonical）JSON 或其哈希，至少包含：`messageId`、`sha256(parts 的规范化序列化)`、`role`、`fromDid`、`audience`（目标 agent 的 DID 或 URL）、`issuedAt`、`nonce`。
   - 网关检查：重新计算正文哈希并比对；`audience` 必须是自己；`issuedAt` 在允许的时钟偏差窗口内（如 ±5 分钟）；`nonce` 在窗口期内未被使用（用带 TTL 的缓存去重）；验签用的密钥必须出现在 DID 文档的 `authentication` 列表中。
   - 进一步：按讲义的流程，验签成功后签发短期 access token，后续请求用 token，减少每次签名验签的开销。

### Q11 — 参考答案

1. **没有做到**。两个 verificationMethod 的 `publicKeyDer` 是同一个值（实测 `same key for auth & keyAgreement: true`），只是换了 `id` 和 `type` 标签。
2. Ed25519 是签名算法用的曲线表示，X25519 是密钥协商（ECDH）用的；同一把密钥材料被标成两种用途，一来类型声明不真实（真正做 HPKE 时这把 Ed25519 SPKI 公钥无法直接当作 X25519 公钥使用），二来违背"签名密钥与加密密钥分离"的原则：一旦一把密钥泄露，身份冒充和解密能力同时失守，也无法单独轮换其中一种。
3. 参考修改：

```typescript
const sign = crypto.generateKeyPairSync("ed25519");
const enc = crypto.generateKeyPairSync("x25519");
const human = crypto.generateKeyPairSync("ed25519");
const der = (k: crypto.KeyObject) =>
  k.export({ format: "der", type: "spki" }).toString("base64");

const keyId = `${did}#key-1`;
const encKeyId = `${did}#key-x25519-1`;
const humanKeyId = `${did}#key-human-1`;

verificationMethod: [
  { id: keyId,      type: "Ed25519VerificationKey2020", controller: did, publicKeyDer: der(sign.publicKey) },
  { id: encKeyId,   type: "X25519KeyAgreementKey2019",  controller: did, publicKeyDer: der(enc.publicKey) },
  { id: humanKeyId, type: "Ed25519VerificationKey2020", controller: did, publicKeyDer: der(human.publicKey) },
],
authentication: [keyId],
keyAgreement: [encKeyId],
humanAuthorization: [humanKeyId],
```

此时 `requiresHumanAuth(did, humanKeyId)` 返回 `true`。还要注意 `IdentityRegistry.verify` 只遍历 `authentication` 中的密钥，用 `humanAuthorization` 密钥签名的高风险操作需要另一个验签入口（并在调用前确认已有人类批准，例如生物识别或硬件密钥）。

### Q12 — 参考答案

- **丢了 `sessionId`**：`delegateTask` 的第五个参数没有传，审计记录的 `sessionId` 为 `undefined`，`getAuditLogForSession` 查不到这次运行。
- **没有 `contextId`**：网关调用 `taskManager.sendMessage(targetAgent, message)` 时从不传 `contextId`，每次委托都新建上下文，A2A 的"同一 contextId 下追问"无从实现。
- **只看技能标签，不看 MIME**：没有核对消息的 part 类型（如 `application/pdf`）是否在候选 agent 的 `inputModes` / `defaultInputModes` 里，也没核对调用方能接受的输出类型；`discoverByInputMode` 写了却没用。
- **候选选择是"取第一个"**：`candidates[0]` 取决于 `Map` 的插入顺序，没有负载、健康状况、版本或成本考量，也没有失败后换下一个候选的回退。
- **验签放在发现之后才做**：严格说先验签是对的（代码在 `delegateTask` 第一步验签），但 `discoverAndDelegate` 在验签前就执行了发现查询，未认证的请求也能触发注册表查询；放大后就是讲义说的发现阶段 thundering herd。
- **发现无缓存/限流**：每次都实时查注册表；生产应给 Agent Card 加 TTL 缓存、错峰刷新或改为推送式注册（讲义练习 5）。

改进思路：签名改为覆盖完整消息（见 Q10）；`discoverAndDelegate` 接收并透传 `sessionId`、`contextId`；候选先按技能标签筛选，再按输入/输出 MIME 过滤，再按健康状态与优先级排序，逐个尝试直到成功。

### Q13 — 参考回答要点

- **MCP**：agent ↔ 工具/数据源。client-server、JSON-RPC，核心是工具发现与调用。
- **A2A**：agent ↔ agent 协作。Agent Card 发现、Task 生命周期、SSE 流式、多种传输绑定，现归 Linux Foundation。
- **ACP**：可审计的 agent 运行。REST/OpenAPI，Run 生命周期，TrajectoryMetadata 记录推理与工具调用；正在并入 A2A。
- **ANP**：跨组织去中心化信任。`did:wba` 身份、HPKE 端到端加密、元协议协商。
- **为什么不竞争**：它们回答的是不同层次的问题（怎么用工具 / 怎么协作 / 怎么审计 / 怎么信任陌生人），讲义："They're not competitors. They solve different problems at different levels."
- **例子**：企业内的研究 agent 用 MCP 连搜索服务器，通过 A2A 把编码任务委托给 coding agent，所有响应带 ACP 风格的轨迹元数据；与外部合作方 agent 交互时先用 ANP 验证 DID，再走 A2A。
- 加分点：指出 MCP 本身也在演进出异步任务等能力（见阶段 13），边界并非一成不变；选型应从"要解决的问题"出发，而不是"协议越多越好"。

### Q14 — 参考回答要点

- **可审计、可复现**：终态是一次工作的"结论"，若能被重新打开，历史 artifact 和状态可能被覆盖，审计和账单（按 task 计费、计量）都会失真。
- **并发与竞态更简单**：多个订阅者/客户端看到的终态永远一致；不需要处理"某客户端认为已完成、另一个客户端又重新激活"的冲突。
- **语义清晰**：task = 一次工作单元，contextId = 一段对话/上下文。追问是新的工作单元，但共享上下文，二者职责分离。
- **实现层面**：本节 `TaskManager` 用 `TERMINAL_STATES` + `break` 和 `cancelTask` 的终态检查来强制执行；讲义的 What Goes Wrong 把"终态后继续 yield"列为状态机违规。
- 常见误区：把 `input-required` 当成终态——它不是，客户端补充信息后 task 回到 `working`。
- 加分点：说出状态表里 8 个状态加上 `UNSPECIFIED` 哨兵值就是对比表里的"9 task states"（讲义两处数字口径不同）。

### Q15 — 参考回答要点

- **记录什么**：借鉴 ACP 的 TrajectoryMetadata，每次运行记录 runId、sessionId/contextId、agent 名与版本、输入、输出、每一步的 tool_name / tool_input / tool_output / 时间戳，以及引用来源（CitationMetadata）。
- **怎么记**：审计必须包裹真实执行（同 Q9），不能事后由另一个 handler"补写"；日志只追加（append-only），存储做不可篡改（WORM 存储、哈希链或签名），查询时返回副本（本节用 `structuredClone` 防止外部修改日志）。
- **按维度查询**：按 agent、按 session、按 run 检索（本节 `getAuditLogForAgent` / `getAuditLogForSession` / `getTrajectoryForRun`）。
- **防膨胀**（讲义 "Trajectory bloat"）：可配置的详细程度——合规场景保留工具名与 IO，非监管负载可跳过推理文本；大对象只存哈希与外部引用；冷热分层存储与保留期策略；对敏感字段脱敏。
- **组织层面**：明确保留期限、访问权限和审计日志本身的访问审计。
- 加分点：把审计链与 OpenTelemetry 追踪打通（trace id 贯穿 A2A task、MCP 工具调用和审计记录）。

### Q16 — 参考回答要点

- **身份**：双方各自在自己域名下发布 `did:wba` DID 文档，签名密钥与密钥协商密钥分离；对高风险操作配置 `humanAuthorization` 密钥。
- **认证流程**（讲义时序图）：A 发送请求 + DID + 签名 → B 通过 HTTPS 拉取 A 的 DID 文档 → 用其中 `authentication` 公钥验签 → 签发短期 access token → 后续请求使用 token。签名覆盖完整消息、audience、时间戳和 nonce（见 Q10）。
- **授权**：最小信任原则，token 只授予该合作场景所需的最小技能范围和速率配额；敏感数据走 HPKE 端到端加密。
- **协作**：身份确认后用 A2A 交换 Agent Card 与 task；格式不统一时可以用 ANP 元协议协商（讲义：最多 10 轮，否则 timeout）。
- **DID 拉取失败**：讲义："ANP recommends fail closed with the principle of least trust." 即拒绝未验证的请求；可以对已验证过的 DID 文档做短 TTL 缓存来缓解对方域名短暂不可用，但缓存过期后仍应 fail closed。
- **故障与运维**：密钥轮换（讲义练习 3：保留 previous 引用、宽限期内新旧密钥都接受）、超时与重试策略、双方审计日志对账。
- 常见误区：fail open"先放行再说"，这会让攻击者通过打挂对方域名来绕过验证。

### Q17 — 参考回答要点

- **传字符串的问题**（讲义 The Problem）：接收方随意解析，容易误解；没有统一的错误与状态语义，容易互相等待形成死锁；跨团队、跨框架的 agent 无法互相发现能力；无法审计；规模一大就失控。
- **协议带来的东西**：能力发现（Agent Card）、明确的任务状态机、结构化的多模态 parts（text / data / file + MIME）、流式进度、认证声明、审计轨迹。
- **什么时候不需要协议**：讲义决策树的结论——agent 既不用外部工具、也不需要互相通信时，"You don't need a protocol"。更实际地说：同一个进程内、同一个团队写的两三个 agent，用函数调用和类型化的数据结构（如本节的 `AgentMessage` 类型）就够了，不必上 HTTP 和 Agent Card。
- 加分点：协议的成本包括序列化、网络、认证、版本兼容（讲义的 Schema drift：给技能和输出 schema 加版本号）。先用类型化的内部消息格式，跨团队、跨组织时再升级到标准协议，是常见的演进路径。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 01 为什么需要多 Agent？](../../01-why-multi-agent/docs/zh.md)：理解拆分成多个 agent 之后为什么必须解决通信问题。
- [阶段 16 · 02 FIPA-ACL 与言语行为理论的历史基础](../../02-fipa-acl-heritage/docs/zh.md)：现代 agent 协议的学术前身，很多设计（performative、交互协议）是"再发明"。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：本节对 MCP 只做回顾，细节在这里。
- [阶段 13 · 19 A2A：Agent 与 Agent 之间的通信协议](../../../13-tools-and-protocols/19-a2a-protocol/docs/zh.md)：从工具与协议视角讲 A2A。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：单个 agent 的运行方式，是协议两端的"端点"。

### 本节被哪些后续内容用到
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：把 handoff、共享状态抽象成与协议无关的原语。
- [阶段 16 · 12 A2A：Agent 与 Agent 之间的通信协议](../../12-a2a-protocol/docs/zh.md)：A2A 的完整实现与细节。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：task 生命周期在生产中的持久化。
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../../13-tools-and-protocols/16-mcp-security-oauth-2-1/docs/zh.md)：协议层的认证与授权实践。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：审计日志与密钥轮换的工程化。

### 延伸关键词
`JSON-RPC 2.0` · `Server-Sent Events (SSE)` · `Agent Card` · `contextId` · `task lifecycle` · `TrajectoryMetadata` · `CitationMetadata` · `W3C DID` · `did:wba` · `HPKE (RFC 9180)` · `Ed25519 / X25519` · `canonical JSON` · `replay protection` · `fail closed` · `thundering herd`
