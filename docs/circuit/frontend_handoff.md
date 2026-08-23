# Frontend handoff

The backend core is intentionally frontend-independent and the `circuit.render` capability is disabled by default.

- Consume `CircuitRenderResult.status`, `validation_state`, `warnings`, and `svg` as optional display data.
- Treat `status=degraded` as usable fallback SVG with a visible nonfatal warning.
- Treat `status=failed` as a text-only fallback; do not block the main answer.
- Enable the tool only through the existing backend registry flag; no frontend route, workspace, CSS, KaTeX version, or lockfile change is part of this commit.
- Keep MathFormattingService output as the single answer-rendering boundary; frontend code should not re-parse raw source Markdown.
