"""Hermetic defaults required while importing Telegram handlers in tests."""

import os


os.environ.setdefault("BOT_TOKEN", "test-token")
