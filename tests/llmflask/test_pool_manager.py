# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import pytest
from pathlib import Path


class TestPoolManager:
    def test_create_basic(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        (src / "data.csv").write_text("a,b,c\n1,2,3\n")

        mgr = PoolManager(str(tmp_path / "pools"))
        name = mgr.create(str(src))

        assert name == "src-pool"
        pool_dir = tmp_path / "pools" / name
        assert pool_dir.is_dir()
        assert (pool_dir / "input" / "src" / "data.csv").read_text() == "a,b,c\n1,2,3\n"
        assert (pool_dir / "scripts").is_dir()
        assert (pool_dir / "output").is_dir()
        assert (pool_dir / "logs").is_dir()

        meta = json.loads((pool_dir / "pool.json").read_text())
        assert meta["pool_name"] == name
        assert meta["schema_version"] == 1
        assert meta["sandbox_image"] == "llmflask-sandbox:1"
        assert "input_hash" in meta

    def test_create_single_file(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src_file = tmp_path / "journal.log"
        src_file.write_text("line1\nline2\n")

        mgr = PoolManager(str(tmp_path / "pools"))
        name = mgr.create(str(src_file))

        assert name == "journal.log-pool"
        pool_input = tmp_path / "pools" / name / "input" / "journal.log"
        assert pool_input.read_text() == "line1\nline2\n"

    def test_create_with_pool_name(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        (src / "data.csv").write_text("x\n")

        mgr = PoolManager(str(tmp_path / "pools"))
        name = mgr.create(str(src), pool_name="mein-pool")

        assert name == "mein-pool"

    def test_name_conflict_increments(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        (src / "x.txt").write_text("x")

        mgr = PoolManager(str(tmp_path / "pools"))
        name1 = mgr.create(str(src))
        name2 = mgr.create(str(src))

        assert name1 == "src-pool"
        assert name2 == "src-pool-2"

    def test_reuse_existing_pool(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        (src / "x.txt").write_text("x")

        mgr = PoolManager(str(tmp_path / "pools"))
        name1 = mgr.create(str(src))
        name2 = mgr.create(str(src), pool_name=name1, reuse=True)

        assert name1 == name2

    def test_reuse_missing_fails(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        mgr = PoolManager(str(tmp_path / "pools"))
        with pytest.raises(FileNotFoundError, match="not found"):
            mgr.create(str(tmp_path / "dummy.txt"), pool_name="nope", reuse=True)

    def test_invalid_pool_name(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        (src / "x.txt").write_text("x")

        mgr = PoolManager(str(tmp_path / "pools"))
        with pytest.raises(ValueError, match="Invalid pool name"):
            mgr.create(str(src), pool_name="../escape")

    def test_public_operations_reject_traversal(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        mgr = PoolManager(str(tmp_path / "pools"))
        with pytest.raises(ValueError, match="Invalid pool name"):
            mgr.pool_path("../outside")
        with pytest.raises(ValueError, match="Invalid pool name"):
            mgr.remove("..")

    def test_create_rejects_symlink_input(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        target = tmp_path / "secret.txt"
        target.write_text("secret")
        (src / "linked.txt").symlink_to(target)

        mgr = PoolManager(str(tmp_path / "pools"))
        with pytest.raises(ValueError, match="Symbolic links"):
            mgr.create(str(src))
        assert not (tmp_path / "pools" / "src-pool").exists()

    def test_create_cleans_staging_on_copy_failure(self, tmp_path, monkeypatch):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src.txt"
        src.write_text("data")
        pool_root = tmp_path / "pools"

        def fail_copy(*_args, **_kwargs):
            raise OSError("copy failed")

        monkeypatch.setattr("shutil.copy2", fail_copy)
        with pytest.raises(OSError, match="copy failed"):
            PoolManager(str(pool_root)).create(str(src))
        assert list(pool_root.iterdir()) == []

    def test_source_not_found(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        mgr = PoolManager(str(tmp_path / "pools"))
        with pytest.raises(FileNotFoundError):
            mgr.create("/nonexistent/path")

    def test_list_pools(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        (src / "x.txt").write_text("x")

        mgr = PoolManager(str(tmp_path / "pools"))
        mgr.create(str(src), pool_name="pool-a")
        mgr.create(str(src), pool_name="pool-b")

        pools = mgr.list_pools()
        assert len(pools) == 2
        names = {p["name"] for p in pools}
        assert names == {"pool-a", "pool-b"}

    def test_remove_pool(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager

        src = tmp_path / "src"
        src.mkdir()
        (src / "x.txt").write_text("x")

        mgr = PoolManager(str(tmp_path / "pools"))
        name = mgr.create(str(src))
        assert mgr.exists(name)

        mgr.remove(name)
        assert not mgr.exists(name)

    def test_validate_rejects_output_symlink_without_reading_target(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager, UnsafePoolError

        src = tmp_path / "src.txt"
        src.write_text("input")
        secret = tmp_path / "secret.txt"
        secret.write_text("do not read")
        mgr = PoolManager(str(tmp_path / "pools"))
        name = mgr.create(str(src))
        (tmp_path / "pools" / name / "output" / "secret").symlink_to(secret)

        with pytest.raises(UnsafePoolError, match="Symbolic links"):
            mgr.validate(name)
        listed = mgr.list_pools()
        assert listed[0]["name"] == name
        assert "Symbolic links" in listed[0]["unsafe"]
        mgr.remove(name)
        assert secret.read_text() == "do not read"

    def test_pool_path_rejects_top_level_symlink(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager, UnsafePoolError

        pool_root = tmp_path / "pools"
        outside = tmp_path / "outside"
        pool_root.mkdir()
        outside.mkdir()
        (pool_root / "linked-pool").symlink_to(outside, target_is_directory=True)

        with pytest.raises(UnsafePoolError, match="must not be"):
            PoolManager(str(pool_root)).pool_path("linked-pool")

    def test_input_hash_stable(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager, _compute_hash
        from pathlib import Path

        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("hello")

        h1 = _compute_hash(src)
        h2 = _compute_hash(src)

        assert h1 == h2
        assert len(h1) == 64

    def test_input_hash_changes(self, tmp_path):
        from llmflask.workbench.pool_manager import _compute_hash

        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("hello")

        h1 = _compute_hash(src)
        (src / "a.txt").write_text("world")
        h2 = _compute_hash(src)

        assert h1 != h2

    def test_input_hash_streams_files_without_read_bytes(self, tmp_path, monkeypatch):
        from llmflask.workbench.pool_manager import _compute_hash

        source = tmp_path / "large.bin"
        source.write_bytes(b"content")
        monkeypatch.setattr(
            Path,
            "read_bytes",
            lambda _path: (_ for _ in ()).throw(AssertionError("read_bytes called")),
        )

        assert len(_compute_hash(source)) == 64

    def test_create_from_samples_adr_csv(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager
        from pathlib import Path
        import json

        repo_root = Path(__file__).resolve().parent.parent.parent
        sample = repo_root / "samples" / "adr.csv"
        assert sample.is_file(), f"Sample nicht gefunden: {sample}"

        mgr = PoolManager(str(tmp_path / "pools"))
        name = mgr.create(str(sample))

        assert name == "adr.csv-pool"
        pool_dir = tmp_path / "pools" / name
        copied = pool_dir / "input" / "adr.csv"
        assert copied.read_text() == sample.read_text()

        meta = json.loads((pool_dir / "pool.json").read_text())
        assert meta["source_path"] == str(sample)
        assert len(meta["input_hash"]) == 64

    def test_output_and_logs_are_world_writable(self, tmp_path):
        from llmflask.workbench.pool_manager import PoolManager
        import stat
        import os

        src = tmp_path / "src"
        src.mkdir()
        (src / "x.txt").write_text("x")

        mgr = PoolManager(str(tmp_path / "pools"))
        name = mgr.create(str(src))
        pool_dir = tmp_path / "pools" / name

        output_mode = stat.S_IMODE(os.stat(pool_dir / "output").st_mode)
        logs_mode = stat.S_IMODE(os.stat(pool_dir / "logs").st_mode)

        assert output_mode & stat.S_IWOTH
        assert logs_mode & stat.S_IWOTH
        assert output_mode & stat.S_IXOTH
        assert logs_mode & stat.S_IXOTH
