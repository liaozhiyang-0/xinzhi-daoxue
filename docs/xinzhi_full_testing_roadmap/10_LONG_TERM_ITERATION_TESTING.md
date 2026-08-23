# 长期测试迭代机制

T9 后固定循环：

New Cases → Benchmark → Failure Analysis → Top 3 Problems → Targeted Suite → Minimal Improvement → Replay → Regression → Hidden Holdout → Release。

每次优化只解决 3–5 个高价值问题。

新题来源：
真实学生问题、历年试卷、教材综合题、图片题、教师教学任务、Research 实际需求、线上失败案例。

测试集增长建议：
336 → 500 → 800 → 1000+。

覆盖质量优先于数量。

每次 Release 必须报告：
score delta、top fixes、new failures、cost delta、latency delta、known limitations。

最终形成：
Benchmark-driven Agent Development。
