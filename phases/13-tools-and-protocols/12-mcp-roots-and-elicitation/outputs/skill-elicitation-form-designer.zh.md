---
name: elicitation-form-designer
description: Design explicit resource scope and stateless MCP 2026-07-28 elicitation with authorization, safe forms, and signed retry state.
version: 2.0.0
phase: 13
lesson: 12
tags: [mcp, elicitation, mrtr, scope, authorization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


设计用户输入步骤 MCP 运行目标协议修改 `2026-07-28`.

显示 :

1. Scope contract。将工作空间、目录或资源 URI 放在可见的工具参数或服务器配置中。验证主机的状态可以使用它。
2. 边界检查。 定义 URI normalization、路径构件控制、象征性链接政策和操作系统 sandbox.
3. 触发条件。 列出需要用户输入的精确模糊度、 确认度或外部互动 。
4. 发现和功能大门。 `supportedVersions`能力, 能力, `ttlMs`, 和 `cacheScope` 来自 `server/discover`。如果工具被公布,则包括强制性的确定性 `tools/list` 带有有效对象的描述符 `inputSchema`,服务器身份元数据,以及缓存提示。 `elicitation: {}` 明确 `elicitation.form` 拒绝缺失的或仅使用 URL 支持 `-32021` 和 `data.requiredCapabilities.elicitation.form`; 使用 `-32022` 准确 `supported` 和 `requested` 不支持版本的数据 。
5. MRTR 返回 `resultType: "input_required"` 有个马厩 `inputRequests` 键和 `elicitation/create` request.
6. 互动设计。对于窗体模式,请提供一个普通信息并限制平面图案。对于 URL 模式,请显示 HTTPS 目的地和带外完成规则。
7. 重试合同。 需要新版本 JSON-RPC id, 原始方法和参数, 当前 `inputResponses`,按请求 `_meta`,并精确 `requestState` echo.
   从未收到过无识别通知 JSON-RPC 结果或错误; 一个已接受的流 HTTP 收到通知 `202` 没有尸体
8. Branch 正在处理。 `accept`, `decline`, 和 `cancel` 与不同的安全结果。
9. 国家保护。 绑住 HMAC 或对经认证的本金、 原始参数摘要、 候选集、 操作阶段、 过期和一次性失效进行加密。 将非原子化的重播存储器安装在每个处理器都共享的捆绑的、 TTL 打印的重放存储器中 。
10. 最终重新确认,重新检查授权,现场记录状态,在突变前立即封存

艰难的拒绝 :

- 治疗已衰竭 Roots 授权、封隔或沙箱
- 使用 `roots/list` 或 `notifications/roots/list_changed` 设计了2026-07-28的新设计
- 发送反向 `elicitation/create` 而不是通过请求返回 MRTR.
- 正在收集密码, API 键, 访问 tokens,或表格形式的付款证明。
- 发送 elicitation 模式中,当前每个请求能力中缺少该模式。
- Treating `clientInfo` 是一个经认证的用户身份。
- 在确认接受和最后批准检查之前采取破坏性行动。
- Unsigned `requestState` 载有候选人或与许可有关的数据。

拒绝规则 :

- 重复拒绝 prompts 明确拒绝后
- Refuse elicitation 服务器可以生成或验证一个值,无需用户。
- 拒绝包含证书、用户机密或事先认证的记名值的 URL 。
- 拒绝使用隐藏的协议会话状态的请求, `initialize`, 或 `Mcp-Session-Id`.

输出一页设计,包括范围、授权、封隔、互动模式、图案或 URL, MRTR 线形、状态字段、响应 branches,重新播放政策,最后重新验证核对表。
