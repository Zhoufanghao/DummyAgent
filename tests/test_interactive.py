"""单文件课堂脚本的离线交互测试；所有模型响应均为 fixture。"""
import ast
import contextlib
import copy
import importlib.util
import io
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = range(6)


def load_agent(version):
    name = f"agent_v{version}"
    specification = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class Message:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, **kwargs):
        message = {"role": "assistant"}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": call.id, "type": "function", "function": {
                    "name": call.function.name, "arguments": call.function.arguments}}
                for call in self.tool_calls]
        return message


def answer(text="单元测试 fixture"):
    probabilities = NS(tokens=["续"], token_logprobs=[-0.2],
                       top_logprobs=[{"续": -0.2, "答": -2.0}])
    return NS(choices=[NS(text=text, logprobs=probabilities, message=Message(text))])


def tool_answer(identifier="fixture-calculator", name="calculator", arguments='{"expression":"2+3"}'):
    call = NS(id=identifier, function=NS(name=name, arguments=arguments))
    return NS(choices=[NS(message=Message(tool_calls=[call]))])


def fake_client(replies=None):
    requests = []
    pending = iter(replies) if replies is not None else None

    def create(**parameters):
        requests.append(copy.deepcopy(parameters))
        return next(pending) if pending is not None else answer()

    return NS(completions=NS(create=create), chat=NS(completions=NS(create=create))), requests


def run_agent(version, inputs=(), replies=None, bash_output="fixture bash output"):
    module = load_agent(version)
    client, requests = fake_client(replies)
    output = io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.redirect_stdout(output))
        stack.enter_context(patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-key"}))
        sdk = stack.enter_context(patch.object(module, "OpenAI", return_value=client))
        keyboard = stack.enter_context(patch("builtins.input", side_effect=[*inputs, EOFError()]))
        bash = None
        if version == 5:
            bash = stack.enter_context(patch.object(module, "run_bash", return_value=bash_output))
        try:
            module.main()
        except EOFError:
            pass
    return NS(module=module, requests=requests, output=output.getvalue(),
              sdk=sdk, keyboard=keyboard, bash=bash)


class InteractiveTests(unittest.TestCase):
    def test_six_scripts_are_independent_and_only_import_libraries(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                path = ROOT / f"agent_v{version}.py"
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported = [alias.name.split(".")[0] for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        imported = [node.module.split(".")[0]]
                    else:
                        continue
                    self.assertLessEqual(set(imported), sys.stdlib_module_names | {"openai"})
                module = load_agent(version)
                for name in ("cli", "parse_args", "execute", "agent_loop", "MAX_ITERATIONS"):
                    self.assertFalse(hasattr(module, name))

    def test_all_scripts_accept_multiple_inputs_and_skip_blanks(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                result = run_agent(version, [" \t ", "自定义第一题", "自定义第二题"])
                self.assertEqual(len(result.requests), 2)
                for index, request in enumerate(result.requests):
                    submitted = request.get("prompt") or request["messages"][-1]["content"]
                    self.assertIn(("自定义第一题", "自定义第二题")[index], submitted)
                self.assertTrue(all(call.args == ("$ ",) for call in result.keyboard.call_args_list))
                self.assertNotIn("Tool Schema", result.output)

    def test_sdk_configuration_and_nonstreaming_settings(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                result = run_agent(version, ["测试问题"])
                result.sdk.assert_called_once_with(api_key="fixture-key", base_url="https://api.deepseek.com/beta",
                                                   timeout=45, max_retries=1)
                request = result.requests[0]
                self.assertEqual(request["model"], os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
                self.assertEqual(request["temperature"], 0)
                self.assertFalse(request.get("stream", False))
                if version >= 2:
                    self.assertEqual(request["extra_body"], {"thinking": {"type": "disabled"}})

    def test_eof_and_ctrl_c_are_handled_by_script_footer(self):
        for version in VERSIONS:
            for ending in (EOFError(), KeyboardInterrupt()):
                with self.subTest(version=version, ending=type(ending).__name__):
                    client, requests = fake_client()
                    sdk = Mock(return_value=client)
                    with patch.dict(sys.modules, {"openai": NS(OpenAI=sdk)}), \
                            patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-key"}), \
                            patch("builtins.input", side_effect=ending), contextlib.redirect_stdout(io.StringIO()):
                        runpy.run_path(str(ROOT / f"agent_v{version}.py"), run_name="__main__")
                    self.assertEqual(requests, [])

    def test_ctrl_c_during_model_call_is_handled_by_script_footer(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                create = Mock(side_effect=KeyboardInterrupt())
                client = NS(completions=NS(create=create), chat=NS(completions=NS(create=create)))
                with patch.dict(sys.modules, {"openai": NS(OpenAI=Mock(return_value=client))}), \
                        patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-key"}), \
                        patch("builtins.input", return_value="问题"), contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(ROOT / f"agent_v{version}.py"), run_name="__main__")
                create.assert_called_once()

    def test_former_commands_are_regular_messages_and_do_not_reset_history(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                result = run_agent(version, [":quit", ":reset", "继续"])
                self.assertEqual(len(result.requests), 3)
                for index, text in enumerate((":quit", ":reset", "继续")):
                    request = result.requests[index]
                    submitted = request.get("prompt") or request["messages"][-1]["content"]
                    self.assertIn(text, submitted)
                if version == 1:
                    self.assertIn(":quit", result.requests[2]["prompt"])
                elif version >= 2:
                    self.assertEqual(result.requests[2]["messages"][1]["content"], ":quit")
                    self.assertEqual(result.requests[2]["messages"][3]["content"], ":reset")

    def test_token_prefixes_are_independent_and_use_api_probabilities(self):
        result = run_agent(0, ["第一段前缀", "第二段前缀"])
        self.assertEqual([request["prompt"] for request in result.requests], ["第一段前缀", "第二段前缀"])
        self.assertEqual(result.requests[0]["max_tokens"], 12)
        self.assertEqual(result.requests[0]["logprobs"], 5)
        self.assertIn("Pr[token | context]", result.output)
        self.assertIn("81.8731%", result.output)

    def test_text_history_contains_user_and_assistant(self):
        result = run_agent(1, ["记住编号 Z987", "编号是什么"], [answer("记住了 Z987"), answer("Z987")])
        self.assertIn("记住编号 Z987", result.requests[1]["prompt"])
        self.assertIn("记住了 Z987", result.requests[1]["prompt"])
        self.assertEqual(result.requests[0]["stop"], ["\n用户："])

    def test_chat_history_contains_roles_and_both_sides(self):
        for version in range(2, 6):
            with self.subTest(version=version):
                result = run_agent(version, ["第一题", "第二题"], [answer("第一题回答"), answer("第二题回答")])
                messages = result.requests[1]["messages"]
                self.assertEqual([message["role"] for message in messages], ["system", "user", "assistant", "user"])
                self.assertEqual(messages[2]["content"], "第一题回答")

    def test_v3_fills_tool_result_and_makes_only_one_final_request(self):
        result = run_agent(3, ["计算2+3", "上次答案"],
                           [tool_answer("fixture-one"), answer("5"), answer("上次是5")])
        self.assertEqual(len(result.requests), 3)
        observation = result.requests[1]["messages"][-1]
        self.assertEqual(observation, {"role": "tool", "tool_call_id": "fixture-one", "content": "5"})
        self.assertNotIn("tools", result.requests[1])
        self.assertEqual(result.requests[2]["messages"][-2], {"role": "assistant", "content": "5"})
        self.assertIn("Tool Result", result.output)


if __name__ == "__main__":
    unittest.main()
