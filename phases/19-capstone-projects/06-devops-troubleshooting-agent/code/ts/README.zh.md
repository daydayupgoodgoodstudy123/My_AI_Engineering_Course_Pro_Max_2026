<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-06---devops-troubleshooting-agent-typescript"></a>

# 综合项目06 - 脱氧核糖核酸故障排除 Agent (TypeScript)

黑社会组织骨架待命 agent 在 `../main.py`显示 a/
斜线命令端点和交互性(按键)端点,两个都锁定
由Slack的 HMAC-SHA256 请求签名加上5分钟重播窗口。
破坏性补救只有在黑卡批准后才能进行。

<a id="layout"></a>

## Layout

```text
ts/
  package.json
  tsconfig.json
  src/
    index.ts          # entrypoint, demo + HTTP server
    server.ts         # hono app, /slack/command + /slack/interactivity
    slack_verify.ts   # HMAC v0 verification + timing-safe compare
    agent.ts          # mocked hypothesis ranker
    blocks.ts         # Block Kit response builder
    types.ts          # Hypothesis, AgentReport, SlackResponse, OutboundCall
  tests/
    slack_verify.test.ts
    agent.test.ts
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

Set `SLACK_SIGNING_SECRET=...` 以推翻占位符的秘密。
交互式服务器打印所选端口( 当 `PORT` 尚未设定)

<a id="tests"></a>

## Tests

`node --test` 通过 tsx 运行。 覆盖 :

- 空白签名验证: 有效签名通行证, 篡改签名是
  拒绝, 拒绝淡化的时间戳 (> 5 分钟 skew) , 非数字的时间戳是
  拒绝, 在恒定时间比较前会运行长相匹配路径 。
- Mock agent: OOM 关键字路径, CrashLoop 关键字路径, 后退路径 。
- Server: `/health`, `/slack/command` 快乐/铺设/铺设路径,
  `/slack/interactivity` 批准行动。
