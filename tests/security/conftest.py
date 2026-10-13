"""T03 security checks are offline and independent of M0 fixture imports."""

import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime_environment(monkeypatch):
    """A developer's live settings must not alter this test's deployment matrix."""
    import os

    for name in tuple(os.environ):
        if name.startswith("V2_") or name in {"DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY"}:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def deny_security_network(monkeypatch):
    """No DNS or external sockets, including tests outside backend/conftest.py."""
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def offline(sock, address, original=original):
            # Windows asyncio's socketpair uses a private loopback TCP pair.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("External network forbidden in T03 security tests")

        monkeypatch.setattr(socket.socket, name, offline)

    original_resolution = socket.getaddrinfo

    def offline_resolution(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_resolution(host, *args, **kwargs)
        raise AssertionError("External DNS forbidden in T03 security tests")

    monkeypatch.setattr(socket, "getaddrinfo", offline_resolution)
