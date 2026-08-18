"""Make the repository's legacy import layout deterministic under pytest."""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
for import_root in (ROOT, ROOT / "src" / "services"):
    path = str(import_root)
    if path not in sys.path:
        sys.path.insert(0, path)

# Importing Telegram handlers validates the token at module load time. Tests
# use fake Bot/Message objects and must never require a developer's real token.
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
