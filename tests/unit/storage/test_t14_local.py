"""Real local-file boundary probes, including Windows junctions and handle races."""

from hashlib import sha256
import os
from pathlib import Path
import subprocess
from uuid import UUID, uuid1, uuid4

import pytest

from app.storage.local import LocalStorageBackend
from app.storage.protocol import StorageBackend
from app.storage.schemas import StorageError, StorageNamespace


@pytest.fixture
def backend(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    for namespace in StorageNamespace:
        (root / namespace.value).mkdir()
    return LocalStorageBackend(root)


def test_construction_is_no_io_and_ready_requires_explicit_directories(tmp_path):
    root = tmp_path / "not-created"
    adapter = LocalStorageBackend(root)
    assert not root.exists()
    with pytest.raises(StorageError):
        adapter.verify_ready()
    root.mkdir()
    with pytest.raises(StorageError):
        adapter.verify_ready()
    assert list(root.iterdir()) == []
    with pytest.raises(StorageError):
        LocalStorageBackend(Path("relative"))


def test_real_roundtrip_and_namespace_isolation(backend):
    backend.verify_ready()
    assert isinstance(backend, StorageBackend)
    key = uuid4()
    data = b'{"DEMO_x":1}'
    receipt = backend.write(StorageNamespace.student_private, key, data)
    assert set(receipt.model_dump()) == {"namespace", "object_id", "size_bytes", "sha256"}
    assert backend.read("student_private", key, len(data), sha256(data).hexdigest()) == data
    with pytest.raises(StorageError) as caught:
        backend.read("source_quarantine", key, len(data), sha256(data).hexdigest())
    assert caught.value.status_code == 404
    assert backend.delete("student_private", key) is True
    assert backend.delete("student_private", key) is False


def test_uuid_collision_never_overwrites_original(backend):
    key = uuid4()
    data = b'DEMO_original'
    backend.write("source_quarantine", key, data)
    with pytest.raises(StorageError) as caught:
        backend.write("source_quarantine", key, b'DEMO_replacement')
    assert caught.value.status_code == 409
    assert backend.read("source_quarantine", key, len(data), sha256(data).hexdigest()) == data


@pytest.mark.parametrize("namespace,key", [
    ("../outside", uuid4()), ("student_private/../source_quarantine", uuid4()),
    ("student_private", "../outside"), ("student_private", str(uuid4())),
    ("student_private", uuid1()), ("student_private", UUID(int=0)),
])
def test_typed_server_keys_refuse_path_or_nonrandom_id(backend, namespace, key):
    with pytest.raises(StorageError) as caught:
        backend.write(namespace, key, b'x')
    assert caught.value.status_code == 422
    assert list((backend.root / "student_private").iterdir()) == []


def test_read_requires_exact_hash_size_and_detects_tampering(backend):
    key = uuid4()
    data = b'DEMO_original'
    backend.write("student_private", key, data)
    for size, digest in ((True, sha256(data).hexdigest()), (len(data), "bad"),
                         (len(data) + 1, sha256(data).hexdigest()), (len(data), "0" * 64)):
        with pytest.raises(StorageError):
            backend.read("student_private", key, size, digest)
    (backend.root / "student_private" / str(key)).write_bytes(b'DEMO_modified')
    with pytest.raises(StorageError):
        backend.read("student_private", key, len(data), sha256(data).hexdigest())


def test_adapter_configuration_cannot_be_rebound(backend, tmp_path):
    backend.root = tmp_path
    with pytest.raises(StorageError):
        backend.verify_ready()


def test_real_hardlink_cannot_read_or_delete_external_object(backend, tmp_path):
    outside = tmp_path / "outside-hardlink.txt"
    data = b'DEMO_outside'
    outside.write_bytes(data)
    key = uuid4()
    link = backend.root / "student_private" / str(key)
    os.link(outside, link)
    try:
        for operation in (
            lambda: backend.read("student_private", key, len(data), sha256(data).hexdigest()),
            lambda: backend.delete("student_private", key),
        ):
            with pytest.raises(StorageError):
                operation()
        assert outside.read_bytes() == data
    finally:
        link.unlink()


def test_adapter_body_and_disk_size_guard_before_read_buffer(backend, monkeypatch):
    from app.storage.schemas import MAX_FILE_BYTES
    for data in (b'', bytearray(b'x'), b'x' * (MAX_FILE_BYTES + 1)):
        with pytest.raises(StorageError):
            backend.write("student_private", uuid4(), data)
    key = uuid4()
    path = backend.root / "student_private" / str(key)
    path.write_bytes(b'x' * (MAX_FILE_BYTES + 1))
    if os.name == "nt":
        from app.storage.local import _WindowsAPI
        def unexpected(*args, **kwargs):
            pytest.fail("oversized disk object was buffered")
        monkeypatch.setattr(_WindowsAPI, "read", unexpected)
    with pytest.raises(StorageError):
        backend.read("student_private", key, MAX_FILE_BYTES, "0" * 64)


def test_pure_storage_import_and_closed_constructor_do_not_load_business(tmp_path):
    import sys
    program = '''
import sys
from pathlib import Path
from app.storage.protocol import StorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.validation import validate_upload
root = Path(sys.argv[1])
LocalStorageBackend(root)
assert not root.exists()
assert not any(name.startswith(("sqlalchemy", "httpx", "app.auth", "app.privacy", "app.audit"))
               for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-B", "-c", program, str(tmp_path / "uncreated")],
                            capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "services/api"})
    assert result.returncode == 0, result.stderr


def _symlink(link, target):
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as error:
        pytest.skip(f"real symlink creation unavailable: winerror={getattr(error, 'winerror', None)}")


def test_real_file_symlink_rejected_on_read_delete_and_write(backend, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b'DEMO_outside')
    key = uuid4()
    link = backend.root / "student_private" / str(key)
    _symlink(link, outside)
    try:
        for operation in (
            lambda: backend.read("student_private", key, 12, sha256(b'DEMO_outside').hexdigest()),
            lambda: backend.delete("student_private", key),
            lambda: backend.write("student_private", key, b'DEMO_new'),
        ):
            with pytest.raises(StorageError):
                operation()
        assert outside.read_bytes() == b'DEMO_outside'
    finally:
        link.unlink()


def _junction(link, target):
    result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        pytest.skip(f"real junction creation unavailable: exit={result.returncode}")


@pytest.mark.skipif(os.name != "nt", reason="Windows kernel/reparse probe")
@pytest.mark.parametrize("position", ["namespace", "ancestor"])
def test_real_windows_junction_rejected(backend, tmp_path, position):
    outside = tmp_path / "outside"
    outside.mkdir()
    if position == "namespace":
        link = backend.root / "student_private"
        link.rmdir()
        configured = backend
    else:
        link = tmp_path / "redirect"
        (outside / "private").mkdir()
        for ns in StorageNamespace:
            (outside / "private" / ns.value).mkdir()
        configured = LocalStorageBackend(link / "private")
    _junction(link, outside)
    try:
        with pytest.raises(StorageError):
            configured.verify_ready()
        with pytest.raises(StorageError):
            configured.write("student_private", uuid4(), b'DEMO_content')
        assert not list(outside.glob("**/*-*-*-*-*"))
    finally:
        link.rmdir()  # Removes the test junction itself, never the target directory.


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing mode race probe")
def test_real_windows_namespace_swap_blocked_while_handles_anchored(backend, monkeypatch):
    from app.storage.local import _WindowsAPI
    namespace = backend.root / "student_private"
    moved = backend.root / "moved"
    original = _WindowsAPI.check
    attempts = []
    def check(self, handle, path, *, directory):
        result = original(self, handle, path, directory=directory)
        if directory and path == namespace:
            try:
                os.rename(namespace, moved)
            except PermissionError as error:
                attempts.append(error.winerror)
            else:
                os.rename(moved, namespace)
                pytest.fail("anchored namespace could be renamed")
        return result
    monkeypatch.setattr(_WindowsAPI, "check", check)
    key = uuid4()
    receipt = backend.write("student_private", key, b'DEMO_content')
    assert attempts and all(error == 32 for error in attempts)
    assert backend.read("student_private", key, receipt.size_bytes, receipt.sha256) == b'DEMO_content'


@pytest.mark.skipif(os.name != "nt", reason="Windows handle-only partial-write cleanup")
def test_partial_write_failure_leaves_no_registered_blob(backend, monkeypatch):
    from app.storage.local import _WindowsAPI
    original = _WindowsAPI.write
    def fail(self, handle, data):
        original(self, handle, data[:3])
        raise StorageError()
    monkeypatch.setattr(_WindowsAPI, "write", fail)
    key = uuid4()
    with pytest.raises(StorageError):
        backend.write("student_private", key, b'DEMO_content')
    assert not (backend.root / "student_private" / str(key)).exists()
