<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="lesson-17---personal-ai-tutor-typescript-web-app"></a>

# 17课 - 个人自学辅导员TypeScript 网页应用程序)

TypeScript 半块墓碑 Python 边船 学习者模型和
辅导政策; 此项目揭示了网络应用表面: 课程 DAG
步态器, BKT 式学习模型, 和 FRS- 精度的重复
排程器落后于 2 HTTP routes.

<a id="layout"></a>

## Layout

```text
src/
  index.ts       entry: demo (default) or HTTP server (--serve)
  server.ts      Hono routes (GET /lesson/next, POST /lesson/:id/submit)
  curriculum.ts  DAG fixture + Kahn topo sort + next-lesson picker
  mastery.ts     MasteryStore (per-lesson BKT-ish update)
  repetition.ts  scheduleNextDue (interval doubling / halving, clamped)
  types.ts       Lesson, Mastery, Pick
tests/
  curriculum.test.ts  topo order, BKT update, FSRS scheduling
```

<a id="run"></a>

## Run

```bash
npm install
npm run typecheck
npm test
npm start            # self-terminating curriculum walk
npm run serve        # HTTP server on :8090
```
