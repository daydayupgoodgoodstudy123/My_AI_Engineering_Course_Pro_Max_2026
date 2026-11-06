<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---multi-session-handoff"></a>

# 任务-多次会议 Handoff

<a id="goal"></a>

## 目标
生成 `handoff.md` 和 `handoff.json` 工作台的工艺品,所以在会话结尾处, 下个会话在第一分钟内是有效的。 两种形式都包含相同的七个字段; 和 JSON 分歧胜出

<a id="inputs"></a>

## 输入
- `agent_state.json`, `verification_report.json`, `review_report.json`, `feedback_record.jsonl` 校对:Soup
- 七个字段:摘要,已更改_文件, 命令_运行, 失败_尝试, 打开_风险, 下一个_行动,判决_pointer

<a id="deliverables"></a>

## Deliverables
- 一个 `WorkbenchSnapshot` 装四件艺术品的货机
- `generate_handoff(snapshot) -> (markdown, payload)`
- 选择最后 K 记录的反馈过滤器, 加上每个非零退出
- `handoff.md` 和 `handoff.json` 写入脚本旁边

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 两种文件都包含全部七个字段和一个非空白字段 `next_action`
- 使用相同的输入重新运行脚本, 产生相同的包

<a id="out-of-scope"></a>

## 超出范围
- 压缩战略(《油污损害民事责任公约》的尾点, Claude 代码5阶段)。 Handoff 关闭会话;压缩延展一次。
- 做个假的 markdown 以公关形式重新使用,但课程停止在文件上。

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-handoff-generator.md` - 技术
