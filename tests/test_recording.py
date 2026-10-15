"""教师录制回归；所有响应均为明确的unit fixture，不请求API。"""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import preflight
import verify_live


def token_events(reason="length"):
    return [{"endpoint": "completions.create", "request": {"prompt": prompt},
             "response": {"id": f"unit-fixture-{index}", "model": "unit-fixture-model",
                          "choices": [{"finish_reason": reason, "text": "fixture continuation",
                                       "logprobs": {"tokens": ["续"], "token_logprobs": [-0.2],
                                                    "top_logprobs": [{"续": -0.2, "答": -2.0}]}}]},
             "elapsed_seconds": 0.001}
            for index, prompt in enumerate(verify_live.SCENARIOS["v0-token"])]


class RecordingTests(unittest.TestCase):
    def test_namespaced_defaults_remain_under_partial_candidate_mapping(self):
        with patch.dict(os.environ, {"DUMMY_AGENT_STAGE_REFS": '{"v0-token":"candidate-fixture"}'}):
            refs = verify_live.stage_refs()
        self.assertEqual(refs["v0-token"], "candidate-fixture")
        self.assertEqual(refs["v5-execution"], "teaching-cleanup/v5-execution")
        self.assertEqual(set(refs), set(verify_live.STAGES))

    def test_request_is_snapshot_and_endpoints_are_distinct(self):
        class Response:
            def model_dump(self, **kwargs):
                return {"id": "unit-test-fixture"}

        client = NS(completions=NS(create=lambda **params: Response()),
                    chat=NS(completions=NS(create=lambda **params: Response())))
        recorder = verify_live.RecordingClient(client)
        messages = [{"role": "user", "content": "first"}]
        recorder.chat.completions.create(messages=messages)
        messages.append({"role": "assistant", "content": "later"})
        recorder.completions.create(prompt="fixture")
        self.assertEqual(len(recorder.events[0]["request"]["messages"]), 1)
        self.assertEqual([event["endpoint"] for event in recorder.events],
                         ["chat.completions.create", "completions.create"])

    def test_teacher_import_does_not_require_sdk_or_legacy_modules(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-S", "-c", "import preflight, verify_live"],
                                cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_token_length_is_expected_but_chat_truncation_is_rejected(self):
        verify_live.validate_events("v0-token", token_events(), verify_live.SCENARIOS["v0-token"])
        with self.assertRaisesRegex(ValueError, "截断"):
            verify_live.validate_events("v2-chat", token_events(), verify_live.SCENARIOS["v2-chat"])

    def test_recording_is_bound_to_agent_tools_and_commit(self):
        with tempfile.TemporaryDirectory(prefix="recording-unit-fixture-") as folder:
            directory = Path(folder)
            (directory / "agent.py").write_text("# explicitly marked unit fixture\n")
            (directory / "tools.py").write_text("# tools unit fixture\n")
            hashes = verify_live.runtime_hashes(directory)
            recording = {"kind": "live-api-recording", "stage": "v0-token",
                         "source_sha256": hashes["agent.py"], "runtime_sha256": hashes,
                         "source_commit": "unit-fixture-commit", "mode": "interactive",
                         "inputs": list(verify_live.SCENARIOS["v0-token"]),
                         "recorded_at": "unit-fixture-not-a-live-run", "transcript": "unit fixture",
                         "model_requested": "unit-fixture-model", "events": token_events()}
            path = directory / "recording.json"
            verify_live.save_recording(path, recording)
            self.assertEqual(preflight.check_recording(directory, "v0-token", "unit-fixture-commit", path),
                             recording)
            with self.assertRaisesRegex(ValueError, "提交"):
                preflight.check_recording(directory, "v0-token", "different-commit", path)
            (directory / "tools.py").write_text("# changed unit fixture\n")
            with self.assertRaisesRegex(ValueError, "运行文件"):
                preflight.check_recording(directory, "v0-token", "unit-fixture-commit", path)
            self.assertEqual([entry.name for entry in directory.glob(".recording-*")], [])

    def test_failed_live_validation_does_not_write_a_recording_or_print_key(self):
        fake_sdk = NS(OpenAI=lambda **kwargs: contextlib.nullcontext(NS()))
        with tempfile.TemporaryDirectory(prefix="recording-failure-fixture-") as folder:
            destination = Path(folder) / "new-recordings"
            output = io.StringIO()
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "UNIT-SECRET-MUST-NOT-PRINT",
                                         "DUMMY_AGENT_STAGE_REFS": "{}"}), \
                    patch.dict(sys.modules, {"openai": fake_sdk}), \
                    patch.object(verify_live, "verify_stage", side_effect=ValueError("unit fixture failure")), \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                result = verify_live.main(["--stage", "v0-token", "--output-dir", str(destination)])
            self.assertEqual(result, 1)
            self.assertFalse(destination.exists())
            self.assertNotIn("UNIT-SECRET-MUST-NOT-PRINT", output.getvalue())

    def test_memory_answers_must_preserve_the_real_identifier(self):
        questions = verify_live.SCENARIOS["v1-memory"]
        events = [{"request": {"prompt": questions[0]}, "response": {
            "id": "unit-fixture-1", "model": "unit-fixture-model",
            "choices": [{"finish_reason": "stop", "text": "记住了A102"}]}},
            {"request": {"prompt": questions[0] + "记住了A102" + questions[1]}, "response": {
                "id": "unit-fixture-2", "model": "unit-fixture-model",
                "choices": [{"finish_reason": "stop", "text": "编号是A102"}]}}]
        verify_live.validate_events("v1-memory", events, questions)
        events[1]["response"]["choices"][0]["text"] = "不记得"
        with self.assertRaisesRegex(ValueError, "A102"):
            verify_live.validate_events("v1-memory", events, questions)

    def test_v5_accepts_separate_successful_result_and_report_reads(self):
        questions = verify_live.SCENARIOS["v5-execution"]
        messages = [{"role": "system", "content": "unit fixture"},
                    {"role": "user", "content": questions[0]}]
        events = []

        def tool(command):
            identifier = f"unit-fixture-call-{len(events)}"
            call = {"id": identifier, "type": "function", "function": {
                "name": "bash", "arguments": json.dumps({"command": command})}}
            message = {"role": "assistant", "tool_calls": [call]}
            events.append({"request": {"messages": copy.deepcopy(messages)}, "response": {
                "id": identifier, "model": "unit-fixture-model", "choices": [
                    {"finish_reason": "tool_calls", "message": message}]}})
            messages.extend([message, {"role": "tool", "tool_call_id": identifier,
                                      "content": '{"ok":true,"exit_code":0,"output":"unit fixture"}'}])

        def answer():
            message = {"role": "assistant", "content": "unit fixture final answer"}
            events.append({"request": {"messages": copy.deepcopy(messages)}, "response": {
                "id": f"unit-fixture-answer-{len(events)}", "model": "unit-fixture-model", "choices": [
                    {"finish_reason": "stop", "message": message}]}})
            messages.append(message)

        for command in ("cat data/temperature.csv", "python3 analysis.py", "cat result.json", "cat report.md"):
            tool(command)
        answer()
        messages.append({"role": "user", "content": questions[1]})
        tool("cat result.json")
        tool("cat report.md")
        answer()
        verify_live.validate_events("v5-execution", events, questions)
        # An unsuccessful read is not evidence that the second-turn report was checked.
        events[-1]["request"]["messages"][-1]["content"] = '{"ok":false,"error":"fixture failure"}'
        with self.assertRaisesRegex(ValueError, "跨用户轮"):
            verify_live.validate_events("v5-execution", events, questions)


if __name__ == "__main__":
    unittest.main()
