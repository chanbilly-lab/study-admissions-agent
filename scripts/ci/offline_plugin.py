"""Pytest process guard: allow only local sockets, including local PG/HTTP."""
import ipaddress
import socket


def _local(address):
    if isinstance(address, tuple):
        try:
            return ipaddress.ip_address(address[0]).is_loopback
        except (ValueError, TypeError):
            return False
    return isinstance(address, (str, bytes))  # AF_UNIX local sockets.


def pytest_sessionstart(session):
    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def guarded_connect(sock, address):
        if not _local(address):
            raise AssertionError("CI_OUTBOUND_NETWORK_FORBIDDEN")
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        if not _local(address):
            raise AssertionError("CI_OUTBOUND_NETWORK_FORBIDDEN")
        return connect_ex(sock, address)

    def guarded_resolution(host, *args, **kwargs):
        if host not in {None, "localhost", "127.0.0.1", "::1", b"localhost", b"127.0.0.1", b"::1"}:
            raise AssertionError("CI_OUTBOUND_DNS_FORBIDDEN")
        return getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.getaddrinfo = guarded_resolution
