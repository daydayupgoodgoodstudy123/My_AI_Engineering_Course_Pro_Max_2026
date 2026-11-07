# AuditMesh 参考讲解

## 1 一次执行与私有审计

capture_once在开始时取得输入快照，handler执行一次，emit记录真实观察，再把结果或异常封入同一个run。正确service消费者核验业务调用编号并读取凭据。原始候选把handler再调一次、持有输入别名、只给成功写完成时间；修复顺序会依次暴露后面的缺陷。

AuditStore.append只复制当前新观察；begin、seal与read/all分别在相应所有权边界取得快照。每次append重复制所有既往run会让真实多run记录成本随历史膨胀。完整计时执行所有handler、消费完整返回凭据，并核对所有私有记录；完整连续3慢3快实测：慢1.771720/1.752557/1.762869秒，快0.013874/0.014164/0.014496秒，限值0.15秒，双余量11.684×/10.348×。

## 2 轨迹是位置序列

SQLite给定schema把run主体和观察分开。save存主体及每个slot，更新同一run先移除其旧观察；load按slot恢复。纯观察、重复工具、重复时间戳都保留。session和agent共同筛选。给定的tagged值codec保留bool/int/float/null、binary64 hex与负零；给定事务负责提交和回滚。

## 3 独立的gateway

delegate先求注入的trust；拒绝或不可用都不能发生业务效果。随后调用已修capture一次，持久化并读回同一个run。模态验证对所有part执行：text对应text/plain，data/file用其声明media_type。模态不被接受时task失败，但private/public audit仍如实记载业务执行结果。

project_task_and_public_audit与public_step只进行数据投影。task id来自run而不是session；公共audit只输出时间、工具名及policy明确选择的tool_input/tool_output，永不输出私有reasoning。私有存储不会因公共脱敏而失去证据。

## 4 同步领域回调与给定driver

AuditProjection按观察出现顺序累计完整私有step，返回单个结构patch。on_seal检查run及整条已观察轨迹，输出真实status/error/completion和观察数。finish要求确实封口。stream_support提供正确async拉取、SSE编码、发布与关闭；这些机制不交给候选重新修复。

## 5 DID用途结构

将本地#fragment展开到document.id，再按verificationMethod解析每个relationship occurrence。用途选择允许的类型；controller与未解析引用分别形成finding。相同key可服务多个声明用途，每条记录仍拥有独立快照。所有密钥材料和URL都是不解释的数据。

## 来源与适配

来源为本课main.ts的AuditableRunner、ProtocolGateway、tagged MessagePart和DIDDocument，以及正文的TrajectoryMetadata、schema drift、trust failure、trajectory bloat和streaming audit exercise。实际TS等待processTask，网关task→audit；正文示例未await且audit→task。本地教学adapter只执行一个operation，再派生task/audit，不声称复制两种示例的调度顺序或协议实现。

SQLite、纳秒fixture、事件patch schema、redaction policy及结构DID检查均是明确本地合同。信任结果由注入fixture给出，不假装用stdlib替代真实Ed25519、HPKE、TLS或身份验证。

## 这套题证明了什么，没证明什么

本地测试验证所列fixture上的执行次数、所有权、观察顺序、持久化、投影、流事件和用途结构。它不证明真实协议互通、密码身份、安全合规、网络时序、模型推理质量、吞吐能力或真实用户收益。

同一agent/session查询中的多个run按创建顺序保留；公共投影分别复制嵌套tool_input/tool_output。封口比较完整私有轨迹，等长或公共字段相同仍不足以证明一致。DID controller和purpose是独立检查，同一relationship可以同时产生两条finding。
