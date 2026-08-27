# Browser stability coverage

Run the real Legacy Workspace acceptance flow with:

```powershell
$env:NODE_PATH = (Join-Path (Get-Location) ".codex-tmp\playwright-runner\node_modules")
node tests\browser\workspace_stability.spec.js
```

The runner uses a temporary test database and a local FastAPI test server. The
scenario matrix in `scripts/student_browser_smoke.js` covers workspace loading,
natural-language submission, SSE completion, input/button restoration, session
creation, evidence interaction, text/image attachments, the explicit frozen
data-analysis boundary, execution debug, presentation/mobile/dark views, and
browser page errors. Keep API-delay, provider-timeout, SSE-disconnect, 500/503,
and rapid-submit cases in the server-level harness; they should be added there
when the test server exposes deterministic fault injection rather than being
silently treated as a successful browser result.
