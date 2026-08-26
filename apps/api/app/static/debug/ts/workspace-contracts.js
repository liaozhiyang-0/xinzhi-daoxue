/** Typed request contracts for the student workspace submit boundary. */
function attachmentRef(file) {
    return {
        file_id: file.id,
        filename: file.filename,
        content_type: file.content_type,
        size_bytes: file.size_bytes,
        storage_key: file.storage_key,
        checksum_sha256: file.checksum_sha256,
    };
}
export function buildStudentTaskPayload({ sessionId, userId, userRole, courseId, intent, scenarioId, canonicalInput, materials, responseDepth, circuitVisualizationEnabled = false, teachingMode, studentAttempt, learningFollowUp, requestId, researchAnalysis, }) {
    const options = {
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
    if (researchAnalysis !== undefined)
        options.research_analysis_v2 = researchAnalysis;
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
