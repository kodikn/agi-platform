# Secure Outbound HTTP

All external HTTP integrations must use `SecureHTTPClient`. It validates URL schemes, DNS resolution before connection, redirect destinations, blocked IP ranges, metadata services, domain allowlists, response size, content type, connection/read/total timeouts, and redirect limits.

Blocked by default: localhost, loopback, RFC1918, link-local, cloud metadata IPs, IPv6 local/private/reserved ranges, `file://`, `gopher://`, `ftp://`, and unsafe schemes.
