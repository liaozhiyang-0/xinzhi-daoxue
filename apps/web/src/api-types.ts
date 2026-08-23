/*
 * GENERATED FILE — do not edit by hand.
 * Run: python scripts/generate_openapi_types.py
 * Source: exported OpenAPI 3 schema (docs/api/openapi.json).
 */

/* eslint-disable */

export type AccountRead = {
  id: string;
  login: string;
  display_name: string;
  role: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
  [key: string]: unknown;
};

export type AdminAccountCreate = {
  login: string;
  password: string;
  display_name?: string;
  role?: "student" | "teacher" | "researcher" | "operator" | "admin";
  [key: string]: unknown;
};

export type AdminAccountRead = {
  id: string;
  login: string;
  display_name: string;
  role: string;
  status: string;
  failed_login_attempts: number;
  locked_until: string | null;
  last_login_at: string | null;
  password_changed_at: string;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

export type AdminAccountUpdate = {
  display_name?: string | null;
  role?: "student" | "teacher" | "researcher" | "operator" | "admin" | null;
  status?: "active" | "disabled" | "locked" | null;
  [key: string]: unknown;
};

export type AdminEvaluationAttachmentResidueRead = {
  purpose: string;
  as_of: string;
  grace_seconds: number;
  cutoff: string;
  total_file_count: number;
  total_bytes: number;
  unbound_file_count: number;
  active_task_file_count: number;
  terminal_task_file_count: number;
  missing_task_file_count: number;
  cleanup_candidate_count: number;
  cleanup_candidate_bytes: number;
  oldest_created_at: string | null;
  [key: string]: unknown;
};

export type AdminFeatureSettingRead = {
  key: string;
  label: string;
  description: string;
  enabled: boolean;
  updated_at: string | null;
  updated_by: string | null;
  [key: string]: unknown;
};

export type AdminFeatureSettingUpdate = {
  enabled: boolean;
  [key: string]: unknown;
};

export type AdminFileSummaryRead = {
  total: number;
  pending: number;
  processing: number;
  ready: number;
  partial: number;
  failed: number;
  total_bytes: number;
  [key: string]: unknown;
};

export type AdminOverviewRead = {
  account_count: number;
  active_account_count: number;
  disabled_account_count: number;
  locked_account_count: number;
  active_session_count: number;
  audit_event_count: number;
  [key: string]: unknown;
};

export type AdminPasswordReset = {
  password: string;
  [key: string]: unknown;
};

export type AdminSessionRead = {
  id: string;
  account_id: string;
  login: string;
  access_expires_at: string;
  refresh_expires_at: string;
  revoked_at: string | null;
  last_seen_at: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  [key: string]: unknown;
};

export type AdminTaskObservabilityRead = {
  version?: string;
  data_source?: string;
  window_start: string;
  window_end: string;
  row_limit: number;
  truncated?: boolean;
  task_count: number;
  status_counts?: {
  [key: string]: number;
};
  failure_category_counts?: {
  [key: string]: number;
};
  provider_counts?: {
  [key: string]: number;
};
  route_status_counts?: {
  [key: string]: number;
};
  cancellation_requested_count?: number;
  measured_total_latency_count?: number;
  average_total_latency_ms?: number | null;
  p50_total_latency_ms?: number | null;
  p95_total_latency_ms?: number | null;
  measured_queue_latency_count?: number;
  average_queue_latency_ms?: number | null;
  p50_queue_latency_ms?: number | null;
  p95_queue_latency_ms?: number | null;
  data_quality_warnings?: string[];
  [key: string]: unknown;
};

export type AdminTaskSummaryRead = {
  total: number;
  active: number;
  completed: number;
  failed: number;
  status_counts: {
  [key: string]: number;
};
  failure_category_counts?: {
  [key: string]: number;
};
  provider_counts?: {
  [key: string]: number;
};
  route_status_counts?: {
  [key: string]: number;
};
  cancellation_requested_count?: number;
  [key: string]: unknown;
};

export type AgentDebugRequest = {
  question?: string;
  course_id?: string;
  intent?: Intent;
  canonical_input?: {
  [key: string]: unknown;
};
  options?: {
  [key: string]: unknown;
};
  allow_mock?: boolean;
  [key: string]: unknown;
};

export type AgentDryRunRequest = {
  question?: string;
  course_id?: string;
  intent?: Intent;
  retrieved_context?: string;
  options?: {
  [key: string]: unknown;
};
  [key: string]: unknown;
};

export type AgentRequest = {
  task_id?: string;
  session_id: string;
  user_id: string;
  user_role?: UserRole;
  scene?: Scene;
  course_id?: string;
  intent?: Intent;
  scenario_id?: string | null;
  canonical_input?: {
  [key: string]: unknown;
};
  attachments?: AttachmentRef[];
  context_refs?: string[];
  options?: {
  [key: string]: unknown;
};
  response_depth?: ResponseDepth;
};

export type AgentRequestV2 = {
  request_id?: string;
  session_id?: string | null;
  user_id?: string | null;
  message?: string;
  input_type?: InputType;
  files?: FileReference[];
  course_hint?: CourseCode | null;
  intent_hint?: OrchestrationIntent | null;
  scenario_id?: string | null;
  previous_answer_summary?: string | null;
  metadata?: {
  [key: string]: unknown;
};
  debug?: boolean;
};

export type AgentResponse = {
  request_id: string;
  session_id: string;
  status: ExecutionStatus;
  agent_id: string;
  course: CourseCode;
  intent: OrchestrationIntent;
  answer_text: string;
  math_content?: MathRichContent | null;
  structured_result?: {
  [key: string]: unknown;
};
  citations?: Citation[];
  assumptions?: string[];
  warnings?: string[];
  confidence?: number;
  trace_id: string;
  elapsed_ms: number;
};

export type AgentRunPlan = {
  plan_id: string;
  version?: string;
  goal: string;
  goal_contract?: RuntimeGoal | null;
  nodes: RuntimeNode[];
  success_criteria?: string[];
  max_parallelism?: number;
};

export type AnalyticsReportRead = {
  version?: string;
  data_source?: string;
  window_start: string;
  window_end: string;
  filters?: {
  [key: string]: string | null;
};
  row_limit: number;
  truncated?: boolean;
  metrics?: {
  [key: string]: number | string | null;
};
  breakdowns?: {
  [key: string]: {
  [key: string]: number | null;
} | {
  [key: string]: unknown;
}[];
};
  definitions?: {
  [key: string]: string;
};
  data_quality_warnings?: string[];
  [key: string]: unknown;
};

export type AnswerReviewResult = {
  status: "correct" | "partially_correct" | "incorrect" | "insufficient";
  aligned_steps?: {
  [key: string]: unknown;
}[];
  first_error?: {
  [key: string]: unknown;
} | null;
  error_types?: string[];
  feedback?: string[];
  mastery_delta: number;
};

export type ArtifactRead = {
  id: string;
  task_id: string;
  artifact_type: string;
  version: string;
  content: {
  [key: string]: unknown;
};
  confidence: number | null;
  created_at: string;
  [key: string]: unknown;
};

export type AttachmentRef = {
  file_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  provider_file_id?: string | null;
  checksum_sha256?: string | null;
  ingestion_status?: string;
  page_count?: number;
  extracted_text?: string;
  extraction_metadata?: {
  [key: string]: unknown;
};
};

export type AuditLogRead = {
  id: string;
  actor_account_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  details: {
  [key: string]: unknown;
};
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  [key: string]: unknown;
};

export type AuthMeRead = {
  id: string;
  login: string;
  display_name: string;
  role: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
  session_id: string;
  access_expires_at: string;
  [key: string]: unknown;
};

export type AuthSessionRead = {
  account: AccountRead;
  token_type?: string;
  access_expires_at: string;
  refresh_expires_at: string;
  [key: string]: unknown;
};

export type Body_upload_file_api_v1_files_post = {
  upload: string;
  task_id?: string | null;
  purpose?: string;
  course_id?: string | null;
  material_key?: string | null;
  material_version?: string | null;
  [key: string]: unknown;
};

export type ChatSubmission = {
  request_id: string;
  session_id: string;
  task_id: string;
  trace_id: string;
  scenario_id?: string | null;
  status?: string;
  stream_url: string;
  result_url: string;
};

export type Citation = {
  citation_id: string;
  filename: string;
  chapter?: string;
  page_number?: number | null;
  chunk_id?: string;
  source_ref: string;
  title?: string;
  score?: number | null;
};

export type CommercializationPlan = {
  buyer: string;
  delivery_unit: string;
  value_capture: string;
  expansion_path: string;
};

export type CompareRequest = {
  question: string;
  course_id?: "CT" | "AE" | "DE" | "SS" | "DSP" | "COMM";
  intent?: "general_qa" | "explain_concept" | "summarize_knowledge" | "learning_advice" | "solve_problem";
  response_depth?: "brief" | "standard" | "deep";
  conversation_summary?: string;
  previous_answer_summary?: string;
  use_rag?: boolean;
  include_images?: boolean;
  use_reranker?: boolean;
  request_id?: string;
  comparison_mode?: string;
};

export type ConversationMessage = {
  message_id: string;
  session_id: string;
  user_id: string;
  sequence: number;
  role: MessageRole;
  status: MessageStatus;
  visibility: MessageVisibility;
  content_text: string;
  content_data?: {
  [key: string]: unknown;
};
  source_task_id?: string | null;
  reply_to_message_id?: string | null;
  revision_of_message_id?: string | null;
  origin_message_id?: string | null;
  attachment_ids?: string[];
  created_at: string;
  updated_at: string;
  metadata?: {
  [key: string]: unknown;
};
  [key: string]: unknown;
};

export type CourseAssetEvidenceCheckRead = {
  key: string;
  declared_status: string;
  observed_status: string;
  evidence_status: string;
  evidence_paths?: string[];
  evidence_present: boolean;
};

export type CourseAssetReadinessItemRead = {
  key: string;
  status: string;
  source_ref: string;
};

export type CourseAssetReadinessRead = {
  schema_version: string;
  course_id: string;
  status: "ready" | "evidence_pending" | "unavailable";
  runtime_course_pack_status: string;
  runtime_loaded: boolean;
  runtime_source: string | null;
  frozen_fallback_reference: string | null;
  boundaries?: {
  [key: string]: unknown;
};
  readiness_items?: CourseAssetReadinessItemRead[];
  evidence_checks?: CourseAssetEvidenceCheckRead[];
  knowledge_inventory: CourseKnowledgeInventoryRead;
  ocr_decision_evidence?: KnowledgeOCRDecisionEvidenceRead | null;
  evaluation_provenance?: CourseEvaluationProvenanceRead | null;
  source_statuses?: {
  [key: string]: string;
};
  blockers?: {
  [key: string]: string;
}[];
  next_actions?: string[];
  teacher_review_queue?: {
  [key: string]: unknown;
};
  teacher_review_evidence?: {
  [key: string]: unknown;
};
  contest_boundary?: {
  [key: string]: unknown;
};
};

export type CourseCode = "CT" | "AE" | "DE" | "SS" | "DSP" | "COMM" | "RF" | "EM" | "INFO" | "EMBEDDED" | "IC" | "UNKNOWN";

export type CourseEvaluationConsistencyRead = {
  status: "consistent" | "partial" | "inconsistent" | "not_checkable";
  schema_version_supported: boolean;
  summary_result_count_match: boolean;
  summary_status_counts_match: boolean;
  course_statistics_match: boolean;
  metadata_case_count_match: boolean | null;
  metadata_case_ids_match: boolean | null;
  metadata_filters_match: boolean | null;
  case_catalog_present: boolean | null;
  case_catalog_content_present: boolean | null;
  case_source_files_present: boolean | null;
  case_attachment_manifest_present: boolean | null;
  report_completed_at_parseable: boolean;
  report_completed_at_not_future: boolean | null;
  issues?: string[];
};

export type CourseEvaluationProvenanceRead = {
  schema_version: string;
  status: "available" | "report_missing" | "report_invalid" | "course_not_covered";
  course_id: string;
  report_path: string;
  report_present: boolean;
  report_valid: boolean | null;
  report_schema_version: string | null;
  report_mode: string | null;
  started_at: string | null;
  completed_at: string | null;
  report_filters?: {
  [key: string]: unknown;
};
  snapshot_at: string;
  report_age_seconds?: number | null;
  temporal_consistency: "valid" | "invalid" | "future" | "not_checkable";
  report_case_count?: number | null;
  course_case_count: number;
  course_passed_count: number;
  course_pass_rate?: number | null;
  run_metadata_present: boolean;
  run_id: string | null;
  case_ids_sha256: string | null;
  case_catalog_sha256: string | null;
  case_catalog_content_sha256: string | null;
  case_catalog_content_version: string | null;
  case_source_files_sha256: string | null;
  case_source_files_version: string | null;
  case_attachment_manifest_sha256: string | null;
  case_attachment_manifest_version: string | null;
  case_attachment_count?: number | null;
  filters_sha256: string | null;
  implementation_fingerprint: string | null;
  execution_channel: string | null;
  model_trace_retention: string | null;
  raw_prompts_stored: boolean | null;
  raw_results_included?: boolean;
  data_boundary?: string[];
  consistency: CourseEvaluationConsistencyRead;
};

export type CourseKnowledgeInventoryRead = {
  status: "available" | "partial" | "unavailable";
  manifest_present: boolean;
  manifest_path: string;
  document_count: number;
  malformed_manifest_rows: number;
  quality_issues_file_present: boolean;
  quality_issues_file_parseable: boolean;
  quality_issue_count: number;
  quality_issue_type_counts?: {
  [key: string]: number;
};
  quality_status_counts?: {
  [key: string]: number;
};
  parse_status_counts?: {
  [key: string]: number;
};
  rows_with_ocr_metadata: number;
  rows_with_ocr_confidence: number;
  rows_with_manual_review_flag: number;
  ocr_metadata_coverage_ratio?: number | null;
  ocr_status: "available" | "partial" | "unavailable";
};

export type DebugRunRequest = {
  question: string;
  course_id?: "CT" | "AE" | "DE" | "SS" | "DSP" | "COMM";
  intent?: "general_qa" | "explain_concept" | "summarize_knowledge" | "learning_advice" | "solve_problem";
  response_depth?: "brief" | "standard" | "deep";
  conversation_summary?: string;
  previous_answer_summary?: string;
  use_rag?: boolean;
  include_images?: boolean;
  use_reranker?: boolean;
  request_id?: string;
};

export type ErrorPoolReviewDecisionSaveRequest = {
  source_fingerprint: string;
  reviewer: string;
  decisions: ErrorPoolReviewDecisionWrite[];
};

export type ErrorPoolReviewDecisionWrite = {
  proposal_id: string;
  decision: "pending" | "approved" | "rejected";
  evidence_refs?: string[];
  notes?: string;
};

export type EvalRequest = {
  group?: "all" | "CT" | "AE" | "DE" | "SS" | "DSP" | "COMM" | "boundary" | "degradation";
  limit?: number;
  [key: string]: unknown;
};

export type EvaluationReportSummary = {
  version?: string;
  report_kind?: string;
  schema_version: string;
  mode: "offline" | "live" | "local_deterministic" | "local_mock" | "real_model";
  started_at: string;
  completed_at: string;
  filters?: {
  [key: string]: unknown;
};
  summary: {
  [key: string]: unknown;
};
  statistics: {
  [key: string]: unknown;
};
  run_metadata: EvaluationRunMetadata;
  result_status_counts?: {
  [key: string]: number;
};
  raw_results_included?: boolean;
  data_boundary?: string[];
};

export type EvaluationRunMetadata = {
  version?: string;
  run_id?: string;
  case_count?: number;
  case_ids_sha256?: string;
  case_catalog_sha256?: string;
  case_catalog_content_sha256?: string;
  case_catalog_content_version?: string | null;
  case_source_files_sha256?: string;
  case_source_files_version?: string | null;
  case_attachment_manifest_sha256?: string;
  case_attachment_manifest_version?: string | null;
  case_attachment_count?: number;
  filters_sha256?: string;
  implementation_fingerprint?: string;
  execution_channel?: string;
  model_trace_retention?: string;
  raw_prompts_stored?: boolean;
};

export type EventRead = {
  id: string;
  task_id: string;
  sequence: number;
  event_type: string;
  event_data: {
  [key: string]: unknown;
};
  created_at: string;
  [key: string]: unknown;
};

export type ExecutionMode = "local" | "disabled";

export type ExecutionStatus = "success" | "partial" | "failed" | "skipped" | "timeout" | "fallback";

export type FeedbackCreate = {
  task_id: string;
  resolved?: boolean | null;
  satisfaction?: FeedbackSatisfaction | null;
  problem_type?: string | null;
  manual_review_required?: boolean;
  comment?: string;
};

export type FeedbackFeatureStatusRead = {
  key?: string;
  enabled: boolean;
  [key: string]: unknown;
};

export type FeedbackMetricsRead = {
  version?: string;
  course_id?: string | null;
  window_start: string;
  window_end: string;
  data_source?: string;
  task_count: number;
  task_status_counts?: {
  [key: string]: number;
};
  completed_task_count: number;
  failed_task_count: number;
  task_completion_rate?: number | null;
  average_latency_ms?: number | null;
  unique_user_count: number;
  repeat_user_rate?: number | null;
  feedback_count: number;
  feedback_response_rate?: number | null;
  satisfaction_counts?: {
  [key: string]: number;
};
  resolved_count: number;
  resolved_rate?: number | null;
  manual_review_request_count: number;
  problem_type_counts?: {
  [key: string]: number;
};
  user_role_counts?: {
  [key: string]: number;
};
  task_type_counts?: {
  [key: string]: number;
};
  average_citation_coverage?: number | null;
  row_limit: number;
  truncated?: boolean;
  data_quality_warnings?: string[];
};

export type FeedbackRead = {
  id: string;
  task_id: string;
  user_role: string;
  course_id: string;
  task_type: string;
  agent_id: string;
  agent_version: string | null;
  provider: string;
  model_version: string | null;
  rag_version: string | null;
  retrieval_mode: string | null;
  resolved: boolean | null;
  satisfaction: FeedbackSatisfaction | null;
  problem_type: string | null;
  manual_review_required: boolean;
  citation_coverage?: number | null;
  latency_ms?: number | null;
  comment: string | null;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

export type FeedbackSatisfaction = "satisfied" | "unsatisfied" | "neutral";

export type FeedbackUptakeStatus = "applied_correctly" | "applied_incorrectly" | "partially_applied" | "not_applied" | "indeterminate" | "not_applicable";

export type FeedbackUptakeV1 = {
  version?: string;
  user_id: string;
  session_id: string;
  source_task_id: string;
  previous_attempt_id: string;
  current_attempt_id: string;
  hint_level: string | null;
  hint_source: string | null;
  target_step_id: string | null;
  target_skill_ids?: string[];
  student_modified: boolean;
  modified_step_ids?: string[];
  target_step_modified: boolean;
  previous_verification_status: string | null;
  current_verification_status: string | null;
  status: FeedbackUptakeStatus;
  modification_correct: boolean | null;
  time_to_revision_seconds?: number | null;
  evaluation_method: string;
  confidence?: number | null;
  warnings?: string[];
};

export type FileChunkRead = {
  id: string;
  file_id: string;
  ordinal: number;
  page_number: number | null;
  section: string;
  content: string;
  char_start: number;
  char_end: number;
  source_ref: string;
  created_at: string;
  [key: string]: unknown;
};

export type FileRead = {
  id: string;
  task_id: string | null;
  filename: string;
  course_id?: string | null;
  material_key?: string | null;
  material_version?: string | null;
  knowledge_status?: string;
  knowledge_index_status?: string;
  knowledge_published_by?: string | null;
  knowledge_published_at?: string | null;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  checksum_sha256: string;
  detected_content_type: string;
  ingestion_status: string;
  page_count: number;
  extracted_text: string;
  extraction_metadata: {
  [key: string]: unknown;
};
  extraction_error: string | null;
  extraction_version: string;
  extraction_started_at: string | null;
  extraction_completed_at: string | null;
  created_at: string;
  [key: string]: unknown;
};

export type FileReference = {
  file_id: string;
  filename?: string;
  content_type?: string;
  size_bytes?: number;
  resource_id?: string | null;
  page_numbers?: number[];
  metadata?: {
  [key: string]: unknown;
};
};

export type ForgetRequest = {
  user_id: string;
  query?: string;
  all_memories?: boolean;
  [key: string]: unknown;
};

export type GuestSessionRead = {
  guest?: boolean;
  user_id: string;
  display_name?: string;
  role?: string;
  expires_at: string;
  [key: string]: unknown;
};

export type HTTPValidationError = {
  detail?: ValidationError[];
  [key: string]: unknown;
};

export type HealthRead = {
  status: string;
  environment: string;
  database: string;
  redis: string;
  minio: string;
  requested_provider: string;
  active_provider: string;
  provider_mode: string;
  version: string;
  runtime_identity?: {
  [key: string]: unknown;
};
  configuration_status?: string;
  configuration_warnings?: string[];
  model_runtime?: {
  [key: string]: unknown;
};
  external_retrieval?: {
  [key: string]: unknown;
};
  task_queue?: {
  [key: string]: unknown;
};
  [key: string]: unknown;
};

export type InputType = "text" | "image" | "pdf" | "mixed";

export type Intent = "unknown" | "follow_up_question" | "solve_problem" | "explain_concept" | "verify_answer" | "check_user_solution" | "general_qa" | "summarize_knowledge" | "learning_advice" | "check_simple_step" | "lesson_prep" | "assignment_review" | "academic_writing" | "data_analysis" | "academic_search";

export type KnowledgeCourseId = "CT" | "AE" | "DE" | "SS" | "DSP" | "COMM";

export type KnowledgeDocumentPage = {
  source_ref: string;
  course_id: string;
  relative_path: string;
  requested_chunk?: string;
  content: string;
  total_chars: number;
  start_offset: number;
  end_offset: number;
  previous_offset?: number | null;
  next_offset?: number | null;
  anchor_status: "matched" | "not_found" | "not_requested";
};

export type KnowledgeEvidencePolicy = {
  authoritative_source_types: string[];
  supplemental_source_types?: string[];
  citation_required?: boolean;
  manual_review_required?: boolean;
  allow_synthetic?: boolean;
  freshness_days?: number | null;
};

export type KnowledgeHit = {
  chunk_id?: string;
  evidence_id?: string;
  document_id?: string;
  course_id: KnowledgeCourseId;
  course_name: string;
  chapter?: string;
  section?: string;
  document_path: string;
  title: string;
  content_type?: string;
  content: string;
  score: number;
  score_components?: {
  [key: string]: number;
};
  source_ref: string;
  document_checksum?: string;
  related_images?: RelatedImage[];
};

export type KnowledgeMaterialManifestRead = {
  manifest_filename: string;
  chunk_filename: string;
  generated_at: string;
  material_count: number;
  chunk_count: number;
  course_ids?: string[];
};

export type KnowledgeMaterialRead = {
  file_id: string;
  filename: string;
  owner_user_id: string | null;
  course_id: string;
  material_key: string;
  material_version: string;
  checksum_sha256: string;
  ingestion_status: string;
  knowledge_status: string;
  knowledge_index_status: string;
  page_count: number;
  chunk_count: number;
  extraction_version: string;
  quality_status?: string;
  ocr_required?: boolean;
  manual_review_required?: boolean;
  ocr_candidate_pages?: number[];
  quality_warnings?: string[];
  material_review_status?: string;
  material_reviewed_by?: string | null;
  material_reviewed_at?: string | null;
  material_review_note?: string | null;
  knowledge_published_by: string | null;
  knowledge_published_at: string | null;
  created_at: string;
  [key: string]: unknown;
};

export type KnowledgeMaterialReviewRequest = {
  status: "approved" | "rejected";
  note?: string;
};

export type KnowledgeMaterialStatus = "draft" | "published" | "superseded" | "withdrawn";

export type KnowledgeOCRDecisionEvidenceRead = {
  status: "decision_file_missing" | "pending" | "complete_with_evidence" | "complete_without_evidence" | "invalid_or_stale";
  decision_file_present: boolean;
  report_valid: boolean | null;
  review_complete: boolean;
  candidate_count: number;
  decided_count: number;
  pending_count: number;
  rows_missing_evidence_refs: number;
  stale_checksum_error_count: number;
  validation_error_count: number;
  next_action: string;
};

export type KnowledgeOCRDecisionSaveRequest = {
  source_fingerprint?: string;
  reviewer: string;
  decisions: KnowledgeOCRDecisionWrite[];
};

export type KnowledgeOCRDecisionWrite = {
  queue_id: string;
  checksum: string;
  decision: "pending" | "approve_existing_text" | "request_ocr" | "split_pdf" | "reject_source" | "needs_manual_inspection";
  evidence_refs?: string[];
  note?: string;
};

export type KnowledgeOCRQualityDocumentRead = {
  queue_id: string;
  course_id: string;
  document_id: string;
  relative_path: string;
  file_name: string;
  page_count?: number | null;
  parse_status: string;
  quality_status: string;
  index_status: string;
  ocr_required: boolean;
  ocr_status: string;
  ocr_candidate_pages?: number[];
  candidate_page_count: number;
  low_text_page_count: number;
  page_coverage_ratio?: number | null;
  manual_review_required: boolean;
  warnings?: string[];
  priority: string;
  review_action: string;
  review_decision: string;
};

export type KnowledgeOCRQualitySummaryRead = {
  schema_version: string;
  course_id: string;
  mode: string;
  runtime_loaded: boolean;
  ocr_execution_performed: boolean;
  audit_status: "available" | "partial" | "unavailable";
  decision_evidence: KnowledgeOCRDecisionEvidenceRead;
  summary?: {
  [key: string]: unknown;
};
  rows?: KnowledgeOCRQualityDocumentRead[];
  cache_status?: string;
  cache_backend?: string;
  source_fingerprint?: string;
  snapshot_age_seconds?: number;
};

export type KnowledgeOCRReviewQueueRead = {
  schema_version: string;
  generated_at: string;
  mode: string;
  runtime_loaded: boolean;
  ocr_execution_performed: boolean;
  summary?: {
  [key: string]: unknown;
};
  rows?: {
  [key: string]: unknown;
}[];
  decision_reports?: {
  [key: string]: {
  [key: string]: unknown;
};
};
  cache_status?: string;
  cache_backend?: string;
  source_fingerprint?: string;
  snapshot_age_seconds?: number;
};

export type KnowledgeSearchRequest = {
  query: string;
  course_ids?: KnowledgeCourseId[];
  top_k?: number;
};

export type KnowledgeSearchResponse = {
  query: string;
  hits?: KnowledgeHit[];
  sources?: KnowledgeSourceStatus[];
};

export type KnowledgeSourceStatus = {
  course_id: KnowledgeCourseId;
  course_name: string;
  available: boolean;
  document_count: number;
  chunk_count: number;
  indexed_at?: string | null;
  message?: string | null;
};

export type LearnerKnowledgeState = {
  course_id: string;
  knowledge_point: string;
  mastery_score: number;
  confidence: number;
  correct_count: number;
  incorrect_count: number;
  hint_count: number;
};

export type LearningActionRequest = {
  source_task_id: string;
  user_id: string;
  action: "add_wrong_answer" | "get_hint" | "check_answer" | "generate_variant" | "related_knowledge" | "mark_mastered" | "request_more_hint" | "submit_check_response" | "switch_to_direct_answer" | "submit_attempt_revision" | "start_retest" | "complete_retest" | "dismiss_retest";
  idempotency_key: string;
  student_answer?: string;
  payload?: {
  [key: string]: unknown;
};
};

export type LearningActionResponse = {
  interaction_id: string;
  action: "add_wrong_answer" | "get_hint" | "check_answer" | "generate_variant" | "related_knowledge" | "mark_mastered" | "request_more_hint" | "submit_check_response" | "switch_to_direct_answer" | "submit_attempt_revision" | "start_retest" | "complete_retest" | "dismiss_retest";
  status: "completed" | "accepted" | "needs_task";
  message: string;
  follow_up_prompt?: string;
  follow_up_context?: LearningFollowUpContext | null;
  review?: AnswerReviewResult | null;
  practice?: PracticeProblem | null;
  mastery?: LearnerKnowledgeState[];
  teaching?: {
  [key: string]: unknown;
};
  attempt?: StudentAttemptV2 | null;
  feedback_uptake?: FeedbackUptakeV1 | null;
  mastery_evidence?: MasteryEvidenceV1[];
  retest_plans?: RetestPlanV1[];
  runtime_run_id?: string | null;
  runtime_status?: string;
  approval_required?: boolean;
};

export type LearningFollowUpContext = {
  source_task_id: string;
  course_id: string;
  intent: string;
  action: "add_wrong_answer" | "get_hint" | "check_answer" | "generate_variant" | "related_knowledge" | "mark_mastered" | "request_more_hint" | "submit_check_response" | "switch_to_direct_answer" | "submit_attempt_revision" | "start_retest" | "complete_retest" | "dismiss_retest";
};

export type LearningMetricsRead = {
  version?: string;
  course_id?: string | null;
  window_start: string;
  window_end: string;
  data_source?: string;
  attempt_count: number;
  attempt_status_counts?: {
  [key: string]: number;
};
  verification_status_counts?: {
  [key: string]: number;
};
  manual_review_count: number;
  feedback_uptake_event_count: number;
  feedback_uptake_status_counts?: {
  [key: string]: number;
};
  feedback_uptake_determinate_count: number;
  feedback_uptake_determinate_rate?: number | null;
  feedback_uptake_applied_correctly_count: number;
  feedback_uptake_correct_rate?: number | null;
  retest_count: number;
  retest_status_counts?: {
  [key: string]: number;
};
  row_limit: number;
  truncated?: boolean;
  data_quality_warnings?: string[];
  [key: string]: unknown;
};

export type LearningRuntimeApprovalRequest = {
  expected_state_version?: number | null;
};

export type LearningRuntimeCapabilityRead = {
  capability_id: string;
  domain?: string;
  runtime_id: string;
  version: string;
  agent_version?: string;
  runtime_plan_version?: string;
  structural_release_eligible?: boolean;
  semantic_release_eligible?: boolean;
  canary_release_eligible?: boolean;
  canary_reason?: string;
  enabled: boolean;
  supported_actions?: string[];
  supports_pause?: boolean;
  supports_resume?: boolean;
  supports_approval?: boolean;
  supports_input?: boolean;
  control_scope: string;
  result_contract: string;
  blockers?: string[];
};

export type LearningRuntimeControlProjectionRead = {
  version?: string;
  provider_called?: boolean;
  run_id: string;
  runtime_id: string;
  run_kind: "teaching_interaction" | "learning_progress";
  status: string;
  state_version: number;
  control_scope?: string;
  controls?: LearningRuntimeControlRead[];
  available_controls?: "approve" | "pause" | "resume" | "input"[];
};

export type LearningRuntimeControlRead = {
  action: "approve" | "pause" | "resume" | "input";
  available: boolean;
  reason_code?: string;
  reason?: string;
};

export type LearningRuntimeControlRequest = {
  action: "approve" | "pause" | "resume" | "input";
  expected_state_version?: number | null;
  data?: {
  [key: string]: unknown;
};
  idempotency_key?: string;
};

export type LearningRuntimeControlResultRead = {
  version?: string;
  provider_called?: boolean;
  run_id: string;
  action: "approve" | "pause" | "resume" | "input";
  accepted?: boolean;
  status: string;
  state_version: number;
  result?: LearningActionResponse | null;
};

export type LearningRuntimeNodeStatusRead = {
  node_id: string;
  status: string;
  effect_status: string;
  attempt: number;
  error_code?: string;
};

export type LearningRuntimeReadinessRead = {
  version?: string;
  provider_called?: boolean;
  capabilities?: LearningRuntimeCapabilityRead[];
  blockers?: string[];
};

export type LearningRuntimeStatusRead = {
  run_id: string;
  task_id: string;
  runtime_id: string;
  run_kind: "teaching_interaction" | "learning_progress";
  status: string;
  state_version: number;
  goal: string;
  success_criteria?: string[];
  required_capabilities?: string[];
  goal_source?: string;
  node_statuses?: LearningRuntimeNodeStatusRead[];
  control_scope?: string;
  available_controls?: "approve" | "pause" | "resume" | "input"[];
  approval_required?: boolean;
  resumable?: boolean;
};

export type LoginRequest = {
  login: string;
  password: string;
  [key: string]: unknown;
};

export type MasteryEvidenceType = "independent_correct" | "h0_h1_correct" | "h2_correct" | "full_solution_seen" | "feedback_applied_correctly" | "feedback_not_applied" | "verified_error" | "manual_review" | "delayed_retest_correct" | "delayed_retest_incorrect";

export type MasteryEvidenceV1 = {
  evidence_id: string;
  user_id: string;
  skill_id: string;
  source_task_id: string;
  attempt_id: string | null;
  evidence_type: MasteryEvidenceType;
  verified: boolean;
  evidence_strength: number;
  mastery_delta: number;
  reason_code: string;
  created_at: string;
};

export type MathBlockType = "inline" | "display" | "aligned" | "matrix" | "cases" | "equation_system" | "raw_text";

export type MathExpression = {
  expression_id: string;
  latex: string;
  block_type: MathBlockType;
  source_text?: string | null;
  normalized?: boolean;
  validation_status?: string;
  render_status?: string;
  error_code?: string | null;
  variables?: string[];
  warnings?: string[];
  metadata?: {
  [key: string]: unknown;
};
};

export type MathRichContent = {
  plain_text: string;
  markdown: string;
  segments?: RichTextSegment[];
  math_expressions?: MathExpression[];
  warnings?: string[];
};

export type MathSegmentType = "text" | "inline_math" | "display_math" | "code" | "table" | "html";

export type MemoryCreate = {
  user_id: string;
  memory_type?: MemoryType;
  scope?: MemoryScope;
  course_id?: string | null;
  content: string;
  content_data?: {
  [key: string]: unknown;
};
  tags?: string[];
  source_session_id?: string | null;
  source_message_id?: string | null;
  [key: string]: unknown;
};

export type MemoryMutationResult = {
  affected: number;
  message: string;
  [key: string]: unknown;
};

export type MemoryRead = {
  memory_id: string;
  user_id: string;
  memory_type: MemoryType;
  scope: MemoryScope;
  course_id: string | null;
  content: string;
  content_data: {
  [key: string]: unknown;
};
  tags: string[];
  source_session_id: string | null;
  source_message_id: string | null;
  status: MemoryStatus;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revision: number;
  [key: string]: unknown;
};

export type MemoryScope = "global" | "course";

export type MemoryStatus = "candidate" | "active" | "rejected" | "superseded" | "deleted" | "expired";

export type MemoryType = "preference" | "learning_preference" | "stable_profile" | "project_context" | "episodic" | "semantic_learning";

export type MemoryUpdate = {
  user_id: string;
  content?: string | null;
  memory_type?: MemoryType | null;
  scope?: MemoryScope | null;
  course_id?: string | null;
  tags?: string[] | null;
  [key: string]: unknown;
};

export type MessageRole = "user" | "assistant" | "tool" | "system_event";

export type MessageStatus = "pending" | "completed" | "failed" | "cancelled" | "superseded";

export type MessageVisibility = "user_visible" | "developer_only" | "internal";

export type OrchestrationIntent = "solve_problem" | "explain_concept" | "follow_up_question" | "summarize_knowledge" | "learning_advice" | "check_simple_step" | "general_qa" | "lesson_prep" | "assignment_review" | "academic_writing" | "data_analysis" | "academic_search" | "fallback" | "unknown";

export type PracticeProblem = {
  status: "ready" | "unsupported" | "invalid";
  problem_text?: string;
  known_conditions?: {
  [key: string]: unknown;
}[];
  target_quantities?: {
  [key: string]: unknown;
}[];
  reference_answer?: {
  [key: string]: unknown;
};
  validation_checks?: {
  [key: string]: unknown;
}[];
  source_task_id: string;
};

export type PrewarmRequest = {
  models?: "text" | "image" | "reranker"[];
  [key: string]: unknown;
};

export type RAGSearchRequest = {
  query_text?: string;
  course_id: KnowledgeCourseId;
  image_resource_uri?: string | null;
  intent?: string;
  target_agent_id?: string;
  top_k?: number;
  content_types?: string[];
  include_images?: boolean;
  use_reranker?: boolean | null;
};

export type RefreshRequest = {
  refresh_token?: string | null;
  [key: string]: unknown;
};

export type RegisterRequest = {
  login: string;
  password: string;
  display_name?: string;
  [key: string]: unknown;
};

export type RelatedImage = {
  image_id: string;
  resource_uri: string;
  caption?: string;
  description_source?: string;
  course_id?: string;
  parent_document_id?: string | null;
  parent_chunk_id?: string | null;
  image_type?: string;
  score?: number;
  retrieval_channels?: string[];
};

export type ResearchKnowledgeSearchRequest = {
  query: string;
  limit?: number;
  [key: string]: unknown;
};

export type ResearchReviewChecklist = {
  items?: ResearchReviewItem[];
  reviewer_id?: string;
  signed_off?: boolean;
};

export type ResearchReviewDecision = {
  reviewer_id: string;
  reviewer_role: "researcher" | "statistician" | "pi" | "admin";
  checklist: ResearchReviewChecklist;
  signed_at: string;
  decision_hash: string;
};

export type ResearchReviewItem = {
  review_id: string;
  category: "data" | "design" | "method" | "interpretation" | "artifact";
  question: string;
  status?: "pending" | "accepted" | "needs_change" | "not_applicable";
  note?: string;
};

export type ResearchReviewSubmission = {
  reviewer_id: string;
  reviewer_role: "researcher" | "statistician" | "pi" | "admin";
  items: ResearchReviewItem[];
  signed_off?: boolean;
};

export type ResponseDepth = "brief" | "standard" | "deep";

export type RetestPlanStatus = "scheduled" | "due" | "completed" | "cancelled" | "superseded";

export type RetestPlanV1 = {
  retest_plan_id: string;
  user_id: string;
  skill_id: string;
  source_task_id: string;
  source_attempt_id: string | null;
  interval_days: number;
  due_at: string;
  status: RetestPlanStatus;
  reason_code: string;
  generated_problem_id: string | null;
  completed_task_id: string | null;
  result: string | null;
  created_at: string;
  updated_at: string;
};

export type RetrievalResult = {
  query: string;
  normalized_query: string;
  course_ids: string[];
  hits?: KnowledgeHit[];
  confidence?: number | null;
  retrieval_mode?: string;
  warnings?: string[];
  latency_ms: number;
  image_hits?: RelatedImage[];
  rag_status?: string;
  embedding_status?: string;
  vector_store_status?: string;
  reranker_status?: string;
  query_modalities?: string[];
  retrieval_trace_id?: string;
  index_version?: string;
  trace?: {
  [key: string]: unknown;
};
};

export type RichTextSegment = {
  segment_type: MathSegmentType;
  text?: string | null;
  math?: MathExpression | null;
};

export type RuntimeApprovalSubmission = {
  decision?: "approved" | "rejected";
  reason?: string;
  expected_state_version?: number | null;
};

export type RuntimeGoal = {
  objective: string;
  success_criteria?: string[];
  constraints?: {
  [key: string]: unknown;
};
  required_capabilities?: string[];
  parallel_groups?: string[][];
  context?: {
  [key: string]: unknown;
};
  source?: string;
};

export type RuntimeInputSubmission = {
  data: {
  [key: string]: unknown;
};
  expected_state_version?: number | null;
};

export type RuntimeNode = {
  node_id: string;
  node_type: string;
  handler_id: string;
  target_id?: string;
  depends_on?: string[];
  activation?: RuntimeNodeActivation;
  recovery_for?: string[];
  parallel_group?: string;
  timeout_ms?: number;
  max_retries?: number;
  optional?: boolean;
  failure_policy?: string;
  input_artifact_ids?: string[];
  skill_id?: string;
  skill_version?: string;
  skill_binding_id?: string;
};

export type RuntimeNodeActivation = "all_succeeded" | "any_failed" | "always";

export type RuntimePlanBudgetImpact = {
  model_calls?: number;
  tool_calls?: number;
  subagent_runs?: number;
};

export type RuntimePlanProposal = {
  proposal_id: string;
  task_id: string;
  run_id: string;
  base_iteration: number;
  target_iteration: number;
  base_state_version: number;
  state_version: number;
  base_plan_id: string;
  base_plan_version: string;
  proposed_plan: AgentRunPlan;
  reason_codes: string[];
  rationale: string;
  affected_node_ids?: string[];
  budget_impact: RuntimePlanBudgetImpact;
  approval_required?: boolean;
  status?: RuntimePlanProposalStatus;
  decision_reason?: string;
  created_at?: string;
  decided_at?: string | null;
  applied_at?: string | null;
};

export type RuntimePlanProposalDecisionSubmission = {
  decision: "approved" | "rejected";
  reason?: string;
  expected_state_version?: number | null;
};

export type RuntimePlanProposalStatus = "pending" | "approved" | "rejected" | "applied";

export type RuntimeReconciliationSubmission = {
  runtime_run_id?: string | null;
  node_id: string;
  reconciliation_id?: string | null;
  outcome: "succeeded" | "failed";
  facts?: {
  [key: string]: unknown;
};
  artifact_ids?: string[];
  evidence_ids?: string[];
  warnings?: string[];
  errors?: string[];
  error_code?: string;
  expected_state_version?: number | null;
};

export type ScenarioDefinition = {
  id: string;
  version: string;
  name: string;
  summary: string;
  customer_segment: string;
  commercialization: CommercializationPlan;
  evidence_policy: KnowledgeEvidencePolicy;
  roles: string[];
  courses: string[];
  agent_id: string;
  intents: string[];
  input_modes: string[];
  retrieval_profile: string;
  primary_value_metric: string;
  evidence_requirements: string[];
  demo_steps: string[];
  demo_cases?: ScenarioDemoCase[];
  enabled?: boolean;
};

export type ScenarioDemoCase = {
  id: string;
  role: string;
  course: string;
  prompt: string;
  expected_agent: string;
  expected_output: string[];
  business_context: string;
  evidence_requirements: string[];
  review_boundary: string;
  acceptance_conditions: string[];
  formula_output_contract?: {
  [key: string]: unknown;
} | null;
  visual_acceptance?: {
  [key: string]: unknown;
} | null;
};

export type ScenarioEvidenceReviewRequest = {
  sources: ScenarioEvidenceSource[];
};

export type ScenarioEvidenceReviewResponse = {
  scenario_id: string;
  status: "approved" | "needs_manual_review" | "rejected";
  checked_count: number;
  cited_count: number;
  accepted_source_refs?: string[];
  rejected_source_refs?: string[];
  warnings?: string[];
};

export type ScenarioEvidenceSource = {
  source_type: string;
  source_ref: string;
  cited?: boolean;
  synthetic?: boolean;
  published_at?: string | null;
};

export type ScenarioPreflightResponse = {
  scenario_id: string;
  scenario_version: string;
  agent_id: string;
  agent_status: "runtime_available" | "fallback_only" | "mock_only" | "configured_unavailable" | "unavailable";
  fallback_agent_id?: string | null;
  fallback_available?: boolean;
  runtime_available: boolean;
  configured: boolean;
  mock_available: boolean;
  demo_ready: boolean;
  production_ready: boolean;
  commercialization_complete: boolean;
  evidence_review_required: boolean;
  input_modes?: string[];
  blockers?: string[];
  warnings?: string[];
};

export type Scene = "dispatch" | "solving" | "learning" | "teaching" | "research" | "infrastructure";

export type SessionCreate = {
  user_id: string;
  course_id?: string;
  title?: string;
  [key: string]: unknown;
};

export type SessionRead = {
  id: string;
  user_id: string;
  course_id: string;
  title: string;
  title_source: string;
  archived_at: string | null;
  last_message_at: string | null;
  message_count: number;
  session_revision: number;
  parent_session_id: string | null;
  branch_from_message_id: string | null;
  memory_enabled: boolean;
  auto_memory_enabled: boolean;
  context_compaction_enabled: boolean;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

export type SessionSummaryRead = {
  id: string;
  session_id: string;
  version: number;
  covers_from_sequence: number;
  covers_through_sequence: number;
  summary_text: string;
  structured_state: {
  [key: string]: unknown;
};
  source_message_ids: string[];
  source_checksum: string;
  generation_method: string;
  model_name: string;
  token_estimate: number;
  status: string;
  created_at: string;
  [key: string]: unknown;
};

export type SessionTaskHistoryItem = {
  id: string;
  course_id: string;
  intent: string;
  status: TaskStatus;
  provider: string;
  agent_id: string;
  question: string;
  answer: string;
  error_message: string | null;
  fallback_used?: boolean;
  fallback_reason?: string;
  answer_quality_status?: string;
  requires_review?: boolean;
  publishable?: boolean | null;
  math_quality_status?: string;
  formula_contract_status?: string;
  created_at: string;
  completed_at: string | null;
  [key: string]: unknown;
};

export type SessionUpdate = {
  user_id: string;
  title?: string | null;
  course_id?: string | null;
  memory_enabled?: boolean | null;
  auto_memory_enabled?: boolean | null;
  context_compaction_enabled?: boolean | null;
  [key: string]: unknown;
};

export type StudentAttemptStatus = "submitted" | "verified" | "manual_review" | "superseded" | "cancelled";

export type StudentAttemptStep = {
  step_id?: string | null;
  sequence?: number | null;
  content: string;
  expression?: string | null;
  claimed_result?: string | null;
  unit?: string | null;
  reference_direction?: string | null;
};

export type StudentAttemptV2 = {
  version?: string;
  attempt_id: string;
  user_id: string;
  session_id: string;
  task_id: string;
  source_task_id: string;
  attempt_sequence: number;
  revision_of_attempt_id?: string | null;
  raw_text?: string;
  final_answer?: string | null;
  steps?: StudentAttemptStep[];
  confidence?: number | null;
  teaching_mode: TeachingMode;
  hint_level_used?: string | null;
  full_solution_seen?: boolean;
  verification_status?: string | null;
  verification_report_ref?: string | null;
  submitted_at: string;
  status: StudentAttemptStatus;
};

export type TaskRead = {
  id: string;
  session_id: string;
  user_id: string;
  course_id: string;
  intent: string;
  status: TaskStatus;
  provider: string;
  agent_id: string;
  route_status: string;
  route_reason: string;
  input_content: {
  [key: string]: unknown;
};
  result_content: {
  [key: string]: unknown;
} | null;
  error_message: string | null;
  parent_task_id: string | null;
  attempt: number;
  cancellation_requested: boolean;
  idempotency_key: string | null;
  max_attempts: number;
  execution_owner: string | null;
  lease_expires_at: string | null;
  heartbeat_at: string | null;
  cancel_requested_at: string | null;
  failure_category: string | null;
  user_message_id: string | null;
  assistant_message_id: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  artifact_ids?: string[];
  retryable?: boolean;
  [key: string]: unknown;
};

export type TaskRuntimeControlProjectionRead = {
  task_id: string;
  runtime_run_id?: string;
  run_kind?: string;
  status?: string;
  state_version?: number;
  control_request?: string;
  control_scope?: "runtime" | "runtime_plan_proposal";
  plan_proposal?: TaskRuntimePlanProposalRead | null;
  controls?: TaskRuntimeControlRead[];
  [key: string]: unknown;
};

export type TaskRuntimeControlRead = {
  action: "pause" | "resume" | "approve" | "input";
  available: boolean;
  reason_code?: string;
  reason?: string;
  [key: string]: unknown;
};

export type TaskRuntimePlanProposalRead = {
  proposal_id: string;
  status: "pending" | "approved" | "rejected" | "applied";
  state_version: number;
  base_iteration: number;
  target_iteration: number;
  reason_codes?: string[];
  affected_node_ids?: string[];
  [key: string]: unknown;
};

export type TaskStatus = "created" | "queued" | "running" | "waiting_user" | "waiting_review" | "completed" | "failed" | "cancelled";

export type TeacherReviewQueueItemRead = {
  proposal_id: string;
  error_signature: string;
  priority: "P1" | "P2";
  priority_reason: string;
  skill_ids?: string[];
  problem_types?: string[];
  covered_by_runtime: boolean;
  review_decision: string;
  review_evidence_refs?: string[];
  review_notes?: string;
  reviewer?: string | null;
  reviewed_at?: string | null;
  review_evidence_quality?: "missing" | "traceable" | "untraceable";
  review_evidence_reference_kinds?: string[];
  evidence_required: boolean;
  runtime_eligible: boolean;
  deterministic_evidence_status?: "evidence_ready" | "review" | "not_declared";
  deterministic_conflict_types?: string[];
  deterministic_evidence_scope?: "structured_fields_only" | "finite_deterministic" | "not_declared";
  deterministic_validator_id?: string | null;
  deterministic_validator_path?: string | null;
  deterministic_evidence_note?: string;
  next_action: string;
};

export type TeacherReviewQueueRead = {
  schema_version: string;
  course_id: string;
  status: string;
  source_fingerprint?: string;
  runtime_loaded: boolean;
  item_count: number;
  items?: TeacherReviewQueueItemRead[];
  unresolved_signatures_without_proposal?: string[];
  all_items_require_teacher_evidence: boolean;
  proposal_schema_errors?: string[];
};

export type TeachingMode = "direct_answer" | "guided_learning" | "check_my_work" | "review";

export type UserRole = "student" | "teacher" | "researcher" | "admin" | "system";

export type ValidationError = {
  loc: string | number[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: {
  [key: string]: unknown;
};
  [key: string]: unknown;
};

export type WorkflowStatus = {
  agent_id: string;
  execution_mode: ExecutionMode;
  enabled: boolean;
  local_ready: boolean;
  available: boolean;
  unavailable_reason?: string | null;
  last_health_check?: string;
};
