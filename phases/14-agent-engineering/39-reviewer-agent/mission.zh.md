<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---reviewer-agent-separate-builder-from-marker"></a>

# 任务 - Reviewer Agent: 从标记中分离构建器

<a id="goal"></a>

## 目标
建立一个审查循环,读取建筑商的文物只读并发布 `review_report.json` 得分超过五个维度,总共10个, 并有通过判断,软_失败或困难_fail.

<a id="inputs"></a>

## 输入
- `ReviewerInputs` 汇总以往经验教训的diff、状态、反馈和核实裁定
- 理表尺寸:问题是否合适,范围纪律,假设,核查质量, handoff readiness

<a id="deliverables"></a>

## Deliverables
- 每个维度一个评分函数( 课的评分, 确定性)
- `review_report.json` 作家,五分,总分,和判决
- 两个演示案例: 干净的改变和“正确的测试,错误的问题”的改变

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 整齐换班至少得7分 `pass`
- 问题的变化至少在一个维度上降到5以下,判决也翻转到 `hard_fail`

<a id="out-of-scope"></a>

## 超出范围
- Real LLM 课分根每个维度, 技能交换后在模型中进行。
- 编辑 diff 。 评审者读取, 评分和报告 。 Patches 下次轮到建筑工了

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-reviewer-agent.md` - 技术
