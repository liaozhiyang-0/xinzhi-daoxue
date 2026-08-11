from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "apps" / "api" / "app" / "static" / "debug" / "agents.js"


def test_agents_ui_keeps_publication_not_ready_until_authorization() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the isolated UI behavior check")
    harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8") + `
globalThis.__publicationContract = {
  evidence: runtimePublicationEvidence,
  summary: runtimePublicationEvidenceSummary,
};`;
const noop = () => {};
const context = {
  XinzhiUI: {
    $: noop,
    all: () => [],
    api: noop,
    badge: noop,
    el: noop,
    initShell: noop,
    initTabs: noop,
    renderJson: noop,
    toast: noop,
  },
  console,
  window: { addEventListener: noop, confirm: () => false },
};
context.globalThis = context;
vm.runInNewContext(source, context, { filename: "agents.js" });
const contract = context.__publicationContract;
const authorized = contract.evidence({
  structural_release_eligible: true,
  semantic_release_eligible: true,
  canary_release_eligible: true,
  canary_reason: "canary_release_evidence_approved",
});
if (!authorized.publicationReady) throw new Error("authorized evidence was blocked");

const missingAuthorization = contract.evidence({
  structural_release_eligible: true,
  semantic_release_eligible: true,
  canary_release_eligible: false,
  canary_reason: "release_authorization_missing",
  blockers: ["release_authorization_missing"],
});
if (missingAuthorization.publicationReady) {
  throw new Error("authorization gate was bypassed");
}
if (!missingAuthorization.authorizationBlocked) {
  throw new Error("authorization blocker was lost");
}
if (!contract.summary({ canary_reason: "release_authorization_missing" })
  .includes("\u6388\u6743")) {
  throw new Error("authorization summary was not rendered");
}
'''
    result = subprocess.run(
        [node, "-e", harness, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr or result.stdout
