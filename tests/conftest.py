# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import pytest


@pytest.fixture
def project_root():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent
