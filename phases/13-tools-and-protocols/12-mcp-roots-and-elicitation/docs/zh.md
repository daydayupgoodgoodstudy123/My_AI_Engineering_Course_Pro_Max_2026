<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="explicit-scope-and-stateless-elicitation"></a>

# 显式作用范围与无状态 Elicitation

> Roots 折旧 MCP 2026-07-28,从未成为保安 sandbox。在可见的工具参数或资源 URIs中设置范围,授权将其输入服务器,并使用 MRTR 当工具真正需要用户输入时。 用户看到决定, 模型看到控件, 任何服务器实例都可以处理重试 。

**类型:** Build
**语言:** Python
**先修要求:** 阶段13 -07 (MCP 13 11 (无 MRTR)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 替换已折旧的 Roots 具有明确的工作空间 parameters,资源 URIs,或服务器配置。
- 使用授权、路径控制、操作系统沙箱等不同范围提示。
- 交付形式模式 `elicitation/create` 通过 MRTR `input_required` 结果.
- Advertise elicitation 支持每个请求客户端能力, 拒绝不支持的模式 。
- Validate `accept`, `decline`, 和 `cancel` 它们是独特的结果。
- 将破坏性确认附在经认证的本金、原始论点、候选人系列和过期失效上。

<a id="two-problems-that-look-similar"></a>

## 两个问题看起来相似

便条工具收到此请求 : “ 删除旧的 TPS 报告 。 ”

服务器必须回答两个不同的问题。

1. 操作会触摸哪个工作空间?
2. 三个匹配的音符中,哪个是用户的意思?

第一个是范围和授权。 第二个是互动的模糊。 混合它们会导致危险的设计, 比如将客户端提供的文件夹作为调用者可以删除其内所有内容的证据 。

<a id="roots-are-a-migration-surface"></a>

## Roots 是一个迁移面

Earlier MCP 修改后让客户做广告 Roots 并在列表更改时通知服务器。 Roots 信息指导。 它们没有限制服务器进程可以读到的内容, 没有授权调用, 没有创建操作系统 sandbox.

MCP 2026-07-28 折旧 `roots/list` 和 `notifications/roots/list_changed` 更喜欢使用其中一种明显替换:

- 一个 `workspaceUri` 或 `directory` 工具参数,当每个呼叫的工程范围不同时。
- 当操作已经瞄准资源时, 资源 URI 。
- 当一个部署方拥有一个固定的工作空间时, 服务器配置 。
- 进程 sandbox 或被囚禁的文件系统 当代码在技术上 一定无法逃跑。

如果现有的2026-07-28融合仍然需要 `roots/list` 在折旧窗口中,服务器将其嵌入 MRTR `inputRequests`。它不能发送一个实时反向请求。这是一个迁移适配器;新的操作者应该接受明确的操作范围。

模型可以看到并重复一个明确的控件。 隐藏的运输会话范围更难检查、 重播、 审计和路线 。

<a id="the-three-layer-rule"></a>

### 三层规则

明确的 URI 仍然不能授权自己。

1. **Authorization:** 是否允许这位认证的校长使用这个工作空间?
2. **Containment:** 目标正统的URI是否停留在授权的工作空间边界内?
3. **Sandbox:** 操作系统能阻止一个失密的服务器逃跑吗?

可运行服务器保留了授权工作空间的允许列表, 将%编码路径正常化, 检查路径组成部分的真实边界, 并在删除前立即重新检查封隔 。

原始字符串前缀检查错误 :

```text
allowed:   file:///work/notes
attacker:  file:///work/notes-evil/secret.md
traversal: file:///work/notes/%2e%2e/private.md
```

两种敌对路径都以误导字符串开头。 首先将路径组件正常化, 然后比较路径组件。 生产文件系统服务器也必须防御符号链接竞赛和平台专用路径语义 。

<a id="elicitation-still-exists-but-delivery-changed"></a>

## Elicitation 仍然存在,但交付改变了

Elicitation 是当前客户端 feature 用于在 `tools/call`, `prompts/get`, 或 `resources/read`方法名称 `elicitation/create`。改变的是电线流的方向。

2026-07-28 服务器不发送反向 JSON-RPC 请求。 它返回 `InputRequiredResult`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resultType": "input_required",
    "inputRequests": {
      "delete_choice": {
        "method": "elicitation/create",
        "params": {
          "mode": "form",
          "message": "Choose one matching note and confirm deletion.",
          "requestedSchema": {
            "type": "object",
            "properties": {
              "note_id": {
                "type": "string",
                "enum": ["note-3", "note-7", "note-14"]
              },
              "confirm": {"type": "boolean"}
            },
            "required": ["note_id", "confirm"]
          }
        }
      }
    },
    "requestState": "integrity-protected-delete-state"
  }
}
```

主机生成表格。 用户可以接受、 明确拒绝或取消它。 然后客户端重试原始的 `tools/call` 带有新ID:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "notes_delete",
    "arguments": {
      "workspaceUri": "file:///Users/alice/Documents/Notes",
      "title": "TPS report"
    },
    "inputResponses": {
      "delete_choice": {
        "action": "accept",
        "content": {"note_id": "note-14", "confirm": true}
      }
    },
    "requestState": "integrity-protected-delete-state",
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "elicitation": {"form": {}}
      }
    }
  }
}
```

两个呼叫之间没有协议会话。 服务器验证回声状态, 校验响应与预期的策略, 检查选中的注释是否在签名的候选人集中, 重新授权工作空间, 重新检查封隔, 然后删除 。

<a id="capability-negotiation-is-per-request"></a>

## 能力谈判是按要求进行的

支持窗体模式的客户端 elicitation declares:

```json
{
  "io.modelcontextprotocol/clientCapabilities": {
    "elicitation": {"form": {}}
  }
}
```

空的 elicitation capability, `"elicitation": {}`,仍然等于只对表单的兼容性支持。 `"elicitation": {"form": {}}` 也支持窗体模式。仅使用 URL 的报表, `"elicitation": {"url": {}}`,则不。服务器不能嵌入当前请求能力所缺少的模式,即使先前的请求已经公布。

每一项请求也包含 `io.modelcontextprotocol/protocolVersion`返回。 `-32602`返回不支持的字符串 `-32022` 准确 `supported` 和 `requested` 数据。 丢失或仅使用 URL elicitation 支持返回 `-32021` 与 `data.requiredCapabilities` 设置为 `{"elicitation":{"form":{}}}`.

信封没有 JSON-RPC `id` 是一个通知。在不排放 JSON-RPC 成功或错误响应。 在流线上 HTTP,收到接受的通知 `202 Accepted` 没有尸体

`clientInfo` 诊断应列入,但需自我报告,无法确定用户。

服务器执行器 `server/discover` 返回 `supportedVersions`能力, 能力, `ttlMs`, 和 `cacheScope` 与 `resultType: "complete"`。它不做广告 Roots 因为它为工具做广告,它也强制实施 `tools/list`。结果返回确定论 `notes_delete` 描述符, 一个有效的对象 `inputSchema`,服务器身份元数据,以及公共缓存提示。

<a id="form-mode"></a>

## 窗体模式

窗体模式使用限制 JSON 用于可用对话框的“Schema” 。 根是一个对象, 其属性是平坦原始字段或支持的圆柱阵列。 深嵌对象和通用文档图则不属于确认对话框 。

使用窗体模式 :

- 选择数名候选人中的一名;
- 确认破坏性行动;
- 收集非敏感偏好;
- 收集用户而非模型必须决定的少量值。

不使用密码窗体模式, API 键, 访问 tokens或付款证明 那些秘密会通过 MCP 客户端, 并可以到达日志或模型上下文 。

服务器再次验证返回的内容。 客户端窗体验证会改善 UX, 但不会创建信任 。

<a id="url-mode"></a>

## URL 模式

URL 模式为频带外的交互作用发送安全网络 URL :

```json
{
  "method": "elicitation/create",
  "params": {
    "mode": "url",
    "message": "Connect the report service to continue.",
    "url": "https://mcp.example.com/connect/report-service"
  }
}
```

当敏感信息必须直接进入服务器控制的网络流时使用它, 如第三方授权。 客户端显示全部目的地并在打开前获得同意。 它不能预设 URL 。

一个 `accept` 响应表示用户同意打开 URL。 它没有证明外部流量已完成。 在重试时, 服务器检查自己的状态, 要么完成, 要么返回另一个 `input_required` 结果.

URL elicitation 而不是取代 MCP 客户端和 MCP 服务器。它是用于外部互动 MCP 服务器需要代表用户执行。 服务器必须将浏览器用户绑在开始的同一验证本位上 MCP operation.

<a id="response-branches"></a>

## Response Branches

将行动作为产品决定,而不是别名:

| 动作 | 含义 | 安全服务器行为 |
|--------|---------|----------------------|
| `accept` | 用户提交了互动 | 校验内容并继续进行 |
| `decline` | 用户明确拒绝 | 将完全的、非错误的拒绝结果退回 |
| `cancel` | 用户被开除或无法完成 | 安全停止并允许稍后重试 |

绝不将缺失的内容解释为同意。 绝不将衰落转换为重复 prompt loop.

<a id="protecting-destructive-mrtr-state"></a>

## 保护破坏性 MRTR State

候选人名单不能只以 prompt 或未签名的 Base64 值。 一个客户端控制着它发送到的所有信息 。

课程显示有以下状态有效载荷:

- 经认证的校长;
- 原产方法;
- 汇编 `workspaceUri` 和 `title`;
- 允许在表格中显示注解id;
- 运行阶段;
- 短时间过期。

在突变前, 服务器还检查了现场记录。 此记录会显示删除的比赛, 并在显示表单后将目标移动到工作空间以外 。

对于一次性财务或不可逆转的行动, HMAC 本身并不妨碍在过期期内重新播放有效状态。 将一个非自动存储和消费在每一个处理者共享的重放仓库中一次。 课程输入了被捆绑的、 TTL 打印过的存储并在进行模拟删除时保留原子索赔。 生产数据库应该将非自动请求和突变组合在一个交易或同等的有条件边界中。

在要求非自动反应之前验证交互作用。 `cancel` 执行不突变,并离开状态可重试到过期。 `decline` 是一个终端,所以该课消耗了nonece,没有删除任何内容。

```figure
t3-roots-boundary
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 展示现代 `notes_delete` tool:

- `tools/list` 返回带有所需工作空间和标题图案的确定性、可缓存描述符。
- 范围是明确的 `workspaceUri` argument.
- 服务器配置授权该工作空间用于课程主文 。
- URI normalization 拒绝前缀混乱,并编码过历。
- 每一次破坏性删除都需要形式模式 elicitation.
- 该 elicitation 内地旅行 `resultType: "input_required"`.
- Signed `requestState` 将确切的候选人名单和原始论点捆绑在一起。
- 被注入的重放存储拒绝在服务器中出现相同的被接受或拒绝状态 。
- 重试使用新请求代号并返回 `resultType: "complete"`.

数据存储在记忆中, 这样协议行为很容易检查。 数据库的安全规则保持不变 。

<a id="use-it"></a>

## 实际应用

从仓库根 :

```bash
cd phases/13-tools-and-protocols/12-mcp-roots-and-elicitation/code
python3 main.py
python3 -m unittest discover tests -v
```

Expected checkpoints:

- 发现广告工具 Roots.
- 工具发现返回 `notes_delete` 与 `resultType`,服务器身份和缓存提示。
- 请求代号 `1` 返回窗体 `inputRequests.delete_choice`.
- 请求代号 `2` 重复签名状态, 完成删除 。
- 前缀路径和编码的跨行路径都失败了 。
- 更改的标题不能重复原确认状态。
- 下降使得注数保持不变。
- 两个共享便条和重播状态的服务器对象无法同时执行一个确认 。
- 空和清晰的表单工作, 而只使用 URL 支持返回精确 `-32021` 格式要求。
- 不支持的版本失败使用精确值 `-32022` 数据形状。
- 无ID-通知产生 JSON-RPC response.

<a id="ship-it"></a>

## 交付成果

`outputs/skill-elicitation-form-designer.md` 设计明确的范围, 授权检查, MRTR 窗体,回应 branches,并声明约束性。它拒绝处理 Roots 以 A 为单位 sandbox 或通过窗体模式收集机密。

<a id="exercises"></a>

## 练习

1. 将模拟重放存储器替换为 SQLite。 使用一个交易来要求 process the unce 并删除便笺, 然后证明两个进程不能同时 commit.
2. Add `url` 能力谈判和带外设置流程。 `inputResponses`.
3. 将笔记本图替换为临时 SQLite 数据库。 重新检查突变交易中的授权和封隔 。
4. 添加一个用于执行真实文件系统的符号链接政策。 解释为什么光靠 URI 词汇封闭无法阻止符号链接的逃逸 。
5. 设计一个能绘制现代地图的2025-11-25调适器 MRTR 处理器输出到由遗留服务器启动的 elicitation。保持它与当前处理器的隔离。

<a id="key-terms"></a>

## 关键术语

| 术语 | 2026-07-28年的含义 |
|------|------------------------|
| Roots | 信息空间提示,而非授权或沙箱 |
| 明确范围 | 请求参数中可见的工作空间、目录或资源处理 |
| Containment | 将目标保留在边界内的正常路径组件检查 |
| Elicitation | Client feature 用于在 MCP operation |
| 窗体模式 | 使用限制平面图的带内结构化用户输入 |
| URL 模式 | 用于敏感或外部工作流程的带外互动 |
| MRTR | 无国籍输入要求的结果,然后是重新尝试 |
| `requestState` | 由服务器检查完完整无误的不透明状态回响 |
| Decline | 明确用户拒绝 |
| Cancel | 未经批准即予以开除或不完全的互动 |

<a id="legacy-compatibility"></a>

## 遗产兼容性

对于一个被困在2025-11-25的同伴, `roots/list`, `notifications/roots/list_changed`,并实时服务器启动 `elicitation/create` 可能仍然存在。 标签是适应者遗留的。 不允许遗留的“ 根” 列表绕过服务器授权, 并且不将协议会话假设带入现代处理器 。

<a id="further-reading"></a>

## 进一步阅读

- [MCP 2026-07-28 Elicitation](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation)
- [MCP 2026-07-28 Multi Round-Trip Requests](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
- [MCP 2026-07-28 Roots deprecation](https://modelcontextprotocol.io/specification/2026-07-28/client/roots)
- [MCP 2026-07-28服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
