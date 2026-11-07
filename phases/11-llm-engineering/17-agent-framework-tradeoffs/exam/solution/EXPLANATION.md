# 参考实现说明

本地服务实现正文Exercise3：Problem→固定课程推荐→一句理由与实际求值证据。没有当前产品能力调查、真实SDK或LLM。

## Part 1

normalized_problem正确完成严格类型与默认值；decode_problem必须完整按字段投影，不能读另一个调用次数字段。prepare_cases按输入序保留每个case_id，label只是展示文字，fixture recommender接收完整Problem。正确feature_card/call_count拒绝生产者传来的None，错误在producer外两次调用暴露。format_case_table在完整prepared batch求公共字符宽度，并输出全部case/label/framework/reason/calls，不运行selector。

## Part 2

INI section保持case输入序，label用给定JSON-string codec保留任意文字，全部七个flags显式yes/no，读取getboolean/default；非负整数调用次数以整数精确保留，包含超过浮点精确表示范围的合法值。完整Decision codec实际给定，无数值lexeme转换职责。load依据case_id找对应证据，不能按两个文件的顺序zip；exact keys核对拒绝缺失/多余绑定。两文件只保证completed single-writer save，不承诺crash事务。

## Part 3

hard先于所有soft shapes；tiny要求<=2且七flags都false。dialogue与roles保留typed exclusion并按声明顺序；session在typed之前且排除roles/dialogue，fallback仍是独立rule。每一步记录全部operands及结果，first match返回，因此trace只有真实prefix。requirements保留全部true flags，finish_decision只按实际选择rule和最后evidence生成固定理由，没有隐藏predicate实现。

## Part 4

完整codec给出当前Decision。render_card用JSON string隔离heading的任意label，再按Case/Framework/Rule/Requirements/Reason/Evaluated的声明顺序组成卡片，Case使用稳定case_id。所有字段来自当前事件，false evidence保持完整。Given async driver实际逐事件调用render_card并关闭源；候选不重新实现generic collect-all/owner/cancel机制。格式是本地Markdown报告，不称框架wire。

## Part 5

structure_trace只收到Decision，沿给定RuleNode chain递归对照rule_id；guard path附rule，edge附true/false。false node保留完整operand evidence并沿otherwise；true node验证最后evaluation、decisive rule和framework后生成leaf。未走分支不产生节点，gap/没有true match/额外evaluation拒绝。没有Problem输入、反事实或另一份selector。

## 来源与教学边界

docs80–101 checklist/matrix、111Exercise3与main22–98 Problem/recommend是P3核心来源；main103–107固定60列报告、110–153有序表驱动case、158–174输入投影支持P1。正文/讲解指出source tiny漏typed/session，本题明确补齐七信号；source session-before-typed顺序被保留。每个框架是课程profile，不把原文年代或优势当当前事实核验。

INI/evidence persistence、Markdown artifact和嵌套observed path是围绕该真实selector的显式本地工程扩展；source没有这些存储/流协议。固定60→全batch动态字符宽度也明确是报告扩展。P1 prepared-table计时不含JSON intake/模型生成/推荐规则，只覆盖公开format_case_table完整输入到全部输出消费，不能宣称完整应用延迟。与07已拟合index.avg_dl忽略不同：此处没有预存layout，需在单次报告构建计算布局；此具体近邻仍留全章实际审查，不声称全面去重通过。coderpad短route_task/evidence_gate排除。

完整6000个prepared rows的公开format_case_table在timer内计算layout、格式化全部行并比较完整输出；限值.08s，连续3slow为1.477245/1.490894/1.585907s，3fast为.001917/.004801/.008241s，双余量18.466/9.707，最慢1.586s。输入准备、JSON解析、selector与真实provider不在此报告API计时范围；不作完整应用延迟或真人时间声明。

INI给定parser使用不在合法case_id语法中的`@defaults`作为特殊配置区名称，`DEFAULT`、`default`、`Default`均是彼此独立的普通合法场景ID；候选仍按完整case_id保存和关联证据。

## 这套题证明了什么，没证明什么

本地断言证明字段/身份/报告、INI重开、明确课程规则、Markdown证据卡与实际trace路径符合给定合同；性能证据仅支持该输入上的完整prepared-report CPU响应。它不证明当前框架能力、生产选型最优、真实API成本/延迟、双文件crash事务或真人面试时间。
