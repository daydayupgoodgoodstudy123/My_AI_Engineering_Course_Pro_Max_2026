---
name: computer-use-safety
description: Build per-step safety classifier + confirmation gate for a computer-use agent, with allowlist navigation and injection-marker filtering.
version: 1.0.0
phase: 14
lesson: 21
tags: [computer-use, safety, claude, openai-cua, gemini]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


使用计算机 agent 以及目标应用程序列表, 产生一个安全层, 将执行前的每个动作分类 。

显示 :

1. `SafetyClassifier.assess(action, screen) -> SafetyVerdict` 与字段 `allow`, `reason`, `needs_confirmation`.
2. 元素标签允许列表 agent 单击;否则拒绝。
3. 允许的 URL 列表 agent 能够导航;拒绝从列表中重新定向。
4. 在 DOM 文本上输入标记过滤器, 检索内容, 并输入文本。 任何匹配的选项都阻挡了动作 。
5. 敏感动作的确认关( 登录、 购买、 删除、 发布) 。 Human-in-the-loop 回调界面 。
6. Trace 发布:每个决定记录(行动、判决、理由)。

艰难的拒绝 :

- 仅运行于第一个动作的安全分类器。 每个动作都必须被分类 。
- 表格允许列表 `*`。允许一切的许可列表不是允许列表。
- 跳过确认是因为模型"看起来有信心"。

拒绝规则 :

- 如果 agent 拥有计算机使用权限,无一步步安全,拒绝装运。
- 如果 agent 中可浏览任意的 URL, 拒绝。 需要允许列表或块列表 。
- 如果敏感行动在任何模式下绕过确认大门,请拒绝。

输出: `classifier.py`, `allowlist.py`, `confirmation.py`, `trace.py`, `README.md` 解释大门政策、 输入标记和允许列表维护程序。 结尾处指向课程 27 () “ 下一步读什么 ” (what to read next)prompt injection)和23课(OTel涵盖安全决定的归属)。
