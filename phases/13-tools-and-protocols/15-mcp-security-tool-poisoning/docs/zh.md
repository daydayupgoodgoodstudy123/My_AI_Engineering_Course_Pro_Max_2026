<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-security-poisoned-metadata-routing-and-mrtr-state"></a>

# MCP 安全：元数据投毒、路由与 MRTR 状态

> 无国籍并不意味着没有信任。 这意味着每一个请求都暴露了证据,一个服务器和网关需要独立验证该呼叫。

**类型:** 学习
**语言:** Python
**先修要求:** 阶段13 -07 (MCP 服务器,第13阶段 ・ 08 (MCP client)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 将工具描述、说明、客户信息和服务器信息作为不信任的数据处理。
- 检测元数据中毒、描述器变化和跨服务器名称碰撞。
- 验证2026-07-28请求的元数据和可流数据 HTTP 路由信头
- Protect MRTR `requestState` 禁止篡改,并强制确认确切的论点。
- 应用授权和 rate limits 给主会,而不是删除的礼宾会话。

<a id="the-problem"></a>

## 问题

模式读取工具描述以决定要调用什么。 路由器读取工具名称以决定要发送请求的地址。 用户读取标签以决定要批准什么。 恶意描述符可以针对所有三个对象 。

官方 MCP 安全指导是直接的:描述和说明应该被视为不信任,除非它们来自信任的服务器。即使如此,部署信任也可以改变。服务器更新、损坏的软件包、注册错误或网关合并可以改变模型所看到的。

目前的协议还改变了安全边界。 在2026-07-28年,没有核心握手,也没有运输会话。 一种安全设计, 密钥批准, rate limits,或审计历史仅由 `Mcp-Session-Id` 不是一个当前设计。

<a id="the-concept"></a>

## 概念

<a id="seven-attack-surfaces-worth-checking"></a>

### 7个攻击表面值得检查

使用具体列表代替模糊的指令来小心。

1. **元数据中毒。** 描述包含与声明的工具行为无关的指示 。
2. **描述地毯拉。** 先前核准的名称、说明、方案或注释有变动。
3. **跨服务器的影子。** 两个后端暴露了相同的不合格的工具名, 路径选择一个静默的 。
4. **头和身体混乱。** `Mcp-Method` 或 `Mcp-Name` 不同意该声明 JSON-RPC request.
5. **能力升级。** 同行主张延期或客户端 feature 服务器错误了该声明的授权 。
6. **MRTR 国家篡改。** 客户端更改 `requestState`,回答另一个问题,或用不同的论点重新确认。
7. **供应链身份混淆。** 熟悉的显示名称被当作出版商或服务器身份的证明。

这些表面重叠。 散列会帮助描述符的更改, 但无法证明第一个描述符是安全的。 静态扫描会捕捉明显的词组, 而不是微妙的指示。 名称间隔可以防止一个相撞类, 而不是一个恶意的命名间距服务器。 堆放控制器 。

<a id="the-current-request-envelope-is-evidence-not-identity"></a>

### 目前的请求信封是证据,不是身份

每2026-07-28次请求中包括:

```json
{
  "_meta": {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {
      "elicitation": {"form": {}}
    },
    "io.modelcontextprotocol/clientInfo": {
      "name": "security-lab",
      "version": "1.0.0"
    }
  }
}
```

校验每个请求的版本和能力形状。 使用此功能选择兼容的反应形状。 不要使用 `clientInfo` 身为一名经认证的校长,这是自我报告。

同一警告适用于 `io.modelcontextprotocol/serverInfo` 。 它对于日志和调试有用。 它不是证书、 登记册证明或授权决定 。

<a id="validate-routing-before-policy"></a>

### 校验路线后再定单

用于 `tools/call`,可移动 HTTP includes:

```text
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: notes.export
```

页眉方法必须等于正文方法。页眉名称必须等于 `params.name`拒绝不同意 `-32020` 在选择后端之前,应用 RBAC, 或使用率限制 token.

命令中排除了一种常见的模糊性:一个部件授权尸体,另一个由信头负责。

电线验证遵循一个精确的序列。 JSON-RPC 和元数据类型,与正文比较页眉值,然后检查是否支持匹配版本。 HTTP 4 000 计 `-32020`。如果页眉和正文同意一个不支持的版本,则返回 HTTP 4 000 计 `-32022` 和 `data` exactly `{"supported":["2026-07-28"],"requested":"<actual>"}`返回未知的方法 HTTP 404 计 `-32601`.

每个错误对象都包含可选 `data` 合同需要结构化的追偿信息时。 `id`,所以它从来没有得到 JSON-RPC 成功或错误响应。 被接受 HTTP 通知返回空体202。

<a id="pin-the-whole-descriptor"></a>

### 插入整个描述符

仅描述散列就缺少了图案和注释的更改。 用户批准的描述字段要加固和加长 :

```python
normalized = json.dumps(tool, sort_keys=True, separators=(",", ":"))
digest = hashlib.sha256(normalized.encode()).hexdigest()
```

将摘要存储在合格的密钥下, 例如 `notes.export`,连同出版商的证据和批准时间 在这个玩具的例子之外。

在每个新事物上:

- 未知的密钥: 隔离直到审查。
- 同样的钥匙,不同的文摘:隔离作为地毯拉,直到重新批准。
- 重复不合格名称: 需要确定性名称的间隔 。
- 扫描器撞击: 屏蔽并检查完整描述符 。

毒药的描述器在完全被钉住时会中毒

<a id="static-scanning-is-a-tripwire"></a>

### 静态扫描是条绊线

简单的模式可以标记角色标签、指令取代、隐藏、秘密访问和模糊的网络目的地。 它们非常便宜,可以安装时间和CI。

它们不是语义上的证明。 安全描述可以在合法警告中包含一个标记的词句。 恶意描述可以避免每一个词句。 将扫描器输出作为审查证据, 而不是自动的无罪评分 。

<a id="namespace-before-merging"></a>

### 合并前的命名空间

假设两个服务器都暴露了 `search`绝不让发现命令决定谁赢了

```text
notes.search
issues.search
```

合格名称是公共网关名称。 单独记录后端映射。 稳定姓名可以进行批准、 审计、 散列针和 `Mcp-Name` 路径指同一对象。

<a id="capabilities-are-compatibility-declarations"></a>

### 能力是指兼容性声明

Per-request `clientCapabilities` 告诉服务器哪个协议 features 用户可以处理。 它不允许客户访问工具、数据或行动。

授权还是来自经认证的本金和资源政策。

1. 认证运输证书。
2. 校验版本、信头和请求形状 。
3. 检查能力兼容性。
4. 授权主控、工具、资源和参数。
5. 执行或请求用户输入 。

<a id="protect-stateless-mrtr-confirmation"></a>

### 保护无国籍人 MRTR confirmation

相应的工具可能需要用户确认。 MCP 使用 Multi Round-Trip Requests 而不是服务器对客户的回调 。

第一次回应 :

```json
{
  "resultType": "input_required",
  "inputRequests": {
    "confirm": {
      "method": "elicitation/create",
      "params": {
        "mode": "form",
        "message": "Export notes to archive?",
        "requestedSchema": {
          "type": "object",
          "properties": {
            "confirm": {"type": "boolean"}
          },
          "required": ["confirm"]
        }
      }
    }
  },
  "requestState": "opaque-integrity-protected-value"
}
```

客户获取输入并重试原始方法 JSON-RPC id:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "notes.export",
    "arguments": {"query": "private", "destination": "archive"},
    "requestState": "opaque-integrity-protected-value",
    "inputResponses": {
      "confirm": {
        "action": "accept",
        "content": {"confirm": true}
      }
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "elicitation": {"form": {}}
      }
    }
  }
}
```

每个 `inputRequests` 值是完整嵌入请求 `method` 和 `params`。它的密钥必须与相应的条目匹配 `inputResponses`表格。 elicitation 使用对象根 `requestedSchema`,客户必须已经申报表格 elicitation 服务器要求它之前的功能 。

现有能力有两个有效形式声明。 `{"elicitation":{}}` 默认支持窗体 elicitation, 而 `{"elicitation":{"form":{}}}` 明确说明。 `{"elicitation":{"url":{}}}` 不支持窗体请求。 服务器返回 HTTP 4 000 计 `-32021` 和 `data.requiredCapabilities` 等于 `{"elicitation":{"form":{}}}`.

Treat `requestState` 。 签名或加密它, 验证它, 并把它绑在方法、 工具、 精确的参数、 目的、 过期、 主机和一次性的 无效 中 重放 重要 。 课程代码使用 HMAC 和精确的参数匹配来让边界可见 。

非账簿不能保存在一个网关对象内。可运行模式输入一个被捆绑的、TTL- pruned 的重放存储,该存储可以由多个网关实例共享。它的原子主张是执行边界:只有经验证的接受或明确的终端拒绝会消耗状态。 `cancel` 生产船队需要相同的条件要求,共同储存耐久性。

不在协议会话中存储隐藏的确认上下文。 任何服务器实例都应能够验证重试 。

<a id="rule-of-two-for-high-risk-calls"></a>

### 高风险电话规则二

沿三个轴对呼叫进行分类:

- 它消耗了不可信的投入。
- 它能访问敏感数据
- 这种做法引起了外部的相应行动。

单一个自动步骤不应将所有三个步骤合并。 分割它, 减少特权, 或者通过 MRTR。这是一个设计超常,而不是协议能力。

<a id="reduce-authority-before-execution"></a>

### 执行前减少权力

无国籍本身不是安全。 它会删除隐藏的协议历史, 但自足的请求仍可以要求一个超强的处理者泄露数据或做出不可逆转的改变。 安全来自减少每个边界的权力 :

1. **输入动词 。** 显示一个约束操作,例如 `archive_note`,而不是通用 `run` 或 `request` 工具,可以表达不相干的力量。
2. **论证的参数 。** 在实际可行的情况下使用封闭式模式,拒绝未知字段,一次标准化标识符,上限大小,在政策之前验证目的地、租户和资源所有权 evaluation.
3. **目前的授权。** 将认证的本金绑在精确动词、资源、环境和正常参数上。 工具说明和客户能力不赋予此权限 。
4. **行动许可。** 由此而来,对输入动词和正常参数的文摘进行约束,加上本金、过期和一次性政策。 任何修改字段都需要做出新的决定。
5. **一级拒绝** 模式拒绝、 过期的核准、 用户衰落和不安全的目的地为普通结果, 而不执行副作用 。 不要将拒绝转化为较弱的后退工具 。
6. **重新编造审计证据。** 记录谁问,使用哪个承认的描述和政策版本,什么是正常目标,为什么决定允许或拒绝,以及执行是否开始。 保存摘要或编辑了值而不是秘密。

每一步都会缩小下一个组件可能做的事情。 最后处理者应该收到一个已经验证的域命令, 而不是原始的文本和宽度的证书。 重复整个链条 MRTR 重试、 任务更新或网关前传调。 较早的核准不会将后来的请求转换为信任的会话流量 。

<a id="current-and-legacy-interaction-paths"></a>

### 当前和遗留的互动途径

Roots, Sampling,并且对新的2026-07-28执行程序进行记录。网关可能保留旧的求解通道代码,但只能作为版本配置兼容路径。

不要在每次会议周围建立新的防御 sampling 限制符。 将配额应用到认证的主机、发行者、资源、工具和时间窗口。 对于当前互动工作, 检查 MRTR 投入请求和回应。

<a id="stateless-transport-checks"></a>

### 无国籍运输检查

- 接受现代 MCP 消息在 POST 端点上 。
- 回到405 现代的Get和Dlelete。
- 不薄荷或依赖 `Mcp-Session-Id`.
- 忽略遗留的会话, 重放头作为权威输入 。
- 返回 JSON 或请求为该 PST 设定的 SSE 范围 。
- 使用 `subscriptions/listen` 仅用于选择的长期变更通知。

```figure
tp-tool-poisoning
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行一个小型的流程中安全网关模式。 它能够对工具全描述进行分类和输入, 报告元数据中毒和阴影, 验证现代请求信封和路径值, 并用签名进行双轮确认导出 `requestState` 和注射的共享重播店。

模型开始于 HTTP 适配器解析 JSON 和路径信头。 它不验证 `Content-Type` 或 `Accept`。连接同一调度员到 9 课的完整流体 HTTP 适配器, 需要 `Content-Type: application/json` 和一个 `Accept` 包含两个值的数值 `application/json` 和 `text/event-stream`.

运行：

```bash
cd phases/13-tools-and-protocols/15-mcp-security-tool-poisoning
python3 code/main.py
python3 -m unittest discover code/tests -v
```

样本有意变形描述符,扫描仪和摘要比较产生独立的结果。 `input_required` 和无国籍者重新尝试。

<a id="use-it"></a>

## 实际应用

Replace `SAFE_TOOLS` , 并使用您所批准的服务器上的常规快照。 保存证书和机密, 并不要在快照中出现。 在更新其摘要之前先审查每一个新的或修改过的描述符 。

在网关上,在发现时和发送前进行相同的检查。 缓存可以减少发现工作, 但缓存批准必须过期, 或当描述符更改时无效 。

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-threat-model.md`。它产生一个当前议定书 threat model 跨元数据,路径,能力,授权, MRTR,缓存、注册和兼容性边界。

<a id="exercises"></a>

## 练习

1. 将经认证的委托人和当前授权决定附在密封的 MRTR 状态,然后拒绝根据不同的本金重试。
2. 用一个持久性的有条件插入取代模拟重放存储,并证明两个过程不能同时要求一个不使用。
3. 在重放索赔后但在模拟导出前输入失败。定义和测试交易或 idempotency 规则能保证恢复的安全
4. 更改工具 `inputSchema` 无需改变描述,确认完整说明的标记
5. 添加一项政策,拒绝公众在 `tools/list` 校长不同
6. 模拟一个在网关后面的旧服务器。 请在明确显示后进行握手和会话行为 `2025-11-25` compatibility branch.

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| 元数据中毒 | 工具描述符中嵌入的指示或欺骗性索赔 |
| 鲁格拉 | 改为先前核准的描述符 |
| 工具尾随 | 重复不合格姓名造成的不明朗路线 |
| 页眉不匹配 | 运行信头和 JSON-RPC 体积差异、错误 `-32020` |
| 散列针 | 完整核定说明摘要 |
| MRTR | 服务器请求输入的不透明响应和重试模式 |
| `requestState` | 必须作为不信任输入处理的不透明圆边图案值 |
| 能力声明 | 协议兼容性声明,而非授权 |
| 隐形形式支持 | 空的 `elicitation` 能力对象,相当于窗体支持 |
| 合格的工具名称 | 稳定网关名称, 如 `notes.search` |

<a id="further-reading"></a>

## 进一步阅读

- [MCP 安全和信任指导](https://modelcontextprotocol.io/specification/2026-07-28#security-and-trust--safety)
- [Multi Round-Trip Requests](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
- [Streamable HTTP transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [Deprecated features](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
