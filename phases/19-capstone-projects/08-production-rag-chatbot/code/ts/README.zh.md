<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-08---production-rag-chatbot-typescript"></a>

# 石碑08 - 生产 RAG 查波特( 查波特) (Chatbot) (Chatbot) (Chatbot) (Chatbot) (Chatbot) (查波特) (Chatbot) (查波特) (Chatbot) (Chatbot) (美国首都首都)TypeScript)

聊天界面骨架, 流出一个引用启动的响应 。
事件,对 Python 管道投入 `../main.py`. 对话状态生活
键入的地图 `sessionId`,所以相同的会话ID可以驱动
多方向对话框。

<a id="layout"></a>

## Layout

```text
ts/
  package.json
  tsconfig.json
  src/
    index.ts        # entrypoint, demo + HTTP server
    server.ts      # hono app, /, /chat/stream (SSE), /sessions, /health
    session.ts     # SessionStore (Map<sessionId, Session>)
    stream.ts      # SSE frame encoder + parser + mock retrieval + tokenizer
    types.ts        # Session, Turn, Citation, KbEntry, SseEvent
  tests/
    session.test.ts
    stream.test.ts
    server.test.ts
```

<a id="run"></a>

## Run

```bash
npm install
npm run typecheck
npm test
npm start          # one self-check pass, exits 0
npm run serve      # interactive HTTP server on 127.0.0.1:<port>
```

交互式服务器在 `PORT` 取消设置,挂载聊天
HTML 客户端打开 `/`流经 `GET /chat/stream?sessionId=...&q=...`. 该
演示客户端使用 `EventSource` 并倾听 `session`, `citations`, `token`,
和 `done` events.

<a id="tests"></a>

## Tests

`node --test` 通过 tsx 运行。 覆盖 :

- 会话口: 创建、 查找、 附加、 列表、 无法调用缺失的代号 。
- SSE encoder + 剖析器圆轨;通过管辖区标记进行检索;
  tokenizer 后退 + “ 另见” 尾巴。
- Server: `/`, `/health`, `/chat/stream` 快乐路径(会话+引用+
  token +已完成),400 有关缺失的q, 多方向会话持久性,
  `/sessions` listing.
