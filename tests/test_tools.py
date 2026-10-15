"""两个工具阶段各自内置普通 Python calculator，不依赖 tools.py。"""
import json
import unittest

from test_interactive import answer, load_agent, run_agent, tool_answer


class CalculatorTests(unittest.TestCase):
    def test_each_stage_computes_arithmetic(self):
        for version in (3, 4):
            with self.subTest(version=version):
                module = load_agent(version)
                self.assertEqual(module.calculator("(12+3)*4"), 60)
                self.assertEqual(module.calculator("-2**2"), -4)
                self.assertEqual(module.calculator("1/4"), 0.25)

    def test_python_power_precedence(self):
        examples = {"2**3": 8, "-2**2": -4, "2**3**2": 512,
                    "2**-2": 0.25, "1.5**2 + 1": 3.25}
        for version in (3, 4):
            for expression, expected in examples.items():
                with self.subTest(version=version, expression=expression):
                    self.assertEqual(load_agent(version).calculator(expression), expected)

    def test_power_expression_is_calculated_and_fed_back(self):
        expression = "((12345 * 6789 - 9876 * 5432) / 3 + 2468 * 1357) * 7 - 123**3"
        expected = 91964802
        for version in (3, 4):
            with self.subTest(version=version):
                result = run_agent(version, [expression], [
                    tool_answer(arguments=json.dumps({"expression": expression})), answer(str(expected))])
                observation = result.requests[1]["messages"][-1]
                self.assertEqual(observation["role"], "tool")
                self.assertAlmostEqual(float(observation["content"]), expected)
                self.assertIn("Python → Tool Result：", result.output)

    def test_schema_names_the_local_calculator_argument(self):
        for version in (3, 4):
            with self.subTest(version=version):
                function = load_agent(version).CALCULATOR_TOOL["function"]
                self.assertEqual(function["name"], "calculator")
                self.assertEqual(function["parameters"]["required"], ["expression"])
                self.assertEqual(function["parameters"]["properties"]["expression"]["type"], "string")

    def test_python_calculation_errors_propagate(self):
        for version in (3, 4):
            with self.subTest(version=version), self.assertRaises(ZeroDivisionError):
                load_agent(version).calculator("1/0")


if __name__ == "__main__":
    unittest.main()
