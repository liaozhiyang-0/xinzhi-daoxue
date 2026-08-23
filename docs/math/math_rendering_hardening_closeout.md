# Math rendering hardening closeout

## Scope

- Worktree: `C:\Users\86184\Desktop\xinzhi-math-circuit-night`
- Branch: `feat/math-circuit-backend`
- Knowledge-base source root: `C:\Users\86184\Desktop\xinzhi-daoxue` (read-only)
- Frontend files and frontend KaTeX lockfiles: unchanged

## Delivered

- Added a read-only corpus audit with delimiter, environment, protected-code, risk, sample, and SHA-256 inventory outputs.
- Hardened `MathFormattingService` for `\(...\)`, `\[...\]`, `$...$`, `$$...$$`, array/matrix/aligned/cases, and raw-LaTeX fallback.
- Added typed fallback states: `UNSUPPORTED_RENDER`, `UNSAFE_COMMAND`, and `MALFORMED_LATEX`.
- Preserved code fences, inline code, and Verilog `$monitor` through indexing and answer formatting.
- Added local KaTeX compatibility sampling without changing npm packages or lockfiles.

## Evidence

- 56 Markdown files scanned; 64,316 formula instances: 53,502 inline and 10,814 display.
- Protected fenced/inline code spans observed: 2; no source Markdown writes were performed.
- Current source SHA-256 inventory is stored in `evaluation/math/math_corpus_inventory.json`.
- Local KaTeX runtime: 0.16.22; 549 selected formulas rendered; 2 real failures retained in `evaluation/math/katex_render_failures.jsonl`.
- Both failures are `\textasciicircum` in DSP source and remain raw LaTeX.

## Reproduce

```powershell
$py = 'C:\Users\86184\Desktop\xinzhi-daoxue\.venv\Scripts\python.exe'
& $py scripts\audit_math_corpus.py --source-root 'C:\Users\86184\Desktop\xinzhi-daoxue' --output-root 'C:\Users\86184\Desktop\xinzhi-math-circuit-night'
& $py scripts\check_math_compatibility.py --source-root 'C:\Users\86184\Desktop\xinzhi-daoxue' --output-root 'C:\Users\86184\Desktop\xinzhi-math-circuit-night'
```

The audit and compatibility reports are structural/local-runtime evidence, not a claim that every formula is production-renderable.
