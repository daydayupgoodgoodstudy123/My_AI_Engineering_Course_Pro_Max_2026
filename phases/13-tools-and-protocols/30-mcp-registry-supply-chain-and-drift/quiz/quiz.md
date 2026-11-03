# 测验 · MCP 注册表供应链：准入、漂移与 Rollback（MCP Registry Supply Chain: Admission, Drift, and Rollback）

> **阶段 13 · 工具与协议 · 第 30 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Registry 是索引，不是审批系统 | "在 Registry 里"是四个不同权威给出的事实链：发布者认证了命名空间、包注册表给出了制品、运行中的端点报告了能力、你的组织批准了这个组合 |
| 2 | 六个边界 | Namespace、Record、Execution source、Runtime、Admission、Operations，各有自己的证据来源 |
| 3 | 命名空间精确比较 | 域名 `example.com` → `com.example`；在 `/` 处切分、要求非空 slug、命名空间段**完全相等**；`startswith("com.example")` 会放行 `com.exampleevil/tool`；可信命名空间必须来自认证结果，而不是记录自身 |
| 4 | Provenance join | 包：registryType + identifier + version + transport + 已验证的所有权 + 可信边界算出的制品 digest；远程：URL + transport + 端点所有权 + 证据 digest；只有 remote 的记录同样合法 |
| 5 | 钉住决策而不只是版本 | `^1.4`、`latest` 都不是 pin；pin 含 recordDigest、sourceDigest、toolsetDigest、provenanceDigest、registryStatus；哪个 digest 变了就知道哪个边界出了问题 |
| 6 | 运行时漂移 | 准入后继续观察 `server/discover` 与工具描述符；只对"顺序无意义"的字段做归一化（按名字排序工具列表），新增工具、改 schema、改描述、改注解都会改变 toolsetDigest |
| 7 | `serverInfo` 只是诊断 | `_meta["io.modelcontextprotocol/serverInfo"]` 是自报信息，只能用于展示/日志/调试，绝不能作为命名空间、所有权或准入依据；`_meta` 外的 `serverInfo` 别名不是契约字段 |
| 8 | Registry 状态是实时状态 | 状态在**响应级** `_meta["io.modelcontextprotocol.registry/official"].status`：`active` / `deprecated` / `deleted`；发布者元数据只能放在 `io.modelcontextprotocol.registry/publisher-provided` 下，不能冒充官方状态 |
| 9 | 回滚 = 恢复路由 | 不修改不可变的发布记录；只选择"以前准入过、当前 active、未被隔离、仍解析到 pin、健康"的版本切换路由 |
| 10 | 防篡改账本 | 每条记录含 sequence、time、event、outcome、reasons、evidence、previousHash、entryHash；能检测修改，但不是防篡改——要把账本头锚定到独立信任域 |

### 核心技能（能动手做到）

- [ ] 写出正确的 `namespace_matches`，并举出 `startswith` 被绕过的例子
- [ ] 给定 Registry 记录、Registry 响应 `_meta`、来源证据和 live discovery 结果，逐条推断 `admit()` 会给出哪些拒绝原因
- [ ] 解释 pin 中四个 digest 各自变化时意味着哪一层出了问题
- [ ] 推演 `check_live` → `observe_registry_status` → `rollback` 的一串操作后路由表和账本的内容
- [ ] 解释哈希链能检测什么、不能检测什么（整体重写、截尾），以及外部锚定的作用
- [ ] 给控制器加上"破坏性工具需两名不同评审"的准入门（讲义 Practice Lab）

---

## 二、基础自测（选择题）

**Q1.** 已验证的命名空间是 `com.example`。下列哪种判断能正确拒绝 `com.exampleevil/inventory`，同时接受 `com.example/inventory`？

- A. `server_name.startswith("com.example")`
- B. 在第一个 `/` 处切分，要求 slug 非空，并要求命名空间段与 `com.example` 完全相等
- C. `"example" in server_name`
- D. 读取 `server.json` 里发布者自己声明的命名空间字段

**Q2.** 准入控制器应该从哪里读取一个版本的 Registry 状态（active / deprecated / deleted）？

- A. 发布记录 `server.json` 的 `_meta.status`
- B. 响应级 `_meta.status`（直接放在 `_meta` 下）
- C. live `server/discover` 结果里的 `serverInfo.status`
- D. 响应级 `_meta["io.modelcontextprotocol.registry/official"].status`

**Q3.** 运行 `main.py` 的演示（准入 1.0.0 → 准入 1.1.0 → 1.1.0 出现 delete 工具 → 1.1.0 变为 deprecated → 回滚到 1.0.0）。账本最后一条 rollback 记录的 `evidence["from"]` 是：

- A. `None`
- B. `"1.1.0"`
- C. `"1.0.0"`
- D. 抛出 `KeyError`，因为路由表里没有该服务

**Q4.** 准入时的工具列表为 `[inventory_get, inventory_delete]`。之后 live check 观察到下列哪种变化时，`check_live` **不会**报告漂移？

- A. `inventory_get` 的 `description` 改了一个词
- B. 新增了一个 `inventory_export` 工具
- C. 两个工具在列表中的顺序颠倒
- D. `inventory_delete` 多了 `annotations: {"destructiveHint": true}`

**Q5.** 某服务端在 `_meta["io.modelcontextprotocol/serverInfo"]` 里报告 `{"name": "org.attacker/pretend", "version": "99.0.0"}`，其余证据都正确。按本节代码与讲义：

- A. 准入照常通过；该值只作为诊断信息原样记入 pin 的 `reportedServerInfo`
- B. 准入被拒绝，因为 `serverInfo.name` 与记录名不一致
- C. 准入通过，并且 pin 的 `server` 字段被改成 `org.attacker/pretend`
- D. 准入通过，但版本号被改成 99.0.0

**Q6.** 下列哪个版本可以作为 `rollback()` 的目标？

- A. 从未准入过、但 Registry 上标记为 latest 的 2.0.0
- B. 准入过、但后来 live check 发现新增工具而被隔离的 1.1.0
- C. 准入过、Registry 状态仍为 active、未被隔离的 1.0.0
- D. 准入过、后来 Registry 状态变为 deleted 的 0.9.0

**Q7.** 关于 `AdmissionLedger.verify()`，下列说法正确的是：

- A. 它能保证账本无法被篡改
- B. 修改第 1 条的 `outcome` 后，只有第 1 条校验失败，后续条目仍然有效
- C. 它会校验每条记录的 `time` 单调递增
- D. 如果攻击者删掉最后几条记录，或者重新计算全部哈希重写整条链，`verify()` 仍返回 `True`

**Q8.** 一条记录使用 `2025-12-11` 的 server.json schema，而 live 服务端的 `supportedVersions` 包含 `2026-07-28`。正确的理解是：

- A. 二者必须一致，否则应拒绝准入
- B. Registry schema 版本与 MCP 协议版本相互独立，不能由一个推断另一个
- C. schema 版本更旧，说明服务端一定不支持 2026-07-28
- D. 只要 schema 版本是 2025-12-11，就可以跳过 live discovery

---

## 三、动手 / 代码题

**Q9.** 讲义的 Interactive Lab B 和 Lab C 是连续在同一个 shell 里执行的：

```python
times = iter(f"2026-08-21T12:00:{n:02d}+00:00" for n in range(10))
c = RegistryAdmissionController(clock=lambda: next(times))
meta = {OFFICIAL_META_KEY: {"status": "active"}}
c.admit(sample_record("1.0.0"), meta, "com.example", evidence_for("1.0.0"), sample_live("1.0.0"))
c.check_live("com.example/inventory", "1.0.0", sample_live("1.0.0", True))          # Lab B
c.admit(sample_record("1.1.0"), meta, "com.example", evidence_for("1.1.0"), sample_live("1.1.0"))  # Lab C
c.observe_registry_status("com.example/inventory", "1.1.0", "deprecated")
c.rollback("com.example/inventory", "1.1.0", "unsafe retry")
c.rollback("com.example/inventory", "1.0.0", "restore known release")
c.ledger.verify()
```

讲义说："The quarantined target is rejected. The earlier active pin is accepted. The ledger remains valid." 请推演两次 `rollback` 的实际结果和最终路由表 `c.active`，指出讲义描述的问题，并给出让 Lab C 按讲义预期运行的修改。

**Q10.** 讲义说："A record digest change under the same Registry version is a Registry integrity failure. A source digest change under the same package coordinate ... is an execution-source integrity failure." 请回答：

1. 对已经准入的 `1.0.0`，再次调用 `admit()`，传入**描述被改过**的同版本记录，现有代码会怎样？
2. 如果 `1.0.0` 已因 Registry 状态变为 deprecated 而被隔离，此时再用一份（过时缓存的）`active` 元数据调用 `admit()`，会怎样？
3. 写一个 `StrictController.admit()`，在同一 `(name, version)` 已有 pin 时检测上述两类完整性失败，并把失败记入账本。

**Q11.** 完成讲义 Practice Lab 的核心：当 live 工具集中存在 `annotations.destructiveHint == True` 的工具时，要求两名**不同**评审对**同一组** record / source / toolset digest 给出已验证签名的批准；批准不完整时在账本里保留一次 "pending-approval" 记录且不激活路由。写出实现，并给出 0 人、1 人、同一人两次、2 个不同人四种情况的结果。

**Q12.** 手算下列调用的返回值：

```python
namespace_for_domain("Docs.Example.COM.")
namespace_matches("com.example/a/b", "com.example")
namespace_matches("com.example.docs/tool", "com.example")
namespace_matches("com.example/", "com.example")
normalize_https_remote_url("https://MCP.Example.COM:443")
normalize_https_remote_url("https://mcp.example.com:8443/mcp?x=1")
normalize_https_remote_url("https://mcp.example.com/mcp#a")
normalize_https_remote_url("https://bücher.example/mcp")
```

---

## 四、面试高频题

**Q13.**（基础必考）一个 MCP 服务端已经发布在官方 Registry 上，为什么你的网关还需要自己的准入（admission）？Registry 发布能证明什么、不能证明什么？

**Q14.**（原理深挖）准入 pin 里为什么要同时钉住 recordDigest、sourceDigest、toolsetDigest 和 provenanceDigest？分别在什么情况下会变化，各自意味着什么？

**Q15.**（工程实践）请设计一条从"Registry 同步"到"路由表"的准入流水线：有哪些组件、各自需要什么权限、版本有哪些状态，如何避免客户端在审批完成前通过 `tools/list` 发现新工具？

**Q16.**（场景设计）一个已准入的服务端在没有发布新版本的情况下，突然在 live 描述符里多出了 `inventory_delete` 工具。你的系统应该如何检测、响应和恢复？

**Q17.**（追问型）你的准入账本用了哈希链，面试官问："那它是不是就防篡改了？"你怎么回答？还需要做什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

代码：

```python
def namespace_matches(server_name: str, verified_namespace: str) -> bool:
    prefix, separator, slug = server_name.partition("/")
    return separator == "/" and bool(slug) and prefix == verified_namespace
```

- A 错：`"com.exampleevil/tool".startswith("com.example")` 为 `True`（已实际运行验证），这正是讲义 Lab A 要你观察的越界。
- C 错：子串匹配更宽松。
- D 错：讲义 "pass the verified namespace into admission from the authentication result. Do not derive trust from the untrusted record."

### Q2 — 答案：D

`registry_status()` 只读 `api_meta[OFFICIAL_META_KEY]["status"]`。测试 `test_registry_status_requires_namespaced_official_metadata` 传入 `{"status": "active"}`，结果是 "registry status is missing, not active"。

- A 错：发布记录的 `_meta` 只允许 `publisher-provided` 键（`_record_errors` 拒绝其他键），发布者不能给自己设官方状态。
- B 错：讲义 "A direct `_meta.status` value is not the official wire shape."
- C 错：`serverInfo` 是自报诊断信息，没有任何权威性。

### Q3 — 答案：A

`check_live` 发现 1.1.0 漂移时，除了隔离 pin，还执行 `self.active.pop(server_name)`——路由表里已经没有这个服务了。随后 `observe_registry_status` 只是把已隔离的 1.1.0 再标记一次。`rollback` 中 `previous = self.active.get(server_name)` 得到 `None`，所以证据是 `{"from": None, "to": "1.0.0", "reason": "unexpected delete tool"}`（已实际运行验证）。

这也提醒我们：在漂移被检测到、到回滚执行之前，这个服务**没有任何活跃路由**——这是"宁可不服务也不服务错"的选择。

- B：如果没有 live check 那一步才会是 1.1.0。
- D 错：用的是 `.get()`，不会抛异常。

### Q4 — 答案：C

`normalized_tools` 按 `(name, canonical_json(item))` 排序后再哈希，列表顺序被归一化，测试 `test_tool_order_does_not_create_false_drift` 正是验证这一点。A、B、D 都改变了描述符内容，toolsetDigest 必然变化。讲义："A production policy may allow an editorial change only through a new review, because descriptions influence model tool selection. 'Cosmetic' metadata can alter agent behavior."

### Q5 — 答案：A

`reported_server_info(live)` 只是把 `_meta[SERVER_INFO_KEY]` 深拷贝进 pin 的 `reportedServerInfo`，准入逻辑从不读取它。测试 `test_spoofed_server_info_does_not_change_admission_authority` 断言准入通过且 `reportedServerInfo["name"] == "org.attacker/pretend"`。pin 的 `server` 来自记录名，与 `serverInfo` 无关。

- B 错：代码不会用自报信息做任何安全判断（虽然生产中可以把"不一致"作为告警信号，但不能作为准入权威）。
- C、D 错：自报值不会改写任何权威字段。

### Q6 — 答案：C

`rollback` 的条件：pin 存在、未隔离、`registryStatus == "active"`。

- A 错：没有 pin → "rollback target has no admission pin"。讲义：回滚目标必须有完整的准入记录。
- B 错：漂移已把它隔离。
- D 错：状态变为 deleted 时 `observe_registry_status` 会隔离它。

### Q7 — 答案：D

已实际运行验证：删除最后一条记录后 `verify()` 仍为 `True`；修改第 1 条后按顺序重新计算所有 `previousHash` / `entryHash`，`verify()` 也为 `True`。这正是讲义说的 "tamper-evident, not magically tamper-proof"，需要把账本头锚定到独立信任域（签名发布元数据、一次写入存储）。

- A 错：同上。
- B 错：修改第 1 条后它的 `entryHash` 不再匹配，`verify()` 在第 1 条就返回 `False`；即使只重算第 1 条的哈希，第 2 条的 `previousHash` 也对不上——"breaks verification of that entry and every later link"。
- C 错：`verify()` 只检查 sequence、previousHash、entryHash，不检查时间。

### Q8 — 答案：B

讲义："The Registry schema version and the MCP protocol version are independent ... Never infer one from the other." `sample_record` 的 `$schema` 是 2025-12-11，`sample_live` 的 `supportedVersions` 是 `["2026-07-28"]`，准入正常通过。控制器只检查 live 结果中是否含 `PROTOCOL_VERSION`。

### Q9 — 参考答案

实际运行结果（已在本地执行验证）：

```text
1 admission     1.0.0 approved
2 live-check    1.0.0 drifted      ['live tool descriptors differ from the admitted pin']
3 admission     1.1.0 approved
4 registry-status 1.1.0 quarantined ['registry status changed to deprecated']
5 rollback      1.1.0 rejected     ['rollback target is not eligible or is quarantined']
6 rollback      1.0.0 rejected     ['rollback target is not eligible or is quarantined']
verify() = True，c.active = {}
```

问题：Lab B 对 **1.0.0** 做了 live check 并观察到额外工具，这一步已经把 1.0.0 隔离了；Lab C 再想回滚到 1.0.0 时它不再合格，两次回滚**都被拒绝**，最终没有任何活跃路由。讲义说"The earlier active pin is accepted"与代码行为不符（单独运行 Lab C、或像 `main.py` 那样对 1.1.0 做漂移检查时才符合）。

修改方式（任选其一）：

1. Lab C 开头新建一个控制器，重新准入 1.0.0；
2. 把 Lab B 的漂移检查对象改成 1.1.0（与 `demo()` 一致）；
3. 在讲义中明确说明："由于 Lab B 已隔离 1.0.0，两个回滚都会被拒绝——被漂移隔离的版本永远不是回滚目标"，这本身也是一个很好的教学点。

### Q10 — 参考答案

1. **静默覆盖**。`admit()` 不检查 `(name, version)` 是否已有 pin，直接 `self.pins[(name, version)] = deepcopy(pin)`，于是同版本的不同记录被准入，recordDigest 被替换（已验证：返回 `allowed=True`，新旧 recordDigest 不同）。讲义把这种情况定义为 Registry 完整性失败，代码没有实现。
2. **隔离被清除并重新激活**。新 pin 的 `quarantined` 是 `False`，`self.active[name] = version` 也被执行（已验证：`quarantined` 从 `True` 变回 `False`，路由指回 1.0.0）。一份过期缓存的 `active` 元数据就能撤销隔离。
3. 参考实现（已运行验证：改描述 → 拒绝；改 source digest → 拒绝；相同证据 → 允许；账本仍有效）：

```python
class StrictController(RegistryAdmissionController):
    def admit(self, record, api_meta, verified_namespace, provenance_evidence, live, **kw):
        key = (record.get("name"), record.get("version")) if isinstance(record, dict) else None
        old = self.pins.get(key)
        if old is not None:
            reasons = []
            if old["quarantined"]:
                reasons.append("version is quarantined; re-admission needs a new review")
            if digest(record) != old["recordDigest"]:
                reasons.append("record digest changed under the same registry version")
            if provenance_evidence.get("digest") != old["sourceDigest"]:
                reasons.append("source digest changed under the same source coordinate")
            if reasons:
                self.ledger.append("admission", key[0], key[1], "integrity-failure", reasons,
                                   {"pinned": old["recordDigest"], "observed": digest(record)})
                return Decision(False, tuple(reasons))
        return super().admit(record, api_meta, verified_namespace, provenance_evidence, live, **kw)
```

要点：完整性失败要**保留两个 digest** 作为调查证据（讲义失败模式表："retain both digests, investigate the fetch boundary"），而不是悄悄更新 pin。

### Q11 — 参考答案

参考实现（继承原控制器；已运行验证四种情况）：

```python
class TwoPersonController(RegistryAdmissionController):
    def admit_with_approvals(self, record, api_meta, verified_namespace,
                             provenance_evidence, live, approvals):
        tools = live.get("tools", []) if isinstance(live, dict) else []
        destructive = any(
            isinstance(t, dict) and isinstance(t.get("annotations"), dict)
            and t["annotations"].get("destructiveHint") is True
            for t in tools if isinstance(tools, list)
        )
        target = {                                     # 批准必须针对这三个精确 digest
            "recordDigest": digest(record),
            "sourceDigest": provenance_evidence.get("digest"),
            "toolsetDigest": digest(normalized_tools(tools)) if isinstance(tools, list) else None,
        }
        valid = [a for a in approvals
                 if a.get("signatureVerified") is True and a.get("approves") == target]
        reviewers = [a["reviewer"] for a in valid]
        reasons = []
        if len(reviewers) != len(set(reviewers)):
            reasons.append("duplicate reviewer identity")
        if destructive and len(set(reviewers)) < 2:
            reasons.append("destructive toolset needs two distinct reviewer approvals")
        if reasons:
            self.ledger.append("admission", record.get("name", "<missing>"),
                               record.get("version", "<missing>"), "pending-approval", reasons,
                               {**target, "approvalRefs": [a["ref"] for a in valid]})  # 只存引用
            return Decision(False, tuple(reasons))
        decision = self.admit(record, api_meta, verified_namespace, provenance_evidence, live)
        if decision.allowed:
            self.pins[(record["name"], record["version"])]["approvalRefs"] = [a["ref"] for a in valid]
        return decision
```

运行结果（live 中 `inventory_delete` 带 `destructiveHint: true`）：

| 情况 | allowed | reasons | 账本 | 路由 |
|------|---------|---------|------|------|
| 0 人 | False | 需要两名不同评审 | `pending-approval` | 空 |
| 1 人（alice） | False | 需要两名不同评审 | `pending-approval` | 空 |
| alice 两次 | False | 重复评审身份；需要两名不同评审 | `pending-approval` | 空 |
| alice + bob | True | — | `approved` | 1.0.0 |

设计要点：批准对象是"三个 digest 的组合"，任何一个变化都会让旧批准失效；账本里只存签名**引用**（`ref`），不存签名本身和凭据；`signatureVerified` 应由独立的签名校验组件给出。注意本节 `sample_live` 的工具都没有 `annotations` 字段，需要自己加上 `destructiveHint` 才能触发该门。（简化：这里把批准记录直接附在 pin 上；更严格的做法是让批准引用也进入 provenanceDigest。）

### Q12 — 参考答案

已实际运行验证：

| 调用 | 结果 | 原因 |
|------|------|------|
| `namespace_for_domain("Docs.Example.COM.")` | `"com.example.docs"` | 去首尾空白与末尾点、转小写、按 `.` 反转 |
| `namespace_matches("com.example/a/b", "com.example")` | `True` | `partition` 只切第一个 `/`，slug 为 `a/b` 非空 |
| `namespace_matches("com.example.docs/tool", "com.example")` | `False` | 精确比较：子域名命名空间需要单独验证 |
| `namespace_matches("com.example/", "com.example")` | `False` | slug 为空 |
| `normalize_https_remote_url("https://MCP.Example.COM:443")` | `"https://mcp.example.com/"` | 主机小写、去掉默认端口 443、空路径补成 `/` |
| `...("https://mcp.example.com:8443/mcp?x=1")` | `"https://mcp.example.com:8443/mcp?x=1"` | 非默认端口保留，query 保留 |
| `...("https://mcp.example.com/mcp#a")` | `None` | 拒绝 fragment |
| `...("https://bücher.example/mcp")` | `"https://xn--bcher-kva.example/mcp"` | 国际化域名转 IDNA（punycode） |

`namespace_for_domain("localhost")` 会抛 `ValueError`（至少需要两个标签）。

### Q13 — 参考回答要点

- **Registry 发布能证明**：发布者通过了命名空间认证（域名或 GitHub），记录符合 schema、包所有权检查等发布规则；发布元数据不可变，版本唯一。
- **不能证明**：你实际下载/连接到的制品就是那个（需要可信边界算出的 digest）；运行中的端点现在暴露什么工具（需要 live discovery）；它符合你组织的数据、网络、权限策略；它现在仍然 active。
- **四个事实、四个权威**：发布者 → Registry；制品 → 包注册表；运行时行为 → 端点；批准 → 你的组织。讲义："Collapsing those facts into 'it is in the registry, so trust it' creates a supply chain blind spot."
- **操作规则**："Publication answers 'can this identity publish this name?' Admission answers 'will we execute this exact artifact and expose this exact behavior?'"
- 加分点：举出四个失败例子——有效发布后被 deprecated；包 tag 指向意外制品；审核后新增破坏性工具；回滚选中从未准入的版本。

### Q14 — 参考回答要点

| digest | 内容 | 同版本下变化意味着 |
|--------|------|------------------|
| recordDigest | 规范化 JSON 的发布记录 | Registry 完整性失败（发布元数据本应不可变） |
| sourceDigest | 可信边界算出的制品 / 远程部署证据 digest | 执行来源完整性失败（同一包坐标给了不同字节，或远程部署变了） |
| toolsetDigest | 归一化后的完整工具描述符 | 运行时漂移（新工具、改 schema、改描述、改注解） |
| provenanceDigest | 把 registrySource、server、version、recordDigest、source、sourceDigest 连在一起的 join | 一个紧凑的"证据集指针"，任一组成部分变化都会变 |

- 多层 pin 的价值在于**定位**：知道是哪一层变了，才能决定找谁（Registry、包分发、部署团队）。
- provenanceDigest 只是指针，讲义："It is not a substitute for retaining the evidence."
- 常见误区：只钉版本号（`1.0.0` 或更糟的 `^1.4` / `latest`）；把 digest 交给被验证的制品自己报告。

### Q15 — 参考回答要点

- **流水线**：`Registry sync → artifact verifier → live discovery → admission controller → route table`，旁路写 evidence store 和 admission ledger。
- **最小权限、独立身份**：sync worker 只读 Registry 元数据；artifact verifier 只有包拉取权限；route reconciler 只能激活已批准的 pin；谁都不持有全部凭据。
- **状态显式化**：Approved（证据通过策略）、Active（路由当前选中）、Quarantined（不能接新流量）、Superseded（另一个已准入版本在用）——讲义："Do not encode all four meanings in one Boolean." 注意本节代码 `admit()` 一通过就 `self.active[name] = version`，把"批准"和"激活"耦合在一起，甚至准入一个更旧的版本也会把路由切过去（已验证），生产中应拆开。
- **避免发现窗口**：在把服务端暴露到 `tools/list` 之前完成准入，否则客户端可能在"发布到审批之间"的空窗发现工具。
- **持续对账**：定时同步 Registry 状态（包括 deleted / incremental 视图）、重拉制品、重做 live discovery；激活前再检查一次。
- 加分点：证据收集阶段就做脱敏（不存 bearer token、cookie、包凭据、工具参数）。

### Q16 — 参考回答要点

- **检测**：定时（以及每次激活前）调用 `server/discover` 拿工具描述符，按名字归一化后哈希，与 pin 的 toolsetDigest 比较；新工具必然导致不一致。
- **响应**：立即隔离该 pin、从路由表移除（本节 `check_live` 正是这样做）、记账本、保留新的描述符观测作为证据；被漂移隔离的版本不能作为回滚目标。
- **恢复**：回滚到另一个仍合格的已准入版本（以前准入、active、未隔离；生产中还要重拉制品、重查 live、过健康检查）；同时调查原因——是部署错了、被入侵，还是服务端在同一版本下改了行为。
- **重新上线**：如果新工具是合法的，要求发布新版本并走完整准入（必要时两人审批，因为它带破坏性）；不能"静默更新 pin"。
- 加分点：解释为什么"只是描述变了"也要重新审核——描述会影响模型的工具选择；以及工具投毒（tool poisoning）的风险。

### Q17 — 参考回答要点

- **能做到**：哈希链是 tamper-**evident**——修改任何一条历史记录都会让该条及之后所有链接校验失败。
- **做不到**：
  - 能写存储的攻击者可以从被改的那一条开始重算全部哈希，整条链依然自洽；
  - 截掉最后几条记录，剩下的链仍然有效（已实际验证 `verify()` 返回 `True`）；
  - 不校验时间是否单调、是否可信。
- **还需要**：
  - 定期把账本头（最新 entryHash + sequence）锚定到独立信任域：签名的发布元数据、一次写入（WORM）存储、外部透明日志；
  - 限制谁能追加；追加操作本身要认证和审计；
  - 外部锚点里记录 sequence，才能发现截尾；
  - 证据最小化，不存凭据和工具参数。
- 加分点：类比 Certificate Transparency / 透明日志的思路；说明"本地自洽"和"外部可验证"的区别。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关与注册表的基本角色，本节在其上加入供应链证据。
- [阶段 13 · 18 生产环境中的 MCP 认证：绑定签发者的注册与 Tokens](../../18-mcp-auth-production/docs/zh.md)：命名空间与端点所有权验证的认证基础。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：为什么工具描述的"表面变化"也是安全问题。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../28-mcp-tool-contracts-and-content/docs/zh.md)：工具描述符、schema 与注解（如 `destructiveHint`）。

### 本节被哪些后续内容用到
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：把准入证据扩展成一致性测试与发布门禁。
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：在综合项目中落地准入、漂移检测与回滚。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：路由切换与回滚的生产实践。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：审计日志与证据脱敏。

### 延伸关键词
`MCP Registry` · `server.json` · `reverse-DNS namespace` · `provenance` · `artifact digest` · `SLSA / Sigstore` · `pinning` · `descriptor drift` · `server/discover` · `serverInfo` · `deprecated / deleted status` · `quarantine` · `route restoration` · `hash chain` · `transparency log` · `two-person rule`
