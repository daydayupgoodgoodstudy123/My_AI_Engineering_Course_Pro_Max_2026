# PrimSwap 面试官手册

## 开场与澄清

让候选先区分agent、handoff、shared state、orchestrator，不先说具体缺陷。所有策略均为本地脚本。

| Question | Standard answer |
|---|---|
| Must the three default traces differ? | No. Only the source of control differs; fixtures must expose it. |
| Can a policy choose the sender it impersonates? | No. The invoked Agent owns the canonical sender. |
| What does None mean here? | For target resolution it is an external selector stop; explicit agent done is a different typed outcome. |
| Are policy callables durable configuration? | No. Persist policy names and rebind through the supplied runtime registry. |
| What is shared by a store reference? | The exact supplied SharedState object, including later appends. |

## Part 1 修

主要坑：snapshot暴露整个活容器，使策略清空既有证据；setdefault接受冒充from；未知handoff被当作正常完成；last_by每次反扫无关历史。首错在正确单步消费者的required-sender读取处KeyError，修好后依次显露发送者、typed outcome及完整review响应问题。

提示：检查策略得到的view是否仍是私有池子；调用身份不能由返回消息自报。提速仍要更新最新消息并保持完整可检查历史及所有权。性能测的是预载共享池上的完整ReviewDesk.review请求与全部返回字段，不是池子构建或框架吞吐；完整连续3慢3快实测：慢0.530084/0.529200/0.525803秒，快0.002380/0.002272/0.002217秒；限值0.045秒，双余量11.6845×/18.9079×。首组慢侧3.48×未达整组保留，只调整响应限值后完整重测。

追问：snapshot和last_by各自拥有何种数据？新append后哪个观察应更新？

## Part 2 存

主要坑：durable definition与运行时callable职责分开；相同prompt而tool顺序不同不能合并；policy名称从registry解析且同一注册项可重复绑定；未知配置版本拒绝。agent definition与run配置独立key存放，manifest保留定义顺序，不能按名字排序。

给定dbm正确打开模式、UTF8/JSON及key framing。prompt字节、None/空start、zero budget是给定编解码与字段模型的护栏，不主考字节长度或通用truthiness。提示：持久化的policy名称和agent显示名称不必相同。追问：重启后如何重新绑定一段本地行为？

## Part 3 算

主要坑：静态order忽略returned handoff并保留重复位置；handoff模式遵守当前消息返回的目标，已有历史不占本轮步数预算；selector在append后观察更新状态，忽略消息中的路由建议。三套解释器各自是TODO，P1只修单步原语，不能拿单步wrapper当三套runner。

typed stop和预算原语是前关/给定依赖；候选要把正确控制来源和stop结果留在trace。提示：用同一初始researcher消息令agent返回done，再比较不同控制模式。追问：控制来源不同但消息内容相同的两个trace是否等价？

## Part 4 流

主要坑：decision描述实际控制来源的requested target；selector选择不能被returned handoff替代；stop是独立类型，保留reason、count和last speaker；记录保留原控制位置并独立拥有嵌套message payload。候选做同步领域投影，完整async driver、RS+JSON+LF和UTF8都GIVEN。发布时机/关闭与精确wire封套是集成护栏，不是通用collect-all主坑。

提示：静态最后一个决定与agent返回done是不同控制证据。追问：一个selector决定和一个handoff决定有哪些相同数据，但哪个字段真正控制下一步？

## Part 5 构

主要坑：短name要在嵌套scope中区分；store引用共享原对象而非复制；store和scheduler沿树分别继承。当前路径循环须带location拒绝；同一个无环子树在不同scope复用是合法的，不能全局visited吞掉。

这是本地composition adapter，不运行框架。提示：metadata ownership不等于复制SharedState。追问：为何两条leaf binding可以不同scope、相同store？

## 评分

每关0–4分：0未定位，1能复现，2主路径正确，3边界与所有权完整，4能解释来源、反例和限制。总20分，记录提示与独立过程；不作招聘或真实框架能力保证。
