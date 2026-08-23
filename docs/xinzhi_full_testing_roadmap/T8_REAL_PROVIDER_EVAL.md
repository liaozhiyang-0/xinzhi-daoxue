# T8：Real Provider Controlled Evaluation

## 目标
回答当前系统在真实模型条件下到底表现如何。

## 规模
不直接全量跑付费 336/800 cases。
优先 30–60 representative cases：hard、expert、image、long reasoning、top failure patterns。

## 模型比较
最多 2–3 models：default / backup / high-capability。

## 控制变量
尽可能固定 prompt、temperature、tools、RAG、planner、skills、reflection、experience。

## 记录
provider、model、latency、tokens、cost、score、failure stage。

## 成本门禁
必须有 max_cases、max_calls、max_tokens、max_cost、timeout。
没有预算则 SKIP。

## 提交
`test(eval): complete controlled real-provider evaluation`
