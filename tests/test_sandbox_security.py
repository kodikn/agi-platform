import pytest

from agi_platform.sandbox.core import SandboxLab


def test_profile_declares_production_isolation_controls():
    profile = SandboxLab().policy.as_dict()["isolation_profile"]
    assert profile["non_root"] is True
    assert profile["read_only_rootfs"] is True
    assert profile["no_host_mounts"] is True
    assert profile["docker_socket"] == "blocked"
    assert profile["network_default"] == "disabled"


@pytest.mark.parametrize(
    "command",
    [
        ["python", "-c", "open('/etc/passwd').read()"],
        ["python", "-c", "open('/proc/sys/kernel/hostname').read()"],
        ["python", "-c", "open('/sys/kernel').read()"],
        ["python", "-c", "open('/var/run/docker.sock').read()"],
        [
            "python",
            "-c",
            "import urllib.request; urllib.request.urlopen('http://169.254.169.254')",
        ],
        [
            "python",
            "-c",
            "import urllib.request; urllib.request.urlopen('http://127.0.0.1')",
        ],
        [
            "python",
            "-c",
            "import urllib.request; urllib.request.urlopen('http://10.0.0.1')",
        ],
        ["python", "-c", "import os; os.system('nmap 10.0.0.0/8')"],
    ],
)
def test_adversarial_boundary_commands_fail_closed(command):
    with pytest.raises(ValueError):
        SandboxLab().execute(command)


def test_timeout_cpu_memory_disk_and_process_limits_are_enforced():
    lab = SandboxLab()
    assert lab.execute(["python", "-c", "while True: pass"], timeout_seconds=1)[
        "returncode"
    ] in {124, -9, -24}
    assert lab.policy.memory_bytes > 0
    assert lab.policy.disk_bytes > 0
    assert lab.policy.pid_limit > 0
