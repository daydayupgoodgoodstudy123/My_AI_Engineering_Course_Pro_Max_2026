<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-1901--terminal-native-coding-agent-typescript"></a>

# 顶楼19/01-终端 Coding Agent (TypeScript)

Multi-file TypeScript harness 用于以下描述的计划/行动/观察环
`../docs/en.md`关闭,确定,网络电话零

<a id="layout"></a>

## Layout

```text
src/
  index.ts     entry point; runs a scripted demo and the eval, then exits 0
  repl.ts      interactive command parser (run / eval / help / quit)
  harness.ts   the plan-act-observe loop, wired through the hook bus
  hooks.ts     eight-event hook bus plus a destructive-command guard
  model.ts     scripted offline LLM that drives the demo
  tools.ts     read_file + run_shell with zod-validated args
  plan.ts     PlanState (todo rewrite) + Budget (turn / token / dollar ceilings)
  eval.ts      tiny pass/fail counter across three offline tasks
  types.ts     shared shape definitions
tests/
  harness.test.ts
  tools.test.ts
```

<a id="run"></a>

## Run

```bash
npm install
npm start                # runs the scripted demo + offline eval, exits 0
npm start -- --repl      # opens the interactive harness REPL
npm test                 # node --test runner via tsx
npm run typecheck        # tsc --noEmit
```

非互动 `npm start` 路径称,评估报告 `passed=3
failed=0` 脚本运行会与全完成的计划相融合。
失败了
