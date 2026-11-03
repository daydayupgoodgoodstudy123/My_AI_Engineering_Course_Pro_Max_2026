<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="portable-contract-checklist"></a>

# 便携式合同核对表

- 包是一个包含常规的目录 `SKILL.md` file.
- 前事项从第一行开始,并有一个关闭分隔符。
- `name` ,不超过64个字符,使用小写字母、数字和单连字符。
- `name` 匹配捆绑目录 。
- `description` 显示为存在,不超过1024个字符,并显示技能有用时。
- 可选 `compatibility` 包含 1 到 500 个字符。
- 可选 `metadata` 映射字符串的密钥以显示字符串值。
- 可选实验 `allowed-tools` 是一个非空的空格分隔字符串,其行为在目标主机中被验证。
- 未知运行时间字段与便携式包件合同分离,由明确的适配器处理。
- 该 Markdown 身体包含程序。
- 可选的便携式元数据和主机特有扩展仍然可以区分。

通过此核对表, 软件包结构上可以加载。 它不授予文件系统、 网络、 秘密、 子进程或工具权限 。
