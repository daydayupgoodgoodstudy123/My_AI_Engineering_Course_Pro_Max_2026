# 参考解释：AI Gateways — LiteLLM, Portkey, Kong AI Gateway, Bifrost

## 核心：独立权限与批准

批准不能绕过独立 capability 授权；allow 也不代表已经执行或被 OS 隔离。

准确合同：If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes.

## 加分：滑动窗口限流

清掉左边界以及更早的已接受事件，只让真正接受的事件占用槽位。

准确合同：Times are nondecreasing numeric timestamps. Keep only accepted timestamps in (now-window,now]. Accept when fewer than maximum remain. maximum exact positive int and window>0; descending timestamps/invalid config raises ValueError. Return decision bools; rejected events consume no slot.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
