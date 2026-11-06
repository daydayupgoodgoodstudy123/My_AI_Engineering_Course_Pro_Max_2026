<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="lesson-13---stateless-mcp-server-typescript"></a>

# 课程13 - Stateless MCP 服务器( F)TypeScript)

TypeScript 半块墓碑 Python 侧面 (P)`code/main.py`船舶
注册和政策大门;该项目是 MCP 运输:手动滚动
newline-delimited JSON-RPC 2.0 平整,三部模拟事件工具
implements MCP `2026-07-28` 直接,无 `@modelcontextprotocol/sdk`那样
你可以检查每个字节的线。

尽管模拟事件存储库的数据一直存在,但协议是无国籍的。
每项请求都重复其协议版本和客户能力
`params._meta`; 没有连接、 进程或先前的请求建立
服务器显示强制 `server/discover`,在
并公布可缓存的工具列表。
`tools/call` 验证针对同一条条框框的图案的论据
`tools/list`; 已知工具的错误参数返回完整的工具结果
与 `isError: true` 永远也别想到达它的执行者

运行时间身份是 `com.example/internal-incidents`。它使用反向 DNS
校验的命名空间 `example.com` 出版商。 出版的匹配
`server.json` 本地人必须使用同一名称 npm 软件包中含有
私人项目名称。

<a id="layout"></a>

## Layout

```text
src/
  index.ts      entry: fixture demo (default) or stdio loop (--serve)
  transport.ts  stdin readline + fixture replay
  protocol.ts   request validation / server/discover / tools/list / tools/call
  tools.ts      three incident tools + executors
  types.ts      JSON-RPC + tool shapes
tests/
  protocol.test.ts  stateless metadata, discovery, tools, errors, roundtrip
```

<a id="run"></a>

## Run

```bash
npm install
npm run typecheck
npm test
npm start            # self-terminating fixture demo
npm run serve        # real stdio loop (waits on stdin)
```

演示是自我终结的。 真正的标准服务器在输入前保持生命状态
流关闭; 没有 MCP 关闭请求或初始化握手。
