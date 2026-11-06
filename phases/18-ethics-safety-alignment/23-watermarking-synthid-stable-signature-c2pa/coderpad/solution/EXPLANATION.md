# 参考解释：Watermarking — SynthID, Stable Signature, C2PA

## 核心：水印比特一致率

严格检查 bit 的值和类型，再算匹配比例；一致率不能单独证明来源可信。

准确合同：Require equal-length nonempty lists of exact integer bits 0 or 1 (bool invalid). Return fraction matching. Invalid lists raise ValueError. This bit check does not establish provenance authenticity.

## 加分：声明与证据绑定

声明需要至少一条已知引用；引用存在不自动等于事实正确。

准确合同：Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
