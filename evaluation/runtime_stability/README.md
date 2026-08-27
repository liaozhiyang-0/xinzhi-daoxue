# Runtime stability benchmark

This is a deterministic, publishable benchmark for Runtime timing and
behavioral stability. It is intentionally separate from the 598-case general
evaluation catalog and contains exactly 150 selected cases across seven
runtime-relevant categories.

`scripts/build_runtime_stability_cases.py` selects existing synthetic cases
first and creates only the missing category variants. The generated
`cases.json` stores the normalized cases and a source/catalog hash, so the
selection can be audited and rebuilt without copying prompts into a second
hand-maintained catalog.

The benchmark is not an official model-quality score. Real Provider runs must
be separately authorized and are never implied by local deterministic runs.
