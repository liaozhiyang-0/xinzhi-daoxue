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
browser page errors. `workspace_failure.spec.js` additionally simulates API
delay, provider-style 504, server 500/503, first-SSE disconnect/reconnect,
attachment upload, session restore, and rapid consecutive submission. These
checks run against the same isolated test server and are reported separately
from the successful-response smoke.
