"""Test-only environment defaults needed while pytest imports bot handlers."""

import os


os.environ.setdefault("BOT_TOKEN", "123456789:test-token-for-pytest-collection")
