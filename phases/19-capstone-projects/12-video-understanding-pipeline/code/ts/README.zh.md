<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="lesson-12---video-understanding-pipeline-typescript-ui"></a>

# 课程12 - 了解视频管道(TypeScript UI)

TypeScript 半块墓碑 Python 侧面 (P)`code/main.py`)拥有
多矢量指数和时间 grounding。该项目的仪表板
一半:在四个输油管阶段(chunk、嵌入、索引、qa)的Hono应用软件。

<a id="layout"></a>

## Layout

```text
src/
  index.ts     entry: demo (default) or HTTP server (--serve)
  server.ts    Hono routes (/, /jobs, /job/:id) + HTML index
  jobs.ts     JobStore + fixture seeder
  stages.ts    stage advance + overall status
  types.ts     Stage, StageState, Job
tests/
  stages.test.ts  job state transitions + store
```

<a id="run"></a>

## Run

```bash
npm install
npm run typecheck
npm test
npm start              # self-terminating demo
npm run serve          # HTTP server on :8123
```
