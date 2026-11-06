<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---scope-contracts-and-task-boundaries"></a>

# 任务 - Scope Contracts 任务边界

<a id="goal"></a>

## 目标
撰写每个任务 `scope_contract.json` 和一个对比 agent禁止或禁止使用任何外表。

<a id="inputs"></a>

## 输入
- 任务描述,有允许的球, 禁止的球, 接受命令, rollback 第5款,需经核准
- 两个演示运行: 一个留在范围,一个爬行

<a id="deliverables"></a>

## Deliverables
- `scope_contract.json` 系统验证器(子集) JSON 阵列阵列)
- 生成 `RunSummary` 从被触动的文件加命令运行
- `scope_check(contract, run) -> (violations, in_scope, off_scope)`
- `scope_report.json` 保存在脚本旁边

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 检查范围报告无违反情况
- 爬行记录了准确的离镜文件 以及每个文件的原因

<a id="out-of-scope"></a>

## 超出范围
- 时间预算、 网络反向允许列表。 课程容器文件格; 练习 prompts 继续
- 启动中断,报告课结束

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-scope-contract.md` - 技术
