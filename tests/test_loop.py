"""用明确的 SDK fixture 验证循环观察、完成条件和失败边界。"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_interactive import answer, fake_client, load_stage, tool_answer


LOOP_TAGS = ("v4-agent-loop", "v5-execution")


class LoopTests(unittest.TestCase):
    @contextlib.contextmanager
    def loop(self, tag, replies, limit=3):
        with load_stage(tag) as stage, tempfile.TemporaryDirectory(prefix="loop-fixture-") as folder:
            client, requests = fake_client(replies)
            messages = [{"role": "system", "content": "单元测试 fixture"},
                        {"role": "user", "content": "执行测试任务"}]
            stream = io.StringIO()
            with patch.object(stage.agent, "MAX_ITERATIONS", limit), \
                    patch.object(stage.agent, "execute", return_value={"ok": True, "value": 5}) as execute, \
                    contextlib.redirect_stdout(stream):
                def run():
                    if tag == "v5-execution":
                        return stage.agent.agent_loop(client, messages, Path(folder))
                    return stage.agent.agent_loop(client, messages)
                yield run, requests, messages, execute, stream

    def test_observation_is_in_next_request(self):
        for tag in LOOP_TAGS:
            with self.subTest(tag=tag), self.loop(tag, [tool_answer("fixture-first"), answer("5")]) as fixture:
                run, requests, messages, execute, _ = fixture
                run()
                self.assertEqual(len(requests), 2)
                self.assertEqual(requests[1]["messages"][-1]["tool_call_id"], "fixture-first")
                self.assertEqual(json.loads(requests[1]["messages"][-1]["content"]), {"ok": True, "value": 5})
                self.assertEqual(messages[-1], {"role": "assistant", "content": "5"})
                execute.assert_called_once()

    def test_model_can_request_another_tool_after_observation(self):
        for tag in LOOP_TAGS:
            with self.subTest(tag=tag), self.loop(tag, [tool_answer("fixture-first"),
                                                       tool_answer("fixture-second"), answer("完成")]) as fixture:
                run, requests, _, execute, _ = fixture
                run()
                self.assertEqual(len(requests), 3)
                self.assertEqual(execute.call_count, 2)
                self.assertEqual(requests[2]["messages"][-1]["tool_call_id"], "fixture-second")

    def test_iteration_limit_never_reports_completion(self):
        for tag in LOOP_TAGS:
            with self.subTest(tag=tag), self.loop(tag, [tool_answer()], limit=1) as fixture:
                run, requests, messages, _, stream = fixture
                with self.assertRaisesRegex(RuntimeError, "最大迭代"):
                    run()
                self.assertEqual(len(requests), 1)
                self.assertNotIn("最终回答", stream.getvalue())
                self.assertEqual(messages[-1]["role"], "tool")

    def test_truncation_is_not_a_final_answer(self):
        for tag in LOOP_TAGS:
            with self.subTest(tag=tag), self.loop(tag, [answer("unfinished fixture", reason="length")]) as fixture:
                run, _, messages, execute, stream = fixture
                with self.assertRaisesRegex(RuntimeError, "截断|停止"):
                    run()
                execute.assert_not_called()
                self.assertEqual(len(messages), 2)
                self.assertNotIn("最终回答", stream.getvalue())

    def test_incomplete_or_excessive_tool_calls_are_never_executed(self):
        for tag in LOOP_TAGS:
            for reply in (tool_answer(reason="length"), tool_answer(count=5)):
                with self.subTest(tag=tag, reply=reply), self.loop(tag, [reply]) as fixture:
                    run, _, messages, execute, _ = fixture
                    with self.assertRaisesRegex(RuntimeError, "不完整|超限"):
                        run()
                    execute.assert_not_called()
                    self.assertEqual(len(messages), 2)

    def test_tool_failure_is_an_observation_the_model_can_recover_from(self):
        for tag in LOOP_TAGS:
            with self.subTest(tag=tag), self.loop(tag, [tool_answer("fixture-bad"),
                                                       tool_answer("fixture-retry"), answer("已修正")]) as fixture:
                run, requests, _, execute, _ = fixture
                execute.side_effect = [{"ok": False, "error": "fixture failure"}, {"ok": True, "value": 5}]
                run()
                self.assertFalse(json.loads(requests[1]["messages"][-1]["content"])["ok"])
                self.assertTrue(json.loads(requests[2]["messages"][-1]["content"])["ok"])


if __name__ == "__main__":
    unittest.main()
