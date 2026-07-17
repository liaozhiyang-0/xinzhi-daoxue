# 三课程本地检索评测草稿

这里保存 CT、AE、DE 各 5 条、合计 15 条从真实教材章节抽取的查询草稿。案例均为 `review_status: draft`，不是正式 benchmark，必须由课程教师或维护者核对问题措辞、目标章节和来源路径。

指标以 required `document_path` 为相关性判断；`chapter` 保留给人工审核。`wrong_course_rate` 统计 top-1 落入 `forbidden_courses` 的案例比例。延迟只覆盖进程内检索，不包含首次索引时间。

```powershell
python evaluation/knowledge_retrieval/scripts/validate_cases.py
python evaluation/knowledge_retrieval/scripts/run_retrieval_benchmark.py --mode baseline_lexical_v1
python evaluation/knowledge_retrieval/scripts/run_retrieval_benchmark.py --mode local_lexical_v2
python evaluation/knowledge_retrieval/scripts/compare_runs.py evaluation/knowledge_retrieval/results/baseline_lexical_v1.json evaluation/knowledge_retrieval/results/local_lexical_v2.json
```

脚本优先使用显式 `--ct-path/--ae-path/--de-path`，否则发现当前仓库或相邻 `xinzhi-daoxue` 工作目录中的中文教材目录。结果文件记录实际语料路径、文档数、分块数、逐案例排名和真实测量指标。
