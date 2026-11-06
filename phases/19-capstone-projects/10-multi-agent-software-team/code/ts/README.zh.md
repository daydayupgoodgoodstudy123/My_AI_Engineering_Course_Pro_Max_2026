<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="multi-agent-software-team-typescript-skeleton"></a>

# Multi-agent 软件组TypeScript skeleton)

Multi-file TypeScript 多重的骨架...agent 软件团队的综合项目。
计划员, 代码员, reviewer agents 共享工作空间并旋转
协调员。 worktree 通过 ExecFile 启动 儿童程序
拒绝名单和拒绝Shell金属。

<a id="layout"></a>

## Layout

- `src/index.ts` - 演示员
- `src/agent.ts` 基准 `Agent` 类加 `PlannerAgent`, `CoderAgent`, `ReviewerAgent`.
- `src/coordinator.ts` - 圆环和旋转跟踪。
- `src/workspace.ts` 共享存储文件系统和信息日志。
- `src/runtime.ts` — `child_process.execFile` worktree 带有否定名单的根根
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
npm start
```

<a id="verify"></a>

## Verify

```bash
npm run typecheck
npm test
```

<a id="spec-references"></a>

## 标注引用

- 来源课程 : `phases/19-capstone-projects/10-multi-agent-software-team/docs/en.md`
- [MetaGPT](https://github.com/FoundationAgents/MetaGPT) 以角色为基础的多功能agent framework.
