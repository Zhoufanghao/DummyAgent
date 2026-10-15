"""Calculator 仅属于 v3/v4；直接测试各阶段自己的工具实现。"""
from types import SimpleNamespace as NS
import unittest

from test_interactive import load_stage


CALCULATOR_TAGS = ("v3-tools", "v4-agent-loop")


class CalculatorTests(unittest.TestCase):
    def test_arithmetic(self):
        for tag in CALCULATOR_TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                self.assertEqual(stage.tools.calculator("(12+3)*4"), 60)
                self.assertEqual(stage.tools.calculator("-2**2"), -4)
                self.assertEqual(stage.tools.calculator("1/4"), 0.25)
                self.assertEqual(stage.tools.calculator("2**8"), 256)

    def test_reject_code_and_resource_abuse(self):
        for tag in CALCULATOR_TAGS:
            with load_stage(tag) as stage:
                for expression in ("__import__('os').system('id')", "2**99999", "True", "[1]*100", "1e999", "3j",
                                   "9**9", "+" * 15 + "1"):
                    with self.subTest(tag=tag, expression=expression), self.assertRaises((ValueError, SyntaxError)):
                        stage.tools.calculator(expression)

    def test_bad_arguments_are_observations(self):
        for tag in CALCULATOR_TAGS:
            with load_stage(tag) as stage:
                for name, arguments in (("other", "{}"), ("bash", '{"command":"ls"}'),
                                        ("calculator", "null"), ("calculator", "{bad"),
                                        ("calculator", '{"expression":"1/0"}'),
                                        ("calculator", '{"expression":"1","extra":1}'),
                                        ("calculator", '{"expression":true}'),
                                        ("calculator", "x" * 8193)):
                    with self.subTest(tag=tag, name=name, arguments=arguments[:50]):
                        call = NS(function=NS(name=name, arguments=arguments))
                        result = stage.tools.execute(call)
                        self.assertFalse(result["ok"])
                        self.assertTrue(result["error"])

    def test_success_matches_schema_and_returns_value(self):
        for tag in CALCULATOR_TAGS:
            with self.subTest(tag=tag), load_stage(tag) as stage:
                self.assertEqual([tool["function"]["name"] for tool in stage.tools.TOOLS], ["calculator"])
                call = NS(function=NS(name="calculator", arguments='{"expression":"2+3"}'))
                self.assertEqual(stage.tools.execute(call), {"ok": True, "value": 5})
                self.assertFalse(hasattr(stage.tools, "BASH"))


if __name__ == "__main__":
    unittest.main()
