# 参考答案讲解：MetricPlan（14/52）

计时后再看。参考代码在 metricplan/，`python3 -m pytest --solution --all-parts` 应显示5 passed。

## Part 1 指标合同与源快照

population与source/window相互独立，validate必须交给完整metric_issues检查。合法counter也要报告；原课本来没有过滤它，这是本题移植时种下的缺陷。给定finite和duplicate_names继续处理非法数和身份。

reader的bytearray并未反复复制前缀，慢在每字节一次无缓冲read。文件是有上限的稳定本地快照，可以一次读完或合理分块再UTF-8/JSON解码。1,098,957 bytes（约1.05MiB）慢0.381–0.394秒，参考1.009–1.224毫秒，限值0.04秒。源材料所有字段完整保留，不能只读values丢掉receipt。

## Part 2 原始回放

SQLite每id一个完整快照，同时索引population和给定UTC instant。原timestamp、incident文本、整数毫秒和bool都存原样；get恢复Replay。recent选择真实时间最新N，返回选中子集的时间升序；同id更新索引，不把excluded证据删掉。

## Part 3 先定决定，再看结果

先用正确helper确认合同没改，再选择合格固定批次。所有pilot材料的write都计入安全约束；无write但未满批次只能ambiguous。满批比较rate与偶数median，fail先于pass，counter恶化只能降pass，不能抹去fail。毫秒只转一次秒，不用round改变边界。

## Part 4 固定批次在线报告

先检查当前记录的writes再加入批次，违规立刻Bail out并return。达到合格批次大小时，三行helper输出全部yield后才继续读，随后清空批次。EOF有真正的partial batch才发ambiguous；空批不发。消费方关闭后不会再读下一份证据。

## Part 5 GQM树与共享指标

逐目标的本地问题、再子目标遍历，metric引用都查catalog和states；seen只用于根层孤儿/角色覆盖，不跳过另一个问题。每问题/目标取最差状态，未测/坏链接为ambiguous，fail仍高于结构性不完整。outcome+guardrail覆盖在整个根计划，风险问题可以只接guardrail。

## 这套题证明了什么，没证明什么

通过说明能保留可复现指标合同和原始材料，按预定有限规则作复合决定，在线阻断已观察到的pilot违规并追溯指标。它不证明指标有因果解释、样本代表真实用户、真实source未被篡改或生产系统永远安全；这些仍需证据设计、校准和人类判断。
