# 参考答案讲解：EvidPlan（14/44）

计时结束后再看。同目录 `evidplan/` 为参考实现，`python3 -m pytest --solution --all-parts` 应显示 5 passed。

## Part 1 校验

plan_document 必须在 issues 非空时直接给 blocked 文档与空 waves。起始实现仍调度无效计划，导致内部 execution_waves 抛未知依赖异常，违背外层返回文档的契约。

不能把拓扑排序剩余项都说成环：等待环的下游任务没有通向自己的路径。起始 cycle_members 对每个顶点各做一次可达性搜索，小图答案正确，但长阻塞尾链反复走同一批祖先。给定 `_components` 已一次算好强连通分量；多顶点分量全部在环上，单顶点分量只在有自边时入选，最终对全部成员排序。必须保留所有不相交环和自环，不能只选每个分量的代表。校验时先报告未知引用，再在去除未知边后的已知子图查环，两类问题互不遮蔽。resolver 是人工输入，机械上只要求在不可逆项的前置祖先集合里。

波次使用依赖集合与 followers 索引，只在前置项完成时更新对应下游。ready 保留整波边界，再生成下一波，不能在同一波里顺着链跑完。集合处理重复依赖，循环仍严格报错。

## Part 2 存储

plan.json 是覆盖保存的 JSON 真源，progress.jsonl 是追加的回执流。asdict 与标准库 json 处理换行和 Unicode；重开计划时显式恢复三个 tuple 字段，日志按 UTF-8 文件物理行恢复 Event，保留所有重复与顺序；摘要中的 U+2028/U+0085 是合法字符串内容，不作为额外记录分隔符。

## Part 3 恢复

latest_records helper 已正确扫描最近的 proof、done、artifact_changed，并保留第一次 approved 授予，重复批准不会撤销先前权限。核心是让每项证明晚于自己和全部前置祖先最后一次产物变化：这样旧下游证明不会因为上游重新通过而自动复活。

按拓扑波次确定 complete；本项 proof 有效也必须等前置项 complete。不可逆项还要有早于 done 的 approval。未完成项按 dependencies、approval、fresh proof 的优先级说明原因，能安全继续的加入 ready，排序后第一个就是 next。

这套规则不执行命令，只判断给定回执支持的完成状态。

## Part 4 视图

用已有事件初始化 previous，不发历史快照；每收到一个新 Event，重算受控规模下的状态，用给定 `_changes` 比较完整内容，把它返回的行按 id 输出完，再读下一事件。去重 helper 已给对；候选人负责历史接续、行顺序和事件屏障。异步生成器的自然暂停保证不会预读后续输入。

这里的在线部分是来自并发 worker 的交错回执，不负责调度真实 agent，也不在 Markdown 中存状态。

## Part 5 拆分

先为每项建立替代 id 表，再复制每个 proof 的 WorkItem，并通过同一张表重写 depends_on 与 resolvers。所有原前置项都保留，两个 proof 子项互不新增串行依赖。提前检测生成 id 碰撞。

不可逆检查使用前置祖先集合。release 依赖 resolver 和 docs 两项时，两项都要完成；不要求 resolver 支配每条从根出发的图路径。

## 这套题证明了什么，没证明什么

通过说明能在这个离线规模下验证计划、保存回执、恢复证明有效性、渲染在线视图和拆分依赖。它不判断真实证据是否可信，不替代风险与审批判断，不执行真实 agent 或命令，也没有证明跨进程日志事务、断电恢复或真实并发执行可靠性。
