<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="task-frame-prevent-duplicate-email-addresses-during-signup"></a>

# 任务框架: 注册时防止重复电子邮件地址

现况:准备

<a id="repository-facts"></a>

## 仓库事实
- 账户写入使用账户Store(`app/accounts.py:18`)
- 重复错误使用状态 409 ()`tests/test_accounts.py:44`)

<a id="allowed-paths"></a>

## 允许路径
- `app/accounts.py`
- `tests/test_accounts.py`

<a id="forbidden-paths"></a>

## 禁止路径
- `migrations/**`
- `deploy/**`

<a id="acceptance-evidence"></a>

## 接受证据
- `python3 -m unittest tests.test_accounts`

<a id="unknowns"></a>

## Unknowns
- 电子邮件比较是否不区分大小写
