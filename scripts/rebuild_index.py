from __future__ import annotations

import sys

from scripts.knowledge_base_cli import main

if __name__ == "__main__":
    # Reuses the validated index builder and its versioned Qdrant collections.
    sys.argv.insert(1, "rebuild")
    raise SystemExit(main())
