"""Xác định IP client thật (thuộc tính môi trường cho R5)."""
import ipaddress

from fastapi import Request

from . import config


def _networks(cidrs: list[str]):
    return [ipaddress.ip_network(c, strict=False) for c in cidrs]


_trusted = _networks(config.TRUSTED_PROXY_CIDRS)
_internal = _networks(config.INTERNAL_CIDRS)


def _in(ip: str, networks) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return any(addr in n for n in networks if n.version == addr.version)


def from_trusted_proxy(request: Request) -> bool:
    return bool(request.client) and _in(request.client.host, _trusted)


def client_ip(request: Request) -> str:
    """IP kết nối trực tiếp; nếu kết nối đến từ Kong thì lấy phần tử CUỐI của X-Forwarded-For
    (địa chỉ do chính Kong ghi vào), nên client không giả mạo được bằng cách tự gửi header này."""
    peer = request.client.host if request.client else ""
    if _in(peer, _trusted):
        xff = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if xff:
            peer = xff[-1]
    try:
        addr = ipaddress.ip_address(peer)
        if addr.version == 6 and addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
    except ValueError:
        pass
    return peer


def is_internal(ip: str) -> bool:
    return _in(ip, _internal)
