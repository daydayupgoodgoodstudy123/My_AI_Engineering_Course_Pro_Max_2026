# 参考答案讲解：FlowMap（14/48）

计时后再看。参考实现位于 `flowmap/`，`python3 -m pytest --solution --all-parts` 应显示 5 passed。

## Part 1 证据审计

audit 的 status 排除了 artifact，原因在 audit → _grounded → supports。正文前两级都能直接支持当前行为，不能只认 recording。再把全流程判定从任一步有证据改成每步都有强证据；采访 confidence 为 1 仍是报告。

整数百分比用整数比率做 half-up，避免 Python round 的半偶舍入。显示每一步时只 asdict 那一步，不把整个列表重复构造。320 步慢版约 0.198–0.201 秒，参考 0.689–0.707 毫秒，限值 0.02 秒。

## Part 2 工作流快照

每个 workflow 一个完整 JSON payload 存进 SQLite，独立替换，不把 evidence 当无序集合。载入恢复 tuple[Evidence] 与 Step，所有原文、级别、confidence 和步骤顺序保留。空列表是存下的空观察，与不存在的 id 不同。

## Part 3 工作流风险

按显式字段列出四类 concerns，并由相邻 actor 变化标 handoff。handoff verified 要两侧有强证据；reported authority 不删，只标 verified=False。hidden-state 必须有明确 memory/chat/personal-notes 载体，不能用缺 artifact 替代事实。结果按本题的风险顺序与步骤排序。

## Part 4 录屏切步

只保留当前段。actor 变化或 gap 严格超过阈值，就发出旧段，再用边界事件开始新段。旧段 end 是最后一个已包含事件；idle gap 单独记为新段 wait_ms。收到边界即 yield，流尾补发最后一段，空流只发 header。CSV 序列化 helper 直接复用。

## Part 5 变体前缀树

逐观察沿规范 actor/action 路径累加 count，users/reasons 去重但保持首见次序。终点存 ends，即使此节点还有孩子；这样短流程和长流程都真实存在。缺失原因写 unknown，孩子按次数再按键排序；不生成平均流程或改写原观察。

## 这套题证明了什么，没证明什么

通过说明能把本课工作流与证据梯子做成确定审计，保存原始材料，区分已证实 concern 与待核实线索，在线分段并保留真实变体。它不解码真实录屏、不证明访谈或artifact真实、不授予生产权限，也不自动决定哪个用户变体应该成为产品策略。真实工作仍需补充材料、解释差异和验证authority。
