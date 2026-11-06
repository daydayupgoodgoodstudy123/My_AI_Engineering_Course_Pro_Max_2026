<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---verification-gates"></a>

# 任务 - Verification Gates

<a id="goal"></a>

## 目标
Implement `verify(task_id, artifacts)` 纯粹的确定功能, 相对于范围报告、 规则报告、 反馈日志和 diff , 释放一个 `verification_report.json` 任务结束

<a id="inputs"></a>

## 输入
- 固定装载器 `scope_report.json`, `rule_report.json`, `feedback_record.jsonl`,以及 diff
- 检查表:接受运行,接受退出零,范围干净,无 `null` 退出, 所有块数规则都通过

<a id="deliverables"></a>

## Deliverables
- 纯净的 `verify(task_id, artifacts) -> VerdictReport`
- 显示每次检查结果和最后出入/失败的打印机
- 三个演示情景写入磁盘: 干净的通行证、 范围爬行、 缺少接受

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 清洁通道情况报告 `passed: true`;另外两份报告 `passed: false`
- 每种情况都分别写 `verification_report.json` under `outputs/verification/`

<a id="out-of-scope"></a>

## 超出范围
- LLM门是决定性的,质量判断属于39课的评审者
- 签署过重 audit logs. 演习 prompts 向那边开

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-verification-gate.md` - 技术
