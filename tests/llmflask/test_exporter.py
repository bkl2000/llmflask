# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json


def test_export_md_has_title():
    from llmflask.services.exporter import export_md

    msgs = [{"role": "user", "content": "Hello", "created_at": "2026-07-04T19:00:00"}]
    md = export_md(msgs, "Test Chat")
    assert '# Chat: "Test Chat"' in md
    assert "## 1. User" in md
    assert "Hello" in md


def test_export_md_multiple_messages():
    from llmflask.services.exporter import export_md

    msgs = [
        {"role": "user", "content": "Q1", "created_at": "2026-07-04T19:00:00"},
        {"role": "assistant", "content": "A1", "created_at": "2026-07-04T19:01:00"},
    ]
    md = export_md(msgs, "Chat")
    assert "## 1. User" in md
    assert "## 2. Assistant" in md
    assert "Q1" in md
    assert "A1" in md


def test_export_pdf_returns_bytes():
    from llmflask.services.exporter import export_pdf

    msgs = [{"role": "user", "content": "Hello", "created_at": "2026-07-04T19:00:00"}]
    try:
        data = export_pdf(msgs, "Test")
    except RuntimeError:
        return  # pandoc/weasyprint not installed — skip
    assert isinstance(data, bytes)
    assert len(data) > 0
    assert data[:5] == b"%PDF-"


def test_export_pdf_with_filename(tmp_path):
    from llmflask.services.exporter import export_pdf

    msgs = [{"role": "user", "content": "Hello", "created_at": "2026-07-04T19:00:00"}]
    out = tmp_path / "test.pdf"
    try:
        export_pdf(msgs, "Test", filename=str(out))
    except RuntimeError:
        return
    assert out.exists()


def test_export_ipynb_is_valid_json():
    from llmflask.services.exporter import export_ipynb

    msgs = [
        {"role": "user", "content": "Q", "created_at": "2026-07-04T19:00:00"},
        {"role": "assistant", "content": "A", "created_at": "2026-07-04T19:01:00"},
    ]
    nb = export_ipynb(msgs, "Chat")
    data = json.loads(nb)
    assert data["nbformat"] == 4
    assert len(data["cells"]) >= 2


def test_export_ipynb_cell_types():
    from llmflask.services.exporter import export_ipynb

    msgs = [{"role": "user", "content": "Hello", "created_at": "2026-07-04T19:00:00"}]
    nb = export_ipynb(msgs, "Test")
    data = json.loads(nb)
    for cell in data["cells"]:
        assert cell["cell_type"] == "markdown"


def test_export_pdf_raises_when_pandoc_missing(monkeypatch):
    import llmflask.services.exporter as mod

    original_run = mod.subprocess.run
    def mock_run(cmd, **kwargs):
        raise FileNotFoundError("pandoc")
    monkeypatch.setattr(mod.subprocess, "run", mock_run)
    msgs = [{"role": "user", "content": "Hello", "created_at": "2026-07-04T19:00:00"}]
    try:
        mod.export_pdf(msgs, "Test")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "pandoc is not installed" in str(e)


def test_empty_messages():
    from llmflask.services.exporter import export_md, export_ipynb

    md = export_md([], "Empty")
    assert 'Chat: "Empty"' in md

    nb = export_ipynb([], "Empty")
    data = json.loads(nb)
    assert len(data["cells"]) == 0
