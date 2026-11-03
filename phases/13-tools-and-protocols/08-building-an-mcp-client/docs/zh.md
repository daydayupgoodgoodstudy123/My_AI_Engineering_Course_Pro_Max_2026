<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="building-an-mcp-client-discovery-routing-and-dual-era-fallback"></a>

# 构建 MCP 客户端：发现、路由与新旧协议兼容回退

> 现代 MCP 客户端对每一项请求都重复其合同。 它最难作出的兼容决定是知道一个旧服务器何时真正老旧,以及当一个现代服务器报告了一个可更正的错误时。

**类型:** Build
**语言:** Python
**先修要求:** 第13阶段,第07课
**时间:** ~85分钟

<a id="learning-objectives"></a>

## 学习目标

- 构建每 MCP `2026-07-28` 请求使用当前元数据 。
- 用于 `server/discover` 并选择一个相互支持的版本。
- 授权只允许明确允许列表的同行进行连接式遗留问题查询 。
- 仅在确认一个正值后接受遗留时代 `initialize` 后,将支持修改。
- 合并确定性工具列表,不默默地覆盖碰撞。
- 路径呼叫拥有每个工具的对等点, 不创建协议会话 。

<a id="the-problem"></a>

## 问题

一个 agent 主机通常与多个对话 MCP 服务器。 它必须发现每个服务器, 合并工具目录, 解决重复的名称、 路线呼叫, 并从传输失败中恢复 。

该 `2026-07-28` 修改后会简化稳定状态, 因为每次请求都是自足的。 兼容性会让启动过程更加微妙 。 客户可能遇到 :

- 支持首选版本的现代服务器;
- 返回一个识别版本或页眉错误的现代服务器;
- 从未听说过的遗产服务器 `server/discover`;
- 传统服务器, 在收到前保持安静 `initialize`.

将每个探测错误都视为遗留问题是很危险的。 一个错误的现代请求、 一个超载服务器、 一个已停止的过程和一个旧服务器都可以产生相同的超时或连接关闭。 这些信号是模糊的。 客户端必须在选择遗留时代之前将明确的操作器意图和积极的协议证据结合起来 。

<a id="the-concept"></a>

## 概念

<a id="a-peer-not-a-protocol-session"></a>

### 对等点, 不是协议会话

每个服务器进程或端点都保留一个传输对等点记录 :

- 运输处理或发送功能;
- 选定的协议时间和版本;
- 最近一次发现的服务器能力;
- 最后一个确定性工具列表;
- 有待处理的请求的关联性ID;
- 运输健康。

这是客户端簿记, 不是协议会话状态 。 MCP,服务器仍然接收到当前版本和每个请求的能力。

<a id="build-every-modern-request-from-scratch"></a>

### 从头构建每个现代的要求

```python
def modern_request(request_id, method, params, version, capabilities):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {
            **params,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": version,
                "io.modelcontextprotocol/clientCapabilities": capabilities,
                "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
            },
        },
    }
```

将元数据附加到连接对象上, 并假定它已到达电线。 印章并检查最终的序列请求 。

<a id="modern-discovery"></a>

### 现代发现

`server/discover` 返回支持的版本、服务器能力、指令、缓存提示和建议的服务器身份。客户端选择了最高支持的现代版本。

发现是现代客户端的可选选项, 但推荐在标准版上。 一些遗留服务器在初始化前接受操作, 所以发送 `tools/list` 首先,可以产生模糊的成功。 `server/discover` 创造干净的时代边界。

<a id="the-stdio-compatibility-probe"></a>

### 标准兼容性探测器

双年版的平板电脑客户端发送 `server/discover` 其首选现代元数据, 而不是任何其他请求。 有三个结果类别 :

1. **DiscoverResult.** 服务器是现代的。 选择一个互相支持的版本, 并继续使用每个请求的元数据 。
2. **公认的现代错误。** 服务器是现代的。 `-32022`,从 `data.supported` ,然后使用新的请求代号重试。对于页眉或功能错误,请更正请求。不发送 `initialize`.
3. **模糊的信号** 未经承认的 JSON-RPC 错误、超时、连接关闭或空响应无法识别一个时代。 失败已关闭, 除非该对等点被配置为遗留兼容性 。

公认的现代协议错误包括:

- `-32020` HeaderMismatch
- `-32021` MissingRequiredClientCapability
- `-32022` UnsupportedProtocolVersion

公认的现代错误即使在遗留的允许列表中,也仍然很现代。 一旦服务器证明它理解了现代错误 vocabulary,发送 `initialize` 这会是降级

不治疗 `-32601` 属于积极的遗留证据。 它只允许一个明确允许的端点有资格使用一个遗留的探测。 同一规则适用于超时、 连接关闭或空响应 。

<a id="allowlisting-is-operator-intent-not-evidence"></a>

### 允许列名是操作员的意图,不是证据

遗留的兼容性必须是被钉住的对等方配置的明显属性 :

```python
client.add_server("archive", archive_transport, allow_legacy=True)
```

将该选项绑在配置的命令或端点上。 不要使用任意服务器选择为较弱语义的通配符。 没有此等同 `allow_legacy=True` 发现结果不明之后失败了, 却从未收到 `initialize`.

允许列表允许查询。 它不选择时代。 客户端发送 `initialize` 运输时限,然后要求下列所有规定:

- 一个 JSON-RPC `2.0` 与匹配请求代号对应;
- 刚好 `result` 和没有 `error`;
- 一个 `protocolVersion` 客户端配置的遗留版本集中;
- 对象价值 `capabilities` field;
- 一个 `serverInfo` 带有非空字符串的对象 `name` 和 `version` fields.

超时、 连接关闭、 错误响应、 错误结果、 不匹配的 ID 或不支持的修改失败 。 只有结构有效的正结果才会选择遗留的时代 。 代码通过 `legacy_probe_timeout_ms` 转换器; 真正的平方或 HTTP 适应者必须执行这一最后期限,而不仅仅是记录。

缓存所选的运输对等点的时代。 在每次呼叫前不要再次检测 。

<a id="legacy-is-a-compatibility-branch"></a>

### 遗产是兼容的 branch

一旦被绑定的探测器返回有效的遗迹证据,客户端将使用该修订版所定义的选定遗迹版本:

1. 校验响应信封和对应代号
2. 测试已配置的遗留文件集中包含谈判修改内容。
3. 记录验证的能力和服务器身份。
4. Send `notifications/initialized` 只有在支票都通过之后
5. 使用遗留请求形状来完成运输周期。

此 branch 存在与已知对等点的互操作性。 它不是新服务器或新请求的默认设计。 如果运输重新启动或端点更改, 丢弃对等点时代缓存并再次谈判 。

<a id="discovering-and-caching-tools"></a>

### 发现和缓存工具

对于每个活动对等点, 调用 `tools/list`现代结果包括: `resultType`, `ttlMs`, 和 `cacheScope`。在正确的授权范围内,遵守新提示。过期或订阅的更改列表事件后重新拉伸。

客户必须治疗缺失的 `resultType` 从遗留服务器中生成为 `"complete"`。不需要在早期谈判时期的响应中使用现代缓存字段。

服务器应该返回确定性排序。 客户端也应该在合并前进行排序, 所以本地注册订单并不取决于启动进程的时间 。

<a id="collision-safe-namespace-merge"></a>

### 碰撞安全命名空间合并

两个服务器都可能暴露 `search`选择声明的政策:

1. **碰撞前缀 。** 保留第一个金刚石名称, 并暴露以后的碰撞为 `<server>/<tool>`.
2. **拒绝碰撞** 不装入重复文件, 并显示清晰的配置错误 。
3. **静默地覆盖。** 永远不要使用此选项。 它隐藏哪个服务器接收模型选择的动作 。

存储语句名称和本地名称。 模型看到语句名称。 即将发送 `tools/call` 使用所申报的拥有服务器的本地名称。

<a id="routing-a-call"></a>

### 拨打电话

路途是纯粹的外观:

```text
canonical tool name
  -> peer name + local tool name
  -> new JSON-RPC request id
  -> modern request metadata or explicit legacy shape
  -> matching response id
```

当它拥有的运输工具无法使用时, 不要发送呼叫。 重新连接或重新启动运输, 然后重新运行发现并 `tools/list`损坏的运输机丢失的现代飞行请求可重新审理 JSON-RPC 安全规定允许时

<a id="notifications-and-subscriptions"></a>

### 通知和订阅

仅对客户端打开时才会收到现代列表和资源更改 `subscriptions/listen` 流。客户端发送通知过滤器,等待 `notifications/subscriptions/acknowledged`,并显示在通知元数据中与倾听请求ID相关的事件。

断开时, 打开新的倾听请求并重新获取相关列表或资源。 现代流不会恢复 `Last-Event-ID`.

<a id="no-server-initiated-requests"></a>

### 没有服务器启动的请求

现代服务器不呼叫独立客户端 JSON-RPC 请求 sampling, elicitation, 或 roots。他们返回 `input_required`,客户端在满足嵌入输入请求后重新检查原始请求。

执行输入时不要阻断对等点的响应读取器。 保存相关关系并创建一个新的 JSON-RPC 重试的ID 。

```figure
tp-client-merge
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 使用进程中的对等函数, 使协议决定保持可见。 它连接到两个现代对等点, 一个故意允许列表的遗留对等点, 然后合并和跟踪工具。 传输调用程序接收超时预算, 以便兼容 branch 无法隐藏未设界的探测器 。

```bash
cd code
python3 main.py
python3 -m unittest discover tests -v
```

测试证明正常演示的界限错失:

- 现代要求重复元数据;
- `-32022` 重新输入现代发现,而不初始化;
- 承认的现代错误绝不降低等级,即使是对允许的同级人员也是如此;
- 超时、连接关闭、空响应和未识别错误不触发 `initialize` (a) 没有许可名单;
- 允许列表的对等点只有在有效且支持后才会成为遗产 `initialize` 结果;
- 错误和不支持的遗留结果使得同行无法使用;
- 一个成功选中的时代在传输寿命期间被缓存。

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-client-harness.md`。 它将现代要求标记、 平板时代谈判、 确定性命名空间合并、 路径和关闭失败的遗留兼容性 branch.

<a id="exercises"></a>

## 练习

1. 复制服务器返回 `-32022` 没有相互支持的版本。 确认客户端失败, 而不是发送 `initialize`.
2. 允许一个假的遗留服务器, 使其被绑定 `initialize` 探查时间, 并证明对等点停留 `unknown` 并且没有
3. Add `cacheScope: "private"` 工具列表, 用于两个授权背景。 确认客户从未与另一个客户共享上下文缓存结果 。
4. 将碰撞策略改为拒绝, 并生成错误中两个对等名称的启动失败 。
5. 添加一个限定 `subscriptions/listen` 模拟器。 在流流丢失时, 重新听取新的请求代号并重新获取工具 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| Peer | 客户端记录,用于一个服务器的传输及其发现的数据 |
| 协议时代 | 现代的每个请求元数据或遗留初始化语义 |
| 发现探测器 | Initial `server/discover` 用来识别标准时代 |
| 公认的现代错误 | 错误证明现代行为,禁止遗产的退缩 |
| 遗产许可列表 | 允许对被绑定的对等点进行一个连接兼容性探测的操作器配置 |
| 积极遗留证据 | 有效, 相关 `initialize` 导致明确支持的遗产修订 |
| 合并命名空间 | 对所有活动对等点的卡尼基工具名称 |
| 碰撞政策 | 重复工具名称的前缀或拒绝规则 |
| 时代缓存 | 存储给一个运输同行的选定现代或遗留行为 |
| 运输恢复 | 重新开始或重新连接, 重新发现, 重新列表, 并安全地重试 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP 规格 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/)
- [MCP 服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
- [MCP 平方英尺运输](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)
- [MCP Versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)
- [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
