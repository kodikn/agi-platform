import httpx
import pytest

from agi_platform.outbound import (
    DNSResolver,
    OutboundPolicy,
    OutboundSecurityError,
    SecureHTTPClient,
    validate_outbound_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://169.254.169.254",
        "file:///etc/passwd",
        "gopher://example.com",
    ],
)
def test_blocked_urls(url):
    with pytest.raises(OutboundSecurityError):
        validate_outbound_url(
            url, resolver=DNSResolver({"example.com": ["93.184.216.34"]})
        )


def test_dns_rebinding_blocked_by_resolution():
    with pytest.raises(OutboundSecurityError):
        validate_outbound_url(
            "https://safe.example",
            resolver=DNSResolver({"safe.example": ["127.0.0.1"]}),
        )


def test_redirect_to_private_ip_blocked():
    def handler(request):
        return httpx.Response(302, headers={"location": "http://10.0.0.1/private"})

    client = SecureHTTPClient(
        resolver=DNSResolver({"public.example": ["93.184.216.34"]}),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(OutboundSecurityError):
        client.get("https://public.example")


def test_oversized_response_invalid_content_type_and_redirect_loop():
    big = SecureHTTPClient(
        OutboundPolicy(max_response_bytes=3),
        DNSResolver({"public.example": ["93.184.216.34"]}),
        httpx.MockTransport(
            lambda r: httpx.Response(
                200, headers={"content-type": "text/plain"}, content=b"toolong"
            )
        ),
    )
    with pytest.raises(OutboundSecurityError):
        big.get("https://public.example")
    bad_type = SecureHTTPClient(
        resolver=DNSResolver({"public.example": ["93.184.216.34"]}),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, headers={"content-type": "application/octet-stream"}, content=b"x"
            )
        ),
    )
    with pytest.raises(OutboundSecurityError):
        bad_type.get("https://public.example")
    loop = SecureHTTPClient(
        OutboundPolicy(max_redirects=1),
        DNSResolver({"public.example": ["93.184.216.34"]}),
        httpx.MockTransport(
            lambda r: httpx.Response(
                302, headers={"location": "https://public.example/again"}
            )
        ),
    )
    with pytest.raises(OutboundSecurityError):
        loop.get("https://public.example")
