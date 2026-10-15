"""v5 Bash tool. OS policy is the boundary; command filters are only UX.

Only a disposable temp directory is accepted. Never fall back to host execution.
macOS uses Seatbelt; other platforms need a local Docker daemon + cached image.
"""

import functools
import json
import math
import os
from pathlib import Path
import re
import resource
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


IMAGE = "python:3.12-slim"
OUTPUTS = ("analysis.py", "result.json", "report.md")
MAX_FILE_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 16 * 1024
MAX_COMMAND_CHARS = 8192


def validate_workspace(path):
    """Reject repository/home roots, links, and unexpected writable artifacts."""
    original = Path(path).absolute()
    workspace = original.resolve(strict=True)
    temp_roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    if original.is_symlink() or not workspace.is_dir():
        raise ValueError("workspace must be a real disposable directory")
    if not any(workspace != root and workspace.is_relative_to(root)
               for root in temp_roots):
        raise ValueError("workspace must be a subdirectory of the system temp directory")
    expected = {"data", "data/temperature.csv", *OUTPUTS}
    paths = list(workspace.rglob("*"))
    if len(paths) > len(expected):
        raise ValueError("unexpected workspace files")
    for path in paths:
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink() or relative not in expected:
            raise ValueError("workspace contains an unexpected path or symbolic link")
        if path.is_file() and path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("workspace file is too large")
        if path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("workspace files must not be hard-linked")
        if not path.is_file() and relative != "data":
            raise ValueError("workspace contains an unexpected directory")
    return workspace


def _check_command(command):
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command must be a nonempty string")
    if len(command) > MAX_COMMAND_CHARS or "\x00" in command:
        raise ValueError("command exceeds the size limit or contains NUL")
    # These checks make common mistakes legible. Python can construct arbitrary
    # strings, so no security claim relies on detecting all dangerous text.
    forbidden = r"(?m)(?:^|[;&|])\s*(?:sudo|su|rm|rmdir|mv|chmod|chown|kill|killall|shutdown|reboot|mount|umount|curl|wget|ssh|scp|nc|osascript|launchctl|open|eval|exec|cd)(?:\s|$)"
    if re.search(forbidden, command):
        raise ValueError("command contains an operation outside the classroom allowlist")
    if re.search(r"\$\(|`|\|\s*(?:sh|bash)|(?:^|\s)&(?:\s|$)|:\s*\(\s*\)", command):
        raise ValueError("background processes, command substitution, and shell nesting are disabled")


def _single_command(command):
    """Normalize a literal Python heredoc, then exec one foreground executable.

    Bash normally forks and writes a temporary file for heredocs. Passing the
    same literal source through -c lets the shell exec Python with no fork.
    """
    heredoc = re.fullmatch(
        r"\s*python3\s+-\s+<<\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1\s*\n(.*?)\n\2\s*",
        command, re.DOTALL)
    if heredoc:
        args = ["python3", "-c", heredoc.group(3)]
    else:
        args = shlex.split(command)
    allowed = {"python3", "ls", "cat", "pwd", "head", "wc", "printf", "echo"}
    if not args or args[0] not in allowed:
        raise ValueError("use one of: python3, ls, cat, pwd, head, wc, printf, echo")
    if any(arg in {";", "&&", "||", "|", "&", ">", ">>", "<", "<<"} for arg in args):
        raise ValueError("use one foreground command per tool call; no pipes or redirection")
    return "exec " + shlex.join(args)


def _mac_command(command, workspace):
    # Paths are quoted with JSON, which also quotes strings in Seatbelt profiles.
    # Never allow all of /System: /System/Volumes/Data aliases host user files.
    readable = ["/usr/bin", "/usr/lib", "/usr/share", "/System/Library",
                "/System/Volumes/Preboot/Cryptexes/OS", "/bin", "/sbin", str(workspace)]
    base = Path(sys.base_prefix).resolve()
    if str(base).startswith("/opt/homebrew/"):
        readable += ["/opt/homebrew/Cellar", "/opt/homebrew/opt"]
    elif not str(base).startswith(("/usr/", "/System/")):
        readable.append(str(base))
    read_rules = " ".join(f"(subpath {json.dumps(p)})" for p in readable)
    write_rules = " ".join(f"(literal {json.dumps(str(workspace / name))})"
                           for name in OUTPUTS)
    profile = f"""(version 1)
      (deny default)
      (allow process-exec)
      (allow file-read-metadata)
      (allow file-read* {read_rules} (literal "/")
        (literal "/dev/null") (literal "/dev/random") (literal "/dev/urandom"))
      (allow file-write* {write_rules} (literal "/dev/null"))
    """
    # process-fork, network, Mach services, and all other file writes stay denied.
    return ["/usr/bin/sandbox-exec", "-p", profile,
            "/bin/bash", "--noprofile", "--norc", "-c", command]


def _docker_command(command, workspace, name):
    args = ["docker", "run", "--rm", "--name", name, "--network=none",
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--pids-limit=1", "--memory=128m", "--cpus=1", "--pull=never",
            "--ulimit", f"fsize={MAX_FILE_BYTES}:{MAX_FILE_BYTES}",
            "--ulimit", "nofile=64:64", "--user", f"{os.getuid()}:{os.getgid()}",
            "--workdir=/lab", "--env", "HOME=/lab", "--env", "LANG=C.UTF-8",
            "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONNOUSERSITE=1",
            "--mount", f"type=bind,src={workspace / 'data'},dst=/lab/data,readonly"]
    # Read-only container root + three individual writable file mounts bounds
    # persistent output size; the host directory itself is never mounted writable.
    for filename in OUTPUTS:
        path = workspace / filename
        path.touch(exist_ok=True)
        args += ["--mount", f"type=bind,src={path},dst=/lab/{filename}"]
    return args + [IMAGE, "bash", "--noprofile", "--norc", "-c", command]


def _limits(timeout):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(timeout) + 1,) * 2)


def _capture(args, workspace, timeout, *, docker=False):
    """Bound capture while the process runs, not after buffering arbitrary output."""
    python_bin = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve().parent)
    environment = {"PATH": python_bin + ":/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                   "HOME": str(workspace), "PWD": str(workspace), "LANG": "en_US.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    # Docker client may need its local context. No host environment is forwarded
    # into the container; the container environment is explicit above.
    if docker:
        environment = os.environ.copy()
    process = subprocess.Popen(args, cwd=workspace, env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True,
                               preexec_fn=lambda: _limits(timeout))
    output = bytearray()
    error = None
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = "timeout"
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        break
                    output.extend(chunk[:MAX_OUTPUT_BYTES - len(output)])
                    if len(output) >= MAX_OUTPUT_BYTES:
                        error = "output_limit"
                        break
                if error:
                    break
        if not error:
            try:
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                error = "timeout"
    except BaseException:
        # Stop and reap the isolated process before main exports its workspace.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()
        raise
    if error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()
    process.stdout.close()
    result = {"exit_code": process.returncode,
              "output": output.decode("utf-8", errors="replace")}
    if error:
        result["error"] = error
    return result


@functools.lru_cache(maxsize=1)
def backend_status():
    """Return an actually probed backend name, or a fail-closed explanation."""
    if shutil.which("docker"):
        try:
            check = subprocess.run(["docker", "image", "inspect", IMAGE],
                                   capture_output=True, timeout=5)
            if check.returncode == 0:
                return "docker"
        except (OSError, subprocess.TimeoutExpired):
            pass
    if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").exists():
        with tempfile.TemporaryDirectory(prefix="agent-probe-") as folder:
            workspace = Path(folder).resolve()
            try:
                result = _capture(_mac_command("printf seatbelt-ok", workspace), workspace, 3)
                if result["exit_code"] == 0 and result["output"] == "seatbelt-ok":
                    return "macos-seatbelt"
            except OSError:
                pass
        return "unavailable: macOS denied sandbox-exec (nested sandbox or unsupported OS)"
    return f"unavailable: install/start local Docker and pre-pull {IMAGE}"


def run_bash(command: str, workspace: Path, timeout: int = 8) -> dict:
    """Execute one foreground command; always use an OS-isolated backend.

    Available persistent outputs: analysis.py, result.json, report.md. Input:
    data/temperature.csv. Prefer one `python3 - <<'PY' ... PY` per tool call.
    """
    name = None
    try:
        _check_command(command)
        command = _single_command(command)
        workspace = validate_workspace(workspace)
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 15:
            raise ValueError("timeout must be between 0 and 15 seconds")
        backend = backend_status()
        if backend.startswith("unavailable"):
            return {"error": "sandbox_unavailable", "detail": backend}
        if backend == "docker":
            name = f"agent-lab-{os.getpid()}-{time.monotonic_ns()}"
            args = _docker_command(command, workspace, name)
        else:
            args = _mac_command(command, workspace)
        result = _capture(args, workspace, timeout, docker=backend == "docker")
        result["backend"] = backend
        validate_workspace(workspace)  # Check persisted artifact types and sizes again.
        return result
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        return {"error": "sandbox_rejected", "detail": str(error)}
    finally:
        if name:
            # Killing `docker run` alone does not stop its container.
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=5)


BASH = {"type": "function", "function": {
    "name": "bash", "description": "在禁网隔离实验目录执行一个前台命令。可用python3、ls、cat、pwd、head、wc、printf、echo。支持python3 - <<'PY'\n代码\nPY；不支持管道、shell重定向、cd、后台或子进程。数据只读；仅可写analysis.py、result.json、report.md。8秒超时。",
    "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                   "required": ["command"], "additionalProperties": False}}}

SOURCE = Path(__file__).resolve().parent / "data" / "temperature.csv"


def seed(workspace):
    (workspace / "data").mkdir()
    shutil.copyfile(SOURCE, workspace / "data" / "temperature.csv")


def export_outputs(workspace):
    """自由任务只做文件安全检查，不强制CSV报告格式或统计目标。"""
    validate_workspace(workspace)
    names = [name for name in ("analysis.py", "result.json", "report.md")
             if (workspace / name).is_file() and (workspace / name).stat().st_size]
    if not names:
        return None
    root = Path.cwd() / "lab-runs"
    root.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    for name in names:
        shutil.copyfile(workspace / name, destination / name)
    print(f"[已安全导出产物] {destination}；文件：{', '.join(names)}")
    return destination


def execute(tool_call, workspace):
    """验证 Bash 请求；执行失败也作为工具观察返回给模型。"""
    try:
        if tool_call.function.name != "bash":
            raise ValueError("未知工具")
        if len(tool_call.function.arguments) > MAX_COMMAND_CHARS:
            raise ValueError("参数过长")
        arguments = json.loads(tool_call.function.arguments)
        if not isinstance(arguments, dict) or set(arguments) != {"command"}:
            raise ValueError("参数必须且只能包含command")
        result = run_bash(arguments["command"], workspace, timeout=8)
        return {"ok": result.get("exit_code") == 0 and not result.get("error"), **result}
    except (ValueError, TypeError, RecursionError) as error:
        return {"ok": False, "error": str(error)[:300]}
