# 参考实现讲解

## Part 1：边界必须能够执行

decision_issues 的 bounded 检查应检查 typed boundary，而不是再检查 rationale。否则 compiler 根据没有 issues 的前提调用 compile_boundary，None.kind 在另一个函数才报错。正确 helper 接受 limit 或 allowed 白名单；有数值并非 bounded 的必要条件。

例子必须有 normal/edge/failure/forbidden 四类且文本非空，这是本题更严格的合同。原课的一个 normal 示例在原测试中可通过，不能把本题规则冒充原源码行为。locked 路由保留 id、question、rationale，重复 question 仍独立。编译 catalog 直接 enumerate 并生成不可变 occurrence ordinal/value 对，保留重复和顺序；不用 list 前端反复 pop 搬移。120000 条计时限值 0.08 秒。

## Part 2：理由随历史保留

追加前确认编号恰好是下一 revision，给定 JSONL helper 按物理文件行读取，正确保留多行文字以及字符串内 U+2028/U+0085；它们不会被当作记录分隔符。at 先选 physical prefix，再按事件折叠 id 到 Decision 的有序映射。added 建立初始顺序；后续仅修改目标字段。None 理由不写入 changes，而显式空字符串要写入，才能表达有意开放 delegated 选择。Boundary 恢复 tuple 与原单位；显式 None boundary 清除当前边界，旧 revision 仍保留。重复编号与跳号均在写入前拒绝，历史不得被 canonical 编译覆盖。

## Part 3：匹配而非排等级

MATCH 给每种 claim 唯一 receipt kind。按 required_receipts 顺序检查存在、passed、kind、claim binding、authority scope，每份只报第一个错误。仅有效 receipts 合并 case coverage；若未覆盖整个声明集合，再附 cases。另有好 receipt 不能抹去一个无效 required receipt 的原因。对 authority scope 比较精确集合，额外权限也不合格，原数据顺序不改。验证只涵盖声明的有限案例，不证明现实的全称安全。

## Part 4：动作前的门

先识别 locked，输出 checkpoint 后 return，不运行 fake；这样同时到期的预算不会夺走人工检查点。非 locked 读取给定 cumulative measurement，按声明顺序检查所有 bounded limit，包括 retry count：到阈值就阻止下一动作。当前 bounded allowlist 也要核对依赖或接口选择。一个或多个原因合成一条 stop 后 return；无原因时 apply 恰好一次再 yield continue。终止或消费者关闭后不拉取未来 attempt。

这里没有真正发起搜索或写入。completed counts/elapsed 由上游注入，私有 NDJSON 没有 jsonrpc/method，不声明任何外部协议保证。

## Part 5：完整的阻塞路径

叶子许可和单位换算由给定 helper 实现。递归返回 permission 与 blocker occurrence paths：ALL 要所有子树通过，ANY 有一项通过就许可并隐藏失败兄弟；整体失败时按 DFS 合并实际失败子树的 paths。根叶的路径是空 tuple，同一 metric 在不同位置不能去重。没有解析英文预算或构建自然语言编译器。

## 这套题证明了什么，没证明什么

通过原样五关说明能在受控输入上校验规格、保留决策理由/修订、匹配有限证明、在 fake effect 前执行授权边界并解释 AST blocker。它不证明规格正确代表用户风险、有限案例覆盖所有现实状态、生产工具获得真实授权，也没有验证真实 LLM、网络、RPC 或框架集成。
