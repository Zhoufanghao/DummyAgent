"""真实终端输入回归；仅SDK使用本地fixture，不mock prompt、不请求API。"""

import contextlib
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import struct
import sys
import tempfile
import termios
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
MARKER = "__SDK_REQUEST__"
SDK_FIXTURE = '''"""Explicit test fixture: no network/API."""
import json
from types import SimpleNamespace as NS
print("__OPENAI_FIXTURE_READY__", flush=True)

class Message:
    content = "unit fixture answer"
    tool_calls = None

    def model_dump(self, **kwargs):
        return {"role": "assistant", "content": self.content}

class Completions:
    def create(self, **params):
        print("__SDK_REQUEST__" + json.dumps(params), flush=True)
        probabilities = NS(tokens=["续"], token_logprobs=[-0.2], top_logprobs=[{"续": -0.2}])
        return NS(choices=[NS(text="unit fixture answer", logprobs=probabilities,
                              message=Message(), finish_reason="stop")])

class OpenAI:
    def __init__(self, **kwargs):
        self.completions = Completions()
        self.chat = NS(completions=Completions())
'''


class Terminal:
    def __init__(self, stage, fixture):
        self.stage = stage
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
        environment = {**os.environ, "PYTHONPATH": str(fixture),
                       "DEEPSEEK_API_KEY": "unit-fixture-no-real-key",
                       "TERM": "xterm-256color", "PROMPT_TOOLKIT_NO_CPR": "1"}
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-u", str(ROOT / f"agent_v{stage}.py")], cwd=fixture,
                stdin=slave, stdout=slave, stderr=slave, env=environment)
        finally:
            os.close(slave)
        self.output = b""

    def read_for(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.master], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                break
            try:
                chunk = os.read(self.master, 65536)
            except OSError:
                break
            if not chunk:
                break
            self.output += chunk

    @property
    def text(self):
        return self.output.decode("utf-8", errors="replace")

    @property
    def requests(self):
        return [json.loads(match) for match in re.findall(MARKER + r"([^\r\n]+)\r?\n", self.text)]

    def wait_for(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            self.read_for(0.05)
        raise AssertionError(f"v{self.stage}: terminal timeout\n{self.text}")

    def ready(self):
        self.wait_for(lambda: "__OPENAI_FIXTURE_READY__" in self.text and "$" in self.text)

    def answered(self, count):
        self.wait_for(lambda: len(self.requests) == count and
                      "$" in self.text[self.text.rfind(MARKER):])

    def send(self, data):
        os.write(self.master, data)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=3)
        os.close(self.master)


class PasteTests(unittest.TestCase):
    @contextlib.contextmanager
    def terminal(self, stage):
        with tempfile.TemporaryDirectory(prefix="paste-sdk-fixture-") as folder:
            fixture = Path(folder)
            (fixture / "openai.py").write_text(SDK_FIXTURE, encoding="utf-8")
            terminal = Terminal(stage, fixture)
            try:
                terminal.ready()
                yield terminal
            finally:
                terminal.close()

    def user_input(self, stage, request):
        if stage == 0:
            return request["prompt"]
        if stage == 1:
            return request["prompt"].rsplit("用户：", 1)[1].rsplit("\n助手：", 1)[0]
        return request["messages"][-1]["content"]

    def test_all_stages_paste_is_one_submission_then_single_line_blank_and_eof_work(self):
        pasted = "第一行中文\n\n第二段：保留空行和换行。\n第三行。"
        clipboard = "第一行中文\r\n\r\n第二段：保留空行和换行。\n第三行。"
        for stage in range(6):
            with self.subTest(stage=stage), self.terminal(stage) as terminal:
                terminal.send(b"\x1b[200~" + clipboard.encode("utf-8") + b"\x1b[201~")
                terminal.read_for(0.2)
                self.assertEqual(terminal.requests, [], "paste must wait for a separate Enter")
                terminal.send(b"\r")
                terminal.answered(1)
                self.assertEqual(self.user_input(stage, terminal.requests[0]), pasted)

                terminal.send(b"   \r")
                terminal.read_for(0.1)
                self.assertEqual(len(terminal.requests), 1, "blank input must not call the SDK")
                terminal.send("普通单行追问\r".encode("utf-8"))
                terminal.answered(2)
                self.assertEqual(self.user_input(stage, terminal.requests[1]), "普通单行追问")

                terminal.send(b"\x04")
                terminal.wait_for(lambda: terminal.process.poll() is not None)
                self.assertEqual(terminal.process.returncode, 0)
                self.assertEqual(len(terminal.requests), 2)

    def test_all_stages_ctrl_c_discards_unsubmitted_input_and_exits(self):
        for stage in range(6):
            with self.subTest(stage=stage), self.terminal(stage) as terminal:
                terminal.send("尚未提交的中文".encode("utf-8") + b"\x03")
                terminal.wait_for(lambda: terminal.process.poll() is not None)
                self.assertEqual(terminal.process.returncode, 0)
                self.assertEqual(terminal.requests, [])


if __name__ == "__main__":
    unittest.main()
