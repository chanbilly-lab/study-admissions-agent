"""Private, bounded local blobs. OS administrators and directory ACLs remain trusted."""

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from uuid import UUID

from .schemas import MAX_FILE_BYTES, StorageError, StorageNamespace, StoredBlob


def _reference(namespace, object_id):
    try:
        if not isinstance(namespace, (str, StorageNamespace)):
            raise ValueError
        namespace = StorageNamespace(namespace)
        if type(object_id) is not UUID or object_id.version != 4:
            raise ValueError
    except (ValueError, TypeError):
        raise StorageError(422, "INVALID_FILE") from None
    return namespace, str(object_id)


def _expected(size, digest):
    if (type(size) is not int or not 1 <= size <= MAX_FILE_BYTES
        or type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
        raise StorageError(422, "INVALID_FILE")


class LocalStorageBackend:
    def __init__(self, root: Path | str):
        # Construction performs no filesystem operation and creates no directories.
        if not isinstance(root, (str, Path)):
            raise StorageError()
        try:
            self.root = Path(root)
            raw = str(self.root)
            if (not self.root.is_absolute() or ".." in self.root.parts
                or any(ord(c) < 32 for c in raw) or len(raw) > 4096
                or (os.name == "nt" and not re.fullmatch(r"[A-Za-z]:", self.root.drive))):
                raise ValueError
            raw.encode("utf-8")
        except (ValueError, UnicodeError):
            raise StorageError() from None
        self._initial_root = self.root

    def _check_root(self):
        if self.root != self._initial_root:
            raise StorageError()

    @contextmanager
    def _posix_directory(self, namespace):
        handles = []
        try:
            self._check_root()
            if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
                raise StorageError()
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            fd = os.open(self.root.anchor, flags)
            handles.append(fd)
            for component in (*self.root.parts[1:], namespace.value):
                fd = os.open(component, flags, dir_fd=fd)
                handles.append(fd)
                if not stat.S_ISDIR(os.fstat(fd).st_mode):
                    raise StorageError()
            yield fd
        except OSError:
            raise StorageError() from None
        finally:
            for handle in reversed(handles):
                os.close(handle)

    @contextmanager
    def _windows_directory(self, namespace):
        api = _WindowsAPI()
        handles = []
        try:
            self._check_root()
            current = Path(self.root.anchor)
            # All ancestors stay open without WRITE/DELETE sharing. OPEN_REPARSE_POINT
            # means junctions are inspected rather than traversed at every component.
            for component in (None, *self.root.parts[1:], namespace.value):
                if component is not None:
                    current /= component
                # Attribute-only handles do not participate in Windows sharing
                # checks strongly enough to prevent directory rename. GENERIC_READ
                # anchors the directory against other WRITE/DELETE access.
                handle = api.open(current, access=0x80000000, creation=3, directory=True)
                handles.append(handle)
                api.check(handle, current, directory=True)
            yield api, handles[-1], current
        finally:
            for handle in reversed(handles):
                api.close(handle)

    def verify_ready(self) -> None:
        for namespace in StorageNamespace:
            if os.name == "nt":
                with self._windows_directory(namespace):
                    pass
            else:
                with self._posix_directory(namespace):
                    pass

    def write(self, namespace, object_id: UUID, data: bytes) -> StoredBlob:
        namespace, name = _reference(namespace, object_id)
        if type(data) is not bytes or not data:
            raise StorageError(422, "INVALID_FILE")
        if len(data) > MAX_FILE_BYTES:
            raise StorageError(413, "FILE_TOO_LARGE")
        if os.name == "nt":
            with self._windows_directory(namespace) as (api, _, directory):
                handle = api.open(directory / name, access=0x40000000 | 0x10000 | 0x80,
                                  creation=1, directory=False, share=0)
                try:
                    api.check(handle, directory / name, directory=False)
                    api.write(handle, data)
                    api.check(handle, directory / name, directory=False)
                except BaseException:
                    api.discard(handle)
                    raise
                finally:
                    api.close(handle)
        else:
            with self._posix_directory(namespace) as directory:
                fd = None
                created = False
                try:
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
                    created = True
                    if not stat.S_ISREG(os.fstat(fd).st_mode):
                        raise StorageError()
                    view = memoryview(data)
                    while view:
                        count = os.write(fd, view[:65_536])
                        if count <= 0:
                            raise StorageError()
                        view = view[count:]
                    os.fsync(fd)
                except FileExistsError:
                    raise StorageError(409, "STORAGE_CONFLICT") from None
                except BaseException as error:
                    if created:
                        try:
                            os.unlink(name, dir_fd=directory)
                        except OSError:
                            pass
                    if isinstance(error, OSError):
                        raise StorageError() from None
                    raise
                finally:
                    if fd is not None:
                        os.close(fd)
        return StoredBlob(namespace=namespace, object_id=object_id, size_bytes=len(data),
                          sha256=sha256(data).hexdigest())

    def read(self, namespace, object_id: UUID, expected_size: int, expected_sha256: str) -> bytes:
        namespace, name = _reference(namespace, object_id)
        _expected(expected_size, expected_sha256)
        if os.name == "nt":
            with self._windows_directory(namespace) as (api, _, directory):
                handle = api.open(directory / name, access=0x80000000 | 0x80,
                                  creation=3, directory=False)
                try:
                    info = api.check(handle, directory / name, directory=False)
                    if (info.nFileSizeHigh << 32) | info.nFileSizeLow != expected_size:
                        raise StorageError()
                    data = api.read(handle, expected_size)
                    api.check(handle, directory / name, directory=False)
                finally:
                    api.close(handle)
        else:
            with self._posix_directory(namespace) as directory:
                fd = None
                try:
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != expected_size:
                        raise StorageError()
                    parts = []
                    remaining = expected_size + 1
                    while remaining:
                        chunk = os.read(fd, min(remaining, 65_536))
                        if not chunk:
                            break
                        parts.append(chunk)
                        remaining -= len(chunk)
                    data = b"".join(parts)
                except FileNotFoundError:
                    raise StorageError(404, "FILE_NOT_FOUND") from None
                except OSError:
                    raise StorageError() from None
                finally:
                    if fd is not None:
                        os.close(fd)
        if len(data) != expected_size or sha256(data).hexdigest() != expected_sha256:
            raise StorageError()
        return data

    def delete(self, namespace, object_id: UUID) -> bool:
        namespace, name = _reference(namespace, object_id)
        if os.name == "nt":
            with self._windows_directory(namespace) as (api, _, directory):
                try:
                    handle = api.open(directory / name, access=0x10000 | 0x80,
                                      creation=3, directory=False)
                except StorageError as error:
                    if error.status_code == 404:
                        return False
                    raise
                try:
                    api.check(handle, directory / name, directory=False)
                    api.delete(handle)
                finally:
                    api.close(handle)
        else:
            with self._posix_directory(namespace) as directory:
                try:
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise StorageError()
                    os.unlink(name, dir_fd=directory)
                except FileNotFoundError:
                    return False
                except OSError:
                    raise StorageError() from None
        return True


class _WindowsAPI:
    """Small stdlib kernel wrapper; never invokes a shell or opens a supplied path."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)

        class FileInfo(ctypes.Structure):
            _fields_ = [("dwFileAttributes", wintypes.DWORD), ("ftCreationTime", wintypes.FILETIME),
                        ("ftLastAccessTime", wintypes.FILETIME), ("ftLastWriteTime", wintypes.FILETIME),
                        ("dwVolumeSerialNumber", wintypes.DWORD), ("nFileSizeHigh", wintypes.DWORD),
                        ("nFileSizeLow", wintypes.DWORD), ("nNumberOfLinks", wintypes.DWORD),
                        ("nFileIndexHigh", wintypes.DWORD), ("nFileIndexLow", wintypes.DWORD)]

        self.FileInfo = FileInfo
        signatures = {
            "CreateFileW": ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                             wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE], wintypes.HANDLE),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "GetFileInformationByHandle": ([wintypes.HANDLE, ctypes.POINTER(FileInfo)], wintypes.BOOL),
            "GetFinalPathNameByHandleW": ([wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD,
                                          wintypes.DWORD], wintypes.DWORD),
            "ReadFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p], wintypes.BOOL),
            "WriteFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                           ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p], wintypes.BOOL),
            "FlushFileBuffers": ([wintypes.HANDLE], wintypes.BOOL),
            "SetFileInformationByHandle": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result

    def open(self, path, *, access, creation, directory, share=1):
        flags = 0x00200000 | (0x02000000 if directory else 0)  # OPEN_REPARSE_POINT / BACKUP_SEMANTICS
        handle = self.kernel.CreateFileW(str(path), access, share, None, creation, flags, None)
        if handle == self.ctypes.c_void_p(-1).value:
            error = self.ctypes.get_last_error()
            if not directory and error in (2, 3):
                raise StorageError(404, "FILE_NOT_FOUND")
            if not directory and creation == 1 and error in (80, 183):
                raise StorageError(409, "STORAGE_CONFLICT")
            raise StorageError()
        return handle

    def close(self, handle):
        self.kernel.CloseHandle(handle)

    def check(self, handle, path, *, directory):
        info = self.FileInfo()
        if not self.kernel.GetFileInformationByHandle(handle, self.ctypes.byref(info)):
            raise StorageError()
        if (info.dwFileAttributes & 0x400 or bool(info.dwFileAttributes & 0x10) != directory
            or (not directory and info.nNumberOfLinks != 1)):
            raise StorageError()
        buffer = self.ctypes.create_unicode_buffer(32_768)
        size = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not 0 < size < len(buffer):
            raise StorageError()
        final = buffer.value
        if final.startswith("\\\\?\\"):
            final = final[4:]
        if os.path.normcase(final) != os.path.normcase(str(path)):
            raise StorageError()
        return info

    def write(self, handle, data):
        from ctypes import wintypes
        for offset in range(0, len(data), 65_536):
            chunk = data[offset:offset + 65_536]
            buffer = self.ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if (not self.kernel.WriteFile(handle, buffer, len(chunk), self.ctypes.byref(written), None)
                or written.value != len(chunk)):
                raise StorageError()
        if not self.kernel.FlushFileBuffers(handle):
            raise StorageError()

    def read(self, handle, size):
        from ctypes import wintypes
        remaining = size + 1
        parts = []
        while remaining:
            buffer = self.ctypes.create_string_buffer(min(remaining, 65_536))
            count = wintypes.DWORD()
            if not self.kernel.ReadFile(handle, buffer, len(buffer), self.ctypes.byref(count), None):
                raise StorageError()
            if count.value == 0:
                break
            parts.append(buffer.raw[:count.value])
            remaining -= count.value
        return b"".join(parts)

    def delete(self, handle):
        # FILE_DISPOSITION_INFO.DeleteFile is a one-byte BOOLEAN, not Win32 BOOL.
        disposition = self.ctypes.c_ubyte(True)
        if not self.kernel.SetFileInformationByHandle(handle, 4, self.ctypes.byref(disposition),
                                                      self.ctypes.sizeof(disposition)):
            raise StorageError()

    def discard(self, handle):
        try:
            self.delete(handle)
        except StorageError:
            pass  # An unregistered orphan remains inaccessible through the service.


__all__ = ["LocalStorageBackend"]
