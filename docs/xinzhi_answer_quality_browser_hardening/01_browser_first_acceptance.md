# 01 Browser-First 验收制度

## 一、强制要求

从本阶段开始：

> **浏览器实测不是补充测试，而是主测试。**

所有核心 Bug 修复都必须：

```text
浏览器复现
→ 后端定位
→ 修复
→ 浏览器验证
→ 自动化回归
```

禁止：

```text
后端测试通过
→ 直接宣布修复
```

---

# 二、浏览器测试入口

统一：

```text
http://127.0.0.1:8000/workspace
```

如项目已有 Playwright / browser automation：

优先复用。

如果没有：

可增加轻量浏览器 E2E harness。

不要另建新前端。

---

# 三、每个测试必须记录

```text
case_id
browser_session
user_prompt
attachments
scenario
visible_status
visible_answer
visible_review_state
visible_error
task_id
agent
runtime
provider
latency
semantic_grade
user_effort
```

---

# 四、浏览器真实成功定义

成功必须同时满足：

```text
任务提交成功
+
用户看得到状态
+
用户看得到正文
+
正文不是空洞 fallback
+
回答满足当前问题
+
没有无意义审批
+
最终答案/结论存在
```

---

# 五、重点抓取的问题

## B01

浏览器一直 loading。

## B02

后端 completed，但答案区域空。

## B03

后端有 answer，前端只显示 review notice。

## B04

用户问题正常，但进入 waiting_review。

## B05

页面只显示“能力受限”，不给解答。

## B06

历史消息恢复后答案不同步。

## B07

SSE 与 polling 导致答案覆盖。

## B08

同题刷新后显示不同终态。

## B09

多图上传成功，但回答明显只看了一张。

## B10

用户追问后页面上下文丢失。

---

# 六、浏览器回归最低要求

所有共享层修复：

必须至少浏览器执行：

```text
1 个普通知识问答
1 个文字解题
1 个图片解题
1 个多图问题
1 个追问
1 个自由问答
```

最终阶段再执行完整浏览器矩阵。

---

# 七、输出

生成：

```text
docs/audit/37_browser_acceptance_baseline.md
docs/audit/44_browser_final_acceptance.md
```
