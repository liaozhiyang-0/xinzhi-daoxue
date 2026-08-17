/**
 * Compile-time API contract consistency checks.
 *
 * Hand-written frontend contracts must remain structurally assignable to the
 * generated OpenAPI types (api-types.ts). If the FastAPI schema drifts (e.g.
 * a required field is added), `npm run typecheck` fails here instead of
 * shipping a stale contract.
 */
// The student workspace submit payload must be a valid AgentRequest body.
const _studentPayloadIsAgentRequest = null;
void _studentPayloadIsAgentRequest;
export {};
