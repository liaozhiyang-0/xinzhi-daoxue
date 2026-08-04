const { $, all, api, badge, el, initShell, toast } = XinzhiUI;

const feedbackLabels = {
  applied_correctly: "采纳后正确",
  applied_incorrectly: "采纳后仍错误",
  partially_applied: "部分采纳",
  not_applied: "未采纳",
  indeterminate: "无法判定",
  not_applicable: "不适用",
};
const qualityLabels = {
  ready: "可处理",
  review: "待人工复核",
  failed: "解析失败",
  unknown: "未知",
};
const materialReviewLabels = {
  not_required: "无需复核",
  pending: "待复核",
  approved: "复核通过",
  rejected: "已退回",
};
const verificationLabels = {
  verified_correct: "验证正确",
  verified_incorrect: "验证错误",
  heuristic_correct: "启发式正确",
  heuristic_incorrect: "启发式错误",
  manual_review: "人工复核",
  not_checked: "未检查",
};
const teacherStatusLabels = {
  unknown: "未知",
  unavailable: "不可用",
  not_attached: "未附加",
  not_checkable: "无法检查",
  available: "可用",
  partial: "部分可用",
  ready: "已就绪",
  pending: "待处理",
  evidence_ready: "证据就绪",
  evidence_missing: "缺少证据",
  complete_with_evidence: "证据完整",
  decision_file_missing: "缺少决定文件",
  invalid_or_stale: "无效或过期",
  not_declared: "未声明",
  missing: "缺失",
};
let feedbackEnabled = true;

function teacherStatus(value, fallback = "未知") {
  return teacherStatusLabels[String(value)] || fallback;
}

function localDateTimeValue(value) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function isoWindowValue(value) {
  return new Date(value).toISOString();
}

function renderMetric(label, value, status = "ready") {
  return el("article", { class: "teacher-metric" }, [badge(status), el("strong", { text: String(value ?? 0) }), el("span", { text: label })]);
}

function renderDistribution(target, values, labels) {
  const entries = Object.entries(values || {});
  const total = entries.reduce((sum, [, value]) => sum + Number(value || 0), 0) || 1;
  if (!entries.length) {
    $(target).replaceChildren(el("p", { class: "empty-state", text: "当前窗口暂无数据" }));
    return;
  }
  $(target).replaceChildren(...entries.sort((a, b) => b[1] - a[1]).map(([key, value]) => {
    const amount = Number(value || 0);
    return el("div", { class: "distribution-row" }, [
      el("span", { text: labels[key] || key }),
      el("div", { class: "distribution-track" }, el("div", { class: "distribution-fill", style: `width:${Math.max(4, amount / total * 100)}%` })),
      el("strong", { text: String(amount) }),
    ]);
  }));
}

function renderWarnings(data) {
  const warnings = data.data_quality_warnings || [];
  if (!warnings.length) {
    $("#teacher-warnings").replaceChildren(el("p", { class: "teacher-warning-empty", text: "当前窗口没有额外数据质量告警。" }));
    return;
  }
  $("#teacher-warnings").replaceChildren(...warnings.map((warning) => el("div", { class: "teacher-warning", text: warning })));
}

function renderMaterialQuality(items) {
  if (!items.length) {
    $("#teacher-material-quality").replaceChildren(el("p", { class: "empty-state", text: "当前窗口暂无课程材料" }));
    return;
  }
  const ordered = [...items].sort((a, b) => {
    const review = Number(Boolean(b.manual_review_required)) - Number(Boolean(a.manual_review_required));
    return review || String(a.filename).localeCompare(String(b.filename));
  });
  $("#teacher-material-quality").replaceChildren(...ordered.map((item) => {
    const candidatePages = (item.ocr_candidate_pages || []).join(", ");
    const reviewStatus = item.material_review_status || "not_required";
    const details = [
      `${item.course_id || "-"} · ${item.material_key || item.filename}`,
      `第 ${item.material_version || "未知"} 版`,
      `复核：${materialReviewLabels[reviewStatus] || "未知"}`,
      item.ocr_required ? `OCR待处理：${candidatePages ? `第${candidatePages}页` : "待确认"}` : "无需 OCR",
    ];
    if (item.quality_warnings?.length) details.push(item.quality_warnings.join("；"));
    return el("div", { class: "teacher-material-row" }, [
      el("div", { class: "teacher-material-main" }, [
        el("strong", { text: item.filename || "未命名文件" }),
        el("span", { text: details.join(" · ") }),
      ]),
      badge(
        item.manual_review_required
          ? "degraded"
          : item.quality_status === "failed"
            ? "failed"
            : item.quality_status === "ready"
              ? "ready"
              : "未知",
        qualityLabels[item.quality_status] || teacherStatus(item.quality_status),
      ),
      el("button", {
        class: "button secondary teacher-material-preview-button",
        type: "button",
        text: "查看解析片段",
        onClick: (event) => loadMaterialChunks(item, event.currentTarget),
      }),
      el("div", { class: "teacher-material-actions" }, [
        ...["approved", "rejected"].map((status) => el("button", {
          class: "button secondary teacher-material-review-button",
          type: "button",
          text: status === "approved" ? "复核通过" : "复核退回",
          onClick: (event) => reviewMaterial(item, status, event.currentTarget),
        })),
      ]),
    ]);
  }));
}

async function reviewMaterial(item, status, button) {
  const note = window.prompt("复核备注（可选）", item.material_review_note || "");
  if (note === null) return;
  button.disabled = true;
  try {
    await api(`/api/v1/knowledge/materials/${encodeURIComponent(item.file_id)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note }),
    });
    toast(status === "approved" ? "复核已通过" : "材料已退回", status === "approved" ? "ready" : "degraded");
    await loadMaterials();
  } catch (error) {
    toast(error.message, "failed");
  } finally {
    button.disabled = false;
  }
}

async function loadMaterialChunks(item, button) {
  const row = button.closest(".teacher-material-row");
  if (!row) return;
  button.disabled = true;
  try {
    const chunks = await api(`/api/v1/knowledge/materials/${encodeURIComponent(item.file_id)}/chunks`);
    row.querySelector(".teacher-material-preview")?.remove();
    const preview = el("div", { class: "teacher-material-preview" }, [
      ...(chunks.length ? chunks.slice(0, 3).map((chunk) => el("p", {
        text: `片段 ${chunk.ordinal + 1}${chunk.page_number ? ` · 第${chunk.page_number}页` : ""}：${String(chunk.content || "").slice(0, 600)}`,
      })) : [el("p", { text: "暂无已解析片段" })]),
    ]);
    row.append(preview);
  } catch (error) {
    toast(error.message, "failed");
  } finally {
    button.disabled = false;
  }
}

async function loadMaterials() {
  const params = new URLSearchParams();
  const course = $("#teacher-course").value;
  if (course) params.set("course_id", course);
  try {
    const items = await api(`/api/v1/knowledge/materials?${params.toString()}`);
    renderMaterialQuality(items);
  } catch (error) {
    $("#teacher-material-quality").replaceChildren(el("div", { class: "notice failed", text: error.message }));
  }
}

function renderMetrics(data) {
  const metrics = [
    renderMetric("学习尝试", data.attempt_count),
    renderMetric("人工复核", data.manual_review_count, data.manual_review_count ? "warning" : "ready"),
    renderMetric("复测计划", data.retest_count),
  ];
  if (feedbackEnabled) {
    metrics.splice(2, 0,
      renderMetric("反馈事件", data.feedback_uptake_event_count),
      renderMetric("反馈可判定率", data.feedback_uptake_determinate_rate == null ? "—" : `${(data.feedback_uptake_determinate_rate * 100).toFixed(1)}%`),
      renderMetric("采纳后确定正确", data.feedback_uptake_applied_correctly_count),
    );
  }
  $("#teacher-metrics").replaceChildren(...metrics);
  renderDistribution("#teacher-feedback-distribution", data.feedback_uptake_status_counts, feedbackLabels);
  renderDistribution("#teacher-verification-distribution", data.verification_status_counts, verificationLabels);
  renderWarnings(data);
}

function setDefaultWindow() {
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
  $("#teacher-window-start").value = localDateTimeValue(start);
  $("#teacher-window-end").value = localDateTimeValue(end);
}

const ocrReviewLabels = {
  select_pages_for_ocr: "先选择需要 OCR 的页面",
  split_or_review_parse_limit: "拆分文件或检查解析大小限制",
  confirm_low_text_pages: "确认低文本页面",
  inspect_pdf_parse_failure: "检查 PDF 解析失败",
  teacher_confirm_before_index: "教师确认后再进入索引",
};
const ocrDecisionLabels = {
  pending: "待处理",
  approve_existing_text: "通过现有文本",
  request_ocr: "申请 OCR",
  split_pdf: "拆分 PDF",
  reject_source: "退回来源",
  needs_manual_inspection: "需要人工检查",
};
const ocrDecisionValues = Object.keys(ocrDecisionLabels);
const ocrAuditStatusLabels = { available: "可用", partial: "部分可用", unavailable: "不可用" };
const ocrCacheStatusLabels = { hit: "命中", miss: "未命中", unknown: "未知" };

const ocrReviewState = {
  payload: null,
  requestId: 0,
  action: "",
  priority: "",
  decision: "",
};
const ocrQualityState = { requestId: 0 };
const teacherAssetReviewState = { payloads: [] };

function formatOCRSnapshotAge(seconds) {
  const age = Number(seconds);
  if (!Number.isFinite(age) || age < 1) return "刚刚";
  if (age < 60) return `${Math.round(age)} 秒前`;
  if (age < 3600) return `${Math.round(age / 60)} 分钟前`;
  return `${Math.round(age / 3600)} 小时前`;
}

function truncateOCRText(value, limit = 180) {
  const text = String(value || "").trim();
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

function setOCRFilterOptions(payload) {
  const summary = payload.summary || {};
  const actionSelect = $("#teacher-ocr-action-filter");
  const prioritySelect = $("#teacher-ocr-priority-filter");
  const decisionSelect = $("#teacher-ocr-decision-filter");
  if (!actionSelect || !prioritySelect || !decisionSelect) return;
  const actions = Object.keys(summary.by_action || {}).sort();
  actionSelect.replaceChildren(
    el("option", { value: "", text: "全部复核动作" }),
    ...actions.map((action) => el("option", {
      value: action,
      text: ocrReviewLabels[action] || action,
    })),
  );
  ocrReviewState.action = actions.includes(ocrReviewState.action) ? ocrReviewState.action : "";
  ocrReviewState.priority = ["", "high", "medium"].includes(ocrReviewState.priority)
    ? ocrReviewState.priority
    : "";
  ocrReviewState.decision = ["", "pending", "decided"].includes(ocrReviewState.decision)
    ? ocrReviewState.decision
    : "";
  actionSelect.value = ocrReviewState.action;
  prioritySelect.value = ocrReviewState.priority;
  decisionSelect.value = ocrReviewState.decision;
}

function filteredOCRRows(payload) {
  const rows = payload.rows || [];
  return rows.filter((item) => {
    const decision = item.review_decision || "pending";
    return (!ocrReviewState.action || item.review_action === ocrReviewState.action)
      && (!ocrReviewState.priority || item.priority === ocrReviewState.priority)
      && (!ocrReviewState.decision
        || (ocrReviewState.decision === "pending" && decision === "pending")
        || (ocrReviewState.decision === "decided" && decision !== "pending"));
  });
}

async function saveOCRDecision(item, decisionSelect, evidenceInput, noteInput, button) {
  const reviewer = $("#teacher-ocr-reviewer").value.trim();
  if (!reviewer) {
    toast("保存 OCR 决定前请输入复核人姓名。", "failed");
    return;
  }
  const currentPayload = ocrReviewState.payload;
  if (!currentPayload) return;
  const evidenceRefs = evidenceInput.value
    .split(/\r?\n|,/)
    .map((value) => value.trim())
    .filter(Boolean);
  const decisions = (currentPayload.rows || []).map((row) => {
    const selected = row.queue_id === item.queue_id;
    return {
      queue_id: row.queue_id,
      checksum: row.checksum,
      decision: selected ? decisionSelect.value : (row.review_decision || "pending"),
      evidence_refs: selected ? evidenceRefs : (Array.isArray(row.evidence_refs) ? row.evidence_refs : []),
      note: selected ? noteInput.value.trim() : (row.decision_note || ""),
    };
  });
  button.disabled = true;
  try {
    const updated = await api(`/api/v1/knowledge/ocr-review-decisions/${encodeURIComponent(item.course_id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_fingerprint: currentPayload.source_fingerprint,
        reviewer,
        decisions,
      }),
    });
    renderOCRReviewQueue(updated);
    await loadOCRQualitySummary();
    toast("OCR 决定和证据已保存。", "ready");
  } catch (error) {
    toast(error.message, "failed");
  } finally {
    button.disabled = false;
  }
}

function renderOCRReviewQueue(payload) {
  const summary = payload.summary || {};
  const reports = payload.decision_reports || {};
  const reportCount = Object.keys(reports).length;
  ocrReviewState.payload = payload;
  setOCRFilterOptions(payload);
  const cacheStatus = payload.cache_status || "unknown";
  const cacheBackend = payload.cache_backend || "none";
  const cacheTone = cacheStatus === "hit" ? "ready" : cacheStatus === "miss" ? "warning" : "degraded";
  $("#teacher-ocr-summary").replaceChildren(
    badge("degraded", `候选项 ${Number(summary.candidate_count || 0)}`),
    badge("warning", `高优先级 ${Number(summary.by_priority?.high || 0)}`),
    badge("ready", `决定文件 ${reportCount}`),
    badge(cacheTone, `快照 ${ocrCacheStatusLabels[cacheStatus] || "未知"}`),
    el("span", { class: "teacher-ocr-cache-note", text: `${cacheBackend} · ${formatOCRSnapshotAge(payload.snapshot_age_seconds)}` }),
  );
  const rows = payload.rows || [];
  const visibleRows = filteredOCRRows(payload);
  $("#teacher-ocr-filter-count").textContent = `显示 ${visibleRows.length} / ${rows.length} 个候选项`;
  if (!visibleRows.length) {
    $("#teacher-ocr-review").replaceChildren(
      el("p", {
        class: "empty-state",
        text: rows.length ? "没有符合当前筛选条件的候选项。" : "当前课程没有 PDF/OCR 复核候选项。",
      }),
    );
    return;
  }
  $("#teacher-ocr-review").replaceChildren(...visibleRows.map((item) => {
    const candidatePages = (item.ocr_candidate_pages || []).join(", ") || "待确认";
    const action = ocrReviewLabels[item.review_action] || item.review_action || "人工检查";
    const decision = item.review_decision || "pending";
    const pageCount = item.page_count ? `共 ${item.page_count} 页` : "页数未知";
    const evidenceRefs = Array.isArray(item.evidence_refs)
      ? item.evidence_refs.map((value) => truncateOCRText(value, 100)).filter(Boolean).slice(0, 3)
      : [];
    const decisionDetails = [];
    if (item.reviewer) decisionDetails.push(`复核人：${item.reviewer}`);
    if (item.reviewed_at) decisionDetails.push(`复核时间：${item.reviewed_at}`);
    if (evidenceRefs.length) decisionDetails.push(`证据：${evidenceRefs.join(" · ")}`);
    if (item.decision_note) decisionDetails.push(`备注：${truncateOCRText(item.decision_note)}`);
    const decisionSelect = el("select", {
      class: "teacher-ocr-decision-editor",
      "aria-label": `处理决定：${item.relative_path || item.file_name || item.queue_id}`,
    }, ocrDecisionValues.map((value) => el("option", {
      value,
      text: ocrDecisionLabels[value],
    })));
    decisionSelect.value = decision;
    const evidenceInput = el("textarea", {
      class: "teacher-ocr-evidence-editor",
      rows: "2",
      placeholder: "证据引用，每行一条（文档/页面/来源）",
      "aria-label": "OCR 证据引用",
    }, (Array.isArray(item.evidence_refs) ? item.evidence_refs : []).join("\n"));
    const noteInput = el("textarea", {
      class: "teacher-ocr-note-editor",
      rows: "2",
      placeholder: "可选复核备注",
      "aria-label": "OCR 决定备注",
    }, item.decision_note || "");
    const saveButton = el("button", {
      class: "button secondary teacher-ocr-save-button",
      type: "button",
      text: "保存决定",
      onClick: () => saveOCRDecision(item, decisionSelect, evidenceInput, noteInput, saveButton),
    });
    return el("div", { class: "teacher-ocr-row" }, [
      el("strong", { text: `${item.course_id || "-"} · ${item.relative_path || item.file_name || "未命名文件"}` }),
      el("span", { text: `${action} · 候选页面：${candidatePages} · ${pageCount}` }),
      el("div", { class: "teacher-ocr-meta" }, [
        badge(item.priority === "high" ? "failed" : "warning", item.priority === "high" ? "高" : item.priority === "medium" ? "中" : "待复核"),
        badge(decision === "pending" ? "warning" : "ready", `决定：${ocrDecisionLabels[decision] || decision}`),
      ].filter(Boolean)),
      decisionDetails.length
        ? el("div", { class: "teacher-ocr-evidence", text: decisionDetails.join(" · ") })
        : null,
      el("div", { class: "teacher-ocr-editor" }, [
        el("label", { text: "处理决定" }, [decisionSelect]),
        el("label", { text: "证据引用" }, [evidenceInput]),
        el("label", { text: "备注" }, [noteInput]),
        saveButton,
      ]),
    ]);
  }));
}

async function loadOCRReviewQueue() {
  const requestId = ++ocrReviewState.requestId;
  const course = $("#teacher-course").value;
  const params = new URLSearchParams();
  if (course) params.set("course_id", course);
  try {
    const payload = await api(`/api/v1/knowledge/ocr-review-queue?${params.toString()}`);
    if (requestId !== ocrReviewState.requestId) return;
    renderOCRReviewQueue(payload);
  } catch (error) {
    if (requestId !== ocrReviewState.requestId) return;
    $("#teacher-ocr-summary").replaceChildren();
    $("#teacher-ocr-review").replaceChildren(
      el("div", { class: "notice failed", text: error.message }),
    );
  }
}

function renderOCRQualitySummary(payload) {
  const summary = payload.summary || {};
  const decisionEvidence = payload.decision_evidence || {};
  const status = payload.audit_status || "unavailable";
  const tone = status === "available" ? "ready" : status === "partial" ? "warning" : "degraded";
  const decisionTone = decisionEvidence.status === "complete_with_evidence"
    ? "ready"
    : decisionEvidence.status === "decision_file_missing" || decisionEvidence.status === "invalid_or_stale"
      ? "failed"
      : "warning";
  const coverage = summary.average_page_coverage_ratio == null
    ? "未观测到覆盖率"
    : `${Math.round(Number(summary.average_page_coverage_ratio) * 100)}% 平均文本覆盖率`;
  $("#teacher-ocr-quality-summary").replaceChildren(
    badge(tone, `审计：${ocrAuditStatusLabels[status] || status}`),
    badge("degraded", `文档数 ${Number(summary.candidate_document_count || 0)}`),
    badge("warning", `候选页 ${Number(summary.candidate_page_count || 0)}`),
    badge("ready", coverage),
    badge(decisionTone, `决策：${teacherStatus(decisionEvidence.status)}`),
    el("span", { class: "teacher-ocr-cache-note", text: `是否执行 OCR：${payload.ocr_execution_performed ? "是" : "否"}` }),
    el("span", { class: "teacher-ocr-cache-note", text: `决策下一步：${decisionEvidence.next_action || "未知"}` }),
  );
  const rows = payload.rows || [];
  if (!rows.length) {
    $("#teacher-ocr-quality").replaceChildren(
      el("p", { class: "empty-state", text: "当前课程没有 OCR 质量证据候选项。" }),
    );
    return;
  }
  $("#teacher-ocr-quality").replaceChildren(...rows.map((item) => {
    const pages = (item.ocr_candidate_pages || []).join(", ") || "未记录";
    const pageCount = item.page_count == null ? "页数未知" : `共 ${item.page_count} 页`;
    const coverageText = item.page_coverage_ratio == null
      ? "未观测到覆盖率"
      : `文本覆盖率 ${Math.round(Number(item.page_coverage_ratio) * 100)}%`;
    return el("div", { class: "teacher-ocr-quality-row" }, [
      el("strong", { text: `${item.course_id || "-"} · ${item.relative_path || item.file_name || "未命名文件"}` }),
      el("span", { text: `${pageCount} · 候选页面：${pages} · ${coverageText}` }),
      el("div", { class: "teacher-ocr-meta" }, [
        badge(item.priority === "high" ? "failed" : "warning", item.priority === "high" ? "高" : item.priority === "medium" ? "中" : "待复核"),
        badge(item.ocr_required ? "warning" : "degraded", `OCR：${teacherStatus(item.ocr_status)}`),
        badge(item.manual_review_required ? "warning" : "ready", item.manual_review_required ? "需要人工复核" : "无需人工标记"),
      ]),
      item.warnings?.length
        ? el("div", { class: "teacher-ocr-evidence", text: item.warnings.join(" · ") })
        : null,
    ]);
  }));
}

async function loadOCRQualitySummary() {
  const requestId = ++ocrQualityState.requestId;
  const course = $("#teacher-course").value;
  const params = new URLSearchParams();
  if (course) params.set("course_id", course);
  try {
    const payload = await api(`/api/v1/knowledge/ocr-quality-summary?${params.toString()}`);
    if (requestId !== ocrQualityState.requestId) return;
    renderOCRQualitySummary(payload);
  } catch (error) {
    if (requestId !== ocrQualityState.requestId) return;
    $("#teacher-ocr-quality-summary").replaceChildren();
    $("#teacher-ocr-quality").replaceChildren(
      el("div", { class: "notice failed", text: error.message }),
    );
  }
}

function bindOCRFilters() {
  const filters = [
    ["#teacher-ocr-action-filter", "action"],
    ["#teacher-ocr-priority-filter", "priority"],
    ["#teacher-ocr-decision-filter", "decision"],
  ];
  filters.forEach(([selector, key]) => {
    $(selector).addEventListener("change", (event) => {
      ocrReviewState[key] = event.currentTarget.value;
      if (ocrReviewState.payload) renderOCRReviewQueue(ocrReviewState.payload);
    });
  });
}

async function saveTeacherAssetReview(item, decisionSelect, evidenceInput, notesInput, button) {
  const reviewer = $("#teacher-error-reviewer").value.trim();
  if (!reviewer) {
    toast("保存错误模板决定前请输入复核人姓名。", "failed");
    return;
  }
  const payload = teacherAssetReviewState.payloads.find(
    (candidate) => candidate.course_id === item.course_id,
  );
  if (!payload) return;
  const evidenceRefs = evidenceInput.value
    .split(/\r?\n|,/)
    .map((value) => value.trim())
    .filter(Boolean);
  const decisions = (payload.items || []).map((row) => {
    const selected = row.proposal_id === item.proposal_id;
    return {
      proposal_id: row.proposal_id,
      decision: selected ? decisionSelect.value : (row.review_decision || "pending"),
      evidence_refs: selected ? evidenceRefs : (row.review_evidence_refs || []),
      notes: selected ? notesInput.value.trim() : (row.review_notes || ""),
    };
  });
  button.disabled = true;
  try {
    const updated = await api(`/api/v1/knowledge/course-asset-review-decisions/${encodeURIComponent(item.course_id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_fingerprint: payload.source_fingerprint,
        reviewer,
        decisions,
      }),
    });
    const nextPayloads = teacherAssetReviewState.payloads.map(
      (candidate) => candidate.course_id === item.course_id ? updated : candidate,
    );
    renderTeacherAssetReviewQueue(nextPayloads);
    await loadCourseReadiness();
    toast("错误模板决定和证据已保存。", "ready");
  } catch (error) {
    toast(error.message, "failed");
  } finally {
    button.disabled = false;
  }
}

function renderTeacherAssetReviewQueue(payloads) {
  teacherAssetReviewState.payloads = payloads;
  const items = payloads.flatMap((payload) => (payload.items || []).map((item) => ({
    ...item,
    course_id: payload.course_id,
  })));
  const unresolvedCount = payloads.reduce(
    (total, payload) => total + (payload.unresolved_signatures_without_proposal || []).length,
    0,
  );
  const p1Count = items.filter((item) => item.priority === "P1").length;
  const pendingCount = items.filter((item) => item.review_decision === "pending").length;
  $("#teacher-error-review-summary").replaceChildren(
    badge("degraded", `候选项 ${items.length}`),
    badge(p1Count ? "failed" : "ready", `P1 ${p1Count}`),
    badge("warning", `待补证据 ${pendingCount}`),
    badge(unresolvedCount ? "failed" : "ready", `未解决 ${unresolvedCount}`),
  );
  if (!items.length) {
    $("#teacher-error-review-queue").replaceChildren(
      el("p", {
        class: "empty-state",
        text: payloads.length ? "当前没有 CT/AE 错误模板复核候选项。" : "请选择 CT 或 AE 查看此队列。",
      }),
    );
    return;
  }
  items.sort((a, b) => `${a.priority}-${a.course_id}-${a.proposal_id}`.localeCompare(`${b.priority}-${b.course_id}-${b.proposal_id}`));
  $("#teacher-error-review-queue").replaceChildren(...items.map((item) => {
    const skills = (item.skill_ids || []).join(", ") || "未映射";
    const problemTypes = (item.problem_types || []).join(", ") || "未映射";
    const decisionSelect = el("select", {
      class: "teacher-asset-review-decision",
      "aria-label": `处理决定：${item.proposal_id}`,
    }, ["pending", "approved", "rejected"].map((value) => el("option", {
      value,
      text: value === "pending" ? "待处理" : value === "approved" ? "通过" : "退回",
    })));
    decisionSelect.value = ["pending", "approved", "rejected"].includes(item.review_decision)
      ? item.review_decision
      : "pending";
    const evidenceInput = el("textarea", {
      class: "teacher-asset-review-editor",
      rows: "2",
      placeholder: "证据引用，每行一条",
      "aria-label": "错误模板证据引用",
    }, (item.review_evidence_refs || []).join("\n"));
    const notesInput = el("textarea", {
      class: "teacher-asset-review-editor",
      rows: "2",
      placeholder: "复核备注",
      "aria-label": "错误模板复核备注",
    }, item.review_notes || "");
    const saveButton = el("button", {
      class: "button secondary teacher-asset-review-save",
      type: "button",
      text: "保存决定",
      onClick: () => saveTeacherAssetReview(
        item,
        decisionSelect,
        evidenceInput,
        notesInput,
        saveButton,
      ),
    });
    const evidence = (item.review_evidence_refs || []).join(" · ") || "未记录";
    const evidenceQuality = teacherStatus(item.review_evidence_quality, "缺失");
    const evidenceKinds = (item.review_evidence_reference_kinds || []).join(", ") || "无";
    const deterministicStatus = item.deterministic_evidence_status || "not_declared";
    const deterministicConflicts = (item.deterministic_conflict_types || []).join(", ") || "未映射";
    const deterministicScope = item.deterministic_evidence_scope || "not_declared";
    const deterministicValidator = item.deterministic_validator_id || "未声明";
    const deterministicSource = item.deterministic_validator_path || "未声明";
    return el("div", { class: "teacher-asset-review-row" }, [
      el("strong", { text: `${item.course_id} · ${item.error_signature}` }),
      el("span", { text: `提案 ${item.proposal_id} · 技能：${skills} · 类型：${problemTypes}` }),
      el("div", { class: "teacher-asset-review-meta" }, [
        badge(item.priority === "P1" ? "failed" : "warning", item.priority),
        badge(item.review_decision === "pending" ? "warning" : "ready", `决定：${item.review_decision === "pending" ? "待处理" : item.review_decision === "approved" ? "通过" : "退回"}`),
        badge(item.runtime_eligible ? "failed" : "ready", item.runtime_eligible ? "可进入运行时" : "不进入运行时"),
        badge(deterministicStatus === "evidence_ready" ? "ready" : "warning", `验证器证据：${teacherStatus(deterministicStatus)}`),
      ]),
      el("div", { class: "teacher-asset-review-evidence", text: `验证器冲突：${deterministicConflicts}` }),
      el("div", { class: "teacher-asset-review-evidence", text: `验证器范围：${deterministicScope} · 来源：${deterministicValidator} · 路径：${deterministicSource}` }),
      el("div", { class: "teacher-asset-review-evidence", text: item.deterministic_evidence_note || "" }),
      el("div", { class: "teacher-asset-review-evidence", text: `证据引用：${evidence} · 质量：${evidenceQuality} · 类型：${evidenceKinds}` }),
      el("div", { class: "teacher-asset-review-controls" }, [
        el("label", { text: "处理决定" }, [decisionSelect]),
        el("label", { text: "证据引用" }, [evidenceInput]),
        el("label", { text: "备注" }, [notesInput]),
        saveButton,
      ]),
    ]);
  }));
}

async function loadTeacherAssetReviewQueue() {
  const course = $("#teacher-course").value;
  if (course === "DE") {
    renderTeacherAssetReviewQueue([]);
    return;
  }
  const courses = course ? [course] : ["CT", "AE"];
  try {
    const payloads = await Promise.all(courses.map((courseId) => api(
      `/api/v1/knowledge/course-asset-review-queue?course_id=${encodeURIComponent(courseId)}`,
    )));
    renderTeacherAssetReviewQueue(payloads);
  } catch (error) {
    $("#teacher-error-review-summary").replaceChildren();
    $("#teacher-error-review-queue").replaceChildren(
      el("div", { class: "notice failed", text: error.message }),
    );
  }
}

const readinessStatusLabels = {
  implemented: "已实现",
  partial: "部分完成",
  pending: "待补充",
  owner_designed_pending: "负责人设计待补",
};

function renderCourseReadiness(payloads) {
  if (!payloads.length) {
    $("#teacher-course-readiness").replaceChildren(
      el("p", { class: "empty-state", text: "请选择 CT 或 AE 查看就绪度。" }),
    );
    return;
  }
  $("#teacher-course-readiness").replaceChildren(...payloads.map((payload) => {
    const blockers = payload.blockers || [];
    const queue = payload.teacher_review_queue || {};
    const teacherReviewEvidence = payload.teacher_review_evidence || {};
    const deterministicReady = Number(teacherReviewEvidence.deterministic_evidence_ready_count || 0);
    const deterministicTotal = Number(teacherReviewEvidence.item_count || 0);
    const deterministicScopes = Object.entries(teacherReviewEvidence.deterministic_evidence_scope_counts || {})
      .map(([scope, count]) => `${scope}: ${count}`)
      .join(", ") || "未声明";
    const readinessItems = payload.readiness_items || [];
    const evidenceChecks = payload.evidence_checks || [];
    const knowledgeInventory = payload.knowledge_inventory || {};
    const ocrDecisionEvidence = payload.ocr_decision_evidence || {};
    const evaluationProvenance = payload.evaluation_provenance || {};
    const evaluationConsistency = evaluationProvenance.consistency || {};
    const evaluationAge = evaluationProvenance.report_age_seconds == null
      ? "unavailable"
      : `${Math.round(Number(evaluationProvenance.report_age_seconds) / 3600)}h`;
    const evaluationRate = evaluationProvenance.course_pass_rate == null
      ? "unavailable"
      : `${Math.round(Number(evaluationProvenance.course_pass_rate) * 100)}%`;
    const ocrCoverage = knowledgeInventory.ocr_metadata_coverage_ratio == null
      ? "unavailable"
      : `${Math.round(Number(knowledgeInventory.ocr_metadata_coverage_ratio) * 100)}%`;
    const boundaryEntries = Object.entries(payload.boundaries || {});
    const boundaryText = boundaryEntries.length
      ? boundaryEntries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ")
      : "未声明";
    return el("article", { class: "teacher-readiness-card" }, [
      el("div", {
        class: "teacher-readiness-ocr",
        text: `OCR 决策证据：${teacherStatus(ocrDecisionEvidence.status, "未附加")} · 候选项：${Number(ocrDecisionEvidence.candidate_count || 0)} · 缺少引用：${Number(ocrDecisionEvidence.rows_missing_evidence_refs || 0)}`,
      }),
      el("div", {
        class: "teacher-readiness-evaluation",
        text: `离线评测来源：${teacherStatus(evaluationProvenance.status, "未附加")} · 案例数：${Number(evaluationProvenance.course_case_count || 0)} · 通过率：${evaluationRate} · 一致性：${teacherStatus(evaluationConsistency.status, "无法检查")} · 报告时效：${evaluationAge}`,
      }),
      el("div", { class: "teacher-readiness-heading" }, [
      el("strong", { text: payload.course_id || "未知课程" }),
        badge(
          payload.status === "ready" ? "ready" : payload.status === "unavailable" ? "failed" : "warning",
          payload.status === "ready" ? "已就绪" : payload.status === "unavailable" ? "不可用" : "证据待补",
        ),
      ]),
      el("span", { text: `课程包：${teacherStatus(payload.runtime_course_pack_status)} · 运行时已加载：${payload.runtime_loaded ? "是" : "否"}` }),
      el("div", { class: "teacher-readiness-items" }, readinessItems.map((item) => (
        el("span", { text: `${item.key}: ${readinessStatusLabels[item.status] || item.status}` })
      ))),
      el("div", { class: "teacher-readiness-evidence" }, evidenceChecks.map((item) => (
        el("span", { text: `${item.key}：${teacherStatus(item.evidence_status)} · 观测状态：${teacherStatus(item.observed_status)}` })
      ))),
      el("div", { class: "teacher-readiness-knowledge", text: `知识清单：${Number(knowledgeInventory.document_count || 0)} 份文档 · 质量问题：${Number(knowledgeInventory.quality_issue_count || 0)} · OCR 元数据：${ocrCoverage}（${knowledgeInventory.ocr_status || "未知"}）` }),
      el("div", { class: "teacher-readiness-boundaries", text: `边界 · ${boundaryText}` }),
      el("div", { class: "teacher-readiness-queue", text: `错误模板复核队列：${Number(queue.item_count || 0)} 个候选项 · 未解决提案：${(queue.unresolved_signatures_without_proposal || []).length}` }),
      el("div", { class: "teacher-readiness-queue", text: `教师证据质量：${teacherStatus(teacherReviewEvidence.status, "不可用")} · 缺少：${Number(teacherReviewEvidence.missing_count || 0)} · 无法追溯：${Number(teacherReviewEvidence.untraceable_count || 0)}` }),
      el("div", { class: "teacher-readiness-queue", text: `验证器证据：${teacherStatus(teacherReviewEvidence.deterministic_evidence_status, "不可用")} · 已就绪：${deterministicReady}/${deterministicTotal} · 范围：${deterministicScopes}` }),
      el("div", { class: "teacher-readiness-blockers" }, blockers.length
        ? blockers.map((item) => el("div", { class: "teacher-readiness-blocker", text: `${item.code}: ${item.message}` }))
        : [el("div", { class: "teacher-readiness-clear", text: "未记录阻塞项。" })]),
      payload.next_actions?.length
        ? el("div", { class: "teacher-readiness-actions", text: `下一步：${payload.next_actions.join(" · ")}` })
        : null,
    ]);
  }));
}

async function loadCourseReadiness() {
  const course = $("#teacher-course").value;
  if (course === "DE") {
    renderCourseReadiness([]);
    return;
  }
  const courses = course ? [course] : ["CT", "AE"];
  try {
    const payloads = await Promise.all(courses.map((courseId) => api(
      `/api/v1/knowledge/course-asset-readiness?course_id=${encodeURIComponent(courseId)}`,
    )));
    renderCourseReadiness(payloads);
  } catch (error) {
    $("#teacher-course-readiness").replaceChildren(
      el("div", { class: "notice failed", text: error.message }),
    );
  }
}

async function loadMetrics() {
  if (!feedbackEnabled) {
    $("#teacher-metrics").replaceChildren(el("div", { class: "notice warning", text: "反馈闭环已关闭，当前不读取反馈指标。" }));
    $("#teacher-feedback-distribution").replaceChildren();
    $("#teacher-verification-distribution").replaceChildren();
    $("#teacher-warnings").replaceChildren();
    return;
  }
  const params = new URLSearchParams();
  const course = $("#teacher-course").value;
  if (course) params.set("course_id", course);
  params.set("window_start", isoWindowValue($("#teacher-window-start").value));
  params.set("window_end", isoWindowValue($("#teacher-window-end").value));
  $("#teacher-notice").replaceChildren();
  try {
    const data = await api(`/api/v1/learning/metrics?${params.toString()}`);
    renderMetrics(data);
    if (data.truncated) $("#teacher-notice").replaceChildren(el("div", { class: "notice warning", text: "当前结果达到读取上限，仅适合作为窗口概览。" }));
  } catch (error) {
    $("#teacher-metrics").replaceChildren(el("div", { class: "notice failed", text: error.message }));
    $("#teacher-feedback-distribution").replaceChildren();
    $("#teacher-verification-distribution").replaceChildren();
    $("#teacher-warnings").replaceChildren();
  }
}

async function loadFeedbackFeatureStatus() {
  try {
    const status = await api("/api/v1/feedback/status");
    feedbackEnabled = status.enabled === true;
  } catch (_error) {
    feedbackEnabled = true;
  }
  $("#teacher-feedback-panel").hidden = !feedbackEnabled;
}

async function loadDashboard() {
  await loadFeedbackFeatureStatus();
  await Promise.all([
    loadMetrics(),
    loadMaterials(),
    loadOCRReviewQueue(),
    loadOCRQualitySummary(),
    loadTeacherAssetReviewQueue(),
    loadCourseReadiness(),
  ]);
}

async function bootstrap() {
  try {
    const identity = await api("/api/v1/auth/me");
    $("#teacher-identity").textContent = identity.display_name || identity.login || "本地工作台";
  } catch (_error) {
    $("#teacher-identity").textContent = "本地工作台";
  }
  await loadDashboard();
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "teacher", title: "教师工作台", description: "学习反馈与复核指标" });
  setDefaultWindow();
  bindOCRFilters();
  $("#teacher-course").addEventListener("change", () => {
    loadOCRReviewQueue().catch((error) => toast(error.message, "failed"));
    loadOCRQualitySummary().catch((error) => toast(error.message, "failed"));
    loadTeacherAssetReviewQueue().catch((error) => toast(error.message, "failed"));
    loadCourseReadiness().catch((error) => toast(error.message, "failed"));
  });
  $("#teacher-metrics-filter").addEventListener("submit", (event) => { event.preventDefault(); loadDashboard(); });
  $("#teacher-refresh").addEventListener("click", () => loadDashboard().catch((error) => toast(error.message, "failed")));
  bootstrap();
});
