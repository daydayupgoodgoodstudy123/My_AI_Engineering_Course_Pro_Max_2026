# 参考答案讲解：regadmit（13/30）

计时结束后再看。参考实现在同目录的 `regadmit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修证据和账本

**现象**：解锁后第一个错误是 `listed_version` 给出的状态：三个版本（active、deprecated、deleted）全都显示 active。

**依次修五处**：

1. `registry_status` 写的是 `api_meta.get("status", "active")`。状态在响应级 `_meta` 的官方块里，`api_meta["io.modelcontextprotocol.registry/official"]["status"]`；平铺的 `_meta.status` 不是官方的写法，记录自己的 `_meta` 是发布者写的地方，都不算。拿不到官方状态就返回空串，空串永远不合格。默认 active 是最危险的写法：deprecated 和 deleted 都看不见了。
2. `listed_version` 里有两个名字相近的变量：`namespace` 是记录名字里 `/` 前面那段，`verified_namespace` 是认证结果。原代码把前者传给了 `namespace_matches`，等于让记录给自己作保，`org.attacker/inventory` 也落在 `com.example` 里。改成传 `verified_namespace`。`namespace_matches` 本身照课里写：按 `/` 切开，slug 非空，命名空间段精确相等，所以 `com.example.docs/search` 不在 `com.example` 里。
3. `normalized_tools` 为了排序先按名字建字典，同名的描述符只剩最后一个。服务器在已钉住的工具前面加一个同名的新描述符，字典里留下的还是原来那个，摘要不变，新工具就这样藏过去了。课里说只规范顺序没有意义的部分：工具列表按名字、再按规范 JSON 排序，每个描述符都留着，字段一个不丢：

```python
return sorted(tools, key=lambda tool: (str(tool.get("name", "")), canonical_json(tool)))
```

4. 修到这里，测试在第 3 次 `append` 时报 `LedgerError: ledger does not verify`。`verify()` 没有错，错在链本身：把每条的 `previousHash` 打出来，第 2 条链到的是 GENESIS，而不是第 1 条的哈希。链头来自 `head()`，`head()` 返回的是最新条目的 `previousHash`。改成 `entryHash`。这一处想练的是：报错的位置（验证）和出错的位置（上一次追加拿到的链头）隔了一次调用。
5. `append` 通过 `head()` 拿序号和链头，而 `head()` 每次都从创世条目验证整条链，追加 n 条就是 O(n²)，1000 条在本机要 1.3 到 1.6 秒。追加只需要接在最新一条后面：

```python
newest = self.entries[-1] if self.entries else None
"sequence": len(self.entries) + 1,
"previousHash": newest["entryHash"] if newest else GENESIS,
```

**护栏**：为了提速，最省事的改法是让 `verify()` 只验最后一个链接，或者让 `head()` 不再验证。测试改掉 1000 条里的第 401 条以后，要求 `verify()` 返回 False、`head()` 报错：链头是要锚定到别处的，坏掉的链不能交出链头。修第 2 处时如果写成 `namespace = verified_namespace`，`in_namespace` 也对了，但 `Listing.namespace` 就不再是记录声称的命名空间，被拒的准入记不下 claimedNamespace，测试会抓住。工具集那边，新注解和新 `title` 都要改变摘要，所以把描述符砍成固定几个字段会挂；还有一个写死的摘要，它和已经存下的 toolsetDigest 必须一致，所以换一种排序方式、或者把描述符里的列表（enum）也排序，都会挂。

## Part 2 账本文件和锚点

`LedgerFile` 继承 Part 1 的 `AdmissionLedger`：打开时读回每一行、整链验证、再核对锚点；追加时先让父类算好条目，再写成一行。

```python
if self.path.exists():
    self.entries = _read_entries(self.path)
if not self.verify():
    raise LedgerError(...)
if anchor is not None:
    self._check_anchor(anchor)
```

锚点 `(sequence, entryHash)` 是锚定那一刻的 `head()`。核对的规则是：文件里还有第 sequence 条，而且它的哈希没变。

```python
held = 0 < sequence <= len(self.entries) and self.entries[sequence - 1]["entryHash"] == entry_hash
```

- **链自己能发现什么**：改了任何一条的任何字段（测试改的是 time），那一条的哈希就对不上，重开时报 LedgerError。
- **链自己发现不了什么**：删掉最后几条，剩下的链完全自洽；能写文件的人改掉一条以后把后面的哈希全部重算，链也完全自洽。测试先断言了这两点，再要求带着锚点打开时报错。这就是课里说的 tamper-evident, not tamper-proof，也是 Production Failure Modes 里 “Ledger verifies locally after an attacker rewrites all entries” 那一行的应对：Publish signed ledger heads to a separate trust domain。
- **锚点不是“现在的链头”**：锚定以后账本还会长，旧锚点必须继续成立，所以按下标找那一条，而不是和最后一条比；只比长度会放过整链重写；下标越界要报 LedgerError，不能是 IndexError。
- **整个文件被删**：不带锚点是空账本，带着锚点必须报错。
- **重开以后接着写**：新条目的序号是 6，previousHash 是锚定的那个哈希。父类的 `append` 从 `self.entries` 算序号和链头，所以读回来的条目放进 `self.entries` 就自然接上了。

往返的精度问题在哈希上：每一行的 entryHash 必须能从读回来的九个字段原样算出来。用 `digest()`（规范 JSON：键排序、无空白、非 ASCII 转义）算、按 JSON 存，读回来的值和写进去的值一样，哈希就一样；测试里有 pin、None、带 ü 和德文引号的原因，以及一个以 tuple 传进来的 reasons（父类存成了 list）。

## Part 3 七项准入控制

`decide` 先收集所有失败的控制，再按 CONTROLS 的顺序排好：

```python
failed = set(live_failures(live, required_capabilities))
if not _exact(requested) or requested != listing.version:
    failed.add("version")
...
return Decision(False, tuple(control for control in CONTROLS if control in failed))
```

- **version**：`^1.4` 和 latest 是选择版本的方式，不是钉住的版本。requested 要精确，并且和记录逐字符相同；记录自己写着 latest 或范围也不行。精确只看有没有范围字符、是不是 latest，不要求语义版本，课里说 Registry 推荐 semver 但不强制。这里比的是 Registry 版本（发布记录的标识），不是包版本：一条 1.0.1 的新记录可以引用同一个 1.0.0 的包，包版本在 source 那一步和证据比。
- **status、namespace**：用 Part 1 的 `listed_version`。
- **source**：package 按 (registryType, identifier, version) 一起找，再比 transport.type：

```python
wanted = (evidence.get("registryType"), evidence.get("identifier"), evidence.get("version"))
for package in record.get("packages") or []:
    declared = (package.get("registryType"), package.get("identifier"), package.get("version"))
    if declared == wanted and transport.get("type") == evidence.get("transportType"):
        return {"kind": "package", **deepcopy(package)}
```

本课代码先按 identifier 找第一个包再比别的字段，记录里同名的 npm 包排在 PyPI 包前面时就会连错。remote 两边都先 `normalize_https_remote_url` 再比，再比 type；规范化失败返回 None，要先排除 None，否则两条 http 的 URL 会因为都是 None 而连上。只有 remote 的记录是完整的，`record.get("packages") or []` 不会因为没有 packages 出错。`verified is True` 对两种来源都要求，字符串 `"false"` 不算。
- **digest**：必须是 SHA-256 十六进制，而且来源在白名单里：校验器在可信的抓取边界自己算的（fetch），或者它验证过结果的包服务给的（package-service）。制品自己报的（artifact）和没写来源的都不算。课里：Never accept a digest supplied only by the artifact you are trying to verify。
- **live**：`live_failures` 查三样：supportedVersions 是列表（字符串会让 `in` 变成子串匹配）并且含 2026-07-28（在哪个位置都行，记录的 `$schema` 日期是另一回事）；每个必需能力都是 capabilities 对象的键（`{}` 也算声明了，名字列表不算）；每个工具都有非空白的 name、description 和一个 inputSchema 对象。
- **serverInfo**：只进 `reportedServerInfo`，用课里的 `reported_server_info`。命名空间和 pin 的 server、version 都来自记录。

全部通过才建 pin。provenance 把这次连接的证据合在一个对象里，provenanceDigest 是它的摘要，是指向整套证据的指针，不代替证据本身。

## Part 4 分层对账流

每来一条观测：取 pin、判这一层、更新隔离和路由、记账、输出。

```python
async for observation in observations:
    pin = state.pins.get(key)
    layers, evidence = _judge(check, observation, pin, required_capabilities)
    if pin is None:
        outcome = "unknown"
    else:
        if layers:
            state.quarantined.add(key)
            if state.active.get(server) == version:
                del state.active[server]
        outcome = "quarantined" if key in state.quarantined else "ok"
    entry = ledger.append(EVENTS[check], server, version, outcome, layers, evidence)
    yield json.dumps({"seq": entry["sequence"], ...}) + "\n"
```

- pin 钉了好几层，所以能说清是哪一层变了：同一个 Registry 版本下记录摘要变了，是 Registry 完整性失败（发布元数据本应不可变）；同一个包坐标下 sourceDigest 变了，是执行来源失败；工具集变了或者 live 检查不过，是运行时漂移。
- 工具集用 `toolset_digest` 比，只换顺序不算漂移；工具列表里不全是对象时 toolsetDigest 记 None，这本身就是漂移。
- deprecated 还能被发现，deleted 默认列表里看不见了，但两者都不再是安全的自动选择，都隔离。隔离是粘住的；只有 active 的那个版本才摘路由；pin 一直留在 `state.pins` 里，是证据。
- 证据只记观测到的摘要和状态。观测里带着探针请求的 Authorization 头和 tools/call 的参数，测试检查账本里一个都没有。
- live 检查用调用方传进来的 required_capabilities，不用默认值。
- 先记账再输出，verdict 里带账本序号；async generator 拉一条判一条，测试的探针数过：第一条 verdict 出来时只拉走了一条观测。

## Part 5 按账本回滚

先把账本折叠成状态，规则只有三条：approved 的准入记 pin、切路由；检查事件的 quarantined 隔离，若是 active 就摘路由；activated 的回滚切路由。其余条目，包括被拒的准入和被拒的回滚，什么都不改。

```python
if event == "admission" and outcome == "approved":
    state.pins[(server, version)] = deepcopy(entry["evidence"]["pin"])
    state.active[server] = version
elif event in CHECK_EVENTS and outcome == "quarantined":
    state.quarantined.add((server, version))
    if state.active.get(server) == version:
        del state.active[server]
elif event == "rollback" and outcome == "activated":
    state.active[server] = entry["evidence"]["to"]
```

`rollback` 每次都从账本重新折叠，按 (server, target) 找准入（inventory 准入过 1.1.0，billing 没有），按顺序判 unknown、quarantined、unhealthy，健康检查放在最后，前两条都通过才问。不管结果如何都追加一条 rollback，from 是折叠出来的当前路由。所以“回滚以后再回滚”时，第二次的 from 是第一次切到的版本；billing 当时没有 active 版本，from 是 None。账本只追加，之前的条目一个字节都不变，`verify()` 仍然通过。

`state_of` 把课里 Use It 一节的四种状态分开：approved、active、quarantined、superseded，外加从没准入过的 unknown，而不是用一个布尔值表达所有含义。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着调用链调试，能把哈希链账本存成文件并说清它能发现什么、发现不了什么，能把命名空间、来源、摘要和 live 发现合成一次准入判定，能写出逐条判定、先记账后输出的异步对账流，以及从账本证据里做回滚决定。它不涉及真正连网的部分：Registry API 的分页、deleted 视图和增量视图的同步，真正去抓包、校验 TLS 身份，以及签名和透明日志的实现。课里 Practice Lab 的“破坏性工具需要两个不同评审”也没有覆盖，要回到 `code/main.py` 自己动手加。
