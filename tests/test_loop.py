"""循环必须传回真实观察；用明确标注的单元fixture验证停止边界。"""
import contextlib
import io
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import agent


class Message:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, **kwargs):
        return {"role": "assistant", "tool_calls": [{"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                 for c in self.tool_calls]}


def response(reason, message):
    return NS(choices=[NS(finish_reason=reason, message=message)])


class LoopTests(unittest.TestCase):
    def args(self, limit=3):
        return NS(demo=True, prompt=None, tokens=False, chat=False, calculator=True, task=None,
                  model="unit-test-fixture", temperature=0, max_iterations=limit)

    def client(self):
        return NS(chat=NS(completions=NS(create=object())))

    def test_observation_is_in_next_request(self):
        tool = NS(id="test-call-1", function=NS(name="calculator", arguments='{"expression":"2+3"}'))
        replies = iter([response("stop", Message("plain fixture")),
                        response("tool_calls", Message(tool_calls=[tool])),
                        response("stop", Message("5"))])
        observed = []
        def fake_call(method, **params):
            if len(observed) == 2:
                self.assertEqual(params["messages"][-1]["tool_call_id"], "test-call-1")
                self.assertIn('"value": 5', params["messages"][-1]["content"])
            observed.append(True)
            return next(replies)
        with patch.object(agent, "call", side_effect=fake_call), contextlib.redirect_stdout(io.StringIO()):
            agent.main(self.client(), self.args())
        self.assertEqual(len(observed), 3)

    def test_iteration_limit_does_not_report_completion(self):
        tool = NS(id="test-call-1", function=NS(name="calculator", arguments='{"expression":"2+3"}'))
        with patch.object(agent, "call", side_effect=[response("stop", Message("plain")),
                          response("tool_calls", Message(tool_calls=[tool]))]), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "最大迭代"):
            agent.main(self.client(), self.args(limit=1))

    def test_truncation_is_not_a_final_answer(self):
        with patch.object(agent, "call", side_effect=[response("stop", Message("plain")),
                          response("length", Message("unfinished"))]), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "截断"):
            agent.main(self.client(), self.args())


if __name__ == "__main__":
    unittest.main()
