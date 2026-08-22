# Known Limitations

1. The current official catalog has 84 available synthetic cases versus the 336-case roadmap target; 252 cases are missing.
2. No approved real-provider representative campaign is included in this RC, so real-model accuracy, token cost and provider fallback quality remain conditional.
3. Phase J has no independent blurred-image end-to-end fixture.
4. LLM-specific 429/500 full-chain fixtures and tool timeout/malformed/dependency fixtures remain incomplete; retrieval-layer rate-limit behavior is covered.
5. The 30–60 minute soak was not completed. The available smoke soak found valid `waiting_review` behavior and a frozen data-analysis failure; both are reported rather than hidden.
6. CPU and memory peak metrics are unavailable in the current environment because `psutil` is not installed.
7. Several component versions remain represented as `repository_current` or are not independently versioned. A production release requires explicit planner, skill, prompt, RAG index, tool, reflection, experience and evaluation version identifiers.
8. Experience Memory evidence remains structural/conditional; it does not prove a real-provider answer-quality lift.
9. Multi-image and difficult visual reasoning remain bounded by the declared input and evidence policies.
10. Existing developer changes make the working tree dirty. The K commit stages only release documentation and does not claim ownership of unrelated worktree changes.
