<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-1903--realtime-voice-assistant-typescript"></a>

# 首席发言人19/03-实时语音助理(TypeScript)

Multi-file TypeScript web-client harness 用于 streaming 语音管道
说明 `../docs/en.md`。离线状态机器模拟加上实况
WebSocket 服务器支持 `ws` package.

<a id="layout"></a>

## Layout

```text
src/
  index.ts        entry point; runs two offline sessions, probes the live ws, exits 0
  server.ts       hono /healthz + ws upgrade via WebSocketServer
  orchestrator.ts IDLE -> LISTENING -> WAITING -> THINKING -> SPEAKING with barge-in
  vad.ts          turn-completion scorer + synthetic 20ms-frame generator
  protocol.ts     zod-validated frame envelope (event / summary)
  types.ts        AudioChunk, Metrics, SessionOptions, SessionSummary
tests/
  vad.test.ts
  orchestrator.test.ts
  protocol.test.ts
```

<a id="run"></a>

## Run

```bash
npm install
npm start                # runs two offline sessions + ws self-probe, exits 0
npm start -- --serve     # keep ws server up; ctrl-c to stop
npm test                 # node --test runner via tsx
npm run typecheck        # tsc --noEmit
```

非互动 `npm start` 路径中显示的纯正会话到达
`first_audio_out`,驳船会合记录至少一次驳船事件,
现场网络套接听器 `summary` 关闭前的框 。
