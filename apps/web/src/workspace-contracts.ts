/** Typed request contracts for the student workspace submit boundary. */

import type { Intent, UserRole } from "./api-types.js";
import type { UploadedFile, UploadedMaterial } from "./materials.js";

export interface AttachmentRef {
  file_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  provider_file_id?: string | null;
  checksum_sha256?: string | null;
  ingestion_status?: string;
  page_count?: number;
}

export interface CanonicalInput {
  text: string;
  uploaded_text?: string;
  data_description?: string;
  [key: string]: unknown;
}

export interface LearningFollowUp {
  course_id?: string;
  intent?: string;
  source_task_id?: string;
  action?: string;
}

export interface StudentTaskOptions {
  request_id: string;
  response_depth: string;
  teaching_mode: string;
  student_attempt?: { raw_text: string };
  prefer_internal_agents: true;
  use_local_rag: true;
  source_task_id: string;
  learning_action: string;
  research_analysis_v2?: unknown;
  [key: string]: unknown;
}

export interface StudentTaskPayload {
  session_id: string;
  user_id: string;
  user_role: UserRole;
  scene: "dispatch";
  course_id: string;
  intent: Intent;
  scenario_id: string | null;
  canonical_input: CanonicalInput;
  attachments: AttachmentRef[];
  context_refs: string[];
  options: StudentTaskOptions;
}

export interface BuildStudentTaskPayloadInput {
  sessionId: string;
  userId: string;
  userRole: UserRole;
  courseId: string;
  intent: Intent;
  scenarioId: string | null;
  canonicalInput: CanonicalInput;
  materials: readonly UploadedMaterial[];
  responseDepth: string;
  circuitVisualizationEnabled?: boolean;
  teachingMode: string;
  studentAttempt: string;
  learningFollowUp?: LearningFollowUp | null;
  requestId: string;
  researchAnalysis?: unknown;
}

function attachmentRef(file: UploadedFile): AttachmentRef {
  return {
    file_id: file.id,
    filename: file.filename,
    content_type: file.content_type,
    size_bytes: file.size_bytes,
    storage_key: file.storage_key,
    checksum_sha256: file.checksum_sha256,
  };
}

export function buildStudentTaskPayload({
  sessionId,
  userId,
  userRole,
  courseId,
  intent,
  scenarioId,
  canonicalInput,
  materials,
  responseDepth,
  circuitVisualizationEnabled = false,
  teachingMode,
  studentAttempt,
  learningFollowUp,
  requestId,
  researchAnalysis,
}: BuildStudentTaskPayloadInput): StudentTaskPayload {
  const options: StudentTaskOptions = {
    request_id: requestId,
    response_depth: responseDepth,
    circuit_visualization_mode: circuitVisualizationEnabled ? "controlled" : "off",
    teaching_mode: teachingMode,
    student_attempt: studentAttempt ? { raw_text: studentAttempt } : undefined,
    prefer_internal_agents: true,
    use_local_rag: true,
    source_task_id: learningFollowUp?.source_task_id || "",
    learning_action: learningFollowUp?.action || "",
  };
  if (researchAnalysis !== undefined) options.research_analysis_v2 = researchAnalysis;

  return {
    session_id: sessionId,
    user_id: userId,
    user_role: userRole,
    scene: "dispatch",
    course_id: courseId,
    intent,
    scenario_id: scenarioId,
    canonical_input: canonicalInput,
    attachments: materials.map((item) => attachmentRef(item.uploaded)),
    context_refs: [],
    options,
  };
}
