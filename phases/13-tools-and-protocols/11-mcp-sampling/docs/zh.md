<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-model-input-sampling-migration-and-stateless-mrtr"></a>

# MCP 模型输入：Sampling 迁移与无状态 MRTR

> MCP 2026-07-28 折旧 Sampling 用于新设计并删除服务器到客户请求频道。如果现有的工作流程仍然需要客户的模型,服务器返回 `input_required` ,然后客户端用模型输出重新检查原始请求。推理循环在协议层变得清晰、有条不紊和无国籍。

**类型:** Build
**语言:** Python
**先修要求:** 阶段13 -07 (MCP 10(资源和 prompts)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下 Sampling 折旧 MCP 选择新服务器的直接模型整合默认值。
- 实施包含兼容性工作流程 `sampling/createMessage` through Multi Round-Trip Requests (MRTR).
- 将协议修订和客户能力纳入每一项请求 `_meta` object.
- 返回 `resultType: "input_required"` 并用新旧的方法重试 JSON-RPC id.
- Integrity-protect `requestState` 并约束它与主控、方法、论点和失效。
- 带能力检查、批准、反应验证和圆圈的圆形模型辅助环。

<a id="the-decision-before-the-protocol"></a>

## 本议定书之前的决定

工具, 如 `summarize_repo` 需要两种工作:

1. 确定性工作: 列出文件、 读取允许的文件、 验证路径、 并组装内容 。
2. 示范工作:选择具有代表性的文件,并综合摘要。

你现在有两个有效的建筑

<a id="new-server-integrate-with-a-model-provider-directly"></a>

### 新建服务器: 直接与一个模型提供者整合

这是当前默认的。 服务器拥有模型选择、 证书、 预算、 重试, 以及 observability返回一个普通 `tools/call` 数据 MCP client.

当服务器已经是主机服务时, 或者当可预测的模型行为比使用主机模式更重要时, 请选择此项 。

<a id="existing-sampling-workflow-migrate-it-to-mrtr"></a>

### Existing Sampling 工作流程: 迁移到 MRTR

Sampling 目标为 2026-07-28 的服务器无法发送一个实况 `sampling/createMessage` 请求返回客户端。 它反而将请求嵌入 `InputRequiredResult`.

仅在使用客户的模型和证书是真正的产品要求时选择此兼容路径。 记录删除计划, 因为新执行不应采用折旧 Sampling.

<a id="the-stateless-contract"></a>

## 无国籍合同

2026年7月的协议没有 `initialize` 交换,无 `notifications/initialized`,没有 `Mcp-Session-Id`。每一项请求都包含以前握手时所提供的信息:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "summarize_repo",
    "arguments": {"audience": "developer"},
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {"sampling": {}},
      "io.modelcontextprotocol/clientInfo": {
        "name": "lesson-client",
        "version": "1.0.0"
      }
    }
  }
}
```

服务器对每个请求的修订版进行验证。 缺少或非字符串版本无效参数, `-32602`返回不支持的字符串 `-32022` 具有准确数据 `{"supported":["2026-07-28"],"requested":"<client version>"}`. 失踪 Sampling 能力返回 `-32021` 与 `data.requiredCapabilities` 设置为 `{"sampling":{}}`.

信封没有 JSON-RPC `id` 是一个通知。 接收者可以处理它, 但既不发出成功响应, 也不发出错误响应。 流经可变的响应 。 HTTP 适配器返回 `202 Accepted` 没有接受通知的机构。

服务器也执行 `server/discover` 与准确的 `supportedVersions` 关键,能力, `ttlMs`, 和 `cacheScope` 使客户在调用工具之前可以学习并隐藏服务器合同。因为发现广告 `tools`,服务器还强制执行 `tools/list`. 其决定性 `summarize_repo` 描述符包含一个有效的对象 `inputSchema`, `resultType: "complete"`,服务器身份元数据,以及公共缓存提示。

现代成果中,每个成功的结果都具有歧视性:

- `resultType: "complete"` 表示操作已完成 。
- `resultType: "input_required"` 表示客户端必须满足嵌入请求并重试 。
- 扩展可定义其他结果类型。任务扩展可添加 `"task"` 13课

<a id="one-mrtr-round"></a>

## One MRTR Round

服务器在处理请求时无法调用客户端。 它返回此结果 :

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resultType": "input_required",
    "inputRequests": {
      "pick_files": {
        "method": "sampling/createMessage",
        "params": {
          "messages": [
            {
              "role": "user",
              "content": {
                "type": "text",
                "text": "Choose three representative files and return a JSON array."
              }
            }
          ],
          "systemPrompt": "Return only the requested value.",
          "modelPreferences": {
            "costPriority": 0.8,
            "intelligencePriority": 0.2
          },
          "maxTokens": 400
        }
      }
    },
    "requestState": "opaque-integrity-protected-value"
  }
}
```

客户端确认支持 Sampling,然后发送一份带有不同 JSON-RPC id:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "summarize_repo",
    "arguments": {"audience": "developer"},
    "inputResponses": {
      "pick_files": {
        "role": "assistant",
        "content": {
          "type": "text",
          "text": "[\"README.md\", \"server.py\", \"docs/intro.md\"]"
        },
        "model": "host-model",
        "stopReason": "endTurn"
      }
    },
    "requestState": "opaque-integrity-protected-value",
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {"sampling": {}}
    }
  }
}
```

重试不是协议会话的续发。 这是重复原始方法和参数的新请求, 只添加当前回合的 `inputResponses`,并回声 `requestState` 字节字节。

MRTR 仅允许在 `tools/call`, `prompts/get`, 和 `resources/read`服务器不能返回 `input_required` 来解释一下无关的方法

<a id="multi-round-state"></a>

## 多声状态

这堂课需要两个示范电话:

1. `pick_files` 返回“a” JSON array.
2. `summary` 返回最后的转文。

每个重试只包含该回合的响应。 因此服务器将阶段和验证的中间数据放到下一个 `requestState`.

将此值作为攻击者控制值。 签名一个原始相位名称是不够的。 将状态绑绑到 :

- 认证的委托人,而不是自我报告 `clientInfo`;
- 原产方法;
- 原论点摘要;
- 短时间失效;
- 并验证中间值。

不需要保密时使用 HMAC 。 当客户端不能读取状态时, 请使用已验证的加密 。 拒绝错误的签名、 过期的值、 更改的本金或更改的参数 `-32602`.

客户端不能分析或修改 `requestState`。它唯一的工作就是回响 精确的字符串在重试。

<a id="model-preferences-are-hints"></a>

## 模式首选项是提示

`costPriority`, `speedPriority`, 和 `intelligencePriority` 客户可以忽略这些选择,因为客户拥有模式政策。

Keep `includeContext` 在 `"none"` 如果您保留了遗产 Sampling 其他环境模式增加了渗漏风险,而且本身也有所退化。

<a id="safety-invariants"></a>

## 安全性变化

客户是 trust boundary 嵌入 Sampling requests.

- 显示用户在政策需要批准时, 服务器正在要求模式做什么 。
- Cap MRTR 圆形。 恶意服务器也可以创建模型循环 。
- 校验每个 sampling 使用文件名、 URL 或工具输入前要先回应 。
- 限制字节和 tokens 每圆。
- 拒绝未以当前客户能力申报的输入请求 。
- 使模型输出超出授权决定范围。
- 记录原始方法和输入请求密钥而不记录敏感 prompt content.

`clientInfo` 和 `serverInfo` 显示和诊断元数据。既不能用作验证身份,也不能用作验证身份。

```figure
t3-sampling-flip
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行完整的双轮流动,无第三方包件:

- `server/discover` 返回 `supportedVersions`,发布工具支持,并返回缓存提示。
- `tools/list` 返回可缓存的确定性 `summarize_repo` 带有对象输入图的描述符。
- `tools/call` 验证每个请求的元数据。
- 首个结果嵌入 `sampling/createMessage` 用于选择文件。
- 第一次重试验证模型结果,并嵌入第二个请求。
- HMAC-protected `requestState` 具有独立请求之间的阶段。
- 最终结果的使用 `resultType: "complete"`.

假主机模式使示例具有决定性。 只替换 `fake_host_model` 服务器端的状态机器应该保持确定性和可测试性。

<a id="use-it"></a>

## 实际应用

从仓库根 :

```bash
cd phases/13-tools-and-protocols/11-mcp-sampling/code
python3 main.py
python3 -m unittest discover tests -v
```

Expected checkpoints:

- 发现返回完整结果 `ttlMs` 和 `cacheScope`.
- 工具发现返回相同的排序描述符 `resultType`,服务器身份和缓存提示。
- 缺少能力和未支持版本使用精确 `-32021` 和 `-32022` 错误数据 。
- 无ID-通知产生 JSON-RPC response.
- 请求代号为 `[1, 2, 3]`,证明 MRTR 圆是独立的。
- 前两个结果 `input_required`.
- 最后结果 `complete` 并包含所选文件加摘要。
- 更改重试的原始参数失败了请求状态检查 。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-sampling-loop-designer.md` 是一个移民计划者。 Sampling 需要兼容性时,可生成 MRTR 轮,州约束,能力门,预算,验证和清除计划。

<a id="exercises"></a>

## 练习

1. 更改文件选择响应为无效 JSON服务器返回 `-32602` 而不是信任模型输出。
2. Change `audience` 解释为什么密封的州区块交叉请求重复使用。
3. 添加第三回合, 请主机对摘要进行评议。 将早期摘要放在签名状态内, 并限制整个流程为三轮 。
4. Remove Sampling 将虚假的主机回调替换为服务器所属的模型适配器。 列出哪个批准、 计费以及 observability 责任转到服务器上
5. 使用 a 添加过期测试 state value 已经过了最后期限的一秒钟了

<a id="key-terms"></a>

## 关键术语

| 术语 | 2026-07-28年的含义 |
|------|------------------------|
| Sampling | Deprecated feature 要求客户模式完成 |
| MRTR | 请求期间客户端输入的不规则重试模式 |
| `InputRequiredResult` | 结果 `resultType: "input_required"` |
| `inputRequests` | 服务器指派嵌入地图 elicitation, sampling, 或 roots requests |
| `inputResponses` | 本轮客户的成绩键 `inputRequests` |
| `requestState` | 由客户对不透明服务器状态进行回馈并得到服务器验证 |
| `resultType` | 现代要求的歧视问题 MCP 结果 |
| 直接模式整合 | 建议替换需要模型的新服务器 inference |
| 能力门 | 防止客户发送内嵌请求的规则没有公布 |
| 循环预算 | 最大子弹, tokens,字节,时间和花费允许操作 |

<a id="legacy-compatibility"></a>

## 遗产兼容性

被锁定在2025-11-25的客户仍可能使用旧服务器 `sampling/createMessage` 运行于一个连接。 仅将该行为保留在版本特定的适配器中。 不要将循环路径变成一个 2026-07- 28 服务器的架构 。

Official SDKs 能够翻译现代 `input_required` 处理器为旧的对等点。 shim 是兼容性边界, 不允许添加新的会话逻辑 。

<a id="further-reading"></a>

## 进一步阅读

- [MCP 2026-07-28 Multi Round-Trip Requests](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
- [MCP 2026-07-28变化](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [MCP Sampling deprecation](https://modelcontextprotocol.io/seps/2577-deprecate-roots-sampling-and-logging)
- [MCP 2026-07-28服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
