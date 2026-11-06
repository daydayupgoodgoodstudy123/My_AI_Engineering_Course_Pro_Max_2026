<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-04---multimodal-document-qa-typescript"></a>

# 综合项目 04 - 多式文件质量A(TypeScript)

返回页面图像 URL 附加 a 的查看器骨架 JSON 引用的约束列表
框中选择的文档。 HTML 将一个小布局覆盖脚本内嵌响应
显示页面图像上方引用的区域。 Python
管道投入 `../main.py`.

<a id="layout"></a>

## Layout

```text
ts/
  package.json
  tsconfig.json
  src/
    index.ts        # entrypoint, demo + HTTP server
    server.ts       # hono app, /health, /, /document/:id
    fixtures.ts     # 10-K table + Nature figure fixtures
    render.ts       # HTML index + per-document overlay renderer
    types.ts        # DocumentFixture, EvidenceRegion, BoundingBox
  tests/
    fixtures.test.ts
    render.test.ts
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

交互式服务器在 `PORT` 显示未设置并打印
在 stdout 上选择的 URL。 访问 `/` 用于索引, `/document/10k-acme-2025` 用于
演示重叠, 或设置 `accept: application/json` 来得到结构化的反应。

<a id="tests"></a>

## Tests

`node --test` 通过 tsx 运行。 测试覆盖固定检查( 正+负) ,
HTML 五个敌对人物逃跑,文档 HTML 有效载荷结构,
以及Honno路线(200, 404,内容谈判)。
