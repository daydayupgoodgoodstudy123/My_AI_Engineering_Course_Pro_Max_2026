# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 30 节 MCP 注册表供应链：准入、漂移与 Rollback ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（演示）；`python3 -m unittest discover -s tests -v`（测试） ｜ **依赖**：仅标准库（`hashlib`、`json`、`copy`、`dataclasses`、`datetime`、`typing`、`urllib.parse`），无需网络

---

## 1. 这份代码在考察什么

这份代码实现了一个**准入控制器（admission controller）**，坐在"Registry 发现"和"路由表"之间，把讲义的七个控制点写成可执行的规则：

1. **命名空间精确匹配**：`namespace_for_domain` / `namespace_matches`。
2. **Provenance join**：把记录中声明的包或远程端点，与外部给出的"已验证所有权 + 可信 digest"逐字段对上（`_source_errors`）。
3. **钉住决策**：pin 里同时有 recordDigest、sourceDigest、toolsetDigest、provenanceDigest、registryStatus。
4. **运行时漂移检测**：`check_live` 重算工具描述符 digest 并与 pin 比较。
5. **Registry 状态同步**：`observe_registry_status` 在状态离开 `active` 时隔离并下线。
6. **回滚 = 恢复路由**：`rollback` 只接受"准入过、active、未隔离"的版本。
7. **防篡改账本**：`AdmissionLedger` 的哈希链。

它还演示了几条"信任边界"上的细节：只认响应级官方元数据里的状态、发布者 `_meta` 只能用 publisher-provided 键、`serverInfo` 只是诊断、远程 URL 的规范化与拒绝规则、每次返回 pin 都做深拷贝。

> 一句话：**"在 Registry 里"只是起点；准入要证明你拉到了什么、看到了什么、批准了什么、能安全恢复到什么——并把每一步写进可校验的账本。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROTOCOL_VERSION` / `PUBLISHER_META_KEY` / `OFFICIAL_META_KEY` / `SERVER_INFO_KEY` | 常量 | 协议版本 `2026-07-28` 与三个命名空间化的 `_meta` 键 | 元数据边界 |
| `canonical_json` / `digest` | 函数 | 规范化 JSON → SHA-256 | 确定性证据 |
| `namespace_for_domain` / `namespace_matches` | 函数 | 域名反转；命名空间精确比较 | 控制 1 |
| `normalized_tools` | 函数 | 按名字（再按内容）排序工具列表 | 控制 4 的归一化 |
| `registry_status` | 函数 | 只从 `api_meta[OFFICIAL_META_KEY]["status"]` 读状态 | 控制 5 |
| `is_sha256_digest` | 函数 | 64 位十六进制校验 | 证据格式 |
| `normalize_https_remote_url` / `is_valid_https_remote_url` | 函数 | HTTPS 远程 URL 规范化与拒绝规则 | 远程来源 |
| `reported_server_info` | 函数 | 取出 `_meta` 下的 `serverInfo`（深拷贝），仅诊断 | serverInfo 无权威 |
| `Decision` | frozen dataclass | `allowed`、`reasons`、`pin` | 决策结果 |
| `AdmissionLedger` | 类 | `append` 追加带哈希链的记录；`verify` 校验 | 控制 7 |
| `RegistryAdmissionController` | 类 | `_record_errors` / `_source_errors` / `_live_errors` 三类校验；`admit`、`check_live`、`observe_registry_status`、`rollback` | 控制 2–6 |
| `sample_record` / `sample_live` / `evidence_for` | 函数 | 生成演示和测试用的记录、live 结果、包证据 | 夹具 |
| `demo` | 函数 | 五步演示，打印 JSON 报告 | 演示 |

数据流：`demo()` → `admit(1.0.0)` → `admit(1.1.0)`（路由切到 1.1.0）→ `check_live(1.1.0, 多了 delete 工具)`（隔离并下线）→ `observe_registry_status(1.1.0, deprecated)` → `rollback(1.0.0)`（路由恢复）→ 打印报告与 `ledger.verify()`。

---

## 3. 逐段精讲

### 3.1 规范化与摘要

```python
def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
```

- `sort_keys=True`：字典键顺序不影响结果（实测把工具 dict 的键顺序反过来，digest 不变）。
- `separators=(",", ":")`：去掉空格，避免格式差异。
- `ensure_ascii=True`：非 ASCII 字符转成 `\uXXXX`，例如 `{"b":1,"a":"é"}` → `{"a":"é","b":1}`，跨平台字节一致。
- 这是全文件所有 digest（记录、工具集、provenance、账本条目）的唯一入口，保证"同样的内容 → 同样的哈希"。
- ⚠️ 规范化只作用于字典键；**列表顺序仍然有意义**。例如 `inputSchema.required` 从 `["sku","loc"]` 变成 `["loc","sku"]`，语义不变但 digest 会变（实测为漂移）。讲义说"只归一化顺序无意义的字段"，`required` 恰好是顺序无意义却没被归一化的一个例子——这是偏保守的误报，而不是漏报。

### 3.2 命名空间

```python
def namespace_for_domain(domain: str) -> str:
    labels = [label.lower() for label in domain.strip().strip(".").split(".") if label]
    if len(labels) < 2:
        raise ValueError("a verified namespace domain needs at least two labels")
    return ".".join(reversed(labels))

def namespace_matches(server_name: str, verified_namespace: str) -> bool:
    prefix, separator, slug = server_name.partition("/")
    return separator == "/" and bool(slug) and prefix == verified_namespace
```

- `namespace_for_domain("Docs.Example.COM.")` → `"com.example.docs"`：去空白、去首尾的点、转小写、反转。单标签（如 `localhost`）被拒绝。
- `str.partition("/")` 只在**第一个** `/` 处切成三段，没有 `/` 时 `separator` 为空字符串。
- 三个条件：必须有 `/`；slug 非空；前缀**完全相等**。`startswith` 会放行 `com.exampleevil/...`（讲义 Lab A）。
- 精确比较也意味着：验证了 `com.example` 并不自动覆盖 `com.example.docs/...`（实测 `False`），子域命名空间需要自己的验证输入。
- 比较是大小写敏感的，`namespace_for_domain` 产出的总是小写；如果记录名里有大写（`COM.example/x`），会被拒绝。
- 最关键的不是这个函数本身，而是 `verified_namespace` **从哪来**：`admit()` 把它作为独立参数接收，必须来自认证流程，而不是从 `record["name"]` 推出来。

### 3.3 Registry 状态与 serverInfo

```python
def registry_status(api_meta: dict[str, Any]) -> str:
    official = api_meta.get(OFFICIAL_META_KEY) if isinstance(api_meta, dict) else None
    return str(official.get("status", "")) if isinstance(official, dict) else ""

def reported_server_info(live: Any) -> dict[str, Any] | None:
    if not isinstance(live, dict):
        return None
    metadata = live.get("_meta")
    value = metadata.get(SERVER_INFO_KEY) if isinstance(metadata, dict) else None
    return deepcopy(value) if isinstance(value, dict) else None
```

- 状态只从**响应级** `_meta["io.modelcontextprotocol.registry/official"]` 读；直接的 `_meta.status` 返回空字符串，被当作 "missing"。
- 每一层都先 `isinstance` 检查，任何畸形输入都只会得到 `""`，不会抛异常。
- ⚠️ `str(...)` 会把 `None` 变成字符串 `"None"`，报错信息会是 "registry status is None, not active"——不影响安全（仍然不是 `active`），只是信息不够准确。
- `reported_server_info` 只认 `_meta` 下的键；`live["serverInfo"]` 这种别名被忽略（测试 `test_server_info_is_diagnostic_and_direct_alias_has_no_authority` 断言 pin 中为 `None`）。返回深拷贝，调用方改不到原对象。

### 3.4 远程 URL 规范化

```python
    decoded = unquote(value)
    if any(
        character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
        for character in value + decoded
    ):
        return None
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
        port = parsed.port
    except ValueError:
        return None
```

逐条规则：

| 规则 | 拒绝的例子 | 为什么 |
|------|-----------|--------|
| 原文或 URL 解码后含空白/控制字符 | `.../m cp`、`...\t`、`...%0Aadmin` | 防止日志注入、请求走私、解析歧义 |
| 解析失败（`ValueError`） | `https://[2001:db8::1/mcp`（括号不闭合）、端口 70000 | `urlparse` 的属性访问会对非法端口/IPv6 抛错，统一转为拒绝 |
| scheme 不是 `https` | `http://...` | 远程来源必须加密 |
| 没有主机 | `https:///mcp` | — |
| 含用户名/密码 | `https://learner:secret@...` | 凭据不能出现在记录和证据里 |
| 含 fragment | `...#alternate` | fragment 不发往服务器，会造成"看起来不同、实际相同"的歧义 |

通过后的规范化：

```python
    normalized_host = hostname.lower()
    if ":" in normalized_host:
        normalized_host = f"[{normalized_host}]"
    else:
        normalized_host = normalized_host.encode("idna").decode("ascii")
    netloc = normalized_host
    if port is not None and port != 443:
        netloc = f"{netloc}:{port}"
    return urlunparse(("https", netloc, parsed.path or "/", parsed.params, parsed.query, ""))
```

- 主机转小写；IPv6（含 `:`）重新加方括号；其余转 IDNA（`bücher.example` → `xn--bcher-kva.example`）。
- 默认端口 443 去掉，非默认端口保留；空路径补成 `/`；query 保留；fragment 置空。
- 于是 `https://MCP.Example.COM:443` 和 `https://mcp.example.com/` 规范化后相同（测试 `test_remote_urls_are_normalized_before_evidence_matching_and_pinning`），记录和证据可以按规范形式对上，pin 里也存规范形式。

### 3.5 `AdmissionLedger`：哈希链

```python
    def append(self, event, server_name, version, outcome, reasons, evidence):
        body = {
            "sequence": len(self.entries) + 1,
            "time": self.clock(),
            "event": event,
            "server": server_name,
            "version": version,
            "outcome": outcome,
            "reasons": list(reasons),
            "evidence": deepcopy(evidence),
            "previousHash": self.entries[-1]["entryHash"] if self.entries else "GENESIS",
        }
        entry = {**body, "entryHash": digest(body)}
        self.entries.append(entry)
        return entry
```

- 每条记录的哈希覆盖它的全部内容**加上前一条的哈希**，形成链。第一条的 `previousHash` 是字符串 `"GENESIS"`。
- `deepcopy(evidence)`：账本持有自己的副本，调用方后续修改 pin 不会改到历史记录。
- `clock` 可注入：默认用 UTC 当前时间（去掉微秒，ISO 格式），测试和演示传入固定的时间迭代器，结果完全确定。

```python
    def verify(self) -> bool:
        previous_hash = "GENESIS"
        for expected_sequence, entry in enumerate(self.entries, start=1):
            body = {key: value for key, value in entry.items() if key != "entryHash"}
            if entry.get("sequence") != expected_sequence: return False
            if entry.get("previousHash") != previous_hash: return False
            if entry.get("entryHash") != digest(body): return False
            previous_hash = entry["entryHash"]
        return True
```

- 三项检查：序号连续、链接正确、自身哈希正确。
- ⚠️ 实测两种情况仍返回 `True`：**截掉末尾若干条**；**从被改处开始重算全部哈希**。这正是讲义说的 "tamper-evident, not magically tamper-proof"——要把账本头（含 sequence）锚定到独立信任域。
- ⚠️ 不检查时间单调；`entries` 是公开的 list，谁都能改。

### 3.6 `_record_errors`：记录结构

- `name`、`version`、`description` 必须是非空字符串。
- 至少声明一个 package 或一个 remote（**只有 remote 的记录合法**，讲义特别强调不能因为缺 package 而拒绝）。
- 每个 package 需要 `registryType`、`identifier`、`version`、`transport.type`；每个 remote 的 `type` 必须是 `streamable-http` 或 `sse`，`url` 必须通过 `is_valid_https_remote_url`。
- 发布记录的 `_meta` 只能包含 `PUBLISHER_META_KEY`，否则 "record._meta contains a non-publisher key"——发布者不能塞入 `io.modelcontextprotocol.registry/official` 冒充官方状态。
- 所有错误**累积**到列表里，一次返回全部原因，便于排查。
- ⚠️ 不校验版本字符串的形态：实测 `version="^1.4"` 或 `"latest"` 的记录（配上同样版本的证据）可以被准入。讲义说它们"不是 admission pin"，真实 Registry 会拒绝版本范围，但控制器本身没有这道防线。

### 3.7 `_source_errors`：provenance join

```python
        kind = provenance_evidence.get("kind", "package")
        if kind == "remote":
            ...
            evidence_url = normalize_https_remote_url(provenance_evidence.get("url"))
            remote = next((item for item in candidates
                           if evidence_url is not None
                           and normalize_https_remote_url(item.get("url")) == evidence_url), None)
            if remote is None: errors.append("verified remote endpoint is absent from the registry record"); return errors, None
            if remote.get("type") != provenance_evidence.get("transportType"): ...
            if provenance_evidence.get("verified") is not True: ...
            if not is_sha256_digest(provenance_evidence.get("digest")): ...
            source = deepcopy({"kind": "remote", **remote})
            source["url"] = evidence_url
            return errors, source
```

- 证据缺省 `kind` 时按 package 处理；未知 kind 直接拒绝。
- **remote**：按规范化 URL 在记录的 remotes 里找匹配项；再要求 transport 一致、`verified is True`（严格等于 `True`，`"yes"`、`1` 都不算）、digest 是合法 SHA-256。pin 的 `source.url` 存规范化后的 URL。
- **package**：按 `identifier` 找第一个匹配的 package，再逐项比 `registryType`、`transport.type`、`version`、`verified`、digest。
- `next(generator, None)`：取第一个满足条件的元素，没有则 `None`。
- 返回 `(errors, source)`：即使有错误也可能返回 source，但 `admit()` 只要有任何 reason 就不会使用它。
- ⚠️ `{"kind": "package", **package}` 中 `**package` 在后，如果记录里的 package 自带 `kind` 键会覆盖它（实测可以把 source 的 kind 变成 `"remote"`）。安全上影响不大，但写成 `{**package, "kind": "package"}` 更稳妥。
- ⚠️ 按 identifier 只取**第一个**匹配：若记录里同一 identifier 同时出现在 pypi 和 npm 两个 package 中，证据对应第二个时会被误判为类型不匹配。
- 讲义提醒："Never accept a digest supplied only by the artifact you are trying to verify." 这里的 `verified` 和 `digest` 被假定来自可信的制品校验器——控制器本身无法验证它们的真实性。

### 3.8 `_live_errors`：运行时证据

- `supportedVersions` 必须是字符串列表且包含 `2026-07-28`。
- `capabilities` 必须是 dict，且包含 `required_capabilities`（默认 `("tools",)`）中的每一项。
- `tools` 必须是列表；每个工具需要非空 `name`、非空 `description`、dict 类型的 `inputSchema`。
- ⚠️ 不检查工具名唯一：实测两个同名 `inventory_get`（一个描述被改成 "Delete everything"）不报错。MCP 要求工具名唯一，重名会让路由和审核产生歧义。
- ⚠️ 空工具列表 `[]` 也通过。

### 3.9 `admit()`：汇总四类证据

```python
        reasons = self._record_errors(record)
        status = registry_status(api_meta)
        if status != "active":
            reasons.append(f"registry status is {status or 'missing'}, not active")
        if not namespace_matches(name, verified_namespace):
            reasons.append("server name is outside the verified namespace")
        source_errors, source = self._source_errors(record, provenance_evidence)
        reasons.extend(source_errors)
        reasons.extend(self._live_errors(live))
```

- 顺序：记录结构 → Registry 状态 → 命名空间 → 来源 → 运行时，**全部累积**，不短路。
- 拒绝时也写账本：`"rejected"` + 全部原因 + 最小证据（recordDigest、registrySource、status、verifiedNamespace）。拒绝同样是需要解释的决定。
- 通过时构造 provenance 对象（registrySource、server、registryVersion、recordDigest、source、sourceDigest）并哈希得到 `provenanceDigest`；pin 里再加 `toolsetDigest = digest(normalized_tools(live["tools"]))`、`reportedServerInfo`、`quarantined=False`。
- `assert source is not None`：走到这里时没有任何错误，source 必然存在；这行同时是给类型检查器和读者的说明。
- 存储和返回都用 `deepcopy`：测试分别验证了"改原始记录"和"改返回的 pin"都影响不到存储的 pin。
- ⚠️ `self.active[name] = version`：**准入即激活**。讲义 Use It 一节要求把 Approved / Active / Quarantined / Superseded 四种状态分开，代码把前两者耦合了；实测先准入 2.0.0 再准入 0.9.0，路由会被切到 0.9.0。
- ⚠️ 不检查 `(name, version)` 是否已有 pin：同版本的不同记录会**静默覆盖** pin（讲义把它定义为 Registry 完整性失败），已隔离的版本也会因为重新准入而被解除隔离并重新激活（实测）。参考修复见测验 Q10。

### 3.10 `check_live()`：漂移检测

```python
        reasons = self._live_errors(live)
        tools = live.get("tools") if isinstance(live, dict) else None
        tools_valid = isinstance(tools, list) and all(isinstance(tool, dict) for tool in tools)
        observed_toolset = digest(normalized_tools(tools)) if tools_valid else None
        if tools_valid and observed_toolset != pin["toolsetDigest"]:
            reasons.append("live tool descriptors differ from the admitted pin")
        if pin["quarantined"]:
            reasons.append("version is quarantined")
        if reasons:
            pin["quarantined"] = True
            if self.active.get(server_name) == version:
                self.active.pop(server_name)
```

- 没有 pin 的版本直接拒绝，不记账本。
- 畸形描述符（如 `tools=[None]`）也被视为漂移：`_live_errors` 给出原因，`tools_valid=False` 时不计算 digest，避免 `normalized_tools` 在非 dict 上崩溃。
- 一旦有原因：隔离 pin；若它正是活跃版本则从路由表移除。
- 已隔离的版本每次 live check 都会继续报 "version is quarantined"——隔离是**单向**的，只能通过新的准入流程解除。
- 账本证据只记 `provenanceDigest` 和观测到的 toolset digest，不存完整描述符。
- 返回的 `Decision` 带 pin 的深拷贝。

### 3.11 `observe_registry_status()` 与 `rollback()`

```python
            pin["registryStatus"] = status
            if status != "active":
                pin["quarantined"] = True
                outcome = "quarantined"
                reasons.append(f"registry status changed to {status}")
                if self.active.get(server_name) == version:
                    self.active.pop(server_name)
```

- 未准入的版本：记一条 `"ignored"`。
- 状态离开 `active`（deprecated、deleted 或任何其他字符串）：隔离 + 下线 + 记账本；**不删证据**（讲义："Deletion from the default listing is not permission to erase your audit trail"）。
- 状态回到 `active` 只更新 `registryStatus`，不会解除隔离。

```python
        pin = self.pins.get((server_name, target_version))
        if pin is None:
            reasons.append("rollback target has no admission pin")
        elif pin["quarantined"] or pin["registryStatus"] != "active":
            reasons.append("rollback target is not eligible or is quarantined")
        ...
        previous = self.active.get(server_name)
        self.active[server_name] = target_version
        evidence = {"from": previous, "to": target_version, "reason": reason}
```

- 只检查讲义五个条件中的前三个（有准入记录、active、未隔离），讲义也承认 "A real reconciler should re-fetch the package and re-check the live endpoint before activation."
- 回滚**不修改任何发布记录或 pin**，只改路由表，并追加一条新事件；历史不可改写。
- `previous` 可能是 `None`（演示中正是如此，因为漂移检查已先下线了 1.1.0）。回滚到当前活跃版本也允许，证据里 `from == to`。

### 3.12 夹具与 `demo()`

- `sample_record(version)`：一个 pypi + stdio 的包记录，`$schema` 是 2025-12-11（与协议版本 2026-07-28 无关），`_meta` 只有 publisher-provided。
- `sample_live(version, extra_tool=False)`：一个 `inventory_get` 工具；`extra_tool=True` 时多一个 `inventory_delete`（没有 annotations）。`_meta` 里的 `serverInfo` 名字和版本与记录一致——但这只是诊断。
- `evidence_for(version)`：`verified=True`，digest 是对 `{"wheel": "example-mcp-inventory-<v>.whl"}` 的哈希——模拟"可信制品校验器"的输出。
- `demo()` 的时钟：`f"2026-08-21T10:00:0{second}+00:00" for second in range(9)`，只够 9 次 `append`（演示用了 5 次）；格式串 `0{second}` 在 second ≥ 10 时会变成 `010`，所以只能用于个位数——讲义 Lab B 改用了 `{n:02d}`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 可信命名空间作为独立参数 | 信任来自认证结果，而非记录文本 | 需要真实的域名/GitHub 验证服务把结果规范化成一个字符串 |
| 所有错误累积返回 | 一次看到全部问题，账本可解释 | 原因用自然语言字符串，生产应改为稳定的 reason code |
| 拒绝也写账本 | 拒绝同样是需要审计的决定 | 账本增长更快 |
| 多层 digest 的 pin | 能定位是哪一层变了 | 需要保留完整证据，digest 只是指针 |
| 只按工具名排序归一化 | 不掩盖任何描述符变化 | `required` 等无序数组重排会误报漂移 |
| 漂移/状态变化 → 隔离 + 下线 | 宁可不服务，不服务错 | 可能短时无可用版本，需要尽快回滚 |
| 隔离单向不可逆（在 check_live 中） | 防止"自愈"掩盖问题 | 但 `admit()` 重新准入会绕过它（缺陷） |
| 准入即激活 | 演示简单 | 与讲义"状态显式化"矛盾；生产要分开 Approved / Active / Superseded |
| 回滚只查三项 | 篇幅 | 生产要重拉制品、重查 live、过健康检查后再切流量 |
| 本地哈希链 | 能发现局部修改 | 截尾与整体重写检测不到；要锚定外部信任域 |
| 处处 `deepcopy` | 防止调用方别名修改存储 | 有拷贝开销，pin 很大时要考虑不可变数据结构 |
| 时钟可注入 | 测试确定 | 生产时间应来自可信时间源 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| 类型注解 `Callable[[], str]` | `clock: Callable[[], str] \| None = None` | "无参数、返回 str 的可调用对象" |
| `X \| None` | `dict[str, Any] \| None` | 可选类型（3.10+） |
| `@dataclass(frozen=True)` | `Decision` | 不可变结果对象 |
| `tuple[str, ...]` | `reasons: tuple[str, ...]` | 任意长度的字符串元组；用元组让 `Decision` 真正不可变 |
| `str.partition` | `server_name.partition("/")` | 返回 `(前, 分隔符, 后)` 三元组，只切第一次 |
| 链式字符串方法 | `domain.strip().strip(".").split(".")` | 去空白、去首尾点、切分 |
| 列表推导式 + 过滤 | `[label.lower() for label in ... if label]` | 跳过空标签 |
| `reversed` + `join` | `".".join(reversed(labels))` | 反转后拼接 |
| `all` / `any` + 生成器 | `all(character in "0123456789abcdefABCDEF" for character in value)` | 短路判断 |
| `sorted(key=lambda ...)` | `sorted(tools, key=lambda item: (str(item.get("name", "")), canonical_json(item)))` | 用元组做多级排序键 |
| `next(gen, default)` | `next((item for item in candidates if ...), None)` | 取第一个匹配项 |
| 字典解包合并 | `{**body, "entryHash": digest(body)}`、`{"kind": "remote", **remote}` | 后面的键覆盖前面的 |
| 字典推导式 | `{key: value for key, value in entry.items() if key != "entryHash"}` | 去掉某个键 |
| `enumerate(..., start=1)` | `verify()` | 从 1 开始计数 |
| `copy.deepcopy` | 多处 | 递归复制嵌套结构，断开别名 |
| 条件表达式 | `self.entries[-1]["entryHash"] if self.entries else "GENESIS"` | 三元运算 |
| `or` 提供默认值 | `clock or (lambda: ...)`、`status or 'missing'` | 左边为假值时用右边 |
| `lambda` | `lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat()` | 匿名函数 |
| `try / except ValueError` | URL 解析 | 把解析异常转成"拒绝" |
| `urllib.parse` | `urlparse`、`urlunparse`、`unquote` | 拆解/重组 URL、百分号解码 |
| `str.encode("idna")` | 主机名转 punycode | 国际化域名 |
| `ord()` | `ord(character) < 0x20` | 字符的码点，用于识别控制字符 |
| `isinstance` 防御 | `isinstance(official, dict)` | 外部输入一律先检查类型 |
| `assert` | `assert source is not None` | 内部不变量 |
| 元组作字典键 | `self.pins[(name, version)]` | 不可变元组可哈希 |
| `dict.pop` | `self.active.pop(server_name)` | 删除键并返回值 |
| 生成器表达式作迭代器 | `ticks = iter(f"...{second}..." for second in range(9))` | 每次 `next()` 取一个时间戳 |
| `json.dumps(indent=2)` | `demo()` | 美化打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `demo()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`python3 main.py`）：

```json
{
  "admitted": [
    true,
    true
  ],
  "driftAllowed": false,
  "driftReasons": [
    "live tool descriptors differ from the admitted pin"
  ],
  "rollbackAllowed": true,
  "activeVersion": "1.0.0",
  "ledgerEntries": 5,
  "ledgerValid": true
}
```

逐项解读：

- **`admitted: [true, true]`**：两个版本的记录结构、官方状态、命名空间（`namespace_for_domain("example.com")` = `com.example`）、包证据、live 结果都合格。第二次准入后路由指向 1.1.0。
- **`driftAllowed: false`**：1.1.0 的 live 观测多了 `inventory_delete`，toolsetDigest 不同；pin 被隔离，路由表中该服务被移除。注意包和 Registry 记录都没变——只有运行时变了，这正是"准入后还要持续监控"的理由。
- **`driftReasons`** 只有一条，因为 live 结果本身结构合法。
- **`rollbackAllowed: true` / `activeVersion: "1.0.0"`**：1.0.0 仍是 active、未隔离，回滚成功。
- **`ledgerEntries: 5`**：admission(1.0.0) → admission(1.1.0) → live-check(1.1.0, drifted) → registry-status(1.1.0, quarantined) → rollback(1.0.0, activated)。我们额外打印了账本，rollback 的证据是 `{"from": None, "to": "1.0.0", ...}`——漂移检查已经先下线了 1.1.0。
- **`ledgerValid: true`**：链完整。
- 讲义的 "Expected shape" 省略了 `driftReasons` 和 `ledgerEntries`，其余字段与实际输出一致。

测试运行：**25 个测试全部通过，耗时约 0.01 秒**（见第 9 节）。

另外，按讲义 Interactive Lab B → Lab C 的顺序在同一个控制器上执行时（我们实际跑过），Lab B 已把 **1.0.0** 隔离，所以 Lab C 的两次回滚**都被拒绝**，最终 `active == {}`，与讲义"The earlier active pin is accepted"不符（详见测验 Q9）。

---

## 7. 动手改一改

1. **（入门）Lab A**：把 `namespace_matches` 临时改成 `startswith`，验证 `com.exampleevil/inventory` 被放行；再改回来。
2. **（入门）让 Lab C 按讲义运行**：新建控制器、或把 Lab B 的漂移目标改为 1.1.0，确认"隔离目标被拒、1.0.0 被接受"。
3. **（进阶）同版本完整性检查**：在 `admit()` 里检测"同 `(name, version)` 但 recordDigest / sourceDigest 不同"和"已隔离版本重新准入"，记为 `integrity-failure`（参考测验 Q10）。
4. **（进阶）拆开 Approved 与 Active**：`admit()` 只写 pin，新增 `activate(server, version)`；路由切换时把旧版本标为 `superseded`。再加一条规则：默认只允许激活比当前更高的版本，降级必须走 `rollback`。
5. **（进阶）描述符校验加强**：拒绝重名工具；对 `inputSchema.required`、`enum` 等无序数组做排序后再哈希，并补测试证明"重排不漂移、增删仍漂移"。
6. **（挑战）Practice Lab 两人审批**：破坏性工具需要两名不同评审对三个 digest 的已签名批准；补齐 0 / 1 / 重复 / 2 人四个测试（参考测验 Q11）；再给账本加一个 `head()` 方法，输出 `(sequence, entryHash)` 供外部锚定，并写一个检测截尾的测试。

---

## 8. 常见坑

- **用 `startswith` 判断命名空间**：`com.exampleevil` 会越界。
- **从记录自身推导可信命名空间**：记录是不可信输入。
- **读错状态位置**：只有响应级 `_meta["io.modelcontextprotocol.registry/official"].status` 是官方状态；记录里的 `_meta`、直接的 `_meta.status`、`serverInfo` 都不是。
- **把 `serverInfo` 当身份**：它是自报的，攻击者可以写任何名字。
- **钉 `latest` 或 `^1.4`**：浮动选择会绕过审核；本代码也没有拦截这类版本字符串。
- **只钉版本号不钉 digest**：同一包坐标可能返回不同字节。
- **把列表顺序也算进漂移**：工具列表要按名字归一化；但也不要过度归一化而掩盖真实变化。
- **"只是描述变了"就静默更新 pin**：描述影响模型的工具选择，必须重新审核。
- **回滚到从未准入或已隔离的版本**：回滚必须基于证据，而不是记忆。
- **重新准入绕过隔离**：本代码的 `admit()` 会覆盖同版本 pin 并解除隔离。
- **以为哈希链防篡改**：截尾和整体重写都检测不到，需要外部锚定。
- **证据里存凭据**：bearer token、cookie、包凭据、工具参数都应在收集时脱敏；本代码的 remote `headers` 只存头名和 `isSecret` 标记，没有值。
- **`{"kind": "package", **package}` 的合并顺序**：后面的键会覆盖前面的。

---

## 9. 测试在验证什么

测试文件 `tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按路径加载 `main.py`（模块名 `lesson30_main`）。`setUp` 为每个测试创建一个时钟固定（`2026-08-21T09:00:SS`，最多 40 个时间戳）的控制器和一个 active 的官方元数据；辅助方法 `admit(version)` 用夹具完成一次标准准入。

运行：

```bash
cd phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift
python3 -m unittest discover -s code/tests -v
```

实际结果：`Ran 25 tests in 0.011s — OK`。

| 测试 | 验证的性质 |
|------|-----------|
| `test_domain_namespace_is_reversed_and_boundary_checked` | 域名反转与大小写/末尾点处理；精确边界拒绝 `com.exampleevil` |
| `test_active_verified_release_is_admitted_and_pinned` | 合格版本被准入并激活，provenanceDigest 为 64 位 |
| `test_mutating_registry_record_after_admission_cannot_rewrite_pin` | 准入后修改原始记录不影响存储的 pin |
| `test_mutating_admission_decision_cannot_rewrite_stored_pin` | 修改返回的 pin（含 `reportedServerInfo`）不影响存储 |
| `test_deprecated_release_is_rejected_before_activation` | 状态为 deprecated 时拒绝，原因文本精确 |
| `test_registry_status_requires_namespaced_official_metadata` | 直接 `{"status": "active"}` 被视为缺失 |
| `test_unverified_package_provenance_is_rejected` | `verified=False` 被拒 |
| `test_unknown_publication_metadata_key_is_rejected` | 记录 `_meta` 里出现非 publisher 键被拒 |
| `test_tool_order_does_not_create_false_drift` | 工具列表倒序后 live check 仍健康 |
| `test_new_live_tool_is_detected_as_descriptor_drift` | 新工具 → 漂移、下线、隔离，且不能回滚到它 |
| `test_mutating_live_check_decision_cannot_rewrite_stored_pin` | live check 返回的 pin 是拷贝 |
| `test_server_info_is_diagnostic_and_direct_alias_has_no_authority` | `_meta` 外的 `serverInfo` 别名被忽略，pin 中为 `None` |
| `test_spoofed_server_info_does_not_change_admission_authority` | 伪造的 `serverInfo` 不影响准入，只被原样记录 |
| `test_package_registry_type_and_transport_must_match_evidence` | registryType、transport 不一致各给出一条原因 |
| `test_verified_remote_only_record_is_admitted_without_package_claims` | 只有 remote 的记录可以准入，source.kind 为 remote |
| `test_cleartext_http_remote_is_rejected` | `http://` 远程被拒 |
| `test_malformed_or_credentialed_remote_urls_are_rejected_without_crashing` | 8 种畸形 URL（IPv6 括号、userinfo、无主机、非法端口、fragment、空格、tab、编码换行）都被拒且不崩溃 |
| `test_remote_urls_are_normalized_before_evidence_matching_and_pinning` | `https://MCP.Example.COM:443` 与 `https://mcp.example.com/` 能匹配，pin 存规范形式 |
| `test_mutating_remote_record_after_admission_cannot_rewrite_pin` | remote 的 `headers` 被深拷贝进 pin |
| `test_malformed_packages_and_tools_refuse_without_crashing` | `packages=["not-an-object"]` 被拒；`tools=[None]` 的 live check 失败并隔离 |
| `test_status_change_quarantines_and_deactivates_release` | deleted → 隔离、下线、账本仍有效 |
| `test_rollback_activates_a_previously_admitted_healthy_version` | 1.1.0 deprecated 后回滚到 1.0.0 成功 |
| `test_mutating_rollback_decision_cannot_rewrite_stored_pin` | 回滚返回的 pin 是拷贝 |
| `test_rollback_rejects_quarantined_target` | 被状态隔离的版本不能作为回滚目标 |
| `test_ledger_hash_chain_detects_tampering` | 修改第 1 条的 outcome 后 `verify()` 为 `False` |

测试覆盖的空白（可作为练习补上）：

- 同版本重新准入（记录变化、已隔离版本）没有测试，对应 `admit()` 的静默覆盖缺陷。
- 准入较旧版本会切走路由（准入即激活）没有测试。
- 版本范围 / `latest`、重名工具、`required` 重排的行为没有测试。
- 账本截尾与整体重写（`verify()` 仍为 `True`）没有测试——这类测试应该断言"需要外部锚点才能发现"。
