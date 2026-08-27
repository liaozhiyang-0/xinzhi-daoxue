# Tool、RAG 与文件链路发现

## 文件上传与解析

使用正确的 multipart 字段 `upload` 和 `text/plain` MIME 上传已有 `组员反馈/组员一反馈/README.txt`：API 返回 201，`ingestion_status=ready`，有 extracted text、quality report ready 和 1 个 chunk；GET metadata/chunks 成功。这条基础文件链路通过。

`GET /api/v1/files/{file_id}/content` 在缺少 `user_id` query 时返回 422。它可能是有意的归属校验，但错误信息对 API 使用者不够直观，且与“只拿 file_id 查看内容”的直觉不一致，应在 OpenAPI 示例中明确必填身份参数。

PowerShell 最初用错误 MIME/扩展组合上传失败 422，属于测试工具输入问题，不计为产品缺陷；服务端返回的中文在 UTF-8 文件和浏览器链路中可读，不把终端编码现象误判为服务端乱码。

## 知识库检索

已知 query `串联电阻总电阻` 返回 CT 相关章节，RAG health ready，向量库连接和维度兼容，说明基础检索可用。

随机不存在 query `完全不存在的超随机术语 zzzq-8391` 仍返回 3 条课程片段，`warnings=[]`；`rag-search` 还给出 confidence 0.558566。搜索接口没有明显的 no-match/abstention 语义，存在把低相关片段提升为证据的风险。该问题为 P1，因为答案链会受到检索结果污染。

Reranker `BAAI/bge-reranker-v2-m3` 未加载。当前系统必须显式说明是 embedding/hybrid 召回，不应把结果默认呈现为已完成相关性核验。

## 研究检索

已知医学影像 query 返回 OpenAlex/arXiv 候选；随机不存在研究 query 仍返回 5 条无关主题候选，且没有 warning。研究场景配置要求可核验来源和人工复核，但“无关候选无标记”会增加研究者误引用风险。研究检索必须增加相关性阈值、去重、source confidence 和无匹配状态。

## 工具链结论

计算/单位检查等工具注册存在，文件/向量基础设施正常；当前最大风险不是“工具不可调用”，而是工具或检索输出进入错误的 Agent/证据链，且缺少拒答和用户可理解的可信度边界。
