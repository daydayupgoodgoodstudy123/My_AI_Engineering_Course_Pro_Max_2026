<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="code-migration-agent-dashboard-typescript-skeleton"></a>

# 代码迁移 agent 仪表板(TypeScript skeleton)

Multi-file TypeScript 密码迁移仪表板层的骨架
agent 综合项目 agent (Python运行在 sandbox; 此服务器生成
操作员的进度 。

<a id="layout"></a>

## Layout

- `src/index.ts` 切入点、模拟勾和可选服务 HTTP.
- `src/server.ts` - 胡诺路 `/`, `/dashboard`, `/migrations`, `/migrations/:id`.
- `src/migrations.ts` - 每份国家机器和种子数据。
- `src/cost.ts` 转帐和美元预算执行。
- `src/types.ts` 共有类型。
- `tests/*.test.ts` — `node --test` 通过样式测试 `tsx`.

<a id="install"></a>

## 安装

```bash
npm install
```

<a id="run"></a>

## Run

```bash
npm start         # offline: simulate 40 ticks and print rollup
npm run serve     # serve the HTML dashboard on PORT (default 8009)
```

<a id="verify"></a>

## Verify

```bash
npm run typecheck
npm test
```

<a id="spec-references"></a>

## 标注引用

- 来源课程 : `phases/19-capstone-projects/09-code-migration-agent/docs/en.md`
- Recipes: [OpenRewrite](https://docs.openrewrite.org)来,来
