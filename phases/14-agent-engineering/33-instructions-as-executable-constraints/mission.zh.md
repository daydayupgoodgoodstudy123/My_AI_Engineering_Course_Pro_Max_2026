<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---agent-instructions-as-executable-constraints"></a>

# 任务 - Agent 指令作为可执行的限制

<a id="goal"></a>

## 目标
将报告转换成五类的机器检查规则 并发布规则报告 评审员可以得分

<a id="inputs"></a>

## 输入
- `docs/agent-rules.md` 每个头部有一个规则, 每个携带子弹, 类别,描述,和a `check` field
- 演示 agent 故意违反两条规则

<a id="deliverables"></a>

## Deliverables
- 装载的解析器 `agent-rules.md` 进入数据类
- `rule_checker.py` 样式函数, 1/ `check` referenced
- `rule_report.json` 符合规则的出入/失职情况及总体严重程度

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 输出打印解析规则集, 运行 trace,并按规则通过/失败
- `rule_report.json` 发现两次故意违反

<a id="out-of-scope"></a>

## 超出范围
- 将检查员和CI连线 课上的报告会写出来
- Framework guardrails (OpenAI SDK, LangGraph 规则是执行的人类可读合同。

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-rule-set-builder.md` - 技术
