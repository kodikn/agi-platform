import pytest

from agi_platform.security import validate_outbound_url


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "http://localhost", "http://127.0.0.1", "http://169.254.169.254/latest/meta-data", "http://10.0.0.1"])
def test_ssrf_policy_blocks_internal_and_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_outbound_url(url)
