"""从真实Git Tag临时导出并运行；学生不必使用Git命令。"""
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

TAGS = ("v0-token", "v1-memory", "v2-chat", "v3-tools", "v4-agent-loop", "v5-execution")
ROOT = Path(__file__).resolve().parent


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TAGS:
        print("用法：python run_stage.py TAG [agent.py参数]\n" + "\n".join(TAGS))
        return 2
    tag, *args = sys.argv[1:]
    # 输出/回放路径相对于教师的当前目录，而不是临时导出目录。
    for flag in ("--record", "--replay"):
        if flag in args:
            index = args.index(flag) + 1
            if index >= len(args):
                print(f"{flag}需要文件路径", file=sys.stderr)
                return 2
            args[index] = str(Path(args[index]).resolve())
    try:
        archive = subprocess.run(["git", "archive", tag], cwd=ROOT,
                                 check=True, capture_output=True).stdout
    except subprocess.CalledProcessError:
        print(f"无法读取Tag {tag}；请使用完整仓库（包含.git）。", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="agent-stage-") as directory:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(directory, filter="data")
        return subprocess.call([sys.executable, str(Path(directory) / "agent.py"), *args])


if __name__ == "__main__":
    raise SystemExit(main())
