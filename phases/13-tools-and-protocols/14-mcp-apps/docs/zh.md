<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-apps-on-the-stateless-protocol"></a>

# 无状态协议上的 MCP Apps

> 互动的结果仍然是 MCP 工具和资源交换。 2026-07- 28 核心使这种交换自成一体, 而 Apps 扩展则增加了沙箱浏览器表面 。

**类型:** Build
**语言:** Python
**先修要求:** 阶段13 -07 (MCP 服务器,第13阶段 · 10 (资源)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- Advertise MCP 应用程序通过 `server/discover` 和每个请求的扩展能力。
- 声明a `ui://` 工具上的资源。
- 返回2026-07-28号无国籍线上的完整工具和资源结果。
- 将应用程序分开 `ui/initialize` 桥上已删除的信件 MCP 核心握手。
- 应用原产地验证、沙箱、CSP和最不优惠的许可。

<a id="the-problem"></a>

## 问题

文本结果可以描述一个时间轴。 它不能给用户一个可以过滤、检查或采取行动的时间线 。

MCP 应用程序用可选扩展名解决演示文稿问题。工具定义指向 `ui://` 资源。 在工具运行前, 主机可以获取和审查该资源, 将其放在一个沙箱的iframe中, 并通过一个 JSON-RPC bridge.

核心协议在 2026-07- 28 年更改。 不要在旧连接生命周期中包扎 App :

- 根本就没有核心 `initialize` 请求或 `notifications/initialized` notification.
- 没有 `Mcp-Session-Id` header.
- 每项请求都包含协议版本和客户能力 `params._meta`.
- 服务器工具 `server/discover` 使客户能够检查版本、核心能力和扩展。
- 每一个成功的结果 `resultType` discriminator.
- Streamable HTTP 使用每个请求一个 PST。 现代 Get and DELETE 切入点返回 405 。

应用程序桥仍然有一个方法命名 `ui/initialize`。它属于 Irame 后Message 方言。它不重建核心 MCP session.

<a id="the-concept"></a>

## 概念

<a id="two-protocols-one-feature"></a>

### 两项协议,一项 feature

保持层的清晰度 :

1. 该 MCP 核心承载 `server/discover`, `tools/list`, `tools/call`, `resources/list`, 和 `resources/read`.
2. 该 MCP 应用程序扩展名宣布 UI, 并定义了 Iframe 到主机桥 。
3. Browser sandbox 规则限制UI能达到的程度。

扩展标识符是 `io.modelcontextprotocol/ui`。两个对等点都选择加入。客户端在能力对象中发送扩展支持,以响应每个请求:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "server/discover",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/ui": {}
        }
      },
      "io.modelcontextprotocol/clientInfo": {
        "name": "timeline-host",
        "version": "1.0.0"
      }
    }
  }
}
```

`clientInfo` 推荐进行诊断。这是自报数据,而不是授权身份。

<a id="discover-before-rendering"></a>

### 创建前发现

服务器的发现结果 广告扩展 :

```json
{
  "resultType": "complete",
  "supportedVersions": ["2026-07-28"],
  "capabilities": {
    "tools": {},
    "resources": {},
    "extensions": {
      "io.modelcontextprotocol/ui": {}
    }
  },
  "ttlMs": 300000,
  "cacheScope": "public",
  "_meta": {
    "io.modelcontextprotocol/serverInfo": {
      "name": "timeline-app-server",
      "version": "2.0.0"
    }
  }
}
```

服务器必须支持发现。 客户在每次行动之前, 都不会被迫呼叫发现, 因为每次行动都具有自身的能力 。

<a id="declare-the-ui-on-the-tool-definition"></a>

### 声明工具定义上的 UI

现代应用程序合同将UI与工具结合到 `tools/list`:

```json
{
  "name": "notes_timeline",
  "description": "Render a timeline of notes.",
  "inputSchema": {
    "type": "object",
    "properties": {}
  },
  "_meta": {
    "ui": {
      "resourceUri": "ui://notes/timeline.html"
    }
  }
}
```

这是故意的预调元数据。 主机可以预先装入、缓存和安全审查 HTML 后, 将请求显示它。 旧的平面元数据键可能会被兼容代码所接受, 但新服务器应该释放嵌套 `_meta.ui.resourceUri` form.

`tools/list` 在当前核心中可缓存。包括确定性排序, `ttlMs`, 和 `cacheScope`. 使用 `private` 当可见工具因用户或用户而异时 token.

<a id="return-data-then-let-the-host-bind-the-view"></a>

### 返回数据,然后让主机绑定视图

该 tool call 返回普通内容加上结构化数据:

```json
{
  "resultType": "complete",
  "content": [
    {"type": "text", "text": "Timeline ready."}
  ],
  "structuredContent": {
    "notes": [
      {"id": "note-1", "title": "Discover", "created": "2026-07-28"}
    ]
  },
  "isError": false
}
```

主机已经知道哪个视图属于工具。 避免发明新的内容块以重复 URI 。

<a id="serve-the-app-as-a-resource"></a>

### 将应用程序作为资源使用

服务器广告 `resources` 也执行强制 `resources/list` 。它的确定列表条目包括一个稳定的名、描述和 MIME 类型。 `resultType`服务器身份元数据 `ttlMs`, 和 `cacheScope`,就像确定性工具列表。

主机发送 `resources/read`。在可移动的 HTTP请求中:

```text
POST /mcp
MCP-Protocol-Version: 2026-07-28
Mcp-Method: resources/read
Mcp-Name: ui://notes/timeline.html
```

页眉值和 JSON-RPC 匹配。不匹配是协议错误 `-32020`.

结果包含 HTML 资源和缓存提示 :

```json
{
  "resultType": "complete",
  "contents": [
    {
      "uri": "ui://notes/timeline.html",
      "mimeType": "text/html;profile=mcp-app",
      "text": "<!doctype html>...",
      "_meta": {
        "ui": {
          "csp": {
            "connectDomains": [],
            "resourceDomains": [],
            "frameDomains": [],
            "baseUriDomains": []
          },
          "permissions": {}
        }
      }
    }
  ],
  "ttlMs": 60000,
  "cacheScope": "public"
}
```

<a id="cache-ui-resources-as-executable-content"></a>

### 缓存用户界面资源作为可执行内容

App 资源不能与普通版本互换。 它的缓存条目可以执行桥码, 生成工具数据, 并请求主机调解动作 。 关键值为 Canonical `ui://` URI、 接收服务器身份和版本、 资源内容摘要以及当 `cacheScope` 绝对不要在主机之间再使用私人 App 资源,因为 HTML 或即使URI相同,其政策元数据也可能不同。

当条目 `ttlMs` 过期,工具 `_meta.ui.resourceUri` 设置了自动修改,服务器版本或被允许的描述符针修改,或者确认的资源更改订阅名称 URI。重试并重新应用 CSP 和权限审查后再重新安装。一个简略的ibrale 框架不能仅仅因为新资源版本尚未装入而保留更广泛的权限 。

<a id="reject-wire-ambiguity-before-feature-policy"></a>

### 之前拒绝线条模糊 feature policy

验证有故意的顺序。 JSON-RPC 形状, 并需要字符串协议元数据加上对象客户端能力映射。 接下来比较路径标题与正文。 只有这样, 才能决定匹配的协议版本是否被支持。 此命令阻止代理服务器解释不同的请求 。

| Condition | HTTP | JSON-RPC 错误 |
|-----------|------|----------------|
| 页眉和体型、方法或名称不一致 | 400 | `-32020` |
| 页眉和正文就一个不支持的版本达成一致 | 400 | `-32022`, 与 `data` exactly `{"supported":["2026-07-28"],"requested":"<actual>"}` |
| `resources/read` 缺乏应用程序扩展能力 | 400 | `-32021`, 与 `data.requiredCapabilities.extensions.io.modelcontextprotocol/ui` |
| 方法未知 | 404 | `-32601` |

一个 JSON-RPC 通知没有 `id`,服务器从不发布 JSON-RPC 被接受的 HTTP 通知返回空体 202。错误可以更改 HTTP 状态, 但仍无法创建 JSON-RPC 通知时出错 。

<a id="the-sandbox-is-a-boundary-not-a-trust-verdict"></a>

### 该 sandbox 是一个边界,不是信任判决

主机控制了 iframe 。 App 不能直接读取主机 cookies、 本地存储或页面 DOM 。 所有特许工程都必须通过桥 。

使用这些默认值 :

- 将所有 CSP 域列表都空, 然后只添加 App 需要的源代码 。 `connectDomains` 用于获取、 XHR 和 WebSocket; 使用 `resourceDomains` 用于脚本、样式、图像和字体。
- 实际操作时,将代码和数据捆绑在一起。
- 要求不使用相机、麦克风或位置许可,除非有可见 feature 需要它。
- Pin `postMessage` 拒绝来自其他任何来源的事件。
- 将工具参数、工具结果、资源文本和连接信息作为不信任的输入处理。
- 保持用户在主机中的同意。 iframe 不能批准它自己相应的动作 。

不复制已修正的 `sandbox` 属性。主机必须选择基于 App 的源模式和它自己的孤立设计。

允许的域仍然是一条排泄路径。 `connectDomains: ["https://api.example.com"]` 表示在 App 中执行的脚本可以将允许的数据发送到那里。精确的源匹配可以防止目标混淆,但不能决定有效载荷是否合适。默认情况下保持空连接访问,避免放置挂载器 tokens 在iframe中,代理操作在实际操作时通过主机进行,限制响应和请求大小,以及审计用户行动导致每项外向请求。 `resourceDomains` 与 `connectDomains`; 装入字体或脚本的许可不应允许任意上传数据。

<a id="the-apps-bridge-has-its-own-lifecycle"></a>

### 应用桥有自己的生命周期

应用程序桥是 JSON-RPC 方言结束 `postMessage`。它可以交换 `ui/initialize` 和 `ui/*` 通知和可代理核心外观方法,例如 `tools/call`.

视图发送 `ui/initialize` 与 `appInfo` 和一个 `appCapabilities` 对象。主机返回其能力和主机上下文。只有在响应后,视图才会发送 `ui/notifications/initialized`。在向视图发送信件之前,主机必须等待此 Apps 通知。

当地握手在一框架和一个主机框架之间搭建了一座桥梁。 MCP 协议版本, 创建服务器状态, 或薄荷运输会话。 注意准确的前缀: 核心 `notifications/initialized` 被删除, 而 Apps `ui/notifications/initialized` 由一对桥梁产生的核心请求 tool call 是一个新的自足请求, JSON-RPC 身份和请求的全部元数据。

<a id="host-context-actions-and-revocation"></a>

### 主机环境、动作和撤销

首选项在启动桥后仍为权限。 视图可以要求工具动作、 导航、 剪贴板使用或者其它特惠效果, 只能通过所发布功能进行 。 主机验证了打印的请求、 当前用户、 目标以及参数, 应用了批准策略, 并可能拒绝 。 按下按钮和有效的桥状信件表示意向; 既不授予授权 。

将主题、大小和无障碍性视为不断变化的主机环境,而不是一次性的投入:

- 应用主机提供的颜色和打字 tokens, 然后 react 当主题或对比偏好改变时。
- 让“ 视图” 报告想要的维度, 但让主机上限并应用irame 大小, 这样内容无法摆脱其布局或制造欺骗性重叠 。
- 保存键盘顺序、可见焦点、可访问名称、屏幕阅读器状态、足够对比度、缩放和在iframe 内降低动作行为。
- 调整大小和重置后, 重新测试主机控件与视图控件之间的焦点传输 。

操作时, 不仅在操作期间, 还可以在操作时检查能力和授权 。 `ui/initialize`。在取消时,拒绝尚未取消的特权电话,停止不再符合政策的网络活动,明确敏感状态,并在UI资源本身不再被接受时重新挂载或倒回文本。视图必须处理拒绝作为正常结果,直到主机让出时再尝试。

<a id="fallback-is-part-of-the-contract"></a>

### 撤退是合同的一部分

Apps-awe 服务器仍然可以为不发布 UI 扩展名的主机服务 :

- 返回同一工具 `_meta.ui` 在 `tools/list`.
- 保留有用的文本结果 `tools/call`.
- Refuse `resources/read` 显示显示显示丢失能力错误的 UI 。
- 在决定工具是否完成时,绝不假设存在一个框架。

```figure
t3-ui-sandbox
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 建立一个小的在轨协议模型,不使用 SDK。它验证当前请求信封和可移动 HTTP 路线值, 广告 `server/discover`,列出工具和资源,执行该工具,并服务于一个自成一体的工具 HTML resource.

模型接收已经解析的物体和路由信头。 它不是一个完整的 HTTP 适配器, 不分析 `Content-Type` 或 `Accept`。使用 09 课来完成全流 HTTP 需要的适配器 `Content-Type: application/json` 和一个 `Accept` 包含两个值的数值 `application/json` 和 `text/event-stream`.

运行：

```bash
cd phases/13-tools-and-protocols/14-mcp-apps
python3 code/main.py
python3 -m unittest discover code/tests -v
```

检查输出中的四点:

1. 每一个电话都是独立的
2. 每一个请求都 `_meta` capabilities.
3. `resources/list` 返回任何资源读取前的稳定的描述符。
4. 每一个结果 `resultType` 和服务器身份元数据。
5. 没有显示核心会话标识符 。

<a id="use-it"></a>

## 实际应用

以 `server/discover`确认 `io.modelcontextprotocol/ui` 显示在服务器扩展映射中。 然后调用 `tools/list` 两次,一次具有 Apps 能力,一次没有它。 第一个响应声明资源。 第二个仍然是可用文本工具 。

Read `ui://notes/timeline.html`搜索 HTML 用于 `hostOrigin` 以及该 `event.origin` 守卫,这两条线是 最起码的明显证据

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-apps-spec.md`。在写入框架代码之前,使用它来审查 App 合同。它迫使作者声明当前的核心信封、扩展谈判、后备、UI资源、缓存政策、 CSP、 许可、 桥段方法和同意边界 。

<a id="exercises"></a>

## 练习

1. 将客户端能力更改为空扩展映射。 确认 `tools/list` 保留工具,但删除界面绑定。
2. Send `Mcp-Name: ui://notes/other.html` 与读取时间线的物体。 确认错误 `-32020`.
3. 将资源更改为 `cacheScope: private`。描述用户特有的条件,以证明它是合理的。
4. 将脚本移动到 `https://static.example.com/app.js`。 `resourceDomains` 并解释新的供应链风险。
5. 添加一个 `notes_open` 工具, 并选择单击主机的按钮。 在主机中保持用户的认可 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| MCP Apps | 交互式可选扩展名 HTML 由 MCP host |
| `io.modelcontextprotocol/ui` | 由两个同行公布的扩展标识符 |
| `ui://` | App 界面模板的资源方案 |
| `text/html;profile=mcp-app` | MIME 类型 MCP App HTML |
| `server/discover` | 用于协议和能力发现的现有RPC |
| `resources/list` | 服务器在公布资源时必须使用的资源列表方法 |
| `resultType` | 现代成功结果所需的歧视者 |
| `ui/initialize` | 首个应用程序桥请求, 与删除的核心初始化分开 |
| `ui/notifications/initialized` | 查看主机响应后发出的准备状态通知 |
| CSP | 限制脚本、样式、图像和网络来源的浏览器政策 |
| 文本后退 | 工具行为被保留到主机中, 但没有 Apps 支持 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP 2026-07-28 基本协议](https://modelcontextprotocol.io/specification/2026-07-28/basic)
- [MCP 应用程序概览](https://modelcontextprotocol.io/extensions/apps/overview)
- [MCP 应用程序构建指南](https://modelcontextprotocol.io/extensions/apps/build)
- [官方扩展支助矩阵](https://modelcontextprotocol.io/extensions/client-matrix)
