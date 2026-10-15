"""离线交互回归：所有响应都是明确的单元 fixture，不请求 API 或执行 Bash。

默认检查真实教学 tags；重建 tags 时可设置 STAGE_DIR 及 STAGE_REFS(JSON映射)。
"""
import contextlib
import copy
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TAGS = ("v0-token", "v1-memory", "v2-chat", "v3-tools", "v4-agent-loop", "v5-execution")
MODULES = ("agent", "common", "tools", "lab", "sandbox")


class Message:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, **kwargs):
        result = {"role": "assistant"}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_calls:
            result["tool_calls"] = [
                {"id": call.id, "type": "function", "function": {
                    "name": call.function.name, "arguments": call.function.arguments}}
                for call in self.tool_calls
            ]
        return result


def answer(text="A102 · 单元测试 fixture"):
    probabilities = NS(tokens=["续"], token_logprobs=[-0.2], top_logprobs=[{"续": -0.2, "答": -2.0}])
    return NS(choices=[NS(finish_reason="stop", text=text, logprobs=probabilities,
                          message=Message(text))])


def tool_answer(identifier="fixture-tool", name="calculator", arguments='{"expression":"2+3"}'):
    call = NS(id=identifier, function=NS(name=name, arguments=arguments))
    return NS(choices=[NS(finish_reason="tool_calls", message=Message(tool_calls=[call]))])


class InteractiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(os.environ.get("STAGE_DIR", ROOT)).resolve()
        cls.refs = json.loads(os.environ.get("STAGE_REFS", "{}"))
        cls.materialized = tempfile.TemporaryDirectory(prefix="interactive-tags-")
        cls.addClassCleanup(cls.materialized.cleanup)
        cls.directories = {}
        for tag in TAGS:
            directory = Path(cls.materialized.name) / tag
            directory.mkdir()
            directory = directory.resolve()
            archive = subprocess.run(
                ["git", "archive", cls.refs.get(tag, tag)], cwd=cls.repo,
                check=True, capture_output=True,
            ).stdout
            with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
                # These are this repository's committed teaching snapshots.
                for member in contents.getmembers():
                    destination = (directory / member.name).resolve()
                    if not destination.is_relative_to(directory) or member.issym() or member.islnk():
                        raise ValueError("unsafe path in stage archive")
                contents.extractall(directory, filter="data")
            cls.directories[tag] = directory

    @contextlib.contextmanager
    def stage(self, tag):
        previous = {name: sys.modules.pop(name, None) for name in MODULES}
        sys.path.insert(0, str(self.directories[tag]))
        try:
            common = importlib.import_module("common")
            agent = importlib.import_module("agent")
            yield NS(agent=agent, common=common)
        finally:
            sys.path.pop(0)
            for name, module in previous.items():
                sys.modules.pop(name, None)
                if module is not None:
                    sys.modules[name] = module

    def exercise(self, tag, inputs=(), replies=None, demo=False, **overrides):
        with self.stage(tag) as stage:
            args = NS(demo=demo, tokens=False, chat=False, calculator=False,
                      prompt=None, task=None, steps=12, max_iterations=100,
                      temperature=0, model="unit-test-fixture")
            vars(args).update(overrides)
            requests = []
            pending = iter(replies) if replies is not None else None

            def fake_call(method, **params):
                requests.append(copy.deepcopy(params))
                return next(pending) if pending is not None else answer()

            client = NS(completions=NS(create=object()),
                        chat=NS(completions=NS(create=object())))
            stream = io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(stream))
                stack.enter_context(patch.object(stage.agent, "call", side_effect=fake_call))
                keyboard = stack.enter_context(patch("builtins.input", side_effect=inputs))
                execute = None
                publish = None
                export = None
                if hasattr(stage.agent, "execute"):
                    execute = stack.enter_context(patch.object(
                        stage.agent, "execute", return_value={"ok": True, "value": 5}))
                if tag == "v5-execution":
                    sandbox = importlib.import_module("sandbox")
                    lab = importlib.import_module("lab")
                    stack.enter_context(patch.object(sandbox, "backend_status", return_value="unit-test-sandbox"))
                    publish = stack.enter_context(patch.object(lab, "publish"))
                    if hasattr(lab, "export_outputs"):
                        export = stack.enter_context(patch.object(lab, "export_outputs"))
                try:
                    stage.agent.main(client, args)
                except KeyboardInterrupt:
                    self.fail(f"{tag}: Ctrl-C should end the interaction cleanly")
            return NS(requests=requests, output=stream.getvalue(), keyboard=keyboard,
                      execute=execute, publish=publish, export=export)

    def test_defaults_are_interactive_and_allow_100_iterations(self):
        for tag in TAGS:
            with self.subTest(tag=tag), self.stage(tag) as stage:
                args = stage.common.parse_args([])
                self.assertFalse(args.demo)
                self.assertEqual(args.max_iterations, 100)
                self.assertEqual(stage.common.parse_args(["--max-iterations", "150"]).max_iterations, 150)
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    stage.common.parse_args(["--max-iterations", "0"])

    def test_every_stage_accepts_two_custom_inputs_and_skips_blank(self):
        for tag in TAGS:
            with self.subTest(tag=tag):
                result = self.exercise(tag, [" \t ", "自定义第一题", "自定义第二题", ":quit"])
                self.assertEqual(len(result.requests), 2)
                for index, request in enumerate(result.requests):
                    question = request.get("prompt") or request["messages"][-1]["content"]
                    self.assertIn(("自定义第一题", "自定义第二题")[index], question)
                if result.publish is not None:
                    result.publish.assert_not_called()

    def test_quit_and_eof_do_not_request_a_model_response(self):
        for tag in TAGS:
            for inputs in ([":quit"], [EOFError()], [KeyboardInterrupt()]):
                with self.subTest(tag=tag, inputs=inputs):
                    self.assertEqual(self.exercise(tag, inputs).requests, [])

    def test_demo_uses_fixed_inputs_without_reading_stdin(self):
        for tag in TAGS:
            replies = None
            if tag == "v3-tools":
                replies = [answer(), tool_answer(), answer("5")]
            elif tag == "v4-agent-loop":
                replies = [answer(), tool_answer(), tool_answer("fixture-second"), answer("5")]
            elif tag == "v5-execution":
                replies = [tool_answer(name="bash", arguments='{"command":"cat data/temperature.csv"}'), answer()]
            with self.subTest(tag=tag):
                result = self.exercise(tag, [AssertionError("--demo must not read stdin")], replies, demo=True)
                result.keyboard.assert_not_called()
                self.assertGreater(len(result.requests), 0)

    def test_token_prefixes_are_independent_and_use_requested_notation(self):
        result = self.exercise("v0-token", ["第一段前缀", "第二段前缀", ":quit"])
        self.assertEqual([r["prompt"] for r in result.requests], ["第一段前缀", "第二段前缀"])
        self.assertIn("Pr[token | context]", result.output)
        self.assertNotIn("P(x_t | x_<t)", result.output)

    def test_memory_keeps_both_sides_and_reset_starts_fresh(self):
        result = self.exercise(
            "v1-memory", ["记住编号 Z987", "刚才编号是什么", ":reset", "新话题", ":quit"],
            [answer("已经记下 Z987"), answer("是 Z987"), answer("新的回答")],
        )
        self.assertEqual(len(result.requests), 3)
        self.assertIn("记住编号 Z987", result.requests[1]["prompt"])
        self.assertIn("已经记下 Z987", result.requests[1]["prompt"])
        self.assertNotIn("Z987", result.requests[2]["prompt"])
        self.assertIn("新话题", result.requests[2]["prompt"])

    def test_message_stages_keep_assistant_answers_and_reset(self):
        for tag in TAGS[2:]:
            with self.subTest(tag=tag):
                result = self.exercise(
                    tag, ["第一题", "第二题", ":reset", "新话题", ":quit"],
                    [answer("第一题的回答"), answer("第二题的回答"), answer("新的回答")],
                )
                self.assertEqual(len(result.requests), 3)
                history = result.requests[1]["messages"]
                self.assertEqual([m["role"] for m in history], ["system", "user", "assistant", "user"])
                self.assertEqual(history[2]["content"], "第一题的回答")
                fresh = result.requests[2]["messages"]
                self.assertEqual([m["role"] for m in fresh], ["system", "user"])
                self.assertEqual(fresh[-1]["content"], "新话题")

    def test_v3_pairs_tool_result_and_keeps_final_answer_for_next_question(self):
        result = self.exercise(
            "v3-tools", ["计算 2+3", "刚才结果是什么", ":quit"],
            [tool_answer("fixture-calc"), answer("工具结果是 5"), answer("上次是 5")],
        )
        self.assertEqual(len(result.requests), 3)
        result.execute.assert_called_once()
        observation = result.requests[1]["messages"][-1]
        self.assertEqual(observation["role"], "tool")
        self.assertEqual(observation["tool_call_id"], "fixture-calc")
        self.assertEqual(json.loads(observation["content"])["value"], 5)
        next_history = result.requests[2]["messages"]
        self.assertEqual(next_history[-2], {"role": "assistant", "content": "工具结果是 5"})
        self.assertEqual(next_history[-1], {"role": "user", "content": "刚才结果是什么"})

    def test_v3_does_not_repeat_tools_as_an_agent_loop(self):
        with self.assertRaisesRegex(RuntimeError, "回答|停止"):
            self.exercise(
                "v3-tools", ["计算 2+3", ":quit"],
                [tool_answer("fixture-first"), tool_answer("fixture-unexpected-second")],
            )

    def test_v4_iteration_limit_restarts_for_each_task(self):
        result = self.exercise(
            "v4-agent-loop", ["先算 2+3", "再算 2+3", ":quit"],
            [tool_answer("fixture-first"), answer("第一任务完成"),
             tool_answer("fixture-second"), answer("第二任务完成")], max_iterations=2,
        )
        self.assertEqual(len(result.requests), 4)
        self.assertEqual(result.execute.call_count, 2)
        self.assertEqual(result.requests[2]["messages"][-2]["content"], "第一任务完成")

    def test_v5_reuses_workspace_without_forcing_temperature_report(self):
        result = self.exercise(
            "v5-execution", ["查看 CSV", "列出目录", ":quit"],
            [tool_answer("fixture-read", "bash", '{"command":"cat data/temperature.csv"}'), answer("已读取"),
             tool_answer("fixture-list", "bash", '{"command":"ls"}'), answer("已列出")],
            max_iterations=2,
        )
        self.assertEqual(len(result.requests), 4)
        self.assertEqual(result.execute.call_count, 2)
        first_workspace = result.execute.call_args_list[0].args[1]
        second_workspace = result.execute.call_args_list[1].args[1]
        self.assertEqual(first_workspace, second_workspace)
        self.assertNotEqual(first_workspace, ROOT)
        result.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
