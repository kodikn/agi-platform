# Sandbox Threat Model

The local subprocess executor is not a production security boundary. Production sandboxing must run untrusted work in an isolated container or, for stronger tenant/adversarial isolation, a microVM such as Firecracker/Kata.

## Required production controls

* non-root user, read-only root filesystem, dropped Linux capabilities, seccomp, AppArmor/SELinux where available;
* ephemeral workspace only, no host mounts, no Docker socket, no host credentials, no cloud metadata credentials;
* PID, CPU, memory, disk, file descriptor, process, and wall-clock timeout limits;
* network disabled by default with explicit destination allowlists when needed;
* controlled artifact extraction by size, path, type, and digest;
* no access to host filesystem, `/sys`, dangerous `/proc` controls, Docker socket, cloud metadata IPs, localhost, RFC1918/internal networks, or unrestricted scanning.

If the threat model includes malicious code from another tenant, Docker alone may be insufficient; use a microVM with a minimal jailer, per-run image, no shared kernel attack surface assumptions, and strict egress policy.
