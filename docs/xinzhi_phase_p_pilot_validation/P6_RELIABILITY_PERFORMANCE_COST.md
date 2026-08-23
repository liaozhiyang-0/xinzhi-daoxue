# P6：稳定性、性能与成本

## Runtime
测试：
retry / resume / cancel / waiting_review / waiting_user / duplicate request / SSE reconnect / checkpoint recovery

## Provider Fault
timeout / 429 / 500 / malformed response / unavailable

## RAG / Tool Fault
empty retrieval / wrong retrieval / tool timeout / malformed output

## 性能
记录：
```text
latency p50
latency p95
model calls
tokens
RAG latency
tool latency
failure rate
```

## 成本
真实 Provider 必须有：
max_cases / max_calls / max_tokens / max_cost

## 并发
1 → 5 → 10，根据实际环境决定是否到 20。

## Gate
六个现场 Demo 不允许存在可重复的：
卡死 / SSE 永不终止 / retry 失效 / review 状态丢失。
