<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-1902--rag-over-codebase-typescript"></a>

# 墓碑19/02 - RAG 超过代码基数 (% 1)TypeScript)

Multi-file TypeScript code-search API 用于 hybrid retrieval pipeline
说明 `../docs/en.md`。 离线、确定性、六整层样本,
node:http 后面的霍诺接货员。

<a id="layout"></a>

## Layout

```text
src/
  index.ts        entry point; boots node:http + self-probe + exits 0
  server.ts       hono routes (/healthz, /query) with zod-validated POST body
  retrieval.ts    runQuery + RRF merge over dense and BM25
  index_store.ts  FNV-1a hash embedder, cosine, field-weighted BM25
  corpus.ts       six-chunk sample (uploader / auth / client / catalog)
  types.ts        Chunk, RankedChunk, QueryResponse, anchor()
tests/
  index_store.test.ts
  retrieval.test.ts
  server.test.ts
```

<a id="run"></a>

## Run

```bash
npm install
npm start                # boots api, probes three queries, exits 0
npm start -- --serve     # keep server up; ctrl-c to stop
npm test                 # node --test runner via tsx
npm run typecheck        # tsc --noEmit
```

非互动 `npm start` 路径中称 `/healthz` 返回 200和
每个查询都至少返回一个引用。 路径 :

- `GET /healthz` — 返回 `{ok, corpus}`.
- `GET /query?q=...` - 运行混合查询。
- `POST /query` — JSON `{q, topK?}`,由Zod(SO)验证`topK` 上限为50)。
