"""Pytest plugin enforcing test environment and loopback-only networking."""

from __future__ import annotations

import ipaddress
import socket

from _test_environment_guard import validate_test_environment


validate_test_environment()


_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_ORIGINAL_CREATE_CONNECTION = socket.create_connection
_ORIGINAL_CONNECT = socket.socket.connect


def _is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return False

    if host.lower() == "localhost":
        return True

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _deny_external(host: object) -> None:
    if not _is_loopback(host):
        raise RuntimeError(
            "external network access is denied in clean-room tests"
        )


def _guarded_getaddrinfo(host, *args, **kwargs):
    _deny_external(host)
    return _ORIGINAL_GETADDRINFO(host, *args, **kwargs)


def _guarded_create_connection(address, *args, **kwargs):
    _deny_external(address[0])
    return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)


def _guarded_connect(sock, address):
    if isinstance(address, tuple):
        _deny_external(address[0])

    return _ORIGINAL_CONNECT(sock, address)


# Pytest loads this plugin before collecting test modules. Installing the
# guards at import time prevents collection-time provider calls as well as
# calls made while individual tests execute. The dedicated runner process
# exits after the selected test group, so no global host process is modified.
socket.getaddrinfo = _guarded_getaddrinfo
socket.create_connection = _guarded_create_connection
socket.socket.connect = _guarded_connect
