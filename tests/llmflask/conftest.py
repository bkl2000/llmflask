# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "components" / "llmflask" / "src"))

import pytest


@pytest.fixture(autouse=True)
def patch_config(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("LLMFLASK_DB", db_path)


@pytest.fixture
def db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("LLMFLASK_DB", db_path)
    from llmflask.database import init_db, get_db
    init_db(db_path)
    return db_path
