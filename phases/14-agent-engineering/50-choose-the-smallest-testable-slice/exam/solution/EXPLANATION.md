# 参考实现讲解

## Part 1：先资格，后取舍

正 effort 前提属于 score；起始版本允许零，在同一 score 函数的分母运算抛 ZeroDivisionError。将正值检查修正确保在计算前报告 ValueError。可逆 consequence 系数是 0.5，不可逆是 2；错误系数在 score 产生错误分数，上一层 choose 消费该分数并选错候选 id，构成跨层表现。这沿用本课的简单示例，不是跨场景价值模型。

Candidate.id 是决定身份，Slice 是内容。选中 b 后与它内容相等的 a 仍应留在 alternatives。覆盖比较对 offered 只建一次 set，避免 required 每项扫描长 tuple；报告仍用原 proof 元组。13000 项限值 0.03 秒。非空 proof 与严格数值类型 helper 起始即正确。

## Part 2：保存当时的决定

JSON 保存完整 Snapshot，恢复 Candidate/Slice/StopRule 与元组。selected_score 是当时记录，保留 float 精确值和负零，不重新算。selected_id 必须在候选 id 中，校验在 atomic_json 前，错误不覆盖旧快照。给定原子替换 helper 仅承诺单 writer 文件替换，不承诺多 writer 协调。

## Part 3：小到仍能改变决定

按固定 ORDER 加入所有适用原因：缺 proof、相对真实数据的 UI-only、用户价值、异常、可重复测量、平台先行及停止规则。一个 UI mock 可以服务 comprehension-only 目标，因此不能全局按形式判失败。只有无原因设计进入 choose，缺 proof 的非法低 effort 候选也不该先被打分。

有效停止规则需要三种结果都有非空行动，至少一个行动不是规范化后的 keep building；可用源课中的 change user、test mechanism、collect evidence、narrow authority，也允许其他明确指令。它不解释自由文本的业务效果。

## Part 4：控制 pilot 的边界

计数每次观察，正确结果将连续 errors 清零。每次先 yield measurement，达门槛再 yield failed decision，然后 return。EOF 有观察时发 passed，无观察时发 ambiguous。当前 measurement/decision 交给消费者后才继续，关闭生成器不请求下一份输入。SSE 编码已经给对，候选人实现的是行为而非转义细节。

## Part 5：补全证据链

给定 DAG 校验后，每节点求到任意 outcome 的最优后缀，代价为未建节点数。比较 `(missing_count, full_path_tuple)`，端点同样计入；outcome 是终止状态。共享后缀可缓存，built 中无关节点不影响结果。最终 missing 依路径顺序列出，不把不同分支的现成节点拼成假想 workflow。

## 这套题证明了什么，没证明什么

通过原样五关说明能在受控本地输入上修正 proof-first 切片选择、精确保存决策、处理 false minimums、在线执行 guardrail 与寻找连通补全路径。它不证明候选 proof 真有用户价值、评分权重有效、pilot 成功、生产部署安全，也没有运行真实模型、网络或产品实验。
