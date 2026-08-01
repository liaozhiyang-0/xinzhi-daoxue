# EvidencePacket v1

`EvidencePacketV1` 是既有 `RetrievalContextPacket` 的有界适配。适配器不会触发
第二次检索，也不会把“检索到”升级为“证明了结论”。

每个来源保留 document/chunk 标识、课程、章节、页码、标题、来源引用、检索分数、
版本/校验信息和最多 1200 字符的内容摘录。页码、来源版本或校验值缺失时保持
`null` 并写入 warning，禁止推断。

`support_level` 的默认值是 `potentially_relevant`。只有上游真实引用验证明确给出
支持关系时，未来实现才可使用 `supports_claim`；检索分数和 rerank 分数本身都
不是结论支持度。

CT、AE、DE 是第一阶段正式范围。无检索包、无命中或课程不支持时，返回空 sources
及 `unavailable`/`insufficient` 状态，不制造教材引用。调试和消息持久化只保存
有界摘录，不保存原始教材全文。
