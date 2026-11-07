# 面试官手册

场景：把结构化agent问题映射到固定课程profile，并保留可审阅的完整决策证据。开场2分钟；五关12/10/16/10/10分钟，共60分钟。记录提示等级，无真人用时校准，不需要SDK或联网。

## 澄清问题的标准答案

- Are these live framework recommendations? “No. Use the fixed course profiles and the stated rule order; do not call external services.”
- Can two scenarios share a label? “Yes. case_id is unique identity; label is presentation text and may contain any Unicode text.”
- How do typed state and session memory interact? “Without roles or dialogue, the declared session rule precedes typed state and chooses the course Agno profile.”
- What must the trace contain? “Only the evaluated prefix through its first match, with every named operand including false values.”
- Does the INI store promise crash atomicity? “No. It promises a complete single-writer save and reopen with exact scenario-to-evidence binding.”
- What is timed? “The complete prepared-batch comparison-table API, including layout and all output consumption, not model calls or selector execution.”

## Part 1：intake与完整报告

主要坑：decoder读错调用次数字段；按display label去重丢独立case；每行重算全batch布局。首错来自decode_problem生产None，prepare_cases→正确feature_card→正确call_count在两次调用外抛ValueError；不要改正确consumer或跳过字段。框架规则全部留P3，P1只使用注入Recommendation fixture。

H1：对比原JSON与consumer实际收到的Problem。H2：区分case_id与可重复label。H3：按normalized字段投影、保持ordered rows，再一次求公共width用于全部格式化行。追问：为什么typed+session的推荐不能在这里给定？空batch、长label和零调用会怎样？

## Part 2：场景catalog与证据归属

主要坑：INI的false文字被bool当true；按section名称排序改变场景顺序；把evidence file顺序当case_id关联。candidate保存所有Problem字段，包括会话记忆与精确非负整数调用次数；load使用明确INIboolean grammar/default，证据按稳定身份完整绑定。no-interpolation和文字/Decision codec实际给定，百分号/多行是integration guard，非新的候选格式算法。

H1：重开后比较每个Scenario与对应Decision。H2：试同label不同ID与倒序evidence。H3：INI section输入序恢复；getboolean/getint按声明defaults；用case_id查完整evidence，核对bijection。追问：两个文件的完成save与crash原子性有何区别？

## Part 3：真正的课程selector

主要坑：tiny漏typed/session；hard被soft shape截走；dialogue/roles丢typed exclusion；同框架就复用错误reason或捏造更低优先级evaluation。固定课程顺序不是对现实产品的绝对判断。核心是选择与证据同源：每个被求值rule保存所有命名operands，false也保留；首match停止。

H1：先读固定顺序和冲突case。H2：将predicate结果、operand evidence和stop点一起记录。H3：hard/tiny/两shape guards/session/typed/fallback逐条求值，requirements为全部true flags，finish_decision按实际rule/最后evidence格式化。追问：typed+memory为什么Agno？hard+roles为何只求值hard？

## Part 4：Markdown证据卡

主要坑：多行label制造额外heading；Requirements遗漏；用framework替代实际reason/evaluated operands。candidate负责完整heading和按声明顺序排列的六条领域证据，Case保留稳定case_id；真实current-case/pull-through/close由Given driver负责。每个JSON值可保留Unicode、换行与百分号；没有手拼CSV或长度帧职责。

H1：解析为一个heading和六字段。H2：把label/reason当任意文字。H3：heading的label写JSON string；按固定字段序投影同一Decision完整codec值。追问：为何卡片rule和framework都要保存？false evaluation有什么审查价值？

## Part 5：实际已观察路径

主要坑：省掉false guard及其evidence；path漏false边；把相同framework的不同decisive rule混成一个leaf。沿给定有限RuleNode链对照trace；只挂实际走过的边，不执行任何Problem predicate。缺口/多余步骤/decisive不符必须拒绝。

H1：画一条真实observed prefix。H2：区分guard node与edge path segment。H3：递归消费一个RuleEvaluation；false沿otherwise，true核最后一步和rule/framework后建leaf。追问：为什么这不是第二次选型？同为LangGraph的hard/typed/fallback该如何区别？

## 评分表

| Part | 分值 | 行为标准 |
|---|---:|---|
| 1 | 25 | 完整投影8；身份/顺序7；完整响应报告10 |
| 2 | 15 | flags/defaults5；顺序/完整字段5；证据归属5 |
| 3 | 30 | 规则优先级12；冲突边界8；真实trace/理由10 |
| 4 | 15 | heading隔离5；requirements/reason/evaluated完整7；driver集成3 |
| 5 | 15 | false路径/evidence6；decisive leaf5；拒绝不一致4 |

85–100独立完成并解释；70–84主行为正确且少量提示；50–69部分正确但证据或边界不完整；低于50不能保持场景与推荐证据。所有assert保留，提示与未完成项写复盘。实测与来源边界见SCOPE。

完整6000个prepared rows的公开format_case_table在timer内计算layout、格式化全部行并比较完整输出；限值.08s，连续3slow为1.477245/1.490894/1.585907s，3fast为.001917/.004801/.008241s，双余量18.466/9.707，最慢1.586s。输入准备、JSON解析、selector与真实provider不在此报告API计时范围；不作完整应用延迟或真人时间声明。

INI给定parser使用不在合法case_id语法中的`@defaults`作为特殊配置区名称，`DEFAULT`、`default`、`Default`均是彼此独立的普通合法场景ID；候选仍按完整case_id保存和关联证据。
