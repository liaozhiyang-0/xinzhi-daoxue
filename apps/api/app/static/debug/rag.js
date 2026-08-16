const { $, all, api, badge, el, initShell, initTabs, renderJson, renderMarkdown, toast } = XinzhiUI;
const state = { trace: null, channel: "bm25" };
const pretty = (value) => JSON.stringify(value ?? {}, null, 2);
function payload() { return { question: $("#debug-question").value.trim(), course_id: $("#debug-course").value, intent: $("#debug-intent").value, response_depth: $("#response-depth").value, conversation_summary: $("#conversation-summary").value.trim(), previous_answer_summary: $("#previous-summary").value.trim(), use_rag: $("#use-rag").checked, include_images: $("#include-images").checked, use_reranker: $("#use-reranker").checked } }
function imageUrl(uri) { if (!String(uri).startsWith("kb-image://")) return ""; const rest = uri.slice(11); const slash = rest.indexOf("/"); if (slash < 0) return ""; return `/api/v1/knowledge/images/${encodeURIComponent(rest.slice(0, slash))}/${rest.slice(slash + 1).split("/").map(encodeURIComponent).join("/")}`; }
function metric(name, value, status = "ready") { return el("article", { class: "metric-card" }, [badge(status), el("strong", { text: String(value ?? "—"), title: String(value ?? "—") }), el("span", { text: name })]); }
async function loadStatus() {
  try { const data = await api("/api/v1/debug/rag/status", {}, 10000); $("#status-grid").replaceChildren(metric("API", data.api_status), metric("Provider", `${data.provider} · ${data.provider_available ? "available" : "unavailable"}`, data.provider_available ? "ready" : "degraded"), metric("文本模型", data.text_model_loaded ? "已加载" : "懒加载", data.text_model_loaded ? "ready" : "planned"), metric("图片模型", data.image_model_loaded ? "已加载" : "懒加载", data.image_model_loaded ? "ready" : "planned"), metric("Qdrant", data.vector_store_connected ? "connected" : "degraded", data.vector_store_connected ? "ready" : "degraded"), metric("文本 / 图片 Points", `${data.text_vector_count ?? "—"} / ${data.image_vector_count ?? "—"}`)); const health = badge(data.vector_store_connected ? "ready" : "degraded", data.vector_store_connected ? "索引正常" : "索引降级"); health.id = "health-badge"; $("#health-badge").replaceWith(health); $("#health-time").textContent = `检查于 ${new Date().toLocaleTimeString()}`; }
  catch (error) { const health = badge("failed", "状态不可用"); health.id = "health-badge"; $("#health-badge").replaceWith(health); $("#status-grid").replaceChildren(el("div", { class: "error-state", text: `${error.message}。请检查本地依赖。` })); }
}
async function loadAgents() {
  try { const data = await api("/api/v1/agents/status", {}, 5000); const agents = data.agents || []; $("#agent-select").replaceChildren(...agents.map((item) => el("option", { value: item.agent_id, text: `${item.agent_id} · ${item.configured ? "configured" : "not configured"}` }))); $("#agent-registry-grid").replaceChildren(...agents.map((item) => metric(item.agent_id, `${item.publication_status} · ${item.retrieval_policy}`, item.configured ? item.publication_status : "not_configured"))); renderJson($("#agent-plan-json"), { provider_runtime: data.provider_runtime || {}, note: "敏感凭据始终不会返回" }); }
  catch (error) { $("#agent-registry-grid").replaceChildren(el("div", { class: "error-state", text: error.message })); }
}
async function dryRunAgent() { const id = $("#agent-select").value; if (!id) return; const button = $("#agent-dry-run"); button.disabled = true; try { const data = await api(`/api/v1/agents/${encodeURIComponent(id)}/dry-run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: $("#agent-question").value || "示例问题", course_id: $("#debug-course").value, intent: $("#debug-intent").value, retrieved_context: "[debug mapping preview]" }) }); renderJson($("#agent-plan-json"), data); toast("执行计划预览已生成"); } catch (error) { renderJson($("#agent-plan-json"), { error: error.message }); } finally { button.disabled = false; } }
function renderTimeline(stages = []) { $("#timeline").replaceChildren(...(stages.length ? stages.map((item, index) => el("div", { class: "timeline-item" }, [el("div", { class: "timeline-index", text: String(index + 1).padStart(2, "0") }), el("div", {}, [el("strong", { text: item.name }), el("p", { text: item.summary || `${item.input_count} → ${item.output_count}` }), ...(item.warnings || []).map((warning) => el("small", { text: warning }))]), el("div", {}, [badge(item.status), el("span", { class: "latency", text: `${item.latency_ms} ms` })])])) : [el("div", { class: "empty-state", text: "无阶段数据。" })])); }
function renderEvidence() {
  const channel = state.trace?.retrieval?.trace?.[state.channel] || [];
  if (!channel.length) {
    $("#retrieval-results").replaceChildren(el("div", { class: "empty-state", text: "该通道未运行或无结果。" }));
    return;
  }
  if (state.channel === "images") {
    const figures = channel.map((item) => {
      const src = imageUrl(item.resource_uri);
      return el("figure", { class: "image-thumbnail" }, [
        src ? el("img", { src, loading: "lazy", alt: "相关证据图" }) : null,
        el("figcaption", { text: `${item.caption || item.resource_uri} · score ${Number(item.score || 0).toFixed(4)}` }),
      ].filter(Boolean));
    });
    $("#retrieval-results").replaceChildren(...figures);
    return;
  }
  const rows = channel.map((item, rank) => el("article", { class: "evidence-item" }, [
    el("div", { class: "evidence-rank", text: `#${rank + 1}` }),
    el("div", {}, [
      el("h3", { text: item.title || "Untitled" }),
      el("p", { text: item.text_preview || item.content || "" }),
      el("div", { class: "evidence-meta" }, [item.course_id, item.chapter, item.content_type, item.source_uri || item.source_ref].filter(Boolean).map((value) => el("span", { text: value }))),
    ]),
    el("div", { class: "score-column" }, [
      el("strong", { text: Number(item.final_score ?? item.score ?? 0).toFixed(4) }),
      el("small", { text: (item.retrieval_channels || []).join(" + ") }),
    ]),
  ]));
  $("#retrieval-results").replaceChildren(...rows);
}
function renderFinal(final = {}) { const provider = badge(final.fallback_used ? "degraded" : final.provider === "mock" ? "mock" : "success", final.provider || "unknown"); provider.id = "final-provider"; $("#final-provider").replaceWith(provider); $("#final-meta").replaceChildren(metric("RAG", final.rag_status), metric("Evidence", final.evidence_status), metric("Fallback", final.fallback_used ? `是 · ${final.fallback_reason}` : "否", final.fallback_used ? "degraded" : "ready"), metric("总耗时", `${final.total_latency_ms || 0} ms`)); $("#final-answer-debug").className = "markdown-viewer"; renderMarkdown($("#final-answer-debug"), final.answer_text || "无回答"); $("#final-citations").replaceChildren(...((final.citations || []).length ? final.citations.map((item) => el("span", { class: "citation-chip", text: item })) : [el("span", { class: "muted", text: "无最终引用" })])); $("#final-images").replaceChildren(...(final.related_images || []).map((item) => { const src = imageUrl(item.resource_uri); return src ? el("figure", { class: "image-thumbnail" }, [el("img", { src, loading: "lazy", alt: item.caption || "相关图片" }), el("figcaption", { text: item.caption || item.resource_uri })]) : null; }).filter(Boolean)); }
function renderTrace(trace) { state.trace = trace; $("#trace-id").textContent = trace.trace_id; renderTimeline(trace.stages); renderEvidence(); renderJson($("#context-json"), trace.context); $("#retrieved-context").textContent = trace.retrieved_context || "未启用 RAG"; renderJson($("#citation-json"), trace.citation_validation); renderFinal(trace.final); }
async function runTrace(event) { event?.preventDefault(); $("#debug-error").textContent = ""; const button = $("#run-button"); button.disabled = true; button.textContent = "运行中…"; try { renderTrace(await api("/api/v1/debug/rag/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) })); toast("完整链路运行完成"); } catch (error) { $("#debug-error").textContent = `${error.message}。请调整输入或检查服务状态。`; } finally { button.disabled = false; button.textContent = "运行完整链路"; } }
async function runEval() { const limit = Number($("#eval-limit").value); if (limit >= 20 && !window.confirm(`即将运行 ${limit} 条本地评测，确认继续？`)) return; const button = $("#eval-button"); button.disabled = true; button.textContent = "评测中…"; try { const data = await api("/api/v1/debug/rag/eval", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ group: $("#eval-group").value, limit }) }); $("#eval-summary").replaceChildren(metric("总数", data.total), metric("通过", data.passed), metric("失败", data.failed, data.failed ? "failed" : "ready"), metric("人工复核", data.manual_review_required), metric("Top3 代理召回", `${(data.top3_recall_proxy * 100).toFixed(1)}%`)); $("#eval-results").replaceChildren(...data.results.map((item) => el("div", { class: "eval-row" }, [el("strong", { text: item.case_id }), badge(item.passed ? "success" : "failed"), el("span", { text: item.status || item.trace_id || "" })]))); } catch (error) { $("#eval-results").replaceChildren(el("div", { class: "error-state", text: error.message })); } finally { button.disabled = false; button.textContent = "运行评测"; } }
window.addEventListener("DOMContentLoaded", () => { initShell({ page: "rag", title: "多模态 RAG 调试", description: "检索、证据与引用链路" }); initTabs(); $("#rag-form").addEventListener("submit", runTrace); $("#eval-button").addEventListener("click", runEval); $("#agent-dry-run").addEventListener("click", dryRunAgent); all("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("#debug-question").value = button.dataset.prompt; $("#debug-course").value = button.dataset.course; if (button.dataset.intent) $("#debug-intent").value = button.dataset.intent; })); all("[data-channel]").forEach((button) => button.addEventListener("click", () => { all("[data-channel]").forEach((item) => item.classList.remove("active")); button.classList.add("active"); state.channel = button.dataset.channel; renderEvidence(); })); all("[data-copy]").forEach((button) => button.addEventListener("click", async () => { await navigator.clipboard.writeText($(`#${button.dataset.copy}`).textContent); toast("内容已复制"); })); if (new URLSearchParams(location.search).get("scenario") === "fallback") { $("#debug-question").value = "为什么电容电压不能突变？"; toast("已载入受控本地降级场景", "degraded"); } loadStatus(); loadAgents(); });
