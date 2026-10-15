"""录制真实性的结构检查：请求必须是当时的快照，回放不得导入SDK。"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from common import EVENTS, call


class RecordingTests(unittest.TestCase):
    def test_request_is_snapshot(self):
        class Response:
            def model_dump(self, **kwargs):
                return {"id": "unit-test-fixture"}
        def fake(**kwargs):
            return Response()
        EVENTS.clear()
        messages = [{"role": "user", "content": "first"}]
        call(fake, messages=messages)
        messages.append({"role": "assistant", "content": "later"})
        self.assertEqual(len(EVENTS[0]["request"]["messages"]), 1)

    def test_replay_uses_standard_library_only(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "recordings" / "v0-token.json"
        # -S禁止site-packages；因此成功就证明回放不需要SDK。
        result = subprocess.run([sys.executable, "-S", str(root / "run_stage.py"),
                                 "v0-token", "--replay", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("回放 REPLAY", result.stdout)
        self.assertIn("不请求API、不执行工具", result.stdout)


if __name__ == "__main__":
    unittest.main()
