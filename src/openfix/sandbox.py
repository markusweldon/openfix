"""Where repository code (tests, setup, scanners) runs.

The model never gets a shell. It can only ask for the commands the policy
defines (tests, rescan), and those run here: in a throwaway container with no
network by default, or - only when explicitly chosen - as a local process with
a scrubbed environment.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .redact import redact_text

MAX_OUTPUT = 200_000

_SAFE_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "USER", "SHELL", "SYSTEMROOT", "COMSPEC")
_SECRETY = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH", "SESSION", "COOKIE")


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def tail(self, limit: int = 6000) -> str:
        text = (self.stdout + ("\n" + self.stderr if self.stderr else "")).strip()
        return text if len(text) <= limit else "...(truncated)...\n" + text[-limit:]


class Sandbox(Protocol):
    kind: str

    def run(
        self, command: str, cwd: Path, timeout: int = 600, network: bool = False, image: str | None = None
    ) -> CommandResult: ...


def scrubbed_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _SAFE_ENV}
    env.update({"CI": "1", "NO_COLOR": "1", "OPENFIX_SANDBOX": "1"})
    for k, v in (extra or {}).items():
        if not any(s in k.upper() for s in _SECRETY):
            env[k] = v
    return env


def _clip(s: str) -> str:
    s = redact_text(s)
    return s if len(s) <= MAX_OUTPUT else s[: MAX_OUTPUT // 2] + "\n...(clipped)...\n" + s[-MAX_OUTPUT // 2 :]


class LocalSandbox:
    """Runs commands on this machine with secrets removed from the environment.

    This is NOT isolation. Use it on ephemeral CI runners or for repositories you trust.
    """

    kind = "local"

    def run(
        self,
        command: str,
        cwd: Path,
        timeout: int = 600,
        network: bool = False,
        image: str | None = None,
        passthrough: tuple[str, ...] = (),
    ) -> CommandResult:
        start = time.monotonic()
        env = scrubbed_env()
        env.update({k: os.environ[k] for k in passthrough if k in os.environ})
        proc = subprocess.Popen(
            ["/bin/sh", "-c", command] if os.name != "nt" else ["cmd", "/c", command],
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
            start_new_session=os.name != "nt",
        )
        timed_out = False
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:  # pragma: no cover
                proc.kill()
            out, err = proc.communicate()
        return CommandResult(
            command,
            proc.returncode if not timed_out else -9,
            _clip(out),
            _clip(err),
            round(time.monotonic() - start, 2),
            timed_out,
        )


class DockerSandbox:
    """Runs each command in a fresh container: workspace mounted at /work, no network by default,
    all capabilities dropped, no privilege escalation, memory/CPU/PID limits."""

    kind = "docker"

    def __init__(self, image: str, memory: str = "2g", cpus: str = "2", binary: str = "docker") -> None:
        self.image = image
        self.memory = memory
        self.cpus = cpus
        self.binary = binary

    def run(
        self, command: str, cwd: Path, timeout: int = 600, network: bool = False, image: str | None = None
    ) -> CommandResult:
        argv = [
            self.binary,
            "run",
            "--rm",
            "-i",
            "--network",
            "bridge" if network else "none",
            "--memory",
            self.memory,
            "--cpus",
            self.cpus,
            "--pids-limit",
            "1024",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "CI=1",
            "-e",
            "HOME=/tmp",
            "-e",
            "OPENFIX_SANDBOX=1",
            "-v",
            f"{Path(cwd).resolve()}:/work",
            "-w",
            "/work",
        ]
        if hasattr(os, "getuid"):
            argv += ["--user", f"{os.getuid()}:{os.getgid()}"]
        argv += [image or self.image, "sh", "-c", command]
        start = time.monotonic()
        try:
            res = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout + 30,
                stdin=subprocess.DEVNULL,
                env=scrubbed_env(),
            )
            return CommandResult(
                command, res.returncode, _clip(res.stdout), _clip(res.stderr), round(time.monotonic() - start, 2)
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command,
                -9,
                _clip(str(exc.stdout or "")),
                _clip(str(exc.stderr or "")),
                round(time.monotonic() - start, 2),
                timed_out=True,
            )


def default_image(repo: Path) -> str:
    if (repo / "package.json").exists():
        return "node:22-bookworm"
    if any((repo / f).exists() for f in ("pyproject.toml", "requirements.txt", "setup.py")):
        return "python:3.12-bookworm"
    if (repo / "go.mod").exists():
        return "golang:1.23-bookworm"
    if (repo / "Cargo.toml").exists():
        return "rust:1-bookworm"
    if (repo / "pom.xml").exists() or (repo / "build.gradle").exists():
        return "eclipse-temurin:21-jdk"
    return "debian:bookworm"


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class SandboxUnavailable(RuntimeError):
    pass


def make_sandbox(backend: str, repo: Path, image: str | None = None, memory: str = "2g", cpus: str = "2") -> Sandbox:
    if backend == "local":
        return LocalSandbox()
    if backend in ("docker", "auto"):
        if docker_available():
            return DockerSandbox(image or default_image(repo), memory=memory, cpus=cpus)
        if backend == "docker":
            raise SandboxUnavailable("sandbox.backend is 'docker' but Docker is not available")
        raise SandboxUnavailable(
            "Docker is not available, so OpenFix cannot isolate the repository's tests. "
            "Start Docker, or pass --sandbox local to run them on this machine (only for trusted code "
            "or ephemeral CI runners)."
        )
    raise SandboxUnavailable(f"Unknown sandbox backend '{backend}'")
