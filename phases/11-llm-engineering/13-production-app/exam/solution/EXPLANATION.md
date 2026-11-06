# 参考说明

## Part 1

`get_prompt_record` 返回指定 name 内的指定版本 record；正确 formatter 消费 record.template。MD5(user:experiment) 的十六进制整数取模100保留 source cohort，而 Python hash 不能提供跨环境稳定值。准备阶段先 input guard，再 render；cached 内容也做 output guard，记录一条 request provenance，paid usage 为零。干净 miss 交给 Part 3。

Ledger 保留全部原 typed records，并用给定 `fold_one` 更新已有 totals；`replay_observations` 是实际公开 CPU replay 入口，逐条 append，返回完整 summary 与原 records。性能夹具包含完整请求结局和 served/shadow paid attempts，计时包含实际接收、统计、最终输出与完整比对。原教材 CostTracker 本来已增量更新，本题历史重算是刻意插入的 brownfield 回归。

## Part 2

三类表在事务内完整替换；写入失败时旧的完整 snapshot 保持可读。prompts 保留 text/name/version/model/max_tokens；assignments 用 (user,experiment) 关联稳定 bucket；observations 用给定严格 tag codec 逐条保存原事实，不能按 request_id 合并。cost_text 是精确字符串；served 展示文本不参与 token/cost 持久化。bucket 稳定不等于版本固定，traffic_pct 调整可以改变 served 版本。

## Part 3

rollout 按稳定 bucket 与 `<traffic_pct` 选一个 served 版本。shadow 为所有已准备的模型调用 miss 运行 control served 与 variant shadow，不按百分比裁掉影子。provider 是正确注入 replay，成功与 ProviderFailure 都只提供实际已观测的 AttemptFact。guard 可以替换公开文本，但不修改这些事实。每个 fact 的 role/version/ordinal 归属后入账，最后追加一条 served 请求结局。shadow 成功、质量高或失败，都不改变 served 的身份。

## Part 4

正确给定的 driver 拉取一个完成分支、绑定该分支的身份、调用领域 projector、编码完整 SSE 并关闭源。candidate 把 served_text 投影为 served content，把 status/quality/原 paid_usage 投影为 telemetry；shadow 不公开文本。短拒绝的 output_tokens 仍来自原观测。这里重放已完成分支，不能声称真实 provider token streaming、网络背压或生产 SSE 兼容性测试。

## Part 5

先逐 template→version→record 检查 outer identity 与 record.model，再按实验声明的 template 解析 control/variant。每条问题保留实际完整路径，继续访问所有 sibling。实验 `valid` 只表示引用存在；record 的自身有效性在版本报告独立呈现。configuration_ready 表示本地静态一致性，不是健康检查或可用性保证。

本包只验证 Python 3.10 标准库与 pytest 下的本地行为。模型、成本、guard、质量与 provider 都是 fixture；没有真实模型、网络、线上质量、生产性能或真人用时校准。来源 hash、实际测量与独立审查证据见 SCOPE 与包外报告。

本机性能证据：完整公开观测重放连续三慢 0.408216/0.425903/0.415167 秒，三快 0.001255/0.001226/0.002054 秒；响应限值 0.04 秒，最差双侧余量 10.205×/19.471×。680 条输入事实和完整输出都参与真实路径；不代表 provider 延迟或生产吞吐。完整测量与执行记录见 SCOPE 链接的包外报告。
