# T7：Robustness / Fault / Stress Test

## 目标
测试系统在异常和压力条件下是否稳定。

## 输入异常
empty、very long、incomplete、formula-heavy、bad image、multiple attachments、unsupported file、mixed language。

## Provider
模拟 timeout / 429 / 500 / invalid schema / slow response / unavailable。

## RAG
no result / wrong course / low score / embedding unavailable / reranker unavailable / index unavailable。

## Tool
timeout / malformed output / calculation failure / dependency unavailable。

## Runtime
resume / retry / cancel / checkpoint / worker restart / duplicate request / interrupted task。

## 并发
1 → 5 → 10 → 20，环境不足时到 10。

记录 p50/p95/p99、failure rate、queue delay、CPU、memory。

## 长时间
provider-free/mock 模式 30–60 min，观察 memory leak、dead task、stale lock、queue growth、resource leak。

## 提交
`test(system): complete robustness and stress validation`
