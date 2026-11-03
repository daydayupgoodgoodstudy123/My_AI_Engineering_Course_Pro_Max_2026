---
name: mcp-apps-spec
description: Design and review an MCP App contract on the stateless 2026-07-28 protocol.
version: 2.0.0
phase: 13
lesson: 14
tags: [mcp, apps, stateless, ui-resources, csp, sandbox]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 MCP 工具可能需要交互视图,产生框架中立合同。

<a id="required-inputs"></a>

## 所需投入

- 工具名称、参数、普通文本结果和结构化结果。
- 用户互动视图必须支持 。
- 数据敏感性和答复是否因授权情况而异。
- 浏览器权限和视图需要的外部源代码 。
- 用于不支持 Apps 的只文本行为 。

<a id="produce"></a>

## Produce

1. 当前核心信封。 显示 `2026-07-28`,按请求 `protocolVersion`, `clientCapabilities`, 推荐 `clientInfo`,匹配 `Mcp-Method` 和 `Mcp-Name` 信头, `resultType` responses.
2. 发现条目。 广告 `io.modelcontextprotocol/ui` 在 `server/discover`,与保守 `ttlMs` 和 `cacheScope`.
3. 工具声明。 嵌套 `_meta.ui.resourceUri` 返回的工具上的 `tools/list`。不要等待 `tools/call` 来揭发UI
4. 资源合同。 `resources/list` 之前的元数据 `resources/read`。给一个金刚石 `ui://` URI, 稳定名称和描述, `text/html;profile=mcp-app`,缓存提示, CSP 域列表(`connectDomains`, `resourceDomains`, `frameDomains`, `baseUriDomains`),以及最小权限对象。
5. 结果合同。 返回有用的文字和结构化数据, 无论主机是否提供应用程序 。
6. 桥桥合同。 列出每份应用程序 `ui/*` 或代理方法, 精确的信息来源, 参数图案, 结果图案, 以及主机方的同意检查 。
7. 返回。 当客户端省略 Apps 扩展能力时, 描述工具及其结果 。
8. 核实表。 HTTP 400 `-32020` 路由前头不匹配, HTTP 400 `-32022` 具有准确支持和请求的版本数据, HTTP 400 `-32021` 与 `data.requiredCapabilities`, HTTP 404 `-32601`,202个空体通知,违反CSP,不可信的内容,未经授权的桥接和文本回退。
9. 传输边界。 如果执行收到解析的请求和信头, 标记它为进程内协议模式, 并将其连接到 9 课的完整流流 HTTP 适配器,真正的适配器必须 JSON 内容类型和包含该值的接受值 JSON 加上SSE(SSE),我发现他已经...

<a id="hard-rejects"></a>

## 艰难的拒绝

- 核心 `initialize`, `notifications/initialized`, 或 `Mcp-Session-Id` 以当前方式显示的路径 MCP.
- 通配符 `postMessage` 目标来源或跳过的接收器 `event.origin` validation.
- 工具运行后才会显示 UI 绑定 。
- 通配符 CSP 域列表, 未登录网络来源, 或没有可见权限的允许 feature.
- User-controlled HTML 插入时没有定义的清扫边界。
- 相应的 UI 动作, 将 iframe 点击作为主机授权 。
- 广告资源但省略的服务器 `resources/list`.
- 任意 JSON-RPC 通知的回复机构 `id`.

<a id="compatibility-boundary"></a>

## 兼容边界

遗留的平面 UI 元数据可以被解读为后退, 但新输出使用嵌套 `_meta.ui.resourceUri`. `ui/initialize` 只有在指定为 Apps 后Message 握手时才允许。 它从不支持删除 MCP 核心初始化。

<a id="output-format"></a>

## 输出格式

返回带有以下标题的缩略语设计: Core 线、 发现器、 工具、 资源、 结果、 桥梁、 安全、 后退、 验证。 以最小风险来源、 许可或同意假设结束 。
