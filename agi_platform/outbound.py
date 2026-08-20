from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

UNSAFE_SCHEMES = {"file", "gopher", "ftp", "dict", "sftp", "tftp"}
BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
METADATA_IPS = {"169.254.169.254", "100.100.100.200"}


class OutboundSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class OutboundPolicy:
    allowed_schemes: frozenset[str] = frozenset({"http", "https"})
    allowed_domains: frozenset[str] = frozenset()
    allowed_content_types: frozenset[str] = frozenset(
        {"application/json", "text/plain", "text/html"}
    )
    max_redirects: int = 3
    max_response_bytes: int = 2 * 1024 * 1024
    connect_timeout: float = 2.0
    read_timeout: float = 5.0
    total_timeout: float = 10.0

    def allows_domain(self, host: str) -> bool:
        if not self.allowed_domains:
            return True
        return any(
            host == domain or host.endswith(f".{domain}")
            for domain in self.allowed_domains
        )


@dataclass
class DNSResolver:
    overrides: dict[str, list[str]] = field(default_factory=dict)

    def resolve(self, host: str, port: int) -> list[str]:
        if host in self.overrides:
            return self.overrides[host]
        return [
            str(info[4][0])
            for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ]


def validate_outbound_url(
    url: str, policy: OutboundPolicy | None = None, resolver: DNSResolver | None = None
) -> str:
    policy = policy or OutboundPolicy()
    resolver = resolver or DNSResolver()
    parsed = urlparse(url)
    if parsed.scheme in UNSAFE_SCHEMES or parsed.scheme not in policy.allowed_schemes:
        raise OutboundSecurityError("outbound URL scheme is not allowed")
    if not parsed.hostname:
        raise OutboundSecurityError("outbound URL host is required")
    host = parsed.hostname.strip().lower().rstrip(".")
    if host in BLOCKED_HOSTS or not policy.allows_domain(host):
        raise OutboundSecurityError("outbound URL host is blocked")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = resolver.resolve(host, port)
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            address in METADATA_IPS
            or ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise OutboundSecurityError("outbound URL resolves to a blocked network")
    return url


class SecureHTTPClient:
    def __init__(
        self,
        policy: OutboundPolicy | None = None,
        resolver: DNSResolver | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.policy = policy or OutboundPolicy()
        self.resolver = resolver or DNSResolver()
        self.transport = transport

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        current_url = validate_outbound_url(url, self.policy, self.resolver)
        deadline = time.monotonic() + self.policy.total_timeout
        redirects = 0
        timeout = httpx.Timeout(
            self.policy.read_timeout, connect=self.policy.connect_timeout
        )
        while True:
            if time.monotonic() > deadline:
                raise httpx.TimeoutException("secure outbound total timeout exceeded")
            with httpx.Client(
                timeout=timeout, follow_redirects=False, transport=self.transport
            ) as client:
                response = client.request(method, current_url, **kwargs)
            if response.is_redirect:
                redirects += 1
                if redirects > self.policy.max_redirects:
                    raise OutboundSecurityError("redirect limit exceeded")
                location = response.headers.get("location")
                if not location:
                    raise OutboundSecurityError("redirect missing location")
                current_url = str(httpx.URL(current_url).join(location))
                current_url = validate_outbound_url(
                    current_url, self.policy, self.resolver
                )
                continue
            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            if (
                self.policy.allowed_content_types
                and content_type
                and content_type not in self.policy.allowed_content_types
            ):
                raise OutboundSecurityError("response content type is not allowed")
            if len(response.content) > self.policy.max_response_bytes:
                raise OutboundSecurityError("response exceeds maximum allowed size")
            return response

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)
