<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="lesson-16---github-issue-to-pr-agent-typescript-webhook-receiver"></a>

# 课程16 GitHub Issue-to-PR Agent (TypeScript 网络锁定接收器)

TypeScript 半块墓碑 Python 侧船 agent loop 和
dispatcher; YAML 侧端船舶“动作”工作流程。 此工程为 GitHub
App Webhook 接收器: HMAC 验证原始体、事件类型上的路径、 调度
一根根根 agent 用于 `issues.opened`.

<a id="layout"></a>

## Layout

```text
src/
  index.ts    entry: demo (default) or HTTP server (--serve)
  server.ts   Hono webhook receiver (POST /webhook)
  verify.ts   X-Hub-Signature-256 HMAC, timing-safe
  router.ts   event-type routing (ping, issues, pull_request)
  agent.ts    stub agent + audit log
  types.ts    payload + audit shapes
tests/
  verify.test.ts  signature pass, tampered, router pathing
```

<a id="run"></a>

## Run

```bash
npm install
npm run typecheck
npm test
npm start            # self-terminating demo (in-process replays)
npm run serve        # HTTP server on :8081
```

读取HMAC的秘密 `GH_WEBHOOK_SECRET` (默认 `demo-shared-secret`
),请见此。
