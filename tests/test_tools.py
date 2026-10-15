"""两个工具阶段各自内置普通 Python calculator，不依赖 tools.py。"""
import unittest

from test_interactive import load_agent


class CalculatorTests(unittest.TestCase):
    def test_each_stage_computes_arithmetic(self):
        for version in (3, 4):
            with self.subTest(version=version):
                module = load_agent(version)
                self.assertEqual(module.calculator("(12+3)*4"), 60)
                self.assertEqual(module.calculator("-2**2"), -4)
                self.assertEqual(module.calculator("1/4"), 0.25)

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
