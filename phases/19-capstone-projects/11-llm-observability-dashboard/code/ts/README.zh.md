<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="llm-observability-dashboard-typescript-skeleton"></a>

# LLM observability 仪表板(TypeScript skeleton)

Multi-file TypeScript 骨骼为 LLM observability 仪表板的顶石。
一个 Hono 服务器接受 OpenTelephysical GenAI 的宽度, 将其放在10k 环内
缓冲剂,并产生P50/p95/p99的延迟和每模型费用。

<a id="layout"></a>

## Layout

- `src/index.ts` 切入点、种子合成宽度和可选服务 HTTP.
- `src/server.ts` - 胡诺路 `/trace`, `/`, `/dashboard`, `/dashboard.json`, `/healthz`.
- `src/spans.ts` — `RingBuffer` 和 `ObservabilityStore` (默认为10k 平方英尺)
- `src/rollup.ts` — `percentile` 和 `rollUpByModel`.
- `src/pricing.ts` - 2026年每套价格和成本帮助。
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
npm start         # seeds 1200 synthetic spans and prints the rollup
npm run serve     # also serves the HTTP ingest + dashboard on PORT (default 8011)
```

<a id="verify"></a>

## Verify

```bash
npm run typecheck
npm test
```

<a id="spec-references"></a>

## 标注引用

- 来源课程 : `phases/19-capstone-projects/11-llm-observability-dashboard/docs/en.md`
- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
