"""teaching-cleanup 阶段源码的离线测试；fixture 不请求 API、不执行 Bash。

候选提交可用 DUMMY_AGENT_STAGE_REFS 的 JSON tag/ref 映射验证。
临时阶段目录可用 DUMMY_AGENT_STAGE_DIR 指定，其下按教学 tag 分目录。
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


@contextlib.contextmanager
def load_stage(tag):
    """Import the requested snapshot without leaking its tools into another stage."""
    with tempfile.TemporaryDirectory(prefix="test-agent-stage-") as temporary:
        base = os.environ.get("DUMMY_AGENT_STAGE_DIR")
        directory = Path(base) / tag if base else Path(temporary)
        if not (directory / "agent.py").is_file():
            directory = Path(temporary)
            refs = json.loads(os.environ.get("DUMMY_AGENT_STAGE_REFS", "{}"))
            archive = subprocess.run(
                ["git", "archive", refs.get(tag, f"teaching-cleanup/{tag}")], cwd=ROOT,
                check=True, capture_output=True,
            ).stdout
            with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
                contents.extractall(directory, filter="data")
        previous = {name: sys.modules.pop(name, None) for name in MODULES}
        sys.path.insert(0, str(directory))
        try:
            agent = importlib.import_module("agent")
            tools = importlib.import_module("tools") if (directory / "tools.py").exists() else None
            yield NS(agent=agent, tools=tools, directory=directory)
        finally:
            sys.path.pop(0)
            for name, module in previous.items():
                sys.modules.pop(name, None)
                if module is not None:
                    sys.modules[name] = module


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


def answer(text="单元测试 fixture", reason="stop"):
    probabilities = NS(tokens=["续"], token_logprobs=[-0.2], top_logprobs=[{"续": -0.2, "答": -2.0}])
    return NS(choices=[NS(finish_reason=reason, text=text, logprobs=probabilities,
                          message=Message(text))])


def tool_answer(identifier="fixture-tool", name="calculator", arguments='{"expression":"2+3"}',
                reason="tool_calls", count=1):
    calls = [NS(id=f"{identifier}-{index}" if count > 1 else identifier,
                function=NS(name=name, arguments=arguments)) for index in range(count)]
    return NS(choices=[NS(finish_reason=reason, message=Message(tool_calls=calls))])


def fake_client(replies=None):
    """Use the same SDK entry points as production and snapshot mutable messages."""
    requests = []
    pending = iter(replies) if replies is not None else None

    def create(**params):
        requests.append(copy.deepcopy(params))
        return next(pending) if pending is not None else answer()

    return NS(completions=NS(create=create), chat=NS(completions=NS(create=create))), requests


class InteractiveTests(unittest.TestCase):
    def exercise(self, tag, inputs=(), replies=None, limit=None):
        with load_stage(tag) as stage:
            client, requests = fake_client(replies)
            stream = io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(stream))
                keyboard = stack.enter_context(patch("builtins.input", side_effect=[*inputs, EOFError()]))
                if limit is not None:
                    stack.enter_context(patch.object(stage.agent, "MAX_ITERATIONS", limit))
                execute = None
                export = None
                if hasattr(stage.agent, "execute"):
                    execute = stack.enter_context(patch.object(
                        stage.agent, "execute", return_value={"ok": True, "value": 5}))
                if tag == "v5-execution":
                    stack.enter_context(patch.object(stage.agent, "backend_status", return_value="unit-test-sandbox"))
                    export = stack.enter_context(patch.object(stage.agent, "export_outputs"))
                stage.agent.main(client)
            return NS(requests=requests, output=stream.getvalue(), keyboard=keyboard,
                      execute=execute, export=export)

    def test_each_stage_has_only_its_mechanism_and_no_compatibility_cli(self):
        for tag in TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                agent = stage.agent
                self.assertEqual(agent.MODEL, os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
                self.assertEqual(agent.TEMPERATURE, 0)
                for name in ("parse_args", "call", "token_demo", "chat_demo", "calculator_demo"):
                    self.assertFalse(hasattr(agent, name), f"{tag}: unnecessary {name}")
                self.assertFalse((stage.directory / "common.py").exists())
                if tag == "v0-token":
                    self.assertEqual(agent.TOKEN_STEPS, 12)
                else:
                    self.assertFalse(hasattr(agent, "complete_tokens"))
                if tag in TAGS[4:]:
                    self.assertEqual(agent.MAX_ITERATIONS, 100)
                if tag == "v5-execution":
                    self.assertFalse(hasattr(stage.tools, "calculator"))
                if tag in TAGS[:3]:
                    self.assertIsNone(stage.tools)

    def test_stage_runtime_depends_only_on_agent_and_tools(self):
        for tag in TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                local_modules = set()
                for module in list(sys.modules.values()):
                    filename = getattr(module, "__file__", None)
                    if filename:
                        path = Path(filename).resolve()
                        if path.is_relative_to(stage.directory.resolve()):
                            local_modules.add(path.relative_to(stage.directory.resolve()).as_posix())
                self.assertLessEqual(local_modules, {"agent.py", "tools.py"})

    def test_all_stages_skip_blanks_and_accept_two_custom_inputs(self):
        for tag in TAGS:
            with self.subTest(tag=tag):
                result = self.exercise(tag, [" \t ", "自定义第一题", "自定义第二题"])
                self.assertEqual(len(result.requests), 2)
                for index, request in enumerate(result.requests):
                    question = request.get("prompt") or request["messages"][-1]["content"]
                    self.assertIn(("自定义第一题", "自定义第二题")[index], question)
                self.assertTrue(all(call.args == ("$ ",) for call in result.keyboard.call_args_list))
                self.assertNotIn(":quit退出", result.output)
                self.assertNotIn(":reset清空", result.output)

    def test_eof_and_ctrl_c_end_without_model_calls(self):
        for tag in TAGS:
            for ending in (EOFError(), KeyboardInterrupt()):
                with self.subTest(tag=tag, ending=type(ending).__name__):
                    result = self.exercise(tag, [ending])
                    self.assertEqual(result.requests, [])
                    if result.export is not None:
                        result.export.assert_called_once()

    def test_former_commands_are_normal_input(self):
        for tag in TAGS:
            with self.subTest(tag=tag):
                result = self.exercise(tag, [":quit", ":reset", "继续提问"])
                self.assertEqual(len(result.requests), 3)
                for index, text in enumerate((":quit", ":reset", "继续提问")):
                    request = result.requests[index]
                    submitted = request.get("prompt") or request["messages"][-1]["content"]
                    self.assertIn(text, submitted)
                if tag == "v1-memory":
                    self.assertIn(":quit", result.requests[2]["prompt"])
                elif tag != "v0-token":
                    history = result.requests[2]["messages"]
                    self.assertEqual(history[1]["content"], ":quit")
                    self.assertEqual(history[3]["content"], ":reset")

    def test_token_prefixes_are_independent_and_show_real_probabilities(self):
        result = self.exercise("v0-token", ["第一段前缀", "第二段前缀"])
        self.assertEqual([r["prompt"] for r in result.requests], ["第一段前缀", "第二段前缀"])
        self.assertEqual(result.requests[0]["logprobs"], 5)
        self.assertEqual(result.requests[0]["max_tokens"], 12)
        self.assertIn("Pr[token | context]", result.output)
        self.assertIn("81.8731%", result.output)
        self.assertNotIn("P(x_t | x_<t)", result.output)

    def test_token_stage_rejects_missing_logprobs(self):
        reply = answer()
        reply.choices[0].logprobs = None
        with self.assertRaisesRegex(RuntimeError, "logprobs"):
            self.exercise("v0-token", ["前缀"], [reply])

    def test_text_memory_keeps_both_sides(self):
        result = self.exercise("v1-memory", ["记住编号 Z987", "刚才编号是什么"],
                               [answer("已经记下 Z987"), answer("是 Z987")])
        self.assertIn("记住编号 Z987", result.requests[1]["prompt"])
        self.assertIn("已经记下 Z987", result.requests[1]["prompt"])
        self.assertEqual(result.requests[0]["stop"], ["\n用户："])

    def test_message_stages_keep_both_sides_and_roles(self):
        for tag in TAGS[2:]:
            with self.subTest(tag=tag):
                result = self.exercise(tag, ["第一题", "第二题"], [answer("第一题的回答"), answer("第二题的回答")])
                history = result.requests[1]["messages"]
                self.assertEqual([m["role"] for m in history], ["system", "user", "assistant", "user"])
                self.assertEqual(history[2]["content"], "第一题的回答")
                self.assertEqual(result.requests[0]["extra_body"], {"thinking": {"type": "disabled"}})

    def test_v3_fills_one_tool_result_then_answers_once(self):
        result = self.exercise("v3-tools", ["计算 2+3", "刚才结果是什么"],
                               [tool_answer("fixture-calc"), answer("工具结果是 5"), answer("上次是 5")])
        self.assertEqual(len(result.requests), 3)
        result.execute.assert_called_once()
        observation = result.requests[1]["messages"][-1]
        self.assertEqual(observation["role"], "tool")
        self.assertEqual(observation["tool_call_id"], "fixture-calc")
        self.assertEqual(json.loads(observation["content"])["value"], 5)
        self.assertNotIn("tools", result.requests[1])
        self.assertEqual(result.requests[2]["messages"][-2], {"role": "assistant", "content": "工具结果是 5"})

    def test_v3_does_not_repeat_tools_as_an_agent_loop(self):
        with self.assertRaisesRegex(RuntimeError, "回答|停止"):
            self.exercise("v3-tools", ["计算 2+3"],
                          [tool_answer("fixture-first"), tool_answer("fixture-unexpected-second")])

    def test_v4_iteration_limit_restarts_for_each_task(self):
        result = self.exercise("v4-agent-loop", ["先算 2+3", "再算 2+3"],
                               [tool_answer("fixture-first"), answer("第一任务完成"),
                                tool_answer("fixture-second"), answer("第二任务完成")], limit=2)
        self.assertEqual(len(result.requests), 4)
        self.assertEqual(result.execute.call_count, 2)
        self.assertEqual(result.requests[2]["messages"][-2]["content"], "第一任务完成")
        self.assertEqual(result.output.count("[Agent Loop 1/2]"), 2)

    def test_v5_reuses_workspace_and_exports_on_exit(self):
        result = self.exercise("v5-execution", ["查看 CSV", "列出目录"],
                               [tool_answer("fixture-read", "bash", '{"command":"cat data/temperature.csv"}'), answer("已读取"),
                                tool_answer("fixture-list", "bash", '{"command":"ls"}'), answer("已列出")], limit=2)
        self.assertEqual(len(result.requests), 4)
        first_workspace = result.execute.call_args_list[0].args[1]
        self.assertEqual(first_workspace, result.execute.call_args_list[1].args[1])
        self.assertNotEqual(first_workspace, ROOT)
        result.export.assert_called_once_with(first_workspace)

    def test_cli_rejects_removed_options_before_sdk_or_key_lookup(self):
        for tag in TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                for option in ("--calculator", "--tokens", "--chat", "--demo", "--task", "--record"):
                    with patch.object(sys, "argv", ["agent.py", option]), patch.dict(os.environ, {}, clear=True):
                        with self.assertRaisesRegex(SystemExit, "参数|用法"):
                            stage.agent.cli()

    def test_cli_reports_missing_key(self):
        for tag in TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                with patch.object(sys, "argv", ["agent.py"]), patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(SystemExit, "DEEPSEEK_API_KEY"):
                        stage.agent.cli()

    def test_cli_uses_expected_sdk_configuration(self):
        class FixtureAPIError(Exception):
            pass

        for tag in TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                module = NS(APIError=FixtureAPIError, OpenAI=unittest.mock.Mock(return_value=object()))
                with patch.object(sys, "argv", ["agent.py"]), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-key"}), \
                        patch.dict(sys.modules, {"openai": module}), patch.object(stage.agent, "main") as main:
                    stage.agent.cli()
                module.OpenAI.assert_called_once_with(api_key="fixture-key", base_url="https://api.deepseek.com/beta",
                                                       timeout=45, max_retries=1)
                main.assert_called_once_with(module.OpenAI.return_value)

    def test_ctrl_c_during_sdk_call_ends_without_a_traceback(self):
        class FixtureAPIError(Exception):
            pass

        for tag in TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                module = NS(APIError=FixtureAPIError, OpenAI=unittest.mock.Mock(return_value=object()))
                with patch.object(sys, "argv", ["agent.py"]), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-key"}), \
                        patch.dict(sys.modules, {"openai": module}), \
                        patch.object(stage.agent, "main", side_effect=KeyboardInterrupt()), \
                        contextlib.redirect_stdout(io.StringIO()):
                    stage.agent.cli()


if __name__ == "__main__":
    unittest.main()
