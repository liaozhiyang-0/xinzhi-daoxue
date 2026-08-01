# StudentVerification V1

`StudentVerificationService` 接收文字 `StudentAttempt` 与
`SolutionPacketV1`，输出 `VerificationReportV1`。默认配置
`STUDENT_VERIFICATION_MODEL_ENABLED=false`，当前实现只使用规则和标准解中的
确定性信息，不调用裁判模型。

支持的通用范围包括最终数值、单位存在性/兼容性、明确正负号或参考方向冲突。
课程规则目前覆盖 CT 电容电压连续性、AE 理想运放虚短/虚断条件，以及 DE
同或/异或混淆。DE 规则只在标准解或结构化已知条件明确给出 XOR/XNOR 时生效，
不依赖模糊文本相似。

判断无法由规则确认时返回：

```text
overall_status = manual_review
first_confirmed_error_step = null
manual_review_required = true
```

多条合法路径、复杂证明、开放建模、多级电路推导、复杂时序波形、图像草稿和
自然语言省略过程均不承诺稳定诊断。正确但非最优的方法不能被标成错误。
