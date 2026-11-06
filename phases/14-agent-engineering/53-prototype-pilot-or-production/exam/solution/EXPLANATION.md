# 参考答案讲解：StageGate（14/53）

计时后再看。参考在stagegate/，`python3 -m pytest --solution --all-parts`应5 passed。

## Part 1 声明、控制与活跃遥测

完整pilot control表来自正文。_missing只返回尚未具备的控制，按原清单次序；_effective_stage保留明确声明，推荐单独显示。production在readiness下降时仍承担原责任，不能重贴pilot标签掩盖缺口。

active-session遥测按system维护session→user和user活跃引用计数。重绑先减旧user，join再加新user，最后引用离开才删user。14000session慢0.964–1.005秒，快4.241–4.736毫秒，限值0.08秒。它只表示当下活跃，不能替代累计admitted/exposed pilot audience。

## Part 2 原声明快照

SQLite每id一个完整JSON。用给定decode恢复tuple和Marker，保存原日期、authority与退出策略文本，不用marker推导stage。同id替换不影响另一个id；每次读取重建独立对象。

## Part 3 观察边界

按固定次序列出所有当前问题。pilot合法用production data，但累计受众不能超cap、日期不能过until；prototype的数据/权限暴露和无主责任分别列出。production缺on-call不会改变声明，只产生缺口。四处标记都检查，控制清单以原声明为准。

## Part 4 当前风险与episode分工

先算current issues，只有为空才release下一假动作。EpisodeGate只负责哪些通知新进入，不能决定安全；重复unsafe即使不再发告警也不release。全部当前告警发完再拉下一份，恢复后重报，流尾/关闭不预取。

## Part 5 必要责任证据

给定helper迭代校验必要DAG，长链不会受解释器递归深度限制；再算必要可达路径，optional不参与。逐必要edge看child的owner、缺control和多余authority，每条edge各查，shared child不能全局跳过。缺口按component/kind/value合并，只保留确实施加该义务的最小edge-path。stage标签不参与质量排序。

## 这套题证明了什么，没证明什么

通过说明能保存明确学习环境和责任，发现受众/期限/权限/技术边界漂移，报告具体依赖缺口。它不证明真实生产就绪、不验证控制凭证真实性、不撤销已发生写入，也不说明所有production依赖都必须标production。实际还需要责任接受、证据与组织政策。
