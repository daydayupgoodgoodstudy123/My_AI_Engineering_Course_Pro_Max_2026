# 参考答案讲解：AppBridge（13/14）

计时结束后再看。参考实现在同目录的 `appbridge/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 UI 绑定与回退

**现象**：解锁后的第一个错误是 `an Apps host reads the UI that tools/list bound, got {'code': -32602, 'message': 'Unknown resource URI'}`。这个 URI 是 `tools/list` 刚刚给的，不可能不认识。

**顺着往下找**：`-32602 Unknown resource URI` 是 `_read` 抛的，条件是 `uri != RESOURCE_URI or not apps`。URI 相等，所以是 `apps` 为 False，也就是 `_apps_enabled` 把一个声明了扩展的宿主判成了没声明。打印 `meta[CLIENT_CAPABILITIES_META]` 就能看到 `{"extensions": {"io.modelcontextprotocol/ui": {}}}`：声明在 `extensions` 下面，而代码在顶层找。这一关想练的是：报错的位置往往不是出 bug 的位置，错误消息也可能把你引到错的方向。

**依次修四处**：

1. `_apps_enabled` 先取 `extensions`，要求它是 dict，再要求扩展的值也是 dict：

   ```python
   extensions = meta[CLIENT_CAPABILITIES_META].get("extensions")
   return isinstance(extensions, dict) and isinstance(extensions.get(APPS_EXTENSION), dict)
   ```

2. `_tool` 的 `or` 改成 `and`。课里说 Both peers opt in：服务端在 `server/discover` 里提供扩展，客户端在每个请求里声明，两边都有才带 `_meta.ui.resourceUri`。服务端总是提供，所以 `or` 等于“永远带绑定”。
3. `_read` 拆成两步：不认识的 URI 是 `-32602`；认识但客户端没声明扩展，是 `-32021`，data 写成 `{"requiredCapabilities": {"extensions": {"io.modelcontextprotocol/ui": {}}}}`。宿主看到它就知道该退回文本，而不是以为资源不存在。
4. `AppMount.review` 只在需要时审查一次：`__init__`、`replace` 和 `withdraw` 都把 `self._review` 置成 None，`review()` 发现是 None 才调 `review_resource` 并记下结果。原来的写法每个动作都把 1 MB 的 HTML 编码一遍、算一遍 sha256，2000 个动作本机实测 0.7 到 2.0 秒；修好以后 0.4 到 3 毫秒。

**护栏**：

- 声明要严格判断。`APPS_EXTENSION in extensions` 对列表也成立，对 `{APPS_EXTENSION: True}` 也成立；`extensions.get(...) is not None` 放过 `true`；`if extensions.get(...)` 把空对象 `{}` 当成没声明，正确声明的宿主反而拿不到 UI；`== {}` 又把带设置的声明当成没声明。只要是对象就算声明。本课自己的测试 `test_malformed_extension_map_does_not_grant_apps_capability` 就是名字列表这一条。
- 不要矫枉过正。不认识的 URI 仍然是 `-32602`；没有扩展的宿主拿到的是同一个工具，只少了 `_meta.ui`，课里 Fallback 一节第一条就是 Return the same tool without `_meta.ui`。
- 缓存审查结果，必须说清楚它什么时候失效。资源换了新版本、宿主撤回了一个准入的摘要，下一个动作都要重新审查。新版本没准入，`review()` 就报 ReviewError，不能接着用上一版的审查：上一版的 CSP 可能更宽，课里原话是 A stale iframe must not keep broader permissions merely because a new resource version has not loaded yet。永久缓存、按 URI 缓存、新版本审查不过就保留旧版本，都会被测试抓住。

## Part 2 App 资源缓存

布局就是 docstring 里写的：`blobs/<digest>` 是 HTML 的 UTF-8 字节，摘要是这些字节的 sha256 十六进制；`index.json` 是索引。参考实现的键是 `json.dumps([uri, name, version, digest, principal])`，public 条目的 principal 一律写 null，值是去掉 `text` 以后的整个 content 条目。

给定 `put/get` 先验证 App 输入并调用 `blob_io.store_html/load_html`，候选人实现 `_put_entry`、`_get_entry` 和 `_key`。六个 identity 同用一份 HTML，但 CSP、permissions、额外 _meta 各不相同；重开后逐个取回。只改一个 identity 的 metadata 时完整替换它，清掉的权限和删掉的字段都不能从旧记录合并回来，其他 identity 不变。

- **给定的按字节读写**：`content["text"].encode("utf-8")` 写进 blob，`read_bytes()` 读回，再 `decode("utf-8")`。`read_text()` 按 universal newlines 读，会把 `\r\n` 和单独的 `\r` 都变成 `\n`，读回来的摘要就对不上了。
- **读的时候校验摘要**：每次 `get` 都重新算一遍 blob 的 sha256，不等于键里的摘要就当没命中。缓存里放的是会在 iframe 里执行的代码，磁盘上被换掉的 blob 不能交给 View。
- **写的时候也要校验**：`put` 先读出已有的 blob，字节不同才重写。只看文件在不在，坏掉的 blob 就永远修不好。写文件用临时文件加 `os.replace`，进程中途退出不会留下半个 blob。
- **键里四样都要有**：URI、服务器名字、版本、摘要。同一份 HTML 在 2.0.0 和 2.1.0 下是两个条目，它们共用一个 blob；同一个 URI 的两个版本靠摘要分开。
- **principal**：private 条目的键带 principal，只有它自己能拿到；public 条目的键不带，谁都能拿到，存的时候带了 principal 也忽略。`get` 先查 public 的键，再查调用者的 private 键。principal 必须在键里，不能只记在条目上：同一份 HTML 给 alice 和 bob 各读一次，摘要相同，CSP 可能不同，是两个条目。
- **`_meta` 原样存**：CSP 列表的顺序、空列表、别的键都不动。把 CSP 排序或者只留 `_meta.ui`，读回来就不相等了。
- **只缓存 App**：URI 不是 `ui://`、MIME 不是 `text/html;profile=mcp-app`、private 没有 principal，都报 ValueError。

最后的端到端检查从本课的服务端读出 App，以 alice 的身份存，bob 从新开的缓存里拿到同一份，再交给 Part 1 的 AppMount 审查。服务端说的是 `cacheScope: "public"`，所以 bob 能拿到。

## Part 3 宿主策略引擎

构造时把 `_meta.ui` 拆成三样：connect 源的集合、resource 源的集合、声明的设备。缺了哪一部分都当空：

```python
csp = ui_meta.get("csp") or {}
self._connect = frozenset(csp.get("connectDomains") or ())
self._resource = frozenset(csp.get("resourceDomains") or ())
self._devices = frozenset(ui_meta.get("permissions") or ())
```

- **两张表分开**：fetch、xhr、websocket 只查 connect 集合，script、style、image、font 只查 resource 集合。课里说得很直白，能加载字体或脚本不等于能上传任意数据。
- **源精确相等**：`urlsplit(url)` 取出 scheme 和 netloc，拼成 `scheme://netloc`，看它在不在集合里。路径、查询串都不影响；userinfo 留在 netloc 里，`https://api.notes.example@evil.test` 拼出来就不等于任何列出的源；`http://` 和 `https://` 是两个源；端口也留在 netloc 里，`:8443` 不等于没写端口的源。用 `hostname` 拼会把端口丢掉。
- **设备**：名字在 permissions 里才允许。
- **postMessage**：`origin == self.view_origin`，一个字符都不能差。构造时拒绝 `"*"`，它会接受任何帧发来的消息。

特权动作是一张调用表，每个调用有 capability、目标、参数、状态（pending、done、rejected）和是否已批准：

- `request` 先查 capability 现在是否授予，没有就 Refused，不建调用。`user_gesture` 只是记录意图，不改 `approved`。
- `approve` 只对 pending 的调用生效。
- `run` 在执行的这一刻检查三件事：还是 pending、capability 仍然授予、用户批准过。通过就把状态改成 done，所以一个调用只能跑一次。
- `revoke` 拿掉 capability，把它下面所有 pending 的调用（批准了没执行的也算）标成 rejected，按 id 返回。rejected 是永久的，之后 `grant` 回来也不能复活：用户当时批准的是旧的授权状态下的那次操作。

课里说 Check capability and authorization at action time，not only during `ui/initialize`，`run` 里的检查就是这一句；On revocation, reject pending privileged calls，是 `revoke` 里的标记。两样缺一样，测试都能看出来。

## Part 4 Apps 桥生命周期

桥是一个 async generator：每处理完 inbox 里的一个事件，就把这个事件产生的帧全部 yield 出去，然后才去拉下一个事件。状态只有四样：

```python
context = copy.deepcopy(self.host_context)   # 当前的宿主上下文
ready = False                                 # 收到 ui/notifications/initialized 没有
held = []                                     # ready 之前宿主想发的通知
in_flight = {}                                # 核心 id -> View 的 id
```

- **分类**：View 发来的东西，只有带 method 的 JSON-RPC 2.0 对象才算；有 `"id"` 键的是请求（id 可以是 0），没有的是通知。字符串、没有 jsonrpc 的对象、没有 method 的响应都直接跳过。
- **回答不等待**：`ui/initialize` 立刻回 `{"hostCapabilities": ..., "hostContext": <当前上下文的副本>}`；不认识的请求（包括已经删除的核心 `initialize`）立刻回 `-32601 Method not found`。View 要等这个回答才发 `ui/notifications/initialized`，所以回答绝不能排队。
- **通知要等**：工具结果、主题变化、给 View 的尺寸，ready 之前放进 `held`，收到 `ui/notifications/initialized` 时按顺序全部发出，之后的通知直接发。只认这一个方法名；核心的 `notifications/initialized` 已经删除，不开闸。
- **尺寸**：每一维取 `min(要的, max_size)`，写进上下文，再用 `host-context-changed {"size": ...}` 告诉 View。
- **上下文是当前的**：`context` 是 `host_context` 的副本，每次变化都更新它，`ui/initialize` 回答的是它，所以 View 初始化之前发生的主题变化也会反映在回答里。不直接改 `host_context`，那是调用方的对象。
- **代理 tools/call**：

  ```python
  core_id = next(self.core_ids)
  body, headers = make_request("tools/call", core_id,
                               {"name": params.get("name"), "arguments": params.get("arguments", {})})
  in_flight[core_id] = view_id
  self.send_core(body, headers)
  ```

  核心请求用宿主自己的 id、元数据和路由头，只带 View 的 name 和 arguments；View 塞进来的 `_meta` 和 `principal` 不转发。核心响应回来时 `in_flight.pop(response["id"])` 找到 View 的 id，结果或错误原样回给 View。pop 掉以后，重复的响应就找不到在途请求，自然被忽略。

测试记下每一帧出来时桥已经拉了几个事件，期望是 `[1, 2, 9, 9, 9, 13, 14, 16]`：两个回答各在自己的事件之后马上出来，三条排队的通知在第 9 个事件（`ui/notifications/initialized`）之后一起出来。先读完整个 inbox、提前发通知、晚一拍发，都会让这串数字变样。最后一段把桥接到本课的服务端，服务端会校验 `_meta` 和路由头，证明代理出去的确实是一个完整的、自包含的请求。

## Part 5 缓存失效传播

分两步。第一步把每个事件翻译成“失效的资源”或“失效的条目”：

- `expired`：只把那个条目放进 dropped。
- `binding`：用 `state.bindings.get` 取出这个工具旧的 URI（第一次绑定的工具没有），旧的和新的两个 (server, uri) 都放进 resources；这个工具自己的 View 直接放进 remount。state 只读不写。
- `server`：这台服务器缓存里有条目的资源，和它的工具绑定的资源，都放进 resources。
- `updated`：只有 (server, uri) 在已确认的订阅里才放进 resources。
- 别的类型报 ValueError。

第二步沿着依赖边展开：

```python
dropped |= {eid for eid, e in state.entries.items() if (e.server, e.uri) in resources}
bound = {tool for tool, uri in state.bindings.items() if (tool[0], uri) in resources}
remount |= {vid for vid, v in state.views.items() if v.entry in dropped or (v.server, v.tool) in bound}
```

资源始终用 (server, uri) 表示，所以 tasks 上的 `ui://notes/timeline.html` 不会被 notes 的变化拖进来；到期只丢那一个条目，所以 bob 的副本和共用 blob 的条目都不受影响。View 有两条路被找到：从被丢的条目挂载的，以及它的工具绑定到失效资源的。v7 挂载时用的条目已经被驱逐，只能走第二条路。最后用 sorted 输出，集合顺带去重。

## 这套题证明了什么，没证明什么

通过了说明你能在 MCP Apps 的代码里顺着错误码找到能力判断的根因，知道文本回退和 `-32021` 的契约，能把可执行内容按内容寻址存盘并在读的时候校验，能写出 connect 与 resource 分开、精确匹配源、按调用批准并能撤销的宿主策略，能写一个先回答、后排队、id 不混用的 postMessage 桥，并能沿依赖图算出一次变化要失效什么。它不涉及真实浏览器里的 iframe、sandbox 属性和 CSP 头的执行，不涉及 HTTP 适配器（第 09 课）、OAuth 授权（第 16、18 课）和网关的描述符 pin（第 17 课），也没有测可访问性、焦点和主题切换在真实 View 里的表现。这些需要在真实宿主里另外动手验证。
