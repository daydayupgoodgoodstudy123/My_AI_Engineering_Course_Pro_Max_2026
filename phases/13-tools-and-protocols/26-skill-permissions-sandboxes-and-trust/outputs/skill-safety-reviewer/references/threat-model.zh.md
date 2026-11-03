<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="threat-model"></a>

# Threat model

独立审查这些边界:

- 权限: 指令不能重写主机权限 。
- 文件系统: 解决目标, 并保留在工作空间根内; 拒绝符号链接退出 。
- 命令:接受一个argv 矩阵,拒绝提供Shell元字符和破坏性执行文件,并要求有一个可执行的允许列表。
- 网络:需要 HTTPS 和精确来源许可列表。 将有效的端口正常化, 所以 `https://api.example.test` 和 `https://api.example.test:443` 匹配, 端口 `8443` 需要自己的条目。 不接受 URL 用户信息中的证书 。
- 外部内容:将检索到的文本作为数据处理,从不作为政策或核准。
- 秘密:在不记录其价值的情况下,探测可能含有秘密的有效载荷。
- 破坏性行动:根据东道方的政策拒绝或要求有记录的人类批准。

一个 `allow` 裁决仅表示模拟请求符合所提供的策略。 此捆绑不执行任何动作 。
